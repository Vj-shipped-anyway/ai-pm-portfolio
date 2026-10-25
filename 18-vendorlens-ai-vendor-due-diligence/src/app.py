"""VendorLens - AI vendor due diligence scored on evidence, concentration and exit.

Streamlit walkthrough. Pick one vendor, then step through the story:
  Step 1  Pick a vendor
  Step 2  Without VendorLens - the questionnaire verdict (red) and what is actually true (blue)
  Step 3  With VendorLens - evidence-adjusted score, concentration, exit and review cadence
  Step 4  Proof at scale - the same measures over all 40 vendors, with the known limits

All data is synthetic (data/_generate.py, seeded). Vendor ids and model providers are invented
codes. The scoring is plain rules; there is no model anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_status_quo import (  # noqa: E402
    AS_OF, DOC_TYPES, FLAT_CYCLE_DAYS, answer_support, load_all, summarize as summarize_step1,
)
from step_02_questionnaire_checklist import PASS_YES_PCT, summarize as summarize_step2  # noqa: E402
from step_03_deficiencies_exposed import summarize as summarize_step3  # noqa: E402
from step_04_with_vendorlens import (  # noqa: E402
    CREDIT, SUPPORT_BUCKET, analyze, questionnaire_tag, sensitivity, vendorlens_tag,
)

st.set_page_config(
    page_title="VendorLens - AI vendor risk scored on evidence, not a questionnaire",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/18-vendorlens-ai-vendor-due-diligence/README.md"
SR234_URL = "https://www.federalreserve.gov/supervisionreg/srletters/SR2304.htm"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.vl-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.vl-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.vl-hero h1 {color: #ffffff !important; font-size: 46px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.vl-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.vl-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.vl-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.vl-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.vl-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.vl-card h3 {margin-top: 0; color: #0f172a;}
.vl-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
                border-radius: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.04em;
                text-transform: uppercase; margin-bottom: 10px;}

/* Verdict card */
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
.verdict-card .vfind {margin-top: 12px; font-size: 15px; line-height: 1.5;}
.verdict-card .vfind .vchip {margin-right: 6px;}
.verdict-card .vtldr {margin-top: 16px; font-size: 15px; line-height: 1.5; opacity: 0.95;}

/* Proof-at-scale metric grid (verdict cards, two across) */
.metric-grid {display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 18px;}
.metric-grid .verdict-card {margin-bottom: 0;}
@media (max-width: 760px) {.metric-grid {grid-template-columns: 1fr;}}

/* Trust panel */
.trust-card {background: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid #1f5fb0;
             border-radius: 12px; padding: 20px 24px; margin-bottom: 18px;}
.trust-card h4 {margin: 0 0 10px 0; color: #0f172a; font-size: 16px; letter-spacing: 0.04em;
                text-transform: uppercase;}
.trust-card ul {margin: 6px 0 0 18px; padding: 0;}
.trust-card li {color: #334155; line-height: 1.55;}
.trust-card.quiet {border-left-color: #94a3b8;}
.trust-card.quiet h4 {color: #475569;}
.trust-card.quiet li {color: #64748b; font-size: 14px;}

/* Questionnaire vs truth panels */
.bot-bad {background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #dc2626;
          border-radius: 10px; padding: 14px 18px; color: #7f1d1d;}
.bot-good {background: #ecfdf5; border: 1px solid #bbf7d0; border-left: 4px solid #059669;
           border-radius: 10px; padding: 14px 18px; color: #065f46;}
.bot-truth {background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb;
            border-radius: 10px; padding: 14px 18px; color: #1e3a8a;}
.bot-bad ul, .bot-truth ul {margin: 8px 0 0 18px; padding: 0;}
.bot-bad li, .bot-truth li {line-height: 1.5; margin-bottom: 8px;}
.bot-truth li ul {margin-top: 4px;}
.bot-truth li li {margin-bottom: 2px;}
.bot-bad .small {font-size: 13px; opacity: 0.85; margin-top: 8px;}
.bot-bad .tag {display: inline-block; background: #dc2626; color: #fff; padding: 2px 10px; border-radius: 6px;
               font-size: 12px; font-weight: 700; letter-spacing: 0.05em; margin-left: 6px;}
.bot-bad .tag.ok {background: #475569;}

/* Known-limit note (amber, same palette as the review card) */
.limit-note {background: #fef3c7; border: 1px solid #fde68a; border-left: 5px solid #f59e0b;
             border-radius: 10px; padding: 12px 16px; color: #78350f; font-size: 14px; margin-bottom: 14px;}

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


def esc(v) -> str:
    return html.escape(str(v), quote=True)


CLS = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}
DOC_LABEL = {"independent_control_report": "independent control report", "penetration_test": "penetration test",
             "model_documentation": "model documentation"}
EV_LABEL = {"valid": "valid", "stale": "stale (over 12 months old)", "out_of_scope": "does not cover the AI service",
            "missing": "missing"}
DATA_LABEL = {"customer_pii": "customer PII", "internal": "internal data", "none": "no data"}
BACKING_LABEL = {"verified": "backed", "unbacked": "no valid document", "unverifiable": "cannot be checked here",
                 "contradicted": "contradicted by the contract"}


def months_label(days: int) -> str:
    return f"{round(days / 30.4375)} months"


@st.cache_resource
def load_analysis() -> dict:
    data = load_all(DATA_DIR)
    a = analyze(data)
    a["s1"] = summarize_step1(data)
    a["s2"] = summarize_step2(data)
    a["s3"] = summarize_step3(data)
    a["sens"] = sensitivity(data)
    return a


A = load_analysis()
DATA = A["data"]
S1, S2, S3, S4 = A["s1"], A["s2"], A["s3"], A["summary"]
ROWS = A["rows"]
ROW = {r["vendor_id"]: r for r in ROWS}
N = S4["vendors"]
NQ = len(DATA["questions"])


# Picker: sorted by VendorLens risk; the default is the first vendor the questionnaire passes and VendorLens catches.
ORDER = [r["vendor_id"] for r in ROWS]
LABEL_TO_ID = {
    f"{vid}  -  {ROW[vid]['service_type']}  -  {ROW[vid]['criticality']}  -  "
    f"questionnaire {'PASS' if ROW[vid]['checklist_pass'] else 'FAIL'}": vid
    for vid in ORDER
}
LABELS = list(LABEL_TO_ID)
DEFAULT_ID = next((r["vendor_id"] for r in ROWS if r["checklist_pass"] and r["true_risk"] == "high" and r["class"] == "high"),
                  ORDER[0])
DEFAULT_LABEL = next(k for k, v in LABEL_TO_ID.items() if v == DEFAULT_ID)

if "step" not in st.session_state:
    st.session_state.step = 1


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='vl-hero'>
  <div class='brand'>🏢 VendorLens</div>
  <h1>AI vendor risk scored on evidence, concentration and exit, not a questionnaire that passes {S4['passed_high_total']} of {S4['true_high']} high-risk vendors.</h1>
  <div class='sub'>Many AI vendors run on the same upstream model, and a questionnaire never asks. VendorLens checks each answer against a document or the contract, flags concentration and scores how the bank would leave.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>No model: plain rules</span>
    <span class='pill'>{N} vendors · {NQ} questions · {S1['documents']} documents</span>
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
# STEP 1 - pick a vendor
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='vl-card'><span class='vl-step-label'>Step 1</span>"
    "<h3>Pick a vendor</h3>"
    f"<p class='muted'>{N} AI vendors of a modeled bank, ordered by VendorLens risk. The pre-selected vendor passes "
    "the questionnaire and is truly high risk.</p></div>",
    unsafe_allow_html=True,
)
if "vendor_choice" not in st.session_state:
    st.session_state.vendor_choice = DEFAULT_LABEL
st.session_state.vendor_choice = st.selectbox(
    "Vendor:",
    LABELS,
    index=LABELS.index(st.session_state.vendor_choice),
    label_visibility="collapsed",
)
vid = LABEL_TO_ID[st.session_state.vendor_choice]
r = ROW[vid]
v = DATA["by_id"][vid]
ans = DATA["answers"][vid]
truth = DATA["truth"][vid]

st.markdown(
    f"<div class='vl-card'><b>Vendor:</b> <code>{esc(vid)}</code> - {esc(r['service_type'])}<br>"
    f"<span class='muted'>{esc(r['criticality'])} vendor, {esc(DATA_LABEL[r['data_access']])}, "
    f"supports {v['critical_use_cases']} critical use case{'' if v['critical_use_cases'] == 1 else 's'}. Upstream model provider: "
    f"{esc(r['provider']) if r['provider_disclosed'] else 'not disclosed'}.</span></div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='muted'>Synthetic data, no model. These vendors and model providers are invented codes: nothing here "
    "is a real vendor, provider, bank or dataset. The generator decided every vendor's true risk, so the truth is "
    "known. Numbers marked modeled depend on an assumption of a modeled bank (review cadence, allowed exit window, "
    "the 40% concentration line). Scoring is plain rules, not a model.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - Without VendorLens: the questionnaire verdict
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='vl-card'><span class='vl-step-label'>Step 2</span>"
        "<h3>Without VendorLens - the questionnaire passes the answers it is given</h3>"
        "<p class='muted'>The vendor fills in 20 answers about its own controls. A vendor passes at "
        f"{PASS_YES_PCT}% yes. Nothing is checked against a document, a contract, an upstream provider or an exit plan."
        "</p></div>",
        unsafe_allow_html=True,
    )
    yes = sum(1 for a in ans.values() if a == "yes")
    part = sum(1 for a in ans.values() if a == "partial")
    no = sum(1 for a in ans.values() if a == "no")
    tag, failed = questionnaire_tag(r)
    age = r["age_days"]
    red = (
        f"<div class='bot-bad'><b>What the questionnaire says: {'PASS' if r['checklist_pass'] else 'FAIL'}</b>"
        f"<span class='tag{'' if failed else ' ok'}'>{esc(tag)}</span>"
        "<ul>"
        f"<li>{yes} yes, {part} partial, {no} no: {round(100 * yes / NQ, 1)}% yes against the {PASS_YES_PCT}% line.</li>"
        "<li>The documents on file are filed, not read against the answers (a modeled-bank assumption).</li>"
        f"<li>Questions about the upstream model provider: {S3['d2']['questions_asking_provider']} of {NQ}. "
        f"Questions about how the bank would leave: {S3['d3']['questions_asking_exit']} of {NQ}.</li>"
        f"<li>Last assessed {age} days ago. The flat {FLAT_CYCLE_DAYS // 30}-month cycle calls that "
        f"{'overdue' if age > FLAT_CYCLE_DAYS else 'on time'}.</li>"
        "</ul>"
        "<div class='small'>The checklist counts the word yes.</div></div>"
    )

    ev_items = "".join(
        f"<li>{esc(DOC_LABEL[dt])}: {esc(EV_LABEL[r['evidence'][dt]])}</li>" for dt in DOC_TYPES)
    exit_txt = ("no exit clause" if v["exit_clause"] != "yes" else
                f"exit clause, {v['portability_days']} days to port, "
                f"{'tested' if v['exit_tested'] == 'yes' else 'never tested'}")
    blue = (
        "<div class='bot-truth'><b>Source of truth - what is actually there (synthetic):</b><ul>"
        f"<li>Documents on file:<ul>{ev_items}</ul></li>"
        f"<li>Answers that said better than the facts (truth): <b>{truth['overclaimed']}</b> of {NQ}.</li>"
        f"<li>True risk: <b>{esc(CLS[truth['true_risk']])}</b> (latent score {truth['latent']:.3f}, set by the generator).</li>"
        f"<li>Upstream model provider: <b>{esc(truth['true_provider'])}</b> "
        f"({'disclosed to the bank' if truth['provider_disclosed'] else 'not disclosed to the bank'}).</li>"
        f"<li>Contract: {esc(exit_txt)}; audit right {esc(v['audit_right'])}; "
        f"{v['model_change_notice_days']} days notice of a model change.</li>"
        "</ul></div>"
    )
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**The 20 answers, and what could back each one**")
        rows_a = []
        for q in DATA["questions"]:
            sup = answer_support(DATA, vid, q)
            rows_a.append({"Question": q["question_id"], "Text": q["text"], "Answer": ans[q["question_id"]],
                           "What backs it": BACKING_LABEL[SUPPORT_BUCKET[sup]]})
        st.dataframe(pd.DataFrame(rows_a), use_container_width=True, hide_index=True)
        st.markdown("**The six named deficiencies of the questionnaire, on this vendor**")
        gaps = sum(1 for dt in DOC_TYPES if r["evidence"][dt] != "valid")
        top = S3["d2"]["top_provider"]
        dfs = [
            ("1", "Self-declared answers over-claim", gaps > 0 or r["yes_unbacked"] > 0,
             f"{gaps} of 3 document types not valid; {r['yes_unbacked']} yes answers with no valid document"),
            ("2", "Concentration hidden vendor by vendor", r["provider"] == top or not r["provider_disclosed"],
             f"runs on {r['provider']}" + (f", which carries {S3['d2']['top_share_pct']}% of critical use cases"
                                           if r["provider"] == top else "")),
            ("3", "Exit readiness never asked", r["exit_state"] != "ready",
             f"exit {r['exit_state']}: modeled {round(r['modeled_exit_days'])} days against {r['allowed_exit_days']} allowed"),
            ("4", "Data access not weighted", r["data_access"] == "customer_pii",
             f"{DATA_LABEL[r['data_access']]}, same {PASS_YES_PCT}% line"),
            ("5", "Stale assessment", r["age_days"] > r["tier_cadence_days"],
             f"assessed {r['age_days']} days ago; the {r['criticality']} tier calls for {r['tier_cadence_days']} days or less"),
            ("6", "Contract gaps", r["contract_gap"] > 0,
             f"audit right {r['audit_right']}; {r['notice_days']} days notice of a model change"),
        ]
        st.dataframe(pd.DataFrame([{"#": d[0], "Deficiency": d[1], "Hits this vendor": "yes" if d[2] else "no",
                                    "Evidence": d[3]} for d in dfs]), use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With VendorLens
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='vl-card'><span class='vl-step-label'>Step 3</span>"
        f"<h3>With VendorLens - {esc(vid)} is scored on what can be checked</h3>"
        "<p class='muted'>Each answer earns credit only if a valid document or the contract backs it. Then the score "
        "is weighted by criticality and data access, and adjusted for concentration, exit and contract gaps.</p></div>",
        unsafe_allow_html=True,
    )
    if r["conc_flag"]:
        conc_chip = f"Concentration: FLAGGED - {r['provider']} carries {S4['top_share_pct']}% of critical use cases"
    elif not r["provider_disclosed"]:
        conc_chip = "Concentration: unknown - provider not disclosed"
    else:
        share = next(x["share_pct"] for x in A["conc"]["rows"] if x["provider"] == r["provider"])
        conc_chip = f"Concentration: {r['provider']} at {share}%, below the 40% line"
    cad = r["cadence_days"]
    cad_chip = (f"Review every {months_label(cad)}; "
                f"{'overdue by ' + str(r['days_overdue']) + ' days' if r['overdue'] else 'next due ' + r['next_review']}")
    part_label = {"control": "Evidence", "exit": "Exit", "contract": "Contract", "concentration": "Concentration"}
    finds = "".join(
        f"<div class='vfind'><span class='vchip'>{esc(part_label[k])}</span>{esc(t)}</div>" for k, t in r["reasons"])
    vtag = vendorlens_tag(r)
    st.markdown(
        "<div class='verdict-card verdict-pass'>"
        f"<div class='vlabel'>With VendorLens - {esc(vid)} - {esc(vtag)}</div>"
        f"<div class='vbig'>{esc(CLS[r['class']])}</div>"
        f"<div class='vmetric'>Risk score {r['risk']} of 100. Control score {r['control_score']} of 100, "
        f"where the questionnaire said {round(100 * r['checklist_yes'] / NQ)}% yes.</div>"
        "<div class='vrow'>"
        f"<span class='vchip'>{esc(conc_chip)}</span>"
        f"<span class='vchip'>Exit: {esc(r['exit_state'])} ({r['exit_score']} of 100)</span>"
        f"<span class='vchip'>{esc(cad_chip)}</span></div>"
        + finds +
        f"<div class='vtldr'><b>Truth (synthetic):</b> {esc(CLS[r['true_risk']])} risk. "
        f"The questionnaire said {'PASS' if r['checklist_pass'] else 'FAIL'}.</div></div>",
        unsafe_allow_html=True,
    )
    if vtag == "MISSED":
        st.markdown(
            "<div class='limit-note'>Known limit. This vendor is truly high risk and VendorLens does not rate it HIGH. "
            "The generator gave it a risk factor that no answer, document or contract field reveals, or its "
            "documents look valid but its controls are weaker than they say. Evidence authenticity is not verified.</div>",
            unsafe_allow_html=True)
    elif vtag == "FLAGGED":
        st.markdown(
            f"<div class='limit-note'>False alarm. VendorLens rates this vendor HIGH and the truth is "
            f"{esc(CLS[r['true_risk']])}. A person clears it in review.</div>",
            unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Where the risk points come from** (weighted by criticality and data access)")
        st.dataframe(pd.DataFrame([
            {"Part": "Control gap", "Points": r["parts"]["control"]},
            {"Part": "Exit gap", "Points": r["parts"]["exit"]},
            {"Part": "Contract gap", "Points": r["parts"]["contract"]},
            {"Part": "Concentration", "Points": r["parts"]["concentration"]},
            {"Part": "Total risk score", "Points": r["risk"]},
        ]), use_container_width=True, hide_index=True)
        st.markdown("**Credit per answer, by what backs it**")
        st.dataframe(pd.DataFrame([{"Backing": BACKING_LABEL[k], "Yes": c["yes"], "Partial": c["partial"], "No": c["no"]}
                                   for k, c in CREDIT.items()]), use_container_width=True, hide_index=True)
        st.markdown("**Documents on file for this vendor**")
        docs = DATA["docs"].get(vid, [])
        if docs:
            st.dataframe(pd.DataFrame([{"Type": DOC_LABEL[d["doc_type"]], "Issued": d["issued_on"].isoformat(),
                                        "Age (days)": d["age_days"], "Covers the AI service": "yes" if d["covers"] else "no",
                                        "Status": EV_LABEL[d["status"]]} for d in docs]),
                         use_container_width=True, hide_index=True)
        else:
            st.markdown("No documents on file.")
        st.markdown("**Exit model** (modeled)")
        st.markdown(f"Modeled time to exit: {round(r['modeled_exit_days'])} days against {r['allowed_exit_days']} allowed "
                    f"for {'an' if r['criticality'] == 'important' else 'a'} {r['criticality']} vendor. No exit clause counts as 180 days; an untested plan counts as 1.5 times the stated days.")

    lines = [f"# VendorLens review: {vid}", "",
             "Synthetic data. Prototype output for a modeled bank; not a real vendor, provider or assessment.", "",
             f"- Service: {r['service_type']}; {r['criticality']}; {DATA_LABEL[r['data_access']]}",
             f"- Questionnaire: {'PASS' if r['checklist_pass'] else 'FAIL'} ({r['checklist_yes']} of {NQ} yes)",
             f"- VendorLens: {CLS[r['class']]}, risk {r['risk']} of 100, control score {r['control_score']} of 100",
             f"- Concentration: {conc_chip}", f"- Exit: {r['exit_state']} ({r['exit_score']} of 100)",
             f"- Review: {cad_chip}", ""]
    lines += [f"- {part_label[k]}: {t}" for k, t in r["reasons"]]
    st.download_button("Download vendor review (Markdown)", "\n".join(lines),
                       file_name=f"vendorlens_{vid}.md", mime="text/markdown")

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    d1, d2, d3, d5 = S3["d1"], S3["d2"], S3["d3"], S3["d5"]
    st.markdown(
        "<div class='vl-card'><span class='vl-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same checks over the whole synthetic estate: {N} vendors, {NQ} questions, "
        f"{S1['documents']} documents, {S4['critical_use_cases']} critical use cases.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without VendorLens: the questionnaire</div>"
        f"<div class='vbig'>{S4['passed_high_total']} of {S4['true_high']}</div>"
        "<div class='vmetric'>truly high-risk vendors pass</div>"
        f"<div class='vtldr'>{S2['passes']} of {N} vendors pass at {PASS_YES_PCT}% yes. "
        f"{d1['passes_with_evidence_gap']} of those {S2['passes']} have a missing, stale or out-of-scope document.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Without VendorLens: concentration</div>"
        f"<div class='vbig'>{S4['top_share_pct']}%</div>"
        f"<div class='vmetric'>of critical use cases rest on {esc(S4['top_provider'])}</div>"
        f"<div class='vtldr'>The questionnaire asks which provider in {d2['questions_asking_provider']} of {NQ} questions. "
        f"{d2['top_vendors_passing']} of the {d2['top_vendors']} vendors on it pass on their own.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With VendorLens: high risk found</div>"
        f"<div class='vbig'>{S4['high_tp']} of {S4['pred_high']}</div>"
        "<div class='vmetric'>vendors rated HIGH are truly high risk</div>"
        f"<div class='vtldr'>Precision {S4['high_precision_pct']}% against {S4['checklist_precision_pct']}% for a failed questionnaire "
        f"({S4['checklist_found']} of {S4['checklist_fail']}). At the same queue size of {S4['queue_size']}, "
        f"{S4['topk_found']} of {S4['true_high']} truly high-risk vendors are in VendorLens's top {S4['queue_size']}.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With VendorLens: exit and cadence</div>"
        f"<div class='vbig'>{S4['critical_exit_not_ready']} of {S4['critical']}</div>"
        "<div class='vmetric'>critical vendors have no ready exit</div>"
        f"<div class='vtldr'>{d5['critical_overdue']} of {d5['critical']} critical vendors are overdue on a 12-month tier cadence "
        f"(modeled); the flat 24-month cycle flags {d5['overdue_flat']}.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    sens = A["sens"]
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>{len(S4['missed_high'])} of {S4['true_high']} truly high-risk vendors are not rated HIGH, and "
        f"{len(S4['false_high'])} vendors rated HIGH are not. The generator adds a risk factor no answer, document or "
        "contract reveals, so no score built from them can match the truth.</li>"
        f"<li>{S4['unknown_vendors']} vendors do not disclose their upstream provider. {S4['top_provider']} is shown at "
        f"{S4['top_share_pct']}% and is really {S4['true_top_share_pct']}%, "
        f"{S4['understated_points']} points higher. That is understated by construction.</li>"
        "<li>Weights, the HIGH line and the 40% concentration line are my assumptions. Moving the concentration line to 45% "
        f"leaves {sens['conc_line'][2]['flagged']} vendors rated HIGH instead of {S4['pred_high']}.</li>"
        "<li>A document counts as valid if it exists, is recent and covers the AI service. Whether it is authentic "
        "or says anything good is not checked.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Which upstream providers carry the critical use cases**")
    st.caption("Share of all critical use cases. The disclosed view is what the bank can see; the true share is "
               "known only because the data is synthetic.")
    provs = sorted(S4["true_share_pct"])
    disc = {x["provider"]: x["share_pct"] for x in A["conc"]["rows"]}
    fig = go.Figure()
    fig.add_bar(x=provs, y=[disc.get(p, 0.0) for p in provs], name="disclosed view", marker_color="#2563eb")
    fig.add_bar(x=provs, y=[S4["true_share_pct"][p] for p in provs], name="true share (synthetic)", marker_color="#f59e0b")
    fig.add_hline(y=40, line_dash="dash", line_color="#b91c1c", annotation_text="40% line (assumption)")
    fig.update_layout(barmode="group", height=340, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12), yaxis_title="% of critical use cases")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"VendorLens rates {S4['classes']['high']} vendors HIGH, {S4['classes']['medium']} MEDIUM and "
               f"{S4['classes']['low']} LOW. The truth file has {S4['true_high']} HIGH.")

    with st.expander("See the data"):
        st.markdown("**All 40 vendors, ranked by VendorLens risk**")
        st.dataframe(pd.DataFrame([{
            "Rank": x["rank"], "Vendor": x["vendor_id"], "Tier": x["criticality"], "Data": DATA_LABEL[x["data_access"]],
            "Provider": x["provider"], "Questionnaire": "pass" if x["checklist_pass"] else "fail",
            "Control score": x["control_score"], "Exit score": x["exit_score"], "Risk": x["risk"],
            "VendorLens": CLS[x["class"]], "Truth": CLS[x["true_risk"]]} for x in ROWS]),
            use_container_width=True, hide_index=True)

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Upstream model provider", "The company whose model a vendor's product runs on. Several vendors can share one."),
            ("Fourth party", "A supplier of your supplier. Here, the upstream model provider."),
            ("Concentration", "Share of the bank's critical use cases that depend on one provider."),
            ("HHI", "Sum of squared percentage shares, 0 to 10,000. Higher means more concentrated."),
            ("Evidence-adjusted control score", "The questionnaire score after each answer is weighed against a document or the contract."),
            ("Exit readiness", "An exit clause, a tested exit, and a modeled time to exit inside the allowed window."),
            ("Review cadence", "How often a vendor is reassessed, set by its tier. A HIGH vendor is reviewed twice as often."),
            ("Precision", "Of the vendors flagged HIGH, the share that are truly high risk."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a vendor register fed by the contract "
            "system and the questionnaire tool, an evidence store with issue dates and scope, a fourth-party map "
            "maintained from vendor disclosures, and a scoring service that writes each decision with its reasons to "
            "the third-party risk record. It is a design, not deployed; see `ARCHITECTURE.md`. Interlocks with "
            "other projects in this repo (designed, none built): InferenceLens (07) for spend per vendor, SwapBrief (13) for model swaps that "
            "change the fourth party, ControlMap (16) for vendor-model obligations, SchemaWatch (15) for vendor API "
            "changes, KillSwitch (25) for exit and fallback drills."
        )
    st.markdown(
        "<div class='vl-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Reference: the interagency "
        f"third-party risk guidance, <a href='{SR234_URL}' target='_blank'>SR 23-4</a>. As-of date {esc(AS_OF.isoformat())}.</div>",
        unsafe_allow_html=True,
    )
