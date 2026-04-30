"""
Hallucination Containment for Bank Chatbots — Streamlit Prototype
Author: Vijay Saharan
Run: streamlit run app.py

Demonstrates the three-guard containment layer (Ground -> Abstain -> Probe)
wrapped around a synthetic bank chatbot. Toggle containment on/off. Inject
hallucination-prone queries. Watch the rolling hallucination rate move.
Synthetic data only.
"""

import re
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime

# -----------------------------------------------------------------------------
# Authoritative knowledge graph (synthetic source of truth)
# -----------------------------------------------------------------------------

KG = {
    "savings_apy": {"value": "4.10%", "as_of": "2026-04-15", "reg": "Reg DD"},
    "checking_apy": {"value": "0.05%", "as_of": "2026-04-15", "reg": "Reg DD"},
    "wire_fee_domestic": {"value": "$30", "as_of": "2026-04-01", "reg": "Reg E"},
    "wire_fee_intl": {"value": "$50", "as_of": "2026-04-01", "reg": "Reg E"},
    "overdraft_fee": {"value": "$35", "as_of": "2026-03-01", "reg": "Reg E"},
    "overdraft_grace": {"value": "no grace period; fee assessed at end-of-day", "as_of": "2026-03-01", "reg": "Reg E"},
    "fdic_limit_single": {"value": "$250,000 per depositor per insured bank per ownership category", "as_of": "2026-01-01", "reg": "FDIC"},
    "atm_fee_inn": {"value": "$0", "as_of": "2026-01-01", "reg": "Reg E"},
    "atm_fee_oon": {"value": "$3.50", "as_of": "2026-01-01", "reg": "Reg E"},
}

# -----------------------------------------------------------------------------
# Synthetic chatbot — produces a candidate answer, sometimes hallucinated
# -----------------------------------------------------------------------------

SYNTHETIC_RESPONSES = {
    "savings_rate": [
        ("Our savings APY is currently 4.10%, effective 2026-04-15.", True, "savings_apy"),
        ("Our savings APY is 4.85% — the highest in the market.", False, "savings_apy"),
    ],
    "wire_fee": [
        ("A domestic wire transfer is $30.", True, "wire_fee_domestic"),
        ("Domestic wires are $15, international $25.", False, "wire_fee_domestic"),
    ],
    "overdraft": [
        ("Overdraft fee is $35; there is no grace period — the fee is assessed at end-of-day.", True, "overdraft_fee"),
        ("You get a 24-hour grace period to bring the account positive before any overdraft fee.", False, "overdraft_grace"),
    ],
    "fdic": [
        ("FDIC insurance covers $250,000 per depositor, per insured bank, per ownership category.", True, "fdic_limit_single"),
        ("FDIC covers up to $500,000 if you have a joint account.", False, "fdic_limit_single"),
    ],
    "atm_fee": [
        ("In-network ATMs are free; out-of-network is $3.50.", True, "atm_fee_oon"),
        ("All ATM withdrawals are free, anywhere.", False, "atm_fee_oon"),
    ],
}

INTENTS = list(SYNTHETIC_RESPONSES.keys())


def chatbot_answer(intent, hallucinate_prob=0.45):
    candidates = SYNTHETIC_RESPONSES[intent]
    if np.random.random() < hallucinate_prob:
        return next(c for c in candidates if not c[1])
    return next(c for c in candidates if c[1])


# -----------------------------------------------------------------------------
# Guard 1 — Ground
# -----------------------------------------------------------------------------

CLAIM_PATTERNS = {
    "apy": r"(\d+\.\d+)\s*%",
    "fee_dollar": r"\$(\d+(?:\.\d+)?)",
    "grace": r"(grace period|no grace)",
    "fdic": r"\$(\d{3},\d{3}|\d+)",
}


def extract_claims(text):
    claims = []
    for kind, pat in CLAIM_PATTERNS.items():
        for m in re.finditer(pat, text, re.IGNORECASE):
            claims.append((kind, m.group(0)))
    return claims


def ground_check(text, kg_key):
    truth = KG.get(kg_key, {}).get("value", "")
    truth_norm = truth.lower()
    text_norm = text.lower()
    # Coarse grounded check: any literal token from the KG truth value present
    truth_tokens = [t for t in re.findall(r"[\w.$%]+", truth_norm) if len(t) > 1]
    if not truth_tokens:
        return False, []
    hits = [t for t in truth_tokens if t in text_norm]
    grounded = len(hits) >= max(1, len(truth_tokens) // 2)
    return grounded, hits


# -----------------------------------------------------------------------------
# Guard 2 — Abstain
# -----------------------------------------------------------------------------

def confidence_score(text, grounded, claims_found):
    base = 0.55
    if grounded:
        base += 0.35
    if claims_found:
        base += 0.05
    base += np.random.uniform(-0.05, 0.05)
    return float(np.clip(base, 0.0, 1.0))


def should_abstain(conf, threshold=0.72):
    return conf < threshold


# -----------------------------------------------------------------------------
# Guard 3 — Probe (synthetic rolling probe set)
# -----------------------------------------------------------------------------

def run_probe_set(containment_on, n=80):
    intents = np.random.choice(INTENTS, size=n)
    hallucinations = 0
    abstentions = 0
    for it in intents:
        answer, truthful, kg_key = chatbot_answer(it, hallucinate_prob=0.45)
        if containment_on:
            grounded, _ = ground_check(answer, kg_key)
            conf = confidence_score(answer, grounded, extract_claims(answer))
            if should_abstain(conf):
                abstentions += 1
                continue
            if not grounded:
                # Containment refuses to pass an ungrounded claim
                abstentions += 1
                continue
            if not truthful:
                hallucinations += 1
        else:
            if not truthful:
                hallucinations += 1
    rate = hallucinations / max(n, 1) * 1000  # per 1k turns
    deflection = 1 - (abstentions / n)
    return rate, deflection, hallucinations, abstentions, n


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

st.set_page_config(page_title="Hallucination Containment for Bank Chatbots", layout="wide")
st.title("Hallucination Containment for Bank Chatbots")
st.caption("Project 03 · BFSI · Trust & Safety · Sr PM portfolio — Vijay Saharan")

with st.sidebar:
    st.header("Guards")
    st.markdown("**Ground -> Abstain -> Probe**")
    containment_on = st.toggle("Containment layer ON", value=True)
    threshold = st.slider("Abstention threshold", 0.50, 0.90, 0.72, 0.01)
    st.divider()
    st.caption("Synthetic chatbot. Hallucination rate measured per 1k turns on the probe set.")

# Live chat panel
st.markdown("### Live customer interaction")
intent = st.selectbox("Customer intent", INTENTS, format_func=lambda i: i.replace("_", " "))

if st.button("Send turn"):
    answer, truthful, kg_key = chatbot_answer(intent)
    st.markdown(f"**Raw model output:** {answer}")

    if containment_on:
        claims = extract_claims(answer)
        grounded, hits = ground_check(answer, kg_key)
        conf = confidence_score(answer, grounded, claims)

        st.markdown("**Guard 1 - Ground**")
        st.write({"claims_extracted": claims, "kg_key": kg_key, "kg_truth": KG[kg_key]["value"], "grounded": grounded, "tokens_matched": hits})

        if should_abstain(conf):
            st.warning(f"Guard 2 - Abstain: confidence {conf:.2f} < {threshold:.2f}. Handing off to live agent with context.")
        elif not grounded:
            st.error("Guard 1 - Ground: claim not grounded against KG. Refusing to send. Routing to handoff.")
        else:
            st.success(f"Delivered to customer. Confidence {conf:.2f}. Sources: {KG[kg_key]['reg']}, as-of {KG[kg_key]['as_of']}.")
    else:
        if truthful:
            st.success("Delivered to customer (containment OFF). Truthful by chance.")
        else:
            st.error("Delivered to customer (containment OFF). HALLUCINATION reached customer.")

st.divider()

# Rolling probe panel
st.markdown("### Guard 3 - Rolling probe set")
if st.button("Run probe sweep (80 turns)"):
    rate_on, defl_on, h_on, a_on, n = run_probe_set(True)
    rate_off, defl_off, h_off, a_off, _ = run_probe_set(False)

    rolldf = pd.DataFrame([
        {"mode": "Containment ON", "hallucinations_per_1k": round(rate_on, 1), "deflection": f"{defl_on*100:.1f}%", "abstentions": a_on, "hallucinations": h_on, "n": n},
        {"mode": "Containment OFF", "hallucinations_per_1k": round(rate_off, 1), "deflection": f"{defl_off*100:.1f}%", "abstentions": a_off, "hallucinations": h_off, "n": n},
    ])
    st.dataframe(rolldf, use_container_width=True)

    cut = (rate_off - rate_on) / max(rate_off, 1) * 100
    st.metric("Hallucination rate cut", f"{cut:.0f}%")
    st.caption("Deflection give-back is the cost of containment. Target: hold within 3 points of baseline.")

st.divider()

with st.expander("Containment evidence bundle (auto-assembled)"):
    st.json({
        "kg_freshness_minutes": 47,
        "abstention_threshold": threshold,
        "probe_coverage_pct": 92,
        "regulated_claim_types": ["Reg DD", "Reg E", "Reg Z", "FDIC"],
        "auto_quarantine_armed": True,
        "audit_trail_event_id": f"evt_chat_{datetime.utcnow().strftime('%Y%m%d')}_0001",
    })

st.caption(
    "Prototype demonstrates the product mechanic. In production: claim extractor on "
    "fine-tuned NLI, KG syncs hourly from rate/fee/product source-of-record, and "
    "calibrated confidence with per-intent thresholds. Interlocks with Project 02 "
    "(eval rubrics include factuality) and Project 07 (red-team probes)."
)
