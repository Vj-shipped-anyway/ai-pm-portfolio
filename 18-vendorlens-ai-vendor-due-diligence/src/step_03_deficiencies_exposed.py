"""Step 3 - Where the questionnaire breaks: six named deficiencies, each with a count.

Step 2 showed that a questionnaire with an 85 percent line passes most vendors, including
some that are truly high risk. This step asks what the checklist cannot do, using the same 40
synthetic vendors.

  (1) Self-declared answers over-claim: passes with missing, stale or out-of-scope evidence.
  (2) A vendor-by-vendor view hides fourth-party concentration on one upstream model provider.
  (3) Exit readiness is never asked: no exit clause, no tested exit, a modeled time to exit
      longer than the allowed window.
  (4) Data access is not weighted: vendors that hold customer PII face the same line.
  (5) Stale assessments: not reassessed inside the cadence the vendor's tier calls for.
  (6) Contract gaps: no audit right, no notice of a model change.

Counts of evidence, contract and exit facts come from vendors.csv and evidence.csv. Counts
labeled "truth" come from truth.csv, which the generator wrote; they are used to score, not to
decide. Items marked MODELED depend on an assumption named in step_01 (tier cadence, allowed
exit window, modeled time to exit).

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deficiencies.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

from step_01_status_quo import (
    AS_OF, CADENCE_DAYS, DOC_TYPES, FLAT_CYCLE_DAYS, OUT_DIR, ALLOWED_EXIT_DAYS, answer_support,
    assessed_age_days, exit_in_window, load_all, modeled_exit_days,
)
from step_02_questionnaire_checklist import PASS_YES_PCT, passes, pct


def concentration_view(data: dict) -> dict:
    """The disclosed view: share of ALL critical use cases by upstream provider, plus an
    unknown bucket for vendors that do not disclose. HHI is on disclosed use cases only."""
    total = sum(v["critical_use_cases"] for v in data["vendors"])
    by_p: dict = {}
    unknown = 0
    vendors_on: dict = {}
    for v in data["vendors"]:
        if not v["provider_disclosed"]:
            unknown += v["critical_use_cases"]
            continue
        p = v["model_provider"]
        by_p[p] = by_p.get(p, 0) + v["critical_use_cases"]
        vendors_on.setdefault(p, []).append(v["vendor_id"])
    disclosed_total = sum(by_p.values())
    hhi = round(sum((100.0 * n / disclosed_total) ** 2 for n in by_p.values()))
    rows = [{"provider": p, "vendors": len(vendors_on[p]), "critical_use_cases": by_p[p],
             "share_pct": pct(by_p[p], total)} for p in sorted(by_p, key=lambda x: (-by_p[x], x))]
    return {"total": total, "rows": rows, "unknown": unknown, "unknown_pct": pct(unknown, total),
            "hhi": hhi, "vendors_on": vendors_on, "top": rows[0]}


def summarize(data: dict) -> dict:
    vs, by_id, ids = data["vendors"], data["by_id"], data["ids"]
    n = len(vs)
    passing = [vid for vid in ids if passes(data["answers"][vid])]
    n_pass = len(passing)
    critical = [v["vendor_id"] for v in vs if v["criticality"] == "critical"]

    # (1) over-claim versus evidence -------------------------------------------------------
    ev_q = [q for q in data["questions"] if q["verified_by"] in DOC_TYPES]
    pairs = Counter()                       # (vendor, document type) on passing vendors
    pass_gap = 0
    yes_backed = yes_unbacked = 0
    strict_drop = 0
    contradicted = contradicted_pass = 0
    for vid in passing:
        sts = [answer_support(data, vid, {"question_id": "-", "verified_by": dt}) for dt in DOC_TYPES]
        for st in sts:
            pairs[st.replace("evidence_", "")] += 1
        if any(st != "evidence_valid" for st in sts):
            pass_gap += 1
    for vid in ids:
        a = data["answers"][vid]
        counted = 0
        for q in data["questions"]:
            sup = answer_support(data, vid, q)
            if a[q["question_id"]] == "yes":
                if q["verified_by"] in DOC_TYPES and vid in passing:
                    if sup == "evidence_valid":
                        yes_backed += 1
                    else:
                        yes_unbacked += 1
                if sup == "contract_contradicts":
                    contradicted += 1
                    contradicted_pass += 1 if vid in passing else 0
                if sup in ("evidence_valid", "contract_supports", "unverifiable"):
                    counted += 1
        if vid in passing and counted * 100 < PASS_YES_PCT * len(a):
            strict_drop += 1
    claimers = [vid for vid in passing if data["truth"][vid]["overclaimed"] > 0]
    claimers_touched = [vid for vid in claimers if any(
        answer_support(data, vid, q) not in ("evidence_valid", "contract_supports", "unverifiable")
        for q in data["questions"] if data["answers"][vid][q["question_id"]] == "yes")]
    d1 = {"passes": n_pass, "passes_with_evidence_gap": pass_gap,
          "pairs_total": n_pass * len(DOC_TYPES), "pairs_valid": pairs["valid"], "pairs_stale": pairs["stale"],
          "pairs_out_of_scope": pairs["out_of_scope"], "pairs_missing": pairs["missing"],
          "yes_on_evidence_questions": yes_backed + yes_unbacked, "yes_without_valid_evidence": yes_unbacked,
          "yes_without_valid_evidence_pct": pct(yes_unbacked, yes_backed + yes_unbacked),
          "strict_drop": strict_drop, "contradicted_yes": contradicted, "contradicted_yes_on_passes": contradicted_pass,
          "truth_passes_with_overclaim": len(claimers), "truth_overclaim_touched_by_gap": len(claimers_touched)}

    # (2) concentration hidden by the vendor-by-vendor view --------------------------------
    cv = concentration_view(data)
    top = cv["top"]
    top_vendors = cv["vendors_on"][top["provider"]]
    asks = sum(1 for q in data["questions"] if "provider" in q["text"].lower() or "upstream" in q["text"].lower())
    d2 = {"providers": len(cv["rows"]), "critical_use_cases": cv["total"], "rows": cv["rows"],
          "top_provider": top["provider"], "top_share_pct": top["share_pct"], "top_vendors": len(top_vendors),
          "top_vendors_passing": sum(1 for vid in top_vendors if vid in passing),
          "top_critical_use_cases": top["critical_use_cases"], "hhi": cv["hhi"],
          "unknown": cv["unknown"], "unknown_pct": cv["unknown_pct"], "questions_asking_provider": asks,
          "questions": len(data["questions"])}

    # (3) exit readiness never asked ---------------------------------------------------------
    no_clause = [v for v in vs if v["exit_clause"] != "yes"]
    untested = [v for v in vs if v["exit_clause"] == "yes" and v["exit_tested"] != "yes"]
    not_ready = no_clause + untested
    out_window = [v for v in vs if not exit_in_window(v)]
    d3 = {"no_clause": len(no_clause), "clause_untested": len(untested), "no_clause_or_test": len(not_ready),
          "exit_tested": sum(1 for v in vs if v["exit_tested"] == "yes"),
          "critical": len(critical),
          "critical_no_clause": sum(1 for v in no_clause if v["criticality"] == "critical"),
          "critical_no_clause_or_test": sum(1 for v in not_ready if v["criticality"] == "critical"),
          "out_of_window": len(out_window),
          "critical_out_of_window": sum(1 for v in out_window if v["criticality"] == "critical"),
          "out_of_window_passing": sum(1 for v in out_window if v["vendor_id"] in passing),
          "questions_asking_exit": sum(1 for q in data["questions"] if "exit" in q["text"].lower()),
          "questions": len(data["questions"])}

    # (4) data access is not weighted ----------------------------------------------------------
    pii = [v["vendor_id"] for v in vs if v["data_access"] == "customer_pii"]
    nonpii = [v["vendor_id"] for v in vs if v["data_access"] != "customer_pii"]
    pii_pass = [vid for vid in pii if vid in passing]
    d4 = {"pii": len(pii), "pii_passing": len(pii_pass), "pii_passing_pct": pct(len(pii_pass), len(pii)),
          "nonpii": len(nonpii), "nonpii_passing": sum(1 for vid in nonpii if vid in passing),
          "nonpii_passing_pct": pct(sum(1 for vid in nonpii if vid in passing), len(nonpii)),
          "pass_line_pct": PASS_YES_PCT,
          "pii_passing_critical": sum(1 for vid in pii_pass if by_id[vid]["criticality"] == "critical"),
          "pii_passing_truly_high": sum(1 for vid in pii_pass if data["truth"][vid]["true_risk"] == "high"),
          "pii_passing_truly_medium_or_high": sum(1 for vid in pii_pass if data["truth"][vid]["true_risk"] != "low")}

    # (5) stale assessments ----------------------------------------------------------------------
    over_tier = [v for v in vs if assessed_age_days(v) > CADENCE_DAYS[v["criticality"]]]
    over_flat = [v for v in vs if assessed_age_days(v) > FLAT_CYCLE_DAYS]
    d5 = {"overdue_by_tier": len(over_tier), "overdue_flat": len(over_flat),
          "critical_overdue": sum(1 for v in over_tier if v["criticality"] == "critical"),
          "critical": len(critical),
          "important_overdue": sum(1 for v in over_tier if v["criticality"] == "important"),
          "important": sum(1 for v in vs if v["criticality"] == "important"),
          "standard_overdue": sum(1 for v in over_tier if v["criticality"] == "standard"),
          "missed_by_flat_cycle": sum(1 for v in over_tier if v not in over_flat),
          "cadence_months": {k: round(d / 30.4375) for k, d in CADENCE_DAYS.items()}}

    # (6) contract gaps ------------------------------------------------------------------------------
    no_audit = [v for v in vs if v["audit_right"] != "yes"]
    no_notice = [v for v in vs if v["model_change_notice_days"] == 0]
    both = [v for v in no_audit if v["model_change_notice_days"] == 0]
    either = {v["vendor_id"] for v in no_audit} | {v["vendor_id"] for v in no_notice}
    claims_audit = sum(1 for v in no_audit if data["answers"][v["vendor_id"]]["Q16"] == "yes")
    claims_notice = sum(1 for v in no_notice if data["answers"][v["vendor_id"]]["Q15"] == "yes")
    d6 = {"no_audit": len(no_audit), "no_notice": len(no_notice), "both": len(both), "either": len(either),
          "either_passing": sum(1 for vid in either if vid in passing),
          "critical_either": sum(1 for vid in either if by_id[vid]["criticality"] == "critical"),
          "critical": len(critical),
          "claims_audit_yes": claims_audit, "claims_notice_yes": claims_notice}

    return {"vendors": n, "passes": n_pass, "d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5, "d6": d6}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)
    n = s["vendors"]
    d1, d2, d3, d4, d5, d6 = (s[k] for k in ("d1", "d2", "d3", "d4", "d5", "d6"))

    print("\n" + "=" * 78)
    print("Step 3 - Where the questionnaire breaks: six named deficiencies")
    print("=" * 78)
    print(f"\n{n} synthetic vendors; {s['passes']} pass the 85% checklist. As-of date {AS_OF.isoformat()}.")
    print("MODELED items depend on assumptions named in step_01 (tier cadence, allowed exit window, modeled time to exit).\n")

    print("(1) Self-declared answers over-claim")
    print(f"    {d1['passes_with_evidence_gap']} of {d1['passes']} passing vendors have at least one evidence type that is missing, stale or out of scope.")
    print(f"    Across the passing vendors' {d1['pairs_total']} vendor-document slots: {d1['pairs_valid']} valid, "
          f"{d1['pairs_missing']} missing, {d1['pairs_stale']} stale, {d1['pairs_out_of_scope']} out of scope.")
    print(f"    {d1['yes_without_valid_evidence']} of {d1['yes_on_evidence_questions']} yes answers on evidence-backed questions "
          f"({d1['yes_without_valid_evidence_pct']}%) have no valid document behind them.")
    print(f"    {d1['contradicted_yes']} yes answers on audit or model-change notice are contradicted by the vendor's own contract "
          f"({d1['contradicted_yes_on_passes']} of them on vendors that pass).")
    print(f"    Strict reading: {d1['strict_drop']} of {d1['passes']} passes drop under the 85% line if only backed or unverifiable yes answers count.")
    print(f"    Truth: {d1['truth_passes_with_overclaim']} of {d1['passes']} passing vendors over-claimed at least one answer; "
          f"{d1['truth_overclaim_touched_by_gap']} of those have a yes with no valid backing.\n")

    print("(2) A vendor-by-vendor view hides concentration on one upstream model provider")
    print(f"    The questionnaire asks which model provider a vendor runs on in {d2['questions_asking_provider']} of {d2['questions']} questions.")
    print("    Share of all critical use cases by disclosed provider:")
    for r in d2["rows"]:
        print(f"      {r['provider']}  {r['vendors']:>2} vendors  {r['critical_use_cases']:>2} critical use cases  {r['share_pct']:>5.1f}%")
    print(f"      unknown  vendors that do not disclose: {d2['unknown']} critical use cases ({d2['unknown_pct']}%)")
    print(f"    Top provider {d2['top_provider']}: {d2['top_share_pct']}% of {d2['critical_use_cases']} critical use cases across {d2['top_vendors']} vendors; "
          f"{d2['top_vendors_passing']} of those {d2['top_vendors']} vendors pass on their own.")
    print(f"    HHI of the disclosed critical use cases: {d2['hhi']} (scale 0 to 10,000; higher is more concentrated).\n")

    print("(3) Exit readiness is never asked")
    print(f"    The questionnaire asks about exit in {d3['questions_asking_exit']} of {d3['questions']} questions.")
    print(f"    {d3['no_clause']} of {n} vendors have no exit clause; {d3['clause_untested']} more have a clause that was never tested "
          f"({d3['no_clause_or_test']} of {n} without a tested exit).")
    print(f"    {d3['critical_no_clause_or_test']} of {d3['critical']} critical vendors have no tested exit ({d3['critical_no_clause']} have no clause at all).")
    print(f"    MODELED: {d3['out_of_window']} of {n} vendors would take longer to exit than the allowed window "
          f"({d3['critical_out_of_window']} of {d3['critical']} critical); {d3['out_of_window_passing']} of those pass the questionnaire.")
    print(f"    Allowed windows (days): critical {ALLOWED_EXIT_DAYS['critical']}, important {ALLOWED_EXIT_DAYS['important']}, standard {ALLOWED_EXIT_DAYS['standard']}.\n")

    print("(4) Data access is not weighted")
    print(f"    The same {d4['pass_line_pct']}% line applies to every vendor. {d4['pii_passing']} of {d4['pii']} vendors with customer PII access pass "
          f"({d4['pii_passing_pct']}%); {d4['nonpii_passing']} of {d4['nonpii']} without it pass ({d4['nonpii_passing_pct']}%).")
    print(f"    Of the {d4['pii_passing']} passing PII vendors, {d4['pii_passing_critical']} are critical. "
          f"Truth: {d4['pii_passing_truly_high']} are truly high risk and {d4['pii_passing_truly_medium_or_high']} are medium or high.\n")

    cm = d5["cadence_months"]
    print("(5) Stale assessments")
    print(f"    MODELED tier cadence: critical {cm['critical']} months, important {cm['important']}, standard {cm['standard']}. The status quo uses one {FLAT_CYCLE_DAYS // 30} month cycle.")
    print(f"    {d5['overdue_by_tier']} of {n} vendors are overdue on their tier cadence; the flat cycle flags {d5['overdue_flat']}.")
    print(f"    Overdue: {d5['critical_overdue']} of {d5['critical']} critical, {d5['important_overdue']} of {d5['important']} important, "
          f"{d5['standard_overdue']} standard. The flat cycle misses {d5['missed_by_flat_cycle']} of them.\n")

    print("(6) Contract gaps")
    print(f"    {d6['no_audit']} of {n} vendors have no audit right; {d6['no_notice']} of {n} have no commitment to notify before a model change; {d6['both']} have neither.")
    print(f"    {d6['either']} of {n} vendors have at least one gap ({d6['either_passing']} of them pass the questionnaire; "
          f"{d6['critical_either']} of {d6['critical']} critical vendors).")
    print(f"    {d6['claims_audit_yes']} of {d6['no_audit']} vendors with no audit right answered yes to \"customers may audit\"; "
          f"{d6['claims_notice_yes']} of {d6['no_notice']} with no notice commitment answered yes to \"notified before a model change\".\n")

    print("The checklist counts the word yes. It does not weigh the claim against a document, a contract, a shared")
    print("upstream provider, an exit plan or the data the vendor holds. The product is the evidence adjustment, the")
    print("concentration view, the exit score and the cadence, not another questionnaire.")

    rows = [
        (1, "Self-declared answers over-claim", d1["passes_with_evidence_gap"], d1["passes"]),
        (2, "Vendor-by-vendor view hides concentration", d2["top_vendors"], n),
        (3, "Exit readiness never asked", d3["no_clause_or_test"], n),
        (4, "Data access not weighted", d4["pii_passing"], d4["pii"]),
        (5, "Stale assessments", d5["overdue_by_tier"], n),
        (6, "Contract gaps", d6["either"], n),
    ]
    with open(OUT_DIR / "step_03_deficiencies.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "deficiency", "count", "of"])
        w.writerows(rows)
    with open(OUT_DIR / "step_03_summary.json", "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_03_deficiencies.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
