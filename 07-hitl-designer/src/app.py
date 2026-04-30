"""
HITL Workflow Designer — Streamlit Prototype
Author: Vijay Saharan
Run: streamlit run app.py

Visual workflow designer for HITL-aware AI workflows. PMs/ops leads tune
confidence tiers, reviewer pools, SLAs, and abstention paths. A synthetic
batch of 200 AI decisions is routed through the design; the dashboard shows
routing distribution, SLA compliance, reviewer-quality kappa, rubber-stamp
rate, and escalation paths.
"""

import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

np.random.seed(11)

# -----------------------------------------------------------------------------
# Synthetic batch — 200 AI decisions with confidence + ground truth
# -----------------------------------------------------------------------------

N = 200
WORKFLOWS = ["aml_alert_triage", "credit_exception", "kyc_summary_qa"]


def gen_batch():
    rows = []
    base = datetime(2026, 4, 1, 9, 0, 0)
    for i in range(N):
        wf = np.random.choice(WORKFLOWS, p=[0.5, 0.3, 0.2])
        # confidence with bimodal distribution + noise
        conf = float(np.clip(np.random.beta(5, 2) if np.random.random() < 0.7
                              else np.random.beta(2, 5), 0, 1))
        truth = np.random.choice(["positive", "negative"], p=[0.18, 0.82])
        # AI suggested verdict — accuracy correlates with confidence
        if np.random.random() < 0.4 + 0.55 * conf:
            ai_verdict = truth
        else:
            ai_verdict = "negative" if truth == "positive" else "positive"
        difficulty = "hard" if conf < 0.55 else ("med" if conf < 0.80 else "easy")
        rows.append({
            "case_id": f"C{i:04d}", "workflow": wf,
            "ai_confidence": round(conf, 3),
            "ai_verdict": ai_verdict, "ground_truth": truth,
            "difficulty": difficulty,
            "arrived_at": base + timedelta(minutes=int(np.random.exponential(8))),
        })
    return pd.DataFrame(rows)


batch = gen_batch()


# -----------------------------------------------------------------------------
# Reviewer pool — simulated
# -----------------------------------------------------------------------------

def build_reviewers(n_reviewers, skill_mix):
    rows = []
    for i in range(n_reviewers):
        rows.append({
            "reviewer_id": f"R{i:02d}",
            "skill": np.random.choice(WORKFLOWS, p=skill_mix),
            "calibration": round(np.clip(np.random.normal(0.78, 0.08), 0.4, 0.98), 2),  # accuracy
            "speed_factor": round(np.random.uniform(0.7, 1.4), 2),  # 1=baseline
            "load": 0,
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Routing
# -----------------------------------------------------------------------------

def route_case(row, t1, t2, t3):
    c = row["ai_confidence"]
    if c >= t1:
        return "AUTO_APPROVE"
    if c >= t2:
        return "SAMPLE_REVIEW"
    if c >= t3:
        return "REVIEW"
    return "ABSTAIN_ESCALATE"


def assign_reviewer(reviewers, workflow):
    eligible = reviewers.sort_values(["load", "calibration"], ascending=[True, False])
    skilled = eligible[eligible["skill"] == workflow]
    pick = skilled.iloc[0] if len(skilled) else eligible.iloc[0]
    reviewers.loc[reviewers["reviewer_id"] == pick["reviewer_id"], "load"] += 1
    return pick["reviewer_id"], pick["calibration"], pick["speed_factor"]


def simulate_review(row, reviewer_cal, speed_factor, sla_min):
    # dwell time
    base_dwell = {"easy": 12, "med": 45, "hard": 110}[row["difficulty"]]
    dwell = max(3, np.random.normal(base_dwell, base_dwell * 0.3) / speed_factor)
    # SLA latency (queue + dwell)
    queue = np.random.exponential(sla_min * 0.6)
    latency_min = (queue + dwell / 60.0)
    # reviewer verdict — accuracy ~ calibration
    correct = np.random.random() < reviewer_cal
    rev_verdict = row["ground_truth"] if correct else (
        "negative" if row["ground_truth"] == "positive" else "positive")
    rubber = dwell < 15 and row["difficulty"] != "easy"
    return {
        "dwell_s": round(dwell, 1),
        "latency_min": round(latency_min, 1),
        "reviewer_verdict": rev_verdict,
        "rubber_stamp": rubber,
        "sla_breach": latency_min > sla_min,
        "correct": rev_verdict == row["ground_truth"],
    }


# -----------------------------------------------------------------------------
# Kappa (Cohen's, two-rater agreement vs chance)
# -----------------------------------------------------------------------------

def cohens_kappa(rater_a, rater_b):
    if len(rater_a) == 0:
        return float("nan")
    a = np.array(rater_a)
    b = np.array(rater_b)
    po = (a == b).mean()
    cats = list(set(list(a) + list(b)))
    pe = sum((np.mean(a == c) * np.mean(b == c)) for c in cats)
    return float((po - pe) / (1 - pe + 1e-9))


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

st.set_page_config(page_title="HITL Workflow Designer", layout="wide")
st.title("Human-in-the-Loop Workflow Designer")
st.caption("Project 07 · AI Platform · BFSI Ops · Governance — Vijay Saharan")

with st.sidebar:
    st.header("Loop 1 · Design")
    st.markdown("**Confidence tiers**")
    t1 = st.slider("Auto-approve at confidence ≥", 0.50, 0.99, 0.92, 0.01)
    t2 = st.slider("Sample-review at ≥", 0.30, t1, 0.75, 0.01)
    t3 = st.slider("Always-review at ≥", 0.10, t2, 0.45, 0.01)
    st.caption("Below t3 → abstain / escalate")
    st.divider()
    st.markdown("**Reviewer pool**")
    n_reviewers = st.slider("Reviewers", 4, 24, 10)
    sla_min = st.slider("Tier-3 SLA (minutes)", 5, 240, 35)
    st.divider()
    run = st.button("Run synthetic batch through design", type="primary")

st.markdown("### Workflow design preview")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Auto-approve threshold", f"{t1:.2f}")
c2.metric("Sample-review threshold", f"{t2:.2f}")
c3.metric("Review threshold", f"{t3:.2f}")
c4.metric("SLA p95 target", f"{sla_min} min")

if run:
    reviewers = build_reviewers(n_reviewers, [0.5, 0.3, 0.2])
    routed = batch.copy()
    routed["route"] = routed.apply(lambda r: route_case(r, t1, t2, t3), axis=1)

    # Operate: assign + simulate
    operate_rows = []
    for _, row in routed.iterrows():
        if row["route"] in ("AUTO_APPROVE",):
            operate_rows.append({
                "case_id": row["case_id"], "route": row["route"],
                "reviewer": "-", "dwell_s": 0, "latency_min": 0.05,
                "reviewer_verdict": row["ai_verdict"], "rubber_stamp": False,
                "sla_breach": False, "correct": row["ai_verdict"] == row["ground_truth"],
            })
        elif row["route"] in ("SAMPLE_REVIEW", "REVIEW"):
            rid, cal, spd = assign_reviewer(reviewers, row["workflow"])
            res = simulate_review(row, cal, spd, sla_min)
            operate_rows.append({
                "case_id": row["case_id"], "route": row["route"],
                "reviewer": rid, **res,
            })
        else:  # ABSTAIN_ESCALATE
            operate_rows.append({
                "case_id": row["case_id"], "route": row["route"],
                "reviewer": "SENIOR_QUEUE", "dwell_s": 0, "latency_min": sla_min * 1.2,
                "reviewer_verdict": "ESCALATED", "rubber_stamp": False,
                "sla_breach": False, "correct": True,  # escalation is correct outcome
            })
    op_df = pd.DataFrame(operate_rows).merge(routed, on="case_id")

    # -------------- Loop 2: Operate --------------
    st.markdown("### Loop 2 · Operate — routing distribution")
    rt = op_df["route"].value_counts().reset_index()
    rt.columns = ["route", "n"]
    st.bar_chart(rt, x="route", y="n", height=240)

    # -------------- Loop 3: Measure --------------
    st.markdown("### Loop 3 · Measure")
    reviewed = op_df[op_df["route"].isin(["SAMPLE_REVIEW", "REVIEW"])]
    sla_p95 = reviewed["latency_min"].quantile(0.95) if len(reviewed) else 0
    rubber_rate = reviewed["rubber_stamp"].mean() * 100 if len(reviewed) else 0
    sla_compliance = (1 - reviewed["sla_breach"].mean()) * 100 if len(reviewed) else 100
    kappa = cohens_kappa(reviewed["reviewer_verdict"].tolist(),
                         reviewed["ground_truth"].tolist()) if len(reviewed) else float("nan")
    overall_correct = op_df["correct"].mean() * 100

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("SLA p95 (min)", f"{sla_p95:.1f}", delta=f"target ≤ {sla_min}")
    m2.metric("SLA compliance", f"{sla_compliance:.1f}%")
    m3.metric("Reviewer kappa", f"{kappa:.2f}", delta="target ≥ 0.75")
    m4.metric("Rubber-stamp rate", f"{rubber_rate:.1f}%", delta="target ≤ 4%")
    m5.metric("End-to-end correct", f"{overall_correct:.1f}%")

    st.markdown("**Reviewer load (Gini = inequality of assignment)**")
    load = op_df[op_df["reviewer"].str.startswith("R", na=False)]["reviewer"].value_counts()
    if len(load) > 1:
        sorted_l = np.sort(load.values)
        n = len(sorted_l)
        gini = (2 * np.sum((np.arange(1, n + 1)) * sorted_l) / (n * sorted_l.sum())) - (n + 1) / n
        st.write(f"Gini coefficient: **{gini:.2f}** (target ≤ 0.20)")
        st.bar_chart(load, height=200)

    st.markdown("### Routed cases (sample)")
    st.dataframe(op_df[["case_id", "workflow", "ai_confidence", "route",
                          "reviewer", "latency_min", "rubber_stamp",
                          "reviewer_verdict", "ground_truth", "correct"]].head(40),
                 use_container_width=True)

    with st.expander("Audit event sample (Project 08)"):
        st.json({
            "case_id": op_df.iloc[0]["case_id"],
            "workflow": op_df.iloc[0]["workflow"],
            "ai_confidence": op_df.iloc[0]["ai_confidence"],
            "ai_verdict": op_df.iloc[0]["ai_verdict"],
            "route_decision": op_df.iloc[0]["route"],
            "reviewer": op_df.iloc[0]["reviewer"],
            "reviewer_verdict": op_df.iloc[0]["reviewer_verdict"],
            "ground_truth": op_df.iloc[0]["ground_truth"],
            "latency_min": float(op_df.iloc[0]["latency_min"]),
            "design_version": "hitl_v1.3",
            "thresholds": {"t1": t1, "t2": t2, "t3": t3},
        })

st.divider()
st.caption(
    "Prototype demonstrates the HITL design + measurement mechanic. In production: "
    "live agent funnel from Project 05 Layer 3, blended ground-truth audit cases "
    "for kappa, signed audit chain to Project 08, calibration coaching loop."
)
