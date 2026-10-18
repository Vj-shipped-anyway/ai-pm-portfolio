"""Step 4 - The fix: SchemaWatch.

For every schema release, SchemaWatch does five things before the release reaches the agent:

  1. Structural diff -> classify each change: breaking, non-breaking or behavior-risk,
     with a reason a tool owner can read.
  2. Description heuristic -> extract numbers and units from parameter descriptions and flag
     a change (a unit swap leaves the structure untouched).
  3. Replay -> run the recorded calls against the new schema with a small strict validator
     (standard library only) and count the calls that would break, per tool.
  4. Blast radius -> rank tools by the recorded calls a release breaks or silently changes.
  5. Release gate -> BLOCK, REVIEW or ALLOW, with the reason.

It is then scored against the change ledger and the per-call truth from data/_generate.py.
The truth is known because the data is synthetic. There is no model anywhere in this step:
the diff, the heuristic, the validator and the gate are plain rules.

KNOWN LIMIT, left in on purpose: a change in meaning that carries no number and no unit
("inclusive" -> "exclusive", "per account" -> "per customer") is not detected. The ledger has
3 of them. The script prints them, with the calls they leave misread.

Run (from src/):
    python3 step_04_with_schemawatch.py

Output: a readable report, plus CSVs and out/step_04_summary.json in src/out/.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import Counter, defaultdict

from step_01_no_monitoring import OUT_DIR, load_all
from step_02_hash_and_version_check import score_releases

CHANGES_PER_QUARTER = 12     # MODELED assumption: schema changes per quarter across a 28-tool estate
RENAME_SIMILARITY = 0.5      # description overlap needed to call a removed+added pair a rename
DECISION_RANK = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}


# ---------------------------------------------------------------------------
# 1. A small strict validator (standard library only)
# ---------------------------------------------------------------------------
# Supported: type (string, integer, number, boolean, array, object), enum, required,
# minimum, maximum, maxLength, items.type / items.enum, and additionalProperties false
# (unknown keys are rejected). Not supported: pattern, format, oneOf/anyOf, nested objects.
def _is_int(v) -> bool:
    return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer())


def _type_ok(v, t: str) -> bool:
    if t == "string":
        return isinstance(v, str)
    if t == "integer":
        return _is_int(v)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "array":
        return isinstance(v, list)
    if t == "object":
        return isinstance(v, dict)
    return True


def _check_value(name: str, v, spec: dict) -> list:
    t = spec.get("type")
    if t and not _type_ok(v, t):
        return [f"type_mismatch:{name}:expected {t}, got {type(v).__name__}"]
    errs = []
    if "enum" in spec and v not in spec["enum"]:
        errs.append(f"enum_violation:{name}:{v!r} is not an allowed value")
    if t in ("integer", "number"):
        if "minimum" in spec and v < spec["minimum"]:
            errs.append(f"below_minimum:{name}:{v} < {spec['minimum']}")
        if "maximum" in spec and v > spec["maximum"]:
            errs.append(f"above_maximum:{name}:{v} > {spec['maximum']}")
    if t == "string" and "maxLength" in spec and len(v) > spec["maxLength"]:
        errs.append(f"too_long:{name}:{len(v)} > {spec['maxLength']}")
    if t == "array" and "items" in spec:
        for i, x in enumerate(v):
            errs.extend(_check_value(f"{name}[{i}]", x, spec["items"]))
    return errs


def strict_validate(schema: dict, args: dict) -> list:
    """Return a list of violations; an empty list means the call is valid."""
    params = schema["parameters"]
    props = params["properties"]
    errs = [f"unknown_parameter:{k}:not in the schema" for k in args if k not in props]
    errs += [f"missing_required:{r}:required but absent" for r in params.get("required", [])
             if r not in args]
    for k, v in args.items():
        if k in props:
            errs.extend(_check_value(k, v, props[k]))
    return errs


# ---------------------------------------------------------------------------
# 2. Description heuristic: numbers and units
# ---------------------------------------------------------------------------
_UNITS = {
    "USD": ["us dollars", "us dollar", "dollars", "dollar", "usd"],
    "EUR": ["euros", "euro", "eur"],
    "GBP": ["pounds sterling", "pounds", "gbp"],
    "cents": ["cents", "cent"],
    "ms": ["milliseconds", "millisecond", "msec", "ms"],
    "s": ["seconds", "second", "secs", "sec"],
    "min": ["minutes", "minute", "mins"],
    "h": ["hours", "hour", "hrs"],
    "d": ["days", "day"],
    "wk": ["weeks", "week"],
    "mo": ["months", "month"],
    "yr": ["years", "year"],
    "bps": ["basis points", "basis point", "bps"],
    "pct": ["percentage", "percent", "per cent"],
    "mi": ["miles", "mile"],
    "km": ["kilometers", "kilometres", "kilometer", "kilometre", "km"],
    "bytes": ["bytes"],
}
_ALIAS = {alias: canon for canon, aliases in _UNITS.items() for alias in aliases}
_WORDS = sorted(_ALIAS, key=len, reverse=True)
_UNIT_RE = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in _WORDS) + r")(?![a-z0-9])|%")
_NUM_RE = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?")


def _norm_number(s: str) -> str:
    s = s.replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def description_signature(text: str) -> frozenset:
    """The (number, unit) pairs a description states. A number followed by a unit is one pair;
    a lone number or a lone unit is a pair with None. Number words ('seven') are not parsed."""
    t = text.lower()
    units = [(m.start(), m.end(), "pct" if m.group() == "%" else _ALIAS[m.group()])
             for m in _UNIT_RE.finditer(t)]
    used, sig = set(), set()
    for m in _NUM_RE.finditer(t):
        unit = None
        for i, (us, _ue, canon) in enumerate(units):
            if i not in used and us >= m.end() and t[m.end():us].strip() == "" and us - m.end() <= 2:
                unit = canon
                used.add(i)
                break
        sig.add((_norm_number(m.group()), unit))
    for i, (_us, _ue, canon) in enumerate(units):
        if i not in used:
            sig.add((None, canon))
    return frozenset(sig)


def fmt_signature(sig: frozenset) -> str:
    parts = sorted(f"{n} {u}".strip() if n else (u or "") for n, u in sig)
    return ", ".join(parts) if parts else "none"


# ---------------------------------------------------------------------------
# 3. Structural diff and classification
# ---------------------------------------------------------------------------
def _finding(kind, param, cls, reason, old="", new="", value="") -> dict:
    return {"kind": kind, "param": param, "class": cls, "reason": reason, "old": old, "new": new,
            "value": value}


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _detect_renames(old_props: dict, new_props: dict, removed: list, added: list) -> list:
    cands = []
    for r in removed:
        for a in added:
            if old_props[r]["type"] != new_props[a]["type"]:
                continue
            ta, tb = _tokens(old_props[r]["description"]), _tokens(new_props[a]["description"])
            score = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
            cands.append((score, r, a))
    cands.sort(key=lambda x: (-x[0], x[1], x[2]))
    pairs, used_r, used_a = [], set(), set()
    for score, r, a in cands:
        if score >= RENAME_SIMILARITY and r not in used_r and a not in used_a:
            pairs.append((r, a))
            used_r.add(r)
            used_a.add(a)
    return pairs


def _enum_of(spec: dict):
    if "enum" in spec:
        return spec["enum"]
    return spec.get("items", {}).get("enum")


def _describe(param: str, old_text: str, new_text: str, use_heuristic: bool) -> dict:
    so, sn = description_signature(old_text), description_signature(new_text)
    if use_heuristic and so != sn:
        return _finding("unit_or_number_changed", param, "behavior_risk",
                        f"numbers or units in the description changed: [{fmt_signature(so)}] -> "
                        f"[{fmt_signature(sn)}]. The structure is identical, so validation still "
                        f"passes calls that now mean something different.", old_text, new_text)
    return _finding("description_reworded", param, "non_breaking",
                    "wording changed; no number or unit changed", old_text, new_text)


def diff_schemas(old: dict, new: dict, use_heuristic: bool = True) -> list:
    """Compare two revisions of one tool and return classified findings."""
    out = []
    if old.get("description") != new.get("description"):
        out.append(_describe("", old["description"], new["description"], use_heuristic))
    op, np_ = old["parameters"]["properties"], new["parameters"]["properties"]
    oreq = set(old["parameters"].get("required", []))
    nreq = set(new["parameters"].get("required", []))
    removed = [n for n in op if n not in np_]
    added = [n for n in np_ if n not in op]
    renames = _detect_renames(op, np_, removed, added)
    ren_old, ren_new = {o for o, _ in renames}, {n for _, n in renames}
    for o, n in renames:
        extra = f" `{n}` is also required, so calls without it fail." if n in nreq else ""
        out.append(_finding("param_renamed", o, "breaking",
                            f"`{o}` is gone and `{n}` appears with the same type and description. "
                            f"Any call that still sends `{o}` is rejected.{extra}", o, n))
    for o in removed:
        if o not in ren_old:
            out.append(_finding("param_removed", o, "breaking",
                                f"`{o}` was removed. Calls that send it are rejected.", o, ""))
    for n in added:
        if n in ren_new:
            continue
        if n in nreq:
            out.append(_finding("required_added", n, "breaking",
                                f"new required field `{n}`. Every existing call lacks it, so every "
                                f"existing call fails.", "", n))
        else:
            out.append(_finding("optional_added", n, "non_breaking",
                                f"new optional field `{n}`. Existing calls are unaffected.", "", n))
    for name, spec in np_.items():
        if name not in op:
            continue
        o = op[name]
        if name in nreq and name not in oreq:
            out.append(_finding("required_added", name, "breaking",
                                f"`{name}` became required. Calls that omit it fail.", "optional",
                                "required"))
        if name in oreq and name not in nreq:
            out.append(_finding("required_relaxed", name, "non_breaking",
                                f"`{name}` is no longer required.", "required", "optional"))
        if o.get("type") != spec.get("type"):
            ot, nt = o.get("type"), spec.get("type")
            if (ot, nt) == ("integer", "number"):
                out.append(_finding("type_changed", name, "non_breaking",
                                    f"`{name}` widened integer -> number. Every value that was valid "
                                    f"still is.", ot, nt))
            elif (ot, nt) == ("number", "integer"):
                out.append(_finding("type_changed", name, "breaking",
                                    f"`{name}` narrowed number -> integer. Fractional values are now "
                                    f"rejected.", ot, nt))
            else:
                out.append(_finding("type_changed", name, "breaking",
                                    f"`{name}` changed {ot} -> {nt}. Values of the old type are "
                                    f"rejected.", ot, nt))
        oe, ne = _enum_of(o), _enum_of(spec)
        if oe is not None and ne is not None:
            for v in oe:
                if v not in ne:
                    out.append(_finding("enum_value_removed", name, "breaking",
                                        f"`{v}` was removed from `{name}`. Calls that send it are "
                                        f"rejected.", v, "", v))
            for v in ne:
                if v not in oe:
                    out.append(_finding("enum_value_added", name, "non_breaking",
                                        f"`{v}` was added to `{name}`. Existing calls still validate.",
                                        "", v, v))
        if o.get("default") != spec.get("default"):
            out.append(_finding("default_changed", name, "behavior_risk",
                                f"default of `{name}` changed from {json.dumps(o.get('default'))} to "
                                f"{json.dumps(spec.get('default'))}. Calls that omit it get the new "
                                f"value and still pass validation.", json.dumps(o.get("default")),
                                json.dumps(spec.get("default"))))
        if o.get("description") != spec.get("description"):
            out.append(_describe(name, o["description"], spec["description"], use_heuristic))
    return out


# ---------------------------------------------------------------------------
# 4. Replay, blast radius, gate
# ---------------------------------------------------------------------------
def _reason_mix(errors_by_call: dict) -> dict:
    return dict(Counter(e.split(":")[0] for errs in errors_by_call.values() for e in errs[:1]))


def evaluate_release(data: dict, rel: dict, use_heuristic: bool = True) -> dict:
    tool = rel["tool"]
    old = data["schemas"][tool][rel["from_rev"]]["schema"]
    new = data["schemas"][tool][rel["to_rev"]]["schema"]
    calls = data["calls_by_tool"].get(tool, [])
    findings = diff_schemas(old, new, use_heuristic)
    prev = {c["call_id"]: strict_validate(old, c["args"]) for c in calls}
    cur = {c["call_id"]: strict_validate(new, c["args"]) for c in calls}
    newly = {cid: errs for cid, errs in cur.items() if errs and not prev[cid]}
    at_risk: set = set()
    for f in findings:
        if f["class"] != "behavior_risk":
            f["at_risk_calls"] = 0
            continue
        p = f["param"]
        if f["kind"] == "default_changed":
            ids = {c["call_id"] for c in calls if p not in c["args"] and not cur[c["call_id"]]}
        else:
            ids = {c["call_id"] for c in calls if (p == "" or p in c["args"]) and not cur[c["call_id"]]}
        f["at_risk_calls"] = len(ids)
        at_risk |= ids
    if newly:
        mix = _reason_mix(newly)
        why = ", ".join(f"{k.replace('_', ' ')} x{v}" for k, v in sorted(mix.items(), key=lambda kv: -kv[1]))
        decision = "BLOCK"
        reason = (f"{len(newly)} of {len(calls)} recorded calls to {tool} would fail strict "
                  f"validation ({why}). Hold the release until the owner and the agent team agree a fix.")
    elif any(f["class"] == "breaking" for f in findings):
        decision = "REVIEW"
        reason = ("breaking change by structure, but no recorded call exercises it. Confirm with the "
                  "owner before it ships.")
    elif any(f["class"] == "behavior_risk" for f in findings):
        decision = "REVIEW"
        reason = (f"{len(at_risk)} recorded calls still validate but would mean something different. "
                  f"Validation cannot see this; a person has to confirm the new meaning.")
    else:
        decision = "ALLOW"
        reason = "only non-breaking changes. Notify the agent team; nothing to hold."
    return {"release_id": rel["release_id"], "tool": tool, "from_rev": rel["from_rev"],
            "to_rev": rel["to_rev"], "released_at": rel["released_at"], "bumped": rel["bumped"],
            "declared_before": rel["declared_before"], "declared_after": rel["declared_after"],
            "findings": findings, "n_calls": len(calls), "newly_broken": sorted(newly),
            "newly_broken_errors": {cid: newly[cid] for cid in sorted(newly)},
            "at_risk": sorted(at_risk), "decision": decision, "reason": reason}


def should_decide(data: dict, rel: dict) -> str:
    """What the gate ought to say, derived from the ledger and the per-call truth."""
    broken = any(data["truth"][c["call_id"]]["first_break_rev"] == rel["to_rev"]
                 for c in data["calls_by_tool"].get(rel["tool"], []))
    if broken:
        return "BLOCK"
    if any(ch["true_class"] in ("breaking", "behavior_risk") for ch in rel["changes"]):
        return "REVIEW"
    return "ALLOW"


# ---------------------------------------------------------------------------
# 5. Scoring against the ledger and the truth
# ---------------------------------------------------------------------------
ACCEPT = {
    "param_renamed": {"param_renamed"}, "param_removed": {"param_removed"},
    "required_added": {"required_added"}, "optional_added": {"optional_added"},
    "type_changed": {"type_changed"}, "enum_value_removed": {"enum_value_removed"},
    "enum_value_added": {"enum_value_added"}, "default_changed": {"default_changed"},
    "unit_changed": {"unit_or_number_changed", "description_reworded"},
    "meaning_changed": {"unit_or_number_changed", "description_reworded"},
    "description_reworded": {"unit_or_number_changed", "description_reworded"},
}


def match_to_ledger(data: dict, evaluated: list) -> tuple:
    """Pair each ledger change with the finding that describes it. Returns (rows, spurious)."""
    by_rel = {e["release_id"]: e["findings"] for e in evaluated}
    used: set = set()
    rows = []
    for ch in data["ledger"]:
        rid = f"{ch['tool']}@{ch['to_rev']}"
        hit = None
        for i, f in enumerate(by_rel[rid]):
            if (rid, i) in used or f["kind"] not in ACCEPT[ch["change_type"]] or f["param"] != ch["param"]:
                continue
            if ch["change_type"] == "enum_value_removed" and f["value"] != ch["old_value"]:
                continue
            if ch["change_type"] == "enum_value_added" and f["value"] != ch["new_value"]:
                continue
            hit = (i, f)
            break
        if hit:
            used.add((rid, hit[0]))
        f = hit[1] if hit else None
        rows.append({"change_id": ch["change_id"], "release_id": rid, "tool": ch["tool"],
                     "change_type": ch["change_type"], "param": ch["param"],
                     "true_class": ch["true_class"], "semantic_kind": ch["semantic_kind"],
                     "predicted_kind": f["kind"] if f else "undetected",
                     "predicted_class": f["class"] if f else "undetected",
                     "ok": bool(f and f["class"] == ch["true_class"]),
                     "reason": f["reason"] if f else "no finding matches this change"})
    spurious = [(rid, f["kind"], f["param"]) for rid, fs in by_rel.items()
                for i, f in enumerate(fs) if (rid, i) not in used]
    return rows, spurious


def analyze(data: dict | None = None) -> dict:
    """Everything the report, the app and the demo need, computed once."""
    data = data or load_all()
    truth, ledger = data["truth"], data["ledger"]
    evaluated = [evaluate_release(data, r) for r in data["releases"]]
    rel_by_id = {r["release_id"]: r for r in data["releases"]}
    for e in evaluated:
        e["should"] = should_decide(data, rel_by_id[e["release_id"]])
        e["true_newly_broken"] = sum(1 for c in data["calls_by_tool"].get(e["tool"], [])
                                     if truth[c["call_id"]]["first_break_rev"] == e["to_rev"])
    rows, spurious = match_to_ledger(data, evaluated)
    ablated = [evaluate_release(data, r, use_heuristic=False) for r in data["releases"]]
    abl_rows, _ = match_to_ledger(data, ablated)

    # classification
    correct = sum(1 for r in rows if r["ok"])
    cm = {t: Counter() for t in ("breaking", "non_breaking", "behavior_risk")}
    for r in rows:
        cm[r["true_class"]][r["predicted_class"]] += 1

    # semantic recall
    sem = [r for r in rows if r["semantic_kind"] != "none"]
    unit = [r for r in sem if r["semantic_kind"] == "unit_signal"]
    nosig = [r for r in sem if r["semantic_kind"] == "no_signal"]
    flagged = lambda r: r["predicted_kind"] == "unit_or_number_changed"           # noqa: E731
    reworded = [r for r in rows if r["change_type"] == "description_reworded"]

    # call-level replay vs truth, against the latest revision of each tool
    tp = fp = fn = tn = attr_ok = 0
    pred_broken: set = set()
    for c in data["calls"]:
        revs = data["revs"][c["tool"]]
        first = ""
        for rv in revs[1:]:
            if strict_validate(data["schemas"][c["tool"]][rv]["schema"], c["args"]):
                first = rv
                break
        t = truth[c["call_id"]]
        pb = bool(first)
        if pb:
            pred_broken.add(c["call_id"])
        tp += pb and t["broken"]
        fp += pb and not t["broken"]
        fn += (not pb) and bool(t["broken"])
        tn += (not pb) and not t["broken"]
        attr_ok += first == t["first_break_rev"]
    v1_valid = sum(1 for c in data["calls"]
                   if not strict_validate(data["schemas"][c["tool"]]["v1"]["schema"], c["args"]))

    # silent (valid but different) calls: flagged vs truth
    flagged_silent = {cid for e in evaluated for cid in e["at_risk"]} - pred_broken
    truth_silent = {cid for cid, t in truth.items()
                    if not t["broken"] and (t["misread_unit"] or t["misread_meaning"] or t["shifted_default"])}
    meaning_only = {cid for cid in truth_silent
                    if truth[cid]["misread_meaning"] and not truth[cid]["misread_unit"]
                    and not truth[cid]["shifted_default"]}
    sil_tp = len(flagged_silent & truth_silent)

    # gate
    gate_ok = sum(1 for e in evaluated if e["decision"] == e["should"])
    gate_miss = [e for e in evaluated if e["decision"] != e["should"]]

    # protection: which truth-affected calls are still hit once the gate holds releases?
    release_of = {ch["change_id"]: f"{ch['tool']}@{ch['to_rev']}" for ch in ledger}
    dec = {e["release_id"]: e["decision"] for e in evaluated}
    bumped = {e["release_id"]: e["bumped"] for e in evaluated}
    affected = {cid: t["causes"] for cid, t in truth.items()
                if t["broken"] or t["misread_unit"] or t["misread_meaning"] or t["shifted_default"]}
    still_sw = [cid for cid, cs in affected.items() if any(dec[release_of[c]] == "ALLOW" for c in cs)]
    still_ver = [cid for cid, cs in affected.items() if any(not bumped[release_of[c]] for c in cs)]
    n_changes = len(ledger)
    per_wo = len(affected) / n_changes
    per_w = len(still_sw) / n_changes

    # per-tool blast radius (latest revision)
    tool_rows = []
    for tool in data["tools"]:
        calls = data["calls_by_tool"].get(tool, [])
        ids = {c["call_id"] for c in calls}
        wb = len(ids & pred_broken)
        ar = len(ids & flagged_silent)
        worst = "ALLOW"
        for e in evaluated:
            if e["tool"] == tool and DECISION_RANK[e["decision"]] > DECISION_RANK[worst]:
                worst = e["decision"]
        tool_rows.append({"tool": tool, "calls": len(calls), "would_break": wb, "at_risk": ar,
                          "affected": wb + ar, "share_pct": round(100 * (wb + ar) / len(calls), 1) if calls else 0.0,
                          "decision": worst, "releases": sum(1 for e in evaluated if e["tool"] == tool)})
    tool_rows.sort(key=lambda r: (-r["affected"], -r["would_break"], r["tool"]))
    for i, r in enumerate(tool_rows, 1):
        r["rank"] = i

    summary = {
        "tools": len(data["tools"]), "releases": len(evaluated), "changes": n_changes,
        "calls": len(data["calls"]), "v1_valid_calls": v1_valid,
        "class_correct": correct, "class_total": len(rows),
        "class_acc_pct": round(100 * correct / len(rows), 1),
        "class_correct_no_heuristic": sum(1 for r in abl_rows if r["ok"]),
        "class_acc_no_heuristic_pct": round(100 * sum(1 for r in abl_rows if r["ok"]) / len(abl_rows), 1),
        "spurious_findings": len(spurious),
        "confusion": {k: dict(v) for k, v in cm.items()},
        "replay_tp": tp, "replay_fp": fp, "replay_fn": fn, "replay_tn": tn,
        "replay_true_broken": tp + fn, "replay_pred_broken": tp + fp,
        "replay_precision_pct": round(100 * tp / (tp + fp), 1) if tp + fp else 0.0,
        "replay_recall_pct": round(100 * tp / (tp + fn), 1) if tp + fn else 0.0,
        "attribution_ok": attr_ok,
        "semantic_total": len(sem), "semantic_caught": sum(1 for r in sem if flagged(r)),
        "semantic_recall_pct": round(100 * sum(1 for r in sem if flagged(r)) / len(sem), 1),
        "unit_total": len(unit), "unit_caught": sum(1 for r in unit if flagged(r)),
        "nosignal_total": len(nosig), "nosignal_caught": sum(1 for r in nosig if flagged(r)),
        "reworded_total": len(reworded), "reworded_false_flags": sum(1 for r in reworded if flagged(r)),
        "silent_truth": len(truth_silent), "silent_flagged": len(flagged_silent),
        "silent_tp": sil_tp, "silent_fp": len(flagged_silent - truth_silent),
        "silent_recall_pct": round(100 * sil_tp / len(truth_silent), 1) if truth_silent else 0.0,
        "silent_precision_pct": round(100 * sil_tp / len(flagged_silent), 1) if flagged_silent else 0.0,
        "limit_changes": len(nosig), "limit_calls": len(meaning_only),
        "gate_ok": gate_ok, "gate_total": len(evaluated),
        "gate_acc_pct": round(100 * gate_ok / len(evaluated), 1),
        "gate_counts": dict(Counter(e["decision"] for e in evaluated)),
        "gate_needs_action": sum(1 for e in evaluated if e["should"] != "ALLOW"),
        "gate_caught": sum(1 for e in evaluated if e["should"] != "ALLOW" and e["decision"] != "ALLOW"),
        "gate_false_review": sum(1 for e in gate_miss if e["decision"] == "REVIEW" and e["should"] == "ALLOW"),
        "gate_missed": sum(1 for e in gate_miss if e["decision"] == "ALLOW" and e["should"] != "ALLOW"),
        "affected_without": len(affected), "affected_with": len(still_sw),
        "affected_version_only": len(still_ver),
        "per_change_without": round(per_wo, 2), "per_change_with": round(per_w, 2),
        "changes_per_quarter": CHANGES_PER_QUARTER,
        "utility_per_quarter": round((per_wo - per_w) * CHANGES_PER_QUARTER, 0),
        "utility_sensitivity": {str(n): round((per_wo - per_w) * n, 0) for n in (6, 12, 24, n_changes)},
        "top_blast": [{k: r[k] for k in ("rank", "tool", "calls", "would_break", "at_risk", "decision")}
                      for r in tool_rows[:5]],
    }
    return {"data": data, "evaluated": evaluated, "ledger_rows": rows, "spurious": spurious,
            "tool_rows": tool_rows, "gate_miss": gate_miss, "summary": summary,
            "pred_broken": pred_broken, "flagged_silent": flagged_silent,
            "truth_silent": truth_silent, "meaning_only": meaning_only}


# ---------------------------------------------------------------------------
# Self-checks (run before the report)
# ---------------------------------------------------------------------------
def selftest() -> int:
    n = 0
    s = {"parameters": {"properties": {"a": {"type": "integer", "minimum": 1},
                                       "b": {"type": "string", "enum": ["x", "y"]}},
                        "required": ["a"]}}
    assert strict_validate(s, {"a": 2, "b": "x"}) == []
    assert strict_validate(s, {"a": 2.0}) == []
    assert strict_validate(s, {"a": 2.5})[0].startswith("type_mismatch")
    assert strict_validate(s, {"a": True})[0].startswith("type_mismatch")
    assert strict_validate(s, {"b": "x"})[0].startswith("missing_required")
    assert strict_validate(s, {"a": 1, "c": 1})[0].startswith("unknown_parameter")
    assert strict_validate(s, {"a": 1, "b": "z"})[0].startswith("enum_violation")
    assert strict_validate(s, {"a": 0})[0].startswith("below_minimum")
    n += 8
    sig = description_signature
    assert sig("Wire amount in US dollars.") == sig("Wire amount in USD.")
    assert sig("Maximum wait, in seconds.") != sig("Maximum wait, in milliseconds.")
    assert sig("expires after 7 days") != sig("expires after seven days")     # known weakness
    assert sig("up to 500 items") == sig("Up to 500 items.")
    assert sig("rate of 5%") != sig("rate of 5 basis points")
    n += 5
    old = {"description": "d", "parameters": {"properties": {"p": {"type": "string", "description": "x"}},
                                              "required": []}}
    new = {"description": "d", "parameters": {"properties": {"p": {"type": "string", "description": "x"}},
                                              "required": ["p"]}}
    assert diff_schemas(old, new)[0]["kind"] == "required_added"       # optional -> required
    assert diff_schemas(new, old)[0]["kind"] == "required_relaxed"     # required -> optional
    n += 2
    return n


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def write_outputs(a: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_04_findings.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["release_id", "kind", "param", "class", "at_risk_calls", "reason"])
        for e in a["evaluated"]:
            for x in e["findings"]:
                w.writerow([e["release_id"], x["kind"], x["param"], x["class"], x["at_risk_calls"], x["reason"]])
    with open(OUT_DIR / "step_04_release_gate.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["release_id", "bumped", "n_calls", "would_break_predicted", "would_break_true",
                    "at_risk_calls", "gate", "should", "reason"])
        for e in a["evaluated"]:
            w.writerow([e["release_id"], int(e["bumped"]), e["n_calls"], len(e["newly_broken"]),
                        e["true_newly_broken"], len(e["at_risk"]), e["decision"], e["should"], e["reason"]])
    with open(OUT_DIR / "step_04_tool_blast_radius.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "tool", "calls", "would_break", "at_risk", "affected", "share_pct", "gate"])
        for r in a["tool_rows"]:
            w.writerow([r["rank"], r["tool"], r["calls"], r["would_break"], r["at_risk"], r["affected"],
                        r["share_pct"], r["decision"]])
    with open(OUT_DIR / "step_04_classification_vs_ledger.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["change_id", "release_id", "change_type", "param", "true_class", "predicted_kind",
                    "predicted_class", "ok"])
        for r in a["ledger_rows"]:
            w.writerow([r["change_id"], r["release_id"], r["change_type"], r["param"], r["true_class"],
                        r["predicted_kind"], r["predicted_class"], int(r["ok"])])
    with open(OUT_DIR / "step_04_summary.json", "w") as f:
        json.dump(a["summary"], f, indent=2)


def main() -> None:
    checks = selftest()
    a = analyze()
    s = a["summary"]
    write_outputs(a)

    print("\n" + "=" * 78)
    print("Step 4 - SchemaWatch: diff, classify, replay, rank, gate")
    print("=" * 78)
    print(f"\nSelf-checks passed: {checks}. Validator accepts {s['v1_valid_calls']:,} of {s['calls']:,} "
          f"recorded calls under v1 (the generator promised all of them).")
    print("No model is used in this step. Everything is a rule you can read.\n")

    print("RELEASE GATE (one row per schema release)")
    print(f"{'release':<34} {'bump':>4} {'break':>5} {'risk':>5} {'gate':>7} {'ought':>7}")
    print(f"{'-' * 34} {'-' * 4} {'-' * 5} {'-' * 5} {'-' * 7} {'-' * 7}")
    for e in sorted(a["evaluated"], key=lambda x: (-DECISION_RANK[x["decision"]], -len(x["newly_broken"]), x["release_id"])):
        flag = "" if e["decision"] == e["should"] else "  <-- differs"
        print(f"{e['release_id']:<34} {'yes' if e['bumped'] else 'no':>4} {len(e['newly_broken']):>5} "
              f"{len(e['at_risk']):>5} {e['decision']:>7} {e['should']:>7}{flag}")
    gc = s["gate_counts"]
    print(f"\n  Decisions: {gc.get('BLOCK', 0)} BLOCK, {gc.get('REVIEW', 0)} REVIEW, {gc.get('ALLOW', 0)} ALLOW "
          f"across {s['releases']} releases.")

    print("\nBLAST RADIUS (tools ranked by recorded calls broken or silently changed)")
    print(f"{'#':>2} {'tool':<28} {'calls':>5} {'break':>5} {'risk':>5} {'share':>6}  gate")
    for r in a["tool_rows"][:10]:
        print(f"{r['rank']:>2} {r['tool']:<28} {r['calls']:>5} {r['would_break']:>5} {r['at_risk']:>5} "
              f"{r['share_pct']:>5.1f}%  {r['decision']}")

    print("\nMEASURED AGAINST THE LEDGER AND THE PER-CALL TRUTH")
    print(f"  Classification accuracy:     {s['class_correct']} of {s['class_total']} changes ({s['class_acc_pct']}%)"
          f"; without the description heuristic {s['class_correct_no_heuristic']} of {s['class_total']} "
          f"({s['class_acc_no_heuristic_pct']}%)")
    print(f"  Findings with no ledger entry: {s['spurious_findings']}")
    print(f"  Replay vs true broken calls: predicted {s['replay_pred_broken']}, true {s['replay_true_broken']}; "
          f"false positives {s['replay_fp']}, false negatives {s['replay_fn']} "
          f"(precision {s['replay_precision_pct']}%, recall {s['replay_recall_pct']}%)")
    print(f"  First-break revision matches truth for {s['attribution_ok']:,} of {s['calls']:,} calls")
    print(f"  Semantic changes flagged:    {s['semantic_caught']} of {s['semantic_total']} "
          f"({s['semantic_recall_pct']}%); with a unit signal {s['unit_caught']} of {s['unit_total']}, "
          f"with none {s['nosignal_caught']} of {s['nosignal_total']}")
    print(f"  Cosmetic rewrites flagged by the heuristic: {s['reworded_false_flags']} of {s['reworded_total']}")
    print(f"  Silent calls (valid, different meaning): truth {s['silent_truth']}, flagged {s['silent_flagged']}, "
          f"caught {s['silent_tp']} (recall {s['silent_recall_pct']}%, precision {s['silent_precision_pct']}%)")
    print(f"  Gate decision matches the ledger-derived answer: {s['gate_ok']} of {s['gate_total']} releases "
          f"({s['gate_acc_pct']}%)")
    print(f"  Releases that need action caught by the gate: {s['gate_caught']} of {s['gate_needs_action']}; "
          f"false REVIEWs {s['gate_false_review']}")
    print("\n  Where the classifier is wrong:")
    for r in a["ledger_rows"]:
        if not r["ok"]:
            print(f"    {r['change_id']} {r['release_id']:<30} {r['change_type']:<22} truth {r['true_class']:<13} "
                  f"predicted {r['predicted_class']}")
    print("  Where the gate differs from the ledger-derived answer:")
    for e in a["gate_miss"]:
        print(f"    {e['release_id']:<34} gate {e['decision']:<6} ought {e['should']}")

    print("\nKNOWN LIMIT (left in on purpose)")
    print(f"  Meaning changes with no number and no unit are not detected: {s['limit_changes']} in the ledger, "
          f"{s['nosignal_caught']} caught.")
    for r in a["ledger_rows"]:
        if r["semantic_kind"] == "no_signal":
            ch = next(c for c in a["data"]["ledger"] if c["change_id"] == r["change_id"])
            print(f"    {r['change_id']} {r['tool']}.{r['param']}: \"{ch['old_value']}\" -> \"{ch['new_value']}\"")
    print(f"  They leave {s['limit_calls']} recorded calls passing validation with a different meaning, "
          f"and the gate says ALLOW.")

    print("\nUTILITY (per recorded week of traffic after each change)")
    print(f"  Calls broken or misread, no gate:            {s['affected_without']} ({s['per_change_without']} per change over {s['changes']} changes)")
    print(f"  Still affected if every version alert were acted on perfectly: {s['affected_version_only']}")
    print(f"  Still affected with the SchemaWatch gate:    {s['affected_with']} ({s['per_change_with']} per change)")
    print(f"  MODELED: {s['changes_per_quarter']} schema changes per quarter across this 28-tool estate (assumption,")
    print(f"           not measured; edit CHANGES_PER_QUARTER). Assumes every BLOCK and REVIEW is acted on.")
    print(f"  Utility = ({s['per_change_without']} - {s['per_change_with']}) x {s['changes_per_quarter']} = "
          f"{int(s['utility_per_quarter'])} calls per quarter, per recorded-week of exposure per change")
    print("  Sensitivity to changes per quarter: " +
          ", ".join(f"{k}: {int(v)}" for k, v in s["utility_sensitivity"].items()))
    print("\nWrote step_04_findings.csv, step_04_release_gate.csv, step_04_tool_blast_radius.csv,")
    print("      step_04_classification_vs_ledger.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
