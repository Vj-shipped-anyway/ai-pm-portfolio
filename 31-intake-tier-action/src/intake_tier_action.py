"""intake_tier_action: read an AI intake issue (the markdown body an issue form produces), recompute the
risk tier from its fields, and say which labels and which comment the issue should carry.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 intake_tier_action.py --demo
    python3 intake_tier_action.py check BODY.md|- [--catalog catalog.csv] [--registry registry.csv --issue-number N]
                                  [--labels labels.json] [--out-dir DIR] [--format text|github|json]
                                  [--fail-on needs-info|mismatch|never]

BODY.md is the issue body; "-" reads it from standard input. --catalog is a CSV with dataset_name and
catalog_class. --registry is a CSV with issue_number and vendor_model (an export from procurement) and
needs --issue-number. --labels is a JSON list of the labels the issue carries now, so the tool can say
which of its own labels to add and which to remove. --out-dir writes labels_add.txt, labels_remove.txt
and comment.md for the Action to apply.

Exit status: 0 normally; 1 when the result is at or above --fail-on (default never); 2 for input that
cannot be read (missing file, not text, a catalog or registry with a bad row, a bad labels file).

There is no model here. The parser reads headings, the rubric adds points, the labels are a fixed set.
The rubric (points per input, tier = min(4, 1 + points // 4)) and the evidence list are assumptions of
this prototype, not taken from any framework.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys

MARKER = "<!-- intake-tier-action -->"

# (key, heading as the issue form writes it)
FIELDS = [("summary", "Use case summary"), ("unit", "Sponsor unit"), ("dataset", "Dataset name"),
          ("customer_facing", "Customer-facing"), ("autonomy", "Decision autonomy"), ("data_class", "Data class"),
          ("vendor", "Vendor model"), ("regulatory", "Regulatory scope"), ("exposure", "Financial exposure band"),
          ("declared", "Declared tier")]
LABEL_OF = dict(FIELDS)
KEY_OF = {label.lower(): key for key, label in FIELDS}
CHOICES = {"customer_facing": ["yes", "no", "unsure"], "autonomy": ["advisory", "assisted", "automated"],
           "data_class": ["public", "internal", "confidential", "restricted"],
           "vendor": ["none", "self_hosted", "vendor_api"],
           "regulatory": ["none", "privacy", "aml", "udaap", "fair_lending"],
           "exposure": ["lt_1m", "1m_10m", "10m_50m", "gt_50m"], "declared": ["1", "2", "3", "4"]}
POINTS = {"customer_facing": {"yes": 2, "no": 0}, "autonomy": {"advisory": 0, "assisted": 1, "automated": 3},
          "data_class": {"public": 0, "internal": 1, "confidential": 2, "restricted": 3},
          "vendor": {"none": 0, "self_hosted": 1, "vendor_api": 2},
          "regulatory": {"none": 0, "privacy": 1, "aml": 2, "udaap": 2, "fair_lending": 3},
          "exposure": {"lt_1m": 0, "1m_10m": 1, "10m_50m": 2, "gt_50m": 3}}
RUBRIC_KEYS = ["customer_facing", "autonomy", "data_class", "vendor", "regulatory", "exposure"]
REQUIRED = ["autonomy", "data_class", "vendor", "regulatory", "exposure"]
CUE_RE = re.compile(r"\b(customer|client|borrower|cardholder|applicant|consumer|caller|depositor|account holder)s?\b",
                    re.IGNORECASE)
HEADING_RE = re.compile(r"^###[ \t]+(.+?)[ \t]*$")
MANAGED = ["ai-tier:1", "ai-tier:2", "ai-tier:3", "ai-tier:4", "needs-info", "tier-mismatch"]
EVIDENCE = [(1, "E01", "Use-case card with a named line-1 owner"), (1, "E02", "Data-source attestation"),
            (2, "E03", "Evaluation plan and results summary"), (2, "E04", "Privacy and data-handling review"),
            (3, "E05", "Independent validation with effective challenge"), (3, "E06", "Human review design"),
            (3, "E07", "Decision logging and lineage plan"), (3, "E08", "Vendor and third-party due diligence"),
            (4, "E09", "Regulatory-scope legal review"), (4, "E10", "Fallback and exit plan"),
            (4, "E11", "Chief risk officer sign-off")]
FAIL_RANK = {"never": 3, "needs-info": 2, "mismatch": 1}


class InputError(Exception):
    """Input the tool cannot read. The command line turns it into exit status 2."""


def tier_from_score(score: int) -> int:
    return min(4, 1 + score // 4)


def safe_text(value, limit: int = 40) -> str:
    """Make sponsor text safe to echo: letters, digits, space and a few marks only, so it cannot carry a
    mention, a link, markup or a workflow command into a comment, a log or an annotation."""
    s = re.sub(r"[^A-Za-z0-9 _.\-/]", "?", " ".join(str(value).split()))
    return s if len(s) <= limit else s[:limit] + "..."


def escape_annotation(text: str) -> str:
    """Escape a workflow-command message the way GitHub documents, so text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


# ---------------------------------------------------------------- reading the issue body
def split_sections(body: str):
    """Split on the form's own headings. Any other '###' line also ends a section, and its text is dropped.
    Returns ({key: text}, set of keys whose heading appears twice)."""
    sections, dups, current = {}, set(), None
    for line in body.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        m = HEADING_RE.match(line)
        if m:
            current = KEY_OF.get(" ".join(m.group(1).split()).lower())
            if current in sections:
                dups.add(current)
            elif current:
                sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}, dups


def read_form(body: str) -> dict:
    """Read the form. Returns {"values": {key: normalized text}, "problems": [...], "present": {keys whose
    heading appears}}. A problem stops the tier: the tool does not guess a missing input."""
    sections, dups = split_sections(body)
    values, problems = {}, []
    for key, label in FIELDS:
        if key in dups:
            problems.append("heading '%s' appears more than once, so its value is ambiguous" % label)
            continue
        raw = sections.get(key)
        if raw is None:
            if key in REQUIRED:
                problems.append("heading '%s' is missing" % label)
            continue
        if raw == "_No response_":
            raw = ""
        if key in ("summary", "unit", "dataset"):
            if raw:
                values[key] = raw if key == "summary" else " ".join(raw.split())
            continue
        norm = " ".join(raw.split()).lower()
        if norm and norm not in CHOICES[key]:
            if key == "declared":
                continue
            problems.append("'%s' has the value '%s'; allowed: %s" % (label, safe_text(raw), ", ".join(CHOICES[key])))
        elif norm:
            values[key] = norm
        elif key in REQUIRED:
            problems.append("'%s' is blank" % label)
    return {"values": values, "problems": problems, "present": set(sections)}


# ---------------------------------------------------------------- the recompute
def assess(body: str, catalog=None, registry=None, issue_number=None) -> dict:
    """Recompute the tier. catalog maps a lower-case dataset name to a class; registry maps an issue number
    to a vendor model. Either may be None, and then that check is not made."""
    form = read_form(body)
    v, problems, flags, notes = form["values"], list(form["problems"]), [], []
    fields_read = sum(1 for key, _ in FIELDS if key in v)
    out = {"decision": "NEEDS_INFO", "tier": None, "score": None, "declared": None, "rows": [], "flags": flags,
           "problems": problems, "notes": notes, "fields_read": fields_read}
    if problems:
        return out
    cls = v["data_class"]
    if catalog is not None:
        ds = v.get("dataset")
        if not ds:
            flags.append({"code": "DATASET_NOT_GIVEN", "reason": "no dataset name; the data class could not be checked against the catalog"})
        elif ds.lower() not in catalog:
            flags.append({"code": "DATASET_NOT_IN_CATALOG", "reason": "dataset `%s` is not in the catalog; the data class is unverified" % safe_text(ds)})
        else:
            c_cls = catalog[ds.lower()]
            if CHOICES["data_class"].index(c_cls) > CHOICES["data_class"].index(cls):
                flags.append({"code": "DATA_CLASS_BELOW_CATALOG", "reason": "form says %s; the catalog records %s for `%s`; using %s" % (cls, c_cls, safe_text(ds), c_cls)})
                cls = c_cls
            elif CHOICES["data_class"].index(c_cls) < CHOICES["data_class"].index(cls):
                flags.append({"code": "DATA_CLASS_ABOVE_CATALOG", "reason": "form says %s; the catalog records %s for `%s`; kept %s, the steward should review the catalog entry" % (cls, c_cls, safe_text(ds), cls)})
    ven = v["vendor"]
    if registry is not None and issue_number is not None:
        r_ven = registry.get(issue_number)
        if r_ven is None:
            notes.append("the registry has no entry for issue %d" % issue_number)
        elif CHOICES["vendor"].index(r_ven) > CHOICES["vendor"].index(ven):
            flags.append({"code": "VENDOR_NOT_DECLARED", "reason": "form says %s; the vendor registry lists %s; using %s" % (ven, r_ven, r_ven)})
            ven = r_ven
    cf = v.get("customer_facing", "")
    if cf == "yes":
        pass
    elif cf == "no":
        m = CUE_RE.search(v.get("summary", ""))
        if m:
            flags.append({"code": "CUSTOMER_FACING_CUE", "reason": "form says internal; the summary mentions '%s'; the tier uses the form's answer, and the sponsor should confirm" % m.group(0).lower()})
    else:
        flags.append({"code": "CUSTOMER_FACING_AMBIGUOUS", "reason": "customer-facing answer is %s; treated as customer-facing until the sponsor confirms" % ("'unsure'" if cf == "unsure" else "blank")})
        cf = "yes"
    used = {"customer_facing": cf, "autonomy": v["autonomy"], "data_class": cls, "vendor": ven,
            "regulatory": v["regulatory"], "exposure": v["exposure"]}
    out["rows"] = [(LABEL_OF[k], used[k], POINTS[k][used[k]]) for k in RUBRIC_KEYS]
    out["score"] = sum(r[2] for r in out["rows"])
    out["tier"] = tier_from_score(out["score"])
    out["decision"] = "TIERED"
    if "declared" in v:
        out["declared"] = int(v["declared"])
        if out["declared"] < out["tier"]:
            flags.append({"code": "TIER_DECLARED_BELOW", "reason": "sponsor declared tier %d; the rubric on the checked inputs gives tier %d (%d points)" % (out["declared"], out["tier"], out["score"])})
        elif out["declared"] > out["tier"]:
            flags.append({"code": "TIER_DECLARED_ABOVE", "reason": "sponsor declared tier %d; the rubric on the checked inputs gives tier %d (%d points)" % (out["declared"], out["tier"], out["score"])})
    else:
        notes.append("the declared tier is blank or unreadable" if "declared" in form["present"] else "no declared tier on the form")
    return out


# ---------------------------------------------------------------- labels and comment
def wanted_labels(result: dict) -> list:
    if result["decision"] == "NEEDS_INFO":
        return ["needs-info"]
    labels = ["ai-tier:%d" % result["tier"]]
    if result["declared"] is not None and result["declared"] != result["tier"]:
        labels.append("tier-mismatch")
    return labels


def plan_labels(wanted: list, current: list):
    """(labels to add, labels to remove). Only labels this tool owns are ever removed."""
    add = sorted(set(wanted) - set(current))
    remove = sorted((set(current) & set(MANAGED)) - set(wanted))
    return add, remove


def evidence_for(tier: int) -> list:
    return [(i, t) for lvl, i, t in EVIDENCE if lvl <= tier]


def render_comment(result: dict) -> str:
    if result["decision"] == "NEEDS_INFO":
        lines = [MARKER, "**No tier yet: the form needs changes.**", ""]
        lines += ["- " + p for p in result["problems"]]
        lines += ["", "Edit the issue so each heading below appears once, in this order, with one of its allowed values. "
                  "This comment updates when you save.", ""]
        lines += ["- %s: %s" % (LABEL_OF[k], ", ".join(CHOICES[k])) for k in ("customer_facing", "autonomy", "data_class", "vendor", "regulatory", "exposure", "declared")]
        return "\n".join(lines) + "\n"
    t = result["tier"]
    head = "**Intake tier: %d** (%d points)." % (t, result["score"])
    if result["declared"] is not None:
        head += " The form declared tier %d." % result["declared"]
    lines = [MARKER, head, "", "| Input | Value used | Points |", "|---|---|---|"]
    lines += ["| %s | %s | %d |" % r for r in result["rows"]]
    if result["flags"]:
        lines += ["", "Checks for the reviewer to read:"]
        lines += ["- `%s`: %s" % (f["code"], f["reason"]) for f in result["flags"]]
    ev = evidence_for(t)
    lines += ["", "Evidence to attach before approval at tier %d (%d items): %s." % (t, len(ev), "; ".join("%s %s" % e for e in ev)),
              "", "The tier comes from a prototype rubric, and a reviewer confirms it. Edit the issue to correct an input; this comment updates when you save.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- loading
def _oneline(msg) -> str:
    return " ".join(str(msg).split())


def read_text(path: str) -> str:
    try:
        if path == "-":
            raw = sys.stdin.buffer.read()
        else:
            with open(path, "rb") as fh:
                raw = fh.read()
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("%s: not valid UTF-8 text" % ("standard input" if path == "-" else path))
    except OSError as e:
        raise InputError("cannot read %s: %s" % (path, e.strerror or e))
    if "\x00" in text:
        raise InputError("%s: contains NUL bytes, expected text" % ("standard input" if path == "-" else path))
    return text


def _csv_rows(path: str, columns: list) -> list:
    text = read_text(path)
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except csv.Error as e:
        raise InputError("%s: %s" % (path, e))
    if not reader.fieldnames or any(c not in reader.fieldnames for c in columns):
        raise InputError("%s: expected columns %s" % (path, ", ".join(columns)))
    if not rows:
        raise InputError("%s: no rows" % path)
    return rows


def load_catalog(path: str) -> dict:
    out = {}
    for n, r in enumerate(_csv_rows(path, ["dataset_name", "catalog_class"]), 2):
        name, cls = (r["dataset_name"] or "").strip().lower(), (r["catalog_class"] or "").strip().lower()
        if not name or cls not in CHOICES["data_class"]:
            raise InputError("%s: row %d needs a dataset_name and one of %s" % (path, n, ", ".join(CHOICES["data_class"])))
        if name in out:
            raise InputError("%s: row %d repeats dataset %s" % (path, n, safe_text(name)))
        out[name] = cls
    return out


def load_registry(path: str) -> dict:
    out = {}
    for n, r in enumerate(_csv_rows(path, ["issue_number", "vendor_model"]), 2):
        num, ven = (r["issue_number"] or "").strip(), (r["vendor_model"] or "").strip().lower()
        if not num.isdigit() or ven not in CHOICES["vendor"]:
            raise InputError("%s: row %d needs a whole-number issue_number and one of %s" % (path, n, ", ".join(CHOICES["vendor"])))
        if int(num) in out:
            raise InputError("%s: row %d repeats issue %s" % (path, n, num))
        out[int(num)] = ven
    return out


def load_labels(path: str) -> list:
    try:
        data = json.loads(read_text(path))
    except ValueError as e:
        raise InputError("%s: not JSON (%s)" % (path, e))
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise InputError("%s: expected a JSON list of label names" % path)
    return data


# ---------------------------------------------------------------- output
def render_text(result: dict, add: list, remove: list, issue_number=None) -> str:
    ref = "issue %d" % issue_number if issue_number is not None else "issue"
    lines = ["%s: %d of %d form fields read, %d problem%s" % (ref, result["fields_read"], len(FIELDS), len(result["problems"]),
                                                              "" if len(result["problems"]) == 1 else "s")]
    lines += ["  " + p for p in result["problems"]]
    if result["decision"] == "TIERED":
        d = "declared tier %d -> " % result["declared"] if result["declared"] is not None else ""
        lines.append("%srecomputed tier %d (%d points)" % (d, result["tier"], result["score"]))
        lines += ["  %-26s %s" % (f["code"], f["reason"]) for f in result["flags"]]
    lines += ["  note: " + n for n in result["notes"]]
    ch = ["add " + ", ".join(add)] if add else []
    ch += ["remove " + ", ".join(remove)] if remove else []
    lines.append("labels: " + ("; ".join(ch) if ch else "no change"))
    lines.append("decision: " + result["decision"])
    return "\n".join(lines)


def render_github(result: dict) -> str:
    lines = []
    for p in result["problems"]:
        lines.append("::warning title=intake-tier-action needs-info::" + escape_annotation(p))
    for f in result["flags"]:
        if f["code"] in ("TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE", "DATA_CLASS_BELOW_CATALOG", "VENDOR_NOT_DECLARED"):
            lines.append("::warning title=intake-tier-action %s::%s" % (f["code"], escape_annotation(f["reason"])))
    msg = "decision %s" % result["decision"] + ("; tier %d" % result["tier"] if result["tier"] else "")
    lines.append("::notice title=intake-tier-action::" + escape_annotation(msg))
    return "\n".join(lines)


def write_out(out_dir: str, add: list, remove: list, comment: str) -> None:
    try:
        os.makedirs(out_dir, exist_ok=True)
        for name, text in (("labels_add.txt", "".join(x + "\n" for x in add)), ("labels_remove.txt", "".join(x + "\n" for x in remove)),
                           ("comment.md", comment)):
            with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
    except OSError as e:
        raise InputError("cannot write to %s: %s" % (out_dir, e.strerror or e))


def run_check(body_path, catalog_path, registry_path, issue_number, labels_path, out_dir, fmt, fail_on) -> int:
    try:
        num = None
        if issue_number is not None:
            if not issue_number.isdigit() or int(issue_number) < 1:
                raise InputError("--issue-number must be a whole number of 1 or more")
            num = int(issue_number)
        if registry_path and num is None:
            raise InputError("--registry needs --issue-number")
        body = read_text(body_path)
        catalog = load_catalog(catalog_path) if catalog_path else None
        registry = load_registry(registry_path) if registry_path else None
        current = load_labels(labels_path) if labels_path else []
        result = assess(body, catalog, registry, num)
        wanted = wanted_labels(result)
        add, remove = plan_labels(wanted, current)
        comment = render_comment(result)
        if out_dir:
            write_out(out_dir, add, remove, comment)
    except InputError as e:
        print("input error: " + _oneline(e), file=sys.stderr)
        return 2
    if fmt == "json":
        print(json.dumps({"decision": result["decision"], "tier": result["tier"], "score": result["score"],
                          "declared": result["declared"], "flags": result["flags"], "problems": result["problems"],
                          "labels_add": add, "labels_remove": remove, "comment": comment}, indent=1, sort_keys=True))
    elif fmt == "github":
        print(render_github(result))
    else:
        print(render_text(result, add, remove, num))
    level = 2 if result["decision"] == "NEEDS_INFO" else 1 if "tier-mismatch" in wanted else 0
    return 1 if level >= FAIL_RANK[fail_on] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="intake_tier_action")
    ap.add_argument("--demo", action="store_true", help="run the bundled example issue (data/example_issue.md)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="recompute the tier of one issue body")
    c.add_argument("body", help="path to the issue body, or - for standard input")
    c.add_argument("--catalog")
    c.add_argument("--registry")
    c.add_argument("--issue-number")
    c.add_argument("--labels", help="JSON list of the labels the issue carries now")
    c.add_argument("--out-dir")
    c.add_argument("--format", choices=["text", "github", "json"], default="text")
    c.add_argument("--fail-on", choices=["needs-info", "mismatch", "never"], default="never")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_issue.md"), os.path.join(d, "catalog.csv"), os.path.join(d, "registry.csv"),
                         "301", os.path.join(d, "example_labels.json"), None, "text", "never")
    if a.cmd == "check":
        return run_check(a.body, a.catalog, a.registry, a.issue_number, a.labels, a.out_dir, a.format, a.fail_on)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
