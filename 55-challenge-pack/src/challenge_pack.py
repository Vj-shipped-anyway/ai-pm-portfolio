"""challenge_pack: build a second-line challenge pack for AI use cases from the risk tier.

For each use case it chooses the tests the tier calls for, adds overlays for vendor products and for
use cases outside the guidance's model definition, reconciles the evidence the first line has on file
(missing, stale, wrong version, prepared inside the developer's own unit), and writes a challenge memo.
There is no model in this file. The tier table is an assumption of this prototype, not a reading of any
rule; the SR 26-2 areas named in it come from the public text (see the README).

Usage (from src/)
  python3 challenge_pack.py --demo
  python3 challenge_pack.py table
  python3 challenge_pack.py pack USE_CASES.csv EVIDENCE.csv --as-of YYYY-MM-DD [--id ID] [--out-dir DIR]
                                                            [--format text|github] [--all]

Exit status: 0 no use case has a gap, 1 at least one has a gap (a finding, not a failure), 2 the input
could not be read or is malformed (one line on stderr). Standard library only, Python 3.9 or newer.

The tier recompute uses the rubric of project 11: points on six inputs, tier = min(4, 1 + points // 4).
The tier used for a pack is the higher of the declared tier and the recomputed one.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import datetime as dt
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(HERE, "..", "data")
DEMO_AS_OF = "2026-10-01"

PTS_CUSTOMER = {"yes": 2, "no": 0}
PTS_AUTONOMY = {"advisory": 0, "assisted": 1, "automated": 3}
CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
PTS_CLASS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
VENDOR_ORDER = ["none", "self_hosted", "vendor_api"]
PTS_VENDOR = {"none": 0, "self_hosted": 1, "vendor_api": 2}
PTS_REG = {"none": 0, "privacy": 1, "aml": 2, "udaap": 2, "fair_lending": 3}
PTS_EXPOSURE = {"lt_1m": 0, "1m_10m": 1, "10m_50m": 2, "gt_50m": 3}
MODEL_TYPES = ("statistical", "ml", "rules", "generative", "agentic")
OUT_OF_SCOPE = ("rules", "generative", "agentic")

USE_CASE_COLUMNS = ["use_case_id", "title", "model_type", "vendor_model", "customer_facing", "decision_autonomy",
                    "data_class", "regulatory_scope", "financial_exposure_band", "developer_unit",
                    "deployed_version", "declared_tier"]
EVIDENCE_COLUMNS = ["use_case_id", "item_id", "ref", "prepared_by_unit", "covers_version", "evidence_date",
                    "reaffirmed_date"]
ALLOWED = {
    "model_type": MODEL_TYPES,
    "vendor_model": tuple(VENDOR_ORDER),
    "customer_facing": ("yes", "no"),
    "decision_autonomy": tuple(PTS_AUTONOMY),
    "data_class": tuple(CLASS_ORDER),
    "regulatory_scope": tuple(PTS_REG),
    "financial_exposure_band": tuple(PTS_EXPOSURE),
}
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,39}")


def _item(item_id, title, test, area, min_tier, independent, overlay=""):
    return {"id": item_id, "title": title, "test": test, "area": area, "min_tier": min_tier,
            "independent": independent, "overlay": overlay}


# The tier-to-test-plan table. Which item sits at which tier, which items need a preparer outside the
# developer's unit, and the evidence windows below are assumptions of this prototype.
ITEMS = [
    _item("CH01", "Inventory record and named owner",
          "Confirm the inventory lists the use case with a named first-line owner and a stated intended use.",
          "Model inventory", 1, False),
    _item("CH02", "Statement of purpose",
          "Read the purpose statement. It should name the decision the output supports and what the use case is not for.",
          "Development: purpose", 1, False),
    _item("CH03", "Limitations and monitoring conditions",
          "Confirm the known limitations are written down, with the conditions under which the use would become material.",
          "Use and limitations", 1, False),
    _item("CH04", "Developmental testing summary",
          "Read the tests the developer ran and check that they fit the stated purpose.",
          "Development: testing", 2, False),
    _item("CH05", "Input data quality and relevance",
          "Review how the input data was chosen and checked for quality and relevance.",
          "Development: testing", 2, False),
    _item("CH06", "Documentation a third party could follow",
          "Check that someone outside the team could follow the design, the data and the assumptions.",
          "Documentation", 2, False),
    _item("CH07", "Conceptual soundness review",
          "Challenge the design, the key choices, the assumptions and the data selection, and the evidence offered for them.",
          "Validation: conceptual soundness", 3, True),
    _item("CH08", "Outcomes analysis",
          "Compare outputs with real outcomes or a benchmark against the performance thresholds set for the use case.",
          "Validation: outcomes analysis", 3, True),
    _item("CH09", "Ongoing monitoring plan",
          "Check that the plan names metrics, thresholds, a frequency and the response when a threshold is crossed.",
          "Ongoing monitoring", 3, False),
    _item("CH10", "Use-within-purpose check",
          "Confirm current use matches the purpose that was validated; if use has grown, check what analysis was added.",
          "Model use", 3, True),
    _item("CH11", "Challenger or benchmark comparison",
          "Compare against an alternative method or a benchmark and explain the differences.",
          "Validation: benchmarking", 4, True),
    _item("CH12", "Aggregate risk review",
          "List the other use cases that share the same data, assumptions or method and note the combined exposure.",
          "Overview: aggregate risk", 4, True),
    _item("CH13", "Senior sign-off and conflicts check",
          "Confirm a named senior risk owner signed off and that no reviewer reports into the developer's line.",
          "Governance: roles and conflicts", 4, True),
    _item("V01", "Vendor product understanding",
          "Check the file records the vendor model's design, development data and performance evidence, and what the bank customised.",
          "Vendor and third-party products", 1, False, "vendor"),
    _item("V02", "Vendor ongoing monitoring and outcomes",
          "Check the bank runs its own outcomes analysis on the vendor model and does not rely on the vendor's word.",
          "Vendor and third-party products", 2, True, "vendor"),
    _item("G01", "Scope determination",
          "Record why the guidance's model definition does not cover this use case and which bank-defined controls apply instead.",
          "Scope: model definition and footnote 3", 1, True, "scope"),
]
ITEM_BY_ID = {it["id"]: it for it in ITEMS}
TIERS = {
    1: {"depth": "Inventory and monitor", "window_months": 36},
    2: {"depth": "Desk review", "window_months": 24},
    3: {"depth": "Independent validation", "window_months": 12},
    4: {"depth": "Independent validation, benchmark and senior sign-off", "window_months": 12},
}
PROBLEM_ORDER = ["missing", "wrong_version", "not_independent", "stale"]


class InputError(Exception):
    """The input could not be read or is malformed. The message is one line."""


def clean(text, limit: int = 80) -> str:
    """One printable line: control characters become spaces and long text is cut."""
    one_line = re.sub(r"[\x00-\x1f\x7f-\x9f  ]+", " ", str(text)).strip()
    return one_line if len(one_line) <= limit else one_line[: limit - 3] + "..."


def gh_escape(text) -> str:
    """Escape text for a GitHub workflow command message."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def csv_safe(value) -> str:
    """Stop a spreadsheet from reading a cell as a formula."""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def md_cell(text, limit: int = 200) -> str:
    """Text from the input made safe for one Markdown table cell or heading."""
    s = clean(text, limit)
    for ch in ("\\", "|", "`", "[", "]", "*", "_"):
        s = s.replace(ch, "\\" + ch)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------------------------
# Dates, tier and plan
# --------------------------------------------------------------------------------------------
def add_months(d: dt.date, n: int) -> dt.date:
    """Move a date by whole months; a day that does not exist in the target month becomes its last day."""
    y, m0 = divmod(d.year * 12 + (d.month - 1) + n, 12)
    m = m0 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def parse_date(text: str, label: str) -> dt.date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text or ""):
        raise InputError("%s '%s' must be a date written YYYY-MM-DD" % (label, clean(text, 30)))
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise InputError("%s '%s' is not a real date" % (label, clean(text, 30)))


def rubric_points(form: dict) -> int:
    return (PTS_CUSTOMER[form["customer_facing"]] + PTS_AUTONOMY[form["decision_autonomy"]]
            + PTS_CLASS[form["data_class"]] + PTS_VENDOR[form["vendor_model"]]
            + PTS_REG[form["regulatory_scope"]] + PTS_EXPOSURE[form["financial_exposure_band"]])


def effective_tier(form: dict) -> tuple:
    """(tier used, tier recomputed from the form as written, points). The higher of declared and recomputed."""
    pts = rubric_points(form)
    recomputed = min(4, 1 + pts // 4)
    return max(form["declared_tier"], recomputed), recomputed, pts


def plan_items(model_type: str, vendor_model: str, tier: int) -> list:
    out = []
    for it in ITEMS:
        if it["min_tier"] > tier:
            continue
        if it["overlay"] == "vendor" and vendor_model == "none":
            continue
        if it["overlay"] == "scope" and model_type not in OUT_OF_SCOPE:
            continue
        out.append(it)
    return out


def same_unit(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def assess(form: dict, rows: dict, as_of: dt.date) -> dict:
    """The pack for one use case. rows maps item id to that use case's evidence row."""
    tier, recomputed, pts = effective_tier(form)
    window = TIERS[tier]["window_months"]
    cutoff = add_months(as_of, -window)
    plan = plan_items(form["model_type"], form["vendor_model"], tier)
    items = []
    for it in plan:
        row = rows.get(it["id"])
        problems, details = [], {}
        if row is None:
            problems.append("missing")
            details["missing"] = "no evidence row for this item"
        else:
            if row["covers_version"] != form["deployed_version"]:
                problems.append("wrong_version")
                details["wrong_version"] = "covers %s, deployed %s" % (
                    clean(row["covers_version"], 20), clean(form["deployed_version"], 20))
            if it["independent"] and same_unit(row["prepared_by_unit"], form["developer_unit"]):
                problems.append("not_independent")
                details["not_independent"] = "prepared by %s, the developer's unit" % clean(row["prepared_by_unit"], 40)
            latest = row["reaffirmed_date"] or row["evidence_date"]
            if latest < cutoff:
                problems.append("stale")
                details["stale"] = "latest %s, window %d months, as of %s" % (latest.isoformat(), window, as_of.isoformat())
        items.append({"item": it, "problems": problems, "details": details, "row": row})
    overlays = []
    if any(i["item"]["overlay"] == "vendor" for i in items):
        overlays.append("vendor")
    if any(i["item"]["overlay"] == "scope" for i in items):
        overlays.append("scope note")
    planned = {it["id"] for it in plan}
    return {"form": form, "tier": tier, "declared": form["declared_tier"], "recomputed": recomputed, "points": pts,
            "raised": tier > form["declared_tier"], "window": window, "items": items, "overlays": overlays,
            "scope": "in" if form["model_type"] in ("statistical", "ml") else "by analogy",
            "on_file_not_requested": sorted(k for k in rows if k not in planned and k in ITEM_BY_ID),
            "gaps": [i for i in items if i["problems"]]}


# --------------------------------------------------------------------------------------------
# Reading and validating input
# --------------------------------------------------------------------------------------------
def read_table(path: str, label: str, required: list) -> list:
    shown = clean(path)
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        raise InputError("%s file %s is not UTF-8 text" % (label, shown))
    except OSError as exc:
        raise InputError("cannot read %s file %s: %s" % (label, shown, clean(exc.strerror or type(exc).__name__)))
    if not text.strip():
        raise InputError("%s file %s is empty" % (label, shown))
    if "\x00" in text:
        raise InputError("%s file %s is not a CSV text file (it contains NUL bytes)" % (label, shown))
    try:
        rows = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as exc:
        raise InputError("%s file %s is not valid CSV: %s" % (label, shown, clean(exc)))
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
    return out


def need(label: str, n: int, ident: str, column: str, value: str) -> None:
    if not value:
        raise InputError("%s row %d (%s): %s is blank" % (label, n, clean(ident, 40), column))


def read_use_cases(path: str) -> list:
    rows = read_table(path, "use-case", USE_CASE_COLUMNS)
    if not rows:
        raise InputError("use-case file %s has a header and no rows" % clean(path))
    forms, seen = [], set()
    for n, raw in rows:
        uid = raw["use_case_id"]
        if not ID_RE.fullmatch(uid):
            raise InputError("use-case row %d: use_case_id '%s' must be 1 to 40 letters, digits, dot, dash or underscore, "
                             "starting with a letter or digit" % (n, clean(uid, 40)))
        if uid in seen:
            raise InputError("use-case row %d: use_case_id '%s' appears twice" % (n, uid))
        seen.add(uid)
        for column in ("title", "developer_unit", "deployed_version"):
            need("use-case", n, uid, column, raw[column])
        for column, allowed in ALLOWED.items():
            if raw[column] not in allowed:
                raise InputError("use-case row %d (%s): %s '%s' is not one of %s"
                                 % (n, uid, column, clean(raw[column], 40), ", ".join(allowed)))
        if raw["declared_tier"] not in ("1", "2", "3", "4"):
            raise InputError("use-case row %d (%s): declared_tier '%s' is not one of 1, 2, 3, 4"
                             % (n, uid, clean(raw["declared_tier"], 40)))
        form = {c: raw[c] for c in USE_CASE_COLUMNS}
        form["declared_tier"] = int(raw["declared_tier"])
        forms.append(form)
    return forms


def read_evidence(path: str, as_of: dt.date) -> list:
    """Evidence rows with dates parsed. A header with no rows is allowed: every plan item is then missing."""
    out, seen = [], set()
    for n, raw in read_table(path, "evidence", EVIDENCE_COLUMNS):
        key = (raw["use_case_id"], raw["item_id"])
        for column in ("use_case_id", "item_id", "ref", "prepared_by_unit", "covers_version"):
            need("evidence", n, raw["use_case_id"] or "?", column, raw[column])
        if key in seen:
            raise InputError("evidence row %d: item %s of use case %s appears twice"
                             % (n, clean(key[1], 20), clean(key[0], 40)))
        seen.add(key)
        row = dict(raw)
        row["evidence_date"] = parse_date(raw["evidence_date"], "evidence row %d evidence_date" % n)
        row["reaffirmed_date"] = (parse_date(raw["reaffirmed_date"], "evidence row %d reaffirmed_date" % n)
                                  if raw["reaffirmed_date"] else None)
        if row["evidence_date"] > as_of or (row["reaffirmed_date"] and row["reaffirmed_date"] > as_of):
            raise InputError("evidence row %d (%s %s): a date is after --as-of %s"
                             % (n, clean(key[0], 40), clean(key[1], 20), as_of.isoformat()))
        if row["reaffirmed_date"] and row["reaffirmed_date"] < row["evidence_date"]:
            raise InputError("evidence row %d (%s %s): reaffirmed_date is before evidence_date"
                             % (n, clean(key[0], 40), clean(key[1], 20)))
        out.append(row)
    return out


def group_evidence(rows: list) -> dict:
    by_uc = {}
    for r in rows:
        by_uc.setdefault(r["use_case_id"], {})[r["item_id"]] = r
    return by_uc


# --------------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------------
def tier_note(r: dict) -> str:
    if r["raised"]:
        return "tier %d (declared %d, raised by the rubric)" % (r["tier"], r["declared"])
    return "tier %d" % r["tier"]


def headline(r: dict) -> str:
    f = r["form"]
    # The use case id comes first so that no line of text output starts with text taken from a title.
    s = "%s  %s  %s  scope: %s (%s)" % (clean(f["use_case_id"], 40), clean(f["title"], 60), tier_note(r),
                                        r["scope"], f["model_type"])
    return s + ("  overlays: " + ", ".join(r["overlays"]) if r["overlays"] else "")


def problem_text(g: dict) -> str:
    return "; ".join("%s (%s)" % (p.replace("_", " "), g["details"][p]) for p in PROBLEM_ORDER if p in g["problems"])


def gap_line(g: dict) -> str:
    it = g["item"]
    return "  GAP  %s %s: %s" % (it["id"], it["title"], problem_text(g))


def summary_line(results: list) -> str:
    planned = sum(len(r["items"]) for r in results)
    bad = sum(len(r["gaps"]) for r in results)
    return "checked %d use cases: %d with gaps, %d complete; %d plan items, %d on file and current" % (
        len(results), sum(1 for r in results if r["gaps"]), sum(1 for r in results if not r["gaps"]), planned,
        planned - bad)


def render_text(results: list, show_all: bool) -> list:
    lines = []
    for r in results:
        if not r["gaps"] and not show_all:
            continue
        lines.append(headline(r))
        if not r["gaps"]:
            lines.append("  complete: %d plan items on file and current" % len(r["items"]))
        lines.extend(gap_line(g) for g in r["gaps"])
    lines.append(summary_line(results))
    return lines


def render_github(results: list) -> list:
    lines = []
    for r in results:
        for g in r["gaps"]:
            lines.append("::error title=challenge-pack::" + gh_escape(
                "%s %s" % (clean(r["form"]["use_case_id"], 40), gap_line(g).strip()[5:])))
        if r["raised"]:
            lines.append("::notice title=challenge-pack::" + gh_escape(
                "%s %s" % (clean(r["form"]["use_case_id"], 40), tier_note(r))))
    lines.append(summary_line(results))
    return lines


def table_lines() -> list:
    lines = ["| Tier | Depth | Items | Evidence window |", "|---|---|---|---|"]
    for t in sorted(TIERS):
        n = len([i for i in ITEMS if i["overlay"] == "" and i["min_tier"] <= t])
        lines.append("| %d | %s | %d | %d months |" % (t, TIERS[t]["depth"], n, TIERS[t]["window_months"]))
    lines += ["", "| Item | From tier | Preparer outside the developer's unit | Applies when | Area |", "|---|---|---|---|---|"]
    when = {"": "always", "vendor": "vendor_model is not none", "scope": "model_type is rules, generative or agentic"}
    for it in ITEMS:
        lines.append("| %s %s | %d | %s | %s | %s |" % (it["id"], it["title"], it["min_tier"],
                                                      "yes" if it["independent"] else "no", when[it["overlay"]], it["area"]))
    return lines


def render_memo(r: dict, as_of: dt.date) -> str:
    f = r["form"]
    scope_line = ("In scope of the guidance as a model." if r["scope"] == "in" else
                  "Outside the guidance's model definition or scope (%s). The tests below are applied by analogy under the "
                  "bank's own governance, and item G01 records that decision." % f["model_type"])
    out = [
        "# Challenge memo: %s %s" % (md_cell(f["use_case_id"], 40), md_cell(f["title"], 80)),
        "",
        "Draft for the challenger to complete. Prepared as of %s from the intake record and the evidence file. "
        "Nothing in it is a conclusion about the use case." % as_of.isoformat(),
        "",
        "## 1. Use case",
        "",
        "| Field | Value |",
        "|---|---|",
        "| Model type | %s |" % md_cell(f["model_type"], 40),
        "| Scope | %s |" % scope_line,
        "| Declared tier | %d |" % r["declared"],
        "| Tier used for this pack | %s |" % (
            "%d (raised from %d: the rubric gives %d points on the form as written)" % (r["tier"], r["declared"], r["points"])
            if r["raised"] else str(r["tier"])),
        "| Depth | %s |" % TIERS[r["tier"]]["depth"],
        "| Evidence window | %d months |" % r["window"],
        "| Vendor model | %s |" % md_cell(f["vendor_model"], 40),
        "| Developer unit | %s |" % md_cell(f["developer_unit"], 60),
        "| Deployed version | %s |" % md_cell(f["deployed_version"], 30),
        "",
        "## 2. Why this depth",
        "",
        "Rigour is set in proportion to how much the use case matters. The tier-to-depth table is an assumption of this "
        "prototype, not text from any rule. Independence applies to the items marked yes below: the preparer must sit "
        "outside the developer's unit.",
        "",
        "## 3. Test plan and evidence checklist",
        "",
        "| Item | What the challenger does | Independent preparer | Status | Detail |",
        "|---|---|---|---|---|",
    ]
    for g in r["items"]:
        it = g["item"]
        status = "gap" if g["problems"] else "on file and current"
        detail = problem_text(g)
        if not g["problems"]:
            row = g["row"]
            detail = "%s, %s, %s" % (row["ref"], row["prepared_by_unit"], (row["reaffirmed_date"] or row["evidence_date"]).isoformat())
        out.append("| %s %s | %s | %s | %s | %s |" % (it["id"], md_cell(it["title"]), md_cell(it["test"], 240),
                                                      "yes" if it["independent"] else "no", status, md_cell(detail, 240)))
    if r["on_file_not_requested"]:
        out += ["", "On file but not requested at this tier: %s." % ", ".join(r["on_file_not_requested"])]
    out += [
        "",
        "## 4. Findings",
        "",
        "| # | Item | Finding | Severity | Owner | Due |",
        "|---|---|---|---|---|---|",
        "|   |      |         |          |       |     |",
        "",
        "## 5. Limits of this pack",
        "",
        "- It checks that evidence exists, is current, covers the deployed version and, where required, was prepared outside "
        "the developer's unit. It does not read the evidence. A document can pass every check and say very little.",
        "- The tier comes from the intake form. If the form understates vendor use, data class or autonomy, the plan is too light.",
        "",
        "## 6. Sign-off",
        "",
        "Challenger: ______________  Unit: ______________  Date: ______________",
        "",
    ]
    return "\n".join(out)


def write_outputs(out_dir: str, results: list, as_of: dt.date) -> None:
    try:
        os.makedirs(out_dir, exist_ok=True)
        for r in results:
            with open(os.path.join(out_dir, r["form"]["use_case_id"] + ".md"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render_memo(r, as_of))
        with open(os.path.join(out_dir, "summary.csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["use_case_id", "title", "tier", "declared_tier", "scope", "plan_items", "gaps", "gap_items"])
            for r in results:
                w.writerow([r["form"]["use_case_id"], csv_safe(r["form"]["title"]), r["tier"], r["declared"], r["scope"],
                            len(r["items"]), len(r["gaps"]), ";".join(g["item"]["id"] for g in r["gaps"])])
    except OSError as exc:
        raise InputError("cannot write to %s: %s" % (clean(out_dir), clean(exc.strerror or type(exc).__name__)))


def notes_for(forms: list, evidence: list) -> list:
    notes = []
    known = {f["use_case_id"] for f in forms}
    if not evidence:
        notes.append("note: the evidence file has no rows, so every plan item is reported missing")
        return notes
    stray = [r for r in evidence if r["use_case_id"] not in known]
    if stray:
        notes.append("note: %d evidence rows name a use case that is not in the use-case file and were ignored (first: %s)"
                     % (len(stray), clean(stray[0]["use_case_id"], 40)))
    if len(stray) == len(evidence):
        notes.append("note: no evidence row matches any use case in the use-case file; check that the two files belong together")
    unknown = [r for r in evidence if r["use_case_id"] in known and r["item_id"] not in ITEM_BY_ID]
    if unknown:
        notes.append("note: %d evidence rows name an item that is not in the plan and were ignored (first: %s)"
                     % (len(unknown), clean(unknown[0]["item_id"], 20)))
    return notes


def run_pack(use_path: str, evidence_path: str, as_of_text: str, only_id, out_dir, fmt: str, show_all: bool) -> int:
    as_of = parse_date(as_of_text, "--as-of")
    forms = read_use_cases(use_path)
    evidence = read_evidence(evidence_path, as_of)
    if only_id:
        forms_sel = [f for f in forms if f["use_case_id"] == only_id]
        if not forms_sel:
            raise InputError("--id '%s' is not in the use-case file" % clean(only_id, 40))
    else:
        forms_sel = forms
    by_uc = group_evidence(evidence)
    results = [assess(f, by_uc.get(f["use_case_id"], {}), as_of) for f in forms_sel]
    if out_dir:
        write_outputs(out_dir, results, as_of)
    for line in notes_for(forms, evidence):
        print(line)
    for line in (render_github(results) if fmt == "github" else render_text(results, show_all)):
        print(line)
    return 1 if any(r["gaps"] for r in results) else 0


class OneLineParser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError("usage error: " + clean(message, 160))


def build_parser() -> argparse.ArgumentParser:
    p = OneLineParser(prog="challenge_pack", description="Build a second-line challenge pack from the risk tier.")
    p.add_argument("--demo", action="store_true", help="run on the bundled sample use cases")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("table", help="print the tier-to-test-plan table")
    c = sub.add_parser("pack", help="reconcile evidence against the plan and write challenge memos")
    c.add_argument("use_cases")
    c.add_argument("evidence")
    c.add_argument("--as-of", required=True, help="date the evidence is judged on, YYYY-MM-DD")
    c.add_argument("--id", help="only this use case")
    c.add_argument("--out-dir", help="write one memo per use case, and summary.csv, into this folder")
    c.add_argument("--format", choices=["text", "github"], default="text")
    c.add_argument("--all", action="store_true", help="also print use cases that have no gap")
    return p


def main(argv=None) -> int:
    try:
        a = build_parser().parse_args(argv)
        if a.demo:
            run_pack(os.path.join(DEMO_DIR, "example_use_cases.csv"), os.path.join(DEMO_DIR, "example_evidence.csv"),
                     DEMO_AS_OF, None, None, "text", False)
            return 0
        if a.cmd == "table":
            print("\n".join(table_lines()))
            return 0
        if a.cmd == "pack":
            return run_pack(a.use_cases, a.evidence, a.as_of, a.id, a.out_dir, a.format, a.all)
        build_parser().print_help()
        return 2
    except InputError as exc:
        print("challenge_pack: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
