"""TierGate - AI use-case intake and risk tiering for a regulated bank.

Streamlit walkthrough on 150 synthetic intake submissions:
  Step 1 - Before: one spreadsheet, same review for every case, first in first out
  Step 2 - Basic approach: trust the tier the sponsor declared
  Step 3 - Six deficiencies, each with a count (or a yes/no for one submission)
  Step 4 - TierGate: recomputed tier, discrepancies with reasons, evidence gate,
           duplicate links, tier-ordered queue

Pick one submission or a cohort in the selectbox. Everything is computed from the
CSVs in ../data by the same functions the step scripts use. Synthetic data only.
The reference tier is true by construction. No AI model is used anywhere here:
the rubric, the cross-checks and the similarity score are plain rules.
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
    page_title="TierGate - AI use-case intake and risk tiering",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1100px;}
.tg-hero {background: linear-gradient(135deg,#0f172a 0%, #1e3a5f 55%, #0e7490 100%);
          border-radius: 18px; padding: 34px 38px; color:#fff; margin-bottom:22px;}
.tg-hero .brand {font-size:24px; font-weight:600; opacity:0.92; margin-bottom:10px;}
.tg-hero h1 {color:#fff !important; font-size:40px; line-height:1.14; margin:0 0 12px 0; font-weight:700;}
.tg-hero .sub {font-size:16px; line-height:1.5; opacity:0.93; max-width:860px; margin-bottom:18px;}
.tg-hero .pills {display:flex; flex-wrap:wrap; gap:10px;}
.tg-hero .pill {background:rgba(255,255,255,0.12); border:1px solid rgba(255,255,255,0.25);
                color:#fff; padding:6px 12px; border-radius:999px; font-size:13px;}
.tg-hero .pill a {color:#fff; text-decoration:none;}
.tg-card {background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:20px 24px;
          margin-bottom:16px; box-shadow:0 1px 2px rgba(15,23,42,0.04);}
.tg-card h3 {margin-top:0; color:#0f172a;}
.tg-step {display:inline-block; background:#0e7490; color:#fff; padding:3px 10px; border-radius:6px;
          font-size:12px; font-weight:600; letter-spacing:0.04em; text-transform:uppercase; margin-bottom:8px;}
.tg-note {background:#f8fafc; border:1px solid #cbd5e1; border-left:5px solid #0e7490;
          border-radius:12px; padding:14px 18px; margin-bottom:16px; color:#334155; font-size:14px;}
.tg-tier {display:inline-block; padding:6px 14px; border-radius:10px; font-weight:700; font-size:18px; margin-right:8px;}
.t1 {background:#dcfce7; color:#14532d;} .t2 {background:#fef9c3; color:#713f12;}
.t3 {background:#ffedd5; color:#7c2d12;} .t4 {background:#fee2e2; color:#7f1d1d;}
.tg-flag {border-left:4px solid #d97706; background:#fffbeb; padding:8px 12px; margin:6px 0;
          border-radius:6px; font-size:14px; color:#44403c;}
.tg-flag b {color:#92400e;}
.tg-ok {border-left:4px solid #16a34a; background:#f0fdf4; padding:8px 12px; margin:6px 0;
        border-radius:6px; font-size:14px; color:#14532d;}
.tg-bad {border-left:4px solid #b91c1c; background:#fef2f2; padding:8px 12px; margin:6px 0;
         border-radius:6px; font-size:14px; color:#7f1d1d;}
.muted {color:#64748b; font-size:14px;}
div.stButton > button[kind="primary"] {background: linear-gradient(135deg,#0e7490,#155e75) !important;
  color:#fff !important; border:0 !important; padding:12px 26px !important; font-size:16px !important;
  font-weight:600 !important; border-radius:12px !important;}
h1, h2, h3 {color:#0f172a;}
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

if "step" not in st.session_state:
    st.session_state.step = 1


def advance(target: int) -> None:
    if st.session_state.step < target:
        st.session_state.step = target


def tier_pill(t: int) -> str:
    return "<span class='tg-tier t%d'>Tier %d</span>" % (t, t)


# ---------------------------------------------------------------------------
# Hero and scoreboard
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class='tg-hero'>
  <div class='brand'>TierGate</div>
  <h1>AI use-case intake and risk tiering: recompute the tier, gate the evidence, order the queue.</h1>
  <div class='sub'>A sponsor fills in an intake form and declares a risk tier. TierGate recomputes the tier from the
  form plus the data catalog and the vendor registry, flags every discrepancy with a reason, links duplicates,
  holds approval until the tier's evidence is on file, and orders the review queue by tier.
  150 synthetic submissions. No real bank, vendor or person.</div>
  <div class='pills'>
    <span class='pill'><a href='{GITHUB_URL}' target='_blank'>GitHub</a></span>
    <span class='pill'><a href='{LINKEDIN_URL}' target='_blank'>LinkedIn</a></span>
    <span class='pill'>{R4['n_cases']} synthetic submissions</span>
    <span class='pill'>Project 11</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    "<div class='tg-note'><b>How to read the numbers.</b> The reference tier is true by construction: the written rubric "
    "applied to the hidden true attributes. Accuracy below measures how well each method recovers it from noisy "
    "inputs, not how real banks behave. Tier accuracy, recall and evidence counts are measured on this set. Queue waits, "
    "reviewer hours and the annual figure are modeled from the assumptions in the step scripts. No AI model is used: "
    "the rubric, the cross-checks and the duplicate score are plain rules.</div>",
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Tier accuracy", "%.1f%%" % (100 * R4["accuracy"]),
          "%+.1f pts vs self-declared" % (100 * (R4["accuracy"] - (1 - R4["err_declared"]))))
m2.metric("Tier 3-4 recall", "%.1f%%" % (100 * R4["hi_recall"]),
          "%+.1f pts vs self-declared" % (100 * (R4["hi_recall"] - R4["declared_hi_recall"])))
m3.metric("Evidence-gap detection", "%.1f%%" % (100 * R4["gap_detection_rate"]),
          "%+.1f pts vs basic" % (100 * (R4["gap_detection_rate"] - R4["basic_gap_detection_rate"])))
m4.metric("Tier 3-4 mean wait (modeled)", "%.1f days" % Q["hi_ordered"],
          "%.1f days FIFO" % Q["hi_fifo"], delta_color="off")

if st.session_state.step == 1:
    cta_col, _ = st.columns([1, 2])
    with cta_col:
        if st.button("See it in action  ->", key="cta_hero", type="primary", use_container_width=True):
            advance(2)
            st.rerun()

# ---------------------------------------------------------------------------
# Scenario picker
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='tg-card'><span class='tg-step'>Scenario</span>"
    "<h3>Pick one intake submission, or a cohort</h3>"
    "<p class='muted'>Single submissions show what the sponsor declared, what TierGate recomputed, the discrepancies, "
    "the evidence checklist and the queue effect. Cohorts show the same four stages in aggregate.</p></div>",
    unsafe_allow_html=True,
)
choice = st.selectbox("Scenario", OPTIONS, index=DEFAULT_INDEX, key="scenario", label_visibility="collapsed")
kind, key = KEYS[OPTIONS.index(choice)]
if kind == "case":
    sel_ids = [key]
else:
    sel_ids = COHORTS[key][1]
sel = [BY_ID[i] for i in sel_ids]


def mean_of(xs: list) -> float:
    return sum(xs) / len(xs) if xs else 0.0


# ---------------------------------------------------------------------------
# STEP 1 - Before
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='tg-card'><span class='tg-step'>Step 1</span><h3>Before: one spreadsheet, same review, first in first out</h3>"
    "<p class='muted'>Every row gets the same standard review in arrival order. Nobody can say how many AI use cases "
    "exist, which tier each sits in, or what evidence each owes.</p></div>",
    unsafe_allow_html=True,
)
if kind == "case":
    c = sel[0]
    st.dataframe(pd.DataFrame([{
        "use case": c["use_case_id"], "submitted": c["submitted_date"], "sponsor unit": c["sponsor_unit"],
        "title": c["title"], "tier typed by sponsor": c["self_declared_tier"]}]),
        use_container_width=True, hide_index=True)
    st.write("Review given: **%.1f hours**, same as every other row. Queue wait for this row (modeled mean): **%.1f business days**."
             % (s1.UNIFORM_REVIEW_H, T4[c["use_case_id"]]["wait_before"]))
else:
    waits = [T4[i]["wait_before"] for i in sel_ids]
    st.write("%d submissions, each given **%.1f hours** of the same review. Mean queue wait for this cohort (modeled): **%.1f business days**. "
             "Across all tier 3-4 cases: %.1f days."
             % (len(sel_ids), s1.UNIFORM_REVIEW_H, mean_of(waits), R1["wait_hi_mean"]))
st.caption("Queue numbers are modeled: %d reviewers, %d intake hours each per week, %.1f hours per review, %d seeded replications."
           % (s1.N_REVIEWERS, s1.INTAKE_HOURS_PER_REVIEWER_PER_WEEK, s1.UNIFORM_REVIEW_H, s1.REPLICATIONS))

if st.session_state.step < 2:
    if st.button("Show the basic approach  ->", type="primary", key="cta_step1"):
        advance(2)
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 2 - Basic approach
# ---------------------------------------------------------------------------
if st.session_state.step >= 2:
    st.markdown(
        "<div class='tg-card'><span class='tg-step'>Step 2</span><h3>Basic approach: trust the tier the sponsor declared</h3>"
        "<p class='muted'>The reviewer applies the checklist for the declared tier and approves when it is covered.</p></div>",
        unsafe_allow_html=True,
    )
    if kind == "case":
        c = sel[0]
        r2 = T2[c["use_case_id"]]
        st.markdown(tier_pill(c["self_declared_tier"]) + " declared &nbsp;&nbsp; " + tier_pill(c["reference_tier"])
                    + " reference", unsafe_allow_html=True)
        if r2["declared"] == r2["reference"]:
            st.markdown("<div class='tg-ok'>Declared tier matches the reference tier.</div>", unsafe_allow_html=True)
        elif r2["declared"] < r2["reference"]:
            st.markdown("<div class='tg-bad'>Declared tier is <b>%d below</b> the reference tier: the case gets a lighter review and a shorter checklist than its risk calls for.</div>"
                        % (r2["reference"] - r2["declared"]), unsafe_allow_html=True)
        else:
            st.markdown("<div class='tg-flag'>Declared tier is above the reference tier: extra review effort.</div>",
                        unsafe_allow_html=True)
        if r2["approved"]:
            msg = "Approved: the declared tier's checklist is covered."
            if r2["missing_reference"]:
                msg += " Evidence the reference tier requires is missing: %s." % ", ".join(r2["missing_reference"])
                st.markdown("<div class='tg-bad'>%s</div>" % esc(msg), unsafe_allow_html=True)
            else:
                st.markdown("<div class='tg-ok'>%s</div>" % esc(msg), unsafe_allow_html=True)
        else:
            st.markdown("<div class='tg-flag'>Held: declared-tier evidence missing (%s). Requested ad hoc.</div>"
                        % esc(", ".join(r2["missing_declared"])), unsafe_allow_html=True)
    else:
        rows2 = [T2[i] for i in sel_ids]
        n_mis = sum(1 for r in rows2 if r["mis_tier"])
        n_app = sum(1 for r in rows2 if r["approved"])
        n_gap = sum(1 for r in rows2 if r["approved"] and r["missing_reference"])
        a, b, cc = st.columns(3)
        a.metric("Declared tier wrong", "%d of %d" % (n_mis, len(rows2)))
        b.metric("Approved by the basic approach", "%d of %d" % (n_app, len(rows2)))
        cc.metric("Approved with required evidence missing", "%d" % n_gap)
    if st.session_state.step < 3:
        if st.button("Show the six deficiencies  ->", type="primary", key="cta_step2"):
            advance(3)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 3 - Six deficiencies
# ---------------------------------------------------------------------------
DEF_LABELS = [
    ("a", "Self-declared tier understates risk"),
    ("b", "Data class never cross-checked against the catalog"),
    ("c", "Customer-facing impact missing or ambiguous"),
    ("d", "Vendor dependency unflagged"),
    ("e", "Overlapping use cases not linked"),
    ("f", "Approval without the evidence the tier requires"),
]
if st.session_state.step >= 3:
    st.markdown(
        "<div class='tg-card'><span class='tg-step'>Step 3</span><h3>Six deficiencies, each with a count</h3>"
        "<p class='muted'>For one submission: does the deficiency show up on it? For a cohort: how many of its submissions. "
        "The last column is the count across all %d submissions (step_03 output).</p></div>" % R4["n_cases"],
        unsafe_allow_html=True,
    )
    totals = {
        "a": D["res3"]["a"]["n"], "b": D["res3"]["b"]["below_catalog_n"], "c": D["res3"]["c"]["n"],
        "d": D["res3"]["d"]["omitted_n"], "e": D["res3"]["e"]["cases_n"], "f": D["res3"]["f"]["n"],
    }
    table = []
    for k, label in DEF_LABELS:
        hits = sum(1 for i in sel_ids if FLAGS3[i][k])
        shown = ("yes" if hits else "no") if kind == "case" else "%d of %d" % (hits, len(sel_ids))
        table.append({"#": k, "deficiency": label, "this selection": shown,
                      "all %d submissions" % R4["n_cases"]: totals[k]})
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
    st.caption("Deficiency (e) counts submissions that belong to a duplicate group: %d groups, %d true pairs. The spreadsheet links none of them."
               % (D["res3"]["e"]["groups_n"], D["res3"]["e"]["pairs_n"]))
    if kind == "case":
        c = sel[0]
        notes = []
        cat_cls = D["catalog"][c["dataset_name"]]
        notes.append("Form data class: %s. Catalog records %s for %s." % (c["data_class"], cat_cls, c["dataset_name"]))
        notes.append("Form customer-facing answer: %s. Form vendor model: %s." % (c["customer_facing"] or "(blank)", c["vendor_model"]))
        if c["duplicate_group"]:
            others = [x["use_case_id"] for x in CASES if x["duplicate_group"] == c["duplicate_group"] and x["use_case_id"] != c["use_case_id"]]
            notes.append("Same underlying use case as: %s (spreadsheet has no link)." % ", ".join(others))
        for t in notes:
            st.caption(t)
    if st.session_state.step < 4:
        if st.button("Run TierGate  ->", type="primary", key="cta_step3"):
            advance(4)
            st.rerun()

# ---------------------------------------------------------------------------
# STEP 4 - TierGate
# ---------------------------------------------------------------------------
if st.session_state.step >= 4:
    st.markdown(
        "<div class='tg-card'><span class='tg-step'>Step 4</span><h3>TierGate: recompute, flag, link, gate, order</h3>"
        "<p class='muted'>The recompute reads the form, the catalog's recorded class and the vendor registry. "
        "It never reads the hidden true columns; they are used afterwards to score it.</p></div>",
        unsafe_allow_html=True,
    )
    if kind == "case":
        c = sel[0]
        x = T4[c["use_case_id"]]
        st.markdown(
            tier_pill(x["declared"]) + " declared &nbsp;&nbsp; " + tier_pill(x["recomputed"]) + " TierGate &nbsp;&nbsp; "
            + tier_pill(x["reference"]) + " reference", unsafe_allow_html=True)
        if x["recomputed"] == x["reference"]:
            st.markdown("<div class='tg-ok'>TierGate matches the reference tier (%d points on the rubric).</div>" % x["score"],
                        unsafe_allow_html=True)
        else:
            why = "; ".join(x["causes"]) if x["causes"] else "see flags"
            st.markdown("<div class='tg-bad'>TierGate is %s the reference tier. Cause: %s.</div>"
                        % ("below" if x["recomputed"] < x["reference"] else "above", esc(why)), unsafe_allow_html=True)
        st.markdown("**Discrepancies and reasons**")
        if not x["flags"]:
            st.markdown("<div class='tg-ok'>No discrepancy: form, catalog and registry agree.</div>", unsafe_allow_html=True)
        for f in x["flags"]:
            st.markdown("<div class='tg-flag'><b>%s</b> %s</div>" % (esc(f["code"]), esc(f["reason"])), unsafe_allow_html=True)

        have = D["on_file"].get(c["use_case_id"], set())
        ev_rows = []
        for eid in D["checklist"][x["recomputed"]]:
            item, interlock = D["names"][eid]
            ev_rows.append({"evidence": eid, "required item": item, "on file": "yes" if eid in have else "MISSING",
                            "interlock": interlock})
        st.markdown("**Evidence checklist for tier %d**" % x["recomputed"])
        st.dataframe(pd.DataFrame(ev_rows), use_container_width=True, hide_index=True)
        if x["gate"] == "READY":
            st.markdown("<div class='tg-ok'>Gate: READY. Approval may proceed.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='tg-bad'>Gate: HOLD. Approval blocked until %s are on file.</div>" % esc(", ".join(x["missing"])),
                        unsafe_allow_html=True)
        if x["linked_to"]:
            st.markdown("<div class='tg-flag'>Proposed duplicate link to <b>%s</b> (token overlap %.2f). A reviewer confirms the link (%.1fh)%s.</div>"
                        % (esc(x["linked_to"]), x["link_score"], s1.LINK_CHECK_H,
                           "" if x["link_true"] else "; in this set this link is a false positive"), unsafe_allow_html=True)
        elif c["duplicate_group"]:
            st.markdown("<div class='tg-bad'>This submission has a true duplicate that the similarity score did not link at threshold %.2f.</div>"
                        % R4["link_threshold"], unsafe_allow_html=True)
        sel_rows = [x]
    else:
        sel_rows = [T4[i] for i in sel_ids]
        n = len(sel_rows)
        acc = sum(1 for r in sel_rows if r["recomputed"] == r["reference"])
        dec = sum(1 for r in sel_rows if r["declared"] == r["reference"])
        hi = [r for r in sel_rows if r["reference"] >= 3]
        a, b, cc, dd = st.columns(4)
        a.metric("TierGate tier correct", "%d of %d" % (acc, n))
        b.metric("Self-declared tier correct", "%d of %d" % (dec, n))
        cc.metric("True tier 3-4 found", "%d of %d" % (sum(1 for r in hi if r["recomputed"] >= 3), len(hi)))
        dd.metric("Held for evidence", "%d of %d" % (sum(1 for r in sel_rows if r["gate"] == "HOLD"), n))
        show = []
        for r in sel_rows[:60]:
            show.append({"use case": r["use_case_id"], "title": BY_ID[r["use_case_id"]]["title"][:58],
                         "declared": r["declared"], "TierGate": r["recomputed"], "reference": r["reference"],
                         "gate": r["gate"], "flags": ", ".join(f["code"] for f in r["flags"] if f["code"] not in ("TIER_DECLARED_BELOW", "TIER_DECLARED_ABOVE"))})
        st.dataframe(pd.DataFrame(show), use_container_width=True, hide_index=True)
        if n > 60:
            st.caption("Showing the first 60 of %d." % n)

    # queue effect
    mb = mean_of([r["wait_before"] for r in sel_rows])
    mf = mean_of([r["wait_fifo"] for r in sel_rows])
    mo = mean_of([r["wait_ordered"] for r in sel_rows])
    fig = go.Figure(go.Bar(
        x=["Step 1: same review, FIFO", "TierGate depth, FIFO", "TierGate depth, ordered by tier"],
        y=[mb, mf, mo], marker_color=["#94a3b8", "#0e7490", "#16a34a"],
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

    # workpaper
    if kind == "case":
        c = sel[0]
        x = T4[c["use_case_id"]]
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

    # known limit and utility
    with st.expander("Known limit left in on purpose"):
        st.write("%d use cases have a data class that the form AND the catalog both understate. TierGate takes the higher of the two, "
                 "so it agrees with the wrong answer; %d of them end up at the wrong tier. Pick the cohort 'Known limit' above to see them."
                 % (R4["both_wrong_n"], R4["both_wrong_mis_n"]))
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
