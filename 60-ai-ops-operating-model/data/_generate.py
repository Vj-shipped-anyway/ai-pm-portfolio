"""Generate the synthetic data for project 60: a checklist of 23 evidence items across the eight lifecycle
stages of OPERATING_MODEL.md, 60 AI programs in bank operations, and the evidence register each one
would hand a reviewer.

Everything is seeded, so the files are byte-for-byte reproducible. The truth does not come from the
review rules. For each program the generator first draws how far the work really got (`reach`). It then
draws a planted state for every evidence item: ok, absent, lapsed, blank_ref, hollow, future or
self_signed. The true stage of a program is the last stage whose owed items are all `ok`.

Three kinds are hard on purpose:
  hollow            a row that looks complete (reference, producer, date) for an artifact that does not
                    show what the checklist names. The review reads the register, not the artifact, so it
                    cannot see these.
  lapsed            evidence whose cycle was skipped. Its age is drawn from 1.15 to 3.0 times the cycle, so
                    some of it sits inside the review's 1.5 times grace and passes.
  ok, but late      a cycle that ran late. Its age is drawn from 1.52 to 1.8 times the cycle for 2 percent of
                    the ok items, so the review calls it stale: a false alarm.
Items a program's tier does not owe may still carry evidence; a tier-blind checklist would count them.

Run (from data/):  python3 _generate.py
Writes:  checklist.csv, programs.csv, evidence.csv, program_truth.csv, item_truth.csv, as_of.txt,
         example_programs.csv, example_evidence.csv
"""
import csv
import datetime
import random

rng = random.Random(60)
AS_OF = datetime.date(2026, 9, 30)

STAGE_NAMES = {1: "Find the work", 2: "Admit and tier", 3: "Commit capacity", 4: "Build and prove",
               5: "Limited rollout", 6: "Hand off", 7: "Run and watch", 8: "Review"}

# item_id, stage, item, evidence asked for, min_tier, cycle_days, independent, day_window, must_show, source
CHECKLIST = [
    ("I01", 1, "Build brief", "Build brief that classes each step as AGENT, AGENT_HITL, HUMAN_JUDGMENT or HUMAN_CONTROL", 1, 180, "no", 30,
     "every step has a class and the control screen names the worker-data limits", "section 1 stage 1; project 26"),
    ("I02", 2, "Tier record", "Recomputed tier with a named line-1 owner", 1, 180, "no", 30,
     "the tier is recomputed from the form questions and not copied from the sponsor", "section 4; project 11"),
    ("I03", 2, "Evidence status", "READY or HOLD against the evidence owed at the tier", 1, 90, "no", 60,
     "each missing item is listed by id", "section 1 stage 2 and section 4; project 11"),
    ("I04", 2, "Vendor rating", "Vendor rating with exit readiness", 3, 365, "no", 60,
     "the rating states criticality, data access and the upstream provider", "section 4 E08; project 18"),
    ("I05", 3, "Board status", "Board status with reasons computed from evidence", 1, 30, "no", 60,
     "the reasons cite evidence and not the owner's color", "section 1 stage 3; project 24"),
    ("I06", 3, "Reviewer capacity row", "Capacity row for the review team the program needs", 2, 90, "no", 60,
     "planned demand is set against supply for the quarter", "section 1 stage 3; project 24"),
    ("I07", 3, "Benefit baseline", "Benefit baseline with a named finance partner", 2, 90, "no", 60,
     "the baseline period and the holdout are stated", "section 1 stage 3; project 12"),
    ("I08", 4, "Permissions record", "Tool inventory with one least-privilege credential and one owner per tool", 1, 90, "no", 90,
     "each tool maps to one credential and one owner", "section 9 row 2; projects 23, 27"),
    ("I09", 4, "Offline test report", "Eval results from a clean checkout with the probe-set version", 2, 90, "no", 90,
     "the probe-set version and the failing cases are listed", "section 4 E03; project 04"),
    ("I10", 4, "Independent validation", "Validation with effective challenge by a person other than the builder", 3, 365, "yes", 90,
     "the challenge points and how each was resolved", "section 4 E05; project 11"),
    ("I11", 4, "Shadow scorecard", "Agreement with people on the shadow run, with the known-miss list", 2, 90, "no", 90,
     "each known miss has an owner", "section 1 stage 4; project 27"),
    ("I12", 5, "Human review design", "Routing rules and review floors for the cases that go to a person", 3, 180, "no", 0,
     "the floors and the escalation path are written down", "section 4 E06; project 08"),
    ("I13", 5, "Rollout report", "Weekly report against the exit criteria", 1, 7, "no", 0,
     "scope violations and unapproved resubmits are counted, including a count of zero", "section 1 stage 5; project 27"),
    ("I14", 5, "Decision lineage plan", "What is logged per decision, from prompt version to reviewer and outcome", 3, 180, "no", 0,
     "the log fields cover the decision from input to outcome", "section 4 E07; project 09"),
    ("I15", 6, "Signed hand-off record", "Hand-off signed by the owning team lead, naming the brief version", 1, 365, "yes", 0,
     "the signer is on the owning team and the brief version is named", "section 9 row 1; project 27"),
    ("I16", 6, "Rehearsed runbook", "Kill switch and rollback to human-only rehearsed by someone other than the builder", 2, 45, "yes", 0,
     "both steps were run and left an audit trace", "section 9 row 6; projects 25, 27"),
    ("I17", 6, "Fallback and exit plan", "Plan for returning the work to people and for leaving the vendor", 4, 365, "no", 0,
     "the trip conditions and a named approver for restoring", "section 4 E10; project 25"),
    ("I18", 6, "Monitors wired", "Queue depth, tool errors, scope blocks and kill-switch state alert on-call", 1, 90, "no", 0,
     "each listed signal alerts into platform monitoring", "section 9 row 7; project 05"),
    ("I19", 7, "Run-health report", "Scheduled drift and run-health report", 1, 30, "no", 0,
     "the latest report ends in a named decision and not only charts", "section 5 stage 7; projects 02, 05"),
    ("I20", 7, "Permission usage diff", "Grants set against calls in the window", 2, 90, "no", 0,
     "grants with no call are listed with an owner decision", "section 5 stage 4; project 23"),
    ("I21", 7, "Incident clock policy", "Notification hours confirmed with counsel and a named determination role", 3, 365, "no", 0,
     "the hours are dated and the determination role is a person", "section 9 row 9; project 19"),
    ("I22", 8, "Review record", "Widen, fix, hold or retire decision with the evidence it rested on", 1, 90, "no", 0,
     "the decision is one of the four and cites evidence", "section 1 stage 8; project 24"),
    ("I23", 8, "Benefit statement", "Benefit against a holdout with a hard-cash column", 2, 90, "no", 0,
     "hard cash and soft capacity are shown apart", "section 1 stage 8 and section 5; project 12"),
]
ITEMS = [dict(zip(("item_id", "stage", "item", "evidence", "min_tier", "cycle_days", "independent", "day_window",
                   "must_show", "source"), row)) for row in CHECKLIST]
STAGES = sorted(STAGE_NAMES)

TASKS = ["Dispute triage", "Wire exception summary", "Account-opening document check", "Sanctions alert narrative",
         "Payment return coding", "Statement inquiry reply", "Chargeback evidence pack", "Loan-document tie-out",
         "Complaint routing", "Reconciliation break match", "Address-change screening", "Fee waiver review"]
UNITS = ["card operations", "payments operations", "deposit servicing", "lending operations", "client onboarding"]


def pick(weights):
    """Index drawn with the given weights."""
    x = rng.random() * sum(weights)
    for i, w in enumerate(weights):
        x -= w
        if x < 0:
            return i
    return len(weights) - 1


def person(exclude=None):
    while True:
        p = f"u{rng.randint(1, 40):03d}"
        if p != exclude:
            return p


def draw_state(independent):
    x = rng.random()
    for state, p in (("absent", 0.02), ("lapsed", 0.04), ("blank_ref", 0.015), ("hollow", 0.03), ("future", 0.005),
                     ("self_signed", 0.06 if independent else 0.0)):
        if x < p:
            return state
        x -= p
    return "ok"


def age_for(state, cycle):
    if state == "lapsed":
        return max(1, int(round((1.15 + rng.random() * 1.85) * cycle)))
    if state == "ok" and rng.random() < 0.02:
        return int(round((1.52 + rng.random() * 0.28) * cycle))
    return int(round(rng.random() * 1.2 * cycle))


def make_row(program, item, state):
    """The evidence row a program would file for an item in the given planted state."""
    if state == "blank_ref":
        ref = rng.choice(["", "TBD", "n/a", "TODO"])
    else:
        ref = f"DOC-{rng.randint(10000, 99999)}"
    if state == "future":
        when = AS_OF + datetime.timedelta(days=rng.randint(1, 30))
    else:
        when = AS_OF - datetime.timedelta(days=age_for(state, item["cycle_days"]))
    if state == "self_signed":
        who = program["builder"]
    elif item["independent"] == "yes":
        who = person(exclude=program["builder"])
    else:
        who = program["builder"] if rng.random() < 0.6 else person(exclude=program["builder"])
    return {"program_id": program["program_id"], "item_id": item["item_id"], "artifact_ref": ref,
            "produced_by": who, "date": when.isoformat()}


def true_stage(states):
    """Last stage whose owed items are all ok, with every earlier stage clean as well."""
    reached = 0
    for s in STAGES:
        if all(st == "ok" for (stage, owed, st) in states if stage == s and owed):
            reached = s
        else:
            break
    return reached


def build_programs():
    combos = [(t, u) for t in TASKS for u in UNITS]
    rng.shuffle(combos)
    programs, evidence, item_truth, program_truth = [], [], [], []
    for n, (task, unit) in enumerate(combos, 1):
        program = {"program_id": f"P-{n:03d}", "program_name": f"{task} - {unit}",
                   "tier": 1 + pick([18, 18, 15, 9]), "builder": person()}
        reach = pick([2, 4, 5, 7, 8, 9, 7, 5, 3])
        states = []
        for item in ITEMS:
            owed = program["tier"] >= item["min_tier"]
            if not owed:
                state = "ok" if rng.random() < 0.4 else "absent"
            elif item["stage"] <= reach:
                state = draw_state(item["independent"] == "yes")
            elif item["stage"] == reach + 1:
                state = draw_state(item["independent"] == "yes") if rng.random() < 0.35 else "absent"
            else:
                state = "ok" if rng.random() < 0.04 else "absent"
            if state != "absent":
                evidence.append(make_row(program, item, state))
            states.append((item["stage"], owed, state))
            item_truth.append({"program_id": program["program_id"], "item_id": item["item_id"],
                               "owed": int(owed), "planted_state": state})
        shift = (0, 1, 2, 3, -1)[pick([62, 18, 6, 2, 12])]
        program["claimed_stage"] = min(8, max(0, reach + shift))
        in_window = [s[2] for it, s in zip(ITEMS, states) if s[1] and 0 < it["day_window"] <= 90]
        window_ok = all(st == "ok" for st in in_window)
        program_truth.append({"program_id": program["program_id"], "reach": reach,
                              "true_stage": true_stage(states), "window90_ok": int(window_ok)})
        programs.append(program)
    return programs, evidence, item_truth, program_truth


def build_example():
    """A hand-built program for the command-line demo: three defects in a tier-3 program that claims stage 6."""
    program = {"program_id": "EX-01", "program_name": "Dispute triage - card operations", "tier": 3,
               "builder": "u007", "claimed_stage": 6}
    ages = {"I01": 40, "I02": 38, "I03": 12, "I05": 9, "I06": 30, "I07": 30, "I08": 25, "I09": 20,
            "I10": 18, "I11": 14, "I12": 60, "I13": 46, "I14": 60, "I15": 10, "I16": 22, "I18": 15,
            "I19": 6, "I20": 33, "I21": 90, "I22": 5}
    rows = []
    for k, item in enumerate(i for i in ITEMS if i["item_id"] in ages):
        who = "u007" if item["item_id"] == "I10" else f"u{20 + k:03d}"
        rows.append({"program_id": "EX-01", "item_id": item["item_id"], "artifact_ref": f"DOC-9{k:04d}",
                     "produced_by": who, "date": (AS_OF - datetime.timedelta(days=ages[item["item_id"]])).isoformat()})
    return [program], rows


def write(name, fields, rows):
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    programs, evidence, item_truth, program_truth = build_programs()
    write("checklist.csv", ["item_id", "stage", "stage_name", "item", "evidence", "min_tier", "cycle_days", "independent",
                            "day_window", "must_show", "source"],
          [dict(i, stage_name=STAGE_NAMES[i["stage"]]) for i in ITEMS])
    pfields = ["program_id", "program_name", "tier", "builder", "claimed_stage"]
    efields = ["program_id", "item_id", "artifact_ref", "produced_by", "date"]
    write("programs.csv", pfields, programs)
    write("evidence.csv", efields, evidence)
    write("item_truth.csv", ["program_id", "item_id", "owed", "planted_state"], item_truth)
    write("program_truth.csv", ["program_id", "reach", "true_stage", "window90_ok"], program_truth)
    ex_programs, ex_rows = build_example()
    write("example_programs.csv", pfields, ex_programs)
    write("example_evidence.csv", efields, ex_rows)
    with open("as_of.txt", "w", encoding="utf-8") as fh:
        fh.write(AS_OF.isoformat() + "\n")
    print(f"wrote {len(ITEMS)} checklist items, {len(programs)} programs and {len(evidence)} evidence rows")


if __name__ == "__main__":
    main()
