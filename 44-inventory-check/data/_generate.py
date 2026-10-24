"""Write the synthetic data for project 44: an inventory of 100 generative and agentic systems, a gateway usage
export for them, and the planted truth about both.

Everything is seeded, so the files are byte-for-byte reproducible. The truth comes from the case each record was
built as, not from the checker in src/. Two kinds of case are hard on purpose. Hard negatives look wrong and are
not (a review exactly on its cadence, a model id that differs only in case, a pilot with no evaluation yet). Hard
misses are wrong and look fine (a placeholder the word list does not know, a review date refreshed in bulk, a
system that sends its traffic under another system's id).

Run (from data/):  python3 _generate.py
Writes:  as_of.txt, inventory.json, inventory_truth.csv, usage.csv, shadow_truth.csv,
         example_inventory.json, example_usage.csv
"""
import csv
import json
import random
from collections import namedtuple
from datetime import date, timedelta

SEED = 44
AS_OF = date(2026, 9, 30)
rng = random.Random(SEED)

CADENCE = {1: 365, 2: 270, 3: 180, 4: 90}

Arch = namedtuple("Arch", "title kind purpose data_class customer_facing tier tools permission approval")


def G(title, purpose, data_class, cf, tier):
    return Arch(title, "generative", purpose, data_class, cf, tier, None, None, None)


def A(title, purpose, data_class, cf, tier, tools, permission, approval):
    return Arch(title, "agentic", purpose, data_class, cf, tier, tools, permission, approval)


ARCH = [
    G("Customer FAQ chat assistant", "Answers product and fee questions from the approved help-centre text.", "internal", "yes", 2),
    G("Staff procedures assistant", "Answers staff questions about internal procedures from the policy library.", "internal", "no", 1),
    G("Meeting notes summarizer", "Turns meeting transcripts into minutes and action lists.", "internal", "no", 1),
    G("Complaint letter drafter", "Drafts reply letters to customer complaints for a handler to edit and send.", "confidential", "yes", 3),
    G("Contract clause extractor", "Pulls named clauses and dates out of vendor contracts for review.", "confidential", "no", 2),
    G("Call summary generator", "Writes a short summary and disposition note for each recorded service call.", "confidential", "no", 2),
    G("Developer code assistant", "Suggests code and tests inside the engineering editor.", "internal", "no", 1),
    G("Marketing copy drafter", "Drafts product marketing copy for compliance review before use.", "internal", "yes", 2),
    G("Credit memo drafting assistant", "Drafts sections of a credit memo from the analyst's inputs.", "confidential", "no", 3),
    G("Regulatory change summarizer", "Summarizes new regulatory publications for the compliance team.", "internal", "no", 2),
    G("Loan file question answering", "Answers questions about the documents in one loan file.", "restricted", "no", 3),
    G("Transaction explainer", "Explains a transaction line to the customer in plain words.", "restricted", "yes", 3),
    A("Dispute triage agent", "Reads a card dispute, classifies it and routes the case to the right queue.", "restricted", "no", 3,
      ["classify_dispute", "get_dispute", "route_case"], "read_write", "on_exception"),
    A("Card servicing agent", "Handles card block and replacement requests in chat.", "restricted", "yes", 4,
      ["block_card", "get_card", "send_notification"], "transact", "before_action"),
    A("KYC refresh agent", "Collects missing documents for a periodic customer review.", "restricted", "no", 3,
      ["fetch_customer_docs", "request_documents", "update_review_status"], "read_write", "before_action"),
    A("Collections outreach agent", "Plans and drafts reminder messages for accounts past due.", "confidential", "yes", 3,
      ["draft_message", "get_account", "schedule_call"], "read_write", "before_action"),
    A("IT service desk agent", "Searches known fixes and opens tickets for staff.", "internal", "no", 2,
      ["create_ticket", "search_tickets"], "read_write", "on_exception"),
    A("Reconciliation break agent", "Proposes matches for unreconciled items and posts approved adjustments.", "confidential", "no", 4,
      ["get_breaks", "post_adjustment", "propose_match"], "transact", "before_action"),
    A("Payment repair agent", "Proposes fixes for payments held in a repair queue.", "restricted", "no", 4,
      ["propose_fix", "read_payment", "release_payment"], "transact", "before_action"),
    A("Procurement intake agent", "Checks a purchase request against vendor and budget lists.", "internal", "no", 2,
      ["create_request", "search_vendors"], "read_write", "on_exception"),
    A("Research digest agent", "Collects public filings and news into a daily digest.", "public", "no", 1,
      ["fetch_filing", "search_news", "write_digest"], "read_only", "none"),
    A("Fraud alert triage agent", "Gathers history for an alert and sets its review status.", "restricted", "no", 3,
      ["get_alert", "get_history", "set_alert_status"], "read_write", "on_exception"),
    A("Onboarding checklist agent", "Tracks open items on a new-account application and asks for what is missing.", "confidential", "yes", 2,
      ["get_application", "request_info", "tick_item"], "read_write", "on_exception"),
    A("Treasury cash positioning agent", "Builds the morning cash position from bank balance feeds.", "confidential", "no", 3,
      ["get_balances", "write_position"], "read_write", "on_exception"),
]
UNITS = ["Retail Banking", "Payments", "Collections", "Treasury", "Fraud Operations", "Credit Operations",
         "Compliance", "Contact Centre", "Human Resources", "Technology"]
TOOL_NAMES = ["create_case", "get_customer", "post_note", "search_kb", "send_email", "update_record"]

# (older id, newer id, provider type). Every id is invented.
PAIRS = [("vendor-a-large-2026-03", "vendor-a-large-2026-08", "vendor_api"),
         ("vendor-a-small-2026-03", "vendor-a-small-2026-08", "vendor_api"),
         ("vendor-b-chat-2026-01", "vendor-b-chat-2026-07", "vendor_api"),
         ("vendor-c-reason-2026-05", "vendor-c-reason-2026-09", "vendor_api"),
         ("selfhost-open-8b-v3", "selfhost-open-8b-v4", "self_hosted"),
         ("selfhost-open-70b-v2", "selfhost-open-70b-v3", "self_hosted")]
MODELS = [(m, p) for old, new, p in PAIRS for m in (old, new)]

KNOWN_PLACEHOLDERS = ["TBD", "N/A", "unknown", "None", "TBA", "tbd"]
NOVEL_PLACEHOLDERS = ["to be confirmed with the team", "see wiki", "same as above", "pending assignment"]
SENTENCES_WITH_PLACEHOLDER_WORDS = ["Flags unknown merchant names on disputed card items.",
                                    "Routes a ticket to a person when the category is n/a or none of the listed ones.",
                                    "Lists answers marked none of the above for a person to read."]
BLANKABLE = ["name", "kind", "status", "business_owner", "technical_owner", "risk_tier", "purpose", "provider_type",
             "model_id", "data_class", "customer_facing", "last_reviewed"]

# (case kind, count). The first eleven are defects the checker should find, the next two are defects it should
# miss, the rest are clean records and the hard ones among them are the hard negatives. The last hard one,
# seasonal_quiet, is a false alarm the rules cannot avoid, and it stays in on purpose.
QUOTA = [("missing_required", 6), ("invalid_value", 5), ("placeholder_known", 4), ("agent_gap", 5), ("evidence_gap", 6),
         ("misclassified_kind", 3), ("review_overdue", 6), ("evaluation_overdue", 4), ("model_changed", 5),
         ("retired_running", 3), ("listed_no_traffic", 4),
         ("placeholder_novel", 3), ("rubber_stamp", 3),
         ("boundary_review_age", 3), ("boundary_eval_age", 2), ("case_only_model_id", 3), ("model_migrated_recorded", 4),
         ("pre_production_no_evidence", 4), ("retired_old_traffic", 4), ("idle_boundary", 2),
         ("placeholder_in_sentence", 3), ("seasonal_quiet", 2), ("clean", 16)]
DEFECTIVE = {k for k, _ in QUOTA[:13]}

VISIBLE_SHADOWS = [("scratch-notes-bot", "vendor-a-small-2026-03"), ("ops-summarizer-test", "selfhost-open-8b-v3"),
                   ("team-sandbox-agent", "vendor-c-reason-2026-05"), ("adhoc-translator", "vendor-b-chat-2026-01")]
HIDDEN_SHADOWS = ["finance-forecast-notebook", "hr-faq-prototype"]


def iso(d):
    return d.isoformat()


def days_ago(n):
    return AS_OF - timedelta(days=n)


def row(sid, model, first_age, last_age, calls):
    return {"system_id": sid, "model_id": model, "first_seen": days_ago(first_age), "last_seen": days_ago(last_age), "calls": calls}


def clean_rows(sid, status, model):
    if status == "production":
        last = rng.randint(0, 12)
        return [row(sid, model, last + rng.randint(40, 400), last, rng.randint(2000, 120000))]
    if status == "pilot":
        last = rng.randint(0, 20)
        return [row(sid, model, last + rng.randint(10, 120), last, rng.randint(100, 8000))]
    if status == "development" and rng.random() < 0.5:
        last = rng.randint(0, 30)
        return [row(sid, model, last + rng.randint(1, 60), last, rng.randint(5, 900))]
    return []


def clean_record(sid, a, unit, status, model, provider):
    tier = a.tier
    rec = {"system_id": sid, "name": f"{a.title} - {unit}", "kind": a.kind, "status": status,
           "business_owner": f"OWN-{rng.randint(1, 24):02d}", "technical_owner": f"TECH-{rng.randint(1, 16):02d}",
           "risk_tier": tier, "purpose": f"{a.purpose} Used by {unit}.", "provider_type": provider, "model_id": model,
           "data_class": a.data_class, "customer_facing": a.customer_facing,
           "last_reviewed": iso(days_ago(rng.randint(5, CADENCE[tier])))}
    if a.kind == "agentic":
        rec.update(tools=list(a.tools), permission_scope=a.permission, human_approval=a.approval)
    if tier >= 2 and (status == "production" or rng.random() < 0.5):
        rec["evaluation_ref"] = f"EV-{rng.randint(1000, 9999)}"
        rec["last_evaluated"] = iso(days_ago(rng.randint(10, CADENCE[tier])))
    if status == "production":
        if tier >= 3:
            rec["independent_review_date"] = iso(days_ago(rng.randint(20, 400)))
        if tier == 4:
            rec["fallback_plan"] = "yes"
    return rec


def make_case(sid, case, names):
    """Build one record, its usage rows and a one-line description of what was planted."""
    pool, sub = ARCH, None
    if case == "agent_gap":
        pool = [a for a in ARCH if a.kind == "agentic"]
    elif case == "misclassified_kind":
        pool = [a for a in ARCH if a.kind == "generative"]
    elif case == "evidence_gap":
        sub = rng.choice(["evaluation", "independent_review", "fallback"])
        pool = [a for a in ARCH if a.tier >= {"evaluation": 2, "independent_review": 3, "fallback": 4}[sub]]
    elif case in ("evaluation_overdue", "boundary_eval_age"):
        pool = [a for a in ARCH if a.tier >= 2]
    elif case == "pre_production_no_evidence":
        pool = [a for a in ARCH if a.tier >= 3]
    a = rng.choice(pool)
    while True:
        unit = rng.choice(UNITS)
        if f"{a.title} - {unit}" not in names:
            names.add(f"{a.title} - {unit}")
            break
    if case in ("evidence_gap", "evaluation_overdue", "boundary_eval_age", "listed_no_traffic", "idle_boundary",
                "model_migrated_recorded", "seasonal_quiet"):
        status = "production"
    elif case in ("retired_running", "retired_old_traffic"):
        status = "retired"
    elif case == "pre_production_no_evidence":
        status = rng.choice(["pilot", "development"])
    elif case in ("model_changed", "case_only_model_id"):
        status = rng.choice(["production", "pilot"])
    else:
        status = rng.choice(["production"] * 6 + ["pilot"] * 2 + ["development"] * 2)
    pair = rng.choice(PAIRS)
    if case == "model_changed":
        model, provider = pair[0], pair[2]
    elif case == "model_migrated_recorded":
        model, provider = pair[1], pair[2]
    else:
        model, provider = rng.choice(MODELS)
    rec = clean_record(sid, a, unit, status, model, provider)
    rows = clean_rows(sid, status, model)
    tier = a.tier
    detail = ""

    if case == "missing_required":
        f, how = rng.choice(BLANKABLE), rng.choice(["absent", "empty", "spaces"])
        if how == "absent":
            del rec[f]
        else:
            rec[f] = "" if how == "empty" else "  "
        detail = f"{f} {how}"
    elif case == "invalid_value":
        sub = rng.choice(["tier", "date_format", "future_date", "enum_case", "enum_unknown"])
        if sub == "tier":
            rec["risk_tier"] = rng.choice([0, 5, "high"])
        elif sub == "date_format":
            rec["last_reviewed"] = rng.choice(["31/03/2026", "2026-13-02", "26-09-2026"])
        elif sub == "future_date":
            rec["last_reviewed"] = iso(AS_OF + timedelta(days=rng.randint(5, 90)))
        elif sub == "enum_case":
            rec["data_class"] = rec["data_class"].capitalize()
        else:
            rec["status"] = "live"
        detail = f"invalid {sub}"
    elif case == "placeholder_known":
        f = rng.choice(["business_owner", "technical_owner", "purpose", "model_id"])
        rec[f] = rng.choice(KNOWN_PLACEHOLDERS)
        detail = f"{f} set to a listed placeholder"
    elif case == "placeholder_novel":
        f = rng.choice(["business_owner", "technical_owner", "purpose"])
        rec[f] = rng.choice(NOVEL_PLACEHOLDERS)
        detail = f"{f} set to a placeholder the word list does not hold"
    elif case == "agent_gap":
        gone = sorted(rng.sample(["tools", "permission_scope", "human_approval"], rng.randint(1, 3)))
        for f in gone:
            if f == "tools" and rng.random() < 0.5:
                rec[f] = []
            else:
                del rec[f]
        detail = ", ".join(gone) + " missing on an agentic record"
    elif case == "misclassified_kind":
        rec["tools"] = sorted(rng.sample(TOOL_NAMES, 2))
        detail = "generative record lists tools"
    elif case == "evidence_gap":
        if sub == "evaluation":
            gone = rng.choice([["evaluation_ref"], ["last_evaluated"], ["evaluation_ref", "last_evaluated"]])
            for f in gone:
                del rec[f]
            detail = ", ".join(gone) + f" missing at tier {tier}"
        elif sub == "independent_review":
            del rec["independent_review_date"]
            detail = f"independent_review_date missing at tier {tier}"
        elif rng.random() < 0.5:
            del rec["fallback_plan"]
            detail = "fallback_plan missing at tier 4"
        else:
            rec["fallback_plan"] = "no"
            detail = "fallback_plan is no at tier 4"
    elif case == "review_overdue":
        age = CADENCE[tier] + rng.randint(10, 200)
        rec["last_reviewed"] = iso(days_ago(age))
        detail = f"tier {tier} cadence {CADENCE[tier]}; reviewed {age} days ago"
    elif case == "rubber_stamp":
        age = CADENCE[tier] + rng.randint(60, 300)
        rec["last_reviewed"] = iso(days_ago(4))
        detail = f"date refreshed in bulk on {iso(days_ago(4))}; last real review {iso(days_ago(age))}, tier {tier} cadence {CADENCE[tier]}"
    elif case == "evaluation_overdue":
        age = CADENCE[tier] + rng.randint(10, 200)
        rec["last_evaluated"] = iso(days_ago(age))
        detail = f"tier {tier} cadence {CADENCE[tier]}; evaluated {age} days ago"
    elif case in ("model_changed", "model_migrated_recorded"):
        old_last = rng.randint(40, 120)
        new_last = rng.randint(0, 10)
        rows = [row(sid, pair[0], old_last + rng.randint(30, 300), old_last, rng.randint(2000, 90000)),
                row(sid, pair[1], old_last - rng.randint(1, 20), new_last, rng.randint(2000, 90000))]
        detail = (f"traffic moved from {pair[0]} to {pair[1]}; the record still says {pair[0]}" if case == "model_changed"
                  else f"traffic moved from {pair[0]} to {pair[1]}; the record says {pair[1]}")
    elif case == "retired_running":
        last = rng.randint(0, 30)
        rows = [row(sid, model, last + rng.randint(30, 300), last, rng.randint(200, 20000))]
        detail = f"retired, last traffic {last} days ago"
    elif case == "retired_old_traffic":
        last = rng.choice([31, rng.randint(32, 300)])
        rows = [row(sid, model, last + rng.randint(30, 300), last, rng.randint(200, 20000))]
        rec["last_reviewed"] = iso(days_ago(CADENCE[tier] + rng.randint(100, 300)))
        detail = f"retired, last traffic {last} days ago, old review date"
    elif case == "listed_no_traffic":
        if rng.random() < 0.5:
            rows = []
            detail = "production, no usage rows"
        else:
            last = rng.randint(91, 300)
            rows = [row(sid, model, last + rng.randint(30, 300), last, rng.randint(2000, 90000))]
            detail = f"production, last traffic {last} days ago"
    elif case == "idle_boundary":
        rows = [row(sid, model, 90 + rng.randint(30, 300), 90, rng.randint(2000, 90000))]
        detail = "production, last traffic exactly 90 days ago"
    elif case == "seasonal_quiet":
        last = rng.randint(100, 200)
        rec["purpose"] = f"Runs once a quarter. {a.purpose}"
        rows = [row(sid, model, last + rng.randint(30, 300), last, rng.randint(2000, 90000))]
        detail = f"production process that runs once a quarter, last traffic {last} days ago"
    elif case == "boundary_review_age":
        rec["last_reviewed"] = iso(days_ago(CADENCE[tier]))
        detail = f"reviewed exactly {CADENCE[tier]} days ago, the tier {tier} cadence"
    elif case == "boundary_eval_age":
        rec["last_evaluated"] = iso(days_ago(CADENCE[tier]))
        detail = f"evaluated exactly {CADENCE[tier]} days ago, the tier {tier} cadence"
    elif case == "case_only_model_id":
        if rng.random() < 0.5:
            rows[0]["model_id"] = rows[0]["model_id"].upper()
            detail = "usage writes the model id in upper case"
        else:
            rec["model_id"] = rec["model_id"] + " "
            detail = "record has a trailing space in the model id"
    elif case == "pre_production_no_evidence":
        for f in ("evaluation_ref", "last_evaluated"):
            rec.pop(f, None)
        detail = f"{status} at tier {tier} with no evaluation yet"
    elif case == "placeholder_in_sentence":
        rec["purpose"] = rng.choice(SENTENCES_WITH_PLACEHOLDER_WORDS)
        detail = "purpose is a sentence that contains a placeholder word"
    return rec, rows, detail


def build():
    kinds = [k for k, n in QUOTA for _ in range(n)]
    rng.shuffle(kinds)
    records, usage, truth, names = [], [], [], set()
    for i, case in enumerate(kinds, 1):
        sid = f"AI-{i:03d}"
        rec, rows, detail = make_case(sid, case, names)
        records.append(rec)
        usage.extend(rows)
        truth.append((sid, case, "defective" if case in DEFECTIVE else "clean", detail))
    # Systems that call a model with no inventory record, one with no system id, and two that borrow a listed id.
    shadows = []
    for name, model in VISIBLE_SHADOWS:
        last = rng.randint(0, 20)
        calls = rng.randint(300, 20000)
        usage.append(row(name, model, last + rng.randint(30, 150), last, calls))
        shadows.append((name, "unregistered_visible", name, calls))
    calls = rng.randint(3000, 9000)
    usage.append(row("", "vendor-b-chat-2026-01", 45, 1, calls))
    shadows.append(("untagged-batch-job", "untagged", "", calls))
    plain = [r["system_id"] for r, t in zip(records, truth) if t[1] == "clean" and r["status"] == "production"]
    for name, sid in zip(HIDDEN_SHADOWS, rng.sample(plain, 2)):
        extra = rng.randint(2000, 15000)
        target = [u for u in usage if u["system_id"] == sid][0]
        target["calls"] += extra
        shadows.append((name, "hidden_behind_registered", sid, extra))
    usage.sort(key=lambda u: (u["system_id"], u["model_id"], u["first_seen"]))
    return records, usage, truth, shadows


EXAMPLE_INVENTORY = [
    {"system_id": "AI-901", "name": "Customer FAQ chat assistant - Retail Banking", "kind": "generative", "status": "production",
     "business_owner": "OWN-03", "technical_owner": "TECH-05", "risk_tier": 2,
     "purpose": "Answers product and fee questions from the approved help-centre text.", "provider_type": "vendor_api",
     "model_id": "vendor-a-large-2026-03", "data_class": "internal", "customer_facing": "yes", "last_reviewed": "2026-08-20",
     "evaluation_ref": "EV-2041", "last_evaluated": "2026-07-15"},
    {"system_id": "AI-902", "name": "Card servicing agent - Contact Centre", "kind": "agentic", "status": "production",
     "business_owner": "OWN-11", "technical_owner": "TECH-02", "risk_tier": 4,
     "purpose": "Handles card block and replacement requests in chat.", "provider_type": "vendor_api",
     "model_id": "vendor-b-chat-2026-07", "data_class": "restricted", "customer_facing": "yes", "last_reviewed": "2026-09-01",
     "permission_scope": "transact", "human_approval": "before_action",
     "evaluation_ref": "EV-2077", "last_evaluated": "2026-08-30", "independent_review_date": "2026-07-02", "fallback_plan": "yes"},
    {"system_id": "AI-903", "name": "Credit memo drafting assistant - Credit Operations", "kind": "generative", "status": "production",
     "business_owner": "OWN-07", "technical_owner": "TECH-09", "risk_tier": 3,
     "purpose": "Drafts sections of a credit memo from the analyst's inputs.", "provider_type": "self_hosted",
     "model_id": "selfhost-open-70b-v3", "data_class": "confidential", "customer_facing": "no", "last_reviewed": "2025-11-02",
     "evaluation_ref": "EV-1988", "last_evaluated": "2026-06-18", "independent_review_date": "2026-03-12"},
    {"system_id": "AI-904", "name": "Call summary generator - Contact Centre", "kind": "generative", "status": "production",
     "business_owner": "OWN-11", "technical_owner": "TECH-02", "risk_tier": 2,
     "purpose": "Writes a short summary and disposition note for each recorded service call.", "provider_type": "vendor_api",
     "model_id": "vendor-a-small-2026-03", "data_class": "confidential", "customer_facing": "no", "last_reviewed": "2026-07-28",
     "evaluation_ref": "EV-2012", "last_evaluated": "2026-07-10"},
    {"system_id": "AI-905", "name": "IT service desk agent - Technology", "kind": "agentic", "status": "pilot",
     "business_owner": "OWN-19", "technical_owner": "TBD", "risk_tier": 2,
     "purpose": "Searches known fixes and opens tickets for staff.", "provider_type": "self_hosted",
     "model_id": "selfhost-open-8b-v4", "data_class": "internal", "customer_facing": "no", "last_reviewed": "2026-09-10",
     "tools": ["create_ticket", "search_tickets"], "permission_scope": "read_write", "human_approval": "on_exception"},
    {"system_id": "AI-906", "name": "Research digest agent - Treasury", "kind": "agentic", "status": "pilot",
     "business_owner": "OWN-02", "technical_owner": "TECH-14", "risk_tier": 1,
     "purpose": "Collects public filings and news into a daily digest.", "provider_type": "vendor_api",
     "model_id": "vendor-c-reason-2026-09", "data_class": "public", "customer_facing": "no", "last_reviewed": "2026-09-05",
     "tools": ["fetch_filing", "search_news", "write_digest"], "permission_scope": "read_only", "human_approval": "none"},
]
EXAMPLE_USAGE = [
    ("AI-901", "vendor-a-large-2026-03", "2026-02-11", "2026-09-29", 48210),
    ("AI-902", "vendor-b-chat-2026-07", "2026-08-01", "2026-09-30", 23877),
    ("AI-903", "selfhost-open-70b-v3", "2026-04-19", "2026-09-28", 3302),
    ("AI-904", "vendor-a-small-2026-03", "2026-03-02", "2026-07-30", 6120),
    ("AI-904", "vendor-a-small-2026-08", "2026-08-02", "2026-09-27", 4417),
    ("AI-905", "selfhost-open-8b-v4", "2026-08-15", "2026-09-26", 912),
    ("AI-906", "vendor-c-reason-2026-09", "2026-09-06", "2026-09-29", 388),
    ("scratch-notes-bot", "vendor-a-small-2026-03", "2026-07-14", "2026-09-28", 412),
]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    records, usage, truth, shadows = build()
    with open("as_of.txt", "w", encoding="utf-8") as f:
        f.write(iso(AS_OF) + "\n")
    with open("inventory.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=1, sort_keys=True)
        f.write("\n")
    write_csv("inventory_truth.csv", ["system_id", "case_kind", "truth_class", "detail"], truth)
    write_csv("usage.csv", ["system_id", "model_id", "first_seen", "last_seen", "calls"],
              [(u["system_id"], u["model_id"], iso(u["first_seen"]), iso(u["last_seen"]), u["calls"]) for u in usage])
    write_csv("shadow_truth.csv", ["shadow_name", "shadow_kind", "tagged_as", "calls"], shadows)
    with open("example_inventory.json", "w", encoding="utf-8") as f:
        json.dump(EXAMPLE_INVENTORY, f, indent=1, sort_keys=True)
        f.write("\n")
    write_csv("example_usage.csv", ["system_id", "model_id", "first_seen", "last_seen", "calls"], EXAMPLE_USAGE)
    print(f"wrote {len(records)} records, {len(usage)} usage rows and {len(shadows)} shadow systems")


if __name__ == "__main__":
    main()
