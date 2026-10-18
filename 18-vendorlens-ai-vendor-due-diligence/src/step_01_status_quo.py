"""Step 1 - Before VendorLens: a questionnaire and one review cycle for every AI vendor.

A modeled bank has 40 AI vendors. Due diligence is a questionnaire the vendor fills in. This
script describes that status quo on the synthetic estate in data/: how many vendors are
critical, how many hold customer data, how old the last assessments are, and what the bank
holds today. It scores nothing yet.

The estate is made up. Vendor ids (V-01 to V-40) and upstream model providers (MP-1 to MP-5)
are invented codes; nothing here is a real vendor, provider, bank or dataset. No model is used
anywhere in this repo.

ASSUMPTIONS of a modeled bank (not legal advice, not a statistic; edit them below):
  A1. The questionnaire is the assessment. Documents a vendor sends with it are filed, not
      read against the answers.
  A2. Every vendor is reassessed on one flat cycle (FLAT_CYCLE_DAYS), whatever its tier.
  A3. Nothing in the process asks which upstream model provider a vendor runs on, or how
      the bank would leave.

Shared definitions (later steps and the app import these): the loaders, the evidence-status
rule, the tier review cadence, the allowed exit window and the modeled time to exit.

Run (from src/):
    python3 step_01_status_quo.py

Output: a readable summary, plus out/step_01_estate.csv and out/step_01_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

# ---------------------------------------------------------------------------
# Assumptions of a modeled bank (all MODELED; none is a regulatory requirement)
# ---------------------------------------------------------------------------
AS_OF = date(2026, 10, 15)                      # same constant as data/_generate.py
EVIDENCE_MAX_AGE_DAYS = 365                     # a document older than this is stale
FLAT_CYCLE_DAYS = 730                           # status quo: one 24-month cycle for everyone
CADENCE_DAYS = {"critical": 365, "important": 730, "standard": 1095}   # tier cadence (12/24/36 months)
ALLOWED_EXIT_DAYS = {"critical": 45, "important": 90, "standard": 150}  # allowed transition window
NO_CLAUSE_EXIT_DAYS = 180                       # modeled time to exit with no exit clause
UNTESTED_EXIT_FACTOR = 1.5                      # an untested exit plan runs 50 percent over
TIERS = ("critical", "important", "standard")
DOC_TYPES = ("independent_control_report", "penetration_test", "model_documentation")
# Questions a contract field can check (verified_by == "contract" in data/questions.csv).
CONTRACT_CHECK = {
    "Q15": lambda v: v["model_change_notice_days"] > 0,     # notice before a model version changes
    "Q16": lambda v: v["audit_right"] == "yes",             # right to audit
}


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load the five CSVs into plain dicts. No pandas needed."""
    with open(data_dir / "vendors.csv", newline="", encoding="utf-8") as f:
        vendors = list(csv.DictReader(f))
    for v in vendors:
        for k in ("use_cases_supported", "critical_use_cases", "model_change_notice_days"):
            v[k] = int(v[k])
        v["portability_days"] = int(v["portability_days"]) if v["portability_days"] else None
        v["last_assessed_on"] = _d(v["last_assessed_on"])
        v["contract_end"] = _d(v["contract_end"])
        v["provider_disclosed"] = bool(v["model_provider"])
    by_id = {v["vendor_id"]: v for v in vendors}

    with open(data_dir / "questions.csv", newline="", encoding="utf-8") as f:
        questions = list(csv.DictReader(f))
    with open(data_dir / "questionnaire.csv", newline="", encoding="utf-8") as f:
        answers = {r["vendor_id"]: {q["question_id"]: r[q["question_id"]] for q in questions}
                   for r in csv.DictReader(f)}

    docs: dict = defaultdict(list)
    with open(data_dir / "evidence.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            issued = _d(r["issued_on"])
            doc = {"doc_type": r["doc_type"], "issued_on": issued, "covers": r["covers_ai_service"] == "yes",
                   "age_days": (AS_OF - issued).days}
            doc["status"] = doc_status(doc)
            docs[r["vendor_id"]].append(doc)

    truth = {}                  # empty when truth.csv is absent (real exports have none)
    if (data_dir / "truth.csv").exists():
        with open(data_dir / "truth.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                truth[r["vendor_id"]] = {
                    "true_risk": r["true_risk"], "latent": float(r["latent_risk"]),
                    "overclaimed": int(r["overclaimed_answers"]),
                    "provider_disclosed": r["provider_disclosed"] == "yes",
                    "true_provider": r["true_model_provider"],
                }
    return {"vendors": vendors, "by_id": by_id, "ids": [v["vendor_id"] for v in vendors],
            "questions": questions, "answers": answers, "docs": dict(docs), "truth": truth}


# ---------------------------------------------------------------------------
# Shared rules
# ---------------------------------------------------------------------------
def doc_status(doc: dict) -> str:
    """One document: out_of_scope if it does not cover the AI service, stale if older than
    EVIDENCE_MAX_AGE_DAYS, otherwise valid."""
    if not doc["covers"]:
        return "out_of_scope"
    if doc["age_days"] > EVIDENCE_MAX_AGE_DAYS:
        return "stale"
    return "valid"


_STATUS_ORDER = ["valid", "stale", "out_of_scope", "missing"]


def evidence_status(data: dict, vendor_id: str, doc_type: str) -> str:
    """The best status among a vendor's documents of one type: valid, stale, out_of_scope or missing."""
    found = [d["status"] for d in data["docs"].get(vendor_id, []) if d["doc_type"] == doc_type]
    if not found:
        return "missing"
    return min(found, key=_STATUS_ORDER.index)


def answer_support(data: dict, vendor_id: str, question: dict) -> str:
    """What backs one answer: evidence_valid, evidence_stale, evidence_out_of_scope,
    evidence_missing, contract_supports, contract_contradicts or unverifiable (no document in
    this repo could check it)."""
    kind = question["verified_by"]
    if kind in DOC_TYPES:
        return "evidence_" + evidence_status(data, vendor_id, kind)
    if kind == "contract":
        ok = CONTRACT_CHECK[question["question_id"]](data["by_id"][vendor_id])
        return "contract_supports" if ok else "contract_contradicts"
    return "unverifiable"


def assessed_age_days(v: dict) -> int:
    return (AS_OF - v["last_assessed_on"]).days


def modeled_exit_days(v: dict) -> float:
    """MODELED time to exit: no clause = 180 days; a clause with an exit test = the stated
    portability days; a clause never tested = stated days x 1.5."""
    if v["exit_clause"] != "yes":
        return float(NO_CLAUSE_EXIT_DAYS)
    days = float(v["portability_days"])
    return days if v["exit_tested"] == "yes" else days * UNTESTED_EXIT_FACTOR


def exit_in_window(v: dict) -> bool:
    return modeled_exit_days(v) <= ALLOWED_EXIT_DAYS[v["criticality"]]


def months(days: float) -> float:
    return days / 30.4375


# ---------------------------------------------------------------------------
# Status quo summary
# ---------------------------------------------------------------------------
def summarize(data: dict) -> dict:
    vs = data["vendors"]
    n = len(vs)
    crit = Counter(v["criticality"] for v in vs)
    access = Counter(v["data_access"] for v in vs)
    ages = sorted(assessed_age_days(v) for v in vs)
    total_cuc = sum(v["critical_use_cases"] for v in vs)
    ends_soon = [v for v in vs if (v["contract_end"] - AS_OF).days <= 180]
    return {
        "vendors": n,
        "critical": crit["critical"], "important": crit["important"], "standard": crit["standard"],
        "pii": access["customer_pii"], "internal": access["internal"], "no_data": access["none"],
        "critical_pii": sum(1 for v in vs if v["criticality"] == "critical" and v["data_access"] == "customer_pii"),
        "critical_use_cases": total_cuc,
        "critical_use_cases_on_critical_vendors": sum(v["critical_use_cases"] for v in vs if v["criticality"] == "critical"),
        "undisclosed": sum(1 for v in vs if not v["provider_disclosed"]),
        "answers": sum(len(a) for a in data["answers"].values()),
        "questions": len(data["questions"]),
        "documents": sum(len(d) for d in data["docs"].values()),
        "vendors_with_documents": len(data["docs"]),
        "median_age_days": int(statistics.median(ages)),
        "oldest_age_days": ages[-1],
        "over_12_months": sum(1 for a in ages if a > 365),
        "over_24_months": sum(1 for a in ages if a > FLAT_CYCLE_DAYS),
        "contracts_ending_180d": len(ends_soon),
        "contracts_expired": sum(1 for v in vs if v["contract_end"] < AS_OF),
        "flat_cycle_days": FLAT_CYCLE_DAYS,
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)

    print("\n" + "=" * 78)
    print("Step 1 - Before VendorLens: a questionnaire and one review cycle for every vendor")
    print("=" * 78)
    print(f"\n{s['vendors']} AI vendors of a modeled bank (V-01 to V-40), {s['questions']} questions, "
          f"{s['documents']} documents on file.")
    print("Data is synthetic and seeded. Vendor ids and model providers (MP-1 to MP-5) are invented codes.")
    print("No model is used anywhere in this repo.\n")
    print("ASSUMPTIONS (modeled):")
    print("  A1  the questionnaire is the assessment; documents sent with it are filed, not checked")
    print(f"  A2  one flat reassessment cycle for every vendor: {s['flat_cycle_days']} days (24 months)")
    print("  A3  nothing asks which upstream model provider a vendor runs on, or how the bank would leave\n")

    print("THE ESTATE")
    print(f"  Criticality:           {s['critical']} critical, {s['important']} important, {s['standard']} standard")
    print(f"  Data access:           {s['pii']} hold customer PII, {s['internal']} internal data, {s['no_data']} none")
    print(f"  Critical and PII:      {s['critical_pii']} vendors are both")
    print(f"  Critical use cases:    {s['critical_use_cases']} across the estate, "
          f"{s['critical_use_cases_on_critical_vendors']} of them on critical vendors")
    print(f"  Upstream provider:     {s['undisclosed']} vendors do not disclose it")

    print("\nWHAT THE BANK HOLDS TODAY")
    print(f"  Self-declared answers: {s['answers']} ({s['vendors']} vendors x {s['questions']} questions)")
    print(f"  Documents on file:     {s['documents']} from {s['vendors_with_documents']} vendors; filed, not read against the answers (A1)")
    print(f"  Contracts:             {s['contracts_ending_180d']} end within 180 days "
          f"(of which {s['contracts_expired']} already past their end date)")

    print("\nLAST ASSESSED (days before the as-of date)")
    print(f"  {'vendor':<7} {'tier':<10} {'data':<13} {'last assessed':<14} {'age (days)':>10}")
    for v in sorted(data["vendors"], key=lambda x: -assessed_age_days(x))[:8]:
        print(f"  {v['vendor_id']:<7} {v['criticality']:<10} {v['data_access']:<13} "
              f"{v['last_assessed_on'].isoformat():<14} {assessed_age_days(v):>10}")
    print("  ...")

    print("\nRESULT")
    print(f"  {s['critical']} of {s['vendors']} vendors are critical; {s['pii']} of {s['vendors']} hold customer PII; "
          f"{s['critical_pii']} are both.")
    print(f"  Median time since last assessment: {s['median_age_days']} days; oldest {s['oldest_age_days']} days.")
    print(f"  Assessed more than 12 months ago: {s['over_12_months']} of {s['vendors']}; "
          f"more than 24 months ago: {s['over_24_months']} of {s['vendors']} (overdue on the flat cycle).")
    print(f"  Vendors whose upstream model provider the bank cannot see: {s['undisclosed']} of {s['vendors']}.")
    print("  Nothing yet says who passes, who is risky, or how the bank would leave. That is steps 2 to 4.")

    with open(OUT_DIR / "step_01_estate.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["vendor_id", "criticality", "data_access", "critical_use_cases", "provider_disclosed",
                    "assessed_age_days"])
        for v in data["vendors"]:
            w.writerow([v["vendor_id"], v["criticality"], v["data_access"], v["critical_use_cases"],
                        "yes" if v["provider_disclosed"] else "no", assessed_age_days(v)])
    with open(OUT_DIR / "step_01_summary.json", "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_01_estate.csv and step_01_summary.json")


if __name__ == "__main__":
    main()
