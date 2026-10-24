"""Step 2 - The common basic approach: check the final answer against the expected one.

This is the eval most teams build first: for each task the expected final answer is written down
and a run passes when its final answer carries those values. It is automatic and cheap, and it
never looks at the calls the agent made. The truth label is known, so this step counts what that
blind spot costs.

Run (from src/):  python3 step_02_final_answer_check.py
"""
from collections import Counter

from common import load_all
from trajectory_eval import outcome_ok


def main() -> None:
    tasks, runs = load_all()
    passes = [r for r in runs if outcome_ok(tasks[r["task_id"]], r)]
    bad = [r for r in runs if r["truth"] == "fail"]
    sound = [r for r in runs if r["truth"] == "pass"]
    caught = [r for r in bad if not outcome_ok(tasks[r["task_id"]], r)]
    false_fail = [r for r in sound if not outcome_ok(tasks[r["task_id"]], r)]
    print("STEP 2 - final-answer check")
    print(f"  runs that pass: {len(passes)} of {len(runs)}")
    print(f"  defective runs it catches: {len(caught)} of {len(bad)}")
    print(f"  defective runs it passes: {len(bad) - len(caught)} of {len(bad)}")
    print(f"  sound runs it fails: {len(false_fail)} of {len(sound)}")
    passed_bad = Counter(r["profile"] for r in bad if outcome_ok(tasks[r["task_id"]], r))
    total_bad = Counter(r["profile"] for r in bad)
    print("  defective runs passed, by planted behavior:")
    for profile in sorted(total_bad):
        print(f"    {profile:<17} {passed_bad[profile]:>2} of {total_bad[profile]}")
    print("  The check sees the answer. A run can reach the right answer by a path nobody approved.")


if __name__ == "__main__":
    main()
