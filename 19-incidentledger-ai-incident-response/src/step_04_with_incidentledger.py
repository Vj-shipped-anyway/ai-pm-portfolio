"""Step 4 - With IncidentLedger: classify, rate, run the clocks, track the follow-ups, link.

Five parts, all plain rules. There is no model, and no stub standing in for one.

  1. Classifier. Fields first (personal data exposed; a linked change plus change wording),
     keywords second. A tie or no keyword at all returns 'needs a person', not a guess.
  2. Severity rubric. S1 to S4 from five fields: customers affected, regulated decision,
     personal data, financial impact band, duration. The thresholds are assumptions of a
     modeled bank.
  3. Clock engine. Reads data/policy.csv and the ticket's determination time, and evaluates
     every clock that applies at AS_OF: on time, late, never sent and past due, running with
     hours left, or not started.
  4. Follow-up tracker. Open past due, or closed with no evidence link.
  5. Linker. Groups tickets by system and change id; without a change id, by system, category
     and a 7-day window.

Scoring uses data/truth.csv (category, severity, root cause) and step 3's truth-side clock
arithmetic. Severity and clock agreement are by construction: the generator and this script
apply the same rubric and the same policy to the same fields. The category and linking
numbers are the ones that can be wrong, and the known limit is printed at the end.

Run (from src/):
    python3 step_04_with_incidentledger.py

Output: a readable summary, plus out/step_04_ledger.csv, out/step_04_clocks.csv and
out/step_04_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from itertools import combinations

from step_01_ticket_queue_status_quo import (AS_OF, CATEGORIES, CATEGORY_NAMES, OUT_DIR, fmt_hour,
                                             load_all)
from step_02_priority_fifo_baseline import summarize as summarize_step2
from step_03_deficiencies_exposed import deadline_rows, summarize as summarize_step3

# --- assumptions of a modeled bank (not legal advice, not a statement of any rule) ---------------
RUBRIC = {"s1_pii_customers": 100, "s1_regulated_customers": 500, "s2_customers": 2000,
          "s2_duration_h": 48, "s3_customers": 100, "s3_duration_h": 12}
WARN_FRACTION = 4            # a countdown warning fires when 1/4 of the window is left (at least 1 h)
LINK_WINDOW_H = 168          # same system, same category, 7 days apart or less
INCIDENTS_PER_QUARTER = 60   # modeled volume; the synthetic set holds 120

KEYWORDS = {
    "wrong_output": ["incorrect", "wrong", "inaccurate", "fabricated", "made-up", "misstated",
                     "does not match", "hallucinat"],
    "unfair_outcome": ["dispar", "protected group", "higher rate", "bias", "unfair", "adverse action",
                       "approval gap"],
    "data_exposure": ["exposed", "leak", "disclosed", "another customer", "visible to", "unauthorized access"],
    "security_injection": ["injection", "injected", "jailbreak", "override", "crafted", "exfiltrat",
                           "ignored its instructions", "tool abuse"],
    "availability": ["outage", "unavailable", "timeout", "timed out", "latency", "not responding",
                     "degraded", "error rate", "down for"],
    "regression_after_change": ["after the release", "since the update", "after the model change",
                                "after deploy", "worse than before", "regression", "since the release",
                                "after the prompt change"],
    "misuse": ["outside approved use", "unapproved", "not permitted", "policy breach", "misuse",
               "against the usage policy", "bypassed the approval"],
}


# ---------------------------------------------------------------------------
# 1. Classifier
# ---------------------------------------------------------------------------
def classify(inc: dict) -> dict:
    text = (inc["title"] + " " + inc["description"]).lower()
    hits = {c: [k for k in KEYWORDS[c] if k in text] for c in CATEGORIES}
    if inc["pii_exposed"]:
        return {"category": "data_exposure", "confidence": "field", "rule": "field: personal data exposed",
                "hits": hits["data_exposure"], "candidates": []}
    if inc["change_id"] and hits["regression_after_change"]:
        return {"category": "regression_after_change", "confidence": "field",
                "rule": "field: linked change " + inc["change_id"] + " plus change wording",
                "hits": hits["regression_after_change"], "candidates": []}
    scores = {c: len(h) for c, h in hits.items()}
    best = max(scores.values())
    if best == 0:
        return {"category": "needs_review", "confidence": "review", "rule": "no keyword matched",
                "hits": [], "candidates": []}
    top = [c for c in CATEGORIES if scores[c] == best]
    if len(top) > 1:
        return {"category": "needs_review", "confidence": "review",
                "rule": "tie between " + " and ".join(CATEGORY_NAMES[c] for c in top),
                "hits": [], "candidates": top}
    return {"category": top[0], "confidence": "keywords",
            "rule": "keywords: " + ", ".join(hits[top[0]]), "hits": hits[top[0]], "candidates": []}


# ---------------------------------------------------------------------------
# 2. Severity rubric
# ---------------------------------------------------------------------------
def rubric(inc: dict) -> tuple:
    """Return (severity, reasons). Reasons are the rubric lines that fired at that level."""
    cust, band, dur = inc["customers_affected"], inc["financial_impact_band"], inc["duration_hours"]
    pii, reg = inc["pii_exposed"], inc["regulated_decision_involved"]
    s1 = []
    if band == "high":
        s1.append("financial impact band is high")
    if pii and cust >= RUBRIC["s1_pii_customers"]:
        s1.append(f"personal data exposed for {cust} customers ({RUBRIC['s1_pii_customers']} or more)")
    if reg and cust >= RUBRIC["s1_regulated_customers"]:
        s1.append(f"regulated decision affecting {cust} customers ({RUBRIC['s1_regulated_customers']} or more)")
    if s1:
        return "S1", s1
    s2 = []
    if band == "medium":
        s2.append("financial impact band is medium")
    if pii:
        s2.append("personal data exposed")
    if reg:
        s2.append("regulated decision involved")
    if cust >= RUBRIC["s2_customers"]:
        s2.append(f"{cust} customers affected ({RUBRIC['s2_customers']} or more)")
    if dur >= RUBRIC["s2_duration_h"]:
        s2.append(f"lasted {dur} hours ({RUBRIC['s2_duration_h']} or more)")
    if s2:
        return "S2", s2
    s3 = []
    if band == "low":
        s3.append("financial impact band is low")
    if cust >= RUBRIC["s3_customers"]:
        s3.append(f"{cust} customers affected ({RUBRIC['s3_customers']} or more)")
    if dur >= RUBRIC["s3_duration_h"]:
        s3.append(f"lasted {dur} hours ({RUBRIC['s3_duration_h']} or more)")
    if s3:
        return "S3", s3
    return "S4", ["no rubric line fired"]


def policy_flags(inc: dict, sev: str) -> dict:
    pii, reg = bool(inc["pii_exposed"]), bool(inc["regulated_decision_involved"])
    notification = sev == "S1" or (sev == "S2" and (pii or reg))
    return {"sev_s1": sev == "S1", "notification_incident": notification, "pii_exposed": pii,
            "serious_incident": sev == "S1" and (pii or reg)}


# ---------------------------------------------------------------------------
# 3. Clock engine
# ---------------------------------------------------------------------------
def evaluate_clocks(inc: dict, sev: str, policy: list, sent: dict, as_of: int = AS_OF,
                    anchor: str = "policy") -> list:
    """One dict per clock that applies. anchor: 'policy' (each clock's own), 'determination', 'detection'."""
    flags = policy_flags(inc, sev)
    out = []
    for p in policy:
        if not flags[p["applies_to"]]:
            continue
        a = p["anchor"] if anchor == "policy" else anchor
        start = inc["determined_at"] if a == "determination" else inc["detected_at"]
        c = {"clock_id": p["clock_id"], "name": p["name"], "hours": p["hours"], "anchor": a, "start": start,
             "due": None, "sent_at": None, "hours_left": None, "hours_over": None, "warn_at": None}
        if start is None:
            c["status"] = "not_started"
            c["hours_since_detection"] = as_of - inc["detected_at"]
        else:
            c["due"] = start + p["hours"]
            c["warn_at"] = c["due"] - max(1, p["hours"] // WARN_FRACTION)
            c["sent_at"] = sent.get((inc["incident_id"], p["clock_id"]))
            if c["sent_at"] is not None:
                c["status"] = "on_time" if c["sent_at"] <= c["due"] else "late"
                if c["status"] == "late":
                    c["hours_over"] = c["sent_at"] - c["due"]
            elif c["due"] < as_of:
                c["status"], c["hours_over"] = "breached", as_of - c["due"]
            else:
                c["status"], c["hours_left"] = "running", c["due"] - as_of
        out.append(c)
    return out


def count_clocks(clocks: list) -> dict:
    c = Counter(x["status"] for x in clocks)
    out = {s: c.get(s, 0) for s in ("on_time", "late", "breached", "running", "not_started")}
    out["applicable"] = len(clocks)
    out["missed"] = out["late"] + out["breached"]
    return out


# ---------------------------------------------------------------------------
# 4. Follow-up tracker
# ---------------------------------------------------------------------------
def track_action(a: dict, as_of: int = AS_OF) -> dict:
    out = dict(a)
    out["hours_over"] = None
    if a["status"] == "closed":
        out["state"] = "closed_no_evidence" if a["evidence_link"] == "no" else "closed_ok"
    elif a["due_at"] < as_of:
        out["state"], out["hours_over"] = "overdue", as_of - a["due_at"]
    else:
        out["state"] = "open_on_track"
    return out


# ---------------------------------------------------------------------------
# 5. Linker
# ---------------------------------------------------------------------------
def link_incidents(incidents: list, pred: dict) -> dict:
    """Union-find over pairs. Same system is required. Both carry a change id: equal links, different
    does not. Otherwise same predicted category (not 'needs a person') within LINK_WINDOW_H links."""
    parent = {i["incident_id"]: i["incident_id"] for i in incidents}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in combinations(incidents, 2):
        if a["system"] != b["system"]:
            continue
        if a["change_id"] and b["change_id"]:
            linked = a["change_id"] == b["change_id"]
        else:
            ca, cb = pred[a["incident_id"]]["category"], pred[b["incident_id"]]["category"]
            linked = ca == cb and ca != "needs_review" and abs(a["reported_at"] - b["reported_at"]) <= LINK_WINDOW_H
        if linked:
            parent[find(a["incident_id"])] = find(b["incident_id"])
    groups = defaultdict(list)
    for i in incidents:
        groups[find(i["incident_id"])].append(i["incident_id"])
    group_of = {x: g for g, members in groups.items() for x in members}
    links = {x: sorted(m for m in groups[group_of[x]] if m != x) for x in group_of}
    return {"group_of": group_of, "links": links, "groups": [sorted(v) for v in groups.values()]}


# ---------------------------------------------------------------------------
# Everything the report, the app and the demo need, computed once
# ---------------------------------------------------------------------------
def analyze(data: dict | None = None) -> dict:
    data = data or load_all()
    inc, truth = data["incidents"], data["truth"]
    n = len(inc)
    pred = {i["incident_id"]: classify(i) for i in inc}
    sev = {}
    for i in inc:
        sev[i["incident_id"]] = rubric(i)
    clocks = {i["incident_id"]: evaluate_clocks(i, sev[i["incident_id"]][0], data["policy"], data["sent"])
              for i in inc}
    clocks_det = {i["incident_id"]: evaluate_clocks(i, sev[i["incident_id"]][0], data["policy"], data["sent"],
                                                    anchor="detection") for i in inc}
    acts_by = defaultdict(list)
    for a in data["actions"]:
        acts_by[a["incident_id"]].append(track_action(a))
    link = link_incidents(inc, pred)

    # category
    correct = [i for i in inc if pred[i["incident_id"]]["category"] == truth[i["incident_id"]]["category"]]
    misses = [i for i in inc if pred[i["incident_id"]]["category"] != truth[i["incident_id"]]["category"]]
    flagged_miss = [i for i in misses if pred[i["incident_id"]]["confidence"] == "review"]
    designed = [i for i in inc if truth[i["incident_id"]]["hard_case"]]
    designed_missed = [i for i in designed if pred[i["incident_id"]]["category"] != truth[i["incident_id"]]["category"]]
    undesigned_missed = [i for i in misses if not truth[i["incident_id"]]["hard_case"]]
    cm = {t: Counter() for t in CATEGORIES}
    for i in inc:
        cm[truth[i["incident_id"]]["category"]][pred[i["incident_id"]]["category"]] += 1
    fields_rule = [i for i in inc if pred[i["incident_id"]]["confidence"] == "field"]
    fields_right = [i for i in fields_rule if pred[i["incident_id"]]["category"] == truth[i["incident_id"]]["category"]]

    # severity (by construction)
    sev_ok = sum(1 for i in inc if sev[i["incident_id"]][0] == truth[i["incident_id"]]["severity"])
    sev_counts = Counter(s for s, _ in sev.values())

    # clocks
    all_clocks = [dict(c, incident_id=x) for x, cs in clocks.items() for c in cs]
    cnt = count_clocks(all_clocks)
    cnt_det = count_clocks([c for cs in clocks_det.values() for c in cs])
    by_clock = {p["clock_id"]: count_clocks([c for c in all_clocks if c["clock_id"] == p["clock_id"]])
                for p in data["policy"]}
    truth_rows = {(r["incident_id"], r["clock_id"]): r["status"] for r in deadline_rows(data, "policy")}
    eng_rows = {(c["incident_id"], c["clock_id"]): c["status"] for c in all_clocks}
    clock_agree = sum(1 for k, v in truth_rows.items() if eng_rows.get(k) == v)
    missed_clocks = [c for c in all_clocks if c["status"] in ("late", "breached")]
    # a countdown warns when 1/4 of the window is left; a missed clock is warned if that moment came
    # after the clock started and before the deadline passed
    warned = [c for c in missed_clocks if c["start"] <= c["warn_at"] < c["due"]]
    inc_with_missed = len({c["incident_id"] for c in missed_clocks})

    # follow-ups
    flat = [a for v in acts_by.values() for a in v]
    act = Counter(a["state"] for a in flat)

    # links, pairwise against the truth
    ids = [i["incident_id"] for i in inc]
    true_pairs = {(a, b) for a, b in combinations(ids, 2)
                  if truth[a]["root_cause"] == truth[b]["root_cause"]}
    pred_pairs = {(a, b) for a, b in combinations(ids, 2) if link["group_of"][a] == link["group_of"][b]}
    tp = len(true_pairs & pred_pairs)
    first_of = {}
    repeats, repeats_linked = [], []
    for i in inc:                                           # incidents are in time order
        rc = truth[i["incident_id"]]["root_cause"]
        if rc not in first_of:
            first_of[rc] = []
        else:
            repeats.append(i["incident_id"])
            if any(link["group_of"][e] == link["group_of"][i["incident_id"]] for e in first_of[rc]):
                repeats_linked.append(i["incident_id"])
        first_of[rc].append(i["incident_id"])

    # utility
    m, z = cnt["missed"], cnt["not_started"]
    util = {"missed": m, "not_started": z, "queue_unflagged": m + z, "with_unflagged": z,
            "per_incident_queue": (m + z) / n, "per_incident_with": z / n, "lift_per_incident": m / n,
            "incidents_per_quarter": INCIDENTS_PER_QUARTER,
            "per_quarter": m / n * INCIDENTS_PER_QUARTER,
            "sensitivity": {q: m / n * q for q in (30, 60, 120)}}

    s3 = summarize_step3(data)
    summary = {
        "incidents": n, "class_correct": len(correct), "class_total": n, "class_misses": len(misses),
        "class_flagged_miss": len(flagged_miss), "class_confident_miss": len(misses) - len(flagged_miss),
        "designed": len(designed), "designed_missed": len(designed_missed),
        "undesigned_missed": len(undesigned_missed),
        "field_rule_used": len(fields_rule), "field_rule_right": len(fields_right),
        "per_class": {c: {"truth": sum(cm[c].values()), "right": cm[c][c]} for c in CATEGORIES},
        "confusion": {c: dict(cm[c]) for c in CATEGORIES},
        "sev_ok": sev_ok, "sev_counts": {k: sev_counts[k] for k in ("S1", "S2", "S3", "S4")},
        "clocks": cnt, "clocks_at_detection": cnt_det, "clocks_by_clock": by_clock,
        "clock_agree": clock_agree, "clock_total": len(truth_rows),
        "missed_warned": len(warned), "missed_total": len(missed_clocks), "incidents_with_missed": inc_with_missed,
        "actions": {"total": len(flat), "overdue": act["overdue"], "closed_no_evidence": act["closed_no_evidence"],
                    "closed_ok": act["closed_ok"], "open_on_track": act["open_on_track"],
                    "flagged": act["overdue"] + act["closed_no_evidence"]},
        "link_true_pairs": len(true_pairs), "link_pred_pairs": len(pred_pairs), "link_tp": tp,
        "link_precision": tp / len(pred_pairs), "link_recall": tp / len(true_pairs),
        "repeat_tickets": len(repeats), "repeat_linked": len(repeats_linked),
        "groups": len(link["groups"]), "util": util,
        "priority_exact": s3["a"]["exact"],
    }
    truth_by = defaultdict(list)
    for r in deadline_rows(data, "policy"):
        truth_by[r["incident_id"]].append(r)
    return {"data": data, "pred": pred, "sev": sev, "clocks": clocks, "clocks_det": clocks_det,
            "actions": dict(acts_by), "link": link, "summary": summary, "misses": misses,
            "repeats": repeats, "repeats_linked": repeats_linked, "step2": summarize_step2(data),
            "step3": s3, "truth_deadlines": dict(truth_by)}


def interest_order(A: dict) -> list:
    """Incident ids, most telling first: severe incidents the queue under-rated that also missed a
    deadline, then other missed deadlines on severe incidents, then the rest by severity."""
    data = A["data"]

    def key(i):
        x = i["incident_id"]
        sev = A["sev"][x][0]
        missed = sum(1 for c in A["clocks"][x] if c["status"] in ("late", "breached"))
        severe = sev in ("S1", "S2")
        low = i["reporter_priority"] in ("P3", "P4")
        return (not (severe and low and missed), not (severe and missed), -missed, sev, x)

    return [i["incident_id"] for i in sorted(data["incidents"], key=key)]


def view(A: dict, x: str) -> dict:
    """One incident, everything the app and the demo show. Pure lookups on the analysis."""
    data = A["data"]
    inc, t = data["by_id"][x], data["truth"][x]
    p, (sv, reasons) = A["pred"][x], A["sev"][x]
    link_ids = A["link"]["links"][x]
    same_rc = [y for y in data["truth"] if y != x and data["truth"][y]["root_cause"] == t["root_cause"]]
    return {
        "inc": inc, "truth": t, "pred": p, "severity": sv, "reasons": reasons,
        "category_ok": p["category"] == t["category"], "severity_ok": sv == t["severity"],
        "queue_position": A["step2"]["position"][x], "clocks": A["clocks"][x], "clocks_det": A["clocks_det"][x],
        "truth_deadlines": A["truth_deadlines"].get(x, []), "actions": A["actions"].get(x, []),
        "links": link_ids, "links_ok": {y: data["truth"][y]["root_cause"] == t["root_cause"] for y in link_ids},
        "same_root_cause": same_rc,
        "missed": sum(1 for c in A["clocks"][x] if c["status"] in ("late", "breached")),
    }


def short(text: str, width: int) -> str:
    return text if len(text) <= width else text[:width - 3] + "..."


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    A = analyze()
    data, pred, sev, s = A["data"], A["pred"], A["sev"], A["summary"]
    truth = data["truth"]
    n = s["incidents"]
    c, cd, u = s["clocks"], s["clocks_at_detection"], s["util"]

    print("\n" + "=" * 78)
    print("Step 4 - With IncidentLedger: classify, rate, run the clocks, track, link")
    print("=" * 78)
    print("\nNo model is used. Every part is a rule you can read in this file.")

    print("\n1. CATEGORY (fields first, keywords second)")
    print(f"   Correct on {s['class_correct']} of {n} incidents ({100 * s['class_correct'] / n:.1f}%). "
          f"{s['class_misses']} wrong: {s['class_flagged_miss']} flagged 'needs a person', "
          f"{s['class_confident_miss']} wrong with no flag.")
    print(f"   A field rule decided {s['field_rule_used']} incidents and was right on {s['field_rule_right']}.")
    print(f"   {'class':<26} {'incidents':>9} {'right':>6}")
    for k, v in s["per_class"].items():
        print(f"   {CATEGORY_NAMES[k]:<26} {v['truth']:>9} {v['right']:>6}")

    print("\n2. SEVERITY (rubric, thresholds are assumptions of a modeled bank)")
    print(f"   S1 {s['sev_counts']['S1']}, S2 {s['sev_counts']['S2']}, S3 {s['sev_counts']['S3']}, "
          f"S4 {s['sev_counts']['S4']}. Matches the truth file on {s['sev_ok']} of {n} (by construction).")

    print("\n3. CLOCKS at " + fmt_hour(AS_OF) + " (clock starts at determination)")
    print(f"   {c['applicable']} deadlines apply: {c['on_time']} on time, {c['late']} late, "
          f"{c['breached']} never sent and past due, {c['running']} running, {c['not_started']} not started.")
    print(f"   Missed (late or never sent): {c['missed']} of {c['applicable']} ({100 * c['missed'] / c['applicable']:.1f}%), "
          f"on {s['incidents_with_missed']} incidents. On time: {c['on_time']} of {c['applicable']} "
          f"({100 * c['on_time'] / c['applicable']:.1f}%).")
    print(f"   Same clocks started at detection: {cd['missed']} missed.")
    print(f"   Statuses agree with the truth-side arithmetic of step 3 on {s['clock_agree']} of {s['clock_total']} (by construction).")
    print(f"   A countdown at one quarter of the window left would have fired before the deadline on "
          f"{s['missed_warned']} of {s['missed_total']} missed clocks (by construction).")
    soon = sorted(((x, cl) for x, cs in A["clocks"].items() for cl in cs if cl["status"] == "running"),
                  key=lambda p: (p[1]["hours_left"], p[0]))
    for x, cl in soon:
        print(f"   running: {x} {cl['name']}, {cl['hours_left']} h left")

    a = s["actions"]
    print("\n4. FOLLOW-UPS")
    print(f"   {a['total']} actions: {a['overdue']} overdue, {a['closed_no_evidence']} closed with no evidence, "
          f"{a['closed_ok']} closed with evidence, {a['open_on_track']} open and on track.")
    print(f"   Flagged: {a['flagged']} of {a['total']} ({100 * a['flagged'] / a['total']:.1f}%).")

    print("\n5. LINKS (same system; change id, else same category within 7 days)")
    print(f"   {s['groups']} groups from {n} incidents. Truth has {A['step3']['f']['root_causes']} root causes.")
    print(f"   Pairs: {s['link_tp']} right of {s['link_pred_pairs']} linked (precision {100 * s['link_precision']:.1f}%), "
          f"{s['link_tp']} of {s['link_true_pairs']} true pairs found (recall {100 * s['link_recall']:.1f}%).")
    print(f"   Repeat tickets linked to an earlier ticket of the same root cause: {s['repeat_linked']} of {s['repeat_tickets']}.")

    print("\nMEASURED AGAINST THE TRUTH FILE")
    print(f"  Category:  {s['class_correct']} of {n} ({100 * s['class_correct'] / n:.1f}%); designed hard cases "
          f"{s['designed']}, missed {s['designed_missed']}; misses outside them {s['undesigned_missed']}")
    print(f"  Severity:  {s['sev_ok']} of {n} (by construction)")
    print(f"  Queue priority matched the rubric severity on {s['priority_exact']} of {n}")
    print(f"  Deadlines: {c['missed']} missed, all {s['missed_warned']} with a countdown that fires first (by construction); the queue showed 0")

    print("\nWHAT IT STILL GETS WRONG (known limit, left in on purpose)")
    print(f"  Category misses: {s['class_misses']} of {n}.")
    for i in A["misses"]:
        p = pred[i["incident_id"]]
        t = truth[i["incident_id"]]
        print(f"    {i['incident_id']} truth {CATEGORY_NAMES[t['category']]:<24} said {CATEGORY_NAMES[p['category']]:<23} "
              f"{p['rule']}")
    undet = [i for i in data["incidents"] if i["determined_at"] is None]
    lags = [i["determined_at"] - i["detected_at"] for i in data["incidents"] if i["determined_at"] is not None]
    print(f"  Determination is a human call. The clock starts when a person records it, and the tool cannot supply it.")
    print(f"    {len(undet)} incidents have no determination at {fmt_hour(AS_OF)}; "
          f"{c['not_started']} deadlines on {len({k for k, v in A['clocks'].items() if any(x['status'] == 'not_started' for x in v)})} of them have not started.")
    print(f"    Detection to determination: median {statistics.median(lags):g} h, longest {max(lags)} h. "
          f"Start the clock at detection and {cd['missed']} deadlines are missed instead of {c['missed']}.")
    print(f"  Links: {s['repeat_tickets'] - s['repeat_linked']} of {s['repeat_tickets']} repeat tickets are not linked "
          f"to an earlier ticket of the same root cause; {s['link_pred_pairs'] - s['link_tp']} linked pairs are not "
          f"the same root cause.")

    print("\nUTILITY (deadline misses plus clocks that never started, per incident)")
    print(f"  Ticket queue:    {u['missed']} missed + {u['not_started']} never started = {u['queue_unflagged']} over {n} incidents "
          f"= {u['per_incident_queue']:.3f} per incident, none flagged")
    print(f"  IncidentLedger:  {u['not_started']} never started = {u['with_unflagged']} over {n} incidents "
          f"= {u['per_incident_with']:.3f} per incident (no determination, so no clock)")
    print(f"  Lift:            {u['missed']} over {n} incidents = {u['lift_per_incident']:.3f} per incident, "
          f"if every countdown is acted on (assumption)")
    print(f"  Modeled volume:  {u['incidents_per_quarter']} incidents a quarter -> "
          f"{u['per_quarter']:.1f} missed deadlines avoided a quarter")
    print("  Sensitivity:     " + ", ".join(f"{q} a quarter gives {v:.1f}" for q, v in u["sensitivity"].items()))

    with open(OUT_DIR / "step_04_ledger.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["incident_id", "true_category", "predicted_category", "rule", "true_severity", "rubric_severity",
                    "queue_priority", "missed_clocks", "linked_to"])
        for i in data["incidents"]:
            x = i["incident_id"]
            w.writerow([x, truth[x]["category"], pred[x]["category"], pred[x]["rule"], truth[x]["severity"], sev[x][0],
                        i["reporter_priority"], sum(1 for cl in A["clocks"][x] if cl["status"] in ("late", "breached")),
                        ";".join(A["link"]["links"][x])])
    with open(OUT_DIR / "step_04_clocks.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["incident_id", "clock_id", "start", "due", "sent_at", "status", "hours_left", "hours_over"])
        for x, cs in A["clocks"].items():
            for cl in cs:
                w.writerow([x, cl["clock_id"], "" if cl["start"] is None else cl["start"],
                            "" if cl["due"] is None else cl["due"], "" if cl["sent_at"] is None else cl["sent_at"],
                            cl["status"], "" if cl["hours_left"] is None else cl["hours_left"],
                            "" if cl["hours_over"] is None else cl["hours_over"]])
    with open(OUT_DIR / "step_04_summary.json", "w") as f:
        json.dump(s, f, indent=2, default=str)
    print("\nWrote src/out/step_04_ledger.csv, step_04_clocks.csv and step_04_summary.json")


if __name__ == "__main__":
    main()
