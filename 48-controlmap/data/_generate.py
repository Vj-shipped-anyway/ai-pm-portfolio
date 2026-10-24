"""Generate the synthetic data for project 48 (controlmap): an obligation register, a control library,
a theme dictionary and the planted truth about which control serves which obligation.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth comes from a hidden
field written here (`serves_theme` in control_truth.csv) and from a status function in this file; the
rules in src/controlmap.py never read either. The two share two definitions by construction: scope
(a control covers an obligation fully when it runs in every use-case class the obligation applies to)
and freshness (evidence is fresh when it is no older than 1.5 times the control's test cycle).

Hard cases are planted on purpose:
  off_dictionary   serves a theme but is worded without any dictionary phrase (a miss for the rules)
  negated_true     serves a theme, but its text says "no exception to human review" (the negation rule drops it)
  negated_decoy    serves nothing and mentions a dictionary phrase only to deny it (a false alarm the rules avoid)
  wrong_sense      serves nothing but uses a dictionary phrase in another sense (a false link the rules cannot see)
  lookalike        serves nothing but shares ordinary words with obligations (a false link for a keyword sheet)

Run (from data/):  python3 _generate.py
Writes: obligations.csv, controls.csv, terms.csv, control_truth.csv, truth_pairs.csv, truth_status.csv,
        dataset.json, example_obligations.csv, example_controls.csv, example_terms.csv
"""
from __future__ import annotations

import csv
import datetime
import json
import random

SEED = 48
AS_OF = datetime.date(2026, 6, 30)
GRACE = 1.5
CLASSES = ["credit_decision", "fraud_scoring", "customer_chat", "doc_summary", "internal_copilot"]
LABELS = {"credit_decision": "credit decisions", "fraud_scoring": "fraud scoring", "customer_chat": "customer chat",
          "doc_summary": "document summaries", "internal_copilot": "the internal copilot"}
QUIET_THEMES = {"vendor model oversight"}   # the owning team stopped collecting evidence: every control is stale

THEMES = [
    dict(key="model inventory", source="AI policy", owner="Model Risk Management", n_ob=5,
         phrases=["model inventory", "inventory attestation"],
         stems=["Keep an inventory entry, with a named owner, for every AI system used in {uc}.",
                "Confirm each year that the inventory entries for {uc} are complete and still correct.",
                "Record a new AI system for {uc} in the inventory before it goes live."],
         ctl=[("Model inventory attestation", "Owners confirm each quarter that their entries in the model inventory are complete and current."),
              ("Inventory completeness sweep", "Second-line staff compare the model inventory against purchase orders and cloud accounts to find systems nobody listed."),
              ("Go-live gate", "A system cannot be released until its entry in the model inventory has an owner and a risk tier.")],
         off=("Live systems register", "Platform team keeps a list of every deployed AI system with its owner and tier, and checks it against deployments each month."),
         retired=[("Spreadsheet inventory check", "Annual check of the model inventory spreadsheet. Retired when the inventory moved to the platform.")]),
    dict(key="independent validation", source="Model risk standard", owner="Model Risk Management", n_ob=5,
         phrases=["independent validation", "validation team", "challenger model"],
         stems=["Have people who did not build the model validate it before it is used for {uc}.",
                "Re-validate the model used for {uc} after any material change.",
                "Document the validation of the model used for {uc} and its open findings."],
         ctl=[("Independent validation", "The validation team, separate from developers, tests each model before release and issues a written opinion."),
              ("Challenger comparison", "Validators build a simpler challenger model and compare its results with the production model on the same data."),
              ("Validation findings tracker", "Each finding is logged with an owner and a due date, and the validation team reports ageing to the risk committee.")],
         off=("Replication exercise", "Analysts outside the build team rebuild the headline results from raw data and reconcile any difference.")),
    dict(key="ongoing monitoring", source="Model risk standard", owner="Model Risk Management", n_ob=5,
         phrases=["performance monitoring", "drift dashboard", "model monitoring"],
         stems=["Watch the performance of the AI system used for {uc} after release and act on drift.",
                "Set alert thresholds for the system used for {uc} and review breaches.",
                "Report monitoring results for {uc} to the owner each month."],
         ctl=[("Performance monitoring", "Monthly performance monitoring compares live results with the levels set at validation and raises an alert on a breach."),
              ("Drift dashboard", "A drift dashboard tracks input and output distributions and notifies the model owner when they move beyond thresholds."),
              ("Monitoring escalation", "Breaches of model monitoring thresholds are escalated to the owner within five days and tracked to closure.")],
         off=("Weekly read of live answers", "Reviewers read a weekly sample of live answers and score them against a checklist.")),
    dict(key="human oversight", source="AI policy", owner="AI Platform Team", n_ob=5,
         phrases=["human review", "override log", "human in the loop"],
         stems=["Make sure a person can review, challenge and override the output of the system used for {uc}.",
                "Train the people who review output from the system used for {uc}.",
                "Record each case where a person overrode the system used for {uc}."],
         ctl=[("Review of declines", "A trained reviewer checks every automated decline before the customer is told, using the human review queue."),
              ("Override log", "Every override of an automated result is logged with the reviewer and the reason, and the log is sampled each quarter."),
              ("Reviewer training", "Reviewers complete a course on the limits of the system and pass a test before they join the human in the loop rota.")],
         off=("Second pair of eyes", "Anything the system flags as unusual goes to a named analyst who can reverse it before it takes effect.")),
    dict(key="change management", source="Model risk standard", owner="Technology Risk", n_ob=5,
         phrases=["change board", "release review", "change approval"],
         stems=["Approve changes to the system used for {uc} before they reach production.",
                "Keep a record of each change to the system used for {uc}, including who approved it.",
                "Test a change to the system used for {uc} against the validated version before release."],
         ctl=[("Weekly change board", "A change board meets weekly and approves or rejects each change request for production AI systems."),
              ("Release review", "Each release gets a release review that compares test results with the last validated version."),
              ("Change record audit", "Quarterly sample of change approval records to confirm each has the approver and test evidence attached.")],
         off=("Deployment freeze rule", "Production pipelines refuse any build that lacks a signed ticket from the system owner.")),
    dict(key="vendor model oversight", source="Third-party standard", owner="Vendor Management", n_ob=5,
         phrases=["vendor model assessment", "purchased model", "vendor attestation"],
         stems=["Assess a purchased AI model for {uc} before contract signature and each year after.",
                "Require the supplier of the model used for {uc} to notify us of material changes.",
                "Keep an exit plan for the supplier of the model used for {uc}."],
         ctl=[("Vendor model assessment", "Third-party risk staff run a vendor model assessment covering testing, data use and support before signature."),
              ("Supplier change notice", "Contracts require notice of any change to a purchased model, and the owner reviews each notice for impact."),
              ("Annual supplier statement", "Each year suppliers send a vendor attestation that covers testing, security and subcontractors.")]),
    dict(key="data quality", source="AI policy", owner="Data Office", n_ob=5,
         phrases=["data quality", "data lineage", "data reconciliation", "data use approval"],
         stems=["Check that the data used to build and test the system for {uc} is relevant and free of known errors.",
                "Keep track of where the data used for {uc} came from.",
                "Reconcile the data fed to the system for {uc} with the source each month."],
         ctl=[("Input file checks", "Automated data quality checks run on each training and scoring file and block files that fail."),
              ("Lineage map", "Data engineering keeps data lineage from source system to model input and reviews it twice a year."),
              ("Feed reconciliation", "Operations performs a data reconciliation between source totals and model input totals every month.")]),
    dict(key="user disclosure", source="Consumer protection procedure", owner="Compliance", n_ob=4,
         phrases=["ai disclosure", "user notice", "instructions for use"],
         stems=["Tell people when they are dealing with an AI system in {uc}.",
                "Give plain instructions on what the system used for {uc} can and cannot do.",
                "Keep the wording of AI notices for {uc} under review."],
         ctl=[("AI disclosure banner", "Customer-facing screens show an AI disclosure banner before the first answer."),
              ("Notice wording review", "Compliance reviews each user notice for reading level and accuracy before it is published."),
              ("Instructions for use", "Each system ships with instructions for use that state purpose, limits and how to reach a person.")]),
    dict(key="fairness testing", source="Consumer protection procedure", owner="Fair Lending Office", n_ob=5,
         phrases=["disparity testing", "proxy screening", "fairness review"],
         stems=["Test the system used for {uc} for different outcomes between groups of people.",
                "Screen the inputs of the system used for {uc} for proxies of protected traits.",
                "Act on the results of fairness tests for {uc} and record the decision."],
         ctl=[("Outcome gap testing", "Fair lending analysts run disparity testing on outcomes each half year and report gaps over the set limit."),
              ("Input screen", "Analysts run proxy screening on every input field against protected traits before the field is used."),
              ("Findings panel", "A fairness review panel reads test results and records whether to change, accept or retire the model.")],
         off=("Outcome gap memo", "A memo each half year compares approval rates across customer groups and sets out what was done about gaps.")),
    dict(key="incident response", source="AI policy", owner="Technology Risk", n_ob=4,
         phrases=["incident response plan", "incident playbook"],
         stems=["Have a written plan to respond to a failure or harmful output of the system used for {uc}.",
                "Practise the response plan for {uc} at least once a year.",
                "Report incidents involving the system used for {uc} to senior management."],
         retired=[("Incident playbook v1", "A playbook for model incidents, kept as the incident playbook until the incident process was rewritten. Retired.")]),
    dict(key="decision explanations", source="Consumer protection procedure", owner="Compliance", n_ob=4,
         phrases=["reason code", "decline reason"],
         stems=["Give the customer the specific reasons for an adverse decision made with {uc}.",
                "Check that the reasons given for {uc} match the factors the system used.",
                "Keep reason wording for {uc} in plain language."],
         retired=[("Reason code review", "Compliance checked each month that the reason code sent to customers matched the model's top factors. Retired."),
                  ("Decline reason wording", "Plain wording for each decline reason was reviewed twice a year. Retired when the letter process moved.")]),
    dict(key="model retirement", source="Model risk standard", owner="Technology Risk", n_ob=4, phrases=None,
         stems=["Retire the system used for {uc} in an orderly way and keep its records.",
                "Switch off access to a retired system for {uc} and confirm no calls remain.",
                "Archive the final validation file of a retired system for {uc}."],
         ctl=[("Decommission checklist", "A checklist covers access removal, record archive and notice to dependent teams when a system is shut down."),
              ("Retired system sweep", "Technology scans for calls to a switched-off system each month and reports any that remain.")]),
]

SPECIAL = [  # (kind, serves_theme, owner, name, description)
    ("negated_true", "human oversight", "AI Platform Team", "Exception handling",
     "There is no exception to human review for declined applications; staff cannot skip the queue."),
    ("negated_decoy", "", "Security Operations", "Network traffic watch",
     "Security operations watch network traffic for unusual volumes. This is not model monitoring and covers no AI system."),
    ("negated_decoy", "", "Records Management", "Call recording retention",
     "Retention of call recordings follows the legal schedule; it is not a change approval step and does not cover releases."),
    ("negated_decoy", "", "Branch Operations", "Branch cash handling",
     "Tellers follow cash limits. There is no human review of till counts beyond the daily tally."),
    ("wrong_sense", "", "Network Engineering", "Switch configuration watch",
     "Network engineers use a drift dashboard to see when switch settings move away from the approved build."),
    ("wrong_sense", "", "Treasury Operations", "Payment file checks",
     "Treasury operations run a data reconciliation between the payment file and the bank statement every day."),
    ("lookalike", "", "Technology Operations", "Production system patching",
     "Technology applies security patches to production systems and reports overdue items each month."),
    ("lookalike", "", "Infrastructure", "Server performance report",
     "Infrastructure reports server performance and capacity each month to the owner of each system."),
    ("lookalike", "", "Customer Care", "Customer complaint log",
     "Complaints about customer chat are logged with the customer, date and outcome, and reviewed by a manager each month."),
    ("lookalike", "", "Procurement", "Supplier invoice approval",
     "Procurement approves supplier invoices against signed contracts before payment."),
    ("orphan", "", "Facilities", "Data centre badge review", "Facilities reviews badge access to the data centre every quarter."),
    ("orphan", "", "Facilities", "Fire drill", "Each site runs a fire drill twice a year and files the attendance sheet."),
    ("orphan", "", "Branch Operations", "Branch opening hours audit", "Area managers confirm that posted opening hours match the staffing rota."),
    ("orphan", "", "Finance", "Travel expense policy check", "Finance samples travel claims against the expense policy."),
    ("orphan", "", "Facilities", "Printer fleet lease review", "Facilities reviews the printer lease terms before each renewal."),
    ("orphan", "", "Human Resources", "Food safety audit", "An outside firm audits the staff canteen once a year."),
]


def join_labels(classes):
    parts = [LABELS[c] for c in classes]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def pick(rng, k):
    """k distinct use-case classes, in the fixed class order."""
    chosen = set(rng.sample(CLASSES, k))
    return [c for c in CLASSES if c in chosen]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def truth_status(app, serving):
    """Generator's own status rule, written from the planted facts (ages and cycles are integers here)."""
    links = [c for c in serving if set(c["scope"]) & app]
    full = [c for c in links if app <= set(c["scope"])]
    if full:
        return "COVERED" if any(c["age"] is not None and c["age"] <= GRACE * c["cycle"] for c in full) else "STALE"
    return "PARTIAL" if links else "UNCOVERED"


def main():
    rng = random.Random(SEED)

    # ---- obligations
    obs = []
    for t in THEMES:
        seen = set()
        for i in range(t["n_ob"]):
            while True:
                k = rng.choice([1, 1, 2, 2, 3])
                classes = pick(rng, k)
                stem = i % len(t["stems"])
                if (stem, tuple(classes)) not in seen:
                    seen.add((stem, tuple(classes)))
                    break
            obs.append(dict(theme=t["key"], source=t["source"], classes=classes,
                            statement=t["stems"][stem].format(uc=join_labels(classes))))
    rng.shuffle(obs)
    for i, o in enumerate(obs, 1):
        o["id"] = "OB-%03d" % i

    # ---- controls
    ctls = []
    for t in THEMES:
        for n, d in t.get("ctl", []):
            ctls.append(dict(name=n, desc=d, owner=t["owner"], serves=t["key"], kind="dict" if t["phrases"] else "unlisted_theme", status="active"))
        if t.get("off"):
            ctls.append(dict(name=t["off"][0], desc=t["off"][1], owner=t["owner"], serves=t["key"], kind="off_dictionary", status="active"))
        for n, d in t.get("retired", []):
            ctls.append(dict(name=n, desc=d, owner=t["owner"], serves=t["key"], kind="retired", status="retired"))
    for kind, serves, owner, n, d in SPECIAL:
        ctls.append(dict(name=n, desc=d, owner=owner, serves=serves, kind=kind, status="active"))
    rng.shuffle(ctls)
    for i, c in enumerate(ctls, 1):
        c["id"] = "CT-%02d" % i
        k = rng.choice([1, 2, 2, 3, 3, 4, 5])
        c["scope"] = pick(rng, k)
        c["cycle"] = rng.choice([90, 180, 365])
        stale = c["serves"] in QUIET_THEMES or c["status"] == "retired" or rng.random() < 0.2
        c["age"] = int(c["cycle"] * (rng.uniform(1.6, 2.8) if stale else rng.uniform(0.1, 1.4)))
    serving_ids = sorted(c["id"] for c in ctls if c["status"] == "active" and c["serves"] and c["serves"] not in QUIET_THEMES)
    never_tested = set(rng.sample(serving_ids, 2))
    for c in ctls:
        if c["id"] in never_tested:
            c["age"] = None
        c["last"] = "" if c["age"] is None else (AS_OF - datetime.timedelta(days=c["age"])).isoformat()

    # ---- truth
    by_theme = {}
    for c in ctls:
        if c["status"] == "active" and c["serves"]:
            by_theme.setdefault(c["serves"], []).append(c)
    pairs, status = [], {}
    for o in obs:
        serving = by_theme.get(o["theme"], [])
        app = set(o["classes"])
        for c in serving:
            cov = "full" if app <= set(c["scope"]) else "partial" if app & set(c["scope"]) else "none"
            pairs.append((o["id"], c["id"], cov))
        status[o["id"]] = truth_status(app, serving)

    # ---- the hand-typed register column (the status quo): old answers, wrong rows, renumbered ids
    claim_rng = random.Random(SEED + 1)
    retired_by_theme = {}
    for c in ctls:
        if c["status"] == "retired":
            retired_by_theme.setdefault(c["serves"], []).append(c["id"])
    active_ids = sorted(c["id"] for c in ctls if c["status"] == "active")
    for o in obs:
        claimed = {c["id"] for c in by_theme.get(o["theme"], []) if claim_rng.random() < 0.6}
        if retired_by_theme.get(o["theme"]) and claim_rng.random() < 0.5:
            claimed.add(claim_rng.choice(retired_by_theme[o["theme"]]))
        if claim_rng.random() < 0.15:
            claimed.add(claim_rng.choice(active_ids))
        if claim_rng.random() < 0.08:
            claimed.add("CT-9%02d" % claim_rng.randint(0, 99))
        o["claimed"] = sorted(claimed)

    # ---- write
    obs.sort(key=lambda o: o["id"])
    ctls.sort(key=lambda c: c["id"])
    write_csv("obligations.csv", ["obligation_id", "source", "theme", "statement", "applies_to", "claimed_controls"],
              [(o["id"], o["source"], o["theme"], o["statement"], ";".join(o["classes"]), ";".join(o["claimed"])) for o in obs])
    write_csv("controls.csv", ["control_id", "name", "description", "owner", "scope", "test_cycle_days", "last_evidence_on", "status"],
              [(c["id"], c["name"], c["desc"], c["owner"], ";".join(c["scope"]), c["cycle"], c["last"], c["status"]) for c in ctls])
    write_csv("terms.csv", ["theme", "phrase"], [(t["key"], p) for t in THEMES if t["phrases"] for p in t["phrases"]])
    write_csv("control_truth.csv", ["control_id", "serves_theme", "kind"], [(c["id"], c["serves"], c["kind"]) for c in ctls])
    write_csv("truth_pairs.csv", ["obligation_id", "control_id", "coverage"], sorted(pairs))
    write_csv("truth_status.csv", ["obligation_id", "status"], [(o["id"], status[o["id"]]) for o in obs])
    with open("dataset.json", "w", encoding="utf-8") as fh:
        json.dump({"as_of": AS_OF.isoformat(), "classes": CLASSES, "grace": GRACE, "seed": SEED}, fh, indent=1, sort_keys=True)
        fh.write("\n")

    # ---- the small worked example behind `python3 controlmap.py --demo`
    write_csv("example_obligations.csv", ["obligation_id", "theme", "statement", "applies_to"], [
        ("EX-1", "model inventory", "Keep an inventory entry, with a named owner, for every AI system used in credit decisions.", "credit_decision"),
        ("EX-2", "ongoing monitoring", "Watch the performance of the AI system used for credit decisions and fraud scoring after release and act on drift.", "credit_decision;fraud_scoring"),
        ("EX-3", "human oversight", "Make sure a person can review, challenge and override the output of the system used for customer chat and the internal copilot.", "customer_chat;internal_copilot"),
        ("EX-4", "incident response", "Have a written plan to respond to a failure or harmful output of the system used for fraud scoring.", "fraud_scoring"),
        ("EX-5", "model retirement", "Retire the system used for document summaries in an orderly way and keep its records.", "doc_summary"),
        ("EX-6", "change management", "Approve changes to the system used for fraud scoring before they reach production.", "fraud_scoring")])
    write_csv("example_controls.csv", ["control_id", "name", "description", "owner", "scope", "test_cycle_days", "last_evidence_on", "status"], [
        ("CT-A1", "Model inventory attestation", "Owners confirm each quarter that their entries in the model inventory are complete and current.", "Model Risk Management", "credit_decision;customer_chat", 90, "2026-05-21", "active"),
        ("CT-B1", "Drift dashboard", "A drift dashboard tracks input and output distributions and notifies the model owner when they move beyond thresholds.", "Model Risk Management", "credit_decision;fraud_scoring", 90, "2025-09-03", "active"),
        ("CT-C1", "Chat answer review", "A trained reviewer checks flagged chat answers in the human review queue.", "AI Platform Team", "customer_chat", 180, "2026-06-10", "active"),
        ("CT-D1", "Call recording retention", "Retention of call recordings follows the legal schedule; it is not a change approval step.", "Records Management", "fraud_scoring", 365, "2026-03-01", "active"),
        ("CT-E1", "Data centre badge review", "Facilities reviews badge access to the data centre every quarter.", "Facilities", "credit_decision", 90, "2026-06-01", "active"),
        ("CT-F1", "Spreadsheet inventory check", "Annual check of the model inventory spreadsheet. Retired when the inventory moved to the platform.", "Model Risk Management", "credit_decision", 365, "2025-02-01", "retired")])
    write_csv("example_terms.csv", ["theme", "phrase"], [
        ("model inventory", "model inventory"), ("ongoing monitoring", "drift dashboard"), ("ongoing monitoring", "performance monitoring"),
        ("human oversight", "human review"), ("incident response", "incident playbook"), ("change management", "change approval")])


if __name__ == "__main__":
    main()
