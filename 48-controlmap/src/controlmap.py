"""controlmap: map each obligation to the controls that meet it and say whether the evidence is current.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 controlmap.py --demo
    python3 controlmap.py check OBLIGATIONS.csv CONTROLS.csv --terms TERMS.csv [--as-of YYYY-MM-DD]
                          [--grace 1.5] [--fail-on uncovered|gap|never] [--format text|csv]

Inputs (CSV, UTF-8, one header row):
    obligations  obligation_id, theme, applies_to (use-case classes separated by ;), statement (optional)
    controls     control_id, name, description, scope (classes separated by ;), test_cycle_days,
                 last_evidence_on (YYYY-MM-DD or empty), status (active or retired), owner (optional)
    terms        theme, phrase   (a phrase in a control's name or description says the control serves the theme)

Rules, all plain code, no model:
    1. A control matches an obligation when it is active and its name or description contains a phrase the
       terms file lists for the obligation's theme. A phrase preceded within 3 words by no, not, without,
       never, lacks, lacking, cannot, excludes, excluding or except does not count.
    2. The match is full when the control's scope includes every class the obligation applies to, partial
       when it includes some, and ignored when it includes none.
    3. Evidence is fresh when the newest item is no older than GRACE times the control's test cycle at the
       as-of date (GRACE defaults to 1.5; that value is an assumption, not taken from any rule).
    4. Status: COVERED (a full match with fresh evidence), STALE (full matches, none fresh), PARTIAL (only
       partial matches), UNCOVERED (no usable match), UNMAPPED (the terms file has no phrase for the theme,
       so the tool cannot tell a gap from a missing dictionary row).

Exit status: 0 when nothing at or above --fail-on was found, 1 when something was, 2 for bad or malformed
input. Fresh evidence shows that someone collected something recently; it does not show the control works.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import re
import sys

STATUSES = ("COVERED", "STALE", "PARTIAL", "UNCOVERED", "UNMAPPED")
GRACE_DEFAULT = 1.5
NEGATORS = frozenset(["no", "not", "without", "never", "lacks", "lacking", "cannot", "excludes", "excluding", "except"])
NEGATION_WINDOW = 3
DEMO_AS_OF = "2026-06-30"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class InputError(ValueError):
    """The input files or options are unusable. The command line turns this into exit status 2."""


# ---------------------------------------------------------------- safe output
def clean(text) -> str:
    """Make untrusted text safe on one line: control and non-printing characters become visible escapes."""
    return "".join(ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii") for ch in str(text))


def csv_safe(text) -> str:
    """Keep a spreadsheet from reading a cell as a formula."""
    s = clean(text)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


# ---------------------------------------------------------------- loading
def _read_table(path: str, required: list, label: str) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames
        if not header:
            raise InputError(f"{label}: the file is empty")
        missing = [c for c in required if c not in header]
        if missing:
            raise InputError(f"{label}: missing column(s) {', '.join(missing)}")
        rows = []
        for row in reader:
            if None in row:
                raise InputError(f"{label}: line {reader.line_num} has more fields than the header")
            if any(v is None for v in row.values()):
                raise InputError(f"{label}: line {reader.line_num} has fewer fields than the header")
            rows.append({k: v.strip() for k, v in row.items()})
    if not rows:
        raise InputError(f"{label}: the file has a header and no rows")
    return rows


def _classes(value: str, label: str, ident: str) -> frozenset:
    out = frozenset(p.strip() for p in value.split(";") if p.strip())
    if not out:
        raise InputError(f"{label}: {clean(ident)} has an empty class list")
    return out


def _theme_key(theme: str) -> str:
    return " ".join(tokens(theme))


def parse_date(value: str, what: str) -> datetime.date:
    if not DATE_RE.match(value):
        raise InputError(f"{what}: '{clean(value)}' is not a date in YYYY-MM-DD form")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise InputError(f"{what}: '{clean(value)}' is not a real date")


def load_obligations(path: str) -> list:
    rows = _read_table(path, ["obligation_id", "theme", "applies_to"], "obligations")
    seen, out = set(), []
    for r in rows:
        oid = r["obligation_id"]
        if not oid or not r["theme"]:
            raise InputError("obligations: a row has an empty obligation_id or theme")
        if oid in seen:
            raise InputError(f"obligations: duplicate obligation_id {clean(oid)}")
        seen.add(oid)
        out.append({"obligation_id": oid, "theme": r["theme"], "statement": r.get("statement", ""),
                    "applies_to": _classes(r["applies_to"], "obligations", oid)})
    return out


def load_controls(path: str, as_of: datetime.date) -> list:
    rows = _read_table(path, ["control_id", "name", "description", "scope", "test_cycle_days", "last_evidence_on", "status"], "controls")
    seen, out = set(), []
    for r in rows:
        cid = r["control_id"]
        if not cid or not r["name"]:
            raise InputError("controls: a row has an empty control_id or name")
        if cid in seen:
            raise InputError(f"controls: duplicate control_id {clean(cid)}")
        seen.add(cid)
        if r["status"] not in ("active", "retired"):
            raise InputError(f"controls: {clean(cid)} has status '{clean(r['status'])}'; use active or retired")
        if not re.fullmatch(r"\d+", r["test_cycle_days"]) or int(r["test_cycle_days"]) < 1:
            raise InputError(f"controls: {clean(cid)} has test_cycle_days '{clean(r['test_cycle_days'])}'; use a whole number of days, 1 or more")
        age = None
        if r["last_evidence_on"]:
            last = parse_date(r["last_evidence_on"], f"controls: {clean(cid)} last_evidence_on")
            if last > as_of:
                raise InputError(f"controls: {clean(cid)} has evidence dated {last.isoformat()}, after the as-of date {as_of.isoformat()}")
            age = (as_of - last).days
        out.append({"control_id": cid, "name": r["name"], "description": r["description"], "owner": r.get("owner", ""),
                    "scope": _classes(r["scope"], "controls", cid), "cycle": int(r["test_cycle_days"]),
                    "age": age, "active": r["status"] == "active"})
    return out


def load_terms(path: str) -> dict:
    """{normalised theme: [phrases in file order]}"""
    out = {}
    for r in _read_table(path, ["theme", "phrase"], "terms"):
        if not r["theme"] or not tokens(r["phrase"]):
            raise InputError(f"terms: a row has an empty theme or a phrase with no letters or digits ('{clean(r['phrase'])}')")
        phrases = out.setdefault(_theme_key(r["theme"]), [])
        if r["phrase"] not in phrases:
            phrases.append(r["phrase"])
    return out


# ---------------------------------------------------------------- matching
def tokens(text: str) -> list:
    return re.findall(r"[a-z0-9]+", re.sub(r"n['’]t\b", " not", str(text).lower()))


def find_phrase(phrases: list, text: str, negation: bool = True) -> tuple:
    """(phrase, negated): the first listed phrase with a clear occurrence in the text, else ('', the first phrase
    found only after a negator, or '')."""
    toks, negated = tokens(text), ""
    for ph in phrases:
        p = tokens(ph)
        denied = False
        for i in range(len(toks) - len(p) + 1):
            if toks[i:i + len(p)] == p:
                if negation and NEGATORS & set(toks[max(0, i - NEGATION_WINDOW):i]):
                    denied = True
                else:
                    return ph, ""
        if denied and not negated:
            negated = ph
    return "", negated


def _coverage(applies: frozenset, scope: frozenset) -> str:
    return "full" if applies <= scope else "partial" if applies & scope else "none"


def _status(links: list) -> str:
    usable = [l for l in links if l["coverage"] != "none"]
    if any(l["coverage"] == "full" for l in usable):
        return "COVERED" if any(l["coverage"] == "full" and l["fresh"] for l in usable) else "STALE"
    return "PARTIAL" if usable else "UNCOVERED"


def analyze(obligations: list, controls: list, terms: dict, grace: float = GRACE_DEFAULT, negation: bool = True) -> dict:
    """Status per obligation, orphan controls, unmatched phrases and the consolidated evidence requests."""
    info = {c["control_id"]: dict(c, fresh=c["age"] is not None and c["age"] <= grace * c["cycle"], limit=grace * c["cycle"])
            for c in controls}
    rows, linked = [], set()
    for o in obligations:
        phrases = terms.get(_theme_key(o["theme"]))
        row = {"obligation_id": o["obligation_id"], "theme": o["theme"], "statement": o["statement"],
               "applies_to": sorted(o["applies_to"]), "links": [], "skipped": []}
        if phrases is None:
            row["status"] = "UNMAPPED"
            rows.append(row)
            continue
        for c in controls:
            c = info[c["control_id"]]
            hit, denied = "", ""
            for text in (c["name"], c["description"]):
                h, d = find_phrase(phrases, text, negation)
                hit, denied = hit or h, denied or d
            if not hit:
                if denied:
                    row["skipped"].append({"control_id": c["control_id"], "why": f'negated phrase "{denied}"'})
                continue
            if not c["active"]:
                row["skipped"].append({"control_id": c["control_id"], "why": "retired"})
                continue
            row["links"].append({"control_id": c["control_id"], "name": c["name"], "phrase": hit, "owner": c["owner"],
                                 "coverage": _coverage(o["applies_to"], c["scope"]), "missing": sorted(o["applies_to"] - c["scope"]),
                                 "age": c["age"], "limit": c["limit"], "fresh": c["fresh"]})
            linked.add(c["control_id"])
        row["status"] = _status(row["links"])
        rows.append(row)
    orphans = [c["control_id"] for c in controls if c["active"] and c["control_id"] not in linked]
    unmatched = []
    for key, phrases in sorted(terms.items()):
        for ph in phrases:
            if not any(find_phrase([ph], c["name"], negation)[0] or find_phrase([ph], c["description"], negation)[0]
                       for c in controls if c["active"]):
                unmatched.append(f"{key}: {ph}")
    asked = sorted({l["control_id"] for r in rows if r["status"] == "STALE" for l in r["links"] if l["coverage"] == "full"})
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    return {"rows": rows, "orphans": orphans, "unmatched_phrases": unmatched, "requests": asked, "counts": counts,
            "controls": info, "stale_obligations": counts["STALE"]}


# ---------------------------------------------------------------- reporting
def _evidence(l: dict) -> str:
    return "no evidence on file" if l["age"] is None else f"evidence {l['age']} days old, limit {l['limit']:g}"


def _primary(row: dict) -> dict:
    want = "partial" if row["status"] == "PARTIAL" else "full"
    pool = [l for l in row["links"] if l["coverage"] == want]
    if row["status"] == "COVERED":
        pool = [l for l in pool if l["fresh"]]
    return sorted(pool, key=lambda l: (len(l["missing"]), l["age"] is None, l["age"] or 0, l["control_id"]))[0]


def reason(row: dict) -> str:
    """One line saying why the obligation has its status."""
    st = row["status"]
    if st == "UNMAPPED":
        return f'the terms file has no phrase for the theme "{row["theme"]}"'
    if st == "UNCOVERED":
        out = f'no active control in scope matches the theme "{row["theme"]}"'
        notes = [f"{l['control_id']} matches the wording but runs outside the scope" for l in row["links"]]
        notes += [f"{s['control_id']} {s['why']}" for s in row["skipped"]]
        return out + (" (" + "; ".join(notes) + ")" if notes else "")
    p = _primary(row)
    scope = "scope full" if p["coverage"] == "full" else "scope misses " + ", ".join(p["missing"])
    more = len([l for l in row["links"] if l["coverage"] != "none"]) - 1
    return f'{p["control_id"]} {p["name"]}: matched "{p["phrase"]}"; {scope}; {_evidence(p)}' + (f"; {more} more control(s) match" if more else "")


def render_text(res: dict, as_of: str, n_controls: int, n_retired: int) -> str:
    lines = [f"controlmap  as of {as_of}  {len(res['rows'])} obligations, {n_controls} controls ({n_controls - n_retired} active, {n_retired} retired)"]
    for r in res["rows"]:
        lines.append(clean(f"{r['obligation_id']:<8}{r['status']:<10} {reason(r)}"))
    if not any(r["links"] for r in res["rows"]):
        lines.append("note: no control matched any obligation; check the terms file and the wording of the controls")
    lines.append("statuses: " + ", ".join(f"{s} {res['counts'][s]}" for s in STATUSES if res["counts"][s]))
    names = {c: res["controls"][c]["name"] for c in res["controls"]}
    lines.append(clean("orphan controls: " + (f"{len(res['orphans'])} (" + "; ".join(f"{c} {names[c]}" for c in res["orphans"]) + ")" if res["orphans"] else "none")))
    lines.append(clean("terms that matched no active control: " + (f"{len(res['unmatched_phrases'])} (" + "; ".join(res["unmatched_phrases"]) + ")" if res["unmatched_phrases"] else "none")))
    if res["requests"]:
        lines.append(clean(f"evidence requests: {len(res['requests'])} control(s) for {res['stale_obligations']} stale obligation(s) ("
                           + "; ".join(f"{c} {res['controls'][c]['owner'] or 'no owner listed'}" for c in res["requests"]) + ")"))
    else:
        lines.append("evidence requests: none")
    return "\n".join(lines)


def render_csv(res: dict) -> str:
    out = ["obligation_id,theme,status,controls,reason"]
    for r in res["rows"]:
        cells = [r["obligation_id"], r["theme"], r["status"], ";".join(l["control_id"] for l in r["links"] if l["coverage"] != "none"), reason(r)]
        out.append(",".join('"' + csv_safe(c).replace('"', '""') + '"' for c in cells))
    return "\n".join(out)


# ---------------------------------------------------------------- command line
def run_check(ob_path, ctl_path, terms_path, as_of, grace, fail_on, fmt) -> int:
    try:
        if as_of is None:
            when = datetime.date.today()
        else:
            when = parse_date(as_of, "--as-of")
        try:
            g = float(grace)
        except ValueError:
            raise InputError(f"--grace: '{clean(grace)}' is not a number")
        if not g > 0 or g == float("inf"):
            raise InputError(f"--grace: '{clean(grace)}' must be a positive number")
        obligations = load_obligations(ob_path)
        controls = load_controls(ctl_path, when)
        terms = load_terms(terms_path)
    except (OSError, ValueError, csv.Error) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    if as_of is None:
        print(f"note: no --as-of given, so evidence age is counted to today, {when.isoformat()}; "
              "pass --as-of to make the run repeatable", file=sys.stderr)
    res = analyze(obligations, controls, terms, g)
    n_retired = sum(1 for c in controls if not c["active"])
    print(render_csv(res) if fmt == "csv" else render_text(res, when.isoformat(), len(controls), n_retired))
    c = res["counts"]
    if fail_on == "never":
        return 0
    bad = c["UNCOVERED"] + c["UNMAPPED"] if fail_on == "uncovered" else len(res["rows"]) - c["COVERED"]
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="controlmap")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="map obligations to controls and report a status for each")
    c.add_argument("obligations")
    c.add_argument("controls")
    c.add_argument("--terms", required=True, help="CSV with columns theme, phrase")
    c.add_argument("--as-of", help="date the evidence age is counted to, YYYY-MM-DD (default: today)")
    c.add_argument("--grace", default=str(GRACE_DEFAULT), help="evidence is fresh up to this many test cycles old (default 1.5)")
    c.add_argument("--fail-on", choices=["uncovered", "gap", "never"], default="uncovered")
    c.add_argument("--format", choices=["text", "csv"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_obligations.csv"), os.path.join(d, "example_controls.csv"),
                         os.path.join(d, "example_terms.csv"), DEMO_AS_OF, GRACE_DEFAULT, "never", "text")
    if a.cmd == "check":
        return run_check(a.obligations, a.controls, a.terms, a.as_of, a.grace, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
