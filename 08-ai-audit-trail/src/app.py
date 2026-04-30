"""
AI Audit Trail & Decision Lineage — Streamlit Prototype
Author: Vijay Saharan
Run: streamlit run app.py

Demonstrates a queryable, immutable decision-lineage layer over a synthetic
store of 50,000 decisions across four deployed models. Filter, drill into a
single decision, and export a one-click audit pack.
"""

import hashlib
import json
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# Synthetic lineage store — 50,000 decisions across 4 deployed models
# -----------------------------------------------------------------------------

np.random.seed(11)
random.seed(11)

MODELS = {
    "credit_ml_v3":        {"vendor": "internal", "snapshot": "2025-11-04-a3f9", "tier": 1},
    "fraud_ml_v7":         {"vendor": "internal", "snapshot": "2026-01-12-77c1", "tier": 1},
    "aml_ml_v4":           {"vendor": "internal", "snapshot": "2025-09-22-b042", "tier": 1},
    "advisor_genai_v2":    {"vendor": "anthropic", "snapshot": "claude-sonnet-2025-10-22", "tier": 1},
}
OUTCOMES = ["approved", "denied", "escalated", "settled", "disputed", "paid", "charged_off"]
ACTIONS  = ["auto_approve", "auto_deny", "route_to_human", "request_docs", "freeze"]


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


@st.cache_data(show_spinner=False)
def gen_lineage_store(n=50_000):
    rows = []
    base = datetime(2025, 6, 1)
    for i in range(n):
        model = random.choice(list(MODELS.keys()))
        meta = MODELS[model]
        ts = base + timedelta(seconds=int(np.random.uniform(0, 300 * 24 * 3600)))
        cust = f"cust_{np.random.randint(10_000, 99_999)}"
        prompt = f"decision_request::{model}::{cust}::{i}"
        retrieval = [_hash(f"chunk_{model}_{j}_{i % 200}") for j in range(np.random.randint(0, 4))]
        action = random.choice(ACTIONS)
        outcome = random.choice(OUTCOMES) if np.random.rand() < 0.7 else None
        reviewer = f"rev_{np.random.randint(100, 199)}" if action == "route_to_human" else None
        confidence = float(np.clip(np.random.beta(8, 2), 0, 1))
        complete = (
            np.random.rand() > 0.02
            and (model != "advisor_genai_v2" or len(retrieval) > 0)
        )
        rows.append({
            "decision_id": _hash(f"{i}-{model}-{ts}"),
            "timestamp": ts,
            "customer_id": cust,
            "model": model,
            "model_version": meta["snapshot"],
            "vendor": meta["vendor"],
            "tier": meta["tier"],
            "prompt_hash": _hash(prompt),
            "retrieval_chunks": retrieval,
            "tool_calls": np.random.randint(0, 3),
            "confidence": round(confidence, 3),
            "action": action,
            "reviewer_id": reviewer,
            "outcome": outcome,
            "lineage_complete": complete,
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
    return df


# -----------------------------------------------------------------------------
# Audit pack assembly
# -----------------------------------------------------------------------------

def assemble_audit_pack(record: dict) -> dict:
    pack = {
        "audit_pack_id": _hash(f"pack-{record['decision_id']}"),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "decision": record,
        "lineage": {
            "training_run_id": f"train_{record['model']}_2025-q4",
            "attestation_id":  f"attest_{record['model']}_{record['model_version']}",
            "feature_store_snapshot": "fs_2026-04-01",
            "system_prompt_hash": _hash(f"sysprompt::{record['model']}"),
        },
        "merkle_anchor": {
            "daily_root": _hash(str(record["timestamp"].date())),
            "anchored_to": "write_once_store://anchor/2026/04",
        },
        "signatures": {
            "ledger_signed_at": datetime.utcnow().isoformat() + "Z",
            "signer": "lineage-ledger-prod",
        },
    }
    return pack


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

st.set_page_config(page_title="AI Audit Trail & Decision Lineage", layout="wide")
st.title("AI Audit Trail & Decision Lineage")
st.caption("Project 08 · BFSI · Compliance · Sr PM portfolio — Vijay Saharan")

df = gen_lineage_store()

with st.sidebar:
    st.header("Query")
    model_filter = st.multiselect("Model", list(MODELS.keys()), default=list(MODELS.keys()))
    cust_q = st.text_input("Customer ID contains", "")
    outcome_filter = st.multiselect("Outcome", OUTCOMES, default=[])
    only_incomplete = st.checkbox("Only lineage-incomplete records", value=False)
    st.divider()
    st.caption(f"Store: {len(df):,} decisions · 4 models · 300-day window")

# Filter
view = df[df["model"].isin(model_filter)]
if cust_q:
    view = view[view["customer_id"].str.contains(cust_q, case=False)]
if outcome_filter:
    view = view[view["outcome"].isin(outcome_filter)]
if only_incomplete:
    view = view[~view["lineage_complete"]]

# Top metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Decisions in view", f"{len(view):,}")
c2.metric("Lineage completeness", f"{(view['lineage_complete'].mean() * 100 if len(view) else 0):.2f}%")
c3.metric("Models", view["model"].nunique())
c4.metric("Median latency to evidence", "12 min", "vs 14d baseline")

st.markdown("### Decision ledger (most recent 500)")
st.dataframe(
    view.head(500)[["decision_id", "timestamp", "customer_id", "model",
                    "model_version", "action", "outcome", "lineage_complete"]],
    use_container_width=True, height=320,
)

# Drill-in
st.markdown("### Drill into decision")
if len(view) == 0:
    st.info("No decisions match this filter.")
    st.stop()

choice = st.selectbox("decision_id", view.head(500)["decision_id"].tolist())
record = view[view["decision_id"] == choice].iloc[0].to_dict()
record["timestamp"] = record["timestamp"].isoformat()

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Inputs & model**")
    st.json({k: record[k] for k in ["decision_id", "timestamp", "customer_id",
                                     "model", "model_version", "vendor", "tier",
                                     "prompt_hash", "retrieval_chunks", "tool_calls"]})
with c2:
    st.markdown("**Outputs & downstream**")
    st.json({k: record[k] for k in ["confidence", "action", "reviewer_id",
                                     "outcome", "lineage_complete"]})

# Audit pack
st.markdown("### One-click audit pack")
if st.button("Assemble audit pack", type="primary"):
    pack = assemble_audit_pack(record)
    st.success(f"Audit pack {pack['audit_pack_id']} assembled in 0.3s.")
    st.download_button(
        "Download audit pack (JSON)",
        data=json.dumps(pack, indent=2, default=str),
        file_name=f"audit_pack_{pack['audit_pack_id']}.json",
        mime="application/json",
    )
    with st.expander("Pack contents"):
        st.json(pack)

st.divider()
st.caption(
    "Prototype demonstrates the product mechanic. In production: append-only "
    "event bus, Merkle-anchored ledger to a write-once store, columnar warm "
    "tier, and OpenTelemetry trace correlation. Interlocks with Project 01 "
    "(Drift Sentinel) and Project 07 (HITL Decision Surface)."
)
