"""Generates the TierGate synthetic data (standard library only, seeded).

Run:  python3 _generate.py      (from any folder; writes next to this file)

Everything here is synthetic. No real bank, vendor, person or submission.

Output files
  intake_submissions.csv   150 AI use-case intake submissions: the form the
                           sponsor filled in, plus HIDDEN true attributes and
                           the committed reference tier (rubric on the truth)
  data_catalog.csv         dataset name -> class as recorded in the catalog,
                           plus the true class (hidden) and a staleness flag
  vendor_registry.csv      use case -> vendor model, partial coverage
  evidence_checklist.csv   evidence required per tier (cumulative, long form)
  evidence_on_file.csv     which evidence items each submission has on file

The reference tier is TRUE BY CONSTRUCTION: it is the written rubric applied
to the true attributes. Accuracy against it measures how well a method
recovers it from noisy inputs, not how real banks behave.
"""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

SEED = 20261011
OUT = Path(__file__).parent
rng = random.Random(SEED)

# ---------------------------------------------------------------------------
# The written rubric (arithmetic). Points on the TRUE attributes, summed.
# ---------------------------------------------------------------------------
CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
VENDOR_ORDER = ["none", "self_hosted", "vendor_api"]
AUTONOMY = ["advisory", "assisted", "automated"]
REG_SCOPES = ["none", "privacy", "aml", "udaap", "fair_lending"]
EXPOSURE = ["lt_1m", "1m_10m", "10m_50m", "gt_50m"]

PTS_CUSTOMER = {"yes": 2, "no": 0}
PTS_AUTONOMY = {"advisory": 0, "assisted": 1, "automated": 3}
PTS_CLASS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
PTS_VENDOR = {"none": 0, "self_hosted": 1, "vendor_api": 2}
PTS_REG = {"none": 0, "privacy": 1, "aml": 2, "udaap": 2, "fair_lending": 3}
PTS_EXPOSURE = {"lt_1m": 0, "1m_10m": 1, "10m_50m": 2, "gt_50m": 3}

# score 0-3 -> tier 1, 4-7 -> tier 2, 8-11 -> tier 3, 12-16 -> tier 4  (tier = min(4, 1 + score // 4))
TIER_CUTS = [(3, 1), (7, 2), (11, 3), (99, 4)]


def rubric_score(cf: str, aut: str, cls: str, ven: str, reg: str, exp: str) -> int:
    return (PTS_CUSTOMER.get(cf, 0) + PTS_AUTONOMY[aut] + PTS_CLASS[cls]
            + PTS_VENDOR[ven] + PTS_REG[reg] + PTS_EXPOSURE[exp])


def tier_from_score(score: int) -> int:
    for cut, tier in TIER_CUTS:
        if score <= cut:
            return tier
    return 4


# ---------------------------------------------------------------------------
# Documented injected error rates (the form deviates from the truth)
# ---------------------------------------------------------------------------
P_DATA_UNDERSTATE = {"internal": 0.10, "confidential": 0.30, "restricted": 0.30}  # one level down
P_VENDOR_OMIT = {"vendor_api": 0.35, "self_hosted": 0.20}                          # form says none
P_CF_NO_WHEN_YES = 0.22        # customer-facing case called internal
P_CF_UNSURE_WHEN_YES = 0.08
P_CF_BLANK_WHEN_YES = 0.04
P_CF_UNSURE_WHEN_NO = 0.05
P_CF_BLANK_WHEN_NO = 0.03
P_CF_YES_WHEN_NO = 0.03
P_SHADE_DOWN = 0.18            # sponsor declares one tier lower than the rubric on their own answers
P_SHADE_UP = 0.03
P_REGISTRY_COVERAGE = 0.65     # share of truly vendor-dependent cases that appear in the vendor registry
N_STALE_UNDER = 3              # catalog entries that understate the true class
N_STALE_OVER = 1               # catalog entries that overstate the true class
P_CUE_WHEN_CF = 0.85           # description of a customer-facing case mentions customers
P_CUE_WHEN_INTERNAL_TALKS = 0.60   # internal case whose subject is customer material
P_CUE_WHEN_INTERNAL_OTHER = 0.04
P_EVIDENCE_DECLARED = 0.95     # sponsor attaches each item on the checklist of the tier they declared
P_EVIDENCE_EXTRA = 0.25        # sponsor happens to attach an item from a higher tier

# ---------------------------------------------------------------------------
# Data catalog: dataset -> steward unit, true class
# ---------------------------------------------------------------------------
DATASETS = [
    ("d_public_rate_sheets", "Product", "public"),
    ("d_product_brochures", "Marketing", "public"),
    ("d_published_filings", "Finance", "public"),
    ("d_market_data_feed", "Treasury", "public"),
    ("d_policy_library", "Compliance", "internal"),
    ("d_procedure_manuals", "Operations", "internal"),
    ("d_branch_ops_logs", "Branch Network", "internal"),
    ("d_marketing_copy_library", "Marketing", "internal"),
    ("d_it_service_tickets", "Technology", "internal"),
    ("d_meeting_notes_corp", "Corporate Office", "internal"),
    ("d_training_materials", "Human Resources", "internal"),
    ("d_code_repository", "Technology", "internal"),
    ("d_complaint_narratives", "Compliance", "confidential"),
    ("d_employee_hr_cases", "Human Resources", "confidential"),
    ("d_vendor_contracts", "Procurement", "confidential"),
    ("d_legal_matter_files", "Legal", "confidential"),
    ("d_internal_audit_findings", "Internal Audit", "confidential"),
    ("d_model_inventory_records", "Risk Management", "confidential"),
    ("d_pricing_models", "Finance", "confidential"),
    ("d_call_center_transcripts", "Contact Centre", "confidential"),
    ("d_chat_logs_customer", "Contact Centre", "confidential"),
    ("d_marketing_response_data", "Marketing", "confidential"),
    ("d_loan_applications", "Lending", "restricted"),
    ("d_transaction_history", "Operations", "restricted"),
    ("d_kyc_documents", "Compliance", "restricted"),
    ("d_sar_case_files", "Compliance", "restricted"),
    ("d_credit_bureau_pulls", "Lending", "restricted"),
    ("d_account_master", "Operations", "restricted"),
    ("d_card_authorisations", "Cards", "restricted"),
    ("d_collections_notes", "Collections", "restricted"),
    ("d_wealth_client_profiles", "Wealth", "restricted"),
    ("d_fraud_case_files", "Fraud", "restricted"),
    ("d_mortgage_underwriting_files", "Lending", "restricted"),
    ("d_deposit_account_events", "Operations", "restricted"),
]
DS_CLASS = {name: cls for name, _, cls in DATASETS}

# ---------------------------------------------------------------------------
# Use-case archetypes. {s} = subject (product line or function),
# {cu} = customer cue word or a neutral word. Three phrasings each.
# ---------------------------------------------------------------------------
POOLS = {
    "lend": ["credit card", "mortgage", "auto lending", "small business lending",
             "personal loans", "student lending", "home equity"],
    "dep": ["checking and savings", "payments and wires", "treasury services",
            "credit card", "business banking", "money market accounts"],
    "wealth": ["wealth management", "private banking", "retirement accounts",
               "brokerage accounts", "trust services", "managed portfolios"],
    "mort": ["mortgage", "home equity", "jumbo mortgage", "refinance", "construction lending"],
    "card": ["credit card", "debit card", "checking and savings", "payments and wires",
             "business banking"],
    "all": ["credit card", "mortgage", "auto lending", "small business lending",
            "personal loans", "checking and savings", "wealth management",
            "commercial banking", "payments and wires", "student lending",
            "treasury services", "business banking"],
}
SUBJECT_UNIT = {
    "credit card": "Cards", "debit card": "Cards", "mortgage": "Mortgage",
    "home equity": "Mortgage", "jumbo mortgage": "Mortgage", "refinance": "Mortgage",
    "construction lending": "Commercial Banking", "auto lending": "Retail Banking",
    "small business lending": "Commercial Banking", "personal loans": "Retail Banking",
    "student lending": "Retail Banking", "checking and savings": "Retail Banking",
    "wealth management": "Wealth", "private banking": "Wealth",
    "retirement accounts": "Wealth", "brokerage accounts": "Wealth",
    "trust services": "Wealth", "managed portfolios": "Wealth",
    "commercial banking": "Commercial Banking", "business banking": "Commercial Banking",
    "payments and wires": "Operations", "treasury services": "Treasury",
    "money market accounts": "Retail Banking",
}
FUNCTIONS = ["retail operations", "compliance", "finance", "human resources",
             "legal", "technology", "internal audit", "procurement", "marketing",
             "risk management", "contact centre", "branch network"]

CUE_WORDS = ["customers", "clients", "borrowers", "cardholders", "applicants",
             "account holders", "consumers"]
NEUTRAL_WORDS = ["users", "people", "staff", "teams", "the front line"]


def A(key, title, pool, cf, aut, ds, ven, reg, lvl, talks, variants, n=4):
    return dict(key=key, title=title, pool=pool, cf=cf, aut=aut, ds=ds, ven=ven,
                reg=reg, lvl=lvl, talks=talks, variants=variants, n=n)


# aut weights: advisory, assisted, automated
# ven weights: none, self_hosted, vendor_api
# reg weights: none, privacy, aml, udaap, fair_lending
ARCHETYPES = [
    A("cust_chat", "Customer service chat aide", "all", 0.97, (0.60, 0.30, 0.10),
      ["d_product_brochures", "d_policy_library", "d_chat_logs_customer", "d_account_master"],
      (0.10, 0.20, 0.70), (0.25, 0.30, 0.0, 0.40, 0.05), 1, True,
      ["Chat aide answers questions from {cu} about {s} fees, rates and eligibility using the policy library.",
       "Virtual agent in the mobile app helps {cu} with {s} balances, disputes and product questions.",
       "Conversational aide handles first-line {s} enquiries from {cu} and hands off to a banker when unsure."]),
    A("loan_prescreen", "Loan application pre-screening", "lend", 0.50, (0.10, 0.50, 0.40),
      ["d_loan_applications", "d_credit_bureau_pulls"],
      (0.45, 0.30, 0.25), (0.0, 0.10, 0.0, 0.20, 0.70), 2, True,
      ["Model scores incoming {s} applications from {cu} and sorts them into approve, refer and decline lanes.",
       "Pre-qualification engine estimates eligibility for {cu} before a formal {s} application is lodged.",
       "Triage service ranks {s} files by completeness and likely outcome for {cu} and underwriters."]),
    A("credit_scorecard", "Credit decision scorecard refresh", "lend", 0.85, (0.05, 0.45, 0.50),
      ["d_loan_applications", "d_credit_bureau_pulls", "d_account_master"],
      (0.55, 0.35, 0.10), (0.0, 0.05, 0.0, 0.05, 0.90), 3, True,
      ["Retrained scorecard sets the credit decision and price band for {s} requests from {cu}.",
       "Gradient boosted model replaces the legacy {s} scorecard that approves or declines {cu}.",
       "Decision model assigns limits and risk grades on {s} accounts held by {cu}."]),
    A("fraud_scoring", "Transaction fraud scoring", "dep", 0.30, (0.05, 0.40, 0.55),
      ["d_transaction_history", "d_card_authorisations", "d_fraud_case_files"],
      (0.30, 0.50, 0.20), (0.30, 0.20, 0.20, 0.30, 0.0), 2, True,
      ["Real-time model scores {s} transactions and holds suspicious payments from {cu}.",
       "Anomaly detector watches {s} activity and raises alerts for fraud analysts.",
       "Scoring service combines device and velocity signals on {s} transactions to stop fraud."]),
    A("aml_triage", "AML alert triage and narrative drafting", "dep", 0.0, (0.15, 0.70, 0.15),
      ["d_sar_case_files", "d_transaction_history", "d_kyc_documents"],
      (0.35, 0.35, 0.30), (0.0, 0.0, 1.0, 0.0, 0.0), 2, False,
      ["Aide drafts investigation narratives for {s} monitoring alerts and proposes a disposition.",
       "Alert prioritiser ranks {s} monitoring hits so investigators open the riskiest first.",
       "Summariser condenses transaction patterns on {s} alerts into a case note for analysts."]),
    A("kyc_extract", "KYC document extraction", "all", 0.20, (0.10, 0.70, 0.20),
      ["d_kyc_documents"],
      (0.30, 0.40, 0.30), (0.0, 0.40, 0.60, 0.0, 0.0), 1, True,
      ["Extraction pipeline reads identity and ownership documents supplied by {cu} during {s} onboarding.",
       "Document reader pulls names, addresses and beneficial owners from {s} onboarding packs.",
       "Classifier checks that {s} onboarding documents from {cu} are complete and legible."]),
    A("complaint_route", "Complaint classification and routing", "func", 0.0, (0.20, 0.60, 0.20),
      ["d_complaint_narratives"],
      (0.30, 0.40, 0.30), (0.10, 0.20, 0.0, 0.70, 0.0), 1, True,
      ["Classifier tags written complaints from {cu} by product and theme and routes them to {s} owners.",
       "Router reads complaint narratives, flags regulatory themes and assigns {s} handlers.",
       "Text model groups complaints raised by {cu} so {s} can spot repeat issues early."]),
    A("collections_outreach", "Collections outreach optimiser", "lend", 1.0, (0.10, 0.60, 0.30),
      ["d_collections_notes", "d_account_master"],
      (0.40, 0.40, 0.20), (0.0, 0.10, 0.0, 0.80, 0.10), 2, True,
      ["Model picks the contact time and script for overdue {cu} on {s} accounts.",
       "Next-best-action engine recommends payment plans and call order across {s} delinquency.",
       "Optimiser sequences reminders and calls to {cu} who are behind on {s} payments."]),
    A("marketing_copy", "Marketing copy generator", "all", 0.90, (0.85, 0.15, 0.0),
      ["d_marketing_copy_library", "d_product_brochures"],
      (0.10, 0.10, 0.80), (0.50, 0.0, 0.0, 0.50, 0.0), 0, False,
      ["Generator drafts emails and landing page copy for {s} campaigns aimed at {cu}.",
       "Writing tool produces ad variants and subject lines for {s} offers with human sign-off.",
       "Copy aide rewrites {s} product messaging in the approved brand voice."]),
    A("next_best_offer", "Next-best-offer propensity model", "all", 1.0, (0.10, 0.50, 0.40),
      ["d_marketing_response_data", "d_account_master"],
      (0.40, 0.40, 0.20), (0.0, 0.30, 0.0, 0.30, 0.40), 2, True,
      ["Propensity model selects which {s} offer each of the {cu} sees in the app and by email.",
       "Recommender ranks cross-sell offers on {s} for {cu} using transaction behaviour.",
       "Targeting model scores likelihood to respond to {s} promotions among {cu}."]),
    A("staff_policy_qa", "Employee policy question aide", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_policy_library", "d_procedure_manuals"],
      (0.15, 0.25, 0.60), (1.0, 0.0, 0.0, 0.0, 0.0), 0, False,
      ["Search aide answers {s} staff questions about policy and procedure with cited paragraphs.",
       "Internal helper finds the right procedure page for {s} colleagues and quotes it.",
       "Q and A bot over the {s} manual saves staff a trip to the intranet."]),
    A("meeting_summary", "Meeting summariser", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_meeting_notes_corp"],
      (0.05, 0.15, 0.80), (0.70, 0.30, 0.0, 0.0, 0.0), 0, False,
      ["Tool turns {s} meeting recordings into minutes and action lists.",
       "Note taker condenses calls held by {s} into a one page recap.",
       "Transcription add-on drafts follow-ups after {s} committee sessions."]),
    A("code_assist", "Engineering code aide", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_code_repository"],
      (0.05, 0.15, 0.80), (1.0, 0.0, 0.0, 0.0, 0.0), 0, False,
      ["Autocomplete and review helper for {s} developers working in the main repositories.",
       "Pair programming aide suggests tests and refactors for {s} code.",
       "Coding partner explains legacy modules to new {s} engineers."]),
    A("it_ticket_triage", "IT helpdesk ticket triage", "func", 0.0, (0.20, 0.80, 0.0),
      ["d_it_service_tickets"],
      (0.30, 0.40, 0.30), (1.0, 0.0, 0.0, 0.0, 0.0), 0, False,
      ["Classifier routes {s} service tickets to the right resolver group and suggests fixes.",
       "Model reads incoming {s} requests, sets priority and attaches similar past tickets.",
       "Ticket sorter reduces manual queue handling for the {s} service desk."]),
    A("resume_screen", "Candidate resume screening", "func", 0.0, (0.20, 0.50, 0.30),
      ["d_employee_hr_cases", "d_training_materials"],
      (0.20, 0.30, 0.50), (0.40, 0.60, 0.0, 0.0, 0.0), 1, False,
      ["Ranker scores incoming resumes against the {s} job description and shortlists candidates.",
       "Screening tool parses applications for {s} openings and schedules interviews.",
       "Matching model orders {s} candidate pools by skills fit."]),
    A("contract_extract", "Contract clause extraction", "func", 0.0, (0.30, 0.70, 0.0),
      ["d_vendor_contracts", "d_legal_matter_files"],
      (0.15, 0.25, 0.60), (0.70, 0.30, 0.0, 0.0, 0.0), 1, False,
      ["Extractor pulls renewal dates, caps and termination rights out of {s} agreements.",
       "Clause finder tags indemnity and data terms across the {s} contract archive.",
       "Reader builds an obligations table from {s} contracts for the register."]),
    A("legal_research", "Legal research aide", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_legal_matter_files", "d_published_filings"],
      (0.10, 0.20, 0.70), (0.80, 0.20, 0.0, 0.0, 0.0), 1, False,
      ["Aide summarises case law and prior matters for {s} counsel with source links.",
       "Research helper drafts memos on regulatory questions raised by {s}.",
       "Discovery aid clusters documents for a {s} investigation and ranks them by relevance."]),
    A("reg_change", "Regulatory change monitoring", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_published_filings", "d_policy_library"],
      (0.15, 0.25, 0.60), (1.0, 0.0, 0.0, 0.0, 0.0), 0, False,
      ["Watcher scans new rules and guidance and maps them to {s} policies.",
       "Alerting tool lists regulatory updates that touch {s} controls.",
       "Digest generator summarises supervisory publications for {s} owners."]),
    A("call_analytics", "Call centre speech analytics", "func", 0.0, (0.60, 0.40, 0.0),
      ["d_call_center_transcripts"],
      (0.10, 0.35, 0.55), (0.0, 0.40, 0.0, 0.60, 0.0), 1, True,
      ["Analytics layer transcribes recorded calls with {cu} and scores {s} agents on script adherence.",
       "Speech model surfaces complaint language and vulnerability cues in {s} conversations with {cu}.",
       "Quality tool samples calls handled by {s} and flags those needing coaching."]),
    A("wealth_prep", "Advisor meeting preparation", "wealth", 0.15, (0.85, 0.15, 0.0),
      ["d_wealth_client_profiles"],
      (0.15, 0.25, 0.60), (0.20, 0.40, 0.0, 0.40, 0.0), 1, True,
      ["Aide compiles holdings, life events and talking points for {s} advisers before reviews with {cu}.",
       "Briefing generator drafts meeting agendas from the {s} client profile.",
       "Preparation tool surfaces open requests and recent activity on {s} relationships."]),
    A("robo_rebalance", "Automated portfolio rebalancer", "wealth", 1.0, (0.0, 0.30, 0.70),
      ["d_wealth_client_profiles", "d_account_master"],
      (0.30, 0.50, 0.20), (0.50, 0.0, 0.0, 0.50, 0.0), 3, True,
      ["Engine rebalances model portfolios held by {cu} in {s} within drift limits.",
       "Robo service places trades to keep {s} allocations on target for {cu}.",
       "Allocation tool proposes and executes {s} switches according to risk profile."]),
    A("sanctions_match", "Sanctions name screening", "dep", 0.30, (0.0, 0.40, 0.60),
      ["d_transaction_history", "d_kyc_documents"],
      (0.25, 0.35, 0.40), (0.0, 0.0, 1.0, 0.0, 0.0), 2, True,
      ["Fuzzy matcher compares payee and sender names on {s} payments with watchlists.",
       "Screening model reduces false hits when checking {cu} and counterparties on {s} flows.",
       "Name match service releases or holds {s} transfers pending analyst review."]),
    A("limit_mgmt", "Credit limit management", "lend", 1.0, (0.05, 0.35, 0.60),
      ["d_account_master", "d_credit_bureau_pulls"],
      (0.55, 0.35, 0.10), (0.0, 0.05, 0.0, 0.35, 0.60), 3, True,
      ["Model raises or lowers {s} limits for {cu} each month based on behaviour and bureau data.",
       "Line management engine reviews {s} exposure and cuts limits on rising risk.",
       "Automated review adjusts {s} credit lines held by {cu} without a banker."]),
    A("account_monitor", "Account activity risk flags", "dep", 1.0, (0.10, 0.40, 0.50),
      ["d_deposit_account_events", "d_transaction_history"],
      (0.35, 0.45, 0.20), (0.0, 0.10, 0.30, 0.60, 0.0), 2, True,
      ["Monitor flags {s} accounts of {cu} for restriction or closure review.",
       "Behaviour model scores {s} deposit activity and recommends account action.",
       "Risk flagging service freezes suspect {s} accounts pending a decision."]),
    A("mortgage_docs", "Mortgage document processing", "mort", 0.30, (0.15, 0.70, 0.15),
      ["d_mortgage_underwriting_files", "d_loan_applications"],
      (0.35, 0.35, 0.30), (0.0, 0.30, 0.0, 0.20, 0.50), 2, True,
      ["Reader extracts income and asset figures from {s} files supplied by {cu}.",
       "Verification tool cross-checks pay stubs and statements in {s} packs.",
       "Processing aide assembles the underwriting checklist for {s} loans."]),
    A("collections_notes", "Collections call note summariser", "lend", 0.0, (0.40, 0.60, 0.0),
      ["d_collections_notes"],
      (0.15, 0.30, 0.55), (0.0, 0.20, 0.0, 0.80, 0.0), 1, True,
      ["Summariser writes the account note after each {s} collections call with {cu}.",
       "Note generator condenses payment promises and hardship statements on {s} calls.",
       "Drafting aid records agreed actions from {s} recovery conversations."]),
    A("fin_plan_chat", "Financial planning chat tool", "wealth", 1.0, (0.80, 0.20, 0.0),
      ["d_wealth_client_profiles", "d_product_brochures"],
      (0.10, 0.20, 0.70), (0.30, 0.20, 0.0, 0.50, 0.0), 1, True,
      ["Planning chat gives {cu} savings and retirement guidance tied to {s} products.",
       "Guided tool walks {cu} through goals and suggests {s} options.",
       "Interactive planner models scenarios for {cu} using {s} holdings."]),
    A("model_docs", "Model documentation drafting", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_model_inventory_records", "d_policy_library"],
      (0.10, 0.20, 0.70), (1.0, 0.0, 0.0, 0.0, 0.0), 0, False,
      ["Writer drafts validation and development documents for {s} models from templates.",
       "Documentation aid fills inventory entries and change logs for {s} owners.",
       "Template filler produces first drafts of model cards for {s} reviews."]),
    A("audit_papers", "Internal audit workpaper drafting", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_internal_audit_findings"],
      (0.15, 0.25, 0.60), (1.0, 0.0, 0.0, 0.0, 0.0), 0, False,
      ["Aide drafts test steps and findings write-ups for {s} audits.",
       "Workpaper helper summarises evidence collected in {s} fieldwork.",
       "Report builder turns {s} audit notes into the closing memo."]),
    A("vendor_questionnaire", "Vendor risk questionnaire reader", "func", 0.0, (0.40, 0.60, 0.0),
      ["d_vendor_contracts"],
      (0.15, 0.25, 0.60), (0.80, 0.20, 0.0, 0.0, 0.0), 1, False,
      ["Reader scores supplier answers to security questionnaires for {s} onboarding.",
       "Review aid compares vendor responses with the {s} control baseline.",
       "Questionnaire parser highlights gaps in third party evidence for {s}."]),
    A("pricing_opt", "Pricing optimisation", "all", 1.0, (0.15, 0.45, 0.40),
      ["d_pricing_models", "d_account_master"],
      (0.45, 0.40, 0.15), (0.0, 0.0, 0.0, 0.50, 0.50), 3, True,
      ["Optimiser sets offered rates and fees on {s} for {cu} by segment and elasticity.",
       "Pricing engine proposes margin changes across {s} and routes outliers to the committee.",
       "Rate tool recommends discounts on {s} deals to hold volume."]),
    A("branch_forecast", "Branch staffing forecast", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_branch_ops_logs"],
      (0.30, 0.40, 0.30), (1.0, 0.0, 0.0, 0.0, 0.0), 0, False,
      ["Forecaster predicts footfall and call volumes to plan {s} rosters.",
       "Planning model suggests shift patterns for {s} using last year's traffic.",
       "Demand estimate supports weekly {s} scheduling."]),
    A("treasury_cash", "Treasury cash forecasting", "func", 0.0, (0.80, 0.20, 0.0),
      ["d_deposit_account_events", "d_market_data_feed"],
      (0.30, 0.50, 0.20), (1.0, 0.0, 0.0, 0.0, 0.0), 2, False,
      ["Time series model projects daily funding needs for {s} across currencies.",
       "Forecast service estimates deposit outflows that drive {s} liquidity buffers.",
       "Projection tool feeds the {s} desk with intraday balance estimates."]),
    A("comms_drafting", "Customer communications drafting", "all", 1.0, (0.40, 0.60, 0.0),
      ["d_policy_library", "d_complaint_narratives"],
      (0.10, 0.15, 0.75), (0.30, 0.10, 0.0, 0.60, 0.0), 1, True,
      ["Drafting tool writes letters and emails to {cu} about {s} changes for agent review.",
       "Letter generator personalises {s} notices for {cu} from approved templates.",
       "Response writer prepares replies to {s} queries from {cu}."]),
    A("dispute_assist", "Card dispute resolution aide", "card", 0.30, (0.20, 0.70, 0.10),
      ["d_card_authorisations", "d_chat_logs_customer"],
      (0.25, 0.35, 0.40), (0.0, 0.20, 0.0, 0.70, 0.10), 2, True,
      ["Aide gathers evidence and proposes outcomes on {s} disputes raised by {cu}.",
       "Chargeback helper reads merchant records and drafts the {s} decision.",
       "Case aid pre-populates {s} dispute forms from transaction data."]),
    A("perf_review_writer", "Performance review writing aide", "func", 0.0, (1.0, 0.0, 0.0),
      ["d_employee_hr_cases"],
      (0.10, 0.20, 0.70), (0.40, 0.60, 0.0, 0.0, 0.0), 0, False,
      ["Writing aid turns manager notes into balanced {s} review text.",
       "Drafting helper suggests wording for {s} appraisal comments.",
       "Review aide standardises tone across {s} performance write-ups."]),
    A("hr_case_triage", "HR case triage", "func", 0.0, (0.40, 0.60, 0.0),
      ["d_employee_hr_cases"],
      (0.15, 0.25, 0.60), (0.30, 0.70, 0.0, 0.0, 0.0), 1, False,
      ["Classifier sorts employee relations cases by type and urgency for {s}.",
       "Intake model reads grievance forms and routes them to {s} specialists.",
       "Case sorter proposes the next step on {s} workplace matters."]),
    A("procurement_spend", "Procurement spend classification", "func", 0.0, (0.60, 0.40, 0.0),
      ["d_vendor_contracts", "d_branch_ops_logs"],
      (0.30, 0.40, 0.30), (1.0, 0.0, 0.0, 0.0, 0.0), 0, False,
      ["Classifier tags invoices and purchase orders by category for {s} reporting.",
       "Spend analysis model groups suppliers and spots duplicate payments for {s}.",
       "Categoriser cleans the {s} spend cube before the quarterly review."]),
]
for _i, _a in enumerate(ARCHETYPES):
    _a["n"] = 4 if _i < 27 else 3   # 27 x 4 + 11 x 3 = 141 base cases

CONTEXT = [
    "weekly backlog review", "north region pilot", "quarter end close window",
    "legacy mainframe feed", "branch rollout phase two", "overnight batch run",
    "dashboard for team leads", "shadow mode first", "twelve week pilot",
    "spreadsheet replacement", "shared mailbox intake", "manual rework today",
    "regional hub only", "overflow handling", "exception queue",
    "monthly committee pack", "audit finding follow up", "policy refresh cycle",
    "peak season volumes", "onboarding backlog", "vendor sandbox first",
    "read only access first", "team of six analysts", "email attachment intake",
    "single sign on required", "phase one scope", "nightly data refresh",
    "steering group reporting", "two branch pilot", "replaces keyword rules",
    "holiday volume spike", "queue ageing report", "pre-approved templates only",
    "evening coverage gap", "headcount neutral goal",
]
CUE_CONTEXT = ["supports the customer complaints log", "feeds client reporting",
               "used before customer contact"]

SYN = [("aide", "partner"), ("summarises", "condenses"), ("drafts", "prepares"),
       ("flags", "surfaces"), ("reviewers", "analysts"), ("cases", "files"),
       ("scores", "rates"), ("routes", "directs"), ("pulls", "extracts"),
       ("tags", "labels"), ("produces", "generates"), ("recommends", "suggests"),
       ("model", "engine"), ("tool", "service"), ("helps", "supports"),
       ("generator", "writer"), ("classifier", "sorter"), ("reader", "parser"),
       ("monitor", "watcher"), ("forecast", "projection"), ("chat", "messaging"),
       ("screening", "checking"), ("optimiser", "optimizer"), ("engine", "platform")]
UNITS = ["Retail Banking", "Cards", "Mortgage", "Commercial Banking", "Wealth", "Operations",
         "Compliance", "Finance", "Human Resources", "Legal", "Technology", "Marketing",
         "Risk Management", "Internal Audit", "Procurement", "Contact Centre", "Treasury",
         "Collections", "Fraud", "Branch Network"]

# ---------------------------------------------------------------------------
# Evidence checklist (cumulative, written long form)
# ---------------------------------------------------------------------------
EVIDENCE = [
    # id, first tier, item, interlock
    ("E01", 1, "Use-case card with named line-1 owner", "-"),
    ("E02", 1, "Data-source attestation (dataset names and classes)", "-"),
    ("E03", 2, "Evaluation plan and results summary", "04 EvalForge"),
    ("E04", 2, "Privacy and data-handling review", "-"),
    ("E05", 3, "Independent validation with effective challenge", "-"),
    ("E06", 3, "Human review design for the tier", "08 OversightOps"),
    ("E07", 3, "Decision logging and lineage plan", "09 LineageLog"),
    ("E08", 3, "Vendor and third-party due diligence", "-"),
    ("E09", 4, "Regulatory-scope legal review", "-"),
    ("E10", 4, "Fallback and exit plan", "-"),
    ("E11", 4, "CRO sign-off", "-"),
]


def required_items(tier: int) -> list[str]:
    return [eid for eid, first, _, _ in EVIDENCE if first <= tier]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def pick(weights, options):
    return rng.choices(options, weights=weights, k=1)[0]


def business_days(start: dt.date, n_weeks: int) -> list[dt.date]:
    days = []
    d = start
    while len(days) < n_weeks * 5:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def build_text(piece: dict, variant: int | None = None) -> tuple[str, str]:
    arch = piece["arch"]
    v = piece["variant"] if variant is None else variant
    sentence = arch["variants"][v].format(s=piece["subject"], cu=piece["cue_word"])
    sentence = sentence[0].upper() + sentence[1:]
    scope = "Scope: " + piece["ctx"][0] + "; " + piece["ctx"][1] + "."
    if piece["extra_cue"]:
        scope = scope[:-1] + "; " + piece["extra_cue"] + "."
    title = "%s for %s" % (arch["title"], piece["subject"])
    return title, sentence + " " + scope


def reword(text: str, p: float) -> str:
    out = text
    for a, b in SYN:
        if a in out and rng.random() < p:
            out = out.replace(a, b)
        elif a.capitalize() in out and rng.random() < p:
            out = out.replace(a.capitalize(), b.capitalize())
    return out


SHADE = {"down": 0, "up": 0}


def form_answers(t: dict) -> dict:
    """Apply the documented error rates to the true attributes."""
    # data class
    cls = t["true_data_class"]
    idx = CLASS_ORDER.index(cls)
    f_cls = cls
    if cls in P_DATA_UNDERSTATE and idx > 0 and rng.random() < P_DATA_UNDERSTATE[cls]:
        f_cls = CLASS_ORDER[idx - 1]
    # vendor
    ven = t["true_vendor_model"]
    f_ven = ven
    if ven in P_VENDOR_OMIT and rng.random() < P_VENDOR_OMIT[ven]:
        f_ven = "none"
    # customer facing
    cf = t["true_customer_facing"]
    r = rng.random()
    if cf == "yes":
        if r < P_CF_NO_WHEN_YES:
            f_cf = "no"
        elif r < P_CF_NO_WHEN_YES + P_CF_UNSURE_WHEN_YES:
            f_cf = "unsure"
        elif r < P_CF_NO_WHEN_YES + P_CF_UNSURE_WHEN_YES + P_CF_BLANK_WHEN_YES:
            f_cf = ""
        else:
            f_cf = "yes"
    else:
        if r < P_CF_YES_WHEN_NO:
            f_cf = "yes"
        elif r < P_CF_YES_WHEN_NO + P_CF_UNSURE_WHEN_NO:
            f_cf = "unsure"
        elif r < P_CF_YES_WHEN_NO + P_CF_UNSURE_WHEN_NO + P_CF_BLANK_WHEN_NO:
            f_cf = ""
        else:
            f_cf = "no"
    # autonomy, regulatory scope and exposure are copied from the truth (no injected error)
    own_score = rubric_score(f_cf, t["true_decision_autonomy"], f_cls, f_ven,
                             t["true_regulatory_scope"], t["true_financial_exposure_band"])
    own_tier = tier_from_score(own_score)
    declared = own_tier
    r2 = rng.random()
    if r2 < P_SHADE_DOWN:
        if own_tier > 1:
            declared = own_tier - 1
            SHADE["down"] += 1
    elif r2 < P_SHADE_DOWN + P_SHADE_UP:
        if own_tier < 4:
            declared = own_tier + 1
            SHADE["up"] += 1
    return dict(customer_facing=f_cf, decision_autonomy=t["true_decision_autonomy"],
                data_class=f_cls, vendor_model=f_ven,
                regulatory_scope=t["true_regulatory_scope"],
                financial_exposure_band=t["true_financial_exposure_band"],
                self_declared_tier=declared)


# ---------------------------------------------------------------------------
# 1. Data catalog (with a few stale entries)
# ---------------------------------------------------------------------------
under_pool = [n for n, _, c in DATASETS if c in ("confidential", "restricted")]
over_pool = [n for n, _, c in DATASETS if c in ("internal", "confidential")]
stale_under = rng.sample(under_pool, N_STALE_UNDER)
stale_over = rng.sample([n for n in over_pool if n not in stale_under], N_STALE_OVER)
catalog_rows = []
for name, steward, true_cls in DATASETS:
    cat_cls, status = true_cls, "current"
    if name in stale_under:
        cat_cls, status = CLASS_ORDER[CLASS_ORDER.index(true_cls) - 1], "stale_understated"
    elif name in stale_over:
        cat_cls, status = CLASS_ORDER[CLASS_ORDER.index(true_cls) + 1], "stale_overstated"
    catalog_rows.append(dict(dataset_name=name, steward_unit=steward, catalog_class=cat_cls,
                             true_class=true_cls, catalog_status=status))

# ---------------------------------------------------------------------------
# 2. Base cases (141) then duplicates (9) -> 150
# ---------------------------------------------------------------------------
base = []
for arch in ARCHETYPES:
    pool = FUNCTIONS if arch["pool"] == "func" else POOLS[arch["pool"]]
    subjects = rng.sample(pool, arch["n"])
    for subject in subjects:
        cf_true = "yes" if rng.random() < arch["cf"] else "no"
        aut = pick(arch["aut"], AUTONOMY)
        ven = pick(arch["ven"], VENDOR_ORDER)
        reg = pick(arch["reg"], REG_SCOPES)
        lvl = arch["lvl"] + rng.choice([-1, 0, 0, 0, 1])
        exp = EXPOSURE[max(0, min(3, lvl))]
        dataset = rng.choice(arch["ds"])
        # cue word for the description
        if cf_true == "yes":
            has_cue = rng.random() < P_CUE_WHEN_CF
        elif arch["talks"]:
            has_cue = rng.random() < P_CUE_WHEN_INTERNAL_TALKS
        else:
            has_cue = False
        cue_word = rng.choice(CUE_WORDS) if has_cue else rng.choice(NEUTRAL_WORDS)
        extra_cue = ""
        if cf_true == "no" and not arch["talks"] and rng.random() < P_CUE_WHEN_INTERNAL_OTHER:
            extra_cue = rng.choice(CUE_CONTEXT)
        piece = dict(arch=arch, subject=subject, variant=rng.randrange(3),
                     ctx=rng.sample(CONTEXT, 2), cue_word=cue_word, extra_cue=extra_cue)
        base.append(dict(
            piece=piece, dataset=dataset, sponsor_unit=subject.title() if arch["pool"] == "func" else SUBJECT_UNIT[subject],
            true_customer_facing=cf_true, true_decision_autonomy=aut,
            true_data_class=DS_CLASS[dataset], true_vendor_model=ven,
            true_regulatory_scope=reg, true_financial_exposure_band=exp,
            dup_group="", is_dup=False,
        ))

assert len(base) == 141, len(base)

# dates for base cases: 20 weeks, two heavy weeks around planning cycles
START = dt.date(2026, 1, 5)
N_WEEKS = 20
DAYS = business_days(START, N_WEEKS)
week_weight = [1.0] * N_WEEKS
for w in (3, 4, 11, 12):
    week_weight[w] = 2.2
day_weight = [week_weight[i // 5] for i in range(len(DAYS))]
for c in base:
    c["date"] = rng.choices(DAYS, weights=day_weight, k=1)[0]

# duplicates: 7 pairs + 1 triple (9 extra rows)
dup_sources = rng.sample(range(len(base)), 8)
dup_rows = []
for gi, src_i in enumerate(dup_sources):
    src = base[src_i]
    gname = "DG-%02d" % (gi + 1)
    src["dup_group"] = gname
    n_copies = 2 if gi == 0 else 1
    for _ in range(n_copies):
        piece = dict(src["piece"])
        piece["ctx"] = list(src["piece"]["ctx"])
        alt = rng.random() < 0.30
        variant = (piece["variant"] + 1) % 3 if alt else piece["variant"]
        title, desc = build_text(piece, variant)
        title = reword(title, 0.65)
        desc = reword(desc, 0.65)
        later = DAYS.index(src["date"]) + rng.randint(3, 30)
        later = min(later, len(DAYS) - 1)
        other_units = [u for u in UNITS if u != src["sponsor_unit"]]
        dup = dict(src)
        dup.update(dict(piece=piece, dup_group=gname, is_dup=True,
                        sponsor_unit=rng.choice(other_units), date=DAYS[later],
                        text_override=(title, desc)))
        dup_rows.append(dup)
assert len(dup_rows) == 9, len(dup_rows)

cases = base + dup_rows
assert len(cases) == 150
order = list(range(len(cases)))
rng.shuffle(order)  # random tie-break within a day
cases = [cases[i] for i in order]
cases.sort(key=lambda c: c["date"])
for i, c in enumerate(cases, 1):
    c["use_case_id"] = "UC-%03d" % i

# ---------------------------------------------------------------------------
# 3. Form answers, reference tier, registry, evidence
# ---------------------------------------------------------------------------
submission_rows, registry_rows, evidence_rows = [], [], []
for c in cases:
    if c.get("text_override"):
        title, desc = c["text_override"]
    else:
        title, desc = build_text(c["piece"])
    f = form_answers(c)
    score = rubric_score(c["true_customer_facing"], c["true_decision_autonomy"],
                         c["true_data_class"], c["true_vendor_model"],
                         c["true_regulatory_scope"], c["true_financial_exposure_band"])
    ref_tier = tier_from_score(score)
    row = dict(
        use_case_id=c["use_case_id"], submitted_date=c["date"].isoformat(),
        sponsor_unit=c["sponsor_unit"], title=title, description=desc,
        dataset_name=c["dataset"],
        customer_facing=f["customer_facing"], decision_autonomy=f["decision_autonomy"],
        data_class=f["data_class"], vendor_model=f["vendor_model"],
        regulatory_scope=f["regulatory_scope"],
        financial_exposure_band=f["financial_exposure_band"],
        self_declared_tier=f["self_declared_tier"],
        true_customer_facing=c["true_customer_facing"],
        true_decision_autonomy=c["true_decision_autonomy"],
        true_data_class=c["true_data_class"], true_vendor_model=c["true_vendor_model"],
        true_regulatory_scope=c["true_regulatory_scope"],
        true_financial_exposure_band=c["true_financial_exposure_band"],
        reference_score=score, reference_tier=ref_tier, duplicate_group=c["dup_group"],
    )
    submission_rows.append(row)
    # vendor registry: partial coverage of truly vendor-dependent cases
    if c["true_vendor_model"] != "none" and rng.random() < P_REGISTRY_COVERAGE:
        registry_rows.append(dict(use_case_id=c["use_case_id"],
                                  vendor_model=c["true_vendor_model"],
                                  source="procurement_registry"))
    # evidence on file: the sponsor attaches items for the tier they declared
    declared_items = set(required_items(f["self_declared_tier"]))
    for eid, first, _, _ in EVIDENCE:
        p = P_EVIDENCE_DECLARED if eid in declared_items else P_EVIDENCE_EXTRA
        if rng.random() < p:
            evidence_rows.append(dict(use_case_id=c["use_case_id"], evidence_id=eid))


def write_csv(name: str, rows: list[dict], fields: list[str]) -> None:
    with open(OUT / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


write_csv("intake_submissions.csv", submission_rows, list(submission_rows[0].keys()))
write_csv("data_catalog.csv", catalog_rows, list(catalog_rows[0].keys()))
write_csv("vendor_registry.csv", registry_rows, ["use_case_id", "vendor_model", "source"])
write_csv("evidence_on_file.csv", evidence_rows, ["use_case_id", "evidence_id"])
checklist_rows = []
for tier in (1, 2, 3, 4):
    for eid, first, item, interlock in EVIDENCE:
        if first <= tier:
            checklist_rows.append(dict(tier=tier, evidence_id=eid, evidence_item=item,
                                       interlock=interlock))
write_csv("evidence_checklist.csv", checklist_rows,
          ["tier", "evidence_id", "evidence_item", "interlock"])

if __name__ == "__main__":
    tiers = [r["reference_tier"] for r in submission_rows]
    cls_below = sum(1 for r in submission_rows
                    if CLASS_ORDER.index(r["data_class"]) < CLASS_ORDER.index(r["true_data_class"]))
    vend_true = [r for r in submission_rows if r["true_vendor_model"] != "none"]
    vend_omit = [r for r in vend_true if r["vendor_model"] == "none"]
    cf_bad = [r for r in submission_rows if r["customer_facing"] != r["true_customer_facing"]]
    n_dup = sum(1 for r in submission_rows if r["duplicate_group"])
    n_groups = len({r["duplicate_group"] for r in submission_rows if r["duplicate_group"]})
    print("Wrote %d submissions to %s" % (len(submission_rows), OUT / "intake_submissions.csv"))
    print("Wrote %d catalog rows, %d registry rows, %d evidence-on-file rows, %d checklist rows"
          % (len(catalog_rows), len(registry_rows), len(evidence_rows), len(checklist_rows)))
    print("Reference tier mix (tier 1, 2, 3, 4):", [tiers.count(t) for t in (1, 2, 3, 4)])
    print("Realized injected error (counts on this seed):")
    print("  form data class below the true class:        %d of %d" % (cls_below, len(submission_rows)))
    print("  vendor dependency omitted (form says none):  %d of %d vendor-dependent" % (len(vend_omit), len(vend_true)))
    print("  customer-facing answer wrong, blank or unsure: %d of %d" % (len(cf_bad), len(submission_rows)))
    print("  declared tier shaded down / up from the sponsor's own rubric result: %d / %d" % (SHADE["down"], SHADE["up"]))
    print("  catalog entries stale: %d understated, %d overstated (of %d datasets)"
          % (N_STALE_UNDER, N_STALE_OVER, len(DATASETS)))
    print("  vendor registry covers %d of %d vendor-dependent use cases" % (len(registry_rows), len(vend_true)))
    print("  duplicate groups: %d (%d submissions)" % (n_groups, n_dup))
    print("  distinct sponsor units: %d    archetypes: %d" % (len({r["sponsor_unit"] for r in submission_rows}), len(ARCHETYPES)))
