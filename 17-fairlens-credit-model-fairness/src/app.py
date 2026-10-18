"""FairLens - a fairness test pack for a credit-decision model.

Streamlit walkthrough. Pick a group and a cutoff, then step through the story:
  Step 1  Pick a scenario (one group at one cutoff)
  Step 2  Without FairLens - the accuracy-only view says the model is fine (red), and what the
          synthetic data says (blue)
  Step 3  With FairLens - the verdict for that group and the six-test pack at that cutoff (green)
  Step 4  Proof at scale - the pack at the policy cutoff, the cutoff sweep and what it still
          gets wrong

All data is synthetic (data/_generate.py, seeded). The scorecard is a stub, not a trained model;
every test is a count, a ratio, a sort or a seeded resample. No model is used anywhere here.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_model_card_only import (GROUPS, POLICY_CUTOFF, default_rates, model_card, prepare)  # noqa: E402
from step_02_accuracy_baseline import accuracy_by_group  # noqa: E402
from step_03_deficiencies_exposed import (AIR_SCREEN, REASONS_LISTED, bootstrap_air, crossing, sweep)  # noqa: E402
from step_04_with_fairlens import (label_noise_stress, pick_cutoffs, run_pack, scenario, utility)  # noqa: E402

st.set_page_config(
    page_title="FairLens - A fairness test pack that finds the gap accuracy hides",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/17-fairlens-credit-model-fairness/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.fl-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.fl-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.fl-hero h1 {color: #ffffff !important; font-size: 42px; line-height: 1.14; margin: 0 0 14px 0; font-weight: 700;}
.fl-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.fl-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.fl-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.fl-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.fl-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.fl-card h3 {margin-top: 0; color: #0f172a;}
.fl-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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

/* Bot vs truth panel */
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


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}%"


@st.cache_resource
def load_analysis() -> dict:
    prep = prepare(DATA_DIR)
    sw = sweep(prep)
    cp = crossing(sw)
    return {"prep": prep, "sweep": sw, "crossing": cp, "cutoffs": pick_cutoffs(cp),
            "card": model_card(prep), "acc_by_group": accuracy_by_group(prep["rows"]),
            "defaults": default_rates(prep), "labels": label_noise_stress(prep)}


A = load_analysis()
PREP = A["prep"]


@st.cache_resource
def pack_at(cutoff: int) -> dict:
    bs = bootstrap_air(PREP, cutoff)
    pack = run_pack(PREP, bs, cutoff)
    return {"pack": pack, "boot": bs, "scn": {g: scenario(PREP, g, cutoff, bs) for g in GROUPS}}


BASE = pack_at(POLICY_CUTOFF)
BASE_T = {t["id"]: t for t in BASE["pack"]["tests"]}
UTIL = utility(BASE["pack"])
MC = A["card"]

CUTOFF_LABELS = {}
for _c in A["cutoffs"]:
    _tag = " - policy cutoff" if _c == POLICY_CUTOFF else (" - last cutoff where the screen holds" if _c == A["crossing"] else "")
    CUTOFF_LABELS[f"{_c} points{_tag}"] = _c
CUTOFF_OPTIONS = list(CUTOFF_LABELS)
DEFAULT_CUTOFF = next(k for k, v in CUTOFF_LABELS.items() if v == POLICY_CUTOFF)

VERDICT_CLASS = {"FAIL": "verdict-flag", "REVIEW": "verdict-review", "PASS": "verdict-pass", "REFERENCE": "verdict-pass"}
VERDICT_WORD = {"FAIL": "FAIL - CAUGHT", "REVIEW": "REVIEW - FLAGGED", "PASS": "PASS", "REFERENCE": "REFERENCE GROUP"}

if "step" not in st.session_state:
    st.session_state.step = 1


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
n_tests = len(BASE["pack"]["tests"])
st.markdown(
    f"""
<div class='fl-hero'>
  <div class='brand'>⚖️ FairLens</div>
  <h1>{n_tests} fairness tests that find the {BASE_T['T1']['spread_pts']:.1f}-point approval gap behind {pct(MC['accuracy'])} accuracy, not one accuracy score.</h1>
  <div class='sub'>The model card reports one accuracy figure. FairLens adds adverse impact by group, a cutoff sweep, a proxy test and a reason-code check, each with a verdict.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>Stub scorecard, not a model</span>
    <span class='pill'>{MC['applicants']:,} applicants · {len(GROUPS)} groups · {n_tests} tests</span>
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
# STEP 1 - pick a scenario
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='fl-card'><span class='fl-step-label'>Step 1</span>"
    "<h3>Pick a group and a cutoff</h3>"
    "<p class='muted'>Three synthetic groups with a small third group on purpose, and the cutoff the scorecard uses to approve. "
    "The default is the group and cutoff with the clearest gap.</p></div>",
    unsafe_allow_html=True,
)
c1, c2 = st.columns(2)
with c1:
    group = st.selectbox("Group", ["Group B", "Group C", "Group A"], index=0)
with c2:
    cutoff_label = st.selectbox("Cutoff", CUTOFF_OPTIONS, index=CUTOFF_OPTIONS.index(DEFAULT_CUTOFF))
cutoff = CUTOFF_LABELS[cutoff_label]

AT = pack_at(cutoff)
SC = AT["scn"][group]
PACK = AT["pack"]
T = {t["id"]: t for t in PACK["tests"]}
REF = SC["reference"]
REF_SC = AT["scn"][REF]
ACC = {b["group"]: b["accuracy"] for b in accuracy_by_group(PREP["rows"], cutoff)}

st.markdown(
    f"<p class='muted'>Synthetic data, stub scorecard, no model. The groups are labels the generator made up and encode no real "
    f"protected class; nothing here is a real bank, applicant or postcode. AIR is a group's approval rate divided by the highest "
    f"group approval rate; {AIR_SCREEN:.2f} is a screening convention from employment guidance, not a credit-law standard or a legal finding. "
    f"Thresholds are assumptions of a modeled bank.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - Without FairLens
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='fl-card'><span class='fl-step-label'>Step 2</span>"
        "<h3>Without FairLens - the accuracy view says the model is fine</h3>"
        "<p class='muted'>This is what a reviewer sees on the model card and in an accuracy-by-group check. "
        "Next to it is what the synthetic data says about the same group.</p></div>",
        unsafe_allow_html=True,
    )
    accs = list(ACC.values())
    gap_to_best = 100 * (max(accs) - ACC[group])
    ov = SC["overall"]
    red = (
        "<div class='bot-bad'><b>What the accuracy-only view shows (LOOKS FINE, MISSED):</b>"
        "<ul>"
        f"<li>Model card at cutoff {cutoff}: <b>{pct(ov['accuracy'])}</b> overall accuracy, {pct(ov['approval_rate'])} approved. Fairness tests run: {UTIL['tests_baseline']}.</li>"
        f"<li>{esc(group)}: <b>{pct(ACC[group])}</b> accuracy, {gap_to_best:.1f} points below the best group. Nothing flags it.</li>"
        f"<li>Nothing says how many {esc(group)} applicants are approved, or how that compares with {esc(REF)}.</li>"
        "</ul>"
        "<div class='small'>Accuracy-style metrics describe how often the scorecard agrees with the outcome. They are silent on who is approved.</div></div>"
    )
    dr = A["defaults"]
    pb_max = PREP["card"]["max"]["postcode_band"]
    tot_max = MC["max_points"]
    if SC["is_reference"]:
        gap_line = (f"<li>{esc(group)} is the reference group: highest approval rate, {pct(SC['approval_rate'])}. "
                    f"AIR is 1.000 by definition. Pick Group B or Group C to see a gap.</li>")
    else:
        gap_line = (f"<li>{esc(group)} approval rate <b>{pct(SC['approval_rate'])}</b> against {pct(REF_SC['approval_rate'])} for {esc(REF)}: "
                    f"AIR <b>{SC['air']:.3f}</b>, 95% interval {SC['lo']:.3f} to {SC['hi']:.3f}, against the {AIR_SCREEN:.2f} screen.</li>")
    blue = (
        "<div class='bot-truth'><b>Source of truth - what the synthetic data says:</b>"
        "<ul>"
        + gap_line +
        f"<li>Default rate (the generator decided who defaulted): {esc(group)} {pct(dr[group]['rate'])}, {esc(REF)} {pct(dr[REF]['rate'])}. "
        "Part of any gap is legitimate risk. The ablation test says how much is not.</li>"
        f"<li>postcode_band is not an input to default in the generator, yet it carries up to {pb_max} of the scorecard's {tot_max} points.</li>"
        "</ul></div>"
    )
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown(f"**Group results at cutoff {cutoff}**")
        gdf = pd.DataFrame([{
            "Group": g, "Applicants": AT["scn"][g]["n"], "Approved": AT["scn"][g]["approved"],
            "Approval rate": pct(AT["scn"][g]["approval_rate"]), "Accuracy": pct(ACC[g]),
            "AIR": "reference" if AT["scn"][g]["is_reference"] else f"{AT['scn'][g]['air']:.3f}",
            "95% interval": "-" if AT["scn"][g]["is_reference"] else f"{AT['scn'][g]['lo']:.3f} to {AT['scn'][g]['hi']:.3f}",
            "Default rate": pct(dr[g]["rate"]),
        } for g in GROUPS])
        st.dataframe(gdf, use_container_width=True, hide_index=True)
        st.caption(f"Computed by the same functions as step_03 and step_04 in src/. {AT['boot']['n_boot']:,} bootstrap resamples, seed {AT['boot']['seed']}.")

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With FairLens
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='fl-card'><span class='fl-step-label'>Step 3</span>"
        f"<h3>With FairLens - {esc(group)} at cutoff {cutoff} is tested, not assumed</h3>"
        "<p class='muted'>FairLens computes the approval rate and AIR with an interval, then runs six tests at this cutoff and "
        "returns PASS, REVIEW or FAIL for each.</p></div>",
        unsafe_allow_html=True,
    )
    chips = "".join(
        f"<span class='vchip'>{esc(t['id'])} {esc(t['name'])}: {esc(t['verdict'])}</span>" for t in PACK["tests"])
    rm = SC["reasons"]
    if rm["top"]:
        reason_line = ("Principal reasons given to declined " + esc(group) + " applicants: "
                       + ", ".join(f"{esc(r['code'])} {pct(r['share'])}" for r in rm["top"])
                       + f" (of {rm['declined']:,} declines).")
    else:
        reason_line = "No declined applicants in this group at this cutoff."
    if SC["is_reference"]:
        metric = f"Reference group. Approval rate {pct(SC['approval_rate'])}; AIR 1.000 by definition."
        tldr = (f"The lowest AIR among the other groups at this cutoff is {SC['min_air']:.3f} ({esc(SC['min_group'])}). "
                "Pick Group B or Group C to see their verdict.")
    else:
        metric = f"AIR {SC['air']:.3f}, 95% interval {SC['lo']:.3f} to {SC['hi']:.3f}, screen {AIR_SCREEN:.2f}"
        tldr = {"FAIL": "The whole interval sits below the screen: this is a gap, not sampling noise.",
                "REVIEW": "The interval straddles the screen. With this few applicants the data cannot say which side the group is on, so a person reviews it.",
                "PASS": "The whole interval is at or above the screen."}[SC["verdict"]]
    st.markdown(
        "<div class='verdict-card verdict-pass'>"
        f"<div class='vlabel'>With FairLens - {esc(group)} - cutoff {cutoff}</div>"
        f"<div class='vbig'>{esc(VERDICT_WORD[SC['verdict']])}</div>"
        f"<div class='vmetric'>{esc(metric)}</div>"
        f"<div class='vrow'>{chips}</div>"
        f"<div class='vtldr'><b>Reading:</b> {esc(tldr)}</div>"
        f"<div class='vtldr'>{reason_line}</div></div>",
        unsafe_allow_html=True,
    )
    if SC["verdict"] == "REVIEW" and not SC["is_reference"] and group == "Group C":
        st.markdown("<div class='limit-note'>Small group on purpose: Group C has "
                    f"{SC['n']} applicants, so its interval is wide. FairLens reports REVIEW rather than choosing a side.</div>",
                    unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown(f"**The six tests at cutoff {cutoff}**")
        tdf = pd.DataFrame([{"Test": t["id"], "Name": t["name"], "Verdict": t["verdict"], "Numbers": t["numbers"], "Rule": t["rule"]}
                            for t in PACK["tests"]])
        st.dataframe(tdf, use_container_width=True, hide_index=True)
        st.caption("Thresholds are assumptions of a modeled bank, not legal advice.")
        t4 = T["T4"]
        st.markdown("**Proxy ablation: AIR with the postcode_band points neutralized**")
        st.dataframe(pd.DataFrame([{"Group": g, "AIR before": f"{t4['air_before'][g]:.3f}", "AIR after": f"{t4['air_after'][g]:.3f}"}
                                   for g in GROUPS]), use_container_width=True, hide_index=True)
        t5 = T["T5"]
        st.markdown("**Reason codes: matched pairs of declined applicants**")
        pr = t5["pairs"]
        st.dataframe(pd.DataFrame(
            [{"Pairs": f"{g} vs {REF}", "Matched pairs": p["pairs"], "Top reason differs": p["differ"], "Share": pct(p["share"])}
             for g, p in pr["pairs"].items()]
            + [{"Pairs": f"Control: {REF} vs {REF}", "Matched pairs": pr["control"]["pairs"],
                "Top reason differs": pr["control"]["differ"], "Share": pct(pr["control"]["share"])}]),
            use_container_width=True, hide_index=True)

    lines = [f"# FairLens test pack: {group} at cutoff {cutoff}", "",
             "Synthetic data and a stub scorecard (not a model). Not a real bank, applicant or finding.", "",
             "| Test | Verdict | Numbers |", "| --- | --- | --- |"]
    lines += [f"| {t['id']} {t['name']} | {t['verdict']} | {t['numbers']} |" for t in PACK["tests"]]
    st.download_button("Download the test pack (Markdown)", "\n".join(lines),
                       file_name=f"fairlens_pack_cutoff_{cutoff}.md", mime="text/markdown")

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    bt = BASE_T
    t2, t4b, t6 = bt["T2"], bt["T4"], bt["T6"]
    flagged = UTIL["flagged"]
    st.markdown(
        "<div class='fl-card'><span class='fl-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The whole synthetic set at the policy cutoff ({POLICY_CUTOFF} points): {MC['applicants']:,} applicants, "
        f"{len(GROUPS)} groups, {n_tests} tests.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without FairLens: the model card</div>"
        f"<div class='vbig'>{pct(MC['accuracy'])}</div>"
        f"<div class='vmetric'>accuracy, with {UTIL['tests_baseline']} of {n_tests} fairness tests run</div>"
        f"<div class='vtldr'>Behind it, approval rates run from {pct(min(bt['T1']['rates'].values()))} to {pct(max(bt['T1']['rates'].values()))}.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>With FairLens: AIR by group</div>"
        f"<div class='vbig'>{t2['min_air']:.3f}</div>"
        f"<div class='vmetric'>lowest AIR ({esc(t2['min_group'])}), screen {AIR_SCREEN:.2f}</div>"
        f"<div class='vtldr'>{esc(t6['group'])}'s interval, {t6['lo']:.3f} to {t6['hi']:.3f}, straddles the screen: REVIEW.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With FairLens: the pack</div>"
        f"<div class='vbig'>{flagged} of {n_tests}</div>"
        f"<div class='vmetric'>tests return REVIEW or FAIL</div>"
        f"<div class='vtldr'>The reason-code test passes. The pack does not flag everything.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With FairLens: the proxy test</div>"
        f"<div class='vbig'>{t4b['before'][0]:.3f} to {t4b['after'][0]:.3f}</div>"
        f"<div class='vmetric'>lowest AIR when postcode points are neutral</div>"
        f"<div class='vtldr'>Accuracy {pct(t4b['acc_before'])} to {pct(t4b['acc_after'])}. Truth known: postcode has no effect on default here.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    px = bt["T5"]["proxy"]
    ln = A["labels"]
    first_pass = next((x for x in ln if x["passes"]), None)
    lim = ("<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
           f"<li>AIR is a screening statistic, not a legal finding. The {AIR_SCREEN:.2f} line comes from employment guidance (29 CFR 1607) and is a screening convention here.</li>"
           "<li>The search for less discriminatory alternatives is one ablation, not a search. A second proxy would not be found.</li>")
    if first_pass:
        lim += (f"<li>Real credit data has no group labels. With {pct(first_pass['wrong_share'])} of labels wrong at random, the AIR screen passes "
                f"(lowest AIR {first_pass['min_air']:.3f}) when it fails on the true labels ({ln[0]['min_air']:.3f}). A pass that depends on label quality is not evidence.</li>")
    lim += (f"<li>The reason-code pair check passes ({bt['T5']['pairs']['excess_pts']:+.1f} points against its control) while {px['proxy_declines']} "
            f"declines are caused by the postcode points. With {REASONS_LISTED} reasons listed, {px['named']} of them name the postcode band.</li>"
            "</ul></div>")
    st.markdown(lim, unsafe_allow_html=True)

    st.markdown("**Where the screen holds: lowest AIR by cutoff**")
    st.caption("Lowest AIR among the non-reference groups at each cutoff, with the 0.80 screen. The policy cutoff sits to the right of the last cutoff that holds.")
    xs = [r["cutoff"] for r in A["sweep"]]
    ys = [r["min_air"] for r in A["sweep"]]
    fig = go.Figure()
    fig.add_scatter(x=xs, y=ys, mode="lines", name="lowest AIR", line=dict(color="#1f5fb0", width=3))
    fig.add_hline(y=AIR_SCREEN, line_dash="dot", line_color="#b91c1c", annotation_text=f"screen {AIR_SCREEN:.2f}")
    fig.add_vline(x=POLICY_CUTOFF, line_dash="dash", line_color="#475569", annotation_text="policy cutoff")
    fig.add_vline(x=A["crossing"], line_dash="dash", line_color="#059669", annotation_text="last cutoff that holds")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                      xaxis_title="cutoff (points)", yaxis_title="lowest AIR", yaxis=dict(range=[float(np.floor(min(ys) * 10) / 10), 1.02]))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Approval rate", "Share of a group's applicants whose score is at or above the cutoff."),
            ("AIR", "Adverse impact ratio: a group's approval rate divided by the highest group approval rate."),
            ("Screen", f"{AIR_SCREEN:.2f}, the four-fifths convention from employment guidance, used here only to decide what to look at."),
            ("Proxy", "An input that stands in for group. Here, postcode_band is correlated with group by construction."),
            ("Ablation", "Replace one input's points with a neutral value and re-run the tests."),
            ("Reason code", "A plain-language reason given to a declined applicant, from the points lost against the maximum."),
            ("Bootstrap interval", "Resample applicants with replacement many times; the middle 95% of the AIR values."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a scheduled job that reads decisions and outcomes from "
            "the model's scoring log, a group-inference step the prototype does not have, a test runner that writes verdicts and "
            "evidence to a store, and a review queue for REVIEW and FAIL. It is a design, not deployed; see `ARCHITECTURE.md`. "
            "Related projects, all designed and none built: ControlMap (16), EvalForge (04), DriftSentinel (02) and TierGate (11)."
        )
    st.markdown(
        "<div class='fl-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Framework reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
