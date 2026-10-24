"""Generate the synthetic data for project 56: a catalogue of 24 framework risks, a registry of 20
runnable checks, the text each check prints, and a crosswalk of 73 rows. A row says "this check
covers that risk, and this line of its output shows it".

Everything is seeded, so the files are byte-for-byte reproducible. The truth about each row comes
from the way the row was built, not from the rules in src/aigf_checks.py:

  * a row is built to have exactly one planted defect (or none), so its label is known;
  * each check has a declared list of aspects (what the registry says) and a real list (what the
    check does). Two checks declare an aspect they do not exercise, which no rule can see;
  * the risk-level truth is derived from the rows' planted truth.

Hard cases, on purpose. Hard negatives that could raise a false alarm: output printed with
thousands separators and different case, a note that says "non-compliant" while describing what
the check lists, and an honest "partial" row. Hard cases the rules should miss: a note that
overclaims in words the rules do not know, and a declared aspect the check does not exercise.

Run (from data/):  python3 _generate.py
Writes: risks.csv, checks.csv, crosswalk.csv, check_outputs.json, row_truth.csv, risk_truth.csv,
        check_truth.csv, example_risks.csv, example_checks.csv, example_crosswalk.csv,
        example_outputs.json
"""
from __future__ import annotations

import csv
import json
import random
import re

SEED = 56

# (risk_id, title, summary, aspects). The aspects are what a check must exercise to cover the risk.
RISKS = [
    ("R-01", "Instructions hidden in user input", "A user types text that tells the assistant to ignore its rules.", ["direct_input"]),
    ("R-02", "Instructions hidden in retrieved documents", "A document the assistant reads carries instructions meant for it.", ["retrieved_content"]),
    ("R-03", "Prompt manipulation across input and documents", "Instructions arrive both from the user and from retrieved text.", ["direct_input", "retrieved_content"]),
    ("R-04", "Tool call with altered arguments", "The arguments of a tool call are changed on the way to the tool.", ["tool_parameters"]),
    ("R-05", "Agent chains tools past its brief", "Calls that are each allowed combine into an outcome nobody allowed.", ["tool_parameters", "permission_scope"]),
    ("R-06", "Answer states what the sources do not say", "A generated answer asserts something no source supports.", ["unsupported_claim"]),
    ("R-07", "Figures in an answer do not match the record", "A number in generated text differs from the number in the record.", ["number_error"]),
    ("R-08", "Narrative with unsupported claims or wrong figures", "A generated narrative mixes claims with no source and figures that are off.", ["unsupported_claim", "number_error"]),
    ("R-09", "Provider changes the model without notice", "Behaviour moves although nobody on the team changed anything.", ["version_change"]),
    ("R-10", "Model upgrade changes behaviour and supplier terms", "A planned upgrade moves quality and the terms of supply together.", ["version_change", "supplier_change"]),
    ("R-11", "Input data moves away from the training data", "Production inputs stop resembling what the model was built on.", ["data_shift"]),
    ("R-12", "Quality decays and nobody can show when", "Quality falls over months and the record cannot date the fall.", ["data_shift", "audit_record"]),
    ("R-13", "Agent holds more permissions than it uses", "The grant is wider than the work, so a mistake has a wider reach.", ["permission_scope"]),
    ("R-14", "Agent skips an approval step", "An action that needs a person's approval runs without it.", ["approval_step"]),
    ("R-15", "Agent exceeds scope and skips approval", "Both failures at once on the same action.", ["permission_scope", "approval_step"]),
    ("R-16", "Outputs differ across customer groups", "The same request gets a worse result for one group.", ["group_gap"]),
    ("R-17", "Supplier alters a tool definition", "The description or schema of a supplied tool changes under the agent.", ["supplier_change", "tool_parameters"]),
    ("R-18", "Supplier compromise reaches the agent", "A compromised supplier feeds the agent content and widens its reach.", ["supplier_change", "retrieved_content", "permission_scope"]),
    ("R-19", "Decisions cannot be reconstructed afterwards", "The record of a decision is too thin to replay it.", ["audit_record"]),
    ("R-20", "Record of an approved action is missing or altered", "The approval happened but the record of it cannot be trusted.", ["audit_record", "approval_step"]),
    ("R-21", "Hidden instructions steer tool choice", "Text in the input changes which tool the agent calls.", ["direct_input", "tool_parameters"]),
    ("R-22", "Answers cite a source that does not exist", "A citation points at a document that is not in the corpus.", ["unsupported_claim", "audit_record"]),
    ("R-23", "Fairness gap appears after a model change", "A group gap opens when the model version moves.", ["group_gap", "version_change"]),
    ("R-24", "Model endpoint is unavailable at peak", "The service cannot be reached when demand is highest.", ["availability"]),
]

# (check_id, project, command, declared aspects, declared aspects it does not really exercise)
CHECKS = [
    ("C-01", "inject-lab", "python3 inject_lab.py --demo", ["direct_input", "retrieved_content"], []),
    ("C-02", "inject-lab", "python3 step_04_replay.py", ["direct_input"], []),
    ("C-03", "tool-gate", "python3 tool_gate.py --demo", ["tool_parameters", "supplier_change"], []),
    ("C-04", "tool-gate", "python3 step_04_gate.py", ["tool_parameters"], []),
    ("C-05", "ground-lab", "python3 ground_lab.py --demo", ["unsupported_claim", "number_error"], []),
    ("C-06", "ground-lab", "python3 step_04_trace.py", ["unsupported_claim"], []),
    ("C-07", "figure-tie", "python3 figure_tie.py --demo", ["number_error", "audit_record"], []),
    ("C-08", "swap-lab", "python3 swap_lab.py --demo", ["version_change", "supplier_change"], []),
    ("C-09", "swap-lab", "python3 step_04_brief.py", ["version_change"], []),
    ("C-10", "drift-lab", "python3 drift_lab.py --demo", ["data_shift"], []),
    ("C-11", "drift-lab", "python3 step_04_monitor.py", ["data_shift", "audit_record"], []),
    ("C-12", "scope-lab", "python3 scope_lab.py --demo", ["permission_scope"], []),
    ("C-13", "scope-lab", "python3 step_04_review.py", ["permission_scope", "approval_step"], []),
    ("C-14", "approval-lab", "python3 approval_lab.py --demo", ["approval_step", "audit_record"], []),
    ("C-15", "fair-lab", "python3 fair_lab.py --demo", ["group_gap"], []),
    ("C-16", "fair-lab", "python3 step_04_gap.py", ["group_gap", "version_change"], []),
    ("C-17", "trail-lab", "python3 trail_lab.py --demo", ["audit_record"], []),
    ("C-18", "supplier-lab", "python3 supplier_lab.py --demo", ["supplier_change", "retrieved_content", "permission_scope"], ["permission_scope"]),
    ("C-19", "breaker-lab", "python3 breaker_lab.py --demo", ["tool_parameters", "permission_scope", "approval_step"], ["approval_step"]),
    ("C-20", "steer-lab", "python3 steer_lab.py --demo", ["direct_input", "tool_parameters"], []),
]

FORMAT_CHECKS = ["C-06", "C-16", "C-20"]      # print Title Case labels and thousands separators
NO_OUTPUT_CHECKS = ["C-04", "C-09", "C-17"]   # no captured output on file
FALSE_PAIRS = [("R-13", "C-18"), ("R-18", "C-18"), ("R-14", "C-19"), ("R-15", "C-19")]
GAP_RISKS = ["R-12", "R-19", "R-24"]          # no row is written for these
FALSE_CHECKS = ["C-18", "C-19"]

LABELS = ["cases caught", "false alarms", "claims traced", "figures tied", "rows read", "drift flagged",
          "scopes cut", "approvals found", "groups compared", "events logged", "calls replayed",
          "regressions flagged", "sources matched", "tools reviewed", "versions compared", "alerts raised"]

NOTES = ["Run it from the project folder.", "Reads the synthetic cases in data/.", "Prints the line cited here.",
         "Checked by hand once.", ""]
CLAIM_NOTES = ["Compliant with the framework requirement for this risk.", "Certified coverage of this risk.",
               "The check guarantees detection of this risk."]
PARAPHRASE_NOTES = ["Fully satisfies the requirement for this risk.", "Meets the standard for this risk.",
                    "Proves the control is effective."]
NEGATED_NOTE = "Also lists non-compliant rows in its output."

PLAN = [("ok", 14), ("ok_reformatted", 6), ("ok_negated_word", 3), ("ok_partial", 5), ("stale_value", 10),
        ("label_missing", 4), ("unknown_check", 3), ("unknown_risk", 3), ("overclaim", 7), ("no_output", 4),
        ("duplicate", 3), ("wording_claim", 4), ("wording_paraphrase", 3), ("false_declaration", 4)]
NOT_DEFECTIVE = {"ok", "ok_reformatted", "ok_negated_word", "ok_partial"}
NO_PROOF = {"stale_value", "label_missing", "no_output", "unknown_check"}
EXPECT = {"stale_value": "stale_value", "label_missing": "label_missing", "unknown_check": "unknown_check",
          "unknown_risk": "unknown_risk", "overclaim": "aspect_gap", "no_output": "no_output",
          "duplicate": "duplicate_row", "wording_claim": "overclaim_wording",
          "wording_paraphrase": "overclaim_wording", "false_declaration": "aspect_gap"}


def make_metrics(rng, big):
    """Four (label, value) lines a check prints. Large numbers when the output will carry separators."""
    out = []
    for label in rng.sample(LABELS, 4):
        form = rng.random()
        if big:
            d = rng.randint(1000, 4000)
            value = f"{rng.randint(d // 2, d)} of {d}"
        elif form < 0.7:
            d = rng.randint(8, 60)
            value = f"{rng.randint(1, d)} of {d}"
        elif form < 0.85:
            value = f"{rng.randint(500, 999) / 10:.1f}%"
        else:
            value = str(rng.randint(2, 140))
        out.append((label, value))
    return out


def with_commas(value):
    return re.sub(r"\d{4,}", lambda m: f"{int(m.group()):,}", value)


def render_output(check_id, project, metrics, styled):
    lines = [f"CHECK {check_id} ({project}) - synthetic output"]
    for label, value in metrics:
        if styled:
            lines.append(f"  {label.title()}  :   {with_commas(value)}")
        else:
            lines.append(f"  {label}: {value}")
    return "\n".join(lines) + "\n"


def stale_claim(value, text, trap):
    """A claim that is no longer true. A trap claim is a suffix of the true value, so it is a substring of it."""
    if trap:
        return value[1:]
    first = int(re.search(r"\d+", value).group())
    for bump in (1, 2, 3):
        claim = re.sub(r"\d+", str(first + bump), value, count=1)
        if claim not in text:
            return claim
    raise SystemExit("generator: no stale claim found")


def is_trap(value):
    return len(value) > 2 and value[0].isdigit() and value[1].isdigit() and value[1] != "0"


def coverage(need, really):
    return "full" if need <= really else "partial" if need & really else "none"


def build(rng):
    aspects = {r[0]: set(r[3]) for r in RISKS}
    declared = {c[0]: set(c[3]) for c in CHECKS}
    really = {c[0]: set(c[3]) - set(c[4]) for c in CHECKS}
    metrics = {c[0]: make_metrics(rng, c[0] in FORMAT_CHECKS) for c in CHECKS}
    outputs = {c[0]: render_output(c[0], c[1], metrics[c[0]], c[0] in FORMAT_CHECKS)
               for c in CHECKS if c[0] not in NO_OUTPUT_CHECKS}
    eligible = sorted(r for r in aspects if r not in GAP_RISKS)
    general = sorted(c for c in declared if c not in FORMAT_CHECKS + NO_OUTPUT_CHECKS + FALSE_CHECKS)
    cap_general = [(r, c, i) for r in eligible for c in general if aspects[r] <= really[c] for i in range(4)]
    cap_format = [(r, c, i) for r in eligible for c in FORMAT_CHECKS if aspects[r] <= really[c] for i in range(4)]
    part_general = [(r, c, i) for r in eligible for c in general
                    if aspects[r] & declared[c] and not aspects[r] <= declared[c] for i in range(4)]
    no_out = [(r, c, 0) for r in eligible for c in NO_OUTPUT_CHECKS if aspects[r] & declared[c]]
    used, keys, rows = set(), set(), []

    def take(cands, accept=lambda t: True):
        pool = [t for t in cands if t not in used and accept(t)]
        if not pool:
            raise SystemExit("generator: no candidates left")
        t = rng.choice(pool)
        used.add(t)
        return t

    def mk(kind, r, c, covers, label, value, note):
        key = (r, c, label)
        if kind != "duplicate":
            assert key not in keys, key
            keys.add(key)
        rows.append({"kind": kind, "risk": r, "check": c, "covers": covers, "label": label, "value": value, "note": note})
        return rows[-1]

    def real_claim(c, i):
        return metrics[c][i]

    def fake_label(r, c):
        while True:
            lab = rng.choice(LABELS)
            if (r, c, lab) not in keys and lab not in [m[0] for m in metrics.get(c, [])]:
                return lab

    ok_rows = []
    for _ in range(14):
        r, c, i = take(cap_general)
        ok_rows.append(mk("ok", r, c, "full", *real_claim(c, i), rng.choice(NOTES)))
    for _ in range(6):
        r, c, i = take(cap_format)
        mk("ok_reformatted", r, c, "full", *real_claim(c, i), rng.choice(NOTES))
    for _ in range(3):
        r, c, i = take(cap_general)
        mk("ok_negated_word", r, c, "full", *real_claim(c, i), NEGATED_NOTE)
    for _ in range(5):
        r, c, i = take(part_general)
        mk("ok_partial", r, c, "partial", *real_claim(c, i), rng.choice(NOTES))
    for n in range(10):
        trap = n < 5
        r, c, i = take(cap_general, (lambda t: is_trap(metrics[t[1]][t[2]][1])) if trap else (lambda t: True))
        label, value = real_claim(c, i)
        mk("stale_value", r, c, "full", label, stale_claim(value, outputs[c], trap), rng.choice(NOTES))
    for _ in range(4):
        r, c, i = take(cap_general)
        mk("label_missing", r, c, "full", fake_label(r, c), metrics[c][(i + 1) % 4][1], rng.choice(NOTES))
    for n in range(3):
        r = rng.choice(eligible)
        c = f"C-{91 + n}"
        mk("unknown_check", r, c, "full", rng.choice(LABELS), f"{rng.randint(1, 30)} of {rng.randint(31, 60)}", rng.choice(NOTES))
    for n in range(3):
        _, c, i = take([(f"R-{91 + n}", c, i) for c in general for i in range(4)])
        mk("unknown_risk", f"R-{91 + n}", c, "full", *real_claim(c, i), rng.choice(NOTES))
    for _ in range(7):
        r, c, i = take(part_general)
        mk("overclaim", r, c, "full", *real_claim(c, i), rng.choice(NOTES))
    for _ in range(4):
        r, c, i = take(no_out)
        mk("no_output", r, c, "full", fake_label(r, c), f"{rng.randint(1, 30)} of {rng.randint(31, 60)}", rng.choice(NOTES))
    for _ in range(4):
        r, c, i = take(cap_general)
        mk("wording_claim", r, c, "full", *real_claim(c, i), rng.choice(CLAIM_NOTES))
    for _ in range(3):
        r, c, i = take(cap_general)
        mk("wording_paraphrase", r, c, "full", *real_claim(c, i), rng.choice(PARAPHRASE_NOTES))
    for r, c in FALSE_PAIRS:
        i = rng.randrange(4)
        used.add((r, c, i))
        mk("false_declaration", r, c, "full", *real_claim(c, i), rng.choice(NOTES))
    for orig in rng.sample(ok_rows, 3):
        d = mk("duplicate", orig["risk"], orig["check"], orig["covers"], orig["label"], orig["value"], orig["note"])
        d["orig"] = orig
    rng.shuffle(rows)
    for d in [x for x in rows if x["kind"] == "duplicate"]:
        i = next(k for k, x in enumerate(rows) if x is d)
        j = next(k for k, x in enumerate(rows) if x is d["orig"])
        if i < j:
            rows[i], rows[j] = rows[j], rows[i]
    for n, row in enumerate(rows, 1):
        row["row_id"] = f"ROW-{n:03d}"
        r, c = row["risk"], row["check"]
        row["proof"] = "no" if row["kind"] in NO_PROOF else "yes"
        row["coverage"] = coverage(aspects[r], really[c]) if r in aspects and c in really else ""
    return rows, aspects, really, outputs


def risk_truth(rows, aspects):
    out = {}
    for r in sorted(aspects):
        mine = [x for x in rows if x["risk"] == r]
        if not mine:
            out[r] = "GAP"
        elif any(x["proof"] == "yes" and x["coverage"] == "full" for x in mine):
            out[r] = "CHECKED"
        elif any(x["proof"] == "yes" and x["coverage"] == "partial" for x in mine):
            out[r] = "PARTIAL"
        else:
            out[r] = "UNVERIFIED"
    return out


def write_csv(path, header, records):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(records)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")


def write_example():
    write_csv("example_risks.csv", ["risk_id", "title", "summary", "aspects"], [
        ("R-01", "Instructions hidden in user input", "A user types text that tells the assistant to ignore its rules.", "direct_input"),
        ("R-02", "Instructions hidden in retrieved documents", "A document the assistant reads carries instructions meant for it.", "retrieved_content"),
        ("R-09", "Provider changes the model without notice", "Behaviour moves although nobody on the team changed anything.", "version_change"),
        ("R-15", "Agent exceeds scope and skips approval", "Both failures at once on the same action.", "permission_scope;approval_step")])
    write_csv("example_checks.csv", ["check_id", "project", "command", "exercises"], [
        ("C-01", "inject-lab", "python3 inject_lab.py --demo", "direct_input;retrieved_content"),
        ("C-08", "swap-lab", "python3 swap_lab.py --demo", "version_change"),
        ("C-13", "scope-lab", "python3 scope_lab.py --demo", "permission_scope")])
    write_csv("example_crosswalk.csv", ["row_id", "risk_id", "check_id", "covers", "claim_label", "claim_value", "note"], [
        ("ROW-1", "R-01", "C-01", "full", "cases caught", "38 of 40", "Run it from the project folder."),
        ("ROW-2", "R-02", "C-01", "full", "retrieved cases caught", "17 of 20", ""),
        ("ROW-3", "R-09", "C-08", "full", "regressions flagged", "6 of 6", "Compliant with the framework requirement."),
        ("ROW-4", "R-15", "C-13", "full", "scopes cut", "9 of 12", ""),
        ("ROW-5", "R-01", "C-01", "full", "cases caught", "38 of 40", "")])
    write_json("example_outputs.json", {
        "C-01": "CHECK C-01 (inject-lab) - synthetic output\n  cases caught: 38 of 40\n  retrieved cases caught: 15 of 20\n  false alarms: 2 of 60\n",
        "C-08": "CHECK C-08 (swap-lab) - synthetic output\n  regressions flagged: 6 of 6\n",
        "C-13": "CHECK C-13 (scope-lab) - synthetic output\n  scopes cut: 9 of 12\n"})


def main():
    rng = random.Random(SEED)
    rows, aspects, really, outputs = build(rng)
    truth = risk_truth(rows, aspects)
    write_csv("risks.csv", ["risk_id", "title", "summary", "aspects"], [(r[0], r[1], r[2], ";".join(r[3])) for r in RISKS])
    write_csv("checks.csv", ["check_id", "project", "command", "exercises"], [(c[0], c[1], c[2], ";".join(c[3])) for c in CHECKS])
    write_csv("crosswalk.csv", ["row_id", "risk_id", "check_id", "covers", "claim_label", "claim_value", "note"],
              [(x["row_id"], x["risk"], x["check"], x["covers"], x["label"], x["value"], x["note"]) for x in rows])
    write_json("check_outputs.json", outputs)
    write_csv("row_truth.csv", ["row_id", "kind", "defective", "expected_finding", "proof_ok", "coverage"],
              [(x["row_id"], x["kind"], "no" if x["kind"] in NOT_DEFECTIVE else "yes", EXPECT.get(x["kind"], ""),
                x["proof"], x["coverage"]) for x in rows])
    write_csv("risk_truth.csv", ["risk_id", "status"], sorted(truth.items()))
    write_csv("check_truth.csv", ["check_id", "declared", "really_exercises"],
              [(c[0], ";".join(c[3]), ";".join(a for a in c[3] if a in really[c[0]])) for c in CHECKS])
    write_example()
    print(f"wrote {len(RISKS)} risks, {len(CHECKS)} checks, {len(rows)} crosswalk rows and {len(outputs)} captured outputs")


if __name__ == "__main__":
    main()
