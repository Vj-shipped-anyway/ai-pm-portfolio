"""
Step 4 - The fix: TierGate.

Five moves on every intake submission, in this order:

  1. Recompute the tier from the form PLUS cross-checks, using the bank's own
     written rubric (points on data class, vendor model, customer-facing,
     autonomy, regulatory scope, exposure; tier = min(4, 1 + points // 4)).
       - data class       : the higher of the form and the data catalog
       - vendor model     : the higher of the form and the vendor registry
       - customer-facing  : blank or 'unsure' resolves to yes until the sponsor
                            confirms; 'no' flips to yes if the text mentions
                            customers (keyword match, standard library)
  2. Flag every discrepancy with a reason a reviewer can read.
  3. Link duplicate or overlapping submissions with token-overlap (Jaccard)
     similarity. Proposed links only: a reviewer confirms them.
  4. Gate approval on the evidence checklist of the RECOMPUTED tier.
  5. Order the review queue by recomputed tier instead of arrival.

TierGate never reads the hidden columns (true_*, reference_*, duplicate_group,
catalog true_class / catalog_status). recompute() receives only the form view,
the catalog's recorded class, and the registry. The reference columns are used
afterwards, to score the result.

The known limit is left in on purpose and printed: when the form AND the catalog
are both wrong about a data class, the recompute agrees with the wrong answer.

Run from this folder:  python3 step_04_with_tiergate.py

Output:
  - prints the four headline measures, the queue comparison, the flags, the limit
  - writes src/out/step_04_results.json and src/out/step_04_cases.csv
"""

from __future__ import annotations

import csv
import json
import re

import step_01_spreadsheet_fifo as s1
import step_02_self_declared_tier as s2
import step_03_deficiencies_exposed as s3
from step_01_spreadsheet_fifo import (
    HI_TIERS, LINK_CHECK_H, OUT_DIR, REPLICATIONS, TIER_REVIEW_H, assumptions_text,
    load_cases, load_checklist, load_evidence_names, load_evidence_on_file, run_queue,
)

# ---------------------------------------------------------------------------
# The written rubric (the same arithmetic that produced the reference tier)
# ---------------------------------------------------------------------------
CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
VENDOR_ORDER = ["none", "self_hosted", "vendor_api"]
PTS_CUSTOMER = {"yes": 2, "no": 0}
PTS_AUTONOMY = {"advisory": 0, "assisted": 1, "automated": 3}
PTS_CLASS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
PTS_VENDOR = {"none": 0, "self_hosted": 1, "vendor_api": 2}
PTS_REG = {"none": 0, "privacy": 1, "aml": 2, "udaap": 2, "fair_lending": 3}
PTS_EXPOSURE = {"lt_1m": 0, "1m_10m": 1, "10m_50m": 2, "gt_50m": 3}


def rubric_score(cf: str, aut: str, cls: str, ven: str, reg: str, exp: str) -> int:
    return (PTS_CUSTOMER[cf] + PTS_AUTONOMY[aut] + PTS_CLASS[cls]
            + PTS_VENDOR[ven] + PTS_REG[reg] + PTS_EXPOSURE[exp])


def tier_from_score(score: int) -> int:
    return min(4, 1 + score // 4)


CROSSCHECK_CODES = ("DATA_CLASS_BELOW_CATALOG", "VENDOR_NOT_DECLARED",
                    "CUSTOMER_FACING_CUE", "CUSTOMER_FACING_AMBIGUOUS")

def rubric_rows(cf: str, aut: str, cls: str, ven: str, reg: str, exp: str) -> list:
    """(input, value, points) rows. A blank or 'unsure' customer-facing answer scores 0 on the sponsor's own form."""
    return [("customer-facing", cf or "(blank)", PTS_CUSTOMER.get(cf, 0)),
            ("decision autonomy", aut, PTS_AUTONOMY[aut]),
            ("data class", cls, PTS_CLASS[cls]),
            ("vendor model", ven, PTS_VENDOR[ven]),
            ("regulatory scope", reg, PTS_REG[reg]),
            ("exposure band", exp, PTS_EXPOSURE[exp])]


# Only these columns are visible to TierGate.
FORM_FIELDS = ["use_case_id", "title", "description", "dataset_name", "customer_facing",
               "decision_autonomy", "data_class", "vendor_model", "regulatory_scope",
               "financial_exposure_band", "self_declared_tier"]


def form_view(case: dict) -> dict:
    return {k: case[k] for k in FORM_FIELDS}


CUE_RE = re.compile(r"\b(customer|client|borrower|cardholder|applicant|consumer|caller|"
                    r"depositor|account holder)s?\b", re.IGNORECASE)

# Duplicate linking
STOPWORDS = set("""a an and are as at be by for from has have in into is it its of on or per
that the their this to was were will with scope using use used""".split())
LINK_THRESHOLD = 0.50


def tokens(text: str) -> set:
    out = set()
    for w in re.findall(r"[a-z]+", text.lower()):
        if len(w) < 3 or w in STOPWORDS:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


# ---------------------------------------------------------------------------
# 1 + 2. Recompute the tier and flag discrepancies
# ---------------------------------------------------------------------------
def recompute(form: dict, catalog: dict, registry: dict) -> dict:
    flags: list[dict] = []
    ds = form["dataset_name"]

    # data class: the higher of the form and the catalog
    f_cls = form["data_class"]
    if ds not in catalog:
        cls = f_cls
        flags.append({"code": "DATASET_NOT_IN_CATALOG",
                      "reason": "dataset %s is not in the catalog; class unverified" % ds})
    else:
        c_cls = catalog[ds]
        if CLASS_ORDER.index(c_cls) > CLASS_ORDER.index(f_cls):
            cls = c_cls
            flags.append({"code": "DATA_CLASS_BELOW_CATALOG",
                          "reason": "form says %s; the catalog records %s for %s; using %s"
                                    % (f_cls, c_cls, ds, c_cls)})
        elif CLASS_ORDER.index(c_cls) < CLASS_ORDER.index(f_cls):
            cls = f_cls
            flags.append({"code": "DATA_CLASS_ABOVE_CATALOG",
                          "reason": "form says %s; the catalog records %s for %s; kept the higher class, "
                                    "steward to review the catalog entry" % (f_cls, c_cls, ds)})
        else:
            cls = f_cls

    # vendor model: the higher of the form and the registry
    f_ven = form["vendor_model"]
    r_ven = registry.get(form["use_case_id"])
    ven = f_ven
    if r_ven is not None and VENDOR_ORDER.index(r_ven) > VENDOR_ORDER.index(f_ven):
        ven = r_ven
        flags.append({"code": "VENDOR_NOT_DECLARED",
                      "reason": "form says %s; the vendor registry lists %s; using %s" % (f_ven, r_ven, r_ven)})

    # customer-facing: resolve missing or ambiguous conservatively; check the text
    f_cf = form["customer_facing"]
    text = form["title"] + " " + form["description"]
    if f_cf == "yes":
        cf = "yes"
    elif f_cf == "no":
        m = CUE_RE.search(text)
        if m:
            cf = "yes"
            flags.append({"code": "CUSTOMER_FACING_CUE",
                          "reason": "form says internal; the text mentions '%s'; treated as customer-facing "
                                    "until the sponsor confirms" % m.group(0).lower()})
        else:
            cf = "no"
    else:
        cf = "yes"
        flags.append({"code": "CUSTOMER_FACING_AMBIGUOUS",
                      "reason": "customer-facing answer is %s; treated as customer-facing until the sponsor "
                                "confirms" % ("blank" if f_cf == "" else "'unsure'")})

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
    return {"tier": tier, "score": score, "customer_facing": cf, "data_class": cls,
            "vendor_model": ven, "flags": flags}


# ---------------------------------------------------------------------------
# 3. Duplicate linking
# ---------------------------------------------------------------------------
def similarity_pairs(cases: list[dict]) -> list[tuple]:
    toks = [tokens(c["title"] + " " + c["description"]) for c in cases]
    pairs = []
    for i in range(len(cases)):
        for j in range(i + 1, len(cases)):
            pairs.append((i, j, jaccard(toks[i], toks[j])))
    return pairs


def true_pair(a: dict, b: dict) -> bool:
    return bool(a["duplicate_group"]) and a["duplicate_group"] == b["duplicate_group"]


def link_metrics(cases: list[dict], pairs: list[tuple], threshold: float) -> dict:
    tp = fp = fn = 0
    for i, j, sc in pairs:
        t = true_pair(cases[i], cases[j])
        if sc >= threshold and t:
            tp += 1
        elif sc >= threshold and not t:
            fp += 1
        elif sc < threshold and t:
            fn += 1
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1}


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
def causes_of_error(c: dict, r: dict) -> list[str]:
    """Why the recomputed tier differs from the reference (uses hidden columns, for scoring only)."""
    out = []
    t_cls = CLASS_ORDER.index(c["true_data_class"])
    if CLASS_ORDER.index(r["data_class"]) < t_cls:
        out.append("data class: form and catalog both below the true class")
    elif CLASS_ORDER.index(r["data_class"]) > t_cls:
        out.append("data class: catalog entry overstates the class")
    t_ven = VENDOR_ORDER.index(c["true_vendor_model"])
    if VENDOR_ORDER.index(r["vendor_model"]) < t_ven:
        out.append("vendor: form and registry both silent")
    if r["customer_facing"] == "no" and c["true_customer_facing"] == "yes":
        out.append("customer-facing: form said no and the text had no cue")
    if r["customer_facing"] == "yes" and c["true_customer_facing"] == "no":
        out.append("customer-facing: resolved to yes, truly internal")
    return out


def run() -> dict:
    cases = load_cases()
    checklist = load_checklist()
    on_file = load_evidence_on_file()
    catalog = s3.load_catalog()
    registry = s3.load_registry()
    n = len(cases)

    step1 = s1.run()
    step2 = s2.run()

    # --- rubric self-check: the same arithmetic reproduces the reference tier from the true columns
    selfcheck = sum(
        1 for c in cases
        if tier_from_score(rubric_score(c["true_customer_facing"], c["true_decision_autonomy"],
                                        c["true_data_class"], c["true_vendor_model"],
                                        c["true_regulatory_scope"], c["true_financial_exposure_band"]))
        == c["reference_tier"])

    # --- 1 + 2 recompute and flag
    recs = [recompute(form_view(c), catalog, registry) for c in cases]

    # --- 3 duplicate links
    pairs = similarity_pairs(cases)
    metrics = link_metrics(cases, pairs, LINK_THRESHOLD)
    sweep = [link_metrics(cases, pairs, t) for t in (0.30, 0.40, 0.50, 0.60, 0.70)]
    linked = [(i, j, sc) for i, j, sc in pairs if sc >= LINK_THRESHOLD]
    linked_to: dict[int, tuple] = {}
    for i, j, sc in linked:      # j is the later submission (cases are sorted by id)
        if j not in linked_to or sc > linked_to[j][1]:
            linked_to[j] = (i, sc)

    # --- 4 evidence gate
    rows = []
    for idx, (c, r) in enumerate(zip(cases, recs)):
        have = on_file.get(c["use_case_id"], set())
        missing = [e for e in checklist[r["tier"]] if e not in have]
        missing_ref = [e for e in checklist[c["reference_tier"]] if e not in have]
        lk = linked_to.get(idx)
        rows.append({
            "use_case_id": c["use_case_id"],
            "declared": c["self_declared_tier"],
            "recomputed": r["tier"],
            "reference": c["reference_tier"],
            "score": r["score"],
            "flags": r["flags"],
            "gate": "READY" if not missing else "HOLD",
            "missing": missing,
            "missing_reference": missing_ref,
            "linked_to": cases[lk[0]]["use_case_id"] if lk else "",
            "link_score": round(lk[1], 3) if lk else 0.0,
            "link_true": bool(lk) and true_pair(cases[lk[0]], c),
            "causes": causes_of_error(c, r) if r["tier"] != c["reference_tier"] else [],
        })

    # --- the headline case: under-declared true tier 3-4, recomputed correctly with every checked input
    # equal to the true value (so the example does not rest on a lucky false flag)
    head = [x for c, r, x in zip(cases, recs, rows)
            if c["reference_tier"] >= 3 and x["declared"] < x["reference"] and x["recomputed"] == x["reference"]
            and r["customer_facing"] == c["true_customer_facing"] and r["data_class"] == c["true_data_class"]
            and r["vendor_model"] == c["true_vendor_model"]]
    head.sort(key=lambda x: (-(x["reference"] - x["declared"]), -len(x["flags"]), x["use_case_id"]))
    headline_id = head[0]["use_case_id"]

    # --- tier measures
    acc_n = sum(1 for x in rows if x["recomputed"] == x["reference"])
    hi = [x for x in rows if x["reference"] in HI_TIERS]
    hi_found = [x for x in hi if x["recomputed"] in HI_TIERS]
    pred_hi = [x for x in rows if x["recomputed"] in HI_TIERS]
    pred_hi_right = [x for x in pred_hi if x["reference"] in HI_TIERS]
    under_n = sum(1 for x in rows if x["recomputed"] < x["reference"])
    over_n = sum(1 for x in rows if x["recomputed"] > x["reference"])
    hi_under_n = sum(1 for x in hi if x["recomputed"] < x["reference"])
    confusion = [[0] * 4 for _ in range(4)]
    for x in rows:
        confusion[x["reference"] - 1][x["recomputed"] - 1] += 1

    # --- evidence measures
    gap_cases = [x for x in rows if x["missing_reference"]]
    gap_held = [x for x in gap_cases if x["gate"] == "HOLD"]
    ready = [x for x in rows if x["gate"] == "READY"]
    ready_gap = [x for x in ready if x["missing_reference"]]
    hold_no_gap = [x for x in rows if x["gate"] == "HOLD" and not x["missing_reference"]]

    # --- flag precision (uses hidden columns, scoring only)
    def flag_stats(code: str, right) -> dict:
        flagged = [(c, x) for c, x in zip(cases, rows) if any(f["code"] == code for f in x["flags"])]
        ok = [1 for c, x in flagged if right(c)]
        return {"code": code, "raised": len(flagged), "right": len(ok)}
    flag_table = [
        flag_stats("DATA_CLASS_BELOW_CATALOG",
                   lambda c: CLASS_ORDER.index(c["data_class"]) < CLASS_ORDER.index(c["true_data_class"])),
        flag_stats("VENDOR_NOT_DECLARED",
                   lambda c: VENDOR_ORDER.index(c["vendor_model"]) < VENDOR_ORDER.index(c["true_vendor_model"])),
        flag_stats("CUSTOMER_FACING_CUE", lambda c: c["true_customer_facing"] == "yes"),
        flag_stats("CUSTOMER_FACING_AMBIGUOUS", lambda c: c["true_customer_facing"] == "yes"),
    ]
    flag_counts: dict[str, int] = {}
    for x in rows:
        for f in x["flags"]:
            flag_counts[f["code"]] = flag_counts.get(f["code"], 0) + 1

    # --- the known limit: form AND catalog both wrong on the data class
    both_wrong = []
    for c, x in zip(cases, rows):
        t_cls = CLASS_ORDER.index(c["true_data_class"])
        if (CLASS_ORDER.index(c["data_class"]) < t_cls
                and CLASS_ORDER.index(catalog[c["dataset_name"]]) < t_cls):
            both_wrong.append((c, x))
    both_wrong_mis = [(c, x) for c, x in both_wrong if x["recomputed"] != x["reference"]]
    cause_counts: dict[str, int] = {}
    for x in rows:
        for cz in x["causes"]:
            cause_counts[cz] = cause_counts.get(cz, 0) + 1

    # --- queue: tier-depth review times after duplicate merging
    hours = []
    for idx, (c, x) in enumerate(zip(cases, rows)):
        h = TIER_REVIEW_H[x["recomputed"]]
        if x["linked_to"]:
            h = LINK_CHECK_H if x["link_true"] else LINK_CHECK_H + h
        hours.append(h)
    prio = [x["recomputed"] for x in rows]
    q_fifo = run_queue(cases, hours, priority=None)
    q_ord = run_queue(cases, hours, priority=prio)

    sens = []
    for k in (2, 3, 4):
        a = run_queue(cases, hours, None, n_reviewers=k)
        b = run_queue(cases, hours, prio, n_reviewers=k)
        sens.append({"reviewers": k, "offered_load": a["offered_load"],
                     "hi_fifo": a["wait_hi_mean"], "hi_ordered": b["wait_hi_mean"],
                     "lo_fifo": a["wait_lo_mean"], "lo_ordered": b["wait_lo_mean"]})

    for idx, x in enumerate(rows):
        x["wait_before"] = round(step1["per_case_mean_wait"][idx], 3)
        x["wait_basic"] = round(step2["per_case_mean_wait"][idx], 3)
        x["wait_fifo"] = round(q_fifo["per_case_mean_wait"][idx], 3)
        x["wait_ordered"] = round(q_ord["per_case_mean_wait"][idx], 3)
        x["review_hours"] = round(hours[idx], 2)

    # --- utility
    err_declared = step2["mis_tier_rate"]
    err_tiergate = 1 - acc_n / n
    weeks_in_set = 20
    per_week = n / weeks_in_set
    annual = int(round(per_week * 50))
    utility = (err_declared - err_tiergate) * annual

    return {
        "n_cases": n,
        "rubric_selfcheck_n": selfcheck,
        "headline_id": headline_id,
        "accuracy_n": acc_n,
        "accuracy": acc_n / n,
        "err_tiergate": err_tiergate,
        "err_declared": err_declared,
        "under_n": under_n,
        "over_n": over_n,
        "hi_n": len(hi),
        "hi_found_n": len(hi_found),
        "hi_recall": len(hi_found) / len(hi),
        "hi_precision": len(pred_hi_right) / len(pred_hi),
        "pred_hi_n": len(pred_hi),
        "hi_under_n": hi_under_n,
        "declared_hi_recall": step2["hi_recall"],
        "declared_hi_under_n": step2["hi_under_n"],
        "confusion": confusion,
        "gap_cases_n": len(gap_cases),
        "gap_held_n": len(gap_held),
        "gap_detection_rate": len(gap_held) / len(gap_cases),
        "basic_gap_detection_rate": step2["gap_detection_rate"],
        "ready_n": len(ready),
        "hold_n": n - len(ready),
        "ready_missing_ref_n": len(ready_gap),
        "hold_no_gap_n": len(hold_no_gap),
        "basic_approved_n": step2["approved_n"],
        "basic_approved_missing_ref_n": step2["approved_missing_ref_n"],
        "link": metrics,
        "link_sweep": sweep,
        "link_threshold": LINK_THRESHOLD,
        "n_pairs": len(pairs),
        "links_proposed_n": len(linked_to),
        "links_split_tier_n": sum(1 for idx, (i, sc) in linked_to.items()
                                  if cases[i]["self_declared_tier"] != cases[idx]["self_declared_tier"]),
        "flag_table": flag_table,
        "flag_counts": flag_counts,
        "crosscheck_flagged_n": sum(1 for x in rows if any(f["code"] in CROSSCHECK_CODES for f in x["flags"])),
        "tier_changed_n": sum(1 for x in rows if x["recomputed"] != x["declared"]),
        "both_wrong_n": len(both_wrong),
        "both_wrong_mis_n": len(both_wrong_mis),
        "both_wrong_ids": [c["use_case_id"] for c, _ in both_wrong],
        "both_wrong_mis_ids": [c["use_case_id"] for c, _ in both_wrong_mis],
        "cause_counts": cause_counts,
        "queue": {
            "hours_before": step1["total_hours"], "hours_basic": step2["total_hours"],
            "hours_tiergate": q_fifo["total_hours"],
            "load_before": step1["offered_load"], "load_basic": step2["offered_load"],
            "load_tiergate": q_fifo["offered_load"],
            "hi_before": step1["wait_hi_mean"], "hi_basic": step2["wait_hi_mean"],
            "hi_fifo": q_fifo["wait_hi_mean"], "hi_fifo_p5": q_fifo["wait_hi_p5"], "hi_fifo_p95": q_fifo["wait_hi_p95"],
            "hi_ordered": q_ord["wait_hi_mean"], "hi_ordered_p5": q_ord["wait_hi_p5"], "hi_ordered_p95": q_ord["wait_hi_p95"],
            "lo_before": step1["wait_lo_mean"], "lo_basic": step2["wait_lo_mean"],
            "lo_fifo": q_fifo["wait_lo_mean"], "lo_ordered": q_ord["wait_lo_mean"],
            "sensitivity": sens,
        },
        "utility": {
            "err_declared": err_declared, "err_tiergate": err_tiergate,
            "per_week": per_week, "annual_intake": annual, "avoided_per_year": utility,
            "annual_sensitivity": [{"intake": m, "avoided": (err_declared - err_tiergate) * m}
                                   for m in (annual, annual * 2, annual * 4)],
        },
        "rows": rows,
        "hours_per_case": hours,
        "assumptions": assumptions_text(),
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    res = run()
    n = res["n_cases"]
    names = load_evidence_names()
    print("\n" + "=" * 80)
    print("Step 4 - The fix: TierGate (recompute, flag, link, gate, order)")
    print("=" * 80)
    print("\nRubric self-check: the written rubric applied to the true columns reproduces the committed")
    print("reference tier on %d of %d submissions." % (res["rubric_selfcheck_n"], n))
    print("Reference tier is true by construction, so the measures below say how well TierGate recovers")
    print("it from noisy inputs, not how real banks behave.")

    print("\nHEADLINE MEASURES (green, measured on the %d synthetic submissions)" % n)
    print("  Tier accuracy (recomputed = reference):       %d of %d  (%.1f%%)   self-declared: %.1f%%"
          % (res["accuracy_n"], n, 100 * res["accuracy"], 100 * (1 - res["err_declared"])))
    print("  Mis-tier rate:                                %.1f%%   self-declared: %.1f%%"
          % (100 * res["err_tiergate"], 100 * res["err_declared"]))
    print("    recomputed too low: %d    recomputed too high: %d" % (res["under_n"], res["over_n"]))
    print("  Tier 3-4 recall:                              %d of %d  (%.1f%%)   self-declared: %.1f%%"
          % (res["hi_found_n"], res["hi_n"], 100 * res["hi_recall"], 100 * res["declared_hi_recall"]))
    print("    true tier 3-4 still below their reference tier: %d   (self-declared: %d)"
          % (res["hi_under_n"], res["declared_hi_under_n"]))
    print("  Tier 3-4 precision:                           %d of %d predicted  (%.1f%%)"
          % (round(res["hi_precision"] * res["pred_hi_n"]), res["pred_hi_n"], 100 * res["hi_precision"]))
    print("  Evidence-gap detection rate:                  %d of %d cases with a real gap held  (%.1f%%)   basic approach: %.1f%%"
          % (res["gap_held_n"], res["gap_cases_n"], 100 * res["gap_detection_rate"],
             100 * res["basic_gap_detection_rate"]))
    print("  Approvals granted with required evidence missing:  %d of %d   basic approach: %d of %d"
          % (res["ready_missing_ref_n"], res["ready_n"], res["basic_approved_missing_ref_n"],
             res["basic_approved_n"]))
    print("  Held for evidence that the reference tier does not require (over-hold): %d" % res["hold_no_gap_n"])

    print("\n  Confusion (rows = reference tier, columns = recomputed tier):")
    print("            recomputed 1  recomputed 2  recomputed 3  recomputed 4")
    for i, r in enumerate(res["confusion"], 1):
        print("  ref %d      %10d    %10d    %10d    %10d" % (i, r[0], r[1], r[2], r[3]))

    ex_id = res["headline_id"]
    ex_case = next(c for c in load_cases() if c["use_case_id"] == ex_id)
    ex_rec = recompute(form_view(ex_case), s3.load_catalog(), s3.load_registry())
    cols = [
        rubric_rows(ex_case["customer_facing"], ex_case["decision_autonomy"], ex_case["data_class"],
                    ex_case["vendor_model"], ex_case["regulatory_scope"], ex_case["financial_exposure_band"]),
        rubric_rows(ex_rec["customer_facing"], ex_case["decision_autonomy"], ex_rec["data_class"],
                    ex_rec["vendor_model"], ex_case["regulatory_scope"], ex_case["financial_exposure_band"]),
        rubric_rows(ex_case["true_customer_facing"], ex_case["true_decision_autonomy"], ex_case["true_data_class"],
                    ex_case["true_vendor_model"], ex_case["true_regulatory_scope"], ex_case["true_financial_exposure_band"]),
    ]
    print("\nWORKED EXAMPLE %s (rubric points; tier = min(4, 1 + points // 4))" % ex_id)
    print("  %s" % ex_case["title"])
    print("  %-18s %-24s %-24s %-24s" % ("input", "sponsor's form", "TierGate checked", "true value (hidden)"))
    for i in range(6):
        cells = ["%s (%d)" % (cols[k][i][1], cols[k][i][2]) for k in range(3)]
        print("  %-18s %-24s %-24s %-24s" % (cols[0][i][0], cells[0], cells[1], cells[2]))
    totals = [sum(r[2] for r in col) for col in cols]
    print("  %-18s %-24s %-24s %-24s" % ("points / tier", "%d / tier %d" % (totals[0], tier_from_score(totals[0])),
                                         "%d / tier %d" % (totals[1], tier_from_score(totals[1])),
                                         "%d / tier %d" % (totals[2], tier_from_score(totals[2]))))
    print("  The sponsor declared tier %d." % ex_case["self_declared_tier"])

    print("\nDISCREPANCY FLAGS (each carries a reason)")
    print("  Cases with at least one cross-check flag: %d of %d.  Cases whose tier TierGate changed: %d of %d."
          % (res["crosscheck_flagged_n"], n, res["tier_changed_n"], n))
    print("  code                          raised  right   (right = the flag pointed at a real form error)")
    for f in res["flag_table"]:
        print("  %-28s %6d  %5d" % (f["code"], f["raised"], f["right"]))
    for code in ("DATA_CLASS_ABOVE_CATALOG", "TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE"):
        print("  %-28s %6d  (informational or derived)" % (code, res["flag_counts"].get(code, 0)))
    ex = next(x for x in res["rows"] if x["flags"] and x["recomputed"] != x["declared"] and x["recomputed"] == x["reference"])
    print("  Example %s (declared %d, recomputed %d, reference %d):" % (ex["use_case_id"], ex["declared"], ex["recomputed"], ex["reference"]))
    for f in ex["flags"]:
        print("    - %s: %s" % (f["code"], f["reason"]))

    lk = res["link"]
    print("\nDUPLICATE LINKING (green; token-overlap Jaccard on title + description, threshold %.2f)" % res["link_threshold"])
    print("  True duplicate pairs in the set:              %d" % (lk["tp"] + lk["fn"]))
    print("  Pairs linked: %d    right: %d    wrong: %d    missed: %d    precision %.2f    recall %.2f"
          % (lk["tp"] + lk["fp"], lk["tp"], lk["fp"], lk["fn"], lk["precision"], lk["recall"]))
    print("  The threshold is a fixed design value, not tuned on this run; the sweep shows what moving it does on this same set:")
    print("    threshold  linked  right  wrong  missed  precision  recall")
    for sw in res["link_sweep"]:
        print("    %.2f       %5d  %5d  %5d  %6d  %9.2f  %6.2f"
              % (sw["threshold"], sw["tp"] + sw["fp"], sw["tp"], sw["fp"], sw["fn"], sw["precision"], sw["recall"]))
    print("  Pairs compared: %d. Each later submission is linked once, to its best earlier match: %d linked submissions."
          % (res["n_pairs"], res["links_proposed_n"]))
    print("  Proposed links are confirmed by a reviewer (%.1fh each). Linked submissions where the two sponsors declared different tiers: %d of %d"
          % (LINK_CHECK_H, res["links_split_tier_n"], res["links_proposed_n"]))

    print("\nQUEUE (yellow, modeled; truly high-risk = reference tier 3-4; review time follows the recomputed tier)")
    for line in res["assumptions"]:
        print("  - " + line)
    q = res["queue"]
    print("\n  Same tier-depth review times, different ordering (%d replications):" % REPLICATIONS)
    print("    Tier 3-4 mean wait, first in first out:     %.1f business days  (5th-95th pct %.1f to %.1f)"
          % (q["hi_fifo"], q["hi_fifo_p5"], q["hi_fifo_p95"]))
    print("    Tier 3-4 mean wait, ordered by tier:        %.1f business days  (5th-95th pct %.1f to %.1f)"
          % (q["hi_ordered"], q["hi_ordered_p5"], q["hi_ordered_p95"]))
    print("    Tier 1-2 mean wait, FIFO -> ordered:        %.1f -> %.1f business days   (the cost of ordering)"
          % (q["lo_fifo"], q["lo_ordered"]))
    print("\n  Across the three steps (tier 3-4 mean wait, business days / total reviewer hours / offered load):")
    print("    Step 1 spreadsheet, same review, FIFO:      %5.1f   %6.1fh   %3.0f%%" % (q["hi_before"], q["hours_before"], 100 * q["load_before"]))
    print("    Step 2 declared tier, FIFO:                 %5.1f   %6.1fh   %3.0f%%" % (q["hi_basic"], q["hours_basic"], 100 * q["load_basic"]))
    print("    Step 4 TierGate, ordered by tier:           %5.1f   %6.1fh   %3.0f%%" % (q["hi_ordered"], q["hours_tiergate"], 100 * q["load_tiergate"]))
    print("  TierGate spends more reviewer hours than Step 2 because tier 3-4 cases get the depth their tier calls for.")
    print("\n  Sensitivity to reviewer count (tier-depth hours, so offered load moves):")
    print("    reviewers  load   T3-4 FIFO  T3-4 ordered  T1-2 FIFO  T1-2 ordered")
    for sv in q["sensitivity"]:
        print("    %9d  %3.0f%%  %9.1f  %12.1f  %9.1f  %12.1f"
              % (sv["reviewers"], 100 * sv["offered_load"], sv["hi_fifo"], sv["hi_ordered"], sv["lo_fifo"], sv["lo_ordered"]))
    print("  An aging cap that stops tier 1-2 cases waiting without limit is a design item, not built here.")

    print("\nKNOWN LIMIT LEFT IN ON PURPOSE (green count): form AND catalog both wrong")
    print("  Use cases where the form's data class AND the catalog's recorded class are both below the true class: %d" % res["both_wrong_n"])
    print("    %s" % ", ".join(res["both_wrong_ids"]))
    print("  TierGate takes the higher of the two, so it agrees with the wrong answer. Of these, %d end up at the wrong tier:"
          % res["both_wrong_mis_n"])
    print("    %s" % ", ".join(res["both_wrong_mis_ids"]))
    print("  The data class was the only input with a second source here; there is nothing to disagree with.")
    wrong = [x for x in res["rows"] if x["recomputed"] != x["reference"]]
    print("\n  All %d wrong tiers, by cause (a case can have more than one cause):" % len(wrong))
    for cz, k in sorted(res["cause_counts"].items(), key=lambda kv: (-kv[1], kv[0])):
        print("    %3d  %s" % (k, cz))
    misses = [x for x in wrong if x["reference"] in HI_TIERS and x["recomputed"] not in HI_TIERS]
    print("  True tier 3-4 cases TierGate leaves below tier 3: %d  %s"
          % (len(misses), ", ".join(x["use_case_id"] for x in misses)))

    u = res["utility"]
    print("\nUTILITY = (self-declared error rate - TierGate error rate) x use cases reviewed per year")
    print("  green  self-declared error rate:   %.1f%%   TierGate error rate: %.1f%%   gap: %.1f percentage points"
          % (100 * u["err_declared"], 100 * u["err_tiergate"], 100 * (u["err_declared"] - u["err_tiergate"])))
    print("  yellow annual intake: %.1f submissions per week in this set x 50 weeks = %d per year"
          % (u["per_week"], u["annual_intake"]))
    print("         assumed bank shape: a $50B-asset US retail bank that sees the same intake rate as this set")
    print("  yellow mis-tiered use cases avoided per year: %.1f  (an expected value, so it can be fractional)" % u["avoided_per_year"])
    for sv in u["annual_sensitivity"]:
        print("         at %5d submissions per year: %6.1f" % (sv["intake"], sv["avoided"]))

    # write outputs
    with open(OUT_DIR / "step_04_cases.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["use_case_id", "declared", "recomputed", "reference", "gate", "missing",
                    "flags", "linked_to", "wait_before", "wait_fifo", "wait_ordered"])
        for x in res["rows"]:
            w.writerow([x["use_case_id"], x["declared"], x["recomputed"], x["reference"], x["gate"],
                        " ".join(x["missing"]), " ".join(f["code"] for f in x["flags"]), x["linked_to"],
                        x["wait_before"], x["wait_fifo"], x["wait_ordered"]])
    out = {k: v for k, v in res.items() if k != "hours_per_case"}
    with open(OUT_DIR / "step_04_results.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("\nWrote src/out/step_04_results.json and src/out/step_04_cases.csv")


if __name__ == "__main__":
    main()
