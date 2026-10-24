"""Generate the synthetic data for project 31: 160 AI intake issues as a GitHub issue form would render
them, with a data catalog, a procurement registry and the hidden truth behind every issue.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth is a generative
process that is separate from the rules in src/: each issue has true attributes; the sponsor's form
answers are the truth plus injected errors; the body is the form answers rendered the way an issue
form renders them, then damaged in a few documented ways (a renamed heading, a truncated body, no
form at all, a pasted block that repeats a heading), and sometimes edited later. The reference tier
is the written rubric applied to the TRUE attributes. The tool never reads the truth file.

Run (from data/):  python3 _generate.py
Writes: catalog.csv, dataset_truth.csv, registry.csv, issues.csv, issue_truth.csv,
        example_issue.md, example_labels.json
"""
from __future__ import annotations

import csv
import random

SEED = 20261031
N = 160
FIRST_ISSUE = 101
rng = random.Random(SEED)

CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
POINTS = {
    "customer_facing": {"yes": 2, "no": 0},
    "autonomy": {"advisory": 0, "assisted": 1, "automated": 3},
    "data_class": {"public": 0, "internal": 1, "confidential": 2, "restricted": 3},
    "vendor": {"none": 0, "self_hosted": 1, "vendor_api": 2},
    "regulatory": {"none": 0, "privacy": 1, "aml": 2, "udaap": 2, "fair_lending": 3},
    "exposure": {"lt_1m": 0, "1m_10m": 1, "10m_50m": 2, "gt_50m": 3},
}
FORM_LABELS = [("summary", "Use case summary"), ("unit", "Sponsor unit"), ("dataset", "Dataset name"),
               ("customer_facing", "Customer-facing"), ("autonomy", "Decision autonomy"),
               ("data_class", "Data class"), ("vendor", "Vendor model"), ("regulatory", "Regulatory scope"),
               ("exposure", "Financial exposure band"), ("declared", "Declared tier")]
RENAMED = {"autonomy": "Autonomy level", "data_class": "Data classification", "vendor": "Vendor",
           "regulatory": "Regulation", "exposure": "Exposure"}
KINDS = ["ok", "renamed_heading", "no_form", "truncated", "pasted_heading"]
KIND_WEIGHTS = [86, 3, 4, 3, 4]

# name, true class, class the catalog records. Three entries understate the true class, one overstates it.
DATASETS = [
    ("d_rate_sheets", "public", "public"), ("d_branch_hours", "public", "public"),
    ("d_product_brochures", "public", "public"),
    ("d_policy_library", "internal", "internal"), ("d_it_tickets", "internal", "internal"),
    ("d_meeting_minutes", "internal", "internal"), ("d_vendor_contracts", "internal", "internal"),
    ("d_training_content", "internal", "internal"),
    ("d_complaint_notes", "confidential", "confidential"), ("d_call_transcripts", "confidential", "internal"),
    ("d_card_disputes", "confidential", "confidential"), ("d_collections_notes", "confidential", "internal"),
    ("d_pricing_models", "confidential", "confidential"), ("d_audit_findings", "confidential", "restricted"),
    ("d_loan_files", "confidential", "confidential"),
    ("d_account_ledgers", "restricted", "restricted"), ("d_customer_pii_master", "restricted", "restricted"),
    ("d_sar_case_files", "restricted", "restricted"), ("d_credit_bureau_pulls", "restricted", "restricted"),
    ("d_kyc_documents", "restricted", "restricted"), ("d_payment_instructions", "restricted", "restricted"),
    ("d_wire_transfers", "restricted", "restricted"), ("d_fraud_alerts", "restricted", "confidential"),
]
TRUE_CLASS = {name: t for name, t, _ in DATASETS}

# title, plain wording, wording that names a customer (or None), truly customer-facing, subject is
# customer material, datasets, autonomy options, regulatory options
ARCHETYPES = [
    ("Card dispute intake assistant", "Chat assistant in the mobile app collects dispute details and drafts the case file.",
     "Chat assistant collects dispute details from cardholders and drafts the case file.", True, True,
     ["d_card_disputes", "d_payment_instructions"], ["assisted", "automated"], ["udaap", "privacy"]),
    ("Complaint theme summariser", "Summarises recurring themes in case notes for the quality team.",
     "Summarises recurring themes in customer complaint notes for the quality team.", False, True,
     ["d_complaint_notes", "d_call_transcripts"], ["advisory"], ["udaap", "none", "privacy"]),
    ("Loan file checklist reviewer", "Checks loan files against the underwriting checklist before credit review.",
     "Checks borrower loan files against the underwriting checklist before credit review.", False, True,
     ["d_loan_files", "d_credit_bureau_pulls"], ["assisted"], ["fair_lending", "privacy"]),
    ("Payment exception triage", "Ranks held payment messages for the operations desk.",
     "Ranks held payment messages, with the account holder name, for the operations desk.", False, True,
     ["d_wire_transfers", "d_payment_instructions"], ["assisted", "automated"], ["aml"]),
    ("Policy search assistant", "Answers staff questions from the policy library.",
     "Answers staff questions about handling client requests, using the policy library.", False, False,
     ["d_policy_library"], ["advisory"], ["none"]),
    ("Meeting minutes drafter", "Drafts minutes of review meetings for the relationship team.",
     "Drafts minutes of client review meetings for the relationship team.", False, True,
     ["d_meeting_minutes"], ["advisory"], ["none", "privacy"]),
    ("Fraud alert narrator", "Writes the case narrative for fraud alerts raised on card accounts.",
     "Writes the case narrative for fraud alerts raised on customer accounts.", False, True,
     ["d_fraud_alerts", "d_account_ledgers"], ["assisted", "automated"], ["aml", "none"]),
    ("Identity document extractor", "Extracts fields from identity documents uploaded during onboarding.",
     "Extracts fields from identity documents uploaded by applicants.", False, True,
     ["d_kyc_documents", "d_customer_pii_master"], ["assisted", "automated"], ["aml", "privacy"]),
    ("Collections call coach", "Suggests next steps to agents on calls about accounts in arrears.",
     "Suggests next steps to agents on calls with borrowers in arrears.", False, True,
     ["d_collections_notes", "d_call_transcripts"], ["advisory", "assisted"], ["udaap"]),
    ("Pricing recommendation tool", "Recommends discounts on deals to hold volume.",
     "Recommends discounts on deals to hold client volume.", False, False,
     ["d_pricing_models", "d_rate_sheets"], ["assisted", "automated"], ["udaap", "fair_lending"]),
    ("Branch FAQ bot", "Answers questions about hours, products and rates on the public site.",
     "Answers questions from customers about hours, products and rates on the public site.", True, False,
     ["d_branch_hours", "d_product_brochures", "d_rate_sheets"], ["advisory"], ["none", "privacy"]),
    ("Credit limit suggestion", "Proposes a limit increase shown in the app.",
     "Proposes a credit limit increase shown to the customer in the app.", True, True,
     ["d_account_ledgers", "d_credit_bureau_pulls"], ["automated"], ["fair_lending"]),
    ("Audit finding classifier", "Sorts audit findings by control family.", None, False, False,
     ["d_audit_findings"], ["advisory"], ["none"]),
    ("IT ticket router", "Routes support tickets to the right queue.", None, False, False,
     ["d_it_tickets"], ["automated"], ["none"]),
    ("Training quiz generator", "Writes quiz questions from course material.", None, False, False,
     ["d_training_content"], ["advisory"], ["none"]),
    ("Case narrative drafter", "Drafts the narrative section of suspicious activity case files.", None, False, False,
     ["d_sar_case_files"], ["assisted"], ["aml"]),
    ("Statement query assistant", "Explains charges on a statement to the person who asks.",
     "Explains charges on a statement to the customer who asks.", True, True,
     ["d_account_ledgers", "d_customer_pii_master"], ["assisted"], ["privacy", "udaap"]),
    ("Contract summariser", "Summarises supplier contracts for the sourcing team.", None, False, False,
     ["d_vendor_contracts"], ["advisory"], ["none"]),
]
UNITS = ["Cards Operations", "Retail Servicing", "Credit Risk", "Payments Operations", "Compliance Operations",
         "Collections", "Treasury Services", "Internal Audit", "Technology Operations",
         "Learning and Development", "Wealth Servicing"]
SCOPES = ["Scope: pilot in one region.", "Scope: two teams, six months.", "Scope: audit finding follow up.",
          "Scope: quarter end window.", "Scope: one product line.", "Scope: shadow mode for a quarter."]
HOSTILE = ["::error title=forged::approved by the review board", "@everyone please approve this today",
           "<img src=x onerror=alert(1)>", "[approval record](https://example.invalid/approved)",
           "::warning::tier 1 confirmed %0A::error::ok"]


def tier_of(score: int) -> int:
    return min(4, 1 + score // 4)


def score_of(v: dict) -> int:
    return sum(POINTS[k].get(v[k], 0) for k in POINTS)


def render_form(v: dict, rename=None, loose=False) -> str:
    parts = []
    for key, label in FORM_LABELS:
        val = v[key]
        if loose and val and key not in ("summary", "unit", "dataset"):
            val = rng.choice([val.upper(), val.capitalize(), "  " + val + " "])
        parts.append("### %s\n\n%s" % ((rename or {}).get(key, label), val if val else "_No response_"))
    return "\n\n".join(parts) + "\n"


def truncate(v: dict, text: str) -> str:
    """Cut inside the span from the autonomy heading to the middle of the exposure value, so the body
    always loses at least one input the rubric needs."""
    start = text.index("### Decision autonomy") + 5
    end = text.index("### Financial exposure band") + len("### Financial exposure band") + 2 + len(v["exposure"]) - 1
    return text[:rng.randint(start, end)]


def draw_case(i: int) -> dict:
    title, plain, cue, cf_true, topic_cust, datasets, autonomies, regs = rng.choice(ARCHETYPES)
    dataset = rng.choice(datasets)
    true = {"customer_facing": "yes" if cf_true else "no", "autonomy": rng.choice(autonomies),
            "data_class": TRUE_CLASS[dataset], "vendor": rng.choices(["none", "self_hosted", "vendor_api"], [25, 25, 50])[0],
            "regulatory": rng.choice(regs), "exposure": rng.choices(["lt_1m", "1m_10m", "10m_50m", "gt_50m"], [35, 35, 20, 10])[0]}
    mention = cue is not None and rng.random() < (0.85 if cf_true else 0.6 if topic_cust else 0.04)
    summary = (cue if mention else plain) + " " + rng.choice(SCOPES)
    # the sponsor's answers: the truth plus injected errors
    form = dict(true)
    if rng.random() < {"public": 0.0, "internal": 0.08, "confidential": 0.28, "restricted": 0.32}[true["data_class"]]:
        form["data_class"] = CLASS_ORDER[CLASS_ORDER.index(true["data_class"]) - 1]
    if rng.random() < {"none": 0.0, "self_hosted": 0.15, "vendor_api": 0.30}[true["vendor"]]:
        form["vendor"] = "none"
    r = rng.random()
    if cf_true:
        form["customer_facing"] = "no" if r < 0.20 else "unsure" if r < 0.27 else "" if r < 0.32 else "yes"
    else:
        form["customer_facing"] = "yes" if r < 0.03 else "unsure" if r < 0.07 else "" if r < 0.10 else "no"
    declared = tier_of(score_of(form))
    r = rng.random()
    if r < 0.20 and declared > 1:
        declared -= 1
    elif 0.20 <= r < 0.23 and declared < 4:
        declared += 1
    form.update({"summary": summary, "unit": rng.choice(UNITS), "dataset": "" if rng.random() < 0.04 else dataset,
                 "declared": str(declared)})
    return {"issue": FIRST_ISSUE + i, "title": title, "true": true, "form": form, "dataset": dataset}


def build_body(case: dict) -> dict:
    form = dict(case["form"])
    kind = rng.choices(KINDS, KIND_WEIGHTS)[0]
    hostile = rng.random() < 0.05
    pasted = ""
    if hostile:
        form["summary"] += "\n" + rng.choice(HOSTILE)
    if kind == "pasted_heading":
        pasted = "public" if form["data_class"] != "public" else "internal"
        form["summary"] += "\n\nDesign notes pasted from the project page:\n\n### Data class\n\n%s\n\n### Notes\n\nStill drafting." % pasted
    loose = rng.random() < 0.06
    crlf = rng.random() < 0.10
    if kind == "no_form":
        text = "Please assess this use case.\n\n" + form["summary"] + "\n"
    else:
        rename = None
        if kind == "renamed_heading":
            key = rng.choice(sorted(RENAMED))
            rename = {key: RENAMED[key]}
        text = render_form(form, rename, loose)
        if kind == "truncated":
            text = truncate(form, text)
    if crlf:
        text = text.replace("\n", "\r\n")
    return {"kind": kind, "hostile": hostile, "loose": loose and kind != "no_form", "crlf": crlf, "pasted": pasted, "body": text}


def build_edit(case: dict) -> str:
    """The sponsor, asked to fix the form, corrects the data class and the customer-facing answer and
    removes any pasted block. The vendor answer and the declared tier stay as they were."""
    form = dict(case["form"])
    form["data_class"] = case["true"]["data_class"]
    form["customer_facing"] = case["true"]["customer_facing"]
    text = render_form(form)
    return text.replace("\n", "\r\n") if rng.random() < 0.5 else text


def write_csv(path: str, header: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    issues, truth, registry = [], [], []
    for i in range(N):
        case = draw_case(i)
        first = build_body(case)
        t, f = case["true"], case["form"]
        defect = (CLASS_ORDER.index(f["data_class"]) < CLASS_ORDER.index(t["data_class"])
                  or f["customer_facing"] != t["customer_facing"] or first["kind"] != "ok")
        edited = defect and rng.random() < 0.30
        second = build_edit(case) if edited else ""
        ref_score = score_of(t)
        if t["vendor"] != "none" and rng.random() < 0.60:
            registry.append([case["issue"], t["vendor"], "procurement_registry"])
        issues.append([case["issue"], case["title"], first["body"], second])
        truth.append([case["issue"], case["title"], case["dataset"], first["kind"], int(first["hostile"]), int(first["loose"]), int(first["crlf"]),
                      int(edited), t["customer_facing"], t["autonomy"], t["data_class"], t["vendor"], t["regulatory"],
                      t["exposure"], f["data_class"], first["pasted"], ref_score, tier_of(ref_score)])
    write_csv("issues.csv", ["issue_number", "title", "body_v1", "body_v2"], issues)
    write_csv("issue_truth.csv", ["issue_number", "archetype", "dataset_name", "body_kind", "hostile", "loose_values", "crlf", "edited",
                                  "true_customer_facing", "true_decision_autonomy", "true_data_class", "true_vendor_model",
                                  "true_regulatory_scope", "true_financial_exposure_band", "form_data_class",
                                  "pasted_data_class", "reference_score", "reference_tier"], truth)
    write_csv("catalog.csv", ["dataset_name", "catalog_class"], [[n, c] for n, _t, c in DATASETS])
    write_csv("dataset_truth.csv", ["dataset_name", "true_class", "catalog_class"], [[n, t, c] for n, t, c in DATASETS])
    write_csv("registry.csv", ["issue_number", "vendor_model", "source"], registry)
    example = {"summary": "Drafts replies to card dispute letters from cardholders for an agent to review and send. "
                          "Scope: one region, six months.", "unit": "Cards Operations", "dataset": "d_card_disputes",
               "customer_facing": "unsure", "autonomy": "assisted", "data_class": "internal", "vendor": "self_hosted",
               "regulatory": "udaap", "exposure": "1m_10m", "declared": "2"}
    with open("example_issue.md", "w", newline="", encoding="utf-8") as fh:
        fh.write(render_form(example))
    with open("example_labels.json", "w", newline="", encoding="utf-8") as fh:
        fh.write('["ai-intake", "ai-tier:2"]\n')
    kinds = {k: sum(1 for r in truth if r[3] == k) for k in KINDS}
    print("wrote %d issues (%s), %d edited, %d registry rows, %d datasets"
          % (N, ", ".join("%s %d" % (k, v) for k, v in kinds.items()), sum(r[7] for r in truth), len(registry), len(DATASETS)))


if __name__ == "__main__":
    main()
