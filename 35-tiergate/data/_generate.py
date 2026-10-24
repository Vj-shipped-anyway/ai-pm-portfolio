"""Generates the synthetic data for project 35 (standard library only, seeded).

Run:  python3 _generate.py      (from any folder; it writes next to this file)

Everything here is invented. No real bank, vendor, person or intake form appears.

Files written
  intake_submissions.csv  200 intake forms: the columns a sponsor fills in, then HIDDEN truth columns
                          (true_*, reference_*, planted) that the tool never reads
  data_catalog.csv        27 datasets: the class the catalog records, plus the true class and a status
  vendor_registry.csv     use case -> vendor model, partial coverage, accurate where it has an entry
  example_intake.csv, example_catalog.csv, example_registry.csv
                          six hand-written forms behind `python3 tiergate.py --demo`

The reference tier is the written rubric applied to the TRUE attributes. Accuracy against it measures
how well a method recovers the rubric result from noisy inputs. It does not measure how real banks tier
AI use cases. The same author wrote this generator and the rules in src/tiergate.py.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

SEED = 20261023
N = 200
OUT = Path(__file__).parent

CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
VENDOR_ORDER = ["none", "self_hosted", "vendor_api"]
PTS_CUSTOMER = {"yes": 2, "no": 0}
PTS_AUTONOMY = {"advisory": 0, "assisted": 1, "automated": 3}
PTS_CLASS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
PTS_VENDOR = {"none": 0, "self_hosted": 1, "vendor_api": 2}
PTS_REG = {"none": 0, "privacy": 1, "aml": 2, "udaap": 2, "fair_lending": 3}
PTS_EXPOSURE = {"lt_1m": 0, "1m_10m": 1, "10m_50m": 2, "gt_50m": 3}

# How the forms go wrong. These are parameters I chose, not observations.
P_CLASS_DOWN = {"public": 0.0, "internal": 0.08, "confidential": 0.25, "restricted": 0.35}
P_VENDOR_OMITTED = {"none": 0.0, "self_hosted": 0.15, "vendor_api": 0.30}
P_CF_ANSWER = {  # true value -> list of (answer, probability); the rest is the true answer
    "yes": [("no", 0.20), ("unsure", 0.08), ("", 0.05)],
    "no": [("yes", 0.03), ("unsure", 0.04), ("", 0.02)],
}
P_SHADE_DOWN = 0.16
P_SHADE_UP = 0.03
P_REGISTRY_COVERS = 0.60
P_TEXT_NAMES_CUSTOMERS = 0.70  # for a customer-facing case that has both phrasings

UNITS = ["Retail Banking", "Commercial Banking", "Wealth", "Payments", "Operations",
         "Financial Crime", "Credit Risk", "Technology"]

# name, steward unit, true class, catalog status
# status: current, stale_understated (catalog one class below the truth), stale_overstated (one above),
#         not_listed (the catalog has no entry)
DATASETS = [
    ("branch_hours_feed", "Retail Banking", "public", "current"),
    ("product_fee_schedule", "Product", "public", "current"),
    ("published_rate_sheets", "Product", "public", "current"),
    ("marketing_copy_library", "Marketing", "public", "current"),
    ("policy_manual_corpus", "Operations", "internal", "current"),
    ("it_service_tickets", "Technology", "internal", "current"),
    ("procedure_wiki", "Operations", "internal", "current"),
    ("staff_directory", "People", "internal", "stale_overstated"),
    ("training_material_index", "People", "internal", "current"),
    ("procurement_notes", "Procurement", "internal", "not_listed"),
    ("complaint_case_notes", "Customer Care", "confidential", "current"),
    ("call_transcripts", "Contact Centre", "confidential", "current"),
    ("card_dispute_log", "Disputes", "confidential", "stale_understated"),
    ("payments_exceptions_queue", "Payments", "confidential", "current"),
    ("loan_application_files", "Lending", "confidential", "current"),
    ("collections_contact_history", "Collections", "confidential", "stale_understated"),
    ("merchant_onboarding_files", "Merchant Services", "confidential", "current"),
    ("wealth_client_notes", "Wealth", "confidential", "current"),
    ("branch_cash_forecasts", "Retail Banking", "confidential", "stale_overstated"),
    ("audit_workpapers", "Internal Audit", "confidential", "current"),
    ("account_master_extract", "Core Banking", "restricted", "current"),
    ("transaction_history", "Core Banking", "restricted", "current"),
    ("credit_bureau_pulls", "Credit Risk", "restricted", "current"),
    ("sanctions_screening_hits", "Financial Crime", "restricted", "current"),
    ("suspicious_activity_drafts", "Financial Crime", "restricted", "stale_understated"),
    ("identity_document_images", "Onboarding", "restricted", "not_listed"),
    ("trading_book_positions", "Markets", "restricted", "current"),
]

# Each archetype: a title, the true customer-facing answer, one or two phrasings of the description
# (mention = the text names the people served), and the pools the generator draws from.
ARCHETYPES = [
    {"title": "Branch hours and fees assistant", "cf": "yes",
     "mention": "Chat assistant answers questions from customers about branch hours and fees.",
     "plain": "Chat assistant on the public website answers questions about branch hours and fees.",
     "datasets": ["branch_hours_feed", "product_fee_schedule"], "autonomy": ["advisory"],
     "reg": ["none", "udaap"], "exposure": ["lt_1m"]},
    {"title": "Rate sheet explainer", "cf": "yes",
     "mention": "Explains rate sheet terms to applicants during online enquiries.",
     "plain": "Explains rate sheet terms inside the online enquiry flow.",
     "datasets": ["published_rate_sheets", "product_fee_schedule"], "autonomy": ["advisory", "assisted"],
     "reg": ["udaap", "fair_lending"], "exposure": ["lt_1m", "1m_10m"]},
    {"title": "Card dispute drafting aide", "cf": "yes",
     "mention": "Drafts dispute outcome letters for cardholders from the case log.",
     "plain": "Drafts dispute outcome letters from the case log for the operations reviewer to send.",
     "datasets": ["card_dispute_log"], "autonomy": ["assisted", "automated"],
     "reg": ["udaap"], "exposure": ["1m_10m", "10m_50m"]},
    {"title": "Collections contact planner", "cf": "yes",
     "mention": "Chooses call and message timing for borrowers in early arrears.",
     "plain": "Chooses call and message timing for accounts in early arrears.",
     "datasets": ["collections_contact_history", "account_master_extract"], "autonomy": ["assisted", "automated"],
     "reg": ["udaap", "fair_lending"], "exposure": ["10m_50m", "gt_50m"]},
    {"title": "Onboarding identity check", "cf": "yes",
     "mention": "Checks identity documents uploaded by new customers and returns a pass or refer result.",
     "plain": "Checks identity documents uploaded in the onboarding flow and returns a pass or refer result.",
     "datasets": ["identity_document_images"], "autonomy": ["assisted", "automated"],
     "reg": ["aml", "privacy"], "exposure": ["10m_50m", "gt_50m"]},
    {"title": "Merchant onboarding guide", "cf": "yes", "mention": None,
     "plain": "Guides merchants through the onboarding questions and flags missing items.",
     "datasets": ["merchant_onboarding_files"], "autonomy": ["assisted"],
     "reg": ["aml"], "exposure": ["1m_10m"]},
    {"title": "Savings nudges", "cf": "yes",
     "mention": "Sends tailored savings nudges to depositors based on account activity.",
     "plain": "Sends tailored savings nudges in the mobile app based on account activity.",
     "datasets": ["transaction_history", "account_master_extract"], "autonomy": ["automated"],
     "reg": ["udaap", "privacy"], "exposure": ["1m_10m", "10m_50m"]},
    {"title": "Campaign copy drafts", "cf": "yes", "mention": None,
     "plain": "Drafts email and web copy for product campaigns for the marketing team to approve.",
     "datasets": ["marketing_copy_library", "product_fee_schedule"], "autonomy": ["assisted"],
     "reg": ["udaap"], "exposure": ["lt_1m"]},
    {"title": "Loan file completeness check", "cf": "no", "mention": None,
     "plain": "Checks loan application files for missing documents before underwriting.",
     "datasets": ["loan_application_files"], "autonomy": ["advisory", "assisted"],
     "reg": ["fair_lending", "privacy"], "exposure": ["1m_10m"]},
    {"title": "Credit memo drafting", "cf": "no", "mention": None,
     "plain": "Drafts credit memo sections from bureau pulls and financial spreads for the analyst.",
     "datasets": ["credit_bureau_pulls"], "autonomy": ["advisory", "assisted"],
     "reg": ["fair_lending"], "exposure": ["10m_50m"]},
    {"title": "Alert history summary", "cf": "no", "mention": None,
     "plain": "Summarises alert history for the financial crime investigator.",
     "datasets": ["transaction_history", "sanctions_screening_hits"], "autonomy": ["advisory"],
     "reg": ["aml"], "exposure": ["1m_10m", "10m_50m"]},
    {"title": "Regulatory filing narrative drafts", "cf": "no", "mention": None,
     "plain": "Drafts narrative sections of regulatory filings for investigator review.",
     "datasets": ["suspicious_activity_drafts", "transaction_history"], "autonomy": ["assisted"],
     "reg": ["aml"], "exposure": ["10m_50m"]},
    {"title": "Staff policy search", "cf": "no", "mention": None,
     "plain": "Answers staff questions from the policy manual and the procedure wiki.",
     "datasets": ["policy_manual_corpus", "procedure_wiki"], "autonomy": ["advisory"],
     "reg": ["none"], "exposure": ["lt_1m"]},
    {"title": "IT ticket router", "cf": "no", "mention": None,
     "plain": "Routes internal service tickets to the right resolver group.",
     "datasets": ["it_service_tickets"], "autonomy": ["automated"],
     "reg": ["none"], "exposure": ["lt_1m"]},
    {"title": "Adviser meeting notes summary", "cf": "no", "mention": None,
     "plain": "Summarises adviser meeting notes into follow-up tasks.",
     "datasets": ["wealth_client_notes"], "autonomy": ["advisory", "assisted"],
     "reg": ["privacy"], "exposure": ["lt_1m", "1m_10m"]},
    {"title": "Complaint theme summary", "cf": "no",
     "mention": "Groups complaint themes from customer letters for the quality team.", "plain": None,
     "datasets": ["complaint_case_notes"], "autonomy": ["advisory"],
     "reg": ["udaap", "privacy"], "exposure": ["lt_1m"]},
    {"title": "Call quality scoring", "cf": "no",
     "mention": "Scores recorded calls with customers against the coaching rubric for team leads.", "plain": None,
     "datasets": ["call_transcripts"], "autonomy": ["advisory", "assisted"],
     "reg": ["privacy", "udaap"], "exposure": ["lt_1m", "1m_10m"]},
    {"title": "Incoming document triage", "cf": "no",
     "mention": "Sorts incoming customer documents into the right work queue for operations staff.", "plain": None,
     "datasets": ["merchant_onboarding_files", "identity_document_images", "loan_application_files"],
     "autonomy": ["assisted", "automated"], "reg": ["aml", "privacy"], "exposure": ["1m_10m"]},
    {"title": "Payment exception resolver", "cf": "no", "mention": None,
     "plain": "Proposes fixes for failed payment instructions in the exceptions queue.",
     "datasets": ["payments_exceptions_queue"], "autonomy": ["assisted", "automated"],
     "reg": ["none", "aml"], "exposure": ["10m_50m", "gt_50m"]},
    {"title": "Branch cash forecast", "cf": "no", "mention": None,
     "plain": "Forecasts branch cash needs for the next two weeks.",
     "datasets": ["branch_cash_forecasts"], "autonomy": ["automated"],
     "reg": ["none"], "exposure": ["1m_10m"]},
    {"title": "Training quiz writer", "cf": "no", "mention": None,
     "plain": "Writes quiz questions from the training material and assigns them by team.",
     "datasets": ["training_material_index", "staff_directory"], "autonomy": ["advisory"],
     "reg": ["none"], "exposure": ["lt_1m"]},
    {"title": "Supplier clause finder", "cf": "no", "mention": None,
     "plain": "Finds clauses in supplier agreements and notes for procurement analysts.",
     "datasets": ["procurement_notes"], "autonomy": ["advisory"],
     "reg": ["none"], "exposure": ["lt_1m", "1m_10m"]},
    {"title": "Audit workpaper search", "cf": "no", "mention": None,
     "plain": "Searches prior audit workpapers for the engagement team.",
     "datasets": ["audit_workpapers"], "autonomy": ["advisory"],
     "reg": ["none", "privacy"], "exposure": ["lt_1m"]},
    {"title": "Desk note summary", "cf": "no", "mention": None,
     "plain": "Summarises overnight position changes for the trading desk head.",
     "datasets": ["trading_book_positions"], "autonomy": ["advisory"],
     "reg": ["none"], "exposure": ["gt_50m"]},
    {"title": "Ownership lookup", "cf": "no", "mention": None,
     "plain": "Answers who-owns-what questions from the staff directory.",
     "datasets": ["staff_directory"], "autonomy": ["advisory"],
     "reg": ["privacy"], "exposure": ["lt_1m"]},
]

INTAKE_HEADER = ["use_case_id", "sponsor_unit", "title", "description", "dataset_name", "customer_facing",
                 "decision_autonomy", "data_class", "vendor_model", "regulatory_scope",
                 "financial_exposure_band", "self_declared_tier",
                 "true_customer_facing", "true_data_class", "true_vendor_model",
                 "reference_score", "reference_tier", "planted"]


def rubric_score(cf, aut, cls, ven, reg, exp):
    return (PTS_CUSTOMER.get(cf, 0) + PTS_AUTONOMY[aut] + PTS_CLASS[cls] + PTS_VENDOR[ven]
            + PTS_REG[reg] + PTS_EXPOSURE[exp])


def tier_of(score):
    return min(4, 1 + score // 4)


def weighted_pick(rng, true_value, table):
    r = rng.random()
    acc = 0.0
    for answer, p in table:
        acc += p
        if r < acc:
            return answer
    return true_value


def write_csv(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def build():
    rng = random.Random(SEED)
    ds_true = {d[0]: d[2] for d in DATASETS}
    ds_status = {d[0]: d[3] for d in DATASETS}

    def catalog_class(name):
        true = ds_true[name]
        i = CLASS_ORDER.index(true)
        if ds_status[name] == "stale_understated":
            return CLASS_ORDER[i - 1]
        if ds_status[name] == "stale_overstated":
            return CLASS_ORDER[i + 1]
        return true

    catalog_rows = [[n, s, catalog_class(n), t, st] for n, s, t, st in DATASETS if st != "not_listed"]

    intake, registry, stats = [], [], {"class_down": 0, "vendor_omitted": 0, "cf_wrong": 0, "shade_down": 0, "shade_up": 0}
    tags_count = {}
    for i in range(1, N + 1):
        uid = "IN-%03d" % i
        unit = rng.choice(UNITS)
        arch = rng.choice(ARCHETYPES)
        ds = rng.choice(arch["datasets"])
        aut = rng.choice(arch["autonomy"])
        reg = rng.choice(arch["reg"])
        exp = rng.choice(arch["exposure"])
        t_cls = ds_true[ds]
        t_ven = rng.choices(VENDOR_ORDER, weights=[0.30, 0.25, 0.45])[0]
        t_cf = arch["cf"]
        if arch["mention"] and arch["plain"]:
            mentions = rng.random() < P_TEXT_NAMES_CUSTOMERS
        else:
            mentions = arch["mention"] is not None
        text = arch["mention"] if mentions else arch["plain"]

        f_cls = t_cls
        if rng.random() < P_CLASS_DOWN[t_cls]:
            f_cls = CLASS_ORDER[CLASS_ORDER.index(t_cls) - 1]
            stats["class_down"] += 1
        f_ven = t_ven
        if rng.random() < P_VENDOR_OMITTED[t_ven]:
            f_ven = "none"
            stats["vendor_omitted"] += 1
        f_cf = weighted_pick(rng, t_cf, P_CF_ANSWER[t_cf])
        if f_cf != t_cf:
            stats["cf_wrong"] += 1

        sponsor_tier = tier_of(rubric_score(f_cf, aut, f_cls, f_ven, reg, exp))
        r = rng.random()
        declared = sponsor_tier
        if sponsor_tier > 1 and r < P_SHADE_DOWN:
            declared = sponsor_tier - 1
            stats["shade_down"] += 1
        elif sponsor_tier < 4 and r > 1 - P_SHADE_UP:
            declared = sponsor_tier + 1
            stats["shade_up"] += 1

        in_registry = t_ven != "none" and rng.random() < P_REGISTRY_COVERS
        if in_registry:
            registry.append([uid, t_ven, "procurement_registry"])

        score = rubric_score(t_cf, aut, t_cls, t_ven, reg, exp)
        tags = []
        if f_cls != t_cls and ds_status[ds] == "stale_understated":
            tags.append("class_understated_in_form_and_catalog")
        if f_cls != t_cls and ds_status[ds] == "not_listed":
            tags.append("class_understated_dataset_not_listed")
        if VENDOR_ORDER.index(f_ven) < VENDOR_ORDER.index(t_ven) and not in_registry:
            tags.append("vendor_omitted_and_not_in_registry")
        if t_cf == "yes" and f_cf == "no" and not mentions:
            tags.append("customer_facing_denied_and_text_silent")
        if t_cf == "no" and mentions:
            tags.append("text_names_customers_but_internal")
        if ds_status[ds] == "stale_overstated":
            tags.append("catalog_overstates_class")
        for t in tags:
            tags_count[t] = tags_count.get(t, 0) + 1
        intake.append([uid, unit, arch["title"], text, ds, f_cf, aut, f_cls, f_ven, reg, exp, declared,
                       t_cf, t_cls, t_ven, score, tier_of(score), ";".join(sorted(tags)) or "none"])
    return catalog_rows, registry, intake, stats, tags_count


EXAMPLE_INTAKE = [
    ["IN-D01", "Retail Banking", "Branch hours assistant", "Chat assistant answers questions from customers about branch hours.",
     "branch_hours_feed", "yes", "advisory", "public", "none", "none", "lt_1m", "1"],
    ["IN-D02", "Payments", "Card dispute drafting aide", "Drafts dispute outcome letters for cardholders from the case log.",
     "card_dispute_log", "yes", "assisted", "internal", "none", "udaap", "1m_10m", "2"],
    ["IN-D03", "Technology", "IT ticket router", "Routes internal service tickets to the right resolver group.",
     "it_service_tickets", "no", "automated", "internal", "self_hosted", "none", "lt_1m", "2"],
    ["IN-D04", "Operations", "Policy search for staff", "Answers staff questions from the policy manual.",
     "policy_manual_corpus", "no", "advisory", "internal", "none", "none", "lt_1m", "1"],
    ["IN-D05", "Credit Risk", "Credit memo drafting", "Drafts credit memo sections from bureau pulls for the analyst.",
     "credit_bureau_pulls", "no", "advisory", "restricted", "vendor_api", "fair_lending", "10m_50m", "3"],
    ["IN-D06", "Commercial Banking", "Loan file completeness check", "Checks loan application files for missing documents before underwriting.",
     "loan_application_files", "no", "assisted", "confidential", "none", "fair_lending", "1m_10m", "2"],
]
EXAMPLE_CATALOG = [
    ["branch_hours_feed", "public"], ["card_dispute_log", "confidential"], ["it_service_tickets", "internal"],
    ["policy_manual_corpus", "internal"], ["credit_bureau_pulls", "restricted"], ["loan_application_files", "confidential"],
]
EXAMPLE_REGISTRY = [["IN-D03", "self_hosted"], ["IN-D05", "vendor_api"]]


def main():
    catalog_rows, registry, intake, stats, tags_count = build()
    write_csv("intake_submissions.csv", INTAKE_HEADER, intake)
    write_csv("data_catalog.csv", ["dataset_name", "steward_unit", "catalog_class", "true_class", "catalog_status"], catalog_rows)
    write_csv("vendor_registry.csv", ["use_case_id", "vendor_model", "source"], registry)
    write_csv("example_intake.csv", INTAKE_HEADER[:12], EXAMPLE_INTAKE)
    write_csv("example_catalog.csv", ["dataset_name", "catalog_class"], EXAMPLE_CATALOG)
    write_csv("example_registry.csv", ["use_case_id", "vendor_model"], EXAMPLE_REGISTRY)
    print("intake forms: %d, catalog entries: %d, registry entries: %d" % (len(intake), len(catalog_rows), len(registry)))
    for k in sorted(stats):
        print("  %s: %d" % (k, stats[k]))
    for k in sorted(tags_count):
        print("  planted %s: %d" % (k, tags_count[k]))


if __name__ == "__main__":
    main()
