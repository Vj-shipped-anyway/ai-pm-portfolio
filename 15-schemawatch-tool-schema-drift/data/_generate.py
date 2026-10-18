"""Generates the SchemaWatch synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes four CSVs next to this file)

What it builds
  tool_schemas.csv    28 tool schemas as JSON-schema-like dicts. Revision v1 for every tool,
                      v2 for the tools that changed, v3 for the few that changed twice.
  change_ledger.csv   45 injected changes. This is the ground truth: every schema revision
                      after v1 is produced by applying these changes to the previous one.
  recorded_calls.csv  2,500 agent calls (argument dicts), all valid under v1, over one week.
  call_truth.csv      For every call: does it break under strict validation of the latest
                      revision, and does it still pass but mean something different.

The truth is known because the data is synthetic: the generator decides what changed, so it
can say exactly which calls break. Nothing here comes from a real bank, tool, API or model.
The calls are written by this script, not by any model.

Truth is computed from the ledger rules (what each change does to a v1-shaped call), not by
running a validator. The SchemaWatch replay in src/step_04 is a separate implementation that
validates calls against the schema text; comparing the two is one of the measurements.
"""

from __future__ import annotations

import copy
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20261017
N_CALLS = 2500
OUT = Path(__file__).parent
BASE_DATE = datetime(2026, 3, 2)          # Monday of the recorded week
V1_RELEASED = "2026-02-16T09:00"


# ---------------------------------------------------------------------------
# Tool definitions (v1)
# ---------------------------------------------------------------------------
def P(name, typ, desc, req=False, enum=None, default=None, minimum=None, maximum=None,
      maxlen=None, items=None, gen=None, p=0.5):
    return {"name": name, "type": typ, "description": desc, "req": req, "enum": enum,
            "default": default, "minimum": minimum, "maximum": maximum, "maxlen": maxlen,
            "items": items, "gen": gen, "p": p}


def T(name, version, weight, desc, params):
    return {"name": name, "version": version, "weight": weight, "description": desc,
            "params": params}


CCY6 = ["USD", "EUR", "GBP", "JPY", "CAD", "CHF"]
NAMES = ["Alder Holdings", "Birch Trading Co", "Cedar Logistics", "Dune Marine Ltd",
         "Elm Street Partners", "Fir Capital", "Gale Imports", "Hazel Foods",
         "Iris Medical Group", "Juniper Freight", "Kestrel Energy", "Linden Textiles"]
SUBJECTS = ["Statement question", "Card replacement", "Wire status", "Address change",
            "Loan documents", "Fee question", "Appointment follow-up", "Dispute update"]
SUMMARIES = ["Card declined at merchant", "Wire not received", "Cannot see statement",
             "Fee charged twice", "Loan payment date question", "Address not updated",
             "Transfer limit too low", "Alert not delivered"]

TOOLS = [
    T("get_account_balance", "1.0.0", 14, "Return the balance of one deposit account.", [
        P("account_id", "string", "Account identifier.", req=True, gen=("id", "AC", 6)),
        P("balance_type", "string", "Which balance to return.",
          enum=["available", "ledger", "pending"], default="available",
          gen=("choice", ["available", "ledger", "pending"], [55, 30, 15]), p=0.6),
        P("as_of_date", "string", "ISO date (YYYY-MM-DD). Defaults to today.",
          gen=("date", -30, 0), p=0.25),
    ]),
    T("get_transaction_history", "1.3.0", 12,
      "List posted transactions for one account over a date range.", [
        P("account_id", "string", "Account identifier.", req=True, gen=("id", "AC", 6)),
        P("start_date", "string", "Start of the range, ISO date.", req=True, gen=("date", -45, -20)),
        P("end_date", "string", "End of the range, ISO date, inclusive.", req=True,
          gen=("date", -19, 0)),
        P("limit", "integer", "Maximum number of transactions to return, up to 500.",
          default=50, minimum=1, maximum=500, gen=("int", 10, 200), p=0.45),
        P("txn_type", "string", "Filter by transaction type.",
          enum=["all", "debit", "credit", "fee"], default="all",
          gen=("choice", ["all", "debit", "credit", "fee"], [40, 30, 20, 10]), p=0.5),
    ]),
    T("initiate_wire_transfer", "1.0.0", 3, "Initiate an outbound wire from a deposit account.", [
        P("from_account", "string", "Source account identifier.", req=True, gen=("id", "AC", 6)),
        P("beneficiary_id", "string", "Registered beneficiary identifier.", req=True,
          gen=("id", "BN", 5)),
        P("amount", "number", "Wire amount in US dollars.", req=True, minimum=0.01,
          maximum=1000000, gen=("num", 100, 250000, 0.7)),
        P("currency", "string", "Currency the beneficiary receives.",
          enum=["USD", "EUR", "GBP"], default="USD",
          gen=("choice", ["USD", "EUR", "GBP"], [80, 12, 8]), p=0.7),
        P("speed", "string", "Delivery speed.", enum=["standard", "same_day"],
          default="standard", gen=("choice", ["standard", "same_day"], [70, 30]), p=0.5),
    ]),
    T("schedule_ach_payment", "1.2.0", 3, "Schedule an ACH payment to a registered payee.", [
        P("from_account", "string", "Source account identifier.", req=True, gen=("id", "AC", 6)),
        P("payee_id", "string", "Registered payee identifier.", req=True, gen=("id", "PY", 5)),
        P("amount", "number", "Payment amount in US dollars.", req=True, minimum=0.01,
          maximum=100000, gen=("num", 20, 8000, 0.8)),
        P("run_date", "string", "Date the payment is initiated, ISO date.", req=True,
          gen=("date", 1, 30)),
        P("frequency", "string", "How often the payment repeats.",
          enum=["once", "weekly", "monthly"], default="once",
          gen=("choice", ["once", "weekly", "monthly"], [60, 15, 25]), p=0.5),
        P("memo", "string", "Free-text memo shown to the payee.", maxlen=80,
          gen=("text", SUBJECTS), p=0.3),
    ]),
    T("get_fx_rate", "1.0.0", 5, "Return an indicative FX rate for a currency pair.", [
        P("base_currency", "string",
          "Base currency; the rate is quoted as units of the quote currency per one unit of base.",
          req=True, enum=CCY6, gen=("choice", CCY6, [40, 20, 15, 10, 10, 5])),
        P("quote_currency", "string", "Quote currency.", req=True, enum=CCY6,
          gen=("choice_not", CCY6, "base_currency")),
        P("amount", "number", "Amount of the base currency to convert.", minimum=0.01,
          gen=("num", 100, 50000, 0.5), p=0.4),
        P("rate_type", "string", "Which side of the market the rate is quoted on.",
          enum=["mid", "buy", "sell"], default="mid",
          gen=("choice", ["mid", "buy", "sell"], [60, 20, 20]), p=0.5),
    ]),
    T("lookup_customer_profile", "1.0.0", 8, "Fetch a customer profile by customer ID.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("fields", "array", "Profile fields to return. Defaults to all.",
          items={"type": "string", "enum": ["name", "address", "phone", "email", "segment",
                                            "risk_rating"]},
          gen=("list", ["name", "address", "phone", "email", "segment", "risk_rating"], 4), p=0.4),
        P("include_inactive", "boolean", "Include inactive relationships.", default=False,
          gen=("bool", 0.3), p=0.35),
    ]),
    T("update_customer_address", "1.0.0", 1.5, "Update the mailing address on a customer record.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("address_line1", "string", "Street address.", req=True, maxlen=80,
          gen=("text", ["12 Harbor Lane", "400 Mill Road", "88 Orchard Court", "7 Quarry Street"])),
        P("city", "string", "City.", req=True, gen=("text", ["Fairview", "Lakeside", "Ridgemont"])),
        P("state", "string", "Two-letter state code.", req=True, maxlen=2,
          gen=("text", ["NY", "CA", "TX", "OH", "WA"])),
        P("postal_code", "string", "Postal code.", req=True,
          gen=("text", ["10001", "94105", "73301", "43004", "98101"])),
        P("effective_date", "string", "Date the change takes effect, ISO date.",
          gen=("date", 0, 14), p=0.4),
    ]),
    T("run_kyc_check", "1.1.0", 1.5, "Run a KYC check against the identity vendor.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("check_level", "string", "Depth of the check.", enum=["standard", "enhanced"],
          default="standard", gen=("choice", ["standard", "enhanced"], [75, 25]), p=0.6),
        P("id_document_type", "string", "Document presented by the customer.", req=True,
          enum=["passport", "drivers_license", "national_id", "utility_bill"],
          gen=("choice", ["passport", "drivers_license", "national_id", "utility_bill"],
               [30, 40, 20, 10])),
    ]),
    T("screen_sanctions", "1.0.0", 2.5, "Screen a name against sanctions lists.", [
        P("name", "string", "Name to screen.", req=True, maxlen=120, gen=("text", NAMES)),
        P("country", "string", "Two-letter country code.", req=True, maxlen=2,
          gen=("text", ["US", "GB", "DE", "FR", "SG", "AE", "MX"])),
        P("date_of_birth", "string", "Date of birth, ISO date.", gen=("date", -20000, -7000), p=0.3),
        P("match_threshold", "number", "Fuzzy match threshold between 0 and 1.", default=0.85,
          minimum=0, maximum=1, gen=("float", 0.7, 0.99, 2), p=0.4),
        P("timeout", "integer", "Maximum wait for the screening vendor, in seconds.",
          minimum=1, maximum=120, gen=("int", 5, 60), p=0.5),
    ]),
    T("get_credit_score", "1.0.0", 6, "Return a credit score for a customer.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("bureau", "string", "Bureau to query.", enum=["equifax", "experian", "transunion"],
          default="experian", gen=("choice", ["equifax", "experian", "transunion"], [30, 40, 30]),
          p=0.5),
        P("purpose", "string", "Permissible purpose for the pull.", req=True,
          enum=["account_opening", "review", "collections"],
          gen=("choice", ["account_opening", "review", "collections"], [50, 40, 10])),
    ]),
    T("calculate_loan_payment", "1.0.0", 4, "Calculate the periodic payment on an amortizing loan.", [
        P("principal", "number", "Loan principal in US dollars.", req=True, minimum=1,
          maximum=5000000, gen=("num", 5000, 750000, 0.2)),
        P("annual_rate", "number", "Annual interest rate, in percent, for example 6.5.", req=True,
          minimum=0, maximum=100, gen=("float", 2.5, 12.5, 2)),
        P("term_months", "integer", "Loan term in months.", req=True, minimum=1, maximum=480,
          gen=("choice", [12, 24, 36, 48, 60, 84, 120, 180, 240, 360], None)),
        P("payment_frequency", "string", "How often payments are made.",
          enum=["monthly", "biweekly"], default="monthly",
          gen=("choice", ["monthly", "biweekly"], [85, 15]), p=0.4),
    ]),
    T("submit_loan_application", "2.4.0", 1.5, "Submit a loan application for a customer.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("product_code", "string", "Loan product.", req=True,
          enum=["auto", "mortgage", "personal", "heloc"],
          gen=("choice", ["auto", "mortgage", "personal", "heloc"], [30, 30, 30, 10])),
        P("requested_amount", "number", "Requested amount in US dollars.", req=True, minimum=1,
          maximum=5000000, gen=("num", 5000, 600000, 0.1)),
        P("term_months", "integer", "Requested term in months.", req=True, minimum=1, maximum=480,
          gen=("choice", [24, 36, 60, 84, 120, 240, 360], None)),
        P("purpose", "string", "Stated purpose of the loan.", maxlen=120,
          gen=("text", ["Vehicle purchase", "Home improvement", "Debt consolidation"]), p=0.5),
    ]),
    T("get_rate_sheet", "1.0.0", 3, "Return the current rate sheet for a product.", [
        P("product_code", "string", "Product to price.", req=True,
          enum=["auto", "mortgage", "personal", "heloc", "cd"],
          gen=("choice", ["auto", "mortgage", "personal", "heloc", "cd"], [25, 30, 20, 15, 10])),
        P("as_of_date", "string", "Effective date of the rates, ISO date.", gen=("date", -10, 0),
          p=0.3),
        P("region", "string", "Pricing region.",
          enum=["national", "northeast", "south", "midwest", "west"], default="national",
          gen=("choice", ["national", "northeast", "south", "midwest", "west"],
               [40, 15, 15, 15, 15]), p=0.5),
    ]),
    T("place_card_hold", "1.0.0", 2, "Place an authorization hold on a card.", [
        P("card_id", "string", "Card identifier.", req=True, gen=("id", "CR", 6)),
        P("amount", "number", "Hold amount in US dollars.", req=True, minimum=0.01,
          maximum=50000, gen=("num", 5, 2500, 0.9)),
        P("merchant", "string", "Merchant name.", maxlen=60, gen=("text", NAMES), p=0.5),
        P("duration_hours", "integer", "Hold duration in hours.", default=72, minimum=1,
          maximum=720, gen=("choice", [24, 48, 72, 120, 168], None), p=0.4),
    ]),
    T("block_card", "1.0.0", 1.5, "Block a card.", [
        P("card_id", "string", "Card identifier.", req=True, gen=("id", "CR", 6)),
        P("reason", "string", "Why the card is being blocked.", req=True,
          enum=["lost", "stolen", "fraud_suspected", "customer_request"],
          gen=("choice", ["lost", "stolen", "fraud_suspected", "customer_request"],
               [35, 30, 20, 15])),
        P("replace_card", "boolean", "Order a replacement card.", default=True,
          gen=("bool", 0.8), p=0.6),
    ]),
    T("dispute_transaction", "1.0.0", 1.5, "Open a dispute on a posted transaction.", [
        P("transaction_id", "string", "Transaction identifier.", req=True, gen=("id", "TX", 8)),
        P("reason_code", "string", "Reason for the dispute.", req=True,
          enum=["unauthorized", "duplicate", "not_received", "incorrect_amount"],
          gen=("choice", ["unauthorized", "duplicate", "not_received", "incorrect_amount"],
               [35, 25, 20, 20])),
        P("amount", "number", "Disputed amount in US dollars.", minimum=0.01,
          gen=("num", 10, 3000, 0.9), p=0.4),
        P("comments", "string", "Free-text comments.", maxlen=500, gen=("text", SUMMARIES), p=0.4),
    ]),
    T("get_statement_pdf", "1.0.0", 4, "Return a monthly statement for an account.", [
        P("account_id", "string", "Account identifier.", req=True, gen=("id", "AC", 6)),
        P("statement_month", "string", "Statement month, format YYYY-MM.", req=True,
          gen=("month",)),
        P("delivery", "string",
          "inline returns the PDF content; secure_link returns a link that expires after 7 days.",
          enum=["inline", "secure_link"], default="inline",
          gen=("choice", ["inline", "secure_link"], [60, 40]), p=0.5),
    ]),
    T("create_support_ticket", "1.0.0", 3, "Open a support ticket for a customer.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("category", "string", "Ticket category.", req=True,
          enum=["card", "payments", "account", "loan", "fraud", "other"],
          gen=("choice", ["card", "payments", "account", "loan", "fraud", "other"],
               [25, 25, 20, 10, 5, 15])),
        P("priority", "string", "Ticket priority.", enum=["low", "normal", "high"],
          default="normal", gen=("choice", ["low", "normal", "high"], [20, 65, 15]), p=0.5),
        P("summary", "string", "One-line summary of the issue.", req=True, maxlen=200,
          gen=("text", SUMMARIES)),
    ]),
    T("schedule_appointment", "1.0.0", 1.5, "Book a branch appointment for a customer.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("branch_id", "string", "Branch identifier.", req=True, gen=("id", "BR", 3)),
        P("slot_start", "string", "Start of the slot, ISO date.", req=True, gen=("date", 1, 30)),
        P("duration_minutes", "integer", "Appointment length in minutes, 15 to 120.", default=30,
          minimum=15, maximum=120, gen=("choice", [15, 30, 45, 60], None), p=0.5),
        P("topic", "string", "Topic of the appointment.",
          enum=["account_opening", "loans", "advice", "other"],
          gen=("choice", ["account_opening", "loans", "advice", "other"], [30, 30, 25, 15]), p=0.5),
    ]),
    T("send_secure_message", "1.0.0", 3, "Send a secure message to a customer.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("subject", "string", "Message subject.", req=True, maxlen=100, gen=("text", SUBJECTS)),
        P("body", "string", "Message body, up to 2000 characters.", req=True, maxlen=2000,
          gen=("text", ["Your request has been received.", "Please see the attached document.",
                        "A banker will contact you shortly."])),
        P("attachment_ids", "array", "Identifiers of uploaded attachments.",
          items={"type": "string"}, gen=("idlist", "AT", 6, 3), p=0.25),
    ]),
    T("find_branch", "1.0.0", 3, "Find branches near a postal code.", [
        P("postal_code", "string", "Postal code to search around.", req=True,
          gen=("text", ["10001", "94105", "73301", "43004", "98101"])),
        P("radius_miles", "number", "Search radius in miles.", minimum=1, maximum=100,
          gen=("choice", [2, 5, 10, 25, 50], None), p=0.5),
        P("services", "array", "Services the branch must offer.",
          items={"type": "string", "enum": ["notary", "safe_deposit", "wire", "business"]},
          gen=("list", ["notary", "safe_deposit", "wire", "business"], 2), p=0.3),
        P("limit", "integer", "Maximum number of branches to return.", default=5, minimum=1,
          maximum=20, gen=("int", 1, 10), p=0.4),
    ]),
    T("find_atm", "1.0.0", 2, "Find ATMs near a coordinate.", [
        P("latitude", "number", "Latitude of the search centre, decimal degrees.", req=True,
          minimum=-90, maximum=90, gen=("float", 25.0, 48.0, 4)),
        P("longitude", "number", "Longitude of the search centre, decimal degrees.", req=True,
          minimum=-180, maximum=180, gen=("float", -122.0, -71.0, 4)),
        P("network", "string", "ATM network to include in the search.",
          enum=["any", "plus", "cirrus", "internal"],
          gen=("choice", ["any", "plus", "cirrus", "internal"], [40, 20, 20, 20]), p=0.5),
    ]),
    T("set_transfer_limit", "1.0.0", 1, "Set the daily transfer limit on an account.", [
        P("account_id", "string", "Account identifier.", req=True, gen=("id", "AC", 6)),
        P("daily_limit", "number", "Daily transfer limit, applied per account, in US dollars.",
          req=True, minimum=0, maximum=1000000, gen=("num", 500, 25000, 0.0)),
        P("channel", "string", "Channel the limit applies to.",
          enum=["online", "mobile", "branch", "all"], default="all",
          gen=("choice", ["online", "mobile", "branch", "all"], [20, 20, 10, 50]), p=0.5),
    ]),
    T("get_fee_schedule", "1.0.0", 2, "Return the fee schedule for a product.", [
        P("product_code", "string", "Product to look up.", req=True,
          enum=["checking", "savings", "business", "premium"],
          gen=("choice", ["checking", "savings", "business", "premium"], [40, 25, 20, 15])),
        P("tier", "string", "Fee tier to return.", enum=["basic", "plus", "premier"],
          default="basic", gen=("choice", ["basic", "plus", "premier"], [50, 30, 20]), p=0.5),
    ]),
    T("calculate_early_payoff", "1.0.0", 3, "Compute the early payoff amount for a loan.", [
        P("loan_id", "string", "Loan identifier.", req=True, gen=("id", "LN", 6)),
        P("payoff_date", "string", "Date the payoff amount is computed for, ISO date.", req=True,
          gen=("date", 1, 60)),
        P("include_fees", "boolean", "Include fees in the payoff amount.", default=True,
          gen=("bool", 0.7), p=0.5),
    ]),
    T("create_savings_goal", "1.0.0", 1, "Create a savings goal for a customer.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("goal_name", "string", "Name of the goal.", req=True, maxlen=60,
          gen=("text", ["Emergency fund", "Home deposit", "Education", "Vehicle"])),
        P("target_amount", "number", "Target amount in US dollars.", req=True, minimum=1,
          gen=("num", 500, 50000, 0.1)),
        P("target_date", "string", "Date the goal should be reached, ISO date.", req=True,
          gen=("date", 60, 720)),
        P("monthly_contribution", "number", "Planned monthly contribution in US dollars.",
          minimum=1, gen=("num", 50, 2000, 0.2), p=0.5),
    ]),
    T("get_portfolio_summary", "1.4.0", 3, "Return a portfolio summary for a customer.", [
        P("customer_id", "string", "Customer identifier.", req=True, gen=("id", "CU", 6)),
        P("as_of_date", "string", "Valuation date, ISO date.", gen=("date", -10, 0), p=0.3),
        P("currency", "string", "Reporting currency.", enum=["USD", "EUR"], default="USD",
          gen=("choice", ["USD", "EUR"], [85, 15]), p=0.4),
        P("include_positions", "boolean", "Include position-level detail.", default=False,
          gen=("bool", 0.4), p=0.3),
    ]),
    T("search_policy_docs", "1.0.0", 5, "Search the internal policy library.", [
        P("query", "string", "Search text.", req=True, maxlen=200,
          gen=("text", ["wire cutoff times", "address change policy", "card dispute process",
                        "fee waiver rules", "KYC refresh policy", "ACH return handling"])),
        P("doc_type", "string", "Document category to search.",
          enum=["policy", "procedure", "faq", "regulation"], default="policy",
          gen=("choice", ["policy", "procedure", "faq", "regulation"], [40, 30, 20, 10]), p=0.5),
        P("max_results", "integer", "Maximum number of results to return.", default=5,
          minimum=1, maximum=20, gen=("int", 1, 10), p=0.4),
    ]),
]

TOOL_BY_NAME = {t["name"]: t for t in TOOLS}
assert len(TOOLS) == 28


# ---------------------------------------------------------------------------
# Change plan: the injected change ledger (ground truth)
# ---------------------------------------------------------------------------
# Each release: (tool, revision, released_at, new_declared_version or None, [ops]).
# new_declared_version None means the release shipped WITHOUT a version bump.
# Ops: (change_type, param, ...) - see apply_op().
SPEC = {
    "locale": {"type": "string", "description": "Locale for formatted fields, for example en-US."},
    "include_holds": {"type": "boolean", "description": "Include pending holds in the result."},
    "accessible_only": {"type": "boolean", "description": "Only return step-free locations."},
    "nickname": {"type": "string", "description": "Optional display name for the goal.",
                 "maxLength": 40},
    "idempotency_key": {"type": "string", "description": "Client-supplied key that makes the wire safe to retry."},
    "verification_token": {"type": "string", "description": "One-time token from the address verification step."},
    "consent_id": {"type": "string", "description": "Identifier of the recorded customer consent."},
    "applicant_consent": {"type": "boolean", "description": "True if the applicant consented to the credit pull."},
}

RELEASES = [
    ("get_account_balance", "v2", "2026-04-08T10:00", "1.1.0", [
        ("enum_value_removed", "balance_type", "pending"),
        ("optional_added", "include_holds", "include_holds"),
    ]),
    ("get_transaction_history", "v2", "2026-04-09T14:30", None, [
        ("param_renamed", "limit", "page_size"),
        ("default_changed", "txn_type", "debit"),
    ]),
    ("initiate_wire_transfer", "v2", "2026-04-13T09:15", "1.1.0", [
        ("required_added", "idempotency_key", "idempotency_key"),
        ("enum_value_added", "currency", "CAD"),
    ]),
    ("schedule_ach_payment", "v2", "2026-04-14T16:00", "2.0.0", [
        ("param_renamed", "payee_id", "beneficiary_id"),
    ]),
    ("get_fx_rate", "v2", "2026-04-15T11:45", None, [
        ("enum_value_added", "rate_type", "wholesale"),
        ("meaning_changed", "base_currency",
         "Base currency; the rate is quoted as units of the base currency per one unit of the quote currency."),
    ]),
    ("lookup_customer_profile", "v2", "2026-04-16T13:20", "1.0.1", [
        ("optional_added", "locale", "locale"),
        ("description_reworded", "",
         "Return the profile record for a customer ID."),
    ]),
    ("update_customer_address", "v2", "2026-04-20T10:05", "2.0.0", [
        ("required_added", "verification_token", "verification_token"),
    ]),
    ("run_kyc_check", "v2", "2026-04-21T15:40", "1.2.0", [
        ("required_added", "consent_id", "consent_id"),
    ]),
    ("screen_sanctions", "v2", "2026-04-22T09:30", "1.0.1", [
        ("default_changed", "match_threshold", 0.95),
        ("unit_changed", "timeout", "Maximum wait for the screening vendor, in milliseconds."),
    ]),
    ("calculate_loan_payment", "v2", "2026-04-23T12:10", None, [
        ("unit_changed", "annual_rate", "Annual interest rate, in basis points, for example 6.5."),
        ("type_changed", "principal", "integer"),
    ]),
    ("submit_loan_application", "v2", "2026-04-27T14:00", "3.0.0", [
        ("required_added", "applicant_consent", "applicant_consent"),
    ]),
    ("get_rate_sheet", "v2", "2026-04-28T10:30", "1.1.0", [
        ("enum_value_removed", "product_code", "heloc"),
        ("default_changed", "region", "northeast"),
    ]),
    ("place_card_hold", "v2", "2026-04-29T16:45", None, [
        ("unit_changed", "amount", "Hold amount in cents."),
    ]),
    ("block_card", "v2", "2026-05-04T09:00", "1.0.1", [
        ("description_reworded", "replace_card", "Whether to order a replacement card."),
    ]),
    ("dispute_transaction", "v2", "2026-05-05T11:15", None, [
        ("type_changed", "transaction_id", "integer"),
        ("enum_value_added", "reason_code", "fraud"),
    ]),
    ("get_statement_pdf", "v2", "2026-05-06T13:50", None, [
        ("description_reworded", "delivery",
         "inline returns the PDF content; secure_link returns a link that expires after seven days."),
    ]),
    ("create_support_ticket", "v2", "2026-05-07T10:20", "1.1.0", [
        ("enum_value_removed", "category", "other"),
    ]),
    ("schedule_appointment", "v2", "2026-05-11T15:10", None, [
        ("type_changed", "branch_id", "integer"),
        ("type_changed", "duration_minutes", "number"),
    ]),
    ("send_secure_message", "v2", "2026-05-12T09:40", "1.1.0", [
        ("param_removed", "attachment_ids", ""),
    ]),
    ("find_branch", "v2", "2026-05-13T14:25", "1.0.1", [
        ("unit_changed", "radius_miles", "Search radius in kilometers."),
        ("type_changed", "limit", "number"),
    ]),
    ("find_atm", "v2", "2026-05-14T10:55", "1.0.1", [
        ("optional_added", "accessible_only", "accessible_only"),
        ("meaning_changed", "network", "ATM network to exclude from the search."),
    ]),
    ("set_transfer_limit", "v2", "2026-05-18T12:35", "1.0.1", [
        ("description_reworded", "", "Change the daily transfer limit for an account."),
        ("meaning_changed", "daily_limit",
         "Daily transfer limit, applied per customer, in US dollars."),
    ]),
    ("get_fee_schedule", "v2", "2026-05-19T16:20", "1.0.1", [
        ("description_reworded", "", "Return the fees that apply to a product."),
    ]),
    ("create_savings_goal", "v2", "2026-05-20T09:10", "1.1.0", [
        ("optional_added", "nickname", "nickname"),
        ("unit_changed", "target_amount", "Target amount in euros."),
    ]),
    ("get_portfolio_summary", "v2", "2026-05-21T11:30", "2.0.0", [
        ("param_removed", "include_positions", ""),
    ]),
    ("search_policy_docs", "v2", "2026-05-22T13:05", None, [
        ("enum_value_added", "doc_type", "guideline"),
    ]),
    # ---- third revisions ----
    ("initiate_wire_transfer", "v3", "2026-06-02T10:00", None, [
        ("description_reworded", "amount", "Wire amount in USD."),
    ]),
    ("lookup_customer_profile", "v3", "2026-06-04T14:10", None, [
        ("param_renamed", "include_inactive", "include_closed"),
    ]),
    ("block_card", "v3", "2026-06-09T09:30", "1.1.0", [
        ("enum_value_removed", "reason", "customer_request"),
    ]),
    ("create_support_ticket", "v3", "2026-06-11T15:50", None, [
        ("param_renamed", "summary", "title"),
    ]),
    ("get_fee_schedule", "v3", "2026-06-16T11:00", None, [
        ("default_changed", "tier", "plus"),
    ]),
]

CLASS_OF = {
    "param_renamed": "breaking", "required_added": "breaking", "enum_value_removed": "breaking",
    "param_removed": "breaking", "enum_value_added": "non_breaking",
    "optional_added": "non_breaking", "description_reworded": "non_breaking",
    "default_changed": "behavior_risk", "unit_changed": "behavior_risk",
    "meaning_changed": "behavior_risk",
}
SEMANTIC_KIND = {"unit_changed": "unit_signal", "meaning_changed": "no_signal"}


def is_widening(old_type: str, new_type: str) -> bool:
    return old_type == "integer" and new_type == "number"


# ---------------------------------------------------------------------------
# Build schemas
# ---------------------------------------------------------------------------
def prop_schema(p: dict) -> dict:
    s: dict = {"type": p["type"], "description": p["description"]}
    if p["enum"] is not None:
        s["enum"] = list(p["enum"])
    if p["default"] is not None:
        s["default"] = p["default"]
    if p["minimum"] is not None:
        s["minimum"] = p["minimum"]
    if p["maximum"] is not None:
        s["maximum"] = p["maximum"]
    if p["maxlen"] is not None:
        s["maxLength"] = p["maxlen"]
    if p["items"] is not None:
        s["items"] = copy.deepcopy(p["items"])
    return s


def v1_schema(tool: dict) -> dict:
    return {
        "name": tool["name"],
        "version": tool["version"],
        "description": tool["description"],
        "parameters": {
            "type": "object",
            "properties": {p["name"]: prop_schema(p) for p in tool["params"]},
            "required": [p["name"] for p in tool["params"] if p["req"]],
            "additionalProperties": False,
        },
    }


def apply_op(schema: dict, op: tuple, new_version) -> dict:
    """Apply one ledger operation to a schema (in place) and return a ledger row stub."""
    ctype, param = op[0], op[1]
    props = schema["parameters"]["properties"]
    req = schema["parameters"]["required"]
    row = {"change_type": ctype, "param": param, "old_value": "", "new_value": "", "kind": ""}
    if ctype == "param_renamed":
        new = op[2]
        props_new = {}
        for k, v in props.items():
            props_new[new if k == param else k] = v
        schema["parameters"]["properties"] = props_new
        schema["parameters"]["required"] = [new if r == param else r for r in req]
        row["old_value"], row["new_value"] = param, new
    elif ctype == "type_changed":
        old_type = props[param]["type"]
        props[param]["type"] = op[2]
        row["old_value"], row["new_value"] = old_type, op[2]
        row["kind"] = "widen" if is_widening(old_type, op[2]) else "tighten"
    elif ctype in ("required_added", "optional_added"):
        spec = copy.deepcopy(SPEC[op[2]])
        props[param] = spec
        if ctype == "required_added":
            req.append(param)
        row["new_value"] = spec["type"]
    elif ctype == "enum_value_removed":
        props[param]["enum"].remove(op[2])
        row["old_value"] = op[2]
    elif ctype == "enum_value_added":
        props[param]["enum"].append(op[2])
        row["new_value"] = op[2]
    elif ctype == "default_changed":
        row["old_value"] = json.dumps(props[param].get("default"))
        props[param]["default"] = op[2]
        row["new_value"] = json.dumps(op[2])
    elif ctype in ("unit_changed", "meaning_changed", "description_reworded"):
        target = props[param] if param else schema
        row["old_value"] = target["description"]
        target["description"] = op[2]
        row["new_value"] = op[2]
    elif ctype == "param_removed":
        del props[param]
        schema["parameters"]["required"] = [r for r in req if r != param]
        row["old_value"] = param
    else:
        raise ValueError(ctype)
    if new_version:
        schema["version"] = new_version
    return row


def build_schemas_and_ledger():
    schemas = {}   # (tool, rev) -> (schema, released_at)
    latest = {}
    for t in TOOLS:
        s = v1_schema(t)
        schemas[(t["name"], "v1")] = (copy.deepcopy(s), V1_RELEASED)
        latest[t["name"]] = (s, "v1")
    ledger = []
    for tool, rev, at, new_version, ops in sorted(RELEASES, key=lambda r: r[2]):
        prev_schema, prev_rev = latest[tool]
        assert (prev_rev, rev) in (("v1", "v2"), ("v2", "v3")), (tool, prev_rev, rev)
        s = copy.deepcopy(prev_schema)
        ver_before = s["version"]
        for op in ops:
            row = apply_op(s, op, None)
            row.update({"tool": tool, "from_rev": prev_rev, "to_rev": rev, "released_at": at})
            ledger.append(row)
        if new_version:
            s["version"] = new_version
        for row in ledger[-len(ops):]:
            row["declared_version_before"] = ver_before
            row["declared_version_after"] = s["version"]
            row["version_bumped"] = "yes" if s["version"] != ver_before else "no"
            ctype = row["change_type"]
            if ctype == "type_changed":
                row["true_class"] = "non_breaking" if row["kind"] == "widen" else "breaking"
            else:
                row["true_class"] = CLASS_OF[ctype]
            row["semantic_kind"] = SEMANTIC_KIND.get(ctype, "none")
        schemas[(tool, rev)] = (copy.deepcopy(s), at)
        latest[tool] = (s, rev)
    for i, row in enumerate(ledger, 1):
        row["change_id"] = f"CH-{i:03d}"
    return schemas, ledger


# ---------------------------------------------------------------------------
# Generate calls
# ---------------------------------------------------------------------------
def gen_value(rng: random.Random, spec: tuple, args: dict):
    kind = spec[0]
    if kind == "id":
        return f"{spec[1]}-{rng.randint(10 ** (spec[2] - 1), 10 ** spec[2] - 1)}"
    if kind == "choice":
        return rng.choices(spec[1], weights=spec[2], k=1)[0] if spec[2] else rng.choice(spec[1])
    if kind == "choice_not":
        other = args[spec[2]]
        return rng.choice([v for v in spec[1] if v != other])
    if kind == "int":
        return rng.randint(spec[1], spec[2])
    if kind == "num":
        lo, hi, frac = spec[1], spec[2], spec[3]
        if rng.random() < frac:
            return round(rng.uniform(lo, hi), 2)
        return int(round(rng.uniform(lo, hi) / 5.0) * 5)
    if kind == "float":
        return round(rng.uniform(spec[1], spec[2]), spec[3])
    if kind == "date":
        return (BASE_DATE + timedelta(days=rng.randint(spec[1], spec[2]))).strftime("%Y-%m-%d")
    if kind == "month":
        return rng.choice(["2025-12", "2026-01", "2026-02"])
    if kind == "text":
        return rng.choice(spec[1])
    if kind == "bool":
        return rng.random() < spec[1]
    if kind == "list":
        k = rng.randint(1, spec[2])
        return rng.sample(spec[1], k)
    if kind == "idlist":
        k = rng.randint(1, spec[3])
        return [f"{spec[1]}-{rng.randint(10 ** (spec[2] - 1), 10 ** spec[2] - 1)}" for _ in range(k)]
    raise ValueError(kind)


def allocate(total: int, weights: list) -> list:
    s = float(sum(weights))
    raw = [w / s * total for w in weights]
    base = [int(x) for x in raw]
    rem = total - sum(base)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:rem]:
        base[i] += 1
    return base


def call_time(rng: random.Random) -> datetime:
    day = rng.choices(range(7), weights=[20, 21, 20, 20, 19, 5, 3], k=1)[0]
    hour = rng.choices(range(24), weights=[1, 1, 1, 1, 1, 1, 2, 4, 8, 10, 11, 11, 9, 10, 11, 11, 10, 8,
                                           5, 3, 2, 2, 1, 1], k=1)[0]
    return BASE_DATE + timedelta(days=day, hours=hour, minutes=rng.randint(0, 59),
                                 seconds=rng.randint(0, 59))


def valid_under_v1(schema: dict, args: dict) -> bool:
    """Minimal check used only to prove the generator emits calls that are valid under v1."""
    props = schema["parameters"]["properties"]
    if any(k not in props for k in args):
        return False
    if any(r not in args for r in schema["parameters"]["required"]):
        return False
    for k, v in args.items():
        sp = props[k]
        t = sp["type"]
        if t == "string" and not isinstance(v, str):
            return False
        if t == "integer" and (isinstance(v, bool) or not isinstance(v, int)):
            return False
        if t == "number" and (isinstance(v, bool) or not isinstance(v, (int, float))):
            return False
        if t == "boolean" and not isinstance(v, bool):
            return False
        if t == "array" and not isinstance(v, list):
            return False
        if "enum" in sp and v not in sp["enum"]:
            return False
        if t in ("integer", "number") and ("minimum" in sp and v < sp["minimum"]
                                           or "maximum" in sp and v > sp["maximum"]):
            return False
        if t == "string" and "maxLength" in sp and len(v) > sp["maxLength"]:
            return False
        if t == "array" and "items" in sp and "enum" in sp["items"]:
            if any(x not in sp["items"]["enum"] for x in v):
                return False
    return True


def generate_calls(rng: random.Random, schemas: dict) -> list:
    counts = allocate(N_CALLS, [t["weight"] for t in TOOLS])
    calls = []
    for tool, n in zip(TOOLS, counts):
        schema = schemas[(tool["name"], "v1")][0]
        for _ in range(n):
            args: dict = {}
            for p in tool["params"]:
                if p["req"] or rng.random() < p["p"]:
                    args[p["name"]] = gen_value(rng, p["gen"], args)
            assert valid_under_v1(schema, args), (tool["name"], args)
            calls.append({"tool": tool["name"], "called_at": call_time(rng), "args": args})
    calls.sort(key=lambda c: (c["called_at"], c["tool"]))
    for i, c in enumerate(calls, 1):
        c["call_id"] = f"C{i:04d}"
    return calls


# ---------------------------------------------------------------------------
# Truth: what each ledger change does to a v1-shaped call
# ---------------------------------------------------------------------------
def change_breaks(ch: dict, args: dict) -> bool:
    t, p = ch["change_type"], ch["param"]
    if t in ("param_renamed", "param_removed"):
        return p in args
    if t == "required_added":
        return True
    if t == "enum_value_removed":
        return p in args and args[p] == ch["old_value"]
    if t == "type_changed" and ch["kind"] == "tighten":
        if ch["old_value"] == "number" and ch["new_value"] == "integer":
            v = args.get(p)
            return isinstance(v, float) and not v.is_integer()
        return p in args           # string -> integer: any string value fails
    return False


def compute_truth(calls: list, ledger: list) -> list:
    by_tool: dict = {}
    for ch in ledger:
        by_tool.setdefault(ch["tool"], []).append(ch)
    rows = []
    for c in calls:
        chs = by_tool.get(c["tool"], [])
        causes, first = [], ""
        for ch in chs:                                  # ledger is in release order
            if change_breaks(ch, c["args"]):
                causes.append(ch["change_id"])
                if not first:
                    first = ch["to_rev"]
        broken = bool(causes)
        mis_unit = mis_meaning = shifted = False
        if not broken:
            for ch in chs:
                if ch["change_type"] == "unit_changed" and ch["param"] in c["args"]:
                    mis_unit = True
                if ch["change_type"] == "meaning_changed" and ch["param"] in c["args"]:
                    mis_meaning = True
                if ch["change_type"] == "default_changed" and ch["param"] not in c["args"]:
                    shifted = True
        silent_ids = []
        if not broken:
            for ch in chs:
                if (ch["change_type"] == "unit_changed" and ch["param"] in c["args"]) or \
                   (ch["change_type"] == "meaning_changed" and ch["param"] in c["args"]) or \
                   (ch["change_type"] == "default_changed" and ch["param"] not in c["args"]):
                    silent_ids.append(ch["change_id"])
        rows.append({
            "call_id": c["call_id"], "true_broken": int(broken), "first_break_rev": first,
            "true_misread_unit": int(mis_unit), "true_misread_meaning": int(mis_meaning),
            "true_shifted_default": int(shifted),
            "cause_change_ids": ";".join(causes if broken else silent_ids),
        })
    return rows


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
def write_csv(path: Path, fields: list, rows: list) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    rng = random.Random(SEED)
    schemas, ledger = build_schemas_and_ledger()
    calls = generate_calls(rng, schemas)
    truth = compute_truth(calls, ledger)

    schema_rows = []
    for (tool, rev), (s, at) in sorted(schemas.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        schema_rows.append({"tool": tool, "rev": rev, "declared_version": s["version"],
                            "released_at": at,
                            "schema_json": json.dumps(s, separators=(",", ":"))})
    write_csv(OUT / "tool_schemas.csv",
              ["tool", "rev", "declared_version", "released_at", "schema_json"], schema_rows)

    ledger_fields = ["change_id", "tool", "from_rev", "to_rev", "released_at", "change_type",
                     "param", "old_value", "new_value", "kind", "declared_version_before",
                     "declared_version_after", "version_bumped", "true_class", "semantic_kind"]
    write_csv(OUT / "change_ledger.csv", ledger_fields, ledger)

    call_rows = [{"call_id": c["call_id"], "tool": c["tool"],
                  "called_at": c["called_at"].strftime("%Y-%m-%dT%H:%M:%S"),
                  "args_json": json.dumps(c["args"], separators=(",", ":"))} for c in calls]
    write_csv(OUT / "recorded_calls.csv", ["call_id", "tool", "called_at", "args_json"], call_rows)
    write_csv(OUT / "call_truth.csv",
              ["call_id", "true_broken", "first_break_rev", "true_misread_unit",
               "true_misread_meaning", "true_shifted_default", "cause_change_ids"], truth)

    n_broken = sum(r["true_broken"] for r in truth)
    n_unit = sum(r["true_misread_unit"] for r in truth)
    n_meaning = sum(r["true_misread_meaning"] for r in truth)
    n_shift = sum(r["true_shifted_default"] for r in truth)
    print(f"Wrote {len(schema_rows)} schema revisions for {len(TOOLS)} tools -> tool_schemas.csv")
    print(f"Wrote {len(ledger)} ledger changes -> change_ledger.csv")
    print(f"Wrote {len(call_rows)} recorded calls (all valid under v1) -> recorded_calls.csv")
    print(f"Truth: {n_broken} broken, {n_unit} unit-misread, {n_meaning} meaning-misread, "
          f"{n_shift} default-shifted -> call_truth.csv")


if __name__ == "__main__":
    main()
