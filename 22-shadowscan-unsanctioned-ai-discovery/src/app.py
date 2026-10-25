"""ShadowScan - finds the AI tools staff already use, ranked by data exposure.

Streamlit walkthrough. Pick one domain or one department, then step through the story:
  Step 1  Pick something to look at
  Step 2  Without ShadowScan - what the blocklist says (red), next to the truth (blue)
  Step 3  With ShadowScan - class, exposure rank, owner and next action (green)
  Step 4  Proof at scale - the same measures over the whole synthetic extract, with the known limit

All data is synthetic (data/_generate.py, seeded). The classifier is a set of plain rules: a catalog
lookup, a feed lookup, a path pattern and a byte-ratio test. There is no model anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_status_quo import load_all, true_label  # noqa: E402
from step_02_blocklist_baseline import summarize as summarize_step2  # noqa: E402
from step_03_deficiencies_exposed import summarize as summarize_step3  # noqa: E402
from step_04_with_shadowscan import BLOCK_TOP_RANK, analyze, describe_option, scenario_options  # noqa: E402

st.set_page_config(
    page_title="ShadowScan - Finds the AI tools staff already use",
    page_icon="🔦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/22-shadowscan-unsanctioned-ai-discovery/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.ss-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.ss-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.ss-hero h1 {color: #ffffff !important; font-size: 44px; line-height: 1.12; margin: 0 0 14px 0; font-weight: 700;}
.ss-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 820px; margin-bottom: 22px;}
.ss-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.ss-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.ss-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.ss-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.ss-card h3 {margin-top: 0; color: #0f172a;}
.ss-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
                border-radius: 6px; font-size: 12px; font-weight: 600; letter-spacing: 0.04em;
                text-transform: uppercase; margin-bottom: 10px;}

/* Verdict card */
.verdict-card {border-radius: 16px; padding: 26px 30px; margin-bottom: 18px; color: #fff;}
.verdict-pass {background: linear-gradient(135deg,#0a7c3f,#10b981);}
.verdict-flag {background: linear-gradient(135deg,#b91c1c,#ef4444);}
.verdict-review {background: linear-gradient(135deg,#b45309,#f59e0b);}
.verdict-card .vlabel {font-size: 13px; opacity: 0.9; letter-spacing: 0.08em; text-transform: uppercase;}
.verdict-card .vbig {font-size: 40px; font-weight: 800; line-height: 1.1; margin: 4px 0 14px 0;}
.verdict-card .vmetric {font-size: 20px; font-weight: 600;}
.verdict-card .vrow {display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px;}
.verdict-card .vchip {background: rgba(255,255,255,0.18); padding: 6px 12px; border-radius: 999px;
                      font-size: 13px; font-weight: 600;}
.verdict-card .vfind {margin-top: 12px; font-size: 15px; line-height: 1.5;}
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


@st.cache_resource
def load_analysis() -> dict:
    a = analyze(load_all(DATA_DIR))
    a["s2"] = summarize_step2(a["data"])
    a["s3"] = summarize_step3(a["data"])
    a["options"] = scenario_options(a)
    a["described"] = {o["key"]: describe_option(a, o) for o in a["options"]}
    return a


A = load_analysis()
DATA = A["data"]
S = A["summary"]
S2 = A["s2"]
S3 = A["s3"]
OPTIONS = A["options"]

# Option labels are plain strings; a dict maps label -> option.
LABEL_TO_OPT = {o["label"]: o for o in OPTIONS}
LABELS = list(LABEL_TO_OPT)

if "step" not in st.session_state:
    st.session_state.step = 1


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


def bullets(lines) -> str:
    return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in lines) + "</ul>"


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='ss-hero'>
  <div class='brand'>🔦 ShadowScan</div>
  <h1>Finds {S['found_domains']} of {S['true_domains']} unapproved AI tools, ranked by data exposure, not the {S['blocklist_domains_hit']} a blocklist hits.</h1>
  <div class='sub'>A blocklist counts hits on domains it already knows. ShadowScan classifies every domain and path in the logs, ranks what it finds by data exposure, and says block, sanction or coach.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>No model: plain rules</span>
    <span class='pill'>{len(DATA['proxy']):,} proxy rows · {len(DATA['dns']):,} DNS rows · {len(DATA['users'])} staff</span>
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
# STEP 1 - pick a domain or a department
# ---------------------------------------------------------------------------
n_dom = sum(1 for o in OPTIONS if o["kind"] == "domain")
n_dept = len(OPTIONS) - n_dom
st.markdown(
    "<div class='ss-card'><span class='ss-step-label'>Step 1</span>"
    "<h3>Pick a domain or a department</h3>"
    f"<p class='muted'>{n_dom} domains and {n_dept} departments. The first {BLOCK_TOP_RANK} are the highest-exposure "
    "domains ShadowScan found; the rest are cases worth a look, then the departments.</p></div>",
    unsafe_allow_html=True,
)
if "choice" not in st.session_state:
    st.session_state.choice = LABELS[0]
st.session_state.choice = st.selectbox(
    "Pick one:",
    LABELS,
    index=LABELS.index(st.session_state.choice),
    label_visibility="collapsed",
)
opt = LABEL_TO_OPT[st.session_state.choice]
D = A["described"][opt["key"]]
st.markdown(
    f"<div class='ss-card'><b>{esc(D['title'])}</b><br><span class='muted'>{esc(D['meta'])}</span></div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='muted'>Synthetic data, no model. Every domain is invented and ends in .example: nothing here is a real "
    "bank, product, vendor or log. The generator decided which domains are AI tools, so the truth is known. "
    "The classifier is plain rules, not a model. Read the numbers as a test set, not as how often real staff use AI tools.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 2 - Without ShadowScan: the blocklist
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='ss-card'><span class='ss-step-label'>Step 2</span>"
        "<h3>Without ShadowScan - a blocklist counts hits</h3>"
        "<p class='muted'>The proxy report ranks domains by hits and a static list flags the ones it knows. "
        "Here is what each says about this pick, next to what really happened.</p></div>",
        unsafe_allow_html=True,
    )
    red = (
        f"<div class='bot-bad'><b>What the report and the blocklist say ({esc(D['red']['tag'])}):</b>"
        + bullets(D["before"][:1] + D["red"]["lines"])
        + "<div class='small'>" + esc(D["before"][1]) + "</div></div>"
    )
    blue = "<div class='bot-truth'><b>Source of truth - what really happened (generator):</b>" + bullets(D["blue"]) + "</div>"
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        if opt["kind"] == "domain":
            dom = opt["target"]
            rows = []
            for s in DATA["proxy"]:
                if s["domain"] == dom:
                    rows.append({"row": s["sid"], "hour": s["hour"], "user": s["user"], "dept": s["dept"], "path": s["path"],
                                 "bytes_out": s["out"], "bytes_in": s["inn"], "client": s["client"],
                                 "blocklist": "hit" if s["sid"] in A["bl_hits"] else "no hit",
                                 "truth": true_label(DATA, s)})
                if len(rows) >= 25:
                    break
            st.markdown("**First proxy rows for this domain (up to 25)**")
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.markdown("No proxy rows: this domain appears only in DNS.")
            ents = D["card"]["blocklist_entries"]
            st.markdown("**Blocklist entries that matched:** " + (", ".join(f"{k}: {v} sessions" for k, v in ents.items()) or "none"))
        else:
            c = D["card"]
            st.dataframe(pd.DataFrame([{
                "department": c["name"], "sensitivity weight": c["weight"], "staff": c["staff"],
                "staff using AI outside the catalog": c["staff_using"],
                "unsanctioned AI sessions": c["unsanctioned_sessions"], "found by blocklist": c["blocklist_found"],
                "found by ShadowScan": c["shadow_found"], "off-network sessions (truth only)": c["off_sessions"]}]),
                use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With ShadowScan
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    st.markdown(
        "<div class='ss-card'><span class='ss-step-label'>Step 3</span>"
        "<h3>With ShadowScan - classify, rank by exposure, recommend</h3>"
        "<p class='muted'>Each domain and path is matched to the catalog, the feed, a generation-style path or an "
        "upload-heavy size ratio, then ranked by bytes out, department sensitivity and distinct users.</p></div>",
        unsafe_allow_html=True,
    )
    G = D["green"]
    tone = {"good": "verdict-pass", "warn": "verdict-review", "bad": "verdict-flag"}[G["tone"]]
    st.markdown(
        f"<div class='verdict-card {tone}'>"
        f"<div class='vlabel'>With ShadowScan - {esc(D['title'])}</div>"
        f"<div class='vbig'>{esc(G['tag'])}</div>"
        + "".join(f"<div class='vfind'>{esc(x)}</div>" for x in G["lines"])
        + (f"<div class='vtldr'><b>Next action:</b> {esc(G['next'])}</div>" if G["next"] else "")
        + "</div>",
        unsafe_allow_html=True,
    )
    if G["note"]:
        st.markdown(f"<div class='limit-note'>{esc(G['note'])}</div>", unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Exposure ranking (all discovered items)**")
        st.caption("Exposure index = weighted MB out x distinct staff, proxy rows only. A ranking index, not a measure of leaked data.")
        st.dataframe(pd.DataFrame([{
            "rank": r["rank"], "domain": r["domain"], "kind": "AI feature in approved SaaS" if r["kind"].startswith("embedded") else "AI tool",
            "evidence": r["evidence"], "staff": r["users"], "MB out": round(r["mb_out"], 1), "exposure": round(r["exposure"]),
            "owner": r["owner"], "high-sensitivity share": f"{r['sens_share']*100:.0f}%", "action": r["action"]}
            for r in A["items"]]), use_container_width=True, hide_index=True)
        if opt["kind"] == "domain":
            cl = D["card"]["shadow_classes"]
            st.markdown("**ShadowScan classes for this pick's sessions:** " + ", ".join(f"{k}: {v}" for k, v in cl.items()))

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    u = S["unsanctioned"]
    em = S["embedded"]
    st.markdown(
        "<div class='ss-card'><span class='ss-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same checks over the whole synthetic extract: {S['visible_sessions']:,} log rows, "
        f"{S['unsanctioned_visible']:,} unsanctioned AI sessions and {S['emb_visible']:,} AI-feature sessions inside approved SaaS.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without ShadowScan: blocklist</div>"
        f"<div class='vbig'>{S['blocklist_tp']:,} of {S['unsanctioned_visible']:,}</div>"
        "<div class='vmetric'>unsanctioned AI sessions found</div>"
        f"<div class='vtldr'>{S['blocklist_domains_hit']} of {S['true_domains']} unapproved AI domains are ever hit.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Without ShadowScan: false alarms</div>"
        f"<div class='vbig'>{S2['fp_lookalike']:,}</div>"
        "<div class='vmetric'>look-alike sessions flagged</div>"
        f"<div class='vtldr'>{S2['lookalike_domains_hit']} harmless domains whose names contain 'ai'. Precision of the list: {S2['precision']*100:.1f}%.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With ShadowScan: discovery</div>"
        f"<div class='vbig'>{u['tp']:,} of {S['unsanctioned_visible']:,}</div>"
        "<div class='vmetric'>unsanctioned AI sessions found</div>"
        f"<div class='vtldr'>Recall {u['recall']*100:.1f}%, precision {u['precision']*100:.1f}%. {S['beyond_blocklist']:,} found that the list missed.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With ShadowScan: ranking</div>"
        f"<div class='vbig'>{S['rank_overlap']} of 10</div>"
        "<div class='vmetric'>top-10 by exposure match the truth ranking</div>"
        f"<div class='vtldr'>The hit-count top 10 shares {S3['d5']['overlap']} of 10 with it and holds {S3['d5']['exposure_share_top_hits']*100:.1f}% of total exposure.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    miss = ", ".join(d.replace(".example", "") for d in S["missed_domains"])
    fp = ", ".join(d.replace(".example", "") for d in S["fp_domains"])
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>{S['off_sessions']} sessions on personal devices or off the network ({S['off_share']*100:.1f}% of all unsanctioned AI sessions) are in no log. No rule can find them.</li>"
        f"<li>{S['miss_sessions']} unsanctioned AI sessions are missed: {esc(miss)} look ordinary (small payloads, plain paths).</li>"
        f"<li>Embedded AI inside approved SaaS: {em['tp']:,} of {S['emb_visible']:,} sessions found ({em['recall']*100:.1f}%). DNS rows carry no path, and some vendors use paths a pattern cannot match.</li>"
        f"<li>{S['fp_sessions']} sessions on {len(S['fp_domains'])} benign domains ({esc(fp)}) were called unsanctioned AI by the path and ratio rules; one ranks in the top 3 by exposure.</li>"
        f"<li>Exposure leaves out {S['dns_unmeasured_mb']:.1f} MB of DNS-only traffic that has no size in the log.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Hit count versus data exposure**")
    st.caption("Share of all discovered sessions (hits) and of total exposure for the 12 highest-exposure items.")
    items = A["items"]
    tot_s = sum(r["sessions"] for r in items)
    tot_e = sum(r["exposure"] for r in items)
    top = items[:12]
    fig = go.Figure()
    fig.add_bar(x=[r["domain"].replace(".example", "") for r in top], y=[r["sessions"] / tot_s * 100 for r in top],
                name="share of hits (%)", marker_color="#b91c1c")
    fig.add_bar(x=[r["domain"].replace(".example", "") for r in top], y=[r["exposure"] / tot_e * 100 for r in top],
                name="share of exposure (%)", marker_color="#1f5fb0")
    fig.update_layout(barmode="group", height=360, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=1.12), xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)
    ac = S["actions"]
    st.caption(f"Next actions across the {S['items']} discovered items: {ac.get('block', 0)} block, {ac.get('sanction', 0)} sanction, "
               f"{ac.get('coach', 0)} coach. Thresholds are assumptions of a modeled bank.")

    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("Sanctioned catalog", "The tools the bank approved, with the data class each is approved for."),
            ("Unsanctioned AI", "An AI tool on a domain that is not in the catalog."),
            ("Embedded AI", "An AI feature inside a product the bank approved as ordinary software."),
            ("Known-AI feed", "A list of domains known to be AI services. Partly out of date."),
            ("Exposure", "Weighted MB out x distinct staff, from the proxy log. A ranking index."),
            ("Block, sanction, coach", "Stop it, take it to intake and due diligence, or guide the department to an approved tool."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is a log collector on the proxy and DNS "
            "resolvers, a classifier service that holds the catalog and feed, an exposure ranker, and a review queue "
            "that routes sanction requests to intake and due diligence. It is a design, not deployed; see `ARCHITECTURE.md`. "
            "Related projects: TierGate (11) is the path to sanction a tool, PromptShield (06) defends sanctioned models "
            "from injection. The interlocks with VendorLens (18), ControlMap (16) and ScopeKeeper (23) are designed, none built."
        )
    st.markdown(
        "<div class='ss-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Framework reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>.</div>",
        unsafe_allow_html=True,
    )
