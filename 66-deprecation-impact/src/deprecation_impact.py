"""deprecation_impact: when a vendor retires a model version, list the features that call it, the
date each one has to move by, and what the move costs. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 deprecation_impact.py --demo
    python3 deprecation_impact.py report --features F.csv --usages U.csv --models M.csv --as-of 2026-09-01
                                         [--aliases A.csv] [--policy P.json] [--model MODEL_ID]
                                         [--fail-on late|tight|never] [--format text|json]

Exit status: 0 when the worst tier is below --fail-on, 1 when it is at or above it, 2 for bad input.
Tiers, worst first: PAST (the model is already retired), LATE (days left are fewer than the lead
time the feature needs), TIGHT (fewer than tight_margin_days to spare), ROOM, SUNSETS (the feature is
switched off before the model retires). A string the tool cannot resolve is listed as CHECK and
never counted as clear. There is no model call in this file: it is lookups, date arithmetic and a
price table. The lead times in DEFAULT_POLICY are assumptions, not findings.

Input files, all CSV with a header row. Features and usages are joined on the explicit feature_id
field. Nothing is inferred from how a name is spelled.
    models:   model_id, family, vendor, notice_date, retire_date, successor, input_usd_per_1m,
              output_usd_per_1m, successor_input_token_factor, base_model_id
    aliases:  alias, model_id, recorded_on
    features: feature_id, feature_name, owner_team, business_line, criticality, has_eval_set, sunset_date
    usages:   usage_id, feature_id, role, model_ref, config_path, monthly_calls, avg_input_tokens, avg_output_tokens
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import sys

DEMO_AS_OF = "2026-09-01"
DEFAULT_POLICY = {"lead_days": {"critical": 60, "standard": 30, "low": 14}, "no_eval_set_extra_days": 30,
                  "judge_extra_days": 14, "finetune_extra_days": 45, "tight_margin_days": 30, "alias_max_age_days": 90}
ROLES = ("primary", "fallback", "judge")
CRITICALITY = ("critical", "standard", "low")
TIER_ORDER = ("PAST", "LATE", "TIGHT", "ROOM", "SUNSETS")
FAIL_TIERS = {"late": ("PAST", "LATE"), "tight": ("PAST", "LATE", "TIGHT"), "never": ()}
MODEL_COLS = ["model_id", "family", "vendor", "notice_date", "retire_date", "successor", "input_usd_per_1m",
              "output_usd_per_1m", "successor_input_token_factor", "base_model_id"]
ALIAS_COLS = ["alias", "model_id", "recorded_on"]
FEATURE_COLS = ["feature_id", "feature_name", "owner_team", "business_line", "criticality", "has_eval_set", "sunset_date"]
USAGE_COLS = ["usage_id", "feature_id", "role", "model_ref", "config_path", "monthly_calls", "avg_input_tokens", "avg_output_tokens"]


# ---------------------------------------------------------------- loading and validation
def clean(text) -> str:
    """Make untrusted text safe to print on one line: control characters and line separators become escapes."""
    out = []
    for c in str(text):
        if c.isprintable():
            out.append(c)
        else:
            out.append("\\x%02x" % ord(c) if ord(c) < 256 else "\\u%04x" % ord(c))
    return "".join(out)


def _rows(path: str, cols: list, label: str) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if not header:
            raise ValueError(f"{label}: the file is empty")
        header = [h.strip() for h in header]
        missing = [c for c in cols if c not in header]
        if missing:
            raise ValueError(f"{label}: missing column(s) {', '.join(missing)}")
        rows = []
        for n, raw in enumerate(reader, 2):
            if not raw:
                continue
            if len(raw) != len(header):
                raise ValueError(f"{label} line {n}: expected {len(header)} columns, found {len(raw)}")
            rows.append(dict(zip(header, (v.strip() for v in raw))))
    return rows


def _date(value: str, label: str, blank_ok: bool = False):
    if value == "" and blank_ok:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label}: {value!r} is not a date in YYYY-MM-DD form") from None


def _number(value: str, label: str, kind=float, minimum=0):
    try:
        n = kind(value)
    except ValueError:
        raise ValueError(f"{label}: {value!r} is not a number") from None
    if not math.isfinite(n) or n < minimum:
        raise ValueError(f"{label}: {value!r} must be a number of at least {minimum}")
    return n


def load_models(path: str) -> dict:
    models = {}
    for r in _rows(path, MODEL_COLS, "models"):
        mid = r["model_id"]
        if not mid or not r["family"]:
            raise ValueError("models: model_id and family may not be blank")
        if mid in models:
            raise ValueError(f"models: duplicate model_id {mid!r}")
        where = f"models {mid!r}"
        notice, retire = _date(r["notice_date"], where, True), _date(r["retire_date"], where, True)
        if notice and retire and retire < notice:
            raise ValueError(f"{where}: retire_date is before notice_date")
        models[mid] = {"model_id": mid, "family": r["family"], "vendor": r["vendor"], "notice_date": notice, "retire_date": retire,
                       "successor": r["successor"], "base_model_id": r["base_model_id"],
                       "in_price": _number(r["input_usd_per_1m"], where), "out_price": _number(r["output_usd_per_1m"], where),
                       "token_factor": _number(r["successor_input_token_factor"] or "1", where, minimum=0.01)}
    if len({m.casefold() for m in models}) != len(models):
        raise ValueError("models: two model_id values differ only in letter case")
    for mid, m in models.items():
        if m["base_model_id"] and m["base_model_id"] not in models:
            raise ValueError(f"models {mid!r}: base_model_id {m['base_model_id']!r} is not in the models file")
    for mid in models:
        seen, cur = set(), mid
        while cur:
            if cur in seen:
                raise ValueError(f"models {mid!r}: base_model_id chain loops")
            seen.add(cur)
            cur = models[cur]["base_model_id"]
    return models


def load_aliases(path: str, models: dict) -> dict:
    aliases = {}
    taken = {m.casefold() for m in models} | {m["family"].casefold() for m in models.values()}
    for r in _rows(path, ALIAS_COLS, "aliases"):
        key = r["alias"].casefold()
        if not key or key in aliases:
            raise ValueError(f"aliases: blank or duplicate alias {r['alias']!r}")
        if key in taken:
            raise ValueError(f"aliases: {r['alias']!r} is also a model_id or a family name")
        if r["model_id"] not in models:
            raise ValueError(f"aliases {r['alias']!r}: model_id {r['model_id']!r} is not in the models file")
        aliases[key] = {"alias": r["alias"], "model_id": r["model_id"], "recorded_on": _date(r["recorded_on"], f"aliases {r['alias']!r}")}
    return aliases


def load_features(path: str) -> dict:
    features = {}
    for r in _rows(path, FEATURE_COLS, "features"):
        fid = r["feature_id"]
        if not fid or fid in features:
            raise ValueError(f"features: blank or duplicate feature_id {fid!r}")
        if r["criticality"] not in CRITICALITY:
            raise ValueError(f"features {fid!r}: criticality must be one of {', '.join(CRITICALITY)}")
        if r["has_eval_set"] not in ("yes", "no"):
            raise ValueError(f"features {fid!r}: has_eval_set must be yes or no")
        features[fid] = {**r, "sunset_date": _date(r["sunset_date"], f"features {fid!r}", True)}
    return features


def load_usages(path: str, features: dict) -> list:
    usages, seen = [], set()
    for r in _rows(path, USAGE_COLS, "usages"):
        uid = r["usage_id"]
        if not uid or uid in seen:
            raise ValueError(f"usages: blank or duplicate usage_id {uid!r}")
        seen.add(uid)
        where = f"usages {uid!r}"
        if r["feature_id"] not in features:
            raise ValueError(f"{where}: feature_id {r['feature_id']!r} is not in the features file")
        if r["role"] not in ROLES:
            raise ValueError(f"{where}: role must be one of {', '.join(ROLES)}")
        usages.append({**r, "monthly_calls": _number(r["monthly_calls"], where, int), "avg_input_tokens": _number(r["avg_input_tokens"], where, int),
                       "avg_output_tokens": _number(r["avg_output_tokens"], where, int)})
    return usages


def load_policy(path: str | None) -> dict:
    if path is None:
        return json.loads(json.dumps(DEFAULT_POLICY))
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict) or not isinstance(raw.get("lead_days", {}), dict):
        raise ValueError("policy: expected a JSON object, with lead_days an object")
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    for key, value in raw.items():
        if key not in policy:
            raise ValueError(f"policy: unknown key {key!r}")
        if key == "lead_days":
            for c, days in value.items():
                if c not in CRITICALITY:
                    raise ValueError(f"policy: lead_days has unknown criticality {c!r}")
                policy[key][c] = _number(str(days), f"policy lead_days {c}", int)
        else:
            policy[key] = _number(str(value), f"policy {key}", int)
    return policy


# ---------------------------------------------------------------- resolving a model string
def retirement(model_id: str, models: dict):
    """(retire_date, root_model_id) for a model, own or inherited through base_model_id; None when none applies."""
    cur = model_id
    while cur:
        m = models[cur]
        if m["retire_date"]:
            return m["retire_date"], cur
        cur = m["base_model_id"]
    return None


def _index(models: dict, aliases: dict) -> dict:
    families = {}
    for mid in sorted(models):
        families.setdefault(models[mid]["family"].casefold(), []).append(mid)
    return {"models": models, "ids": {m.casefold(): m for m in models}, "aliases": aliases, "families": families}


def resolve(ref: str, idx: dict, as_of: datetime.date, policy: dict) -> dict:
    """Map one model string to a verdict: hit (resolves to a retiring model), clear, or check (cannot tell)."""
    models, key = idx["models"], ref.strip().casefold()
    note, mid = "", None
    if key in idx["ids"]:
        mid = idx["ids"][key]
    elif key in idx["aliases"]:
        a = idx["aliases"][key]
        mid = a["model_id"]
        note = f"alias {a['alias']} -> {mid}"
        age = (as_of - a["recorded_on"]).days
        retiring = [m for m in idx["families"][models[mid]["family"].casefold()] if retirement(m, models)]
        if age > policy["alias_max_age_days"] and retiring:
            return {"verdict": "check", "model_id": mid, "note": f"alias recorded {age} days before the as-of date; the vendor may have moved it",
                    "maybe": retiring}
    elif key in idx["families"]:
        retiring = [m for m in idx["families"][key] if retirement(m, models)]
        if retiring:
            return {"verdict": "check", "model_id": None, "note": f"no snapshot is pinned and the family has retiring snapshot(s) {', '.join(retiring)}",
                    "maybe": retiring}
        return {"verdict": "clear", "model_id": None, "note": "", "maybe": []}
    else:
        return {"verdict": "check", "model_id": None, "note": "not in the models file or the alias table", "maybe": []}
    r = retirement(mid, models)
    if r is None:
        return {"verdict": "clear", "model_id": mid, "note": note, "maybe": []}
    if r[1] != mid:
        note = (note + "; " if note else "") + f"{mid} is built on {r[1]}"
    return {"verdict": "hit", "model_id": mid, "root": r[1], "retire": r[0], "note": note, "maybe": []}


# ---------------------------------------------------------------- dates, tiers, cost
def lead_days(feature: dict, role: str, inherited: bool, policy: dict) -> int:
    days = policy["lead_days"][feature["criticality"]]
    days += policy["no_eval_set_extra_days"] if feature["has_eval_set"] == "no" else 0
    days += policy["judge_extra_days"] if role == "judge" else 0
    days += policy["finetune_extra_days"] if inherited else 0
    return days


def tier_of(days_left: int, lead: int, policy: dict) -> str:
    if days_left < 0:
        return "PAST"
    slack = days_left - lead
    return "LATE" if slack < 0 else "TIGHT" if slack < policy["tight_margin_days"] else "ROOM"


def monthly_cost(calls: int, tokens_in: int, tokens_out: int, price_in: float, price_out: float, factor: float = 1.0) -> float:
    return round(calls * (tokens_in * factor * price_in + tokens_out * price_out) / 1_000_000, 2)


def _dep(u, f, v, models, as_of, policy) -> dict:
    d = {"feature_id": f["feature_id"], "feature_name": f["feature_name"], "criticality": f["criticality"], "role": u["role"],
         "model_ref": u["model_ref"], "verdict": v["verdict"], "model_id": v["model_id"] or "", "note": v["note"], "maybe": v["maybe"],
         "root_model_id": "", "retire_date": "", "days_left": None, "lead_days": None, "slack_days": None, "tier": "CHECK",
         "monthly_calls": u["monthly_calls"], "cost_now": None, "cost_after": None, "successor": ""}
    if v["verdict"] != "hit":
        return d
    retire, root, mid = v["retire"], v["root"], v["model_id"]
    d.update(root_model_id=root, retire_date=retire.isoformat(), days_left=(retire - as_of).days)
    sunset = f["sunset_date"]
    if sunset and sunset <= retire:
        d["tier"] = "SUNSETS"
        d["note"] = (d["note"] + "; " if d["note"] else "") + f"feature sunsets {sunset.isoformat()}, before the model retires"
        return d
    inherited = root != mid
    d["lead_days"] = lead_days(f, u["role"], inherited, policy)
    d["slack_days"] = d["days_left"] - d["lead_days"]
    d["tier"] = tier_of(d["days_left"], d["lead_days"], policy)
    m = models[mid]
    d["cost_now"] = monthly_cost(u["monthly_calls"], u["avg_input_tokens"], u["avg_output_tokens"], m["in_price"], m["out_price"])
    succ = models.get(m["successor"]) if not inherited else None
    if succ:
        d["successor"] = succ["model_id"]
        d["cost_after"] = monthly_cost(u["monthly_calls"], u["avg_input_tokens"], u["avg_output_tokens"], succ["in_price"], succ["out_price"], m["token_factor"])
    return d


def worst(tiers) -> str:
    return min(tiers, key=TIER_ORDER.index) if tiers else "CLEAR"


def analyze(features: dict, usages: list, models: dict, aliases: dict, as_of: datetime.date, policy: dict, only_model: str | None = None) -> dict:
    """Resolve every usage, then build the calendar, the hit list, the check list and the cost view."""
    idx = _index(models, aliases)
    if only_model is not None:
        if only_model not in models or not models[only_model]["retire_date"]:
            raise ValueError(f"no retirement notice for model {only_model!r} in the models file")
    deps, used, cleared = [], set(), 0
    for u in usages:
        f = features[u["feature_id"]]
        used.add(f["feature_id"])
        d = _dep(u, f, resolve(u["model_ref"], idx, as_of, policy), models, as_of, policy)
        if d["verdict"] == "clear":
            cleared += 1
        else:
            deps.append(d)
    for fid in sorted(set(features) - used):
        none = {"verdict": "check", "model_id": None, "note": "no model is recorded for this feature", "maybe": []}
        deps.append(_dep({"role": "unknown", "model_ref": "", "monthly_calls": 0}, features[fid], none, models, as_of, policy))
    if only_model is not None:
        deps = [d for d in deps if d["root_model_id"] == only_model or (d["verdict"] == "check" and only_model in d["maybe"])]
    order = {"hit": 0, "check": 1}
    deps.sort(key=lambda d: (order[d["verdict"]], d["retire_date"], d["feature_id"], d["role"]))
    hits = [d for d in deps if d["verdict"] == "hit"]
    calendar = []
    for mid in sorted((m for m in models if models[m]["retire_date"] and (only_model is None or m == only_model)),
                      key=lambda m: (models[m]["retire_date"], m)):
        m = models[mid]
        mine = [d for d in hits if d["root_model_id"] == mid]
        movers = [d for d in mine if d["tier"] != "SUNSETS"]
        priced = [d for d in movers if d["cost_after"] is not None]
        calendar.append({"model_id": mid, "notice_date": m["notice_date"].isoformat() if m["notice_date"] else "", "retire_date": m["retire_date"].isoformat(),
                         "days_left": (m["retire_date"] - as_of).days, "features": len({d["feature_id"] for d in mine}), "dependencies": len(mine),
                         "monthly_calls": sum(d["monthly_calls"] for d in mine), "tier": worst([d["tier"] for d in mine]),
                         "cost_now": round(sum(d["cost_now"] for d in priced), 2), "cost_after": round(sum(d["cost_after"] for d in priced), 2),
                         "unpriced": len(movers) - len(priced)})
    movers = [d for d in hits if d["tier"] != "SUNSETS"]
    priced = [d for d in movers if d["cost_after"] is not None]
    return {"as_of": as_of.isoformat(), "usages_read": len(usages), "clear": cleared, "hits": len(hits),
            "checks": len(deps) - len(hits), "features_hit": len({d["feature_id"] for d in hits}),
            "decision": worst([d["tier"] for d in hits]), "calendar": calendar, "dependencies": deps,
            "cost_now": round(sum(d["cost_now"] for d in priced), 2), "cost_after": round(sum(d["cost_after"] for d in priced), 2),
            "unpriced": len(movers) - len(priced)}


# ---------------------------------------------------------------- output
def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def render_text(res: dict) -> str:
    lines = [f"as of {res['as_of']}: {_plural(res['usages_read'], 'usage')} read, {res['hits']} hit a retiring model, "
             f"{res['checks']} to check, {res['clear']} clear"]
    if res["calendar"]:
        lines.append("calendar")
    for c in res["calendar"]:
        who = f"{_plural(c['features'], 'feature')}  {c['monthly_calls']:,} calls/mo  {c['tier']}" if c["features"] else "no registered feature resolves to it"
        lines.append(f"  {c['retire_date']}  {clean(c['model_id']):<19} {c['days_left']:>4} days  {who}")
    hits = [d for d in res["dependencies"] if d["verdict"] == "hit"]
    if hits:
        lines.append("hits")
    for d in hits:
        parts = [f"{d['tier']:<8} {clean(d['feature_name'])} {d['role']} on {clean(d['model_id'])} retires {d['retire_date']}"]
        if d["slack_days"] is not None:
            parts.append(f"slack {d['slack_days']} days (needs {d['lead_days']})")
        if d["note"]:
            parts.append(f"[{clean(d['note'])}]")
        lines.append("  " + " ".join(parts))
    checks = [d for d in res["dependencies"] if d["verdict"] == "check"]
    if checks:
        lines.append("check (a person has to look)")
    for d in checks:
        ref = f' "{clean(d["model_ref"])}":' if d["model_ref"] else ""
        lines.append(f"  {clean(d['feature_name'])} {d['role']}{ref} {clean(d['note'])}")
    if not hits:
        lines.append("no usage resolves to a model with a retirement notice")
    if res["cost_now"] or res["cost_after"]:
        delta = res["cost_after"] - res["cost_now"]
        lines.append(f"cost per month on the named successors: ${res['cost_now']:,.2f} -> ${res['cost_after']:,.2f} ({'+' if delta >= 0 else '-'}${abs(delta):,.2f})"
                     + (f"; {res['unpriced']} without a priced successor" if res["unpriced"] else ""))
    lines.append(f"decision: {res['decision']}")
    return "\n".join(lines)


def run_report(args: argparse.Namespace) -> int:
    try:
        as_of = _date(args.as_of, "--as-of")
        policy = load_policy(args.policy)
        models = load_models(args.models)
        aliases = load_aliases(args.aliases, models) if args.aliases else {}
        features = load_features(args.features)
        usages = load_usages(args.usages, features)
        res = analyze(features, usages, models, aliases, as_of, policy, args.model)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, csv.Error) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    print(render_text(res) if args.format == "text" else json.dumps(res, indent=1, sort_keys=True))
    return 1 if res["decision"] in FAIL_TIERS[args.fail_on] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="deprecation_impact")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("report", help="map retirement notices to features")
    r.add_argument("--features", required=True)
    r.add_argument("--usages", required=True)
    r.add_argument("--models", required=True)
    r.add_argument("--aliases")
    r.add_argument("--policy", help="JSON file that overrides the assumed lead times")
    r.add_argument("--as-of", required=True, help="the date to count days from, YYYY-MM-DD")
    r.add_argument("--model", help="only this model_id, which must have a retirement notice")
    r.add_argument("--fail-on", choices=["late", "tight", "never"], default="late")
    r.add_argument("--format", choices=["text", "json"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_report(argparse.Namespace(
            features=os.path.join(d, "example_features.csv"), usages=os.path.join(d, "example_usages.csv"),
            models=os.path.join(d, "example_models.csv"), aliases=os.path.join(d, "example_aliases.csv"), policy=None,
            as_of=DEMO_AS_OF, model=None, fail_on="never", format="text"))
    if a.cmd == "report":
        return run_report(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
