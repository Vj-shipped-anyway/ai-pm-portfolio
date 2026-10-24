"""tiergate: recompute the risk tier a sponsor declared on an AI use-case intake form.

The rubric is the one in ../../11-tiergate-ai-usecase-intake/: points on six inputs, summed, and
tier = min(4, 1 + points // 4). The tier is recomputed on inputs that have a second source:
  data class       the higher of the form and the data catalog
  vendor model     the higher of the form and the vendor registry
  customer-facing  a blank or 'unsure' answer counts as yes until the sponsor confirms; a 'no' counts
                   as yes when the title or description names the people served

Usage
  python3 tiergate.py --demo
  python3 tiergate.py check intake.csv [--catalog catalog.csv] [--registry registry.csv]
                                       [--format text|github] [--out result.csv]

Exit status: 0 nothing is declared below its recomputed tier (and always 0 for --demo), 1 at least one
submission is declared below its recomputed tier, 2 the input could not be read or is malformed
(one line on stderr). Standard library only, Python 3.9 or newer.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(HERE, "..", "data")

CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
VENDOR_ORDER = ["none", "self_hosted", "vendor_api"]
PTS_CUSTOMER = {"yes": 2, "no": 0}
PTS_AUTONOMY = {"advisory": 0, "assisted": 1, "automated": 3}
PTS_CLASS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
PTS_VENDOR = {"none": 0, "self_hosted": 1, "vendor_api": 2}
PTS_REG = {"none": 0, "privacy": 1, "aml": 2, "udaap": 2, "fair_lending": 3}
PTS_EXPOSURE = {"lt_1m": 0, "1m_10m": 1, "10m_50m": 2, "gt_50m": 3}

INTAKE_COLUMNS = ["use_case_id", "title", "description", "dataset_name", "customer_facing", "decision_autonomy",
                  "data_class", "vendor_model", "regulatory_scope", "financial_exposure_band", "self_declared_tier"]
ALLOWED = {
    "customer_facing": ("yes", "no", "unsure", ""),
    "decision_autonomy": tuple(PTS_AUTONOMY),
    "data_class": tuple(CLASS_ORDER),
    "vendor_model": tuple(VENDOR_ORDER),
    "regulatory_scope": tuple(PTS_REG),
    "financial_exposure_band": tuple(PTS_EXPOSURE),
}

CUE_RE = re.compile(r"\b(customer|client|borrower|cardholder|applicant|consumer|caller|"
                    r"depositor|account holder)s?\b", re.IGNORECASE)


class InputError(Exception):
    """The input could not be read or is malformed. The message is one line."""


def clean(text, limit: int = 80) -> str:
    """One printable line: control characters become spaces and long text is cut."""
    one_line = re.sub(r"[\x00-\x1f\x7f-\x9f  ]+", " ", str(text)).strip()
    return one_line if len(one_line) <= limit else one_line[: limit - 3] + "..."


def gh_escape(text: str) -> str:
    """Escape text for a GitHub workflow command message."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def csv_safe(value) -> str:
    """Stop a spreadsheet from reading a cell as a formula."""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


# --------------------------------------------------------------------------------------------
# Rubric and recompute
# --------------------------------------------------------------------------------------------
def rubric_score(cf: str, aut: str, cls: str, ven: str, reg: str, exp: str) -> int:
    """Points on the six inputs. A blank or 'unsure' customer-facing answer scores 0."""
    return (PTS_CUSTOMER.get(cf, 0) + PTS_AUTONOMY[aut] + PTS_CLASS[cls]
            + PTS_VENDOR[ven] + PTS_REG[reg] + PTS_EXPOSURE[exp])


def tier_from_score(score: int) -> int:
    return min(4, 1 + score // 4)


def recompute(form: dict, catalog, registry, check_text: bool = True) -> dict:
    """Recompute the tier. catalog and registry are dicts, or None when no second source was given."""
    flags = []
    cls = form["data_class"]
    if catalog is not None:
        ds = form["dataset_name"]
        if ds not in catalog:
            flags.append({"code": "DATASET_NOT_IN_CATALOG",
                          "reason": "dataset %s is not in the catalog; class unverified" % ds})
        elif CLASS_ORDER.index(catalog[ds]) > CLASS_ORDER.index(cls):
            flags.append({"code": "DATA_CLASS_BELOW_CATALOG",
                          "reason": "form says %s; the catalog records %s for %s; using %s"
                                    % (cls, catalog[ds], ds, catalog[ds])})
            cls = catalog[ds]
        elif CLASS_ORDER.index(catalog[ds]) < CLASS_ORDER.index(cls):
            flags.append({"code": "DATA_CLASS_ABOVE_CATALOG",
                          "reason": "form says %s; the catalog records %s for %s; kept the higher class, "
                                    "the steward should review the catalog entry" % (cls, catalog[ds], ds)})

    ven = form["vendor_model"]
    listed = registry.get(form["use_case_id"]) if registry is not None else None
    if listed is not None and VENDOR_ORDER.index(listed) > VENDOR_ORDER.index(ven):
        flags.append({"code": "VENDOR_NOT_DECLARED",
                      "reason": "form says %s; the vendor registry lists %s; using %s" % (ven, listed, listed)})
        ven = listed

    cf = form["customer_facing"]
    if check_text:
        if cf == "no":
            cue = CUE_RE.search(form["title"] + " " + form["description"])
            if cue:
                flags.append({"code": "CUSTOMER_FACING_CUE",
                              "reason": "form says internal; the text mentions '%s'; treated as customer-facing "
                                        "until the sponsor confirms" % cue.group(0).lower()})
                cf = "yes"
        elif cf != "yes":
            flags.append({"code": "CUSTOMER_FACING_AMBIGUOUS",
                          "reason": "customer-facing answer is %s; treated as customer-facing until the sponsor "
                                    "confirms" % ("blank" if cf == "" else "'unsure'")})
            cf = "yes"

    score = rubric_score(cf, form["decision_autonomy"], cls, ven, form["regulatory_scope"],
                         form["financial_exposure_band"])
    tier = tier_from_score(score)
    declared = form["self_declared_tier"]
    if tier > declared:
        flags.append({"code": "TIER_DECLARED_BELOW",
                      "reason": "sponsor declared tier %d; the rubric on the checked inputs gives tier %d (%d points)"
                                % (declared, tier, score)})
    elif tier < declared:
        flags.append({"code": "TIER_DECLARED_ABOVE",
                      "reason": "sponsor declared tier %d; the rubric on the checked inputs gives tier %d (%d points)"
                                % (declared, tier, score)})
    return {"tier": tier, "score": score, "customer_facing": cf, "data_class": cls, "vendor_model": ven,
            "flags": flags}


def status_of(declared: int, tier: int) -> str:
    return "UNDER-DECLARED" if tier > declared else "OVER-DECLARED" if tier < declared else "MATCH"


# --------------------------------------------------------------------------------------------
# Reading and validating input
# --------------------------------------------------------------------------------------------
def read_table(path: str, label: str, required: list) -> list:
    shown = clean(path)
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
    except UnicodeDecodeError:
        raise InputError("%s file %s is not UTF-8 text" % (label, shown))
    except csv.Error as exc:
        raise InputError("%s file %s is not valid CSV: %s" % (label, shown, clean(exc)))
    except OSError as exc:
        raise InputError("cannot read %s file %s: %s" % (label, shown, clean(exc.strerror or type(exc).__name__)))
    if not rows:
        raise InputError("%s file %s is empty" % (label, shown))
    header = [h.strip() for h in rows[0]]
    missing = [c for c in required if c not in header]
    if missing:
        raise InputError("%s file %s is missing columns: %s" % (label, shown, ", ".join(missing)))
    if len(set(header)) != len(header):
        raise InputError("%s file %s repeats a column name" % (label, shown))
    out = []
    for n, row in enumerate(rows[1:], start=1):
        if not row:
            continue
        if len(row) != len(header):
            raise InputError("%s file %s: row %d has %d fields, the header has %d (truncated or mis-quoted?)"
                             % (label, shown, n, len(row), len(header)))
        out.append((n, dict(zip(header, [cell.strip() for cell in row]))))
    if not out:
        raise InputError("%s file %s has a header and no rows" % (label, shown))
    return out


def check_choice(label: str, n: int, ident: str, column: str, value: str, allowed: tuple) -> None:
    if value not in allowed:
        raise InputError("%s row %d (%s): %s '%s' is not one of %s"
                         % (label, n, clean(ident, 40), column, clean(value, 40), ", ".join(a or "(blank)" for a in allowed)))


def read_intake(path: str) -> list:
    rows = read_table(path, "intake", INTAKE_COLUMNS)
    forms, seen = [], set()
    for n, raw in rows:
        uid = raw["use_case_id"]
        if not uid:
            raise InputError("intake row %d: use_case_id is blank" % n)
        if uid in seen:
            raise InputError("intake row %d: use_case_id '%s' appears twice" % (n, clean(uid, 40)))
        seen.add(uid)
        for column, allowed in ALLOWED.items():
            check_choice("intake", n, uid, column, raw[column], allowed)
        if raw["self_declared_tier"] not in ("1", "2", "3", "4"):
            raise InputError("intake row %d (%s): self_declared_tier '%s' is not one of 1, 2, 3, 4"
                             % (n, clean(uid, 40), clean(raw["self_declared_tier"], 40)))
        form = {c: raw[c] for c in INTAKE_COLUMNS}
        form["self_declared_tier"] = int(raw["self_declared_tier"])
        forms.append(form)
    return forms


def read_mapping(path: str, label: str, key: str, value: str, allowed: tuple) -> dict:
    out = {}
    for n, raw in read_table(path, label, [key, value]):
        if not raw[key]:
            raise InputError("%s row %d: %s is blank" % (label, n, key))
        if raw[key] in out:
            raise InputError("%s row %d: %s '%s' appears twice" % (label, n, key, clean(raw[key], 40)))
        check_choice(label, n, raw[key], value, raw[value], allowed)
        out[raw[key]] = raw[value]
    return out


def read_catalog(path: str) -> dict:
    return read_mapping(path, "catalog", "dataset_name", "catalog_class", tuple(CLASS_ORDER))


def read_registry(path: str) -> dict:
    return read_mapping(path, "registry", "use_case_id", "vendor_model", tuple(VENDOR_ORDER))


# --------------------------------------------------------------------------------------------
# Running and printing
# --------------------------------------------------------------------------------------------
def run_check(forms: list, catalog, registry) -> list:
    results = []
    for form in forms:
        r = recompute(form, catalog, registry)
        r.update({"use_case_id": form["use_case_id"], "title": form["title"], "declared": form["self_declared_tier"],
                  "status": status_of(form["self_declared_tier"], r["tier"])})
        results.append(r)
    return results


def notes_for(forms: list, catalog, registry) -> list:
    notes = []
    if catalog is None:
        notes.append("note: no catalog given; data class was not cross-checked")
    elif not any(f["dataset_name"] in catalog for f in forms):
        notes.append("note: no dataset in the intake file is in the catalog; data class was not cross-checked")
    if registry is None:
        notes.append("note: no registry given; vendor model was not cross-checked")
    elif not any(f["use_case_id"] in registry for f in forms):
        notes.append("note: no use case in the intake file is in the registry; vendor model was not cross-checked")
    return notes


def summary_line(results: list) -> str:
    under = sum(1 for r in results if r["status"] == "UNDER-DECLARED")
    over = sum(1 for r in results if r["status"] == "OVER-DECLARED")
    return "checked %d submissions: %d under-declared, %d over-declared, %d unchanged" % (
        len(results), under, over, len(results) - under - over)


def headline(r: dict) -> str:
    # The status comes first so that no line of text output can begin with text taken from the input.
    return "%s  %s  %s  declared tier %d, recomputed tier %d (%d points)" % (
        r["status"], clean(r["use_case_id"], 40), clean(r["title"], 60), r["declared"], r["tier"], r["score"])


def render_text(results: list) -> list:
    lines = []
    for r in results:
        if r["status"] == "MATCH" and not r["flags"]:
            continue
        lines.append(headline(r))
        for f in r["flags"]:
            if f["code"] not in ("TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE"):
                lines.append("  %s  %s" % (f["code"], clean(f["reason"], 200)))
    lines.append(summary_line(results))
    return lines


def render_github(results: list) -> list:
    lines = []
    for r in results:
        if r["status"] == "MATCH" and not r["flags"]:
            continue
        level = "error" if r["status"] == "UNDER-DECLARED" else "notice"
        reasons = "; ".join("%s: %s" % (f["code"], f["reason"]) for f in r["flags"]
                            if f["code"] not in ("TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE"))
        message = headline(r) + (" | " + reasons if reasons else "")
        lines.append("::%s title=tiergate::%s" % (level, gh_escape(message)))
    lines.append(summary_line(results))
    return lines


def write_results(path: str, results: list) -> None:
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["use_case_id", "declared_tier", "recomputed_tier", "score", "status", "flag_codes"])
            for r in results:
                w.writerow([csv_safe(r["use_case_id"]), r["declared"], r["tier"], r["score"], r["status"],
                            "|".join(f["code"] for f in r["flags"])])
    except OSError as exc:
        raise InputError("cannot write %s: %s" % (clean(path), clean(exc.strerror or type(exc).__name__)))


def check_command(intake: str, catalog_path, registry_path, fmt: str, out_path) -> int:
    forms = read_intake(intake)
    catalog = read_catalog(catalog_path) if catalog_path else None
    registry = read_registry(registry_path) if registry_path else None
    results = run_check(forms, catalog, registry)
    for line in notes_for(forms, catalog, registry):
        print(line)
    for line in (render_github(results) if fmt == "github" else render_text(results)):
        print(line)
    if out_path:
        write_results(out_path, results)
    return 1 if any(r["status"] == "UNDER-DECLARED" for r in results) else 0


class OneLineParser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError("usage error: " + clean(message, 160))


def build_parser() -> argparse.ArgumentParser:
    p = OneLineParser(prog="tiergate", description="Recompute the risk tier declared on an AI use-case intake form.")
    p.add_argument("--demo", action="store_true", help="run on the bundled sample forms")
    sub = p.add_subparsers(dest="command")
    c = sub.add_parser("check", help="check an intake CSV")
    c.add_argument("intake", help="intake CSV, one row per use case")
    c.add_argument("--catalog", help="CSV with dataset_name and catalog_class")
    c.add_argument("--registry", help="CSV with use_case_id and vendor_model")
    c.add_argument("--format", choices=("text", "github"), default="text")
    c.add_argument("--out", help="write one row per submission to this CSV")
    return p


def main(argv=None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.demo:
            forms = read_intake(os.path.join(DEMO_DIR, "example_intake.csv"))
            catalog = read_catalog(os.path.join(DEMO_DIR, "example_catalog.csv"))
            registry = read_registry(os.path.join(DEMO_DIR, "example_registry.csv"))
            for line in render_text(run_check(forms, catalog, registry)):
                print(line)
            return 0
        if args.command == "check":
            return check_command(args.intake, args.catalog, args.registry, args.format, args.out)
        raise InputError("usage error: give --demo or the check command")
    except InputError as exc:
        print("tiergate: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
