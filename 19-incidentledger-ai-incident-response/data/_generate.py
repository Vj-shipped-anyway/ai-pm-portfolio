"""Generates the IncidentLedger synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes five CSVs next to this file)

What it builds
  incidents.csv       120 AI incident tickets for a modeled bank, as a ticket queue holds them:
                      reporter priority, a free-text category, a title and description written
                      from templates (a few deliberately ambiguous), and the facts the severity
                      rubric needs.
  truth.csv           What the generator decided: the true category (7 classes), the true
                      severity (S1 to S4, from the rubric inputs), the root-cause key, and a
                      marker for the incidents written to be hard.
  policy.csv          The notification clocks of a modeled bank. Assumed values to confirm with
                      counsel; not legal advice and not a statement of any rule.
  notifications.csv   Which notices were sent and when (the generator decided who was late).
  actions.csv         Follow-up actions: owner, due date, status, evidence link yes or no.

Times are integer hours from EPOCH (hour 0 = 2026-07-01T00:00). AS_OF is a constant: nothing
reads the clock.

The truth is known because the data is synthetic: the generator decided each incident's
category, severity and root cause, and which notices were late. No model wrote any text; the
titles and descriptions are filled-in templates. Nothing here is a real bank, system, vendor,
regulator dataset or incident.
"""

from __future__ import annotations

import csv
import random
from datetime import datetime
from pathlib import Path

SEED = 20261018
OUT = Path(__file__).parent
EPOCH = datetime(2026, 7, 1)          # hour 0
AS_OF = 2304                          # hour 2304 = 2026-10-05T00:00
FIRST_REPORT, LAST_REPORT = 72, 2290  # incidents are reported inside this window (hours)

CATS = ["wrong_output", "unfair_outcome", "data_exposure", "security_injection",
        "availability", "regression_after_change", "misuse"]
CLASS_TICKETS = {"wrong_output": 26, "unfair_outcome": 12, "data_exposure": 16,
                 "security_injection": 16, "availability": 20,
                 "regression_after_change": 20, "misuse": 10}

ALL_SYSTEMS = ["retail-chat-assistant", "card-dispute-summarizer", "kyc-document-extractor",
               "advisor-notes-tool", "contract-clause-finder", "agent-assist-callcenter",
               "mortgage-prescreen-model", "credit-line-model", "underwriting-assistant",
               "fraud-alert-ranker", "collections-draft-tool", "payments-routing-agent",
               "cash-forecast-model", "complaint-classifier"]
DECISION_SYSTEMS = ["mortgage-prescreen-model", "credit-line-model", "underwriting-assistant",
                    "fraud-alert-ranker", "collections-draft-tool"]
SYSTEMS_BY_CAT = {
    "wrong_output": ALL_SYSTEMS[:10] + ["cash-forecast-model"],
    "unfair_outcome": DECISION_SYSTEMS,
    "data_exposure": ["retail-chat-assistant", "advisor-notes-tool", "agent-assist-callcenter",
                      "kyc-document-extractor", "complaint-classifier", "card-dispute-summarizer",
                      "contract-clause-finder", "collections-draft-tool"],
    "security_injection": ["retail-chat-assistant", "payments-routing-agent", "contract-clause-finder",
                           "agent-assist-callcenter", "kyc-document-extractor", "advisor-notes-tool",
                           "card-dispute-summarizer", "complaint-classifier"],
    "availability": ALL_SYSTEMS,
    "regression_after_change": ALL_SYSTEMS,
    "misuse": ["retail-chat-assistant", "advisor-notes-tool", "collections-draft-tool",
               "contract-clause-finder", "underwriting-assistant", "agent-assist-callcenter"],
}

SYSTEM_NAMES = {
    "retail-chat-assistant": "retail chat assistant", "card-dispute-summarizer": "card dispute summarizer",
    "kyc-document-extractor": "KYC document extractor", "advisor-notes-tool": "advisor notes tool",
    "contract-clause-finder": "contract clause finder", "agent-assist-callcenter": "call-center agent assist",
    "mortgage-prescreen-model": "mortgage prescreen model", "credit-line-model": "credit line model",
    "underwriting-assistant": "underwriting assistant", "fraud-alert-ranker": "fraud alert ranker",
    "collections-draft-tool": "collections drafting tool", "payments-routing-agent": "payments routing agent",
    "cash-forecast-model": "cash forecast model", "complaint-classifier": "complaint classifier",
}
ITEMS = ["balance", "fee", "rate", "due date", "payoff amount", "limit", "eligibility result", "address"]
DOCS = ["statement", "invoice", "loan file", "claim form"]
TASKS = ["drafting client letters", "summarizing HR notes", "pricing a deal", "writing marketing copy",
         "preparing a board paper"]
WHO = ["a customer", "a branch banker", "a relationship manager", "a call-center agent"]
ROLES = ["branch staff", "a relationship manager", "the service desk", "internal audit",
         "a compliance analyst", "the operations team", "a team lead", "the monitoring team"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
CLOSERS = ["Reported by {role}.", "Noted by {role} during routine work.", "{n} cases seen so far.",
           "Raised by {role}; more detail to follow.", "First seen on a {day}."]

# (title, body) per category. Written so the clear cases carry the words a reader would use;
# the hard cases are listed further down.
TEMPLATES = {
    "wrong_output": [
        ("{Sys} gave an incorrect {item}",
         "The {sys} quoted an incorrect {item} to {who}. The figure does not match the source record."),
        ("Inaccurate summary from {sys}",
         "A summary produced by the {sys} was inaccurate: it misstated the {item}."),
        ("{Sys} produced a made-up reference",
         "The {sys} cited a policy clause that does not exist; the clause was fabricated."),
        ("Wrong {item} in {sys} output",
         "The {sys} returned the wrong {item} for {n} accounts."),
    ],
    "unfair_outcome": [
        ("Approval gap between groups in {sys}",
         "A monthly review found an approval gap: applicants in one protected group were denied at a "
         "higher rate than comparable applicants."),
        ("Possible disparity in {sys} decisions",
         "Outcome data shows a disparity in {item} decisions across a protected group."),
        ("{Sys} looks biased on {item}",
         "Several customers reported unfair {item} decisions. The pattern suggests the model is "
         "biased against short credit histories."),
        ("Reasons in adverse action notices look off",
         "The adverse action notices cite reasons that were not the real drivers, and the pattern is "
         "unfair to thin-file applicants."),
    ],
    "data_exposure": [
        ("Account details visible to another user",
         "The {sys} showed one customer's {item} to another customer in {n} sessions. The details "
         "were disclosed before the session ended."),
        ("Data leaked through {sys} logs",
         "Debug logs from the {sys} contained a {doc} and were leaked to a shared channel; there was "
         "unauthorized access by staff outside the team."),
        ("Exposed {doc} in an export",
         "An export from the {sys} was exposed on an open share for {n} hours."),
    ],
    "data_exposure_nonpii": [
        ("Internal pricing sheet leaked via {sys}",
         "A prompt template included an internal pricing sheet that was disclosed to an outside party."),
    ],
    "security_injection": [
        ("Prompt injection through an uploaded {doc}",
         "The {sys} ignored its instructions after a crafted message hidden in a customer {doc}."),
        ("Jailbreak attempt succeeded on {sys}",
         "A user used a jailbreak to get the {sys} to produce restricted content in {n} sessions."),
        ("Instruction override via document text",
         "Hidden text in an uploaded file was an injected instruction that made the agent call a "
         "payments tool; the tool abuse was stopped before settlement."),
        ("Data exfiltration attempt on {sys}",
         "A crafted request tried to exfiltrate account notes through the {sys}; the attempt failed."),
    ],
    "availability": [
        ("{Sys} outage",
         "The {sys} was unavailable for {d} hours and {n} requests failed."),
        ("Timeouts on {sys}",
         "Requests to the {sys} timed out and latency was high through the afternoon; error rate "
         "peaked at {pct} percent."),
        ("{Sys} not responding",
         "The {sys} stopped responding for part of the morning and the service was degraded."),
        ("{Sys} down for {d} hours",
         "The {sys} was down for {d} hours overnight; queued work finished the next day."),
    ],
    "regression_after_change": [
        ("{Sys} worse after change {chg}",
         "Quality dropped since the update {chg}: results are worse than before on {item} cases."),
        ("Regression after the model change",
         "After the model change {chg}, the {sys} handles {item} requests differently."),
        ("{Sys} behaves differently after deploy",
         "After deploy of {chg}, the {sys} no longer handles {item} requests as it did."),
        ("Output format changed since the release",
         "Since the release {chg}, the {sys} writes the {item} in a different format and downstream "
         "steps reject it."),
    ],
    "misuse": [
        ("Staff used {sys} outside approved use",
         "A team used the {sys} for {task}, which is outside approved use and not permitted by the "
         "usage policy."),
        ("Unapproved use of {sys}",
         "A policy breach: an analyst used the {sys} on {doc} documents it is not approved for."),
        ("Customer misuse of the {sys}",
         "A customer used the {sys} to draft fake documents; this is misuse of the service against "
         "the usage policy."),
        ("Approval step bypassed on {sys}",
         "A user bypassed the approval step and sent {sys} output to customers without review."),
    ],
}

# Hard cases: (code, true category, title, body, what is forced)
HARD = {
    "tie": {
        "availability": ("{Sys} timed out for some users",
                         "When the {sys} timed out, the fallback path returned an incorrect {item}."),
        "wrong_output": ("{Sys} issue reported by {role}",
                         "The {sys} quoted the wrong {item} to {who}. Latency was also high that hour, so "
                         "it is unclear which problem this is."),
    },
    "outvoted": {
        "availability": ("{Sys} failed, then gave bad data",
                         "After the service was unavailable, answers from the {sys} were incorrect and "
                         "inaccurate until the cache was rebuilt."),
    },
    "no_keyword": {
        "wrong_output": ("Something looks off with {sys}",
                         "{Role} says the {sys} is behaving oddly. No error message and no detail yet."),
        "misuse": ("Question about {sys} activity",
                   "{Role} noticed unusual activity on the {sys} and wants someone to look. No detail yet."),
    },
    "cause_vs_effect": {
        "security_injection": ("Crafted prompt pulled account notes from {sys}",
                               "A crafted prompt made the {sys} read out customer account notes to an "
                               "outside user."),
        "misuse": ("Customer details pasted into {sys}",
                   "A user pasted customer details into the {sys} for a task outside approved use."),
    },
    "no_change_word": {
        "regression_after_change": ("{Sys} less accurate on {item} cases",
                                    "Results from the {sys} are less accurate on {item} cases than last "
                                    "month, and several incorrect answers went to {who}."),
    },
}
HARD_PLAN = [("tie", "availability", 2), ("tie", "wrong_output", 1), ("outvoted", "availability", 1),
             ("no_keyword", "wrong_output", 1), ("no_keyword", "misuse", 1),
             ("cause_vs_effect", "security_injection", 2), ("cause_vs_effect", "misuse", 1),
             ("no_change_word", "regression_after_change", 1)]

# What a reporter types in the free-text category box.
REPORTER_LABELS = {
    "wrong_output": ["wrong answer", "incorrect output", "bad output", "inaccurate", "hallucination",
                     "AI error", "wrong info", "bug"],
    "unfair_outcome": ["bias", "fairness", "unfair decision", "disparity", "complaint", "AI issue"],
    "data_exposure": ["data leak", "privacy", "PII", "exposure", "data issue", "security"],
    "security_injection": ["security", "prompt injection", "jailbreak", "attack", "injection",
                           "security issue", "AI issue"],
    "availability": ["outage", "down", "slow", "performance", "timeout", "unavailable", "system issue"],
    "regression_after_change": ["regression", "model change", "quality drop", "worse after release",
                                "bug", "AI issue", "release problem"],
    "misuse": ["misuse", "policy", "unapproved use", "compliance", "other", "staff issue"],
}

POLICY_ROWS = [
    ("CK1", "Internal executive notice", "sev_s1", 4, "determination",
     "Executive committee told within 4 hours of determination for a severity S1 incident."),
    ("CK2", "Regulator notice", "notification_incident", 36, "determination",
     "Supervisor told within 36 hours of determination for an incident flagged as a notification incident."),
    ("CK3", "Customer notice", "pii_exposed", 720, "determination",
     "Affected customers told within 30 days of determination when personal data was exposed."),
    ("CK4", "Serious-incident report to an AI regulator", "serious_incident", 360, "determination",
     "Report filed within 15 days of determination for a serious incident."),
]
BASIS = "assumption of a modeled bank, not legal advice or a statement of any rule; assumed value to confirm with counsel"
# send-time outcome weights per clock: on time, late, not sent
OUTCOME_W = {"CK1": (55, 25, 20), "CK2": (50, 25, 25), "CK3": (45, 25, 30), "CK4": (40, 25, 35)}


def rubric_severity(customers, regulated, pii, band, duration):
    if band == "high" or (pii and customers >= 100) or (regulated and customers >= 500):
        return "S1"
    if band == "medium" or pii or regulated or customers >= 2000 or duration >= 48:
        return "S2"
    if band == "low" or customers >= 100 or duration >= 12:
        return "S3"
    return "S4"


def is_notification(sev, pii, regulated):
    return sev == "S1" or (sev == "S2" and (pii or regulated))


def is_serious(sev, pii, regulated):
    return sev == "S1" and (pii or regulated)


def clock_applies(clock_id, sev, pii, regulated):
    if clock_id == "CK1":
        return sev == "S1"
    if clock_id == "CK2":
        return is_notification(sev, pii, regulated)
    if clock_id == "CK3":
        return bool(pii)
    return is_serious(sev, pii, regulated)


def fmt(template, ctx):
    text = template.format(**ctx)
    return text[0].upper() + text[1:]


def draw_fields(rng, cat):
    """customers_affected, regulated_decision_involved, pii_exposed, band, duration_hours."""
    def pick(ranges, weights):
        lo, hi = rng.choices(ranges, weights=weights)[0]
        return rng.randint(lo, hi)
    bands = ["none", "low", "medium", "high"]
    if cat == "wrong_output":
        return (pick([(1, 4), (5, 40), (41, 400), (401, 2500)], [30, 40, 22, 8]),
                int(rng.random() < 0.20), 0, rng.choices(bands, weights=[58, 27, 11, 4])[0], rng.randint(0, 12))
    if cat == "unfair_outcome":
        return (pick([(20, 150), (151, 500), (501, 2500)], [40, 30, 30]),
                1, 0, rng.choices(bands, weights=[40, 30, 25, 5])[0], rng.randint(24, 720))
    if cat == "data_exposure":
        return (pick([(1, 30), (31, 99), (100, 5000)], [30, 20, 50]),
                int(rng.random() < 0.10), 1, rng.choices(bands, weights=[35, 35, 20, 10])[0], rng.randint(1, 48))
    if cat == "security_injection":
        return (pick([(0, 5), (6, 50), (51, 400)], [50, 35, 15]),
                int(rng.random() < 0.10), 0, rng.choices(bands, weights=[56, 28, 13, 3])[0], rng.randint(0, 8))
    if cat == "availability":
        return (pick([(50, 400), (401, 1900), (2000, 20000)], [45, 35, 20]),
                int(rng.random() < 0.05), 0, rng.choices(bands, weights=[47, 28, 15, 10])[0], rng.randint(1, 60))
    if cat == "regression_after_change":
        return (pick([(10, 99), (100, 800), (801, 5000)], [40, 40, 20]),
                int(rng.random() < 0.15), 0, rng.choices(bands, weights=[42, 30, 20, 8])[0], rng.randint(6, 72))
    return (pick([(0, 3), (4, 10)], [70, 30]),                       # misuse
            int(rng.random() < 0.05), 0, rng.choices(bands, weights=[72, 23, 5, 0])[0], rng.randint(0, 10))


def noisy(rng, label):
    r = rng.random()
    if r < 0.55:
        return label
    if r < 0.75:
        return label.title()
    if r < 0.82:
        return label.upper()
    if r < 0.90:
        return label + " "
    if r < 0.95:
        return " " + label
    return label + "?"


def build():
    rng = random.Random(SEED)

    # 1. root causes and their tickets
    rcs = []
    for cat in CATS:
        left = CLASS_TICKETS[cat]
        while left > 0:
            size = min(rng.choices([1, 2, 3, 4, 5], weights=[62, 20, 10, 5, 3])[0], left)
            system = rng.choice(SYSTEMS_BY_CAT[cat])
            base = rng.randint(FIRST_REPORT, LAST_REPORT - (150 if size > 1 else 0))
            offs = [0] + sorted(rng.randint(5, 150) for _ in range(size - 1))
            rcs.append({"cat": cat, "system": system, "size": size,
                        "times": [base + o for o in offs]})
            left -= size
    # root-cause keys follow the time of the first ticket
    rcs.sort(key=lambda r: (r["times"][0], r["cat"], r["system"]))
    for i, r in enumerate(rcs, 1):
        r["key"] = f"RC-{i:03d}"
        r["chg"] = f"CHG-{2300 + rng.randint(0, 600)}" if r["cat"] == "regression_after_change" else ""
    tickets = []
    for r in rcs:
        for k, t in enumerate(r["times"]):
            tickets.append({"rc": r, "k": k, "reported_at": t})
    tickets.sort(key=lambda t: (t["reported_at"], t["rc"]["key"], t["k"]))
    for i, t in enumerate(tickets, 1):
        t["incident_id"] = f"INC-{i:04d}"

    # 2. hard cases
    for code, cat, count in HARD_PLAN:
        pool = [t for t in tickets if t["rc"]["cat"] == cat and "hard" not in t]
        if code == "no_change_word":
            pool = [t for t in pool if t["rc"]["chg"]]
        for t in rng.sample(pool, count):
            t["hard"] = code
    # a few non-regression tickets carry a change id (the latest release, linked by the reporter)
    for cat, count in (("availability", 3), ("wrong_output", 2), ("data_exposure", 1)):
        pool = [t for t in tickets if t["rc"]["cat"] == cat and "hard" not in t]
        for t in rng.sample(pool, count):
            t["extra_chg"] = f"CHG-{3000 + rng.randint(0, 400)}"

    # 3. incident fields
    inc_rows, truth_rows, sev_of, flags_of = [], [], {}, {}
    for t in tickets:
        rc, cat = t["rc"], t["rc"]["cat"]
        sys_slug = rc["system"]
        name = SYSTEM_NAMES[sys_slug]
        role = rng.choice(ROLES)
        change_id = rc["chg"] if rc["chg"] else t.get("extra_chg", "")
        ctx = {"sys": name, "Sys": name[0].upper() + name[1:], "chg": change_id,
               "item": rng.choice(ITEMS), "doc": rng.choice(DOCS), "task": rng.choice(TASKS),
               "who": rng.choice(WHO), "role": role, "Role": role[0].upper() + role[1:],
               "n": rng.randint(3, 60), "d": rng.randint(2, 9), "pct": rng.randint(8, 40),
               "day": rng.choice(DAYS)}
        customers, regulated, pii, band, duration = draw_fields(rng, cat)
        hard = t.get("hard", "")
        if cat == "regression_after_change" and rng.random() < 0.15 and hard != "no_change_word":
            change_id = ""                       # the reporter did not know which change it was
            ctx["chg"] = "(change not recorded)"
        if hard:
            title_t, body_t = HARD[hard][cat]
            if hard == "cause_vs_effect":
                pii = 1
                customers = max(customers, rng.randint(5, 60))
        elif cat == "data_exposure" and t["k"] == 0 and rng.random() < 0.20:
            title_t, body_t = TEMPLATES["data_exposure_nonpii"][0]
            pii = 0
        else:
            title_t, body_t = rng.choice(TEMPLATES[cat])
        title = fmt(title_t, ctx)
        body = fmt(body_t, ctx) + " " + fmt(rng.choice(CLOSERS), ctx)
        sev = rubric_severity(customers, regulated, pii, band, duration)
        # reporter priority: usually near the rubric, often not
        base = int(sev[1])
        shift = rng.choices([-1, 0, 1, 2], weights=[12, 38, 32, 18])[0]
        if cat in ("unfair_outcome", "data_exposure") and rng.random() < 0.5:
            shift += 1
        if cat == "availability" and rng.random() < 0.5:
            shift -= 1
        prio = min(4, max(1, base + shift))
        rep_cat = noisy(rng, rng.choice(REPORTER_LABELS[cat]))
        lag_detect = int(rng.expovariate(1 / 6.0)) + (rng.randint(24, 96) if rng.random() < 0.15 else 0)
        detected = max(0, t["reported_at"] - lag_detect)
        lag_det = min(240, int(rng.lognormvariate(2.6, 0.9)))
        determined = t["reported_at"] + lag_det
        t["row"] = {
            "incident_id": t["incident_id"], "reported_at": t["reported_at"],
            "reporter_priority": f"P{prio}", "reporter_category": rep_cat, "title": title,
            "description": body, "system": sys_slug, "change_id": change_id,
            "customers_affected": customers, "regulated_decision_involved": regulated,
            "pii_exposed": pii, "financial_impact_band": band, "duration_hours": duration,
            "detected_at": detected, "determined_at": determined,
        }
        t["truth"] = {"incident_id": t["incident_id"], "true_category": cat, "true_severity": sev,
                      "root_cause_key": rc["key"], "hard_case": hard}
        sev_of[t["incident_id"]] = sev
        flags_of[t["incident_id"]] = (pii, regulated)

    # 4. determination that never happens (stuck in assessment) and not yet happened at AS_OF
    stuck_pool = [t for t in tickets if t["truth"]["true_severity"] == "S2"
                  and is_notification("S2", t["row"]["pii_exposed"], t["row"]["regulated_decision_involved"])
                  and t["row"]["reported_at"] < AS_OF - 24 * 30]
    for t in rng.sample(stuck_pool, 5):
        t["row"]["determined_at"] = ""
    for t in tickets:
        d = t["row"]["determined_at"]
        if d != "" and d > AS_OF:
            t["row"]["determined_at"] = ""

    # 5. notifications
    notes, nid = [], 0
    for t in tickets:
        r = t["row"]
        if r["determined_at"] == "":
            continue
        sev = t["truth"]["true_severity"]
        for ck, _name, _app, hours, _anchor, _note in POLICY_ROWS:
            if not clock_applies(ck, sev, r["pii_exposed"], r["regulated_decision_involved"]):
                continue
            due = r["determined_at"] + hours
            outcome = rng.choices(["on_time", "late", "none"], weights=OUTCOME_W[ck])[0]
            sent = None
            if outcome == "on_time":
                sent = r["determined_at"] + max(0, int(hours * rng.uniform(0.05, 1.0)) - (1 if hours > 4 else 0))
            elif outcome == "late":
                sent = due + 1 + int(hours * rng.uniform(0.05, 0.8))
            if sent is not None and sent <= AS_OF:
                nid += 1
                notes.append({"notification_id": f"N-{nid:04d}", "incident_id": t["incident_id"],
                              "clock_id": ck, "sent_at": sent})

    # 6. follow-up actions
    action_text = {
        "wrong_output": ["Add a check against the source record", "Review the prompt and retrieval set", "Add the case to the eval set"],
        "unfair_outcome": ["Run a disparity review on recent decisions", "Review adverse action reasons", "Agree a remediation with the model owner"],
        "data_exposure": ["Rotate affected credentials", "Purge the exposed copies", "Review access to the shared location"],
        "security_injection": ["Add an input filter for the pattern", "Review tool permissions", "Test the fix against the crafted input"],
        "availability": ["Add capacity or a fallback path", "Review the on-call runbook", "Add an alert on the error rate"],
        "regression_after_change": ["Roll back or patch the change", "Add a regression test", "Review the release checklist"],
        "misuse": ["Remind the team of the usage policy", "Restrict access for the use case", "Review the approval step"],
    }
    n_actions = {"S1": (2, 3), "S2": (1, 3), "S3": (1, 2), "S4": (0, 1)}
    acts, aid = [], 0
    for t in tickets:
        r, sev, cat = t["row"], t["truth"]["true_severity"], t["truth"]["true_category"]
        lo, hi = n_actions[sev]
        anchor = r["determined_at"] if r["determined_at"] != "" else r["reported_at"]
        for text in rng.sample(action_text[cat], rng.randint(lo, hi)):
            aid += 1
            due = anchor + rng.choice([168, 336, 720, 1440])
            p_closed = 0.70 if due < AS_OF else 0.20
            if rng.random() < p_closed:
                status = "closed"
                closed_at = max(anchor, due + rng.randint(-120, 240))
                if closed_at > AS_OF:
                    closed_at = AS_OF - rng.randint(0, 48)
                evidence = "yes" if rng.random() < 0.68 else "no"
            else:
                status = rng.choice(["open", "in_progress"])
                closed_at, evidence = "", "no"
            acts.append({"action_id": f"A-{aid:04d}", "incident_id": t["incident_id"], "action": text,
                         "owner": f"owner-{rng.randint(1, 12):02d}", "due_at": due, "status": status,
                         "closed_at": closed_at, "evidence_link": evidence})

    return tickets, notes, acts


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    tickets, notes, acts = build()
    inc_fields = ["incident_id", "reported_at", "reporter_priority", "reporter_category", "title",
                  "description", "system", "change_id", "customers_affected",
                  "regulated_decision_involved", "pii_exposed", "financial_impact_band",
                  "duration_hours", "detected_at", "determined_at"]
    write_csv(OUT / "incidents.csv", inc_fields, [t["row"] for t in tickets])
    write_csv(OUT / "truth.csv", ["incident_id", "true_category", "true_severity", "root_cause_key", "hard_case"],
              [t["truth"] for t in tickets])
    write_csv(OUT / "policy.csv", ["clock_id", "clock_name", "applies_to", "hours", "anchor", "basis", "note"],
              [{"clock_id": a, "clock_name": b, "applies_to": c, "hours": d, "anchor": e, "basis": BASIS, "note": g}
               for a, b, c, d, e, g in POLICY_ROWS])
    write_csv(OUT / "notifications.csv", ["notification_id", "incident_id", "clock_id", "sent_at"], notes)
    write_csv(OUT / "actions.csv", ["action_id", "incident_id", "action", "owner", "due_at", "status",
                                    "closed_at", "evidence_link"], acts)
    sev = {}
    for t in tickets:
        sev[t["truth"]["true_severity"]] = sev.get(t["truth"]["true_severity"], 0) + 1
    print(f"incidents {len(tickets)}, notifications {len(notes)}, actions {len(acts)}, "
          f"root causes {len({t['truth']['root_cause_key'] for t in tickets})}")
    print("severity " + ", ".join(f"{k} {sev[k]}" for k in sorted(sev)))


if __name__ == "__main__":
    main()
