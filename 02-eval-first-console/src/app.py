"""
Eval-First Console for Regulated AI — Streamlit Prototype
Author: Vijay Saharan
Run: streamlit run app.py

Demonstrates the three-loop eval surface (Author -> Run -> Detect)
across three deployed GenAI use cases (loan-officer Q&A, fraud explainer,
advisor research) with two vendor model versions and slice-level cuts.
Synthetic data only.
"""

import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# Synthetic eval results — three use cases x two vendor versions x slices
# -----------------------------------------------------------------------------

np.random.seed(7)

USE_CASES = {
    "loan_officer_qa": {
        "label": "Loan Officer Q&A",
        "rubrics": ["policy_accuracy", "citation_correctness", "tone_compliant"],
        "slices": ["commercial", "retail", "small_business"],
    },
    "fraud_explainer": {
        "label": "Fraud Decision Explainer",
        "rubrics": ["explanation_faithfulness", "reg_b_compliant", "actionability"],
        "slices": ["card_present", "card_not_present", "wire", "ach"],
    },
    "advisor_research": {
        "label": "Advisor Research Brief",
        "rubrics": ["factuality", "source_attribution", "no_advice_overreach"],
        "slices": ["fixed_income", "equities", "alternatives"],
    },
}

VENDOR_VERSIONS = ["v_2026_01_15 (pinned)", "v_2026_03_02 (silent update)"]


def gen_eval_results():
    rows = []
    base_date = datetime(2026, 1, 15)
    for uc_key, uc in USE_CASES.items():
        for v_idx, version in enumerate(VENDOR_VERSIONS):
            for rubric in uc["rubrics"]:
                for slice_name in uc["slices"]:
                    # Baseline score per rubric/slice
                    base = np.random.uniform(0.78, 0.94)
                    # Slice-level penalty for under-represented segments
                    if slice_name in ("commercial", "wire", "alternatives"):
                        base -= np.random.uniform(0.06, 0.18)
                    # Silent-update version causes regression on specific rubrics
                    if v_idx == 1:
                        if rubric in ("citation_correctness", "explanation_faithfulness", "factuality"):
                            base -= np.random.uniform(0.08, 0.16)
                    score = float(np.clip(base, 0.0, 1.0))
                    n = int(np.random.randint(80, 240))
                    rows.append({
                        "use_case": uc_key,
                        "use_case_label": uc["label"],
                        "vendor_version": version,
                        "rubric": rubric,
                        "slice": slice_name,
                        "score": round(score, 3),
                        "n": n,
                        "run_date": base_date + timedelta(days=v_idx * 45),
                    })
    return pd.DataFrame(rows)


def coverage_map():
    """Synthetic coverage state — what isn't tested is as loud as what fails."""
    return pd.DataFrame([
        {"use_case": "loan_officer_qa", "rubric_count": 3, "slices_covered": 3, "slices_total": 3, "rubric_age_days": 8, "vendor_pinned": True},
        {"use_case": "fraud_explainer", "rubric_count": 3, "slices_covered": 3, "slices_total": 4, "rubric_age_days": 41, "vendor_pinned": True},
        {"use_case": "advisor_research", "rubric_count": 3, "slices_covered": 2, "slices_total": 3, "rubric_age_days": 92, "vendor_pinned": False},
        {"use_case": "kyc_narrative", "rubric_count": 0, "slices_covered": 0, "slices_total": 5, "rubric_age_days": None, "vendor_pinned": False},
        {"use_case": "wealth_intake", "rubric_count": 0, "slices_covered": 0, "slices_total": 4, "rubric_age_days": None, "vendor_pinned": False},
    ])


# -----------------------------------------------------------------------------
# Regression detection — Loop 3
# -----------------------------------------------------------------------------

def detect_regressions(df, threshold=0.05):
    pivot = df.pivot_table(
        index=["use_case", "rubric", "slice"],
        columns="vendor_version",
        values="score",
    ).reset_index()
    pinned, updated = VENDOR_VERSIONS[0], VENDOR_VERSIONS[1]
    pivot["delta"] = pivot[updated] - pivot[pinned]
    pivot["regression"] = pivot["delta"] < -threshold
    return pivot


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

st.set_page_config(page_title="Eval-First Console for Regulated AI", layout="wide")
st.title("Eval-First Console for Regulated AI")
st.caption("Project 02 · BFSI · AI Platform · Sr PM portfolio — Vijay Saharan")

with st.sidebar:
    st.header("Loops")
    st.markdown("**Author -> Run -> Detect**")
    use_case = st.selectbox("Use case", list(USE_CASES.keys()), format_func=lambda k: USE_CASES[k]["label"])
    st.divider()
    st.caption("Synthetic eval results across two vendor versions. Silent update on 2026-03-02.")

results = gen_eval_results()
uc_results = results[results["use_case"] == use_case]

st.subheader(f"Use case: {USE_CASES[use_case]['label']}")

# Loop 1 — Author / Coverage
st.markdown("### Loop 1 - Author (rubric + slice coverage)")
cov = coverage_map()
cov["coverage_pct"] = (cov["slices_covered"] / cov["slices_total"] * 100).round(0)
cov["status"] = cov.apply(
    lambda r: "MISSING - no rubric" if r["rubric_count"] == 0
    else ("STALE - rubric > 90d" if (r["rubric_age_days"] or 0) > 90
          else ("OK" if r["coverage_pct"] == 100 and r["vendor_pinned"] else "WATCH")),
    axis=1,
)
st.dataframe(
    cov[["use_case", "rubric_count", "coverage_pct", "rubric_age_days", "vendor_pinned", "status"]],
    use_container_width=True,
)
st.caption("Coverage gaps are first-class. What isn't tested is reported as loud as what failed.")

# Loop 2 — Run results
st.markdown("### Loop 2 - Run (rubric x slice x vendor version)")
pivot_view = uc_results.pivot_table(
    index=["rubric", "slice"],
    columns="vendor_version",
    values="score",
).reset_index()
st.dataframe(pivot_view, use_container_width=True)

# Loop 3 — Detect regressions
st.markdown("### Loop 3 - Detect (regression flagger)")
regressions = detect_regressions(uc_results)
st.dataframe(
    regressions[["rubric", "slice", VENDOR_VERSIONS[0], VENDOR_VERSIONS[1], "delta", "regression"]],
    use_container_width=True,
)

reg_count = int(regressions["regression"].sum())
if reg_count == 0:
    st.success(f"No regressions > 5pts across {len(regressions)} (rubric x slice) cells.")
else:
    st.error(
        f"{reg_count} regression(s) detected on silent vendor update. "
        f"Recommended: ROLLBACK to pinned version {VENDOR_VERSIONS[0]}; route to MRM."
    )

# Headline rollup
st.markdown("### Fleet rollup")
fleet = (
    results.groupby(["use_case_label", "vendor_version"])["score"]
    .mean()
    .reset_index()
    .pivot(index="use_case_label", columns="vendor_version", values="score")
    .round(3)
)
fleet["delta"] = (fleet[VENDOR_VERSIONS[1]] - fleet[VENDOR_VERSIONS[0]]).round(3)
st.dataframe(fleet, use_container_width=True)

with st.expander("Eval evidence bundle (auto-assembled)"):
    st.json({
        "use_case": use_case,
        "rubrics_run": USE_CASES[use_case]["rubrics"],
        "slices_run": USE_CASES[use_case]["slices"],
        "vendor_versions": VENDOR_VERSIONS,
        "regressions_detected": reg_count,
        "recommendation": "ROLLBACK to pinned" if reg_count else "RETAIN",
        "rubric_attestation": "compliance_l2 + sme_l1",
        "audit_trail_event_id": "evt_eval_2026_03_02_0001",
        "evidence_assembled_in_seconds": 0.6,
    })

st.divider()
st.caption(
    "Prototype demonstrates the product mechanic. In production: LLM-as-judge with "
    "weekly SME calibration, vendor-snapshot pinning, and per-use-case eval budgets. "
    "Interlocks with Project 01 (Drift Sentinel) and Project 08 (Audit Trail)."
)
