"""TierGate - AI use-case intake and risk tiering for a regulated bank.

Streamlit walkthrough on 150 synthetic intake submissions, one step at a time:
  Step 1 - pick an intake submission (or a cohort of them)
  Step 2 - without TierGate: the sponsor's tier is taken as given (red card) next to the
           reference tier and the true attributes the sponsor got wrong (blue card)
  Step 3 - with TierGate: recomputed tier, discrepancies with reasons, evidence gate (green card)
  Step 4 - proof at scale: four result cards and what the design still gets wrong

Everything is computed from the CSVs in ../data by the same functions the step scripts use.
Synthetic data only. The reference tier is true by construction. No AI model is used anywhere
here: the rubric, the cross-checks and the similarity score are plain rules.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SRC_DIR = Path(__file__).parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import step_01_spreadsheet_fifo as s1  # noqa: E402
import step_02_self_declared_tier as s2  # noqa: E402
import step_03_deficiencies_exposed as s3  # noqa: E402
import step_04_with_tiergate as s4  # noqa: E402

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
REPO_BLOB = GITHUB_URL + "/blob/main/11-tiergate-ai-usecase-intake"

st.set_page_config(
    page_title="TierGate - Right risk tier at intake, not the tier the sponsor typed",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, same cards as HalluGuard
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.tg-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.tg-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.tg-hero h1 {color: #ffffff !important; font-size: 46px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.tg-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.tg-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.tg-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.tg-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.tg-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.tg-card h3 {margin-top: 0; color: #0f172a;}
.tg-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
                border-radius: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.04em;
                text-transform: uppercase; margin-bottom: 10px;}

/* Verdict card (green = TierGate, amber = TierGate is off the reference) */
.verdict-card {border-radius: 16px; padding: 26px 30px; margin-bottom: 18px; color: #fff;}
.verdict-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-flag {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-card .vlabel {font-size: 13px; opacity: 0.9; letter-spacing: 0.08em; text-transform: uppercase;}
.verdict-card .vbig {font-size: 44px; font-weight: 800; line-height: 1.1; margin: 4px 0 14px 0;}
.verdict-card .vmetric {font-size: 22px; font-weight: 600;}
.verdict-card .vrow {display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px;}
.verdict-card .vchip {background: rgba(255,255,255,0.18); padding: 6px 12px; border-radius: 999px;
                      font-size: 13px; font-weight: 600;}
.verdict-card .vsec {margin-top: 18px; font-size: 13px; opacity: 0.9; letter-spacing: 0.08em;
                     text-transform: uppercase; font-weight: 600;}
.verdict-card .vflag {background: rgba(0,0,0,0.20); border-radius: 10px; padding: 9px 13px;
                      margin-top: 8px; font-size: 14px; line-height: 1.45;}
.verdict-card .vtldr {margin-top: 16px; font-size: 15px; line-height: 1.5; opacity: 0.95;}

/* Proof metric cards */
.tg-mgrid {display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px;}
.tg-mcard {border-radius: 16px; padding: 22px 22px 20px 22px; color: #fff;}
.tg-mcard .mtag {display: inline-block; background: rgba(255,255,255,0.18); padding: 3px 10px;
                 border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
                 text-transform: uppercase;}
.tg-mcard .mlabel {font-size: 14px; font-weight: 600; margin-top: 12px; opacity: 0.95;}
.tg-mcard .mval {font-size: 44px; font-weight: 800; line-height: 1.1; margin: 4px 0 8px 0;}
.tg-mcard .msub {font-size: 14px; opacity: 0.95;}
@media (max-width: 900px) {.tg-mgrid {grid-template-columns: repeat(2, 1fr);}}

/* Trust and limit panels */
.trust-card {background: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid #1f5fb0;
             border-radius: 12px; padding: 20px 24px; margin-bottom: 18px;}
.tg-limit {background: #f8fafc; border: 1px solid #e2e8f0; border-left: 5px solid #94a3b8;
           border-radius: 12px; padding: 18px 24px; margin-bottom: 18px; color: #475569;}
.tg-limit h4 {margin: 0 0 8px 0; color: #475569; font-size: 15px; letter-spacing: 0.04em;
              text-transform: uppercase;}
.tg-limit ul {margin: 6px 0 0 18px; padding: 0;}
.tg-limit li {color: #475569; line-height: 1.55; font-size: 14px; margin-bottom: 4px;}

/* Basic review vs truth panels */
.bot-bad {background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #dc2626;
          border-radius: 10px; padding: 14px 18px; color: #7f1d1d; line-height: 1.55;}
.bot-good {background: #ecfdf5; border: 1px solid #bbf7d0; border-left: 4px solid #059669;
           border-radius: 10px; padding: 14px 18px; color: #065f46; line-height: 1.55;}
.bot-truth {background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb;
            border-radius: 10px; padding: 14px 18px; color: #1e3a8a; line-height: 1.55;}
.bot-ok {background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #64748b;
         border-radius: 10px; padding: 14px 18px; color: #334155; line-height: 1.55;}

/* Tier pills */
.tg-tier {display: inline-block; padding: 4px 12px; border-radius: 10px; font-weight: 700; font-size: 16px;}
.t1 {background: #dcfce7; color: #14532d;} .t2 {background: #fef9c3; color: #713f12;}
.t3 {background: #ffedd5; color: #7c2d12;} .t4 {background: #fee2e2; color: #7f1d1d;}

/* Buttons - one big primary CTA */
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg,#1f5fb0,#163a6c) !important;
  color: #fff !important; border: 0 !important; padding: 14px 28px !important;
  font-size: 17px !important; font-weight: 600 !important; border-radius: 12px !important;
  box-shadow: 0 4px 14px rgba(31,95,176,0.35) !important;
}

h1, h2, h3 {color: #0f172a;}
.muted {color: #64748b; font-size: 14px;}
</style>
""",
    unsafe_allow_html=True,
)


def esc(x) -> str:
    return html.escape(str(x), quote=True)


# ---------------------------------------------------------------------------
# Data: one cached pass through the same functions the step scripts use
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_all() -> dict:
    res4 = s4.run()
    res3 = s3.run()
    res2 = s2.run()
    res1 = s1.run()
    cases = s1.load_cases()
    return {
        "cases": cases,
        "res1": res1, "res2": res2, "res3": res3, "res4": res4,
        "checklist": s1.load_checklist(),
        "names": s1.load_evidence_names(),
        "on_file": s1.load_evidence_on_file(),
        "catalog": s3.load_catalog(),
        "registry": s3.load_registry(),
    }


D = load_all()
CASES = D["cases"]
BY_ID = {c["use_case_id"]: c for c in CASES}
T4 = {r["use_case_id"]: r for r in D["res4"]["rows"]}
T2 = {r["use_case_id"]: r for r in D["res2"]["rows"]}
FLAGS3 = D["res3"]["flags"]
R4 = D["res4"]
R1 = D["res1"]
R2 = D["res2"]
Q = R4["queue"]

COHORTS = {
    "all": ("All submissions", [c["use_case_id"] for c in CASES]),
    "under_hi": ("True tier 3-4 the sponsor declared too low",
                 [c["use_case_id"] for c in CASES
                  if c["reference_tier"] >= 3 and c["self_declared_tier"] < c["reference_tier"]]),
    "approved_gap": ("Approved by the basic approach with required evidence missing",
                     [c["use_case_id"] for c in CASES if FLAGS3[c["use_case_id"]]["f"]]),
    "dups": ("Duplicate or overlapping submissions",
             [c["use_case_id"] for c in CASES if c["duplicate_group"]]),
    "limit": ("Known limit: form and catalog both wrong on the data class", list(R4["both_wrong_ids"])),
    "over": ("TierGate tiered higher than the reference (cost of conservative checks)",
             [r["use_case_id"] for r in R4["rows"] if r["recomputed"] > r["reference"]]),
}

OPTIONS: list[str] = []
KEYS: list[tuple] = []
for key, (label, ids) in COHORTS.items():
    OPTIONS.append("Cohort: %s (%d)" % (label, len(ids)))
    KEYS.append(("cohort", key))
for c in CASES:
    OPTIONS.append("%s | %s | declared T%d, reference T%d"
                   % (c["use_case_id"], c["title"][:62], c["self_declared_tier"], c["reference_tier"]))
    KEYS.append(("case", c["use_case_id"]))

DEFAULT_ID = D["res4"]["headline_id"]
DEFAULT_INDEX = KEYS.index(("case", DEFAULT_ID))

# Attributes on the form that can differ from the hidden true value
ATTRS = [
    ("customer-facing", "customer_facing", "true_customer_facing"),
    ("decision autonomy", "decision_autonomy", "true_decision_autonomy"),
    ("data class", "data_class", "true_data_class"),
    ("vendor model", "vendor_model", "true_vendor_model"),
    ("regulatory scope", "regulatory_scope", "true_regulatory_scope"),
    ("exposure band", "financial_exposure_band", "true_financial_exposure_band"),
]

if "step" not in st.session_state:
    st.session_state.step = 1


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


def tier_pill(t: int) -> str:
    return "<span class='tg-tier t%d'>Tier %d</span>" % (t, t)


def mean_of(xs: list) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def csv_list(xs: list) -> str:
    return ", ".join(xs)


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='tg-hero'>
  <div class='brand'>🚦 TierGate</div>
  <h1>High-risk AI use cases found at intake: {100 * R4['hi_recall']:.1f}%, not {100 * R4['declared_hi_recall']:.1f}%.</h1>
  <div class='sub'>Sponsors type their own risk tier on the intake form, and the basic review trusts it. TierGate recomputes the tier, flags what the form got wrong, and holds approval until the evidence is on file.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>{R4['n_cases']} submissions</span>
    <span class='pill'>Plain rules, no AI model</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

if st.session_state.step == 1:
    cta_col, _ = st.columns([1, 2])
    with cta_col:
        if st.button("See it in action  ->", key="cta_hero", type="primary", use_container_width=True):
            advance(2)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 1 - Pick an intake submission
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='tg-card'><span class='tg-step-label'>Step 1</span>"
    "<h3>Pick an intake submission</h3>"
    "<p class='muted'>A sponsor asks to use AI at the bank and types in a risk tier. "
    "Pick one request, or a group of them.</p></div>",
    unsafe_allow_html=True,
)

choice = st.selectbox("Scenario", OPTIONS, index=DEFAULT_INDEX, key="scenario", label_visibility="collapsed")
kind, key = KEYS[OPTIONS.index(choice)]
if kind == "case":
    sel_ids = [key]
else:
    sel_ids = COHORTS[key][1]
sel = [BY_ID[i] for i in sel_ids]
sel_rows = [T4[i] for i in sel_ids]

if kind == "case":
    c = sel[0]
    st.markdown(
        "<div class='tg-card'><b>%s</b> - %s<br>"
        "<span class='muted'>%s, submitted %s. The sponsor typed:</span> %s</div>"
        % (esc(c["use_case_id"]), esc(c["title"]), esc(c["sponsor_unit"]), esc(c["submitted_date"]),
           tier_pill(c["self_declared_tier"])),
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='tg-card'><b>%s</b><br><span class='muted'>%d submissions in this group.</span></div>"
        % (esc(COHORTS[key][0]), len(sel_ids)),
        unsafe_allow_html=True,
    )

st.markdown(
    "<p class='muted'>Synthetic data: %d made-up submissions, no real bank, vendor or person. "
    "The reference tier is true by construction: the written rubric applied to the hidden true attributes. "
    "Accuracy measures how well each method recovers it from noisy inputs, not how real banks behave. "
    "Accuracy, recall and evidence counts are measured on this set. Queue waits, reviewer hours and the annual figure "
    "are modeled from the assumptions in the step scripts. No AI model is used: the rubric, the cross-checks and the "
    "duplicate score are plain rules. High-risk means tier 3-4.</p>" % R4["n_cases"],
    unsafe_allow_html=True,
)

if st.session_state.step < 2:
    if st.button("Run the demo  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - Without TierGate
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='tg-card'><span class='tg-step-label'>Step 2</span>"
        "<h3>Without TierGate - the sponsor's tier is taken as given</h3>"
        "<p class='muted'>The reviewer applies the checklist for the tier the sponsor typed "
        "and approves when it is covered.</p></div>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    if kind == "case":
        c = sel[0]
        r2 = T2[c["use_case_id"]]
        d, ref = r2["declared"], r2["reference"]
        gap_missed = bool(r2["approved"] and r2["missing_reference"])

        # RED card: what the declared tier and the basic review do
        body = []
        if r2["approved"]:
            body.append("Declared tier %d, approved with the tier-%d checklist." % (d, d))
        else:
            body.append("Declared tier %d, held: declared-tier evidence missing (%s). Requested ad hoc."
                        % (d, esc(csv_list(r2["missing_declared"]))))
        if d < ref:
            body.append("The case gets a lighter review and a shorter checklist than its risk calls for.")
        elif d > ref:
            body.append("Declared tier is above the reference tier: extra review effort.")
        if gap_missed:
            body.append("<b>MISSED:</b> evidence the reference tier requires is not on file: %s."
                        % esc(csv_list(r2["missing_reference"])))
        if c["duplicate_group"]:
            others = [x["use_case_id"] for x in CASES
                      if x["duplicate_group"] == c["duplicate_group"] and x["use_case_id"] != c["use_case_id"]]
            body.append("<b>MISSED:</b> same underlying use case as %s. The spreadsheet has no link."
                        % esc(csv_list(others)))
        if d != ref:
            red_cls, red_mark = "bot-bad", "WRONG"
        elif gap_missed or c["duplicate_group"]:
            red_cls, red_mark = "bot-bad", "MISSED"
        else:
            red_cls, red_mark = "bot-ok", "CORRECT"
        with c1:
            st.markdown(
                "<div class='%s'><b>Basic review says (%s):</b><br>%s</div>" % (red_cls, red_mark, "<br>".join(body)),
                unsafe_allow_html=True,
            )

        # BLUE card: the reference tier and the true attributes the sponsor got wrong
        wrong = []
        for label_, fk, tk in ATTRS:
            if c[fk] != c[tk]:
                extra = ""
                if fk == "data_class":
                    extra = " (the catalog records %s)" % esc(D["catalog"][c["dataset_name"]])
                wrong.append("<b>%s:</b> the form says %s, the true value is %s%s"
                             % (esc(label_), esc(c[fk] or "(blank)"), esc(c[tk]), extra))
        if not wrong:
            wrong.append("The attributes on the form match the true values.")
        with c2:
            st.markdown(
                "<div class='bot-truth'><b>Source of truth: reference tier %d</b><br>%s<br>"
                "<i>The reference tier is the written rubric applied to the true attributes.</i></div>"
                % (ref, "<br>".join(wrong)),
                unsafe_allow_html=True,
            )

        with st.expander("See the data"):
            st.dataframe(pd.DataFrame([{
                "use case": c["use_case_id"], "submitted": c["submitted_date"], "sponsor unit": c["sponsor_unit"],
                "title": c["title"], "tier typed by sponsor": c["self_declared_tier"]}]),
                use_container_width=True, hide_index=True)
            st.write("Review given: **%.1f hours**, same as every other row. Queue wait for this row (modeled mean): **%.1f business days**."
                     % (s1.UNIFORM_REVIEW_H, T4[c["use_case_id"]]["wait_before"]))
            cat_cls = D["catalog"][c["dataset_name"]]
            st.dataframe(pd.DataFrame([
                {"attribute": label_, "on the form": c[fk] or "(blank)",
                 "catalog": cat_cls if fk == "data_class" else "-", "true value": c[tk]}
                for label_, fk, tk in ATTRS]), use_container_width=True, hide_index=True)
            st.caption("Form data class: %s. Catalog records %s for %s." % (c["data_class"], cat_cls, c["dataset_name"]))
            st.caption("Form customer-facing answer: %s. Form vendor model: %s."
                       % (c["customer_facing"] or "(blank)", c["vendor_model"]))
            st.caption("Queue numbers are modeled: %d reviewers, %d intake hours each per week, %.1f hours per review, %d seeded replications."
                       % (s1.N_REVIEWERS, s1.INTAKE_HOURS_PER_REVIEWER_PER_WEEK, s1.UNIFORM_REVIEW_H, s1.REPLICATIONS))
    else:
        rows2 = [T2[i] for i in sel_ids]
        n_mis = sum(1 for r in rows2 if r["mis_tier"])
        n_app = sum(1 for r in rows2 if r["approved"])
        n_gap = sum(1 for r in rows2 if r["approved"] and r["missing_reference"])
        hi = [r for r in sel_rows if r["reference"] >= 3]
        if n_mis:
            red_cls, red_mark = "bot-bad", "WRONG"
        elif n_gap:
            red_cls, red_mark = "bot-bad", "MISSED"
        else:
            red_cls, red_mark = "bot-ok", "CORRECT"
        with c1:
            st.markdown(
                "<div class='%s'><b>Basic review says (%s):</b><br>"
                "Declared tier wrong: <b>%d of %d</b><br>"
                "Approved by the basic approach: <b>%d of %d</b><br>"
                "<b>MISSED:</b> approved with required evidence missing: <b>%d</b></div>"
                % (red_cls, red_mark, n_mis, len(rows2), n_app, len(rows2), n_gap),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                "<div class='bot-truth'><b>Source of truth: the reference tier</b><br>"
                "True tier 3-4 in this group: <b>%d of %d</b><br>"
                "<i>The reference tier is the written rubric applied to the true attributes.</i></div>"
                % (len(hi), len(sel_rows)),
                unsafe_allow_html=True,
            )
        with st.expander("See the data"):
            waits = [T4[i]["wait_before"] for i in sel_ids]
            st.write("%d submissions, each given **%.1f hours** of the same review. Mean queue wait for this cohort (modeled): **%.1f business days**. "
                     "Across all tier 3-4 cases: %.1f days."
                     % (len(sel_ids), s1.UNIFORM_REVIEW_H, mean_of(waits), R1["wait_hi_mean"]))
            st.caption("Queue numbers are modeled: %d reviewers, %d intake hours each per week, %.1f hours per review, %d seeded replications."
                       % (s1.N_REVIEWERS, s1.INTAKE_HOURS_PER_REVIEWER_PER_WEEK, s1.UNIFORM_REVIEW_H, s1.REPLICATIONS))

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With TierGate
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='tg-card'><span class='tg-step-label'>Step 3</span>"
        "<h3>With TierGate - the tier is recomputed and checked</h3>"
        "<p class='muted'>The recompute reads the form, the catalog's recorded class and the vendor registry. "
        "It never reads the hidden true columns; they are used afterwards to score it.</p></div>",
        unsafe_allow_html=True,
    )
    if kind == "case":
        c = sel[0]
        x = T4[c["use_case_id"]]
        rec, ref, dec = x["recomputed"], x["reference"], x["declared"]

        if rec != ref:
            vclass, vword = "verdict-review", ("TIERED HIGH" if rec > ref else "STILL TOO LOW")
        elif rec != dec:
            vclass, vword = "verdict-pass", "RE-TIERED"
        elif x["gate"] == "HOLD":
            vclass, vword = "verdict-pass", "HELD"
        else:
            vclass, vword = "verdict-pass", "CONFIRMED"

        if rec == ref:
            tldr = "TierGate matches the reference tier (%d points on the rubric)." % x["score"]
            if rec != dec:
                tldr += " The sponsor declared tier %d." % dec
        else:
            why = "; ".join(x["causes"]) if x["causes"] else "see flags"
            tldr = "TierGate is %s the reference tier. Cause: %s." % ("below" if rec < ref else "above", esc(why))

        parts = [
            "<div class='verdict-card %s'>" % vclass,
            "<div class='vlabel'>TierGate verdict</div>",
            "<div class='vbig'>%s</div>" % vword,
            "<div class='vmetric'>Recomputed tier %d  /  declared %d  /  reference %d</div>" % (rec, dec, ref),
            "<div class='vrow'><span class='vchip'>Gate: %s</span><span class='vchip'>%s</span>%s</div>"
            % (esc(x["gate"]),
               "Matches the reference tier" if rec == ref else "Does not match the reference tier",
               "<span class='vchip'>Duplicate link proposed</span>" if x["linked_to"] else ""),
            "<div class='vsec'>Discrepancies flagged, with reasons</div>",
        ]
        if not x["flags"]:
            parts.append("<div class='vflag'>No discrepancy: form, catalog and registry agree.</div>")
        for f in x["flags"]:
            parts.append("<div class='vflag'><b>%s</b> %s</div>" % (esc(f["code"]), esc(f["reason"])))
        parts.append("<div class='vsec'>Evidence checklist for tier %d</div>" % rec)
        if x["gate"] == "READY":
            parts.append("<div class='vflag'>All required evidence is on file. Gate: READY. Approval may proceed.</div>")
        else:
            parts.append("<div class='vflag'>Evidence missing: %s. Gate: HOLD. Approval blocked until they are on file.</div>"
                         % esc(csv_list(x["missing"])))
        if x["linked_to"]:
            parts.append("<div class='vsec'>Possible duplicate</div>")
            parts.append("<div class='vflag'>Proposed duplicate link to <b>%s</b> (token overlap %.2f). A reviewer confirms the link (%.1fh)%s.</div>"
                         % (esc(x["linked_to"]), x["link_score"], s1.LINK_CHECK_H,
                            "" if x["link_true"] else "; in this set this link is a false positive"))
        elif c["duplicate_group"]:
            parts.append("<div class='vsec'>Possible duplicate</div>")
            parts.append("<div class='vflag'>This submission has a true duplicate that the similarity score did not link at threshold %.2f.</div>"
                         % R4["link_threshold"])
        parts.append("<div class='vtldr'><b>TL;DR:</b> %s</div>" % tldr)
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)

        paper = (
            "# TierGate decision record (synthetic data)\n\n"
            "**Use case:** %s - %s\n\n**Declared tier:** %d\n\n**Recomputed tier:** %d (%d rubric points)\n\n"
            "**Reference tier (true by construction):** %d\n\n**Gate:** %s\n\n**Missing evidence:** %s\n\n**Flags:**\n%s\n"
            % (c["use_case_id"], c["title"], x["declared"], x["recomputed"], x["score"], x["reference"], x["gate"],
               ", ".join(x["missing"]) or "none",
               "\n".join("- %s: %s" % (f["code"], f["reason"]) for f in x["flags"]) or "- none")
        )
        st.download_button("Download decision record (Markdown)", paper,
                           file_name="tiergate_%s.md" % c["use_case_id"], mime="text/markdown")

        with st.expander("See the data"):
            have = D["on_file"].get(c["use_case_id"], set())
            ev_rows = []
            for eid in D["checklist"][x["recomputed"]]:
                item, interlock = D["names"][eid]
                ev_rows.append({"evidence": eid, "required item": item, "on file": "yes" if eid in have else "MISSING",
                                "interlock": interlock})
            st.markdown("**Evidence checklist for tier %d**" % x["recomputed"])
            st.dataframe(pd.DataFrame(ev_rows), use_container_width=True, hide_index=True)
    else:
        n = len(sel_rows)
        acc = sum(1 for r in sel_rows if r["recomputed"] == r["reference"])
        dec_ok = sum(1 for r in sel_rows if r["declared"] == r["reference"])
        hi = [r for r in sel_rows if r["reference"] >= 3]
        found = sum(1 for r in hi if r["recomputed"] >= 3)
        held = sum(1 for r in sel_rows if r["gate"] == "HOLD")
        vclass = "verdict-pass" if acc >= dec_ok else "verdict-review"
        st.markdown(
            "<div class='verdict-card %s'>"
            "<div class='vlabel'>TierGate verdict</div>"
            "<div class='vbig'>%d of %d</div>"
            "<div class='vmetric'>TierGate tier correct</div>"
            "<div class='vrow'><span class='vchip'>Self-declared tier correct: %d of %d</span>"
            "<span class='vchip'>True tier 3-4 found: %d of %d</span>"
            "<span class='vchip'>Held for evidence: %d of %d</span></div>"
            "</div>" % (vclass, acc, n, dec_ok, n, found, len(hi), held, n),
            unsafe_allow_html=True,
        )
        with st.expander("See the data"):
            show = []
            for r in sel_rows[:60]:
                show.append({"use case": r["use_case_id"], "title": BY_ID[r["use_case_id"]]["title"][:58],
                             "declared": r["declared"], "TierGate": r["recomputed"], "reference": r["reference"],
                             "gate": r["gate"], "flags": ", ".join(f["code"] for f in r["flags"] if f["code"] not in ("TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE"))})
            st.dataframe(pd.DataFrame(show), use_container_width=True, hide_index=True)
            if n > 60:
                st.caption("Showing the first 60 of %d." % n)

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='tg-card'><span class='tg-step-label'>Step 4</span>"
        "<h3>Proof at scale - %d synthetic submissions</h3>"
        "<p class='muted'>Every submission in the set, scored against the reference tier. "
        "Green cards are measured on this set. The amber card is modeled.</p></div>" % R4["n_cases"],
        unsafe_allow_html=True,
    )

    def mcard(cls: str, tag: str, label: str, value: str, sub: str) -> str:
        return ("<div class='tg-mcard %s'><span class='mtag'>%s</span><div class='mlabel'>%s</div>"
                "<div class='mval'>%s</div><div class='msub'>%s</div></div>" % (cls, tag, label, value, sub))

    st.markdown(
        "<div class='tg-mgrid'>"
        + mcard("verdict-pass", "Measured", "Tier accuracy", "%.1f%%" % (100 * R4["accuracy"]),
                "%+.1f pts vs self-declared" % (100 * (R4["accuracy"] - (1 - R4["err_declared"]))))
        + mcard("verdict-pass", "Measured", "Tier 3-4 recall", "%.1f%%" % (100 * R4["hi_recall"]),
                "%+.1f pts vs self-declared" % (100 * (R4["hi_recall"] - R4["declared_hi_recall"])))
        + mcard("verdict-pass", "Measured", "Evidence-gap detection", "%.1f%%" % (100 * R4["gap_detection_rate"]),
                "%+.1f pts vs basic" % (100 * (R4["gap_detection_rate"] - R4["basic_gap_detection_rate"])))
        + mcard("verdict-review", "Modeled", "Tier 3-4 mean wait", "%.1f days" % Q["hi_ordered"],
                "%.1f days FIFO" % Q["hi_fifo"])
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='tg-limit'><h4>What it still gets wrong</h4><ul>"
        "<li><b>%d use cases</b> have a data class that the form and the catalog both understate. "
        "TierGate takes the higher of the two, so it agrees with the wrong answer; %d of them end up at the wrong tier.</li>"
        "<li><b>%d submissions</b> are tiered above the reference (conservative customer-facing checks) and %d below it.</li>"
        "<li><b>Tier 1-2 cases wait longer.</b> When the queue is ordered by tier, they wait %.1f business days instead of %.1f (modeled).</li>"
        "</ul><p class='muted' style='margin:8px 0 0 0;'>Pick a cohort in Step 1 ('Known limit' or 'TierGate tiered higher than the reference') to see these cases.</p></div>"
        % (R4["both_wrong_n"], R4["both_wrong_mis_n"], R4["over_n"], R4["under_n"], Q["lo_ordered"], Q["lo_fifo"]),
        unsafe_allow_html=True,
    )

    # queue effect for the current selection
    with st.expander("Queue effect for this selection (modeled)"):
        mb = mean_of([r["wait_before"] for r in sel_rows])
        mf = mean_of([r["wait_fifo"] for r in sel_rows])
        mo = mean_of([r["wait_ordered"] for r in sel_rows])
        fig = go.Figure(go.Bar(
            x=["Step 1: same review, FIFO", "TierGate depth, FIFO", "TierGate depth, ordered by tier"],
            y=[mb, mf, mo], marker_color=["#94a3b8", "#1f5fb0", "#16a34a"],
            text=["%.1f" % v for v in (mb, mf, mo)], textposition="outside"))
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="mean queue wait (business days)",
                          title="Queue effect for this selection (modeled)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Modeled: %d reviewers, %d intake hours each per week, tier review times T1 %.1fh, T2 %.1fh, T3 %.1fh, T4 %.1fh, "
                   "%d seeded replications. Across all truly high-risk cases the mean wait is %.1f days in first-in-first-out and %.1f days "
                   "ordered by tier; tier 1-2 cases wait %.1f days instead of %.1f."
                   % (s1.N_REVIEWERS, s1.INTAKE_HOURS_PER_REVIEWER_PER_WEEK, s1.TIER_REVIEW_H[1], s1.TIER_REVIEW_H[2],
                      s1.TIER_REVIEW_H[3], s1.TIER_REVIEW_H[4], s1.REPLICATIONS,
                      Q["hi_fifo"], Q["hi_ordered"], Q["lo_ordered"], Q["lo_fifo"]))

    # six deficiencies of the basic approach
    DEF_LABELS = [
        ("a", "Self-declared tier understates risk"),
        ("b", "Data class never cross-checked against the catalog"),
        ("c", "Customer-facing impact missing or ambiguous"),
        ("d", "Vendor dependency unflagged"),
        ("e", "Overlapping use cases not linked"),
        ("f", "Approval without the evidence the tier requires"),
    ]
    with st.expander("The six deficiencies of the basic approach, with counts"):
        st.write("For one submission: does the deficiency show up on it? For a cohort: how many of its submissions. "
                 "The last column is the count across all %d submissions (step_03 output)." % R4["n_cases"])
        totals = {
            "a": D["res3"]["a"]["n"], "b": D["res3"]["b"]["below_catalog_n"], "c": D["res3"]["c"]["n"],
            "d": D["res3"]["d"]["omitted_n"], "e": D["res3"]["e"]["cases_n"], "f": D["res3"]["f"]["n"],
        }
        table = []
        for k, label_ in DEF_LABELS:
            hits = sum(1 for i in sel_ids if FLAGS3[i][k])
            shown = ("yes" if hits else "no") if kind == "case" else "%d of %d" % (hits, len(sel_ids))
            table.append({"#": k, "deficiency": label_, "this selection": shown,
                          "all %d submissions" % R4["n_cases"]: totals[k]})
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        st.caption("Deficiency (e) counts submissions that belong to a duplicate group: %d groups, %d true pairs. The spreadsheet links none of them."
                   % (D["res3"]["e"]["groups_n"], D["res3"]["e"]["pairs_n"]))

    with st.expander("All wrong tiers by cause"):
        st.write("All %d wrong tiers by cause:" % (R4["n_cases"] - R4["accuracy_n"]))
        st.dataframe(pd.DataFrame([{"cause": k, "cases": v} for k, v in sorted(R4["cause_counts"].items(), key=lambda kv: -kv[1])]),
                     use_container_width=True, hide_index=True)

    with st.expander("Utility = (self-declared error rate - TierGate error rate) x use cases reviewed per year"):
        u = R4["utility"]
        st.write("Measured: self-declared error rate **%.1f%%**, TierGate error rate **%.1f%%**."
                 % (100 * u["err_declared"], 100 * u["err_tiergate"]))
        st.write("Modeled: a $50B-asset US retail bank that sees the same intake rate as this set, %.1f submissions per week for 50 weeks = **%d per year**. "
                 "Mis-tiered use cases avoided per year: **%.1f**." % (u["per_week"], u["annual_intake"], u["avoided_per_year"]))
        st.dataframe(pd.DataFrame([{"submissions per year": s["intake"], "mis-tiered avoided": round(s["avoided"], 1)}
                                   for s in u["annual_sensitivity"]]), use_container_width=True, hide_index=True)

    if st.button("Reset", key="reset_all"):
        st.session_state.step = 1
        st.rerun()

st.markdown(
    "<div class='tg-card muted'>Portfolio prototype on synthetic data. Design and numbers in "
    "<a href='%s/README.md' target='_blank'><code>README.md</code></a>, "
    "<a href='%s/PRD.md' target='_blank'><code>PRD.md</code></a> and "
    "<a href='%s/ARCHITECTURE.md' target='_blank'><code>ARCHITECTURE.md</code></a>.</div>" % (REPO_BLOB, REPO_BLOB, REPO_BLOB),
    unsafe_allow_html=True,
)
