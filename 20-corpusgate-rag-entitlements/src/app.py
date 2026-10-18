"""CorpusGate - entitlement-aware retrieval for an internal AI assistant.

Streamlit walkthrough. Pick one question asked by one user, then step through the story:
  Step 1  Pick a question (about 15, each chosen by a rule to show a different failure)
  Step 2  Without CorpusGate - the results a relevance-only system returns (some the user may not
          read) and the user's real entitlement
  Step 3  With CorpusGate - results filtered before ranking, personal data held or redacted
  Step 4  Proof at scale - the same measures over all 200 queries, with the known limit

All data is synthetic (data/_generate.py, seeded). The retriever is a stub (plain TF-IDF, not a
model); there is no model anywhere in this app.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from step_01_no_access_control import load_all  # noqa: E402
from step_03_deficiencies_exposed import deficiencies  # noqa: E402
from step_04_with_corpusgate import analyze, story_detail  # noqa: E402

st.set_page_config(
    page_title="CorpusGate - Retrieval that respects who may read what",
    page_icon="🚪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_DIR = Path(__file__).parent.parent / "data"

GITHUB_URL = "https://github.com/Vj-shipped-anyway/ai-pm-portfolio"
LINKEDIN_URL = "https://www.linkedin.com/in/vijaysaharan/"
README_URL = GITHUB_URL + "/blob/main/20-corpusgate-rag-entitlements/README.md"
NIST_URL = "https://www.nist.gov/itl/ai-risk-management-framework"
OWASP_URL = "https://genai.owasp.org/llm-top-10/"

# ---------------------------------------------------------------------------
# Theme - dark gradient hero, light body, contrast-preserving CSS (mirrors HalluGuard)
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}

/* Hero block */
.cg-hero {
  background: linear-gradient(135deg, #0b1f3a 0%, #163a6c 55%, #1f5fb0 100%);
  border-radius: 18px;
  padding: 36px 40px 32px 40px;
  color: #ffffff;
  margin-bottom: 28px;
}
.cg-hero .brand {font-size: 26px; font-weight: 600; opacity: 0.92; margin-bottom: 12px;}
.cg-hero h1 {color: #ffffff !important; font-size: 40px; line-height: 1.15; margin: 0 0 14px 0; font-weight: 700;}
.cg-hero .sub {font-size: 17px; line-height: 1.5; opacity: 0.93; max-width: 860px; margin-bottom: 22px;}
.cg-hero .pills {display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px;}
.cg-hero .pill {background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
                color: #fff; padding: 6px 12px; border-radius: 999px; font-size: 13px;}
.cg-hero .pill a {color: #fff; text-decoration: none;}

/* Body cards */
.cg-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
          padding: 22px 26px; margin-bottom: 18px; box-shadow: 0 1px 2px rgba(15,23,42,0.04);}
.cg-card h3 {margin-top: 0; color: #0f172a;}
.cg-step-label {display: inline-block; background: #1f5fb0; color: #fff; padding: 3px 10px;
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
.verdict-card ul {margin: 10px 0 0 18px; padding: 0;}
.verdict-card li {line-height: 1.5; margin-bottom: 6px;}

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

/* Red / blue / green panels */
.bot-bad {background: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #dc2626;
          border-radius: 10px; padding: 14px 18px; color: #7f1d1d;}
.bot-good {background: #ecfdf5; border: 1px solid #bbf7d0; border-left: 4px solid #059669;
           border-radius: 10px; padding: 14px 18px; color: #065f46;}
.bot-truth {background: #eff6ff; border: 1px solid #bfdbfe; border-left: 4px solid #2563eb;
            border-radius: 10px; padding: 14px 18px; color: #1e3a8a;}
.bot-bad ul, .bot-truth ul, .bot-good ul {margin: 8px 0 0 18px; padding: 0;}
.bot-bad li, .bot-truth li, .bot-good li {line-height: 1.5; margin-bottom: 8px;}
.bot-bad .small, .bot-truth .small, .bot-good .small {font-size: 13px; opacity: 0.85; margin-top: 8px;}
.mark {display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: 0.05em; padding: 1px 7px;
       border-radius: 5px; margin-left: 6px; color: #fff;}
.mark-bad {background: #dc2626;}
.mark-ok {background: #059669;}
.mark-warn {background: #d97706;}
.lab {display: inline-block; font-size: 11px; padding: 0 6px; border-radius: 5px; background: rgba(15,23,42,0.08);
      margin-left: 6px;}

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
    a["def"] = deficiencies(a["data"], a["sq"])
    return a


A = load_analysis()
S = A["summary"]
DEF = A["def"]
STORIES = A["stories"]
LABEL_TO_QID = {s["label"]: s["query_id"] for s in STORIES}
LABELS = list(LABEL_TO_QID)

if "step" not in st.session_state:
    st.session_state.step = 1


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def doc_line(x: dict, mark: str = "", extra: str = "") -> str:
    lab = x["shown_label"] if x["shown_label"] == x["true_label"] else f"{x['shown_label']}, really {x['true_label']}"
    return (f"<li><b>{esc(x['doc_id'])}</b><span class='lab'>{esc(lab)}</span> {esc(x['title'])}{mark}{extra}</li>")


# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='cg-hero'>
  <div class='brand'>🚪 CorpusGate</div>
  <h1>Retrieval that respects who may read what, not just what matches: {S['leaked_before']} leaks cut to {S['leaked_after']}.</h1>
  <div class='sub'>Without an entitlement check, {S['leaked_before']} of {S['results']:,} test results went to a user who may not read them. CorpusGate filters before ranking and leaves {S['leaked_after']}, all from ACL changes after its last sync.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>Synthetic data</span>
    <span class='pill'>Stub retriever, not a model</span>
    <span class='pill'>{S['n_docs']} documents · {S['n_users']} users · {S['n_queries']} queries</span>
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
# STEP 1 - pick a question
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='cg-card'><span class='cg-step-label'>Step 1</span>"
    "<h3>Pick a question and the person asking it</h3>"
    f"<p class='muted'>{len(STORIES)} of the {S['n_queries']} test questions, each picked by a rule to show a different failure. "
    "The first one is the plainest: a restricted document in the top 5.</p></div>",
    unsafe_allow_html=True,
)
if "story_choice" not in st.session_state:
    st.session_state.story_choice = LABELS[0]
st.session_state.story_choice = st.selectbox(
    "Question:", LABELS, index=LABELS.index(st.session_state.story_choice), label_visibility="collapsed")
qid = LABEL_TO_QID[st.session_state.story_choice]
D = story_detail(A, qid)
U = D["user"]

st.markdown(
    f"<div class='cg-card'><b>{esc(D['query_id'])}</b> asked by <code>{esc(U['id'])}</code> "
    f"({esc(U['dept'])}, {esc(U['role'])}): <i>&ldquo;{esc(D['text'])}&rdquo;</i><br>"
    f"<span class='muted'>This user may read {U['readable']} of the {U['docs']} documents. "
    f"{D['n_relevant']} documents are relevant to the question.</span></div>",
    unsafe_allow_html=True,
)
with st.expander("How to read the numbers"):
    st.markdown(
        "Every number here is printed by a script in `src/` on synthetic data: the generator decided every "
        "access list, so the truth is known. The test set is built so that each failure appears; the counts "
        "describe this set, not how often real systems fail. The retriever is a stub (plain TF-IDF), not a model. "
        "Modeled numbers say so where they appear."
    )

if st.session_state.step < 2:
    if st.button("Show what happens today  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - Without CorpusGate
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='cg-card'><span class='cg-step-label'>Step 2</span>"
        "<h3>Without CorpusGate - the failure</h3>"
        "<p class='muted'>The top 5 documents by relevance, whoever is asking. Next to it: what this user may really read.</p></div>",
        unsafe_allow_html=True,
    )
    items, n_leak = [], 0
    for x in D["unfiltered"]:
        if x["readable"]:
            items.append(doc_line(x, "<span class='mark mark-ok'>OK</span>"))
        else:
            n_leak += 1
            items.append(doc_line(x, "<span class='mark mark-bad'>LEAK</span>"))
    g = D["guards"]
    pii_open = [x for x in D["unfiltered"] if x["pii"] != "none"]
    bullets = []
    if n_leak:
        bullets.append(f"{n_leak} of {len(D['unfiltered'])} results go to a user who may not read them.")
    bullets.append(f"The relevance eval scores this question at precision {D['precision']:.2f}, recall {D['recall']:.2f}. "
                   + ("It never looks at who is asking, so it counts a leaked document as a correct answer." if n_leak
                      else "It never looks at who is asking."))
    if g["index_acl"]["leaked"]:
        bullets.append(f"A filter on the ACL copy taken at index time still lets {plural(g['index_acl']['leaked'], 'unreadable result', 'unreadable results')} through.")
    if g["index_acl"]["withheld"]:
        bullets.append(f"That index copy hides {plural(g['index_acl']['withheld'], 'relevant document', 'relevant documents')} the user may read.")
    if g["flat"]["leaked"]:
        bullets.append(f"A flat group check lets {plural(g['flat']['leaked'], 'unreadable result', 'unreadable results')} through.")
    if g["flat"]["withheld"]:
        bullets.append(f"A flat group check hides {plural(g['flat']['withheld'], 'relevant document', 'relevant documents')} the user may read.")
    if g["label"]["leaked"]:
        bullets.append(f"A label-only filter lets {plural(g['label']['leaked'], 'unreadable result', 'unreadable results')} through.")
    if g["label"]["withheld"]:
        bullets.append(f"A label-only filter hides {plural(g['label']['withheld'], 'relevant document', 'relevant documents')} the user may read.")
    if pii_open:
        bullets.append(f"{plural(len(pii_open), 'result contains', 'results contain')} personal data in the text (synthetic, invalid formats).")
    if len(bullets) == 1:
        bullets.insert(0, "Nothing goes wrong on this question: every approach returns the same readable results.")
    red = ("<div class='bot-bad'><b>What the assistant returns today (WRONG where marked):</b><ul>" + "".join(items) + "</ul>"
           "<div class='small'><b>What goes wrong on this question</b></div><ul>" + "".join(f"<li>{esc(b)}</li>" for b in bullets) + "</ul></div>")

    eff = U["effective"]
    blue_items = [
        f"<li><b>{esc(x['doc_id'])}</b>: {esc(x['why'])}</li>" for x in D["unfiltered"]
    ]
    blue = ("<div class='bot-truth'><b>Source of truth - who may read what:</b><ul>"
            f"<li><code>{esc(U['id'])}</code> is directly in <code>{esc(', '.join(U['direct']))}</code>.</li>"
            f"<li>Through the group tree the user is in {len(eff)} groups: <code>{esc(', '.join(eff))}</code>.</li>"
            f"<li>The user may read {U['readable']} of {U['docs']} documents.</li></ul>"
            "<div class='small'><b>Each result, checked against its access list</b></div><ul>" + "".join(blue_items) + "</ul></div>")
    left, right = st.columns(2)
    with left:
        st.markdown(red, unsafe_allow_html=True)
    with right:
        st.markdown(blue, unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Top 5 without an entitlement check**")
        st.dataframe(pd.DataFrame([{
            "doc_id": x["doc_id"], "dept": x["dept"], "label shown": x["shown_label"], "label truth": x["true_label"],
            "relevant": "yes" if x["relevant"] else "no", "user may read": "yes" if x["readable"] else "no",
            "personal data": x["pii"], "ACL": x["acl"], "score": x["score"]} for x in D["unfiltered"]]),
            use_container_width=True, hide_index=True)

    if st.session_state.step < 3:
        if st.button("See the fix  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - With CorpusGate
# ---------------------------------------------------------------------------
if st.session_state.step >= 3:
    G = D["gate"]
    st.markdown(
        "<div class='cg-card'><span class='cg-step-label'>Step 3</span>"
        "<h3>With CorpusGate - checked before ranking</h3>"
        "<p class='muted'>The user's real access is resolved through nested groups, documents the user may not read are removed before "
        "the top 5 is chosen, and personal data is held or masked when a document is indexed.</p></div>",
        unsafe_allow_html=True,
    )
    parts = []
    if G["removed_acl"]:
        parts.append(f"{G['removed_acl']} BLOCKED")
    if G["held_pii"]:
        parts.append(f"{len(G['held_pii'])} HELD")
    if G["redacted"]:
        parts.append(f"{len(G['redacted'])} REDACTED")
    big = " · ".join(parts) if parts else "NOTHING TO BLOCK"
    limit_leak = bool(G["leaked"])
    limit_pii = bool(G["pii_served"])
    klass = "verdict-review" if (limit_leak or limit_pii) else "verdict-pass"
    rec = ""
    if G["recall_before"] is not None:
        rec = (f"<span class='vchip'>Recall of readable relevant documents: {G['recall_before']:.2f} to {G['recall_after']:.2f}</span>")
    res_items = []
    for x in G["results"]:
        mark = ""
        if x["doc_id"] in G["leaked"]:
            mark = "<span class='mark mark-warn'>STILL LEAKS</span>"
        elif x["doc_id"] in G["pii_served"]:
            mark = "<span class='mark mark-warn'>PERSONAL DATA PASSED</span>"
        elif x["doc_id"] in G["redacted"]:
            mark = "<span class='mark mark-ok'>REDACTED</span>"
        res_items.append(f"<li><b>{esc(x['doc_id'])}</b><span class='lab'>{esc(x['shown_label'])}</span> {esc(x['title'])}{mark}</li>")
    held_html = "".join(f"<li><b>{esc(h['doc_id'])}</b> held out of the index: {esc(h['kind'].replace('_', '-'))} value found, owner to review</li>" for h in G["held_pii"])
    st.markdown(
        f"<div class='verdict-card {klass}'>"
        "<div class='vlabel'>With CorpusGate</div>"
        f"<div class='vbig'>{esc(big)}</div>"
        f"<div class='vmetric'>{len(G['results'])} results returned, every one the user may read{' except where marked' if (limit_leak or limit_pii) else ''}</div>"
        f"<div class='vrow'>{rec}"
        + (f"<span class='vchip'>{plural(G['removed_acl'], 'better-ranked match', 'better-ranked matches')} withheld by access (titles are not shown to the user)</span>" if G['removed_acl'] else "")
        + "</div>"
        "<ul>" + "".join(res_items) + held_html + "</ul></div>",
        unsafe_allow_html=True,
    )
    if limit_leak:
        st.markdown("<div class='limit-note'>Known limit. This document's access was revoked after CorpusGate's last sync of the source "
                    "lists, so the gate still allows it. The canary pack catches this class; the prototype does not close the window.</div>",
                    unsafe_allow_html=True)
    if limit_pii:
        st.markdown("<div class='limit-note'>Known limit. This document holds personal data in a format the scan patterns do not match "
                    "(for example spaces instead of hyphens), so it was indexed and is served as written.</div>", unsafe_allow_html=True)

    with st.expander("See the data"):
        st.markdown("**Top 5 with CorpusGate**")
        st.dataframe(pd.DataFrame([{
            "doc_id": x["doc_id"], "dept": x["dept"], "label shown": x["shown_label"],
            "relevant": "yes" if x["relevant"] else "no", "user may read": "yes" if x["readable"] else "no",
            "personal data in truth": x["pii"]} for x in G["results"]]), use_container_width=True, hide_index=True)
        st.caption("Personal-data policy (an assumption of the modeled bank): SSN-like and account-like matches are held out of "
                   "the index; e-mail-like matches are masked.")

    lines = [f"# CorpusGate access decision: {D['query_id']}", "",
             "Synthetic data from the CorpusGate prototype; not a real bank, user or document.", "",
             f"- Asker: {U['id']} ({U['dept']}, {U['role']}); query: {D['text']}",
             f"- Returned: {', '.join(x['doc_id'] for x in G['results'])}",
             f"- Blocked by access list: {G['removed_acl']}; held for personal data: {len(G['held_pii'])}; redacted: {len(G['redacted'])}",
             "", "| Document | Decision |", "| --- | --- |"]
    lines += [f"| {x['doc_id']} | {x['why']} |" for x in D["unfiltered"]]
    st.download_button("Download access decision (Markdown)", "\n".join(lines),
                       file_name=f"corpusgate_{D['query_id']}.md", mime="text/markdown")

    if st.session_state.step < 4:
        if st.button("See the proof at scale  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - Proof at scale
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='cg-card'><span class='cg-step-label'>Step 4</span>"
        "<h3>Proof at scale</h3>"
        f"<p class='muted'>The same checks over all {S['n_queries']} test questions and {S['canaries']} canary pairs.</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-grid'>"
        "<div class='verdict-card verdict-flag'><div class='vlabel'>Without CorpusGate</div>"
        f"<div class='vbig'>{S['leaked_before']} of {S['results']:,}</div>"
        "<div class='vmetric'>results go to a user who may not read them</div>"
        f"<div class='vtldr'>The relevance eval scored {DEF['eval']['leaked_scored_as_hits']} of them as correct.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>With CorpusGate</div>"
        f"<div class='vbig'>{S['leaked_after']} of {S['results']:,}</div>"
        "<div class='vmetric'>results still leak</div>"
        f"<div class='vtldr'>All {S['leaked_window']} come from ACL changes made after the last sync.</div></div>"
        "<div class='verdict-card verdict-pass'><div class='vlabel'>Canary pack</div>"
        f"<div class='vbig'>{S['canary_leaked_cg']} of {S['canaries']}</div>"
        f"<div class='vmetric'>canaries leak, against {S['canary_leaked_none']} of {S['canaries']} with no access control</div>"
        "<div class='vtldr'>Each canary asks for one document its user may not read.</div></div>"
        "<div class='verdict-card verdict-review'><div class='vlabel'>Personal data at ingestion</div>"
        f"<div class='vbig'>{S['pii_found']} of {S['pii_injected']}</div>"
        f"<div class='vmetric'>injected values found, {S['pii_false_pos']} look-alike documents flagged</div>"
        "<div class='vtldr'>The scan is a set of regex patterns, so some formats pass.</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='trust-card quiet'><h4>What it still gets wrong</h4><ul>"
        f"<li>{S['pii_missed']} of {S['pii_injected']} injected personal-data values use a format the patterns do not match "
        f"(spaces, no separators, spelled-out e-mail). They are indexed and {S['pii_results_after']} results in the test set still carry them.</li>"
        f"<li>The ACL-sync window: {S['changes_after_sync']} ACL changes landed after the last sync. Until the next one the gate allows "
        f"{S['window_pairs']} user and document pairs the source denies. {S['leaked_after']} test results and {S['canary_leaked_cg']} canaries show it.</li>"
        "<li>The resolver agrees with the generator's truth on every pair by construction: both implement one rule. "
        "It says nothing about a directory that disagrees with itself.</li>"
        f"<li>Quarantine costs recall: readable recall@5 goes {S['readable_recall_before']:.3f} to {S['readable_recall_after']:.3f}, "
        f"and would be {S['readable_recall_redact']:.3f} if matches were masked instead of held.</li>"
        "</ul></div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Leaked results out of 1,000, by approach**")
    st.caption("Each cheap guard is run alone on the same questions. The last bar is CorpusGate.")
    names = ["No access control", "Index ACL copy", "Flat group check", "Label-only filter", "CorpusGate"]
    vals = [DEF["leak"]["leaked"], DEF["stale"]["leaked"], DEF["flat"]["leaked"], DEF["label"]["leaked"], S["leaked_after"]]
    fig = go.Figure()
    fig.add_bar(x=names, y=vals, marker_color=["#b91c1c", "#f59e0b", "#f59e0b", "#f59e0b", "#059669"],
                text=vals, textposition="outside")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="leaked results", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("See the data"):
        st.dataframe(pd.DataFrame([{
            "system": s["name"], "results": s["results"], "leaked": s["leaked"], "queries with a leak": s["queries_with_leak"],
            "readable recall@5": round(s["readable_recall"], 3), "results per query": round(s["per_query"], 2)}
            for s in A["systems"] + [A["truth_sys"]]]), use_container_width=True, hide_index=True)
        st.dataframe(pd.DataFrame([{"stratum": r["stratum"], "pairs": r["pairs"], "leaked, no access control": r["leaked_none"],
                                    "leaked, CorpusGate": r["leaked_cg"]} for r in A["canary_rows"]]),
                     use_container_width=True, hide_index=True)
    with st.expander("Glossary"):
        st.dataframe(pd.DataFrame([
            ("ACL", "The access list on a document: groups that may read it, and groups explicitly denied."),
            ("Nested group", "A group inside another group. Members of the inner group are members of the outer one."),
            ("Leak", "A result returned to a user who may not read that document."),
            ("Pre-filter", "Remove unreadable documents before choosing the top 5, so they do not take a slot."),
            ("Quarantine", "Hold a document out of the index until its owner reviews it."),
            ("Canary", "A test that asks for one document a user may not read; it must come back empty."),
            ("ACL-sync window", "The time between a change in the source ACL and the next time CorpusGate reads it."),
        ], columns=["Term", "Plain English"]), use_container_width=True, hide_index=True)
    with st.expander("What this would look like in production"):
        st.markdown(
            "This is a prototype on synthetic data. The production shape is an ACL sync from the source systems, a group "
            "resolver, a filter inside the vector query, an ingestion scan with a quarantine queue, and a scheduled canary "
            "runner. It is a design, not deployed; see `ARCHITECTURE.md`. Related projects (designed, none built): "
            "HalluGuard (01), PromptShield (06), LineageLog (09), PolicyNeedle (14), ControlMap (16), ScopeKeeper (23)."
        )
    st.markdown(
        "<div class='cg-card muted'>Built as a portfolio prototype on synthetic data. Walkthrough, PRD and architecture in "
        f"the <a href='{README_URL}' target='_blank'><code>README.md</code></a>. Reference: "
        f"<a href='{NIST_URL}' target='_blank'>NIST AI RMF</a>, <a href='{OWASP_URL}' target='_blank'>OWASP LLM Top 10</a>.</div>",
        unsafe_allow_html=True,
    )
