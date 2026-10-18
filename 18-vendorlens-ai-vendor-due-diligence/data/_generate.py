"""Generates the VendorLens synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes five CSVs next to this file)

What it builds (all invented; no real vendor, model provider, bank or dataset)
  vendors.csv        40 AI vendors of a modeled bank: V-01 to V-40, service type, criticality,
                     customer-data access, use cases supported, upstream model provider
                     (MP-1 to MP-5, blank when the vendor does not disclose it), exit clause,
                     exit test, portability days, audit right, model-change notice days,
                     last assessed, contract end.
  questions.csv      the 20 questionnaire questions, with the kind of evidence that could
                     back each answer.
  questionnaire.csv  40 vendors x 20 self-declared answers (yes / partial / no).
  evidence.csv       the documents each vendor supplied: an independent control report, a
                     penetration test, model documentation, with an issue date and whether it
                     covers the AI service.
  truth.csv          what the generator decided: the true risk class (from a latent score),
                     how many answers were over-claimed, whether the upstream provider is
                     disclosed, and what the provider really is.

The truth is known because the data is synthetic. The generator decides, for every vendor, the
real quality of its controls, how much it over-claims, and which model provider it really runs
on. A real estate does not hand you that. Nothing here is a model: the answers, documents and
risk classes are written by this script.

Design choices the generator makes openly (see data/README.md):
  * Most vendors pass a questionnaire that needs 85 percent yes. That is the failure being
    modeled, so a group of vendors over-claims on purpose.
  * The provider assignment is redrawn until three conditions hold (see assign_providers).
    The number of draws is printed when the script runs.
  * The true risk class comes from a latent score with an unobserved component, so no
    scoring method can reproduce it exactly.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261018
AS_OF = date(2026, 10, 15)          # fixed "today" for every age and window in the repo
N_VENDORS = 40
OUT = Path(__file__).parent

PROVIDERS = ["MP-1", "MP-2", "MP-3", "MP-4", "MP-5"]
PROVIDER_WEIGHTS = [0.38, 0.22, 0.17, 0.13, 0.10]
N_UNDISCLOSED = 5
CONC_LINE = 0.40                    # share of critical use cases; same line VendorLens flags on

# Allowed transition window in days by criticality (assumption of a modeled bank).
ALLOWED_EXIT_DAYS = {"critical": 45, "important": 90, "standard": 150}

# (service type, typical data access, importance 1-3). Generic descriptions, not products.
SERVICES = [
    ("customer chat assistant", "customer_pii", 3),
    ("document summarization", "internal", 2),
    ("KYC document extraction", "customer_pii", 3),
    ("fraud scoring support", "customer_pii", 3),
    ("call transcription", "customer_pii", 2),
    ("code assistant", "internal", 1),
    ("credit decision support", "customer_pii", 3),
    ("AML alert triage", "customer_pii", 3),
    ("email and letter drafting", "internal", 1),
    ("translation", "none", 1),
    ("enterprise search", "internal", 1),
    ("market news summarization", "none", 1),
    ("contract analysis", "internal", 2),
    ("voice authentication", "customer_pii", 2),
    ("collections outreach", "customer_pii", 2),
    ("HR screening support", "internal", 2),
]

# (id, group, text, verified_by)
QUESTIONS = [
    ("Q01", "security", "Access to customer data is limited by role and reviewed", "independent_control_report"),
    ("Q02", "security", "Data is encrypted at rest and in transit", "independent_control_report"),
    ("Q03", "security", "Security events are logged and monitored", "independent_control_report"),
    ("Q04", "security", "An incident response plan exists and is exercised", "independent_control_report"),
    ("Q05", "security", "A business continuity plan covers the AI service", "independent_control_report"),
    ("Q06", "security", "Staff with data access are vetted and trained", "independent_control_report"),
    ("Q07", "application", "An independent penetration test runs at least yearly", "penetration_test"),
    ("Q08", "application", "Vulnerabilities are patched within a stated window", "penetration_test"),
    ("Q09", "application", "Secure development practices are followed", "penetration_test"),
    ("Q10", "application", "Defenses against prompt injection and data leakage are tested", "penetration_test"),
    ("Q11", "model", "Model purpose, limits and known failure modes are documented", "model_documentation"),
    ("Q12", "model", "Training and evaluation data sources are documented", "model_documentation"),
    ("Q13", "model", "Bias and accuracy testing is performed and recorded", "model_documentation"),
    ("Q14", "model", "Model outputs are monitored in production", "model_documentation"),
    ("Q15", "contract", "Customers are notified before a model version changes", "contract"),
    ("Q16", "contract", "Customers may audit our controls", "contract"),
    ("Q17", "other", "Subcontractors are covered by written agreements", "none"),
    ("Q18", "other", "Customer data is deleted when the contract ends", "none"),
    ("Q19", "other", "Regulatory change is tracked and applied", "none"),
    ("Q20", "other", "We carry insurance that covers this service", "none"),
]
DOC_TYPES = ["independent_control_report", "penetration_test", "model_documentation"]
RANK = {"no": 0, "partial": 1, "yes": 2}

# Truth: how the latent score is built. Weights differ from VendorLens's on purpose, and the
# score has an unobserved part (hidden), so VendorLens cannot reproduce it by construction.
TRUE_CRIT = {"critical": 0.55, "important": 0.30, "standard": 0.10}
TRUE_DATA = {"customer_pii": 0.45, "internal": 0.15, "none": 0.0}
HIGH_LATENT = 0.40
MEDIUM_LATENT = 0.24


def iso(d: date) -> str:
    return d.isoformat()


def true_exit_gap(clause: str, tested: str, port_days, crit: str) -> float:
    if clause == "no":
        return 1.0
    eff = port_days if tested == "yes" else port_days * 1.5
    gap = 0.15 if tested == "yes" else 0.45
    if eff > ALLOWED_EXIT_DAYS[crit]:
        gap += 0.25
    return gap


def shares(vendors: list, provs: list, undis: set) -> tuple:
    """(true share by provider, disclosed share by provider, undisclosed share) of all critical use cases."""
    total = sum(v["critical_use_cases"] for v in vendors)
    true_s = {p: 0 for p in PROVIDERS}
    disc_s = {p: 0 for p in PROVIDERS}
    unk = 0
    for i, v in enumerate(vendors):
        n = v["critical_use_cases"]
        true_s[provs[i]] += n
        if i in undis:
            unk += n
        else:
            disc_s[provs[i]] += n
    return ({p: n / total for p, n in true_s.items()}, {p: n / total for p, n in disc_s.items()}, unk / total)


def assign_providers(vendors: list, rng: random.Random) -> tuple:
    """Draw providers and the undisclosed set until three design conditions hold:
       1. exactly one provider is above the 40 percent line in the disclosed view, and
          its disclosed share is below 50 percent;
       2. that provider's true share is at least 6 points higher than its disclosed share
          (the undisclosed vendors hide part of it);
       3. no other provider is above the line in the true view.
    Returns (providers by index, undisclosed index set, number of draws)."""
    draws = 0
    while True:
        draws += 1
        provs = [rng.choices(PROVIDERS, PROVIDER_WEIGHTS)[0] for _ in vendors]
        undis = set(rng.sample(range(len(vendors)), N_UNDISCLOSED))
        true_s, disc_s, _unk = shares(vendors, provs, undis)
        over = [p for p in PROVIDERS if disc_s[p] > CONC_LINE]
        if len(over) != 1 or disc_s[over[0]] >= 0.50:
            continue
        if true_s[over[0]] - disc_s[over[0]] < 0.06:
            continue
        if any(true_s[p] > CONC_LINE for p in PROVIDERS if p != over[0]):
            continue
        return provs, undis, draws


def make_doc(rng: random.Random) -> tuple:
    fresh = rng.random() < 0.72
    age = rng.randint(30, 330) if fresh else rng.randint(366, 800)
    covers = "yes" if rng.random() < 0.80 else "no"
    return age, covers


def main() -> None:
    rng = random.Random(SEED)

    # ---- base attributes: service, criticality, data access, use cases --------------------
    services = (SERVICES * 3)[:N_VENDORS]
    rng.shuffle(services)
    order = sorted(range(N_VENDORS), key=lambda i: -(services[i][2] + rng.uniform(0, 1.4)))
    crit_of = {}
    for rank, i in enumerate(order):
        crit_of[i] = "critical" if rank < 10 else ("important" if rank < 24 else "standard")

    vendors = []
    for i in range(N_VENDORS):
        stype, data_default, _imp = services[i]
        data = data_default if rng.random() < 0.75 else rng.choice(["customer_pii", "internal", "none"])
        crit = crit_of[i]
        if crit == "critical":
            ucs = rng.randint(3, 8)
            cuc = rng.randint(2, min(6, ucs))
        elif crit == "important":
            ucs = rng.randint(2, 5)
            cuc = rng.randint(0, min(2, ucs))
        else:
            ucs = rng.randint(1, 3)
            cuc = 1 if rng.random() < 0.15 else 0
        vendors.append({"vendor_id": f"V-{i + 1:02d}", "service_type": stype, "criticality": crit,
                        "data_access": data, "use_cases_supported": ucs, "critical_use_cases": cuc})

    # ---- upstream providers (redrawn until the design conditions hold) --------------------
    provs, undis, draws = assign_providers(vendors, rng)

    # ---- latent quality, contract and exit facts ------------------------------------------
    for i, v in enumerate(vendors):
        weak = rng.random() < 0.28
        q = rng.betavariate(3.0, 3.5) if weak else rng.betavariate(6.0, 2.0)
        v["_q"] = q
        v["_hidden"] = rng.random()
        v["model_provider"] = "" if i in undis else provs[i]
        v["_true_provider"] = provs[i]
        clause = "yes" if rng.random() < 0.35 + 0.35 * q else "no"
        v["exit_clause"] = clause
        if clause == "yes":
            v["exit_tested"] = "yes" if rng.random() < 0.27 else "no"
            v["portability_days"] = rng.randint(10, 150)
        else:
            v["exit_tested"] = "no"
            v["portability_days"] = ""
        v["audit_right"] = "yes" if rng.random() < 0.30 + 0.40 * q else "no"
        v["model_change_notice_days"] = rng.choice([0, 0, 0, 15, 30, 30, 60, 90])
        v["last_assessed_on"] = iso(AS_OF - timedelta(days=rng.randint(45, 820)))
        v["contract_end"] = iso(AS_OF + timedelta(days=rng.randint(-30, 720)))

    # ---- questionnaire answers and over-claiming -------------------------------------------
    answers = {}
    overclaimed = {}
    for v in vendors:
        q = v["_q"]
        overclaimer = rng.random() < (0.55 if q < 0.55 else 0.30)
        o = rng.uniform(0.75, 0.97) if overclaimer else rng.uniform(0.0, 0.20)
        p_yes = 0.35 + 0.65 * q
        row = {}
        over = 0
        for qid, _g, _t, verified_by in QUESTIONS:
            if qid == "Q15":
                true = "yes" if v["model_change_notice_days"] > 0 else "no"
            elif qid == "Q16":
                true = "yes" if v["audit_right"] == "yes" else "no"
            else:
                u = rng.random()
                true = "yes" if u < p_yes else ("partial" if u < p_yes + (1 - p_yes) * 0.6 else "no")
            if true == "yes":
                said = "yes"
            elif true == "partial":
                said = "yes" if rng.random() < o else "partial"
            else:
                if rng.random() < o * 0.8:
                    said = "yes"
                elif rng.random() < o * 0.5:
                    said = "partial"
                else:
                    said = "no"
            row[qid] = said
            if RANK[said] > RANK[true]:
                over += 1
        answers[v["vendor_id"]] = row
        overclaimed[v["vendor_id"]] = over

    # ---- evidence documents -----------------------------------------------------------------
    evidence = []
    for v in vendors:
        for dt in DOC_TYPES:
            if rng.random() < 0.20 + 0.70 * v["_q"]:
                age, covers = make_doc(rng)
                evidence.append((v["vendor_id"], dt, iso(AS_OF - timedelta(days=age)), covers))
                if rng.random() < 0.20:
                    evidence.append((v["vendor_id"], dt, iso(AS_OF - timedelta(days=age + rng.randint(300, 420))), "yes"))

    # ---- truth: latent risk, class, provider ------------------------------------------------
    true_s, disc_s, unk = shares(vendors, provs, undis)
    truth = []
    for i, v in enumerate(vendors):
        port = v["portability_days"] if v["portability_days"] != "" else 0
        exit_gap = true_exit_gap(v["exit_clause"], v["exit_tested"], port, v["criticality"])
        contract_gap = (0.5 if v["audit_right"] == "no" else 0.0) + (0.5 if v["model_change_notice_days"] == 0 else 0.0)
        conc = 1.0 if true_s[provs[i]] > CONC_LINE else 0.0
        weakness = 0.45 * (1 - v["_q"]) + 0.20 * exit_gap + 0.08 * contract_gap + 0.12 * conc + 0.15 * v["_hidden"]
        exposure = TRUE_CRIT[v["criticality"]] + TRUE_DATA[v["data_access"]]
        latent = weakness * (0.35 + 0.65 * exposure) + rng.gauss(0, 0.02)
        cls = "high" if latent >= HIGH_LATENT else ("medium" if latent >= MEDIUM_LATENT else "low")
        truth.append((v["vendor_id"], cls, f"{latent:.3f}", overclaimed[v["vendor_id"]],
                      "no" if i in undis else "yes", provs[i]))

    # ---- write files ------------------------------------------------------------------------
    def write(name: str, header: list, rows: list) -> None:
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)

    vcols = ["vendor_id", "service_type", "criticality", "data_access", "use_cases_supported",
             "critical_use_cases", "model_provider", "exit_clause", "portability_days", "exit_tested",
             "audit_right", "model_change_notice_days", "last_assessed_on", "contract_end"]
    write("vendors.csv", vcols, [[v[c] for c in vcols] for v in vendors])
    write("questions.csv", ["question_id", "group", "text", "verified_by"], QUESTIONS)
    write("questionnaire.csv", ["vendor_id"] + [q[0] for q in QUESTIONS],
          [[v["vendor_id"]] + [answers[v["vendor_id"]][q[0]] for q in QUESTIONS] for v in vendors])
    write("evidence.csv", ["vendor_id", "doc_type", "issued_on", "covers_ai_service"], sorted(evidence))
    write("truth.csv", ["vendor_id", "true_risk", "latent_risk", "overclaimed_answers",
                        "provider_disclosed", "true_model_provider"], truth)

    nh = sum(1 for t in truth if t[1] == "high")
    nm = sum(1 for t in truth if t[1] == "medium")
    print(f"Wrote 5 CSVs in {OUT.name}/: {len(vendors)} vendors, {len(QUESTIONS)} questions, "
          f"{len(evidence)} evidence documents.")
    print(f"Seed {SEED}; provider assignment needed {draws} draw(s). "
          f"True classes: {nh} high, {nm} medium, {len(truth) - nh - nm} low.")


if __name__ == "__main__":
    main()
