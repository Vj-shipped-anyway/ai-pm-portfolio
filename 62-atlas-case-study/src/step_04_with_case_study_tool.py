"""Step 4 - The fix: draft from the trace with atlas_case_study.py.

Each run's trace goes through the tool: phases, the loop rule, three technique steps with call positions,
no ticket text, identifiers scrubbed. The draft is linted against the contribution schema's rules. Two
checks on the result use the planted truth, which the tool never sees: the set of ATLAS ids should equal the
planted set, and none of the strings planted in the ticket may appear in the draft. The runs the tool
does not draft are printed; they are the known limit from step 3.

Writes src/out/step_04_summary.json, step_04_decisions.csv and step_04_example.yaml for the demo.

Run (from src/):  python3 step_04_with_case_study_tool.py
"""
import csv
import json
import os
from statistics import median_low

from common import OUT_DIR, DATA, ensure_out, load_runs, build_study, lint_study, read_json, to_yaml

runs = load_runs()
rows, drafted, exact, problems, todo_fields, leaks_tool, leaks_planted = [], [], 0, 0, 0, 0, 0
for r in runs:
    built = build_study(r["bundle"])
    if not built:
        rows.append([r["run_id"], r["scenario"], "yes" if r["worthy"] else "no", "no", "", 0, r["n_calls"]])
        continue
    doc, evidence = built
    techs = sorted({e["technique"] for e in evidence})
    p, todos, leaks = lint_study(doc, r["bundle"])
    text = json.dumps(doc)
    drafted.append((r, evidence))
    exact += techs == r["truth"]
    problems += len(p)
    todo_fields += len(todos)
    leaks_tool += len(leaks)
    leaks_planted += any(s in text for s in r["planted"])
    rows.append([r["run_id"], r["scenario"], "yes" if r["worthy"] else "no", "yes", ";".join(techs), len(evidence), r["n_calls"]])

worthy = [r for r in runs if r["worthy"]]
found = sum(1 for d in drafted if d[0]["worthy"])
false = len(drafted) - found
steps = [len(d[1]) for d in drafted]
calls = sum(d[0]["n_calls"] for d in drafted)
summary = {"runs": len(runs), "failures": len(worthy), "harmless": len(runs) - len(worthy), "drafted": len(drafted),
           "failures_drafted": found, "harmless_drafted": false, "techniques_exact": exact, "schema_problems": problems,
           "leaks_declared": leaks_tool, "leaks_planted": leaks_planted, "steps_median": median_low(steps), "steps_max": max(steps),
           "calls_in_drafted": calls, "steps_total": sum(steps), "todo_per_draft": todo_fields // len(drafted)}

print("STEP 4 - a draft from the trace")
print(f"  drafts written: {len(drafted)} of {len(runs)} runs")
print(f"  failures drafted: {found} of {len(worthy)}")
print(f"  harmless runs drafted as case studies: {false} of {len(runs) - len(worthy)}")
print(f"  drafts whose techniques equal the planted set: {exact} of {len(drafted)}")
print(f"  schema problems across the drafts: {problems}")
print(f"  drafts with a declared identifier in them: {leaks_tool} of {len(drafted)}; with a string planted in the ticket: {leaks_planted} of {len(drafted)}")
print(f"  procedure steps per draft: median {summary['steps_median']}, longest {summary['steps_max']}; {summary['steps_total']} steps in all, each with its call position")
print(f"  calls behind the drafts: {calls}; fields still left for a person in each draft: {summary['todo_per_draft']} (actor, reporter, references)")
print("KNOWN LIMIT (from step 3), runs that are failures and got no draft:")
for r in sorted(rows):
    if r[2] == "yes" and r[3] == "no":
        print(f"  {r[0]} {r[1]} ({r[6]} calls)")

ensure_out()
example = build_study(read_json(os.path.join(DATA, "example_bundle.json")))[0]
with open(os.path.join(OUT_DIR, "step_04_example.yaml"), "w", encoding="utf-8") as fh:
    fh.write(to_yaml(example) + "\n")
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["run_id", "scenario", "failure", "drafted", "techniques", "steps", "calls"])
    w.writerows(rows)
