"""Step 4 - With VendorLens: score AI vendor risk on evidence, concentration and exit.

Four parts, all plain rules, no model:

  1. Evidence-adjusted control score. Each questionnaire answer earns credit only if a valid
     document or the contract backs it. A yes with no valid backing earns a fraction of a yes;
     a yes the contract contradicts earns none.
  2. Concentration flag. Share of the estate's critical use cases carried by each upstream
     model provider, with an HHI. One provider above CONC_LINE of critical use cases is flagged.
  3. Exit-readiness score. Exit clause, a tested exit, and a modeled time to exit inside the
     allowed window.
  4. Risk class and review cadence. The weakness score is scaled by criticality and data
     access into a 0 to 100 risk score, then bucketed HIGH / MEDIUM / LOW. The review cadence
     follows the tier, and a HIGH vendor is reviewed twice as often.

The scoring never reads data/truth.csv. The truth file (the generator's decision) is used only
afterwards, to score the result: precision and recall for HIGH against the questionnaire.

Every weight, line and threshold below is my assumption. They are not regulatory values and
not legal advice. The weights and the concentration line were set before the first comparison
with truth.csv and have not changed. The HIGH and MEDIUM lines were moved once after that first
run, from 35 and 20 to 45 and 30, because the first run rated 18 of 40 vendors HIGH; the
sensitivity table printed below shows the neighboring lines. Agreement with the truth is partly
by construction: the generator and this script both treat critical vendors with customer data as
more exposed. Step 4 prints the known limits.

Run (from src/):
    python3 step_04_with_vendorlens.py

Output: a readable summary, plus out/step_04_scores.csv, step_04_concentration.csv and
step_04_summary.json.
"""

from __future__ import annotations

import csv
import json
from datetime import timedelta

from step_01_status_quo import (
    AS_OF, CADENCE_DAYS, DOC_TYPES, FLAT_CYCLE_DAYS, OUT_DIR, ALLOWED_EXIT_DAYS, answer_support,
    assessed_age_days, evidence_status, exit_in_window, load_all, modeled_exit_days,
)
from step_02_questionnaire_checklist import passes, pct, yes_count
from step_03_deficiencies_exposed import concentration_view

# ---------------------------------------------------------------------------
# VendorLens settings (assumptions of mine; edit here)
# ---------------------------------------------------------------------------
CRIT_W = {"critical": 0.60, "important": 0.35, "standard": 0.15}     # exposure by criticality
DATA_W = {"customer_pii": 0.40, "internal": 0.20, "none": 0.0}      # exposure by data access
WEIGHTS = {"control": 0.50, "exit": 0.20, "contract": 0.10, "concentration": 0.20}
EXPOSURE_BASE, EXPOSURE_SLOPE = 0.40, 0.60      # risk = weakness x (base + slope x exposure)
HIGH_AT, MEDIUM_AT = 45.0, 30.0                 # risk score (0 to 100) lines for HIGH and MEDIUM
CONC_LINE = 0.40                                # one provider above 40% of critical use cases is flagged
UNDISCLOSED_TERM = 0.5                          # a vendor that hides its provider counts half a flag
CREDIT = {                                      # credit per answer, by what backs it
    "verified":     {"yes": 1.00, "partial": 0.50, "no": 0.0},
    "unbacked":     {"yes": 0.35, "partial": 0.15, "no": 0.0},   # no valid document behind the answer
    "unverifiable": {"yes": 0.70, "partial": 0.35, "no": 0.0},   # nothing in this repo could check it
    "contradicted": {"yes": 0.0, "partial": 0.0, "no": 0.0},     # the contract says otherwise
}
SUPPORT_BUCKET = {
    "evidence_valid": "verified", "contract_supports": "verified",
    "evidence_stale": "unbacked", "evidence_out_of_scope": "unbacked", "evidence_missing": "unbacked",
    "contract_contradicts": "contradicted", "unverifiable": "unverifiable",
}
ESTATE_VENDORS = 120        # MODELED: vendors in a large bank's AI estate (an assumption, not a statistic)
CLASS_ORDER = ("high", "medium", "low")


# ---------------------------------------------------------------------------
# Parts 1 to 4
# ---------------------------------------------------------------------------
def control_score(data: dict, vid: str) -> dict:
    """Evidence-adjusted control score, 0 to 100, and what backed the answers."""
    row = data["answers"][vid]
    total = 0.0
    buckets = {"verified": 0, "unbacked": 0, "unverifiable": 0, "contradicted": 0}
    yes_unbacked = 0
    for q in data["questions"]:
        a = row[q["question_id"]]
        b = SUPPORT_BUCKET[answer_support(data, vid, q)]
        total += CREDIT[b][a]
        if a == "yes":
            buckets[b] += 1
            if b == "unbacked":
                yes_unbacked += 1
    return {"score": round(100.0 * total / len(row), 1), "yes_by_backing": buckets,
            "yes_unbacked": yes_unbacked}


def exit_readiness(v: dict) -> dict:
    """0 to 100: a clause (50), a tested exit (30), modeled time to exit inside the allowed window (20)."""
    clause = v["exit_clause"] == "yes"
    tested = clause and v["exit_tested"] == "yes"
    inside = exit_in_window(v)
    score = (50 if clause else 0) + (30 if tested else 0) + (20 if inside else 0)
    state = "ready" if score == 100 else ("partial" if clause else "not ready")
    return {"score": score, "state": state, "clause": clause, "tested": tested, "in_window": inside,
            "modeled_days": modeled_exit_days(v), "allowed_days": ALLOWED_EXIT_DAYS[v["criticality"]]}


def contract_gap(v: dict) -> float:
    return (0.5 if v["audit_right"] != "yes" else 0.0) + (0.5 if v["model_change_notice_days"] == 0 else 0.0)


def classify(risk: float, high_at: float = HIGH_AT, medium_at: float = MEDIUM_AT) -> str:
    return "high" if risk >= high_at else ("medium" if risk >= medium_at else "low")


def review_cadence_days(tier: str, cls: str) -> int:
    base = CADENCE_DAYS[tier]
    return base // 2 if cls == "high" else base


# ---------------------------------------------------------------------------
# Whole-estate scoring
# ---------------------------------------------------------------------------
def analyze(data: dict | None = None, conc_line: float = CONC_LINE, high_at: float = HIGH_AT,
            medium_at: float = MEDIUM_AT, weights: dict | None = None) -> dict:
    data = data or load_all()
    w = weights or WEIGHTS
    cv = concentration_view(data)
    total = cv["total"]
    flagged = {r["provider"]: r["share_pct"] for r in cv["rows"] if r["critical_use_cases"] / total > conc_line}
    rows = []
    for v in data["vendors"]:
        vid = v["vendor_id"]
        cs = control_score(data, vid)
        ex = exit_readiness(v)
        cg = contract_gap(v)
        if v["provider_disclosed"] and v["model_provider"] in flagged:
            conc_term, conc_note = 1.0, f"{v['model_provider']} carries {flagged[v['model_provider']]}% of critical use cases"
        elif not v["provider_disclosed"]:
            conc_term, conc_note = UNDISCLOSED_TERM, "upstream provider not disclosed"
        else:
            conc_term, conc_note = 0.0, ""
        exposure = CRIT_W[v["criticality"]] + DATA_W[v["data_access"]]
        mult = EXPOSURE_BASE + EXPOSURE_SLOPE * exposure
        parts = {
            "control": 100.0 * w["control"] * (1 - cs["score"] / 100.0) * mult,
            "exit": 100.0 * w["exit"] * (1 - ex["score"] / 100.0) * mult,
            "contract": 100.0 * w["contract"] * cg * mult,
            "concentration": 100.0 * w["concentration"] * conc_term * mult,
        }
        risk = round(sum(parts.values()), 1)
        cls = classify(risk, high_at, medium_at)
        cad = review_cadence_days(v["criticality"], cls)
        age = assessed_age_days(v)
        rows.append({
            "vendor_id": vid, "service_type": v["service_type"], "criticality": v["criticality"],
            "data_access": v["data_access"], "provider": v["model_provider"] or "undisclosed",
            "provider_disclosed": v["provider_disclosed"],
            "checklist_yes": yes_count(data["answers"][vid]), "checklist_pass": passes(data["answers"][vid]),
            "control_score": cs["score"], "yes_by_backing": cs["yes_by_backing"], "yes_unbacked": cs["yes_unbacked"],
            "evidence": {dt: evidence_status(data, vid, dt) for dt in DOC_TYPES},
            "exit_score": ex["score"], "exit_state": ex["state"], "exit_clause": v["exit_clause"],
            "exit_tested": v["exit_tested"], "modeled_exit_days": ex["modeled_days"], "allowed_exit_days": ex["allowed_days"],
            "audit_right": v["audit_right"], "notice_days": v["model_change_notice_days"], "contract_gap": cg,
            "conc_flag": conc_term == 1.0, "conc_term": conc_term, "conc_note": conc_note,
            "exposure": round(exposure, 2), "parts": {k: round(x, 1) for k, x in parts.items()},
            "risk": risk, "class": cls,
            "cadence_days": cad, "age_days": age, "overdue": age > cad,
            "days_overdue": max(0, age - cad),
            "next_review": (v["last_assessed_on"] + timedelta(days=cad)).isoformat(),
            "tier_cadence_days": CADENCE_DAYS[v["criticality"]],
            "true_risk": data["truth"][vid]["true_risk"] if vid in data["truth"] else None,
            "latent": data["truth"][vid]["latent"] if vid in data["truth"] else None,
            "overclaimed": data["truth"][vid]["overclaimed"] if vid in data["truth"] else None,
        })
    rows.sort(key=lambda r: (-r["risk"], r["vendor_id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["reasons"] = reasons(r)
    return {"data": data, "rows": rows, "conc": cv, "flagged": flagged,
            "summary": summarize(data, rows, cv, flagged)}


def reasons(r: dict) -> list:
    """Plain-English reasons, largest contribution first."""
    out = []
    p = r["parts"]
    order = sorted(p, key=lambda k: -p[k])
    for k in order:
        if p[k] <= 0:
            continue
        if k == "control":
            n = r["yes_unbacked"]
            out.append((k, f"control score {r['control_score']} of 100; {n} yes answer{'s' if n != 1 else ''} with no valid document"
                        + (f"; {r['yes_by_backing']['contradicted']} contradicted by the contract" if r["yes_by_backing"]["contradicted"] else "")))
        elif k == "exit":
            if r["exit_clause"] != "yes":
                out.append((k, "no exit clause"))
            elif r["exit_tested"] != "yes":
                out.append((k, "exit clause never tested" + ("" if r["modeled_exit_days"] <= r["allowed_exit_days"] else ", modeled exit longer than the allowed window")))
            else:
                out.append((k, "tested exit, but modeled exit longer than the allowed window"))
        elif k == "contract":
            bits = []
            if r["audit_right"] != "yes":
                bits.append("no audit right")
            if r["notice_days"] == 0:
                bits.append("no notice of model changes")
            out.append((k, ", ".join(bits)))
        elif k == "concentration":
            out.append((k, r["conc_note"]))
    return out


# ---------------------------------------------------------------------------
# Scoring the result against the truth (the only place truth is read)
# ---------------------------------------------------------------------------
def summarize(data: dict, rows: list, cv: dict, flagged: dict) -> dict:
    n = len(rows)
    truth_ok = all(r["true_risk"] is not None for r in rows)
    s: dict = {"vendors": n, "classes": {c: sum(1 for r in rows if r["class"] == c) for c in CLASS_ORDER}}
    s["flagged_providers"] = flagged
    s["hhi_disclosed"] = cv["hhi"]
    s["top_provider"] = cv["top"]["provider"]
    s["top_share_pct"] = cv["top"]["share_pct"]
    s["unknown_vendors"] = sum(1 for r in rows if not r["provider_disclosed"])
    s["unknown_use_cases"] = cv["unknown"]
    s["unknown_pct"] = cv["unknown_pct"]
    s["critical_use_cases"] = cv["total"]
    s["mean_control_score"] = round(sum(r["control_score"] for r in rows) / n, 1)
    s["mean_checklist_pct"] = round(sum(100.0 * r["checklist_yes"] / 20 for r in rows) / n, 1)
    s["exit"] = {k: sum(1 for r in rows if r["exit_state"] == k) for k in ("ready", "partial", "not ready")}
    s["critical_exit_not_ready"] = sum(1 for r in rows if r["criticality"] == "critical" and r["exit_state"] != "ready")
    s["critical"] = sum(1 for r in rows if r["criticality"] == "critical")
    s["overdue_vendorlens"] = sum(1 for r in rows if r["overdue"])
    s["overdue_tier"] = sum(1 for r in rows if r["age_days"] > r["tier_cadence_days"])
    s["overdue_flat"] = sum(1 for r in rows if r["age_days"] > FLAT_CYCLE_DAYS)
    s["extra_overdue_from_high"] = sum(1 for r in rows if r["overdue"] and r["age_days"] <= r["tier_cadence_days"])
    s["checklist_pass"] = sum(1 for r in rows if r["checklist_pass"])
    if not truth_ok:
        return s

    cm = {t: {p: 0 for p in CLASS_ORDER} for t in CLASS_ORDER}
    for r in rows:
        cm[r["true_risk"]][r["class"]] += 1
    true_high = [r for r in rows if r["true_risk"] == "high"]
    pred_high = [r for r in rows if r["class"] == "high"]
    tp = [r for r in pred_high if r["true_risk"] == "high"]
    q_found = [r for r in true_high if not r["checklist_pass"]]
    q_fail = [r for r in rows if not r["checklist_pass"]]
    s["confusion"] = cm
    s["true_high"] = len(true_high)
    s["pred_high"] = len(pred_high)
    s["high_tp"] = len(tp)
    s["high_precision_pct"] = pct(len(tp), len(pred_high))
    s["high_recall_pct"] = pct(len(tp), len(true_high))
    s["class_correct"] = sum(1 for r in rows if r["class"] == r["true_risk"])
    s["class_correct_pct"] = pct(s["class_correct"], n)
    s["checklist_found"] = len(q_found)
    s["checklist_fail"] = len(q_fail)
    s["checklist_precision_pct"] = pct(len(q_found), len(q_fail))
    s["checklist_recall_pct"] = pct(len(q_found), len(true_high))
    s["queue_size"] = len(q_fail)
    s["topk_found"] = sum(1 for r in rows[:len(q_fail)] if r["true_risk"] == "high")
    s["passed_high_total"] = sum(1 for r in true_high if r["checklist_pass"])
    s["passed_high_caught"] = sum(1 for r in true_high if r["checklist_pass"] and r["class"] == "high")
    s["passes_rated_high"] = sum(1 for r in rows if r["checklist_pass"] and r["class"] == "high")
    s["fails_rated_low"] = sum(1 for r in rows if not r["checklist_pass"] and r["class"] == "low")
    s["missed_high"] = [{"vendor_id": r["vendor_id"], "predicted": r["class"], "risk": r["risk"], "latent": r["latent"],
                         "checklist": "pass" if r["checklist_pass"] else "fail"} for r in true_high if r["class"] != "high"]
    s["false_high"] = [{"vendor_id": r["vendor_id"], "true_risk": r["true_risk"], "risk": r["risk"], "latent": r["latent"]}
                       for r in pred_high if r["true_risk"] != "high"]

    # Concentration against the hidden fourth parties (known by construction)
    total = cv["total"]
    true_cuc: dict = {}
    for v in data["vendors"]:
        p = data["truth"][v["vendor_id"]]["true_provider"]
        true_cuc[p] = true_cuc.get(p, 0) + v["critical_use_cases"]
    true_share = {p: round(100.0 * c / total, 1) for p, c in true_cuc.items()}
    true_hhi = round(sum((100.0 * c / total) ** 2 for c in true_cuc.values()))
    top = cv["top"]["provider"]
    hidden_on_top = sum(1 for v in data["vendors"] if not v["provider_disclosed"]
                        and data["truth"][v["vendor_id"]]["true_provider"] == top)
    hidden_cuc_on_top = sum(v["critical_use_cases"] for v in data["vendors"] if not v["provider_disclosed"]
                            and data["truth"][v["vendor_id"]]["true_provider"] == top)
    s["true_share_pct"] = dict(sorted(true_share.items()))
    s["true_top_share_pct"] = true_share.get(top)
    s["understated_points"] = round(true_share.get(top, 0.0) - cv["top"]["share_pct"], 1)
    s["hidden_on_top_vendors"] = hidden_on_top
    s["hidden_on_top_use_cases"] = hidden_cuc_on_top
    s["hhi_true"] = true_hhi
    s["upper_bound_top_pct"] = round(cv["top"]["share_pct"] + cv["unknown_pct"], 1)
    s["cannot_rule_out"] = [r["provider"] for r in cv["rows"]
                            if r["provider"] not in flagged and (r["critical_use_cases"] + cv["unknown"]) / total > CONC_LINE]

    # Utility (found rate x modeled estate size)
    rate_vl, rate_q = len(tp) / n, len(q_found) / n
    s["found_rate_vendorlens"] = round(rate_vl, 3)
    s["found_rate_checklist"] = round(rate_q, 3)
    s["estate_vendors"] = ESTATE_VENDORS
    s["utility_vendors"] = round((rate_vl - rate_q) * ESTATE_VENDORS, 1)
    s["utility_sensitivity"] = {str(k): round((rate_vl - rate_q) * k, 1) for k in (40, 80, 120, 200)}
    return s


def sensitivity(data: dict) -> dict:
    """How the HIGH result moves when my assumptions move. The truth is read only to score."""
    out = {"high_line": [], "conc_line": [], "weights": []}
    for h in (35.0, 40.0, 45.0, 50.0):
        s = analyze(data, high_at=h)["summary"]
        out["high_line"].append({"high_at": h, "flagged": s["pred_high"], "found": s["high_tp"], "of": s["true_high"]})
    for c in (0.35, 0.40, 0.45, 0.50):
        a = analyze(data, conc_line=c)
        s = a["summary"]
        out["conc_line"].append({"line": c, "providers_flagged": len(a["flagged"]), "flagged": s["pred_high"],
                                 "found": s["high_tp"], "of": s["true_high"]})
    eq = {"control": 0.25, "exit": 0.25, "contract": 0.25, "concentration": 0.25}
    s = analyze(data, weights=eq)["summary"]
    out["weights"].append({"name": "equal weights", "flagged": s["pred_high"], "found": s["high_tp"], "of": s["true_high"]})
    return out


def questionnaire_tag(r: dict) -> tuple:
    """(tag text, is_failure): the questionnaire verdict against the truth, for the app and the demo."""
    if r["checklist_pass"] and r["true_risk"] == "high":
        return "WRONG: passed a high-risk vendor", True
    if r["checklist_pass"] and r["true_risk"] == "medium":
        return "MISSED: passed with claims nobody checked", True
    if not r["checklist_pass"] and r["true_risk"] == "low":
        return "WRONG: failed a low-risk vendor", True
    return "Agrees with the truth", False


def vendorlens_tag(r: dict) -> str:
    """CAUGHT, FLAGGED (false alarm), MISSED (the known limit), AGREES or OFF BY ONE."""
    if r["class"] == "high" and r["true_risk"] == "high":
        return "CAUGHT"
    if r["class"] == "high":
        return "FLAGGED"
    if r["true_risk"] == "high":
        return "MISSED"
    return "AGREES" if r["class"] == r["true_risk"] else "OFF BY ONE"


def selftest(data: dict) -> int:
    """Checks that hold by design. Returns how many ran."""
    n = 0
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9; n += 1
    a = analyze(data)
    assert all(0 <= r["control_score"] <= 100 and 0 <= r["exit_score"] <= 100 for r in a["rows"]); n += 1
    assert all(r["class"] in CLASS_ORDER for r in a["rows"]); n += 1
    assert abs(sum(r["parts"][k] for r in a["rows"][:1] for k in r["parts"]) - a["rows"][0]["risk"]) < 0.3; n += 1
    # the scoring must not read the truth: remove it and the classes must not change
    blind = dict(data)
    blind["truth"] = {}
    b = analyze(blind)
    assert {r["vendor_id"]: (r["class"], r["risk"]) for r in a["rows"]} == {r["vendor_id"]: (r["class"], r["risk"]) for r in b["rows"]}; n += 1
    # a document that does not cover the AI service never counts as valid
    assert all(d["status"] != "valid" for ds in data["docs"].values() for d in ds if not d["covers"]); n += 1
    return n


def write_outputs(a: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_04_scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "vendor_id", "criticality", "data_access", "provider", "checklist", "control_score",
                    "exit_score", "contract_gap", "conc_flag", "risk", "class", "cadence_days", "age_days", "overdue",
                    "true_risk"])
        for r in a["rows"]:
            w.writerow([r["rank"], r["vendor_id"], r["criticality"], r["data_access"], r["provider"],
                        "pass" if r["checklist_pass"] else "fail", r["control_score"], r["exit_score"],
                        r["contract_gap"], "yes" if r["conc_flag"] else "no", r["risk"], r["class"],
                        r["cadence_days"], r["age_days"], "yes" if r["overdue"] else "no", r["true_risk"]])
    with open(OUT_DIR / "step_04_concentration.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["provider", "vendors", "critical_use_cases", "share_pct", "flagged"])
        for r in a["conc"]["rows"]:
            w.writerow([r["provider"], r["vendors"], r["critical_use_cases"], r["share_pct"],
                        "yes" if r["provider"] in a["flagged"] else "no"])
    with open(OUT_DIR / "step_04_summary.json", "w", encoding="utf-8") as f:
        json.dump(a["summary"], f, indent=2, default=str)


def main() -> None:
    data = load_all()
    checks = selftest(data)
    a = analyze(data)
    s, rows, cv = a["summary"], a["rows"], a["conc"]
    write_outputs(a)

    print("\n" + "=" * 78)
    print("Step 4 - VendorLens: evidence, concentration, exit and cadence")
    print("=" * 78)
    print(f"\nSelf-checks passed: {checks}. The scoring never reads data/truth.csv; truth is used only to score.")
    print("No model is used in this step. Everything is a rule you can read.\n")
    print("SETTINGS (my assumptions, edit at the top of the file):")
    print(f"  Weakness weights: control {WEIGHTS['control']}, exit {WEIGHTS['exit']}, contract {WEIGHTS['contract']}, "
          f"concentration {WEIGHTS['concentration']}")
    print(f"  Exposure by criticality: critical {CRIT_W['critical']}, important {CRIT_W['important']}, standard {CRIT_W['standard']}; "
          f"by data access: customer PII {DATA_W['customer_pii']}, internal {DATA_W['internal']}, none {DATA_W['none']}")
    print(f"  Risk = 100 x weakness x ({EXPOSURE_BASE} + {EXPOSURE_SLOPE} x exposure); HIGH at {HIGH_AT:.0f} or more, MEDIUM at {MEDIUM_AT:.0f} or more")
    print(f"  Concentration flag: one upstream provider above {int(CONC_LINE * 100)}% of critical use cases")
    print("  Credit per answer (yes / partial / no):")
    for k, label in (("verified", "backed by a valid document or the contract"), ("unbacked", "no valid document behind it"),
                     ("unverifiable", "no document here could check it"), ("contradicted", "the contract says otherwise")):
        c = CREDIT[k]
        print(f"    {label:<44} {c['yes']} / {c['partial']} / {c['no']}")
    print()

    print("1. EVIDENCE-ADJUSTED CONTROL SCORE")
    print(f"   Mean questionnaire yes rate {s['mean_checklist_pct']}%; mean evidence-adjusted control score {s['mean_control_score']} of 100.")
    print("2. CONCENTRATION")
    print(f"   {'provider':<9} {'vendors':>7} {'crit. use cases':>15} {'share':>7}  flag")
    for r in cv["rows"]:
        print(f"   {r['provider']:<9} {r['vendors']:>7} {r['critical_use_cases']:>15} {r['share_pct']:>6.1f}%  "
              f"{'FLAGGED' if r['provider'] in a['flagged'] else ''}")
    print(f"   {'unknown':<9} {s['unknown_vendors']:>7} {s['unknown_use_cases']:>15} {s['unknown_pct']:>6.1f}%  not disclosed")
    print(f"   HHI of the disclosed critical use cases: {s['hhi_disclosed']}")
    print("3. EXIT READINESS")
    print(f"   Ready {s['exit']['ready']}, partial {s['exit']['partial']}, not ready {s['exit']['not ready']} of {s['vendors']}; "
          f"critical vendors not ready: {s['critical_exit_not_ready']} of {s['critical']}.")
    print("4. REVIEW CADENCE (tier cadence; a HIGH vendor is reviewed twice as often)")
    print(f"   Overdue: {s['overdue_vendorlens']} of {s['vendors']} on VendorLens cadence "
          f"({s['overdue_tier']} on tier cadence alone, {s['extra_overdue_from_high']} more because they are HIGH); the flat cycle flags {s['overdue_flat']}.\n")

    print("RISK RANKING (top 14 of 40; 'pts' = points from control / exit / contract / concentration)")
    print(f"{'#':>2} {'vendor':<6} {'tier':<9} {'data':<12} {'ctrl':>5} {'exit':>4} {'pts':<18} {'risk':>5} {'class':<6} {'checklist':<9} {'truth':<6}")
    for r in rows[:14]:
        pts = "/".join(f"{r['parts'][k]:.0f}" for k in ("control", "exit", "contract", "concentration"))
        print(f"{r['rank']:>2} {r['vendor_id']:<6} {r['criticality']:<9} {r['data_access']:<12} {r['control_score']:>5.1f} "
              f"{r['exit_score']:>4} {pts:<18} {r['risk']:>5.1f} {r['class'].upper():<6} "
              f"{'pass' if r['checklist_pass'] else 'fail':<9} {r['true_risk']:<6}")
    print("   ...")
    print(f"   Classes: {s['classes']['high']} HIGH, {s['classes']['medium']} MEDIUM, {s['classes']['low']} LOW.")

    print("\nMEASURED AGAINST THE TRUTH FILE (synthetic: the generator decided the true risk)")
    print(f"  Class agreement:           {s['class_correct']} of {s['vendors']} vendors ({s['class_correct_pct']}%)")
    print(f"  HIGH, VendorLens:          flagged {s['pred_high']}, truly high {s['high_tp']}; "
          f"precision {s['high_precision_pct']}% ({s['high_tp']} of {s['pred_high']}), recall {s['high_recall_pct']}% ({s['high_tp']} of {s['true_high']})")
    print(f"  HIGH, questionnaire fail:  flagged {s['checklist_fail']}, truly high {s['checklist_found']}; "
          f"precision {s['checklist_precision_pct']}% ({s['checklist_found']} of {s['checklist_fail']}), recall {s['checklist_recall_pct']}% ({s['checklist_found']} of {s['true_high']})")
    print(f"  Same review-queue size ({s['queue_size']} vendors, as many as the questionnaire fails): VendorLens's top {s['queue_size']} "
          f"hold {s['topk_found']} of {s['true_high']} truly high-risk vendors; the questionnaire's fails hold {s['checklist_found']}")
    print(f"  Truly high-risk vendors that passed the questionnaire: {s['passed_high_total']}; VendorLens rates {s['passed_high_caught']} of them HIGH")
    print(f"  Passing vendors VendorLens rates HIGH: {s['passes_rated_high']}; failing vendors it rates LOW: {s['fails_rated_low']}")
    print("  Confusion (rows: truth, columns: VendorLens):")
    print(f"    {'':<8} {'HIGH':>5} {'MEDIUM':>7} {'LOW':>5}")
    for t in CLASS_ORDER:
        print(f"    {t:<8} {s['confusion'][t]['high']:>5} {s['confusion'][t]['medium']:>7} {s['confusion'][t]['low']:>5}")

    sens = sensitivity(data)
    print("\nSENSITIVITY TO MY ASSUMPTIONS (the truth is read only to count)")
    for x in sens["high_line"]:
        print(f"  HIGH line {x['high_at']:.0f}: flagged {x['flagged']}, truly high {x['found']} of {x['of']}")
    for x in sens["conc_line"]:
        print(f"  Concentration line {int(x['line'] * 100)}%: {x['providers_flagged']} provider(s) flagged; HIGH flagged {x['flagged']}, truly high {x['found']} of {x['of']}")
    for x in sens["weights"]:
        print(f"  {x['name'].capitalize()}: HIGH flagged {x['flagged']}, truly high {x['found']} of {x['of']}")

    print("\nKNOWN LIMIT (left in on purpose)")
    print(f"  1. Weights, the HIGH line and the {int(CONC_LINE * 100)}% concentration line are my assumptions. The sensitivity above shows how the result moves.")
    print("  2. Evidence authenticity is not verified. A document counts as valid if it exists, is recent and covers the AI service;")
    print("     the data has no field for a forged or inaccurate report, so this limit cannot be measured here.")
    print(f"  3. Vendors that do not disclose their upstream provider make concentration understated by construction:")
    print(f"     {s['unknown_vendors']} of {s['vendors']} vendors, {s['unknown_use_cases']} of {s['critical_use_cases']} critical use cases ({s['unknown_pct']}%) sit in the unknown bucket.")
    print(f"     Truth: {s['hidden_on_top_vendors']} of them run on {s['top_provider']}, carrying {s['hidden_on_top_use_cases']} critical use cases. "
          f"{s['top_provider']} is shown at {s['top_share_pct']}% and is really {s['true_top_share_pct']}% ({s['understated_points']} points higher).")
    print(f"     HHI shown {s['hhi_disclosed']}, true {s['hhi_true']}. Upper bound for {s['top_provider']} if every unknown vendor ran on it: {s['upper_bound_top_pct']}%.")
    print(f"     Providers VendorLens cannot rule out as concentrated: {', '.join(s['cannot_rule_out']) if s['cannot_rule_out'] else 'none'}.")
    print(f"  4. Real misses. Truly high-risk vendors not rated HIGH: {len(s['missed_high'])} of {s['true_high']}.")
    for m in s["missed_high"]:
        print(f"     {m['vendor_id']}: rated {m['predicted'].upper()} (risk {m['risk']}), questionnaire {m['checklist']}, latent truth {m['latent']}")
    print(f"     Rated HIGH but not truly high: {len(s['false_high'])}.")
    for m in s["false_high"]:
        print(f"     {m['vendor_id']}: truly {m['true_risk']} (risk {m['risk']}, latent truth {m['latent']})")
    print("     The truth carries an unobserved factor, so no score built from answers, documents and contracts can match it exactly.")

    print("\nUTILITY (high-risk vendors found per vendor assessed)")
    print(f"  Questionnaire: {s['checklist_found']} of {s['vendors']} vendors found ({s['found_rate_checklist']:.3f} per vendor).")
    print(f"  VendorLens:    {s['high_tp']} of {s['vendors']} vendors found ({s['found_rate_vendorlens']:.3f} per vendor).")
    print(f"  MODELED: {s['estate_vendors']} vendors in a bank's AI estate (assumption, not a statistic; edit ESTATE_VENDORS).")
    print(f"  Utility = ({s['found_rate_vendorlens']:.3f} - {s['found_rate_checklist']:.3f}) x {s['estate_vendors']} = {s['utility_vendors']} more high-risk vendors found")
    print("  Sensitivity to estate size: " + ", ".join(f"{k}: {v}" for k, v in s["utility_sensitivity"].items()))
    print("\nWrote src/out/step_04_scores.csv, step_04_concentration.csv and step_04_summary.json")


if __name__ == "__main__":
    main()
