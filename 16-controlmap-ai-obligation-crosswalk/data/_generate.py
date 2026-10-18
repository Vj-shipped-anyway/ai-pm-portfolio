"""Generates the ControlMap synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes four CSVs next to this file, prints a design summary)

What it builds
  obligations.csv  48 AI-related obligations, 12 per framework (EU AI Act, model risk guidance
                   SR 26-2, NIST AI RMF, ECOA / Regulation B). Each statement is a paraphrase
                   written for this exercise, not the text of the rule.
  controls.csv     60 controls of a modeled bank, with owner, test cycle in days, scope (the
                   use-case classes the control runs for) and status.
  evidence.csv     Evidence items per control, each with a collection date. AS_OF is a constant.
  truth_map.csv    The ground truth: which control meets which obligation, fully or partially.

The truth is known because the data is synthetic: the generator decides which control meets which
obligation, so it can score any crosswalk method. Nothing here comes from a real bank, control
library, vendor, regulator file or model. Every owner, team and reviewer is an invented code.

How the truth is decided
  * Each control is written with a hidden list of the themes it serves. A control that serves a
    theme meets every obligation with that theme.
  * Coverage is "full" when the control's scope includes every use-case class the obligation
    applies to, and "partial" otherwise (a scope mismatch). Coverage is judged one control at a
    time. The design guard at the bottom checks that no obligation is covered only by two partial
    controls that together span its classes.
  * Retired controls and the orphan controls meet nothing.
  * Evidence is stale when its latest item is older than STALE_FACTOR times the control's test
    cycle, measured at AS_OF. Each control is given a "fate" (fresh, late, stale, none) and the
    seed only picks the exact dates, reviewers and evidence types.
The wording of the controls is written by hand. Some controls use the same words as the
obligation, some use different words for the same idea (synonyms), two use wording that the
synonym dictionary in src/step_04 does not contain, and some are lookalikes that meet nothing.
"""

from __future__ import annotations

import csv
import hashlib
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261018
AS_OF = date(2026, 9, 30)      # keep in sync with src/step_01_status_quo.py
STALE_FACTOR = 1.5
OUT = Path(__file__).parent

CD, CC, IC, FS = "credit_decision", "customer_chat", "internal_copilot", "fraud_scoring"
CLASSES = [CD, CC, IC, FS]

EU = "EU AI Act"
SR = "Model risk guidance (SR 26-2)"
NIST = "NIST AI RMF"
ECOA = "ECOA / Regulation B"


def sc(*classes: str) -> str:
    """Canonical scope string: 'all' or semicolon-separated classes in a fixed order."""
    s = [c for c in CLASSES if c in classes]
    return "all" if len(s) == len(CLASSES) else ";".join(s)


ALL = sc(*CLASSES)

# ---------------------------------------------------------------------------
# Obligations (paraphrase written for this exercise, not the text of the rule).
# applies_to is how the modeled bank scoped each one, not a reading of any law.
# ---------------------------------------------------------------------------
OBLIGATIONS = [
    # EU AI Act
    (EU, "risk management", "Keep a written risk process for each high-risk AI system and update it as the system changes.", sc(CD, FS)),
    (EU, "data governance", "Check that data used to build and test the system is relevant, representative and free of known errors.", sc(CD, FS)),
    (EU, "technical documentation", "Prepare documents that describe the system's design, purpose and limits before it goes live.", sc(CD)),
    (EU, "record-keeping", "Let the system log events automatically so its operation can be traced afterwards.", sc(CD, CC)),
    (EU, "transparency to users", "Tell people when they are dealing with an AI system and give instructions for use.", sc(CC, IC)),
    (EU, "human oversight", "Design the system so a trained person can oversee it, intervene and stop it.", sc(CD)),
    (EU, "accuracy and resilience", "State the expected accuracy and keep the system resistant to errors and attempts to manipulate it.", sc(CD, FS)),
    (EU, "external registration", "Register each high-risk system in the public database and keep the entry current.", sc(CD)),
    (EU, "independent validation", "Have someone other than its builders assess the system before first use and again after a substantial change.", sc(CD)),
    (EU, "ongoing monitoring", "Collect and review data on the system's performance after it is in use and act on what it shows.", ALL),
    (EU, "governance and policy", "Run a quality management system with written policies, named roles and set procedures.", ALL),
    (EU, "vendor model oversight", "Obtain the provider's instructions and documentation and hold the provider to them when you deploy its system.", ALL),
    # Model risk guidance (SR 26-2)
    (SR, "model inventory", "Keep a complete list of models in use, with purpose, owner and status.", ALL),
    (SR, "independent validation", "Have staff independent of development validate a model before use and on a regular cycle.", sc(CD, FS)),
    (SR, "ongoing monitoring", "Track model performance in use against set thresholds and escalate breaches.", sc(CD, FS)),
    (SR, "governance and policy", "Have senior management approve a model risk policy that assigns roles and limits.", ALL),
    (SR, "technical documentation", "Document model design, assumptions and limits so an outside reader can follow them.", sc(CD, FS)),
    (SR, "vendor model oversight", "Apply the same validation and monitoring to vendor models as to models built in-house.", ALL),
    (SR, "risk management", "Identify and measure model risk and keep it inside a stated appetite.", ALL),
    (SR, "data governance", "Assess the quality and fit of the data that feeds a model.", sc(CD, FS)),
    (SR, "accuracy and resilience", "Compare model outputs with actual outcomes and investigate gaps.", sc(CD, FS)),
    (SR, "human oversight", "Make sure users of model output can challenge it and override it where warranted.", sc(IC)),
    (SR, "record-keeping", "Keep a record of each model's decisions and changes so they can be reviewed later.", ALL),
    (SR, "change management", "Review changes to models and their uses before they go into production.", ALL),
    # NIST AI RMF
    (NIST, "governance and policy", "Set policies, roles and accountability for managing AI risk across the organization.", ALL),
    (NIST, "model inventory", "Maintain an inventory of AI systems, including those supplied by third parties.", ALL),
    (NIST, "vendor model oversight", "Manage risks that come from third-party AI components and data.", ALL),
    (NIST, "map function", "Record each system's context, intended purpose and the people it may affect.", ALL),
    (NIST, "measure function", "Select metrics and test the system for the risks identified.", ALL),
    (NIST, "manage function", "Prepare a plan for AI incidents, name who responds and tell affected parties when one happens.", ALL),
    (NIST, "human oversight", "Define the roles people play in overseeing AI output and when they step in.", sc(CD, CC, IC)),
    (NIST, "transparency to users", "Explain system outputs and limits to the people who use or are affected by them.", sc(CD, CC, IC)),
    (NIST, "accuracy and resilience", "Evaluate whether the system is valid, reliable, secure and able to recover from failure.", ALL),
    (NIST, "ongoing monitoring", "Monitor deployed AI systems for changes in behavior and for new risks.", ALL),
    (NIST, "independent validation", "Involve assessors who did not build the system when evaluating it.", sc(CD, FS)),
    (NIST, "data governance", "Understand the origin, quality and suitability of the data the system uses.", ALL),
    # ECOA / Regulation B
    (ECOA, "specific adverse-action reasons", "Tell a declined applicant the specific principal reasons for the decision.", sc(CD)),
    (ECOA, "specific adverse-action reasons", "Make sure the reasons given are the factors the scoring model actually used.", sc(CD)),
    (ECOA, "timely notice of action taken", "Notify the applicant of the decision within the period the bank has set.", sc(CD)),
    (ECOA, "timely notice of action taken", "Send a notice for incomplete or countered applications on the same clock.", sc(CD)),
    (ECOA, "record-keeping", "Keep application and decision records for the period the bank has set.", sc(CD)),
    (ECOA, "transparency to users", "Give applicants the standard notice of their rights with each adverse decision.", sc(CD)),
    (ECOA, "prohibited-basis inputs", "Keep prohibited-basis information out of model inputs and test for proxies.", sc(CD)),
    (ECOA, "governance and policy", "Maintain a fair lending compliance program with named owners.", sc(CD)),
    (ECOA, "ongoing monitoring", "Watch decision outcomes and reason patterns for unexplained differences between groups.", sc(CD)),
    (ECOA, "vendor model oversight", "Check that a purchased scoring model can produce accurate reasons.", sc(CD)),
    (ECOA, "technical documentation", "Document how the model's reason codes are derived from its inputs.", sc(CD)),
    (ECOA, "independent validation", "Have the reason-code logic tested by someone who did not build it.", sc(CD)),
]

# ---------------------------------------------------------------------------
# Controls. serves = hidden themes the control truly meets (empty for orphans).
# fate: F fresh (latest evidence inside one test cycle), L late (inside 1.5 cycles, so still
# fresh by the rule), S stale (outside 1.5 cycles), N no evidence on file.
# kind is a design label for the generator summary only; it is not written to controls.csv.
# ---------------------------------------------------------------------------
AIGO, MRM, CRA, DOF, FLO = "AI Governance Office", "Model Risk Management", "Credit Risk Analytics", "Data Office", "Fair Lending Office"
TOPS, CUSO, VMGT, CTEST, INFOSEC = "Technology Operations", "Customer Operations", "Vendor Management", "Compliance Testing", "Information Security"
AIPT, FRDO, RECM, FINC, BRNO, HRO = "AI Platform Team", "Fraud Operations", "Records Management", "Finance Operations", "Branch Operations", "People Operations"


def C(name, desc, owner, freq, scope, serves, fate, kind, status="active"):
    return {"name": name, "desc": desc, "owner": owner, "freq": freq, "scope": scope,
            "serves": serves, "fate": fate, "kind": kind, "status": status}


CONTROL_SPECS = [
    # risk management
    C("AI risk register", "Register of AI risks with an owner, severity rating and review date for every entry.", AIGO, 90, ALL, ["risk management"], "F", "words"),
    C("Model risk appetite review", "Senior risk committee reviews each year whether model risk stays inside the stated appetite limits.", MRM, 365, ALL, ["risk management", "governance and policy"], "F", "words"),
    C("AI risk assessment at intake", "Risk team scores each new AI proposal for severity and likelihood before build starts.", AIGO, 180, ALL, ["risk management"], "F", "words"),
    C("Model risk rating review", "Model risk team assigns a rating to each model and sets how often it is reviewed.", MRM, 180, ALL, ["risk management"], "L", "words"),
    # data governance
    C("Training data quality checks", "Automated checks for gaps, duplicates and known errors in the data used to build and test models.", DOF, 30, sc(CD, FS), ["data governance"], "F", "words"),
    C("Source lineage catalog", "Catalog showing the provenance of every data source, who approved its use and what changed since.", DOF, 90, ALL, ["data governance"], "S", "synonym"),
    C("Input data reconciliation", "Monthly reconciliation of model input tables to the source ledgers, with differences logged.", DOF, 30, sc(CD, FS), ["data governance"], "F", "synonym"),
    C("Customer data use approval", "Approval board decides whether a new use of customer data is allowed and records the reason.", DOF, 90, sc(CC, IC), ["data governance"], "F", "synonym"),
    # technical documentation
    C("Model documentation standard", "Template and review gate that requires design notes, assumptions and known limits before a model is approved.", MRM, 180, ALL, ["technical documentation"], "F", "words"),
    C("Reason-code derivation memo", "Memo signed by the model owner showing how each reason code follows from the scorecard inputs.", FLO, 180, sc(CD), ["technical documentation", "specific adverse-action reasons"], "L", "words"),
    C("Documentation completeness sampling", "Second-line sample of model files checks that the required design notes are present and current.", MRM, 365, ALL, ["technical documentation"], "F", "words"),
    C("Prompt register", "Versioned record of the instructions given to each chatbot or copilot, with the approver and the date.", AIPT, 90, sc(CC, IC), ["technical documentation"], "F", "synonym"),
    # record-keeping
    C("Decision log retention", "Immutable log of each automated decision with its inputs, output and model version, kept for the retention period.", TOPS, 90, sc(CD, FS), ["record-keeping"], "F", "words"),
    C("Copilot prompt log", "Prompts and answers from the internal copilot are stored with user and time for later checks.", TOPS, 90, sc(IC), ["record-keeping"], "F", "synonym"),
    C("Fraud case notes", "Analysts keep a note of why each fraud alert was closed or escalated, stored with the case.", FRDO, 90, sc(FS), ["record-keeping"], "F", "synonym"),
    C("Credit application record retention", "Credit application files and decision notices are kept for the period the bank has set.", RECM, 180, sc(CD), ["record-keeping"], "L", "words"),
    # human oversight
    C("Human review of automated declines", "A trained underwriter reviews a sample of automated declines and can override the outcome.", CRA, 90, sc(CD), ["human oversight"], "F", "words"),
    C("Chat handoff to a human agent", "Customers can reach a human agent at any point, and agents can stop the chatbot.", CUSO, 90, sc(CC), ["human oversight"], "F", "words"),
    C("Underwriter override log", "Every manual override of an automated credit decision is recorded with the reason and the approver.", CRA, 90, sc(CD), ["human oversight"], "F", "synonym"),
    # accuracy and resilience
    C("Outcomes back-testing", "Quarterly comparison of model predictions with realized outcomes, with gaps investigated.", CRA, 90, sc(CD, FS), ["accuracy and resilience"], "F", "words"),
    C("Adversarial testing of the chatbot", "Red-team exercise that tries to push the chatbot into unsafe or wrong answers.", INFOSEC, 180, sc(CC), ["accuracy and resilience"], "F", "synonym"),
    C("Scoring service failure testing", "Twice a year the scoring service is switched to its backup path and the results are compared with the primary.", TOPS, 180, sc(CD, FS), ["accuracy and resilience"], "F", "synonym"),
    # model inventory
    C("Model inventory register", "Single list of every model and AI system in use, with owner, tier and status.", MRM, 30, ALL, ["model inventory"], "S", "words"),
    C("Workload roll-call", "Each quarter the platform team counts the running AI workloads and ties each one to a business owner.", AIPT, 90, ALL, ["model inventory"], "F", "outside"),
    C("Business owner inventory attestation", "Each business owner signs that the entries for their area are correct and complete.", MRM, 365, ALL, ["model inventory"], "S", "words"),
    # independent validation
    C("Annual model validation", "Validation team, independent of development, tests each model before approval and every year after.", MRM, 365, sc(CD, FS), ["independent validation"], "F", "words"),
    C("Challenger comparison review", "A separate team builds a simple alternative and compares its results with the production model.", MRM, 365, sc(CD, FS), ["independent validation"], "F", "synonym"),
    C("Benchmark replication exercise", "Second-line analysts rebuild the model's headline results from raw data and reconcile any difference.", MRM, 365, sc(CD, FS), ["independent validation"], "F", "outside"),
    C("Second-line review of chatbots", "Second-line reviewers test each new chatbot or copilot against its approved use before launch.", MRM, 180, sc(CC, IC), ["independent validation"], "F", "synonym"),
    # ongoing monitoring
    C("Model performance monitoring", "Monthly dashboard of accuracy and drift for each model, with threshold breaches escalated to the owner.", CRA, 30, sc(CD, FS, CC), ["ongoing monitoring"], "F", "words"),
    C("Chatbot answer sampling", "Weekly sample of chatbot answers is read by a reviewer and scored for errors.", CUSO, 30, sc(CC), ["ongoing monitoring"], "F", "synonym"),
    C("Fraud score drift watch", "Daily drift dashboard on the fraud model's score distribution, with an alert when it moves.", FRDO, 30, sc(FS), ["ongoing monitoring"], "L", "synonym"),
    C("Credit decision outcome watch", "Monthly report of approval and decline rates by segment, reviewed for unexplained shifts.", FLO, 30, sc(CD), ["ongoing monitoring"], "F", "synonym"),
    C("Population stability check", "Monthly check that the applicants reaching the scorecard still look like the build population.", CRA, 30, sc(CD), ["ongoing monitoring"], "F", "synonym"),
    # governance and policy
    C("AI governance committee", "Committee chaired by the chief risk officer approves AI policy, assigns roles and reviews exceptions quarterly.", AIGO, 90, ALL, ["governance and policy"], "F", "words"),
    C("Fair lending compliance program", "Written program with named owners for fair lending testing and issue follow-up.", FLO, 180, sc(CD), ["governance and policy"], "F", "words"),
    C("Policy exception log", "Exceptions to AI policy are logged, approved by a named executive and reviewed each quarter.", AIGO, 90, ALL, ["governance and policy"], "F", "words"),
    C("Board reporting on AI use", "Quarterly pack to the board risk committee on AI use, exceptions and open issues.", AIGO, 90, ALL, ["governance and policy"], "F", "synonym"),
    C("Roles and responsibilities matrix review", "Annual refresh of who owns, builds, validates and approves each AI system.", AIGO, 365, ALL, ["governance and policy"], "L", "synonym"),
    # vendor model oversight
    C("Vendor model due diligence", "Purchased models are assessed on onboarding and every year, with results filed by the model owner.", VMGT, 365, ALL, ["vendor model oversight"], "S", "words"),
    C("Vendor attestation collection", "Annual signed statements from model vendors on testing, change notices and support terms.", VMGT, 365, sc(CD), ["vendor model oversight"], "S", "words"),
    C("Vendor model performance review", "Annual comparison of a purchased model's results with the performance the vendor states.", VMGT, 365, sc(CD, FS), ["vendor model oversight"], "S", "words"),
    C("Exit plan review for model vendors", "Annual check that each vendor-supplied model has a tested way out if the contract ends.", VMGT, 365, ALL, ["vendor model oversight"], "S", "words"),
    # measure function
    C("Evaluation test suite", "Standing set of metrics and test cases run against each chatbot and copilot before release and monthly in use.", AIPT, 30, sc(CC, IC), ["measure function"], "F", "words"),
    C("Scorecard metrics review", "Monthly pack of accuracy and stability metrics for the credit scorecard, reviewed by the model owner.", CRA, 30, sc(CD), ["measure function"], "F", "words"),
    # adverse-action reasons, timely notice
    C("Adverse action reason review", "Compliance samples declined applications each month and checks the stated reasons against the model's top factors.", CTEST, 30, sc(CD), ["specific adverse-action reasons"], "F", "words"),
    C("Reason code mapping review", "Annual review of the table that maps scorecard factors to the reason phrases shown to applicants.", FLO, 365, sc(CD), ["specific adverse-action reasons"], "F", "words"),
    C("Notice timeliness report", "Weekly report of days from decision to notice for every credit application, with late items escalated.", CTEST, 30, sc(CD), ["timely notice of action taken"], "S", "words"),
    C("Late notice escalation", "Any application nearing its notice deadline is flagged to the operations lead for same-day action.", CUSO, 30, sc(CD), ["timely notice of action taken"], "N", "words"),
    # orphan controls: meet no obligation. homonym = shares words with an obligation.
    C("Network traffic monitoring", "Continuous monitoring of network traffic across deployed production systems for signs of intrusion.", INFOSEC, 30, ALL, [], "F", "homonym"),
    C("Application uptime monitoring", "Alerts on response time and availability of customer applications against set thresholds, with escalation to the on-call engineer.", TOPS, 30, ALL, [], "F", "homonym"),
    C("Data center power resilience test", "Annual test of generator and battery backup so critical services recover during a power cut.", TOPS, 365, ALL, [], "L", "homonym"),
    C("Marketing material approval", "Compliance sign-off on customer-facing marketing text, including notices and instructions on how to use each offer, before publication.", CTEST, 90, ALL, [], "F", "homonym"),
    C("Employee conduct training", "Annual training for staff on conduct, with policy acknowledgments and roles for reporting concerns.", HRO, 365, ALL, [], "F", "homonym"),
    C("Vendor invoice approval", "Finance reviews third-party invoices against purchase orders before payment is released.", FINC, 30, ALL, [], "F", "homonym"),
    C("Developer pre-release self-check", "Checklist the build team completes on its own work before release; it is not an independent validation.", AIPT, 90, sc(CD), [], "F", "negation"),
    C("Branch cash handling audit", "Quarterly count and reconciliation of cash held at branches, reviewed by the branch audit lead.", BRNO, 90, ALL, [], "N", "plain"),
    C("Access recertification", "Quarterly review of who can log in to production systems and with which privileges.", INFOSEC, 90, ALL, [], "F", "plain"),
    C("Legacy scorecard validation", "Annual validation of the previous credit scorecard; closed when the scorecard was replaced.", MRM, 365, sc(CD), [], "S", "retired", "retired"),
    C("Chatbot reply keyword filter", "Blocklist of words screened from chatbot replies; closed after the chatbot was rebuilt.", AIPT, 90, sc(CC), [], "N", "retired", "retired"),
]

EVIDENCE_TYPES = ["test result", "review minutes", "system report", "sample check", "attestation", "exception log"]
ITEMS_BY_FREQ = {30: 3, 90: 3, 180: 3, 365: 2}


def sort_key(spec: dict) -> str:
    return hashlib.sha256(f"{SEED}:{spec['name']}".encode()).hexdigest()


def stale_limit_days(freq: int) -> float:
    return STALE_FACTOR * freq


def build() -> dict:
    rng = random.Random(SEED)
    obligations = []
    for i, (fw, theme, stmt, applies) in enumerate(OBLIGATIONS, 1):
        obligations.append({"obligation_id": f"OB-{i:02d}", "framework": fw, "theme": theme,
                            "statement": stmt, "applies_to": applies})

    specs = sorted(CONTROL_SPECS, key=sort_key)
    controls, hidden = [], {}
    for i, s in enumerate(specs, 1):
        cid = f"CT-{i:02d}"
        controls.append({"control_id": cid, "name": s["name"], "description": s["desc"], "owner": s["owner"],
                         "test_frequency_days": s["freq"], "scope": s["scope"], "status": s["status"]})
        hidden[cid] = s

    def classes(scope: str) -> set:
        return set(CLASSES) if scope == "all" else set(scope.split(";"))

    truth = []
    for ob in obligations:
        for c in controls:
            s = hidden[c["control_id"]]
            if s["status"] != "active" or ob["theme"] not in s["serves"]:
                continue
            cov = "full" if classes(ob["applies_to"]) <= classes(c["scope"]) else "partial"
            truth.append({"obligation_id": ob["obligation_id"], "control_id": c["control_id"], "coverage": cov})

    evidence = []
    for c in controls:
        s = hidden[c["control_id"]]
        f, fate = c["test_frequency_days"], s["fate"]
        if fate == "N":
            continue
        if fate == "F":
            latest = rng.randint(4, f)
        elif fate == "L":
            latest = rng.randint(int(f * 1.15), int(f * 1.45))
        else:
            latest = rng.randint(int(f * 1.6), int(f * 2.6))
        n = 2 if fate == "S" else ITEMS_BY_FREQ[f]
        age = latest
        for k in range(n):
            evidence.append({"control_id": c["control_id"],
                             "evidence_type": EVIDENCE_TYPES[(rng.randint(0, 5) + k) % len(EVIDENCE_TYPES)],
                             "collected_on": (AS_OF - timedelta(days=age)).isoformat(),
                             "reviewer": f"R-{rng.randint(1, 9):02d}"})
            age += max(7, f + rng.randint(-5, 5))
    evidence.sort(key=lambda e: (e["control_id"], e["collected_on"]))
    for i, e in enumerate(evidence, 1):
        e["evidence_id"] = f"EV-{i:03d}"
    evidence = [{k: e[k] for k in ("evidence_id", "control_id", "evidence_type", "collected_on", "reviewer")} for e in evidence]
    return {"obligations": obligations, "controls": controls, "evidence": evidence, "truth": truth, "hidden": hidden}


def write_csv(name: str, rows: list, fields: list) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def design_summary(d: dict) -> dict:
    """Facts about the design, computed from the generated rows."""
    obs, cts, ev, tr, hid = d["obligations"], d["controls"], d["evidence"], d["truth"], d["hidden"]
    latest = {}
    for e in ev:
        latest[e["control_id"]] = max(latest.get(e["control_id"], "0000-00-00"), e["collected_on"])
    fresh = {}
    for c in cts:
        lt = latest.get(c["control_id"])
        fresh[c["control_id"]] = bool(lt) and (AS_OF - date.fromisoformat(lt)).days <= STALE_FACTOR * c["test_frequency_days"]
    by_ob = {}
    for t in tr:
        by_ob.setdefault(t["obligation_id"], {})[t["control_id"]] = t["coverage"]
    status = {}
    for ob in obs:
        m = by_ob.get(ob["obligation_id"], {})
        full = [c for c, v in m.items() if v == "full"]
        if not m:
            status[ob["obligation_id"]] = "UNCOVERED"
        elif full:
            status[ob["obligation_id"]] = "COVERED" if any(fresh[c] for c in full) else "STALE"
        else:
            status[ob["obligation_id"]] = "PARTIAL"
    scope_of = {c["control_id"]: (set(CLASSES) if c["scope"] == "all" else set(c["scope"].split(";"))) for c in cts}
    joint = 0
    for ob in obs:
        if status[ob["obligation_id"]] == "PARTIAL":
            need = set(CLASSES) if ob["applies_to"] == "all" else set(ob["applies_to"].split(";"))
            union = set()
            for c in by_ob[ob["obligation_id"]]:
                union |= scope_of[c]
            if need <= union:
                joint += 1
    kinds = {}
    for c in cts:
        k = hid[c["control_id"]]["kind"]
        kinds[k] = kinds.get(k, 0) + 1
    met = {t["control_id"] for t in tr}
    orphans = [c["control_id"] for c in cts if c["control_id"] not in met]
    return {
        "status": status, "fresh": fresh, "kinds": kinds, "joint_cover_violations": joint,
        "orphans": orphans, "n_orphans": len(orphans),
        "n_orphans_retired": sum(1 for c in cts if c["control_id"] in orphans and c["status"] == "retired"),
        "n_full": sum(1 for t in tr if t["coverage"] == "full"), "n_partial": sum(1 for t in tr if t["coverage"] == "partial"),
        "no_evidence": sum(1 for c in cts if c["control_id"] not in latest),
        "stale_controls": sum(1 for c in cts if c["control_id"] in latest and not fresh[c["control_id"]]),
        "fresh_controls": sum(1 for c in cts if fresh[c["control_id"]]),
    }


def main() -> None:
    d = build()
    write_csv("obligations.csv", d["obligations"], ["obligation_id", "framework", "theme", "statement", "applies_to"])
    write_csv("controls.csv", d["controls"], ["control_id", "name", "description", "owner", "test_frequency_days", "scope", "status"])
    write_csv("evidence.csv", d["evidence"], ["evidence_id", "control_id", "evidence_type", "collected_on", "reviewer"])
    write_csv("truth_map.csv", d["truth"], ["obligation_id", "control_id", "coverage"])
    s = design_summary(d)
    assert s["joint_cover_violations"] == 0, "an obligation is covered only by partial controls that jointly span its classes"
    n_ob = len(d["obligations"])
    counts = {}
    for st in s["status"].values():
        counts[st] = counts.get(st, 0) + 1
    print(f"Wrote 4 CSVs. Seed {SEED}, AS_OF {AS_OF.isoformat()}, stale after {STALE_FACTOR} x the test cycle.")
    print(f"  obligations {n_ob}, controls {len(d['controls'])}, evidence items {len(d['evidence'])}, truth rows {len(d['truth'])} "
          f"(full {s['n_full']}, partial {s['n_partial']})")
    print(f"  truth statuses: " + ", ".join(f"{k} {counts.get(k, 0)}" for k in ("COVERED", "PARTIAL", "STALE", "UNCOVERED")))
    print(f"  orphan controls {s['n_orphans']} ({s['n_orphans_retired']} retired); controls with no evidence {s['no_evidence']}; "
          f"stale controls {s['stale_controls']}; fresh controls {s['fresh_controls']}")
    print("  control design labels: " + ", ".join(f"{k} {v}" for k, v in sorted(s["kinds"].items())))
    print(f"  design guard: obligations covered only by partial controls that jointly span their classes: {s['joint_cover_violations']}")


if __name__ == "__main__":
    main()
