"""Step 4 - With ControlMap: a theme dictionary, a scope check and an evidence-freshness check.

ControlMap replaces "two words overlap" with three plain rules and adds two views the sheet never had:

  1. Theme dictionary. Each theme has a group of phrases (synonyms). A control matches an obligation
     when the control's name or description contains a phrase from the obligation's theme group.
     Retired controls never match.
  2. Scope check. The match is FULL when the control's scope includes every use-case class the
     obligation applies to, and PARTIAL when it misses one or more.
  3. Evidence freshness. Evidence is fresh when the control's latest item is no older than 1.5 times
     its test cycle at the fixed date AS_OF; otherwise it is stale (or there is none on file).

Each obligation then gets one of four statuses:
  COVERED    a full-scope control with fresh evidence
  STALE      a full-scope control exists but none has fresh evidence
  PARTIAL    only controls that miss part of the obligation's scope
  UNCOVERED  no control matches

It also lists the orphan controls (no obligation) and consolidates the evidence requests to one per
theme. It is scored against data/truth_map.csv with the same rule as the sheet in step 2.

No model is used anywhere in this repo. The dictionary is a plain table written by hand (below),
and it was written by the person who also wrote the synthetic controls. That makes the scores here
an upper bound for the method, not an estimate for a real control library. Two controls are worded
outside the dictionary on purpose, and the script prints the pairs it misses.

Fresh evidence shows that someone collected something recently. It does not show that a control is
well designed or that it works. Design and operating effectiveness are not tested here.

Run (from src/):
    python3 step_04_with_controlmap.py

Output: a readable summary, plus CSV and JSON files in out/.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict

from step_01_status_quo import (FRAMEWORK_SHORT, OUT_DIR, STALE_FACTOR, derive_status, load_all, scope_cover,
                                scope_label, status_ok, summarize as summarize_step1, truth_statuses)
from step_02_keyword_crosswalk import keyword_matches, sheet_status

BUSINESS_LINES = 6      # MODELED assumption: business lines that each track their own copy of the list

# Theme dictionary: theme -> phrases that, in a control's name or description, say the control serves it.
THEME_TERMS = {
    "risk management": ["risk register", "risk appetite", "ai risk assessment", "model risk rating"],
    "data governance": ["data quality", "data lineage", "provenance", "data reconciliation", "data use approval"],
    "technical documentation": ["model documentation", "design notes", "documentation completeness", "prompt register",
                                "derivation memo"],
    "record-keeping": ["decision log", "prompt log", "record retention", "case notes", "audit trail", "transcript archive"],
    "transparency to users": ["ai disclosure", "disclosure banner", "user notice", "plain language notice", "instructions for use"],
    "human oversight": ["human review", "human agent", "human in the loop", "override"],
    "accuracy and resilience": ["back testing", "backtesting", "adversarial testing", "failure testing", "accuracy test",
                                "outcomes analysis"],
    "model inventory": ["model inventory", "inventory register", "inventory attestation"],
    "independent validation": ["independent validation", "model validation", "validation team", "challenger",
                               "second line review"],
    "ongoing monitoring": ["performance monitoring", "drift monitoring", "drift dashboard", "answer sampling",
                           "outcome watch", "population stability", "model monitoring"],
    "governance and policy": ["governance committee", "ai policy", "board reporting", "responsibilities matrix",
                              "compliance program", "risk committee"],
    "vendor model oversight": ["vendor model", "third party model", "vendor attestation", "model vendors", "purchased model"],
    "external registration": ["external registration", "public database", "registry filing"],
    "change management": ["change review", "change approval", "release review", "change board", "change control"],
    "map function": ["intended use", "context mapping", "impact mapping", "use case context"],
    "measure function": ["test suite", "metrics review", "evaluation metrics"],
    "manage function": ["incident response", "incident plan", "incident playbook", "risk treatment", "treatment plan"],
    "specific adverse-action reasons": ["adverse action reason", "reason code", "reason review", "decline reason"],
    "timely notice of action taken": ["notice timeliness", "notice deadline", "late notice", "notification clock"],
    "prohibited-basis inputs": ["prohibited basis", "proxy test", "proxy screening", "input screen"],
}


def norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def find_phrase(theme: str, control: dict, terms: dict = None) -> str:
    """The first dictionary phrase for the theme found in the control's name or description, or ''."""
    terms = terms or THEME_TERMS
    text = f" {norm(control['name'] + ' ' + control['description'])} "
    for ph in terms.get(theme, []):
        if f" {norm(ph)} " in text:
            return ph
    return ""


def controlmap_links(data: dict, terms: dict = None) -> dict:
    """obligation_id -> list of link dicts for every active control that matches the obligation's theme."""
    out = {}
    for o in data["obligations"]:
        links = []
        for c in data["controls"]:
            if not c["active"]:
                continue
            ph = find_phrase(o["theme"], c, terms)
            if not ph:
                continue
            fr = data["fresh"][c["control_id"]]
            links.append({
                "control_id": c["control_id"], "name": c["name"], "phrase": ph,
                "coverage": scope_cover(o["classes"], c["classes"]),
                "missing": sorted(o["classes"] - c["classes"]),
                "state": fr["state"], "age": fr["age"], "limit": fr["limit"], "latest": fr["latest"],
                "freq": c["freq"], "scope": c["scope"],
            })
        out[o["obligation_id"]] = links
    return out


def link_reason(link: dict) -> str:
    """One plain sentence about a link: wording, scope, evidence."""
    scope = ("includes every class the obligation applies to" if link["coverage"] == "full"
             else "misses " + ", ".join(link["missing"]))
    if link["state"] == "none":
        ev = "no evidence on file"
    else:
        verdict = "fresh" if link["state"] == "fresh" else "stale"
        ev = f"latest evidence {link['age']} days old, limit {int(link['limit'])} days: {verdict}"
    return (f"{link['control_id']} {link['name']}: matched on \"{link['phrase']}\"; scope {scope_label(link['scope'])} "
            f"({link['coverage']}, {scope}); {ev}")


def _primary(links: list, status: str) -> dict:
    """The link shown on the status line: the freshest full link, or the closest partial one."""
    want = "full" if status in ("COVERED", "STALE") else "partial"
    pool = [l for l in links if l["coverage"] == want] or links
    return sorted(pool, key=lambda l: (len(l["missing"]), l["age"] is None, l["age"] if l["age"] is not None else 0,
                                       l["control_id"]))[0]


def analyze(data: dict = None, terms: dict = None, with_thin: bool = True) -> dict:
    data = data or load_all()
    terms = terms or THEME_TERMS
    fresh = data["fresh"]
    links = controlmap_links(data, terms)
    ts = truth_statuses(data)
    sheet = sheet_status(keyword_matches(data))
    all_fresh = {c["control_id"]: {"state": "fresh"} for c in data["controls"]}

    rows = []
    stage = {"dictionary": 0, "scope": 0, "freshness": 0, "sheet": 0, "name_only": 0}
    for o in data["obligations"]:
        oid = o["obligation_id"]
        pairs = {l["control_id"]: l["coverage"] for l in links[oid]}
        status, driving = derive_status(pairs, fresh)
        s1 = ("COVERED", sorted(pairs)) if pairs else ("UNCOVERED", [])
        name_hits = sorted(c["control_id"] for c in data["controls"] if c["active"]
                           and f" {norm(o['theme'])} " in f" {norm(c['name'] + ' ' + c['description'])} ")
        s0 = ("COVERED", name_hits) if name_hits else ("UNCOVERED", [])
        stage["name_only"] += status_ok(s0, ts[oid])
        s2 = derive_status(pairs, all_fresh)
        ok = status_ok((status, driving), ts[oid])
        stage["dictionary"] += status_ok(s1, ts[oid])
        stage["scope"] += status_ok(s2, ts[oid])
        stage["freshness"] += ok
        stage["sheet"] += status_ok(sheet[oid], ts[oid])
        rows.append({
            "obligation_id": oid, "framework": o["framework"], "short": FRAMEWORK_SHORT[o["framework"]],
            "theme": o["theme"], "statement": o["statement"], "applies_to": o["applies_to"],
            "status": status, "driving": driving, "links": links[oid],
            "primary": _primary(links[oid], status) if links[oid] else None,
            "truth_status": ts[oid][0], "truth_driving": ts[oid][1], "ok": ok,
            "sheet_status": sheet[oid][0], "sheet_controls": sheet[oid][1],
            "sheet_ok": status_ok(sheet[oid], ts[oid]),
        })
    n_ob = len(rows)

    truth_pairs = {(t["obligation_id"], t["control_id"]) for t in data["truth"]}
    cm_pairs = {(oid, l["control_id"]) for oid, ls in links.items() for l in ls}
    tp = len(cm_pairs & truth_pairs)
    missed = sorted(truth_pairs - cm_pairs)
    false_links = sorted(cm_pairs - truth_pairs)
    cov_ok = sum(1 for (oid, cid) in cm_pairs & truth_pairs
                 if links[oid] and next(l for l in links[oid] if l["control_id"] == cid)["coverage"]
                 == data["truth_by_ob"][oid][cid])

    linked_cm = {cid for _, cid in cm_pairs}
    linked_truth = {cid for _, cid in truth_pairs}
    true_orphans = [c["control_id"] for c in data["controls"] if c["control_id"] not in linked_truth]
    cm_orphans = [c["control_id"] for c in data["controls"] if c["control_id"] not in linked_cm]
    orphan_rows = []
    for cid in cm_orphans:
        c = data["ct_by_id"][cid]
        orphan_rows.append({"control_id": cid, "name": c["name"], "owner": c["owner"], "status": c["status"],
                            "scope": c["scope"], "true_orphan": cid in true_orphans,
                            "reason": "retired" if not c["active"] else "no obligation theme matches its wording"})
    orphan_hit = [r for r in orphan_rows if r["true_orphan"]]

    # consolidated evidence requests: one per theme
    by_theme = defaultdict(list)
    for r in rows:
        by_theme[r["theme"]].append(r)
    requests = []
    for theme, rs in by_theme.items():
        cids = sorted({l["control_id"] for r in rs for l in r["links"]})
        need = [c for c in cids if fresh[c]["state"] != "fresh"]
        requests.append({
            "theme": theme, "obligations": [r["obligation_id"] for r in rs],
            "frameworks": sorted({r["short"] for r in rs}), "controls": cids,
            "need_evidence": need, "gap": not cids,
        })
    requests.sort(key=lambda r: (-len(r["obligations"]), r["theme"]))

    s1 = summarize_step1(data)
    cm_ok = sum(r["ok"] for r in rows)
    sh_ok = sum(r["sheet_ok"] for r in rows)
    conf = Counter((r["truth_status"], r["status"]) for r in rows)
    errors = [r for r in rows if not r["ok"]]
    missed_by = defaultdict(list)
    for oid, cid in missed:
        missed_by[cid].append(oid)
    false_by = defaultdict(list)
    for oid, cid in false_links:
        false_by[cid].append(oid)

    # dictionary fragility: control-theme links that rest on a single dictionary phrase
    link_phrases = defaultdict(set)
    for o in data["obligations"]:
        for c in data["controls"]:
            if c["active"]:
                text = f" {norm(c['name'] + ' ' + c['description'])} "
                for ph in terms.get(o["theme"], []):
                    if f" {norm(ph)} " in text:
                        link_phrases[(c["control_id"], o["theme"])].add(ph)
    single = sum(1 for v in link_phrases.values() if len(v) == 1)

    summary = {
        "obligations": n_ob, "controls": len(data["controls"]),
        "links_total": len(link_phrases), "links_single_phrase": single,
        "cm_ok": cm_ok, "cm_ok_pct": round(cm_ok / n_ob * 100, 1),
        "sheet_ok": sh_ok, "sheet_ok_pct": round(sh_ok / n_ob * 100, 1),
        "lift": cm_ok - sh_ok,
        "stage_sheet": stage["sheet"], "stage_name_only": stage["name_only"], "stage_dictionary": stage["dictionary"], "stage_scope": stage["scope"],
        "stage_freshness": stage["freshness"],
        "cm_pairs": len(cm_pairs), "truth_pairs": len(truth_pairs), "tp": tp, "fp": len(false_links), "fn": len(missed),
        "precision_pct": round(tp / len(cm_pairs) * 100, 1), "recall_pct": round(tp / len(truth_pairs) * 100, 1),
        "coverage_label_ok": cov_ok,
        "status_counts_truth": dict(Counter(r["truth_status"] for r in rows)),
        "status_counts_cm": dict(Counter(r["status"] for r in rows)),
        "true_orphans": len(true_orphans), "cm_orphans": len(cm_orphans), "orphans_found": len(orphan_hit),
        "orphans_wrongly_listed": len(cm_orphans) - len(orphan_hit),
        "requests_framework": s1["requests_per_framework"], "requests_theme": s1["requests_per_theme"],
        "requests_to_owners": sum(1 for r in requests if not r["gap"]), "requests_gap": sum(1 for r in requests if r["gap"]),
        "gap_obligations": sum(len(r["obligations"]) for r in requests if r["gap"]),
        "controls_need_evidence": len({c for r in requests for c in r["need_evidence"]}),
        "missed_pairs": len(missed), "missed_controls": len(missed_by), "false_links": len(false_links),
        "false_controls": len(false_by), "wrong_status": len(errors),
        "business_lines": BUSINESS_LINES, "tracked_entries": n_ob * BUSINESS_LINES,
        "utility_entries": (cm_ok - sh_ok) * BUSINESS_LINES,
        "sensitivity": {str(k): (cm_ok - sh_ok) * k for k in (3, 6, 12)},
        "truth_covered_any": sum(1 for o in data["obligations"] if data["truth_by_ob"].get(o["obligation_id"])),
        "sheet_covered": sum(1 for r in rows if r["sheet_status"] == "COVERED"),
        "sheet_covered_wrong": sum(1 for r in rows if r["sheet_status"] == "COVERED" and not r["sheet_ok"]),
        "dictionary_themes": len(terms), "dictionary_phrases": sum(len(v) for v in terms.values()),
    }
    if with_thin:
        thin = analyze(data, {t: v[:1] for t, v in terms.items()}, with_thin=False)["summary"]
        summary["thin_ok"], summary["thin_recall_pct"] = thin["cm_ok"], thin["recall_pct"]
    sheet_linked = {cid for h in keyword_matches(data).values() for cid in h}
    return {"data": data, "rows": rows, "summary": summary, "links": links, "truth_statuses": ts, "sheet": sheet,
            "sheet_covered": summary["sheet_covered"], "orphans_sheet_linked": len(set(true_orphans) & sheet_linked),
            "missed": missed, "missed_by": dict(missed_by), "false_links": false_links, "false_by": dict(false_by),
            "orphan_rows": orphan_rows, "requests": requests, "conf": conf, "errors": errors,
            "true_orphans": true_orphans}


def picker_order(rows: list) -> list:
    """Order for the app and the demo: the cases where the spreadsheet is most wrong come first, known-limit cases last."""
    def interest(r: dict) -> int:
        if not r["ok"]:
            return 7
        if r["sheet_ok"]:
            return 6
        if r["sheet_status"] == "COVERED" and r["truth_status"] == "UNCOVERED":
            return 0
        if r["truth_status"] == "STALE":
            return 1
        if r["truth_status"] == "PARTIAL":
            return 2
        if r["sheet_status"] == "UNCOVERED":
            return 3
        return 4
    return sorted(rows, key=lambda r: (interest(r), r["obligation_id"]))


def _ev_text(fr: dict) -> str:
    if fr["state"] == "none":
        return "no evidence on file"
    return f"latest evidence {fr['latest']}, {fr['age']} days old, limit {int(fr['limit'])} days: {fr['state']}"


def explain(a: dict, oid: str) -> dict:
    """Plain-data explanation of one obligation for the app and the demo: sheet, truth and ControlMap."""
    data = a["data"]
    r = next(x for x in a["rows"] if x["obligation_id"] == oid)
    ob = data["ob_by_id"][oid]
    tb = data["truth_by_ob"].get(oid, {})
    matches = keyword_matches(data)[oid]

    # keyword sheet
    items = [{"id": c, "name": data["ct_by_id"][c]["name"], "shared": w, "is_true": c in tb}
             for c, w in sorted(matches.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    shown = items[:5]
    t_status, sheet_status_ = r["truth_status"], r["sheet_status"]
    if r["sheet_ok"]:
        tag = "RIGHT"
        why = ("it names a control that really drives the status" if sheet_status_ == "COVERED"
               else "nothing in the register meets it")
    elif sheet_status_ == "COVERED":
        tag = "WRONG"
        why = {"UNCOVERED": "no control in the register meets this obligation",
               "PARTIAL": "the controls that meet it miss part of its scope",
               "STALE": "the evidence behind the controls that meet it is stale",
               "COVERED": "none of the controls it names is the one that drives the status"}[t_status]
    else:
        tag = "MISSED"
        why = "a control in the register meets it in different words"
    sheet = {"status": "covered" if sheet_status_ == "COVERED" else "not covered", "tag": tag, "why": why,
             "items": shown, "n_more": len(items) - len(shown), "n_true": sum(1 for i in items if i["is_true"]),
             "n_false": sum(1 for i in items if not i["is_true"])}

    # truth
    t_items = []
    for cid, cov in sorted(tb.items()):
        c = data["ct_by_id"][cid]
        t_items.append({"id": cid, "name": c["name"], "coverage": cov, "scope": scope_label(c["scope"]),
                        "evidence": _ev_text(data["fresh"][cid]), "state": data["fresh"][cid]["state"]})
    t_why = {"COVERED": "a full-scope control with fresh evidence exists",
             "STALE": "a full-scope control exists, but its evidence is stale or missing",
             "PARTIAL": "only controls that miss part of the obligation's scope exist",
             "UNCOVERED": "no control in the register meets this obligation"}[t_status]
    truth = {"status": t_status, "why": t_why, "items": t_items}

    # ControlMap
    cm_items = [{"text": link_reason(l), "coverage": l["coverage"], "id": l["control_id"]} for l in r["links"]]
    if r["ok"]:
        cm_tag = "CAUGHT" if not r["sheet_ok"] else "SAME AS THE SHEET"
        note = ""
    else:
        cm_tag = "KNOWN LIMIT"
        missed = [c for c in tb if c not in {l["control_id"] for l in r["links"]}]
        wrong = [l["control_id"] for l in r["links"] if l["control_id"] not in tb]
        parts = []
        if missed:
            parts.append("the control that meets it, " + ", ".join(f"{c} {data['ct_by_id'][c]['name']}" for c in missed)
                         + ", uses wording outside the dictionary")
        if wrong:
            parts.append("it linked " + ", ".join(f"{c} {data['ct_by_id'][c]['name']}" for c in wrong)
                         + " on a phrase it cannot read in context")
        detail = "; ".join(parts)
        note = f"ControlMap says {r['status']}; the truth is {t_status}. " + detail[:1].upper() + detail[1:] + "."
    cm = {"status": r["status"], "tag": cm_tag, "items": cm_items, "note": note,
          "ok": r["ok"], "sheet_ok": r["sheet_ok"]}
    return {"oid": oid, "framework": ob["framework"], "short": r["short"], "theme": ob["theme"],
            "statement": ob["statement"], "applies_to": scope_label(ob["applies_to"]),
            "sheet": sheet, "truth": truth, "cm": cm}


def _scope_note(r: dict) -> str:
    p = r["primary"]
    if p is None:
        return "no control matches this theme"
    ev = "no evidence" if p["state"] == "none" else f"evidence {p['age']} d old (limit {int(p['limit'])} d)"
    full = sum(1 for l in r["links"] if l["coverage"] == "full")
    part = len(r["links"]) - full
    if r["status"] == "PARTIAL":
        return f"{part} partial-scope control{'s' if part != 1 else ''}; closest {p['control_id']} misses {', '.join(p['missing'])}; {ev}"
    if r["status"] == "STALE":
        return f"{full} full-scope control{'s' if full != 1 else ''}, none fresh; newest {p['control_id']}, {ev}"
    n = len(r["driving"])
    return f"{n} control{'s' if n != 1 else ''} drive{'' if n != 1 else 's'} it; freshest {p['control_id']}, {ev}"


def main() -> None:
    a = analyze()
    data, s, rows = a["data"], a["summary"], a["rows"]
    ct = data["ct_by_id"]
    n_ob = s["obligations"]
    print("STEP 4 - With ControlMap: theme dictionary + scope check + evidence freshness")
    print("  No model: the dictionary is a plain table of phrases. Statuses: COVERED, STALE, PARTIAL, UNCOVERED.")
    print(f"  Dictionary: {s['dictionary_themes']} themes, {s['dictionary_phrases']} phrases. Evidence is fresh when the latest item is no older than {STALE_FACTOR:g} x the test cycle.")
    print()
    print(f"OBLIGATION STATUS (first rows; all {n_ob} in out/step_04_obligation_status.csv)")
    print(f"  {'obligation':<10} {'framework':<13} {'theme':<30} {'status':<10} driving control and evidence")
    for r in rows[:16]:
        print(f"  {r['obligation_id']:<10} {r['short']:<13} {r['theme']:<30} {r['status']:<10} {_scope_note(r)}")
    print("  ...")
    shown_false = [r["obligation_id"] for r in rows[:16] if r["primary"] and r["primary"]["control_id"] not in data["truth_by_ob"].get(r["obligation_id"], {})]
    print("  Rows above where the control shown is a false link (see KNOWN LIMIT): " + (", ".join(shown_false) or "none"))
    print()
    print("WHAT EACH PART ADDS (obligations with the right status; same strict rule as step 2)")
    print(f"  Keyword sheet (step 2):                          {s['stage_sheet']} of {n_ob}")
    print(f"  Theme name as the only phrase (no synonyms):     {s['stage_name_only']} of {n_ob}")
    print(f"  Theme dictionary with synonym groups:            {s['stage_dictionary']} of {n_ob}")
    print(f"  + scope check (adds PARTIAL):                    {s['stage_scope']} of {n_ob}")
    print(f"  + evidence freshness (adds STALE):               {s['stage_freshness']} of {n_ob}   <- ControlMap")
    print(f"  Thin dictionary (first phrase per theme only):   {s['thin_ok']} of {n_ob}, pair recall {s['thin_recall_pct']}%")
    print()
    print("SCORED AGAINST truth_map.csv")
    w = 44

    def line(label: str, value: str) -> None:
        print(f"  {label:<{w}}{value}")

    line("Right status, ControlMap:", f"{s['cm_ok']} of {n_ob} ({s['cm_ok_pct']}%)")
    line("Right status, keyword sheet:", f"{s['sheet_ok']} of {n_ob} ({s['sheet_ok_pct']}%)")
    line("Pairs linked / true pairs:", f"{s['cm_pairs']} / {s['truth_pairs']}")
    line("Pair precision:", f"{s['tp']} of {s['cm_pairs']} ({s['precision_pct']}%)")
    line("Pair recall:", f"{s['tp']} of {s['truth_pairs']} ({s['recall_pct']}%)")
    line("Links that are wrong:", f"{s['fp']} of {s['cm_pairs']} ({round(s['fp'] / s['cm_pairs'] * 100, 1)}%)")
    line("Scope label right on linked true pairs:", f"{s['coverage_label_ok']} of {s['tp']}")
    order = ["COVERED", "STALE", "PARTIAL", "UNCOVERED"]
    print()
    print("  Status confusion (rows: truth, columns: ControlMap)")
    print(f"  {'':<12}" + "".join(f"{c:>11}" for c in order))
    for t in order:
        print(f"  {t:<12}" + "".join(f"{a['conf'].get((t, c), 0):>11}" for c in order))
    print()
    print("ORPHAN CONTROLS (listed by ControlMap; the sheet has no such view)")
    print(f"  {len(a['orphan_rows'])} controls serve no obligation by ControlMap's reading; {s['orphans_found']} of the {s['true_orphans']} "
          f"({round(s['orphans_found'] / s['true_orphans'] * 100, 1)}%) true orphans are among them.")
    for r in a["orphan_rows"]:
        tag = "true orphan" if r["true_orphan"] else "WRONGLY listed"
        print(f"    {r['control_id']} {r['name']:<38} {r['status']:<8} {tag}")
    print()
    print("CONSOLIDATED EVIDENCE REQUESTS (one per distinct theme)")
    print(f"  {s['requests_framework']} requests if each framework answers on its own, {s['requests_theme']} once per theme: "
          f"{s['requests_to_owners']} go to control owners, {s['requests_gap']} are gaps with no control to ask ({s['gap_obligations']} obligations).")
    print(f"  {'theme':<32} {'frameworks':>10} {'obligations':>12} {'controls':>9} {'need new evidence':>18}")
    for r in a["requests"]:
        if r["gap"]:
            tail = "GAP: no control"
        else:
            tail = f"{len(r['need_evidence']):>18}"
        print(f"  {r['theme']:<32} {len(r['frameworks']):>10} {len(r['obligations']):>12} {len(r['controls']):>9} {tail}")
    print()
    print("KNOWN LIMIT (left in on purpose)")
    print(f"  1. True mappings missed because the wording is outside the dictionary: {s['missed_pairs']} pairs from {s['missed_controls']} controls.")
    for cid, obs in sorted(a["missed_by"].items()):
        print(f"       {cid} {ct[cid]['name']}: misses {', '.join(obs)}")
        print(f"         \"{ct[cid]['description']}\"")
    print(f"     Statuses this gets wrong: {s['wrong_status']} of {n_ob}.")
    for r in a["errors"]:
        print(f"       {r['obligation_id']} {r['theme']:<26} truth {r['truth_status']:<9} ControlMap {r['status']}")
    print(f"  2. Links to controls that do not meet the obligation: {s['false_links']} pairs from {s['false_controls']} control{'s' if s['false_controls'] != 1 else ''}.")
    for cid, obs in sorted(a["false_by"].items()):
        ph = sorted({l["phrase"] for oid in obs for l in a["links"][oid] if l["control_id"] == cid})
        print(f"       {cid} {ct[cid]['name']}: matched on {', '.join(chr(34) + p + chr(34) for p in ph)} for {', '.join(obs)}")
        print(f"         \"{ct[cid]['description']}\"")
    print("  3. Fresh evidence is not proof that a control works. ControlMap checks wording, scope and the date of the latest")
    print("     evidence. It does not test design or operating effectiveness, so a COVERED obligation can still have a weak control.")
    print("  4. The dictionary was written by the author of the data, and truth is judged one control at a time: treat the scores as an upper bound.")
    print(f"     {s['links_single_phrase']} of {s['links_total']} control-to-theme links rest on a single dictionary phrase; remove it and the control is missed.")
    print()
    print("UTILITY (obligations given the right status)")
    print(f"  Right status: keyword sheet {s['sheet_ok']} of {n_ob}, ControlMap {s['cm_ok']} of {n_ob}; lift {s['lift']} obligations.")
    print(f"  MODELED: {s['business_lines']} business lines each track their own copy of the {n_ob}-obligation list (assumption, not measured;")
    print(f"           edit BUSINESS_LINES), so {s['tracked_entries']} obligation entries.")
    print(f"  Utility = ({s['cm_ok']}/{n_ob} - {s['sheet_ok']}/{n_ob}) x {s['tracked_entries']} = {s['utility_entries']} obligation entries given the right status")
    print("  Sensitivity to business lines: " + ", ".join(f"{k}: {v}" for k, v in s["sensitivity"].items()))

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_04_obligation_status.csv", "w", newline="", encoding="utf-8") as f:
        w2 = csv.writer(f, lineterminator="\n")
        w2.writerow(["obligation_id", "framework", "theme", "controlmap_status", "driving_controls", "truth_status", "right_status"])
        for r in rows:
            w2.writerow([r["obligation_id"], r["framework"], r["theme"], r["status"], ";".join(r["driving"]),
                         r["truth_status"], int(r["ok"])])
    with open(OUT_DIR / "step_04_orphans.csv", "w", newline="", encoding="utf-8") as f:
        w2 = csv.writer(f, lineterminator="\n")
        w2.writerow(["control_id", "name", "owner", "status", "true_orphan", "reason"])
        for r in a["orphan_rows"]:
            w2.writerow([r["control_id"], r["name"], r["owner"], r["status"], int(r["true_orphan"]), r["reason"]])
    with open(OUT_DIR / "step_04_evidence_requests.csv", "w", newline="", encoding="utf-8") as f:
        w2 = csv.writer(f, lineterminator="\n")
        w2.writerow(["theme", "frameworks", "obligations", "controls", "need_new_evidence", "gap"])
        for r in a["requests"]:
            w2.writerow([r["theme"], ";".join(r["frameworks"]), ";".join(r["obligations"]), ";".join(r["controls"]),
                         ";".join(r["need_evidence"]), int(r["gap"])])
    (OUT_DIR / "step_04_summary.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    print("\nWrote step_04_obligation_status.csv, step_04_orphans.csv, step_04_evidence_requests.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
