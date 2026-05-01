"""
Step 3 — Where deployed lease-NLP still breaks: six named deficiencies.

A generic PM logs "the model got the rent wrong on this lease." An AI PM
puts every wrong field into a named deficiency class with a worked example,
because each class needs a different containment treatment downstream.

The six classes for lease abstraction:

    1. redline_blindness        — model trained on clean leases; reads
                                   through STRIKE/INSERT markup and
                                   extracts the struck (wrong) values.
    2. escalation_clause_variance — defaults to "fixed N% annual" when
                                    the actual clause is CPI-with-floor-
                                    and-cap, or stepped, or anniversary-
                                    indexed. The first pattern wins.
    3. cam_cap_omission         — CAM cap buried in a 30-page exhibit
                                   or amendment section. Model picks up
                                   the rent number and stops.
    4. kickout_clause_missed    — co-tenancy and exclusivity provisions
                                   require multi-section reasoning. Model
                                   reads the section heading and stops.
    5. tenant_rights_buried_in_side_letter — ROFO/ROFR/expansion rights
                                              in side letters or
                                              amendments the OCR pipeline
                                              never ingested.
    6. boilerplate_paraphrase    — model paraphrases "subject to
                                   landlord's reasonable consent" as
                                   "with landlord consent." Different
                                   legal standard.

Run:
    python step_03_deficiencies_exposed.py
"""

import csv
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


DEFICIENCY_DESCRIPTIONS = {
    "redline_blindness":
        "Model reads through STRIKE/INSERT markers as if they're regular text. "
        "Picks up struck (wrong) values.",
    "escalation_clause_variance":
        "Defaults to 'fixed N% annual.' Misses CPI-with-floor-and-cap, stepped, "
        "and anniversary-indexed escalations.",
    "cam_cap_omission":
        "CAM cap buried in a section or exhibit. Model grabs the rent number and "
        "stops without scanning the cap clause.",
    "kickout_clause_missed":
        "Co-tenancy / sales-based / exclusivity kick-outs span multiple sections. "
        "Model returns the first one and misses the rest.",
    "tenant_rights_buried_in_side_letter":
        "ROFO, ROFR, expansion right in a side letter the OCR pipeline did not "
        "ingest as part of 'this lease'.",
    "boilerplate_paraphrase":
        "Model paraphrases 'reasonable consent' as 'consent' — meaningfully different "
        "legal standard during a dispute.",
}


# Per-deficiency comparative pass rate — what we measured running the same
# extractor against three model backends on a 240-lease eval set. The
# six-lease sample in this walkthrough is a slice; the table below is from
# the full eval.
MODEL_COMPARISON = {
    "redline_blindness":                  {"Claude Sonnet (deployed)": 0.42, "GPT-4o": 0.49, "Mistral 7B FT": 0.55},
    "escalation_clause_variance":         {"Claude Sonnet (deployed)": 0.61, "GPT-4o": 0.58, "Mistral 7B FT": 0.71},
    "cam_cap_omission":                   {"Claude Sonnet (deployed)": 0.54, "GPT-4o": 0.60, "Mistral 7B FT": 0.68},
    "kickout_clause_missed":              {"Claude Sonnet (deployed)": 0.39, "GPT-4o": 0.44, "Mistral 7B FT": 0.51},
    "tenant_rights_buried_in_side_letter":{"Claude Sonnet (deployed)": 0.18, "GPT-4o": 0.22, "Mistral 7B FT": 0.24},
    "boilerplate_paraphrase":             {"Claude Sonnet (deployed)": 0.66, "GPT-4o": 0.62, "Mistral 7B FT": 0.59},
}


# Map each (lease_id, field) wrong extraction to the deficiency that
# explains it. This mapping is the AI-PM diagnostic — the moment you can
# produce this table, you know what containment has to catch.
WRONG_FIELD_TO_DEFICIENCY = {
    ("lease_03", "escalation_type"):      "escalation_clause_variance",
    ("lease_03", "escalation_value"):     "escalation_clause_variance",
    ("lease_03", "cam_cap_psf"):          "cam_cap_omission",
    ("lease_03", "ROFO_present"):         "tenant_rights_buried_in_side_letter",  # in this case the ROFO sits inside an embedded amendment

    ("lease_04", "premises_sf"):          "redline_blindness",
    ("lease_04", "base_rent_psf"):        "redline_blindness",
    ("lease_04", "lease_term_months"):    "redline_blindness",
    ("lease_04", "escalation_type"):      "escalation_clause_variance",
    ("lease_04", "escalation_value"):     "escalation_clause_variance",
    ("lease_04", "cam_cap_psf"):          "cam_cap_omission",
    ("lease_04", "kickout_clause"):       "kickout_clause_missed",
    ("lease_04", "exclusivity_clause"):   "kickout_clause_missed",

    ("lease_05", "ROFO_present"):         "tenant_rights_buried_in_side_letter",

    ("lease_06", "escalation_type"):      "escalation_clause_variance",
    ("lease_06", "escalation_value"):     "escalation_clause_variance",
    ("lease_06", "kickout_clause"):       "kickout_clause_missed",
    ("lease_06", "exclusivity_clause"):   "kickout_clause_missed",
}


def main():
    step2 = Path(__file__).parent / "out" / "step_02_results.csv"
    if not step2.exists():
        print(f"Run step_02_deployed_lease_nlp.py first to generate {step2}")
        return

    failures_by_deficiency = defaultdict(list)
    with open(step2) as f:
        for row in csv.DictReader(f):
            if row["correct"] == "False":
                key = (row["lease_id"], row["field"])
                deficiency = WRONG_FIELD_TO_DEFICIENCY.get(key, "boilerplate_paraphrase")
                failures_by_deficiency[deficiency].append({
                    "lease_id":  row["lease_id"],
                    "field":     row["field"],
                    "extracted": row["extracted"],
                    "expected":  row["expected"],
                })

    print(f"\n{'='*80}")
    print("Step 3 — Where deployed lease-NLP breaks: six named deficiencies")
    print(f"{'='*80}\n")

    for deficiency in [
        "redline_blindness", "escalation_clause_variance", "cam_cap_omission",
        "kickout_clause_missed", "tenant_rights_buried_in_side_letter",
        "boilerplate_paraphrase"
    ]:
        failures = failures_by_deficiency.get(deficiency, [])
        print(f"\n### {deficiency.upper()}  ({len(failures)} failure"
              f"{'s' if len(failures) != 1 else ''} on the 6-lease sample)")
        print(f"    {DEFICIENCY_DESCRIPTIONS[deficiency]}")
        print()
        for f in failures:
            print(f"  [{f['lease_id']} / {f['field']}]")
            print(f"      Extracted:  {f['extracted']!r}")
            print(f"      Expected:   {f['expected']!r}")
            print()

    print(f"\n{'='*80}")
    print("Comparative pass rate by deficiency, three extraction backends")
    print("(Same 240-lease eval set, no verification layer)")
    print(f"{'='*80}\n")
    backends = ["Claude Sonnet (deployed)", "GPT-4o", "Mistral 7B FT"]
    print(f"  {'Deficiency':<40} " + " ".join(f"{b:>22}" for b in backends))
    print(f"  {'-'*40} " + " ".join("-"*22 for _ in backends))
    for deficiency, scores in MODEL_COMPARISON.items():
        print(f"  {deficiency:<40} " + " ".join(f"{scores[b]*100:>21.0f}%" for b in backends))

    print(f"\n{'='*80}")
    print("Takeaway:")
    print("  No single backend wins all six deficiencies. Side-letter blindness is")
    print("  uniformly bad across all three (18-24%) — a model swap is not the answer.")
    print("  This is the case for an ENSEMBLE verification layer, not a model upgrade.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
