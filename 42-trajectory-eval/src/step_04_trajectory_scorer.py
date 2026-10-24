"""Step 4 - The fix: grade the whole trajectory against a rubric.

The scorer in trajectory_eval.py reads, for each task:
  graded steps      each step names the tools that count, the arguments that must match, and which
                    earlier steps it must follow; steps with no order between them may come in any order
  forbidden tools   any call to one fails the run, even a call that returned an error
  stop signals      once a check returns the value that means stop, a blocked tool must not be called
  a call budget     more calls than max_steps fails the run
  the final answer  the expected values must be present
A run passes only when all of these hold. The score (0 to 1) gives partial credit for reading.

KNOWN LIMITS, left in on purpose: the scorer does not read free text inside an argument (note_leak),
and it fails a valid equivalent tool the rubric does not list (unlisted_alias). The script prints both.

Run (from src/):  python3 step_04_trajectory_scorer.py
Output: a report, plus out/step_04_runs.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import load_all, ensure_out, OUT_DIR, HARD_NEGATIVES
from trajectory_eval import grade_run


def trace_text(trace: list) -> str:
    parts = []
    for c in trace:
        shown = ", ".join(f"{k}={json.dumps(v)}" for k, v in sorted(c["args"].items()))
        parts.append(f"{c['tool']}({shown})" + (" !error" if c["obs"].get("ok") is False or "error" in c["obs"] else ""))
    return " > ".join(parts)


def main() -> None:
    tasks, runs = load_all()
    rows = []
    for run in runs:
        task = tasks[run["task_id"]]
        g = grade_run(task, run)
        rows.append({"run_id": run["run_id"], "task_id": run["task_id"], "profile": run["profile"], "truth": run["truth"],
                     "final_answer": "pass" if g["outcome_ok"] else "fail", "trajectory": "pass" if g["passed"] else "fail",
                     "score": f"{g['score']:.2f}", "primary_reason": g["primary"],
                     "reasons": " | ".join(f"{c}: {d}" for c, d in g["reasons"]), "steps": len(run["trace"]),
                     "max_steps": task["max_steps"], "trace": trace_text(run["trace"])})
    bad = [r for r in rows if r["truth"] == "fail"]
    sound = [r for r in rows if r["truth"] == "pass"]
    hard = [r for r in rows if r["profile"] in HARD_NEGATIVES]
    caught = [r for r in bad if r["trajectory"] == "fail"]
    caught_by_answer = [r for r in bad if r["final_answer"] == "fail"]
    answer_blind = [r for r in bad if r["final_answer"] == "pass"]
    answer_blind_caught = [r for r in answer_blind if r["trajectory"] == "fail"]
    false_alarms = [r for r in sound if r["trajectory"] == "fail"]
    missed = [r for r in bad if r["trajectory"] == "pass"]
    at_budget = [r for r in rows if r["steps"] == r["max_steps"] and r["truth"] == "pass"]
    n_pass = sum(1 for r in rows if r["trajectory"] == "pass")
    mean_score = sum(float(r["score"]) for r in answer_blind_caught) / len(answer_blind_caught) if answer_blind_caught else 0.0

    print("STEP 4 - trajectory scorer")
    print(f"  runs: {len(rows)}   tasks: {len(tasks)}   whole trajectory passes: {n_pass} of {len(rows)} (step 2 passed {len(rows) - len(caught_by_answer)})")
    print(f"  defective runs caught: {len(caught)} of {len(bad)} (final-answer check alone: {len(caught_by_answer)} of {len(bad)})")
    print(f"  defective runs with a right-looking final answer that the scorer catches: {len(answer_blind_caught)} of {len(answer_blind)}")
    print(f"  mean score of those {len(answer_blind_caught)} runs: {mean_score:.2f} (the final-answer check passed every one of them)")
    print(f"  hard negatives failed (false alarms): {sum(1 for r in hard if r['trajectory'] == 'fail')} of {len(hard)}")
    print(f"  sound runs failed in all: {len(false_alarms)} of {len(sound)}")
    print(f"  sound runs sitting exactly at the call budget: {sum(1 for r in at_budget if r['trajectory'] == 'pass')} of {len(at_budget)} pass")
    print("  by planted behavior (runs, caught or failed):")
    totals = Counter(r["profile"] for r in rows)
    for profile in sorted(totals):
        mine = [r for r in rows if r["profile"] == profile]
        print(f"    {profile:<19} {totals[profile]:>3}   trajectory fails {sum(1 for r in mine if r['trajectory'] == 'fail'):>3}   "
              f"final answer fails {sum(1 for r in mine if r['final_answer'] == 'fail'):>3}")
    reasons = Counter(r["primary_reason"] for r in rows if r["primary_reason"])
    print("  first reason on failing runs: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())))
    print(f"  KNOWN MISS: defective runs that pass: {len(missed)} of {len(bad)} ({', '.join(sorted({r['profile'] for r in missed})) or 'none'})")
    for r in missed:
        print(f"    {r['run_id']} {r['task_id']} {r['profile']}")
    print(f"  KNOWN FALSE ALARM: sound runs failed on an equivalent tool the rubric does not list: {len(false_alarms)} of {len(sound)}")
    for r in false_alarms:
        print(f"    {r['run_id']} {r['task_id']} {r['profile']}: {r['reasons']}")

    ensure_out()
    with open(os.path.join(OUT_DIR, "step_04_runs.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = {"runs": len(rows), "tasks": len(tasks), "sound": len(sound), "defective": len(bad), "trajectory_passes": n_pass,
               "final_answer_passes": len(rows) - len(caught_by_answer), "defective_caught": len(caught),
               "defective_caught_by_answer": len(caught_by_answer), "answer_blind": len(answer_blind),
               "answer_blind_caught": len(answer_blind_caught), "hard_negatives": len(hard),
               "hard_negatives_failed": sum(1 for r in hard if r["trajectory"] == "fail"), "known_miss": len(missed)}
    with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print("Wrote step_04_runs.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
