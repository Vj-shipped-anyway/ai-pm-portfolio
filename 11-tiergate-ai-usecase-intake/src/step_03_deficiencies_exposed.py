"""
Step 3 - Where the basic approach breaks: six named deficiencies, each with a count.

  (a) the self-declared tier understates risk
  (b) the data class is never cross-checked against the data catalog
  (c) customer-facing impact is missing or ambiguous on the form
  (d) vendor dependency is not flagged
  (e) overlapping use cases are not linked
  (f) an approval is granted without the evidence the tier requires

All counts are green (measured): printed from the committed synthetic data,
reproducible by running this script. The reference tier is true by construction,
so these counts describe this synthetic set, not real banks.

Run from this folder:  python3 step_03_deficiencies_exposed.py
(it reads the same data as step 2, so run step 2 first only if you want the CSV)

Output:
  - prints the six counts with one worked example each
  - writes src/out/step_03_deficiencies.json
"""

from __future__ import annotations

import json
from collections import defaultdict

from step_01_spreadsheet_fifo import OUT_DIR, load_cases, load_checklist, load_evidence_on_file, read_csv
from step_02_self_declared_tier import evaluate_basic

CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
VENDOR_ORDER = ["none", "self_hosted", "vendor_api"]


def load_catalog() -> dict:
    """dataset_name -> class AS RECORDED in the catalog (the only column a check may read)."""
    return {r["dataset_name"]: r["catalog_class"] for r in read_csv("data_catalog.csv")}


def load_registry() -> dict:
    return {r["use_case_id"]: r["vendor_model"] for r in read_csv("vendor_registry.csv")}


def lvl(x: str) -> int:
    return CLASS_ORDER.index(x)


def case_flags(c: dict, catalog: dict, basic_row: dict) -> dict:
    """Which of the six deficiencies show up on one submission (used by run() and the app)."""
    return {
        "a": c["self_declared_tier"] < c["reference_tier"],
        "b": lvl(c["data_class"]) < lvl(catalog[c["dataset_name"]]),
        "c": c["customer_facing"] in ("", "unsure")
             or (c["customer_facing"] == "no" and c["true_customer_facing"] == "yes"),
        "d": c["true_vendor_model"] != "none" and c["vendor_model"] == "none",
        "e": bool(c["duplicate_group"]),
        "f": bool(basic_row["approved"] and basic_row["missing_reference"]),
    }


def run() -> dict:
    cases = load_cases()
    checklist = load_checklist()
    on_file = load_evidence_on_file()
    catalog = load_catalog()
    registry = load_registry()
    basic = {r["use_case_id"]: r for r in evaluate_basic(cases, checklist, on_file)}
    n = len(cases)
    fl = {c["use_case_id"]: case_flags(c, catalog, basic[c["use_case_id"]]) for c in cases}

    # (a) tier understated
    a_cases = [c for c in cases if fl[c["use_case_id"]]["a"]]
    a_hi = [c for c in a_cases if c["reference_tier"] >= 3]
    a_worst = max(a_cases, key=lambda c: (c["reference_tier"] - c["self_declared_tier"], c["reference_tier"]))

    # (b) data class never compared with the catalog
    b_below_catalog = [c for c in cases if fl[c["use_case_id"]]["b"]]
    b_below_catalog_true = [c for c in b_below_catalog if lvl(c["data_class"]) < lvl(c["true_data_class"])]
    b_below_truth = [c for c in cases if lvl(c["data_class"]) < lvl(c["true_data_class"])]
    b_both_wrong = [c for c in b_below_truth if lvl(catalog[c["dataset_name"]]) < lvl(c["true_data_class"])]
    b_shown = max(b_below_catalog_true,
                  key=lambda c: (lvl(c["true_data_class"]) - lvl(c["data_class"]), c["reference_tier"]))

    # (c) customer-facing impact missing or ambiguous
    c_blank = [c for c in cases if c["customer_facing"] == ""]
    c_unsure = [c for c in cases if c["customer_facing"] == "unsure"]
    c_wrong_no = [c for c in cases if c["customer_facing"] == "no" and c["true_customer_facing"] == "yes"]
    c_all = [c for c in cases if fl[c["use_case_id"]]["c"]]
    c_true_cf = [c for c in c_all if c["true_customer_facing"] == "yes"]
    c_under = [c for c in c_all if c["self_declared_tier"] < c["reference_tier"]]
    c_shown = next(c for c in c_wrong_no if c["self_declared_tier"] < c["reference_tier"])

    # (d) vendor dependency unflagged
    d_true_vendor = [c for c in cases if c["true_vendor_model"] != "none"]
    d_omitted = [c for c in cases if fl[c["use_case_id"]]["d"]]
    d_in_registry = [c for c in d_omitted if c["use_case_id"] in registry]
    d_shown = next(c for c in d_in_registry)

    # (e) overlapping use cases not linked
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        if fl[c["use_case_id"]]["e"]:
            groups[c["duplicate_group"]].append(c)
    e_pairs = sum(len(g) * (len(g) - 1) // 2 for g in groups.values())
    e_cases = sum(len(g) for g in groups.values())
    e_split = [g for g in groups.values() if len({c["self_declared_tier"] for c in g}) > 1]
    e_shown = sorted(groups.values(), key=lambda g: (-len({c["self_declared_tier"] for c in g}), g[0]["use_case_id"]))[0]

    # (f) approval without the evidence the tier requires
    approved = [r for r in basic.values() if r["approved"]]
    f_cases = [r for r in approved if fl[r["use_case_id"]]["f"]]
    f_items = sum(len(r["missing_reference"]) for r in f_cases)
    f_shown = max(f_cases, key=lambda r: len(r["missing_reference"]))

    return {
        "n_cases": n,
        "a": {"n": len(a_cases), "hi_n": len(a_hi), "example": a_worst["use_case_id"],
              "example_declared": a_worst["self_declared_tier"], "example_reference": a_worst["reference_tier"],
              "example_title": a_worst["title"]},
        "b": {"below_catalog_n": len(b_below_catalog), "below_catalog_true_n": len(b_below_catalog_true),
              "below_truth_n": len(b_below_truth), "catalog_also_wrong_n": len(b_both_wrong),
              "compared_by_basic": 0,
              "example": b_shown["use_case_id"], "example_form": b_shown["data_class"],
              "example_catalog": catalog[b_shown["dataset_name"]], "example_dataset": b_shown["dataset_name"],
              "example_true": b_shown["true_data_class"]},
        "c": {"n": len(c_all), "blank_n": len(c_blank), "unsure_n": len(c_unsure),
              "wrong_no_n": len(c_wrong_no), "truly_cf_n": len(c_true_cf), "under_tiered_n": len(c_under),
              "example": c_shown["use_case_id"], "example_title": c_shown["title"]},
        "d": {"true_vendor_n": len(d_true_vendor), "omitted_n": len(d_omitted),
              "in_registry_n": len(d_in_registry), "not_in_registry_n": len(d_omitted) - len(d_in_registry),
              "example": d_shown["use_case_id"], "example_true": d_shown["true_vendor_model"],
              "example_title": d_shown["title"]},
        "e": {"groups_n": len(groups), "pairs_n": e_pairs, "cases_n": e_cases, "linked_by_basic": 0,
              "split_tier_groups_n": len(e_split),
              "example_ids": [c["use_case_id"] for c in e_shown],
              "example_declared": [c["self_declared_tier"] for c in e_shown]},
        "f": {"approved_n": len(approved), "n": len(f_cases), "missing_items_n": f_items,
              "example": f_shown["use_case_id"], "example_missing": f_shown["missing_reference"],
              "example_declared": f_shown["declared"], "example_reference": f_shown["reference"]},
        "flags": fl,
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    r = run()
    n = r["n_cases"]
    print("\n" + "=" * 80)
    print("Step 3 - Six deficiencies of the basic approach (green, measured on %d synthetic submissions)" % n)
    print("=" * 80)

    a, b, c, d, e, f = r["a"], r["b"], r["c"], r["d"], r["e"], r["f"]

    print("\n(a) SELF-DECLARED TIER UNDERSTATES RISK")
    print("    %d of %d declared tiers sit below the reference tier; %d of those are cases that are truly tier 3-4."
          % (a["n"], n, a["hi_n"]))
    print("    Example %s: declared tier %d, reference tier %d  (%s)"
          % (a["example"], a["example_declared"], a["example_reference"], a["example_title"]))

    print("\n(b) DATA CLASS NEVER CROSS-CHECKED AGAINST THE CATALOG")
    print("    Comparisons run against the catalog by the basic approach: %d" % b["compared_by_basic"])
    print("    %d forms declare a class below the one the catalog records; %d of those are real understatements."
          % (b["below_catalog_n"], b["below_catalog_true_n"]))
    print("    %d forms declare a class below the TRUE class in total; on %d of those the catalog is below the true class too."
          % (b["below_truth_n"], b["catalog_also_wrong_n"]))
    print("    Example %s: form says %s, catalog says %s for %s, true class %s"
          % (b["example"], b["example_form"], b["example_catalog"], b["example_dataset"], b["example_true"]))

    print("\n(c) CUSTOMER-FACING IMPACT MISSING OR AMBIGUOUS")
    print("    %d forms are unusable or wrong on this field: %d blank, %d 'unsure', %d say 'no' on a truly customer-facing case."
          % (c["n"], c["blank_n"], c["unsure_n"], c["wrong_no_n"]))
    print("    %d of those are truly customer-facing; %d ended up declared below their reference tier."
          % (c["truly_cf_n"], c["under_tiered_n"]))
    print("    Example %s: says 'no'; %s" % (c["example"], c["example_title"]))

    print("\n(d) VENDOR DEPENDENCY UNFLAGGED")
    print("    %d of %d use cases truly depend on a vendor or self-hosted model; %d of those say 'none' on the form."
          % (d["true_vendor_n"], n, d["omitted_n"]))
    print("    The vendor registry already lists %d of those %d; the basic approach never reads it."
          % (d["in_registry_n"], d["omitted_n"]))
    print("    Example %s: form says none, true %s  (%s)" % (d["example"], d["example_true"], d["example_title"]))

    print("\n(e) OVERLAPPING USE CASES NOT LINKED")
    print("    %d duplicate groups (%d submissions, %d true pairs); linked by the spreadsheet: %d."
          % (e["groups_n"], e["cases_n"], e["pairs_n"], e["linked_by_basic"]))
    print("    %d groups carry different declared tiers for the same underlying use case."
          % e["split_tier_groups_n"])
    print("    Example group: %s with declared tiers %s"
          % (", ".join(e["example_ids"]), ", ".join(str(t) for t in e["example_declared"])))

    print("\n(f) APPROVAL WITHOUT THE EVIDENCE THE TIER REQUIRES")
    print("    %d of %d approvals are missing evidence that the reference tier requires (%d required items absent)."
          % (f["n"], f["approved_n"], f["missing_items_n"]))
    print("    Example %s: approved at declared tier %d, reference tier %d, missing %s"
          % (f["example"], f["example_declared"], f["example_reference"], ", ".join(f["example_missing"])))

    print("\nSUMMARY")
    print("    (a) %3d   (b) %3d   (c) %3d   (d) %3d   (e) %3d groups   (f) %3d"
          % (a["n"], b["below_catalog_n"], c["n"], d["omitted_n"], e["groups_n"], f["n"]))

    with open(OUT_DIR / "step_03_deficiencies.json", "w") as fh:
        json.dump(r, fh, indent=2)
    print("\nWrote src/out/step_03_deficiencies.json")


if __name__ == "__main__":
    main()
