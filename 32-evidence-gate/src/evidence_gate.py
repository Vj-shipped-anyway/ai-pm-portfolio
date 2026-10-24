"""evidence_gate: decide whether a pull request may merge, from the evidence its change record lists.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 evidence_gate.py --demo
    python3 evidence_gate.py check (--body BODY.md | --event EVENT.json) --tiers TIERS.csv
                                   [--registry REGISTRY.csv] [--files FILES.txt] [--as-of YYYY-MM-DD]
                                   [--fail-on block|review|never] [--format text|github]

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad or malformed input.
The decision is BLOCK (evidence the tier requires is missing, stale or unusable), REVIEW (nothing is
missing that the gate can prove, but a person should look: the tier label disagrees with the registry,
the tier is the author's own, or a reference is an external link) or ALLOW. There is no model in this
file: the parser, the tier table and the checks are plain rules.

The change record the parser reads (in the pull request description):

    Use case: UC-014
    Declared tier: 2
    - [x] E01 Use-case card | ref: evidence/UC-014/E01-use-case-card.md | date: 2026-09-02

Text inside HTML comments and fenced code blocks is not read, because a reader does not see it as
part of the record. Evidence is matched by its explicit id (E01 to E99), never by wording or path.

Tier table (CSV): evidence_id, evidence_item, first_tier, max_age_days. An item is required at its
first_tier and every tier above it. Registry (CSV): use_case_id, tier. Files (text): one repository
path per line, for example the output of `git ls-files`.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import posixpath
import re
import sys

DECISION_RANK = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}
# Every finding kind, its class, in the order findings are printed.
KIND_CLASS = {
    "no_record": "block",
    "conflicting_fields": "block",
    "use_case_missing": "block",
    "tier_unknown": "block",
    "tier_mismatch": "review",
    "tier_unverified": "review",
    "evidence_missing": "block",
    "not_ticked": "block",
    "no_reference": "block",
    "reference_outside_repo": "block",
    "reference_not_found": "block",
    "reference_external": "review",
    "date_invalid": "block",
    "date_future": "block",
    "stale": "block",
}

_FLAGS = re.IGNORECASE | re.ASCII
_FENCE = re.compile(r"(`{3,}|~{3,})")
_FIELD = re.compile(r"^\s*(?:[-*+]\s+)?(use case|declared tier)\s*:(.*)$", _FLAGS)
_EVIDENCE = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(E[0-9]{2})(?![0-9A-Za-z])(.*)$", _FLAGS)
_TIER = re.compile(r"(?:tier\s*)?([1-4])(?![0-9A-Za-z])", _FLAGS)
_MD_LINK = re.compile(r"^\[[^\]]*\]\(([^)]*)\)$")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_EXTERNAL = re.compile(r"^https?://", re.IGNORECASE)
_DATE = re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")
_ID = re.compile(r"E[0-9]{2}")
_WHOLE = re.compile(r"[0-9]+")


class InputError(ValueError):
    """Bad input to the tool (exit status 2), as opposed to a problem found in a pull request (exit status 1)."""


# ---------------------------------------------------------------- text safety
def clean(text, limit: int = 120) -> str:
    """Make untrusted text safe to print: control characters (including line breaks) become spaces, long text is cut."""
    t = _CONTROL.sub(" ", str(text))
    return t if len(t) <= limit else t[:limit - 3] + "..."


def quote(text, limit: int = 60) -> str:
    return "'" + clean(text, limit) + "'"


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so pull request text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


# ---------------------------------------------------------------- reading the pull request description
def _strip_comments(line: str):
    """(line without complete <!-- --> comments, True when an unterminated comment starts on it)."""
    out, pos = [], 0
    while True:
        start = line.find("<!--", pos)
        if start < 0:
            out.append(line[pos:])
            return "".join(out), False
        end = line.find("-->", start + 4)
        out.append(line[pos:start])
        if end < 0:
            return "".join(out), True
        pos = end + 3


def visible_lines(body: str) -> list:
    """The lines a reader sees: HTML comments and fenced code blocks removed. An unterminated one runs to the end."""
    out, in_comment, fence = [], False, None
    for line in body.splitlines():
        if fence is not None:
            if line.strip().startswith(fence):
                fence = None
            continue
        if in_comment:
            end = line.find("-->")
            if end < 0:
                continue
            in_comment = False
            line = line[end + 3:]
        line, in_comment = _strip_comments(line)
        m = _FENCE.match(line.lstrip())
        if m:
            fence = m.group(1)
            continue
        out.append(line)
    return out


def parse_tier(text: str):
    """1 to 4 from text such as '3' or 'Tier 3', else None."""
    m = _TIER.match(text.strip())
    return int(m.group(1)) if m else None


def parse_date(text: str):
    """A datetime.date from YYYY-MM-DD (month and day may lack the leading zero), else None."""
    m = _DATE.fullmatch(text.strip())
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _entry(m) -> dict:
    kv = {}
    for seg in m.group(3).split("|")[1:]:
        key, sep, value = seg.partition(":")
        key = key.strip().lower()
        if sep and key in ("ref", "date") and key not in kv:
            kv[key] = value.strip()
    return {"id": m.group(2).upper(), "ticked": m.group(1) != " ", "ref": kv.get("ref"), "date": kv.get("date")}


def parse_record(body: str) -> dict:
    """Read the change record from a pull request description.

    Returns {has_record, use_case, declared_tier, declared_text, conflicts, entries}. has_record is False when the
    description has no 'Use case:' or 'Declared tier:' line and no evidence line.
    """
    values = {"use case": [], "declared tier": []}
    entries = []
    for line in visible_lines(body):
        m = _EVIDENCE.match(line)
        if m:
            entries.append(_entry(m))
            continue
        m = _FIELD.match(line.replace("**", "").replace("__", ""))
        if m and m.group(2).strip():
            values[m.group(1).lower()].append(m.group(2).strip())
    conflicts = [label for label in ("use case", "declared tier") if len(set(values[label])) > 1]
    declared_text = values["declared tier"][0] if values["declared tier"] else ""
    return {"has_record": bool(entries or values["use case"] or values["declared tier"]),
            "use_case": values["use case"][0] if values["use case"] else None,
            "declared_tier": parse_tier(declared_text), "declared_text": declared_text,
            "conflicts": conflicts, "entries": entries}


# ---------------------------------------------------------------- tier table, registry, file listing
def _read_csv(path: str, columns: list) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        try:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{clean(path)}: the file is empty")
            missing = [c for c in columns if c not in reader.fieldnames]
            if missing:
                raise InputError(f"{clean(path)}: missing column {', '.join(missing)}")
            return list(reader)
        except csv.Error as e:
            raise InputError(f"{clean(path)}: not readable as CSV ({clean(e)})")


def _whole(value, lo: int, hi: int):
    text = (value or "").strip()
    if not _WHOLE.fullmatch(text) or not lo <= int(text) <= hi:
        return None
    return int(text)


def load_tiers(path: str) -> list:
    """The tier-to-evidence table as a list of {id, item, first_tier, max_age_days}, sorted by id."""
    rows = _read_csv(path, ["evidence_id", "evidence_item", "first_tier", "max_age_days"])
    if not rows:
        raise InputError(f"{clean(path)}: the table has no evidence rows")
    out, seen = [], set()
    for n, r in enumerate(rows, 2):
        eid = (r["evidence_id"] or "").strip()
        tier = _whole(r["first_tier"], 1, 4)
        age = _whole(r["max_age_days"], 1, 36500)
        if not _ID.fullmatch(eid) or eid in seen:
            raise InputError(f"{clean(path)} row {n}: evidence_id must be E and two digits, and unique")
        if tier is None or age is None or not (r["evidence_item"] or "").strip():
            raise InputError(f"{clean(path)} row {n}: needs an item name, a first_tier from 1 to 4 and a max_age_days of 1 or more")
        seen.add(eid)
        out.append({"id": eid, "item": r["evidence_item"].strip(), "first_tier": tier, "max_age_days": age})
    return sorted(out, key=lambda i: i["id"])


def required_ids(tiers: list, tier: int) -> list:
    """Evidence ids a pull request must carry at this tier (cumulative: a higher tier owes everything below it)."""
    return [i["id"] for i in tiers if i["first_tier"] <= tier]


def load_registry(path: str) -> dict:
    """{use_case_id: tier} from a CSV with columns use_case_id and tier."""
    out = {}
    for n, r in enumerate(_read_csv(path, ["use_case_id", "tier"]), 2):
        uc = (r["use_case_id"] or "").strip()
        tier = _whole(r["tier"], 1, 4)
        if not uc or tier is None:
            raise InputError(f"{clean(path)} row {n}: needs a use_case_id and a tier from 1 to 4")
        if out.get(uc, tier) != tier:
            raise InputError(f"{clean(path)} row {n}: {quote(uc)} appears with two different tiers")
        out[uc] = tier
    return out


def _norm_path(p: str) -> str:
    return posixpath.normpath(p.replace("\\", "/"))


def load_files(path: str) -> set:
    """The repository paths, one per line (the output of `git ls-files`)."""
    with open(path, encoding="utf-8-sig") as fh:
        paths = {_norm_path(ln.strip()) for ln in fh if ln.strip()}
    if not paths:
        raise InputError(f"{clean(path)}: the file listing is empty")
    return paths


def load_body(body_path, event_path) -> str:
    """The pull request description, from a markdown file or from the pull_request event JSON GitHub provides."""
    if event_path:
        with open(event_path, encoding="utf-8") as fh:
            event = json.load(fh)
        pr = event.get("pull_request") if isinstance(event, dict) else None
        if not isinstance(pr, dict) or "body" not in pr:
            raise InputError(f"{clean(event_path)}: no pull_request.body; run this on a pull_request event")
        if pr["body"] is None:
            return ""
        if not isinstance(pr["body"], str):
            raise InputError(f"{clean(event_path)}: pull_request.body must be text or null")
        return pr["body"]
    with open(body_path, encoding="utf-8", newline="") as fh:
        return fh.read()


# ---------------------------------------------------------------- the checks
def _clean_ref(ref: str) -> str:
    ref = ref.strip()
    m = _MD_LINK.match(ref)
    if m:
        ref = m.group(1).strip()
    return ref.strip("`<>").strip()


def _classify_ref(ref: str):
    """('external', ref), ('outside', ref) or ('path', normalised path)."""
    if _EXTERNAL.match(ref):
        return "external", ref
    if _SCHEME.match(ref):
        return "outside", ref
    norm = _norm_path(ref)
    if norm.startswith("/") or norm == ".." or norm.startswith("../"):
        return "outside", ref
    return "path", norm


def _check_entry(e: dict, item: dict, files, as_of):
    """(kind, text) for the first problem with one listed evidence line, or None when it passes."""
    eid = item["id"]
    if not e["ticked"]:
        return "not_ticked", f"{eid} is listed but its box is not ticked"
    ref = _clean_ref(e["ref"] or "")
    if ref == "":
        return "no_reference", f"{eid} is ticked with no 'ref:' file"
    where, norm = _classify_ref(ref)
    if where == "outside":
        return "reference_outside_repo", f"{eid} points outside the repository: {quote(ref)}"
    if where == "path" and files is not None and norm not in files:
        return "reference_not_found", f"{eid} names a file that is not in the repository: {quote(ref)}"
    if as_of is not None:
        d = parse_date(e["date"] or "")
        if d is None:
            return "date_invalid", f"{eid} has no usable date (found {quote(e['date'] or '', 30)}; use YYYY-MM-DD)"
        age = (as_of - d).days
        if age < 0:
            return "date_future", f"{eid} is dated {d.isoformat()}, after the as-of date {as_of.isoformat()}"
        if age > item["max_age_days"]:
            return "stale", f"{eid} is {age} days old; the limit is {item['max_age_days']}"
    if where == "external":
        return "reference_external", f"{eid} is an external link, which the gate cannot check: {quote(ref)}"
    return None


def _finish(record, registry_tier, required, ids, found, notes) -> dict:
    findings = []
    for kind, cls in KIND_CLASS.items():
        if kind not in found:
            continue
        pairs = found[kind]
        items = sorted({i for i, _ in pairs if i})
        if kind == "evidence_missing":
            verb = "is" if len(items) == 1 else "are"
            reason = f"{', '.join(items)} {verb} required at tier {required} and not in the record"
        else:
            reason = "; ".join(t for _, t in pairs)
        findings.append({"kind": kind, "class": cls, "items": items, "reason": reason})
    decision = decide(findings)
    return {"use_case": record["use_case"], "declared_tier": record["declared_tier"], "registry_tier": registry_tier,
            "required_tier": required, "required": ids, "findings": findings, "notes": notes, "decision": decision}


def evaluate(record: dict, tiers: list, registry=None, files=None, as_of=None) -> dict:
    """Check one parsed change record. registry, files and as_of are optional; a check whose input is None is skipped
    and the result says so in notes."""
    found, notes = {}, []

    def add(kind: str, item: str, text: str) -> None:
        found.setdefault(kind, []).append((item, text))

    if not record["has_record"]:
        add("no_record", "", "the description has no AI change record: no 'Use case:' line, no 'Declared tier:' line and no evidence line")
        return _finish(record, None, None, [], found, notes)
    uc, declared = record["use_case"], record["declared_tier"]
    for label in record["conflicts"]:
        add("conflicting_fields", "", f"'{label}' is given more than once with different values")
    if uc is None:
        add("use_case_missing", "", "no 'Use case:' line with a value")
    registry_tier = registry.get(uc) if registry is not None and uc is not None else None
    if registry_tier is not None:
        required = registry_tier
        if declared != registry_tier:
            shown = f"tier {declared}" if declared else f"no valid tier ({quote(record['declared_text'], 30)})"
            add("tier_mismatch", "", f"the record declares {shown} but the registry holds {quote(uc, 40)} at tier {registry_tier}; the registry sets the bar")
    elif declared is not None:
        required = declared
        why = "is not in the registry" if registry is not None and uc is not None else "cannot be looked up (no registry or no use case)"
        add("tier_unverified", "", f"{quote(uc or '', 40)} {why}, so tier {declared} is the author's own")
    else:
        required = None
        add("tier_unknown", "", "no valid 'Declared tier:' (1 to 4) and no registry entry to take the tier from")
    ids = required_ids(tiers, required) if required else []
    by_id = {}
    for e in record["entries"]:
        by_id.setdefault(e["id"], []).append(e)
    for item in tiers:
        if item["id"] not in ids:
            continue
        entries = by_id.get(item["id"])
        if not entries:
            add("evidence_missing", item["id"], "")
            continue
        results = [_check_entry(e, item, files, as_of) for e in entries]
        if any(r is None for r in results):
            continue
        externals = [r for r in results if r[0] == "reference_external"]
        problem = externals[0] if externals else results[0]
        add(problem[0], item["id"], problem[1])
    if files is None:
        notes.append("reference files were not checked (no file listing given)")
    if as_of is None:
        notes.append("dates were not checked (no as-of date)")
    return _finish(record, registry_tier, required, ids, found, notes)


def decide(findings: list) -> str:
    classes = {f["class"] for f in findings}
    return "BLOCK" if "block" in classes else "REVIEW" if "review" in classes else "ALLOW"


# ---------------------------------------------------------------- command line
def render(res: dict, fmt: str) -> str:
    uc = clean(res["use_case"] or "(none)", 60)
    lines = []
    if fmt == "github":
        for f in res["findings"]:
            level = "error" if f["class"] == "block" else "warning"
            lines.append(f"::{level} title=evidence-gate {f['kind']}::" + escape_annotation(f"{uc}: {f['reason']}"))
        for n in res["notes"]:
            lines.append("::notice title=evidence-gate::" + escape_annotation(n))
        lines.append(f"::notice title=evidence-gate::decision {res['decision']}")
        return "\n".join(lines)
    bar = f"tier {res['required_tier']}, {len(res['required'])} evidence items" if res["required_tier"] else "unknown"
    lines.append(f"use case {uc}   declared tier {res['declared_tier'] or '(none)'}   "
                 f"registry tier {res['registry_tier'] or '(not listed)'}   bar: {bar}")
    for f in res["findings"]:
        lines.append(f"  [{f['class']:<6}] {f['kind']:<22} {f['reason']}")
    if not res["findings"]:
        lines.append("  every required evidence item is listed, ticked, referenced and in date")
    for n in res["notes"]:
        lines.append(f"  note: {n}")
    lines.append(f"decision: {res['decision']}")
    return "\n".join(lines)


def run_check(body_path, event_path, tiers_path, registry_path, files_path, as_of_text, fail_on, fmt) -> int:
    try:
        tiers = load_tiers(tiers_path)
        registry = load_registry(registry_path) if registry_path else None
        files = load_files(files_path) if files_path else None
        if as_of_text:
            as_of = parse_date(as_of_text)
            if as_of is None:
                raise InputError(f"--as-of {quote(as_of_text, 30)} is not a date; use YYYY-MM-DD")
        else:
            as_of = datetime.date.today()
        body = load_body(body_path, event_path)
    except (OSError, ValueError, RecursionError) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    res = evaluate(parse_record(body), tiers, registry, files, as_of)
    print(render(res, fmt))
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[res["decision"]] >= DECISION_RANK[{"block": "BLOCK", "review": "REVIEW"}[fail_on]] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="evidence_gate")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_pr_body.md)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check one pull request description")
    src = c.add_mutually_exclusive_group(required=True)
    src.add_argument("--body", help="a markdown file holding the pull request description")
    src.add_argument("--event", help="the pull_request event JSON (GITHUB_EVENT_PATH)")
    c.add_argument("--tiers", required=True, help="CSV: evidence_id, evidence_item, first_tier, max_age_days")
    c.add_argument("--registry", help="CSV: use_case_id, tier. The registry tier sets the bar when the use case is listed")
    c.add_argument("--files", help="text file of repository paths; a reference to a path not listed is a problem")
    c.add_argument("--as-of", help="date to measure evidence age from (YYYY-MM-DD); default today")
    c.add_argument("--fail-on", choices=["block", "review", "never"], default="block")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        try:
            with open(os.path.join(d, "as_of.txt"), encoding="utf-8") as fh:
                as_of_text = fh.read().strip()
        except OSError as e:
            print(f"input error: {clean(e)}", file=sys.stderr)
            return 2
        return run_check(os.path.join(d, "example_pr_body.md"), None, os.path.join(d, "tier_evidence.csv"),
                         os.path.join(d, "registry.csv"), os.path.join(d, "repo_files.txt"), as_of_text, "never", "text")
    if a.cmd == "check":
        return run_check(a.body, a.event, a.tiers, a.registry, a.files, a.as_of, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
