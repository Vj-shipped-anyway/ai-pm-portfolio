"""spread_eval: score an extractor's output on financial statements field by field and layout by layout,
then gate on drift between layouts. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 spread_eval.py --demo
    python3 spread_eval.py score --docs DOCS.csv --truth TRUTH.csv --predictions PRED.csv
                                 [--floor 95] [--max-gap 3] [--min-docs 10]
    python3 spread_eval.py predict --extractor fixed_label|alias_aware --docs DOCS.csv > PRED.csv

Files (UTF-8 CSV with a header row):
    DOCS.csv   doc_id, layout            (a column named text is needed only by predict)
    TRUTH.csv  doc_id, field, period, value        period is current or prior
    PRED.csv   doc_id, field, period, value        an empty value means the extractor returned nothing

Exit status of score: 0 when the gate passes, 1 when it fails, 2 for bad or malformed input.
There is no model in this file. The scorer, the tie-out check and the gate are plain rules. The two
extractors that `predict` and `--demo` can run are rule-based stand-ins from _standins.py.

A value is right when it is within half a dollar of the truth. The gate fails a layout whose field
accuracy is below a floor, or more than a gap below the best layout. Both limits and the minimum
number of documents per layout are assumptions of this project, set on the command line.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys

from _standins import EXTRACTORS

FIELDS = ("revenue", "cost_of_sales", "gross_profit", "operating_expenses", "operating_income", "interest_expense",
          "pretax_income", "income_tax", "net_income", "cash", "accounts_receivable", "inventory",
          "total_current_assets", "fixed_assets_net", "total_assets", "accounts_payable", "short_term_debt",
          "total_current_liabilities", "long_term_debt", "total_liabilities", "total_equity",
          "total_liabilities_and_equity")
PERIODS = ("current", "prior")
# (name, result, plus, minus): the result field equals the sum of the plus fields less the minus fields
IDENTITIES = (
    ("gross_profit", "gross_profit", ("revenue",), ("cost_of_sales",)),
    ("operating_income", "operating_income", ("gross_profit",), ("operating_expenses",)),
    ("pretax_income", "pretax_income", ("operating_income",), ("interest_expense",)),
    ("net_income", "net_income", ("pretax_income",), ("income_tax",)),
    ("current_assets", "total_current_assets", ("cash", "accounts_receivable", "inventory"), ()),
    ("total_assets", "total_assets", ("total_current_assets", "fixed_assets_net"), ()),
    ("current_liabilities", "total_current_liabilities", ("accounts_payable", "short_term_debt"), ()),
    ("total_liabilities", "total_liabilities", ("total_current_liabilities", "long_term_debt"), ()),
    ("liabilities_and_equity", "total_liabilities_and_equity", ("total_liabilities", "total_equity"), ()),
    ("balance", "total_assets", ("total_liabilities_and_equity",), ()),
)
ERROR_CLASSES = ("missing", "scale", "sign", "wrong_period", "compound", "wrong_line", "other")
TOLERANCE = 0.5
DEFAULT_FLOOR = 95.0
DEFAULT_MAX_GAP = 3.0
DEFAULT_MIN_DOCS = 10
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


class InputError(Exception):
    """Bad or malformed input. The command line prints it as one line and exits 2."""


def clean(text, limit: int = 60) -> str:
    """Make untrusted text safe to print: no line breaks, control characters or workflow-command syntax."""
    out = []
    for ch in str(text):
        if ch == "%":
            out.append("%25")
        elif ch == "\r":
            out.append("%0D")
        elif ch == "\n":
            out.append("%0A")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("\\x%02x" % ord(ch))
        else:
            out.append(ch)
    s = "".join(out)
    return s if len(s) <= limit else s[:limit - 3] + "..."


def pct(correct: int, total: int) -> float:
    return round(100.0 * correct / total, 1) if total else 0.0


# ---------------------------------------------------------------- loading
def _rows(path: str, columns) -> list:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{clean(path)}: the file is empty")
            absent = [c for c in columns if c not in reader.fieldnames]
            if absent:
                raise InputError(f"{clean(path)}: missing column(s) {', '.join(absent)}")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{clean(path)}: {clean(e)}")
    for i, r in enumerate(rows, start=1):
        if any(r.get(c) is None for c in columns):
            raise InputError(f"{clean(path)}: row {i} has too few columns")
    if not rows:
        raise InputError(f"{clean(path)}: the file has a header and no rows")
    return rows


def _number(text: str, path: str, i: int):
    try:
        v = float(text)
    except ValueError:
        raise InputError(f"{clean(path)}: row {i} value {clean(text)!r} is not a number")
    if not math.isfinite(v):
        raise InputError(f"{clean(path)}: row {i} value {clean(text)!r} is not a finite number")
    return v


def load_docs(path: str, need_text: bool = False) -> list:
    rows = _rows(path, ("doc_id", "layout") + (("text",) if need_text else ()))
    seen = set()
    for i, r in enumerate(rows, start=1):
        if not r["doc_id"] or not r["layout"]:
            raise InputError(f"{clean(path)}: row {i} has an empty doc_id or layout")
        if r["doc_id"] in seen:
            raise InputError(f"{clean(path)}: doc_id {clean(r['doc_id'])!r} appears twice")
        seen.add(r["doc_id"])
    return rows


def _keyed(path: str, allow_empty: bool) -> dict:
    out = {}
    for i, r in enumerate(_rows(path, ("doc_id", "field", "period", "value")), start=1):
        if r["period"] not in PERIODS:
            raise InputError(f"{clean(path)}: row {i} period {clean(r['period'])!r} is not current or prior")
        key = (r["doc_id"], r["field"], r["period"])
        if key in out:
            raise InputError(f"{clean(path)}: row {i} repeats {clean(r['doc_id'])}/{clean(r['field'])}/{r['period']}")
        out[key] = None if allow_empty and r["value"].strip() == "" else _number(r["value"], path, i)
    return out


def load_truth(path: str) -> dict:
    return _keyed(path, allow_empty=False)


def load_predictions(path: str) -> dict:
    return _keyed(path, allow_empty=True)


def predictions_for(extractor, docs: list) -> dict:
    """Run an extractor (text -> {(field, period): number}) over documents that carry a text column."""
    out = {}
    for d in docs:
        for (field, period), v in extractor(d["text"]).items():
            out[(d["doc_id"], field, period)] = v
    return out


# ---------------------------------------------------------------- scoring
def classify(key: tuple, pred, truth: dict, same_period: dict) -> str:
    """The class of one wrong value. same_period maps field -> true value for the key's document and period.
    scale, sign and wrong_period are single repairs (multiply by 1000 or 1,000,000 or divide, flip the sign,
    read the other period); compound needs two or more; wrong_line means the number belongs to another field."""
    doc, field, period = key
    if pred is None:
        return "missing"
    other = truth.get((doc, field, "prior" if period == "current" else "current"))
    best = None
    for target, period_step in ((truth[key], 0), (other, 1)):
        if target is None or target == 0:
            continue
        for factor, scale_step in ((1.0, 0), (1000.0, 1), (0.001, 1), (1000000.0, 1), (0.000001, 1)):
            for sign, sign_step in ((1, 0), (-1, 1)):
                if abs(sign * pred * factor - target) < TOLERANCE:
                    steps = (["scale"] * scale_step + ["sign"] * sign_step + ["wrong_period"] * period_step)
                    if best is None or len(steps) < len(best):
                        best = steps
    if best is not None and len(best) == 1:
        return best[0]
    if best is not None:
        return "compound"
    if any(abs(v - pred) < TOLERANCE for f, v in same_period.items() if f != field):
        return "wrong_line"
    return "other"


def tie_out(preds: dict, doc_ids) -> dict:
    """{doc_id: problems}. Checks the accounting identities on the predictions alone, with no truth.
    A document with no problems ties out. A missing field makes every identity that uses it incomplete."""
    out = {}
    for d in doc_ids:
        problems = []
        for p in PERIODS:
            for name, result, plus, minus in IDENTITIES:
                vals = {f: preds.get((d, f, p)) for f in (result,) + plus + minus}
                if any(v is None for v in vals.values()):
                    problems.append(f"{p}:{name}:incomplete")
                elif abs(sum(vals[f] for f in plus) - sum(vals[f] for f in minus) - vals[result]) >= TOLERANCE:
                    problems.append(f"{p}:{name}:broken")
        out[d] = problems
    return out


def evaluate(layout_of: dict, truth: dict, preds: dict) -> dict:
    """Score predictions against truth, by layout, field and error class, and run the tie-out check."""
    unknown = sorted({k[0] for k in truth if k[0] not in layout_of})
    if unknown:
        raise InputError(f"the truth file names {len(unknown)} document(s) that are not in the docs file, first {clean(unknown[0])!r}")
    matched = sum(1 for k in preds if k in truth)
    if matched == 0:
        raise InputError("no prediction row matches a truth row; check the spelling of doc_id, field and period")
    by_period = {}
    for (d, f, p), v in truth.items():
        by_period.setdefault((d, p), {})[f] = v
    doc_ids = sorted({k[0] for k in truth})
    ties = tie_out(preds, doc_ids)
    layouts, wrong_docs = {}, set()
    for key in sorted(truth):
        d, f, p = key
        lay = layouts.setdefault(layout_of[d], {"docs": set(), "values": 0, "correct": 0,
                                                "errors": dict.fromkeys(ERROR_CLASSES, 0), "fields": {}})
        pred = preds.get(key)
        ok = pred is not None and abs(pred - truth[key]) < TOLERANCE
        lay["docs"].add(d)
        lay["values"] += 1
        lay["correct"] += ok
        cell = lay["fields"].setdefault(f, [0, 0])
        cell[0] += 1
        cell[1] += ok
        if not ok:
            lay["errors"][classify(key, pred, truth, by_period[(d, p)])] += 1
            wrong_docs.add(d)
    for lay in layouts.values():
        members = lay.pop("docs")
        lay["docs"] = len(members)
        lay["docs_all_right"] = len(members - wrong_docs)
        lay["wrong_unflagged"] = sum(1 for d in members & wrong_docs if not ties[d])
    return {"documents": len(doc_ids), "values": len(truth), "correct": sum(v["correct"] for v in layouts.values()),
            "missing": sum(v["errors"]["missing"] for v in layouts.values()), "extra": len(preds) - matched,
            "unscored_documents": len(layout_of) - len(doc_ids), "layouts": layouts,
            "errors": {c: sum(v["errors"][c] for v in layouts.values()) for c in ERROR_CLASSES},
            "tie_flagged": sum(1 for d in doc_ids if ties[d]), "wrong_documents": len(wrong_docs),
            "wrong_unflagged": sum(v["wrong_unflagged"] for v in layouts.values()),
            "right_flagged": sum(1 for d in doc_ids if ties[d] and d not in wrong_docs)}


def gate(layouts: dict, floor: float, max_gap: float, min_docs: int) -> dict:
    """PASS when every layout with enough documents clears the floor and sits within max_gap of the best."""
    gated = sorted(n for n, s in layouts.items() if s["docs"] >= min_docs)
    if not gated:
        raise InputError(f"no layout has {min_docs} or more documents, so nothing can be gated")
    acc = {n: pct(layouts[n]["correct"], layouts[n]["values"]) for n in gated}
    best = sorted(gated, key=lambda n: (-acc[n], n))[0]
    reasons = []
    for n in sorted(gated, key=lambda n: (acc[n], n)):
        parts = []
        if acc[n] < floor:
            parts.append(f"below the floor of {floor:.1f}%")
        if round(acc[best] - acc[n], 1) > max_gap:
            parts.append(f"{acc[best] - acc[n]:.1f} points below {clean(best)}")
        if parts:
            reasons.append(f"{clean(n)}: {acc[n]:.1f}% is " + " and ".join(parts))
    return {"verdict": "FAIL" if reasons else "PASS", "reasons": reasons, "best": best,
            "not_gated": sorted(n for n in layouts if n not in gated)}


# ---------------------------------------------------------------- output
def render(label: str, res: dict, verdict: dict, floor: float, max_gap: float, min_docs: int) -> str:
    lay = res["layouts"]
    names = sorted(lay, key=lambda n: (-pct(lay[n]["correct"], lay[n]["values"]), n))
    w = max([6] + [len(clean(n)) for n in names])
    head = [f"extractor: {clean(label)}",
            f"documents {res['documents']}, truth values {res['values']}, no prediction {res['missing']}, "
            f"extra prediction rows {res['extra']}"]
    lines = head
    if res["unscored_documents"]:
        lines.append(f"documents with no truth, not scored: {res['unscored_documents']}")
    lines.append(f"{'layout':<{w}}  {'docs':>5}  {'values':>6}  {'correct':>7}  {'accuracy':>9}  {'documents all right':>19}")
    for n in names:
        s = lay[n]
        lines.append(f"{clean(n):<{w}}  {s['docs']:>5}  {s['values']:>6}  {s['correct']:>7}  {pct(s['correct'], s['values']):>8.1f}%  "
                     f"{str(s['docs_all_right']) + ' of ' + str(s['docs']):>19}")
    lines.append(f"{'all layouts pooled':<{w}}  {res['documents']:>5}  {res['values']:>6}  {res['correct']:>7}  "
                 f"{pct(res['correct'], res['values']):>8.1f}%")
    wrong = ", ".join(f"{c} {res['errors'][c]}" for c in ERROR_CLASSES if res["errors"][c]) or "none"
    lines.append(f"wrong values by class: {wrong}")
    lines.append(f"tie-out, no truth needed: flags {res['tie_flagged']} of {res['documents']} documents; "
                 f"{res['wrong_unflagged']} of {res['wrong_documents']} documents with a wrong value pass every identity")
    lines.append(f"gate (floor {floor:.1f}%, max gap {max_gap:.1f} points, at least {min_docs} documents per layout): {verdict['verdict']}")
    lines += [f"  {r}" for r in verdict["reasons"]]
    if verdict["not_gated"]:
        lines.append("  not gated, too few documents: " + ", ".join(clean(n) for n in verdict["not_gated"]))
    return "\n".join(lines)


def write_predictions(preds: dict, doc_ids, out) -> None:
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["doc_id", "field", "period", "value"])
    for d in doc_ids:
        for f in FIELDS:
            for p in PERIODS:
                if (d, f, p) in preds:
                    w.writerow([d, f, p, preds[(d, f, p)]])


def run_score(docs_path, truth_path, pred_path, floor, max_gap, min_docs, label=None, demo_preds=None) -> int:
    try:
        if not (0 <= floor <= 100) or max_gap < 0 or min_docs < 1:
            raise InputError("--floor must be 0 to 100, --max-gap 0 or more, --min-docs 1 or more")
        docs = load_docs(docs_path)
        layout_of = {d["doc_id"]: d["layout"] for d in docs}
        truth = load_truth(truth_path)
        preds = demo_preds if demo_preds is not None else load_predictions(pred_path)
        res = evaluate(layout_of, truth, preds)
        verdict = gate(res["layouts"], floor, max_gap, min_docs)
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    print(render(label or os.path.basename(pred_path), res, verdict, floor, max_gap, min_docs))
    return 0 if verdict["verdict"] == "PASS" else 1


def run_predict(name: str, docs_path: str) -> int:
    try:
        docs = load_docs(docs_path, need_text=True)
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    write_predictions(predictions_for(EXTRACTORS[name], docs), [d["doc_id"] for d in docs], sys.stdout)
    return 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"usage error: {message}", file=sys.stderr)
        sys.exit(2)


def main(argv=None) -> int:
    ap = _Parser(prog="spread_eval")
    ap.add_argument("--demo", action="store_true", help="score the fixed_label stand-in on the bundled statements")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("score", help="score a predictions file against truth, by layout")
    s.add_argument("--docs", required=True, help="CSV with doc_id and layout")
    s.add_argument("--truth", required=True, help="CSV with doc_id, field, period, value")
    s.add_argument("--predictions", required=True, help="CSV in the same shape as the truth file")
    s.add_argument("--floor", type=float, default=DEFAULT_FLOOR, help="lowest field accuracy a layout may have, in percent (default %(default)s)")
    s.add_argument("--max-gap", type=float, default=DEFAULT_MAX_GAP, help="largest allowed distance below the best layout, in points (default %(default)s)")
    s.add_argument("--min-docs", type=int, default=DEFAULT_MIN_DOCS, help="fewest documents a layout needs to be gated (default %(default)s)")
    p = sub.add_parser("predict", help="run a bundled stand-in extractor and print a predictions file")
    p.add_argument("--extractor", choices=sorted(EXTRACTORS), required=True)
    p.add_argument("--docs", required=True, help="CSV with doc_id, layout and text")
    a = ap.parse_args(argv)
    if a.demo:
        docs_path = os.path.join(DATA, "statements.csv")
        docs = load_docs(docs_path, need_text=True)
        run_score(docs_path, os.path.join(DATA, "truth.csv"), "", DEFAULT_FLOOR, DEFAULT_MAX_GAP, DEFAULT_MIN_DOCS,
                  label="fixed_label (a rule-based stand-in, not a model)", demo_preds=predictions_for(EXTRACTORS["fixed_label"], docs))
        return 0
    if a.cmd == "score":
        return run_score(a.docs, a.truth, a.predictions, a.floor, a.max_gap, a.min_docs)
    if a.cmd == "predict":
        return run_predict(a.extractor, a.docs)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
