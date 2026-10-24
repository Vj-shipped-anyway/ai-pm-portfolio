"""Step 1 - Status quo: nobody grades the steps.

Twenty operations tasks, 240 recorded agent runs. The only evidence a team has about a run is the
agent's own closing message, so a run counts as done when the agent returned a final answer. This
step counts how many of the accepted runs were in fact defective. The data is synthetic
(data/_generate.py); the truth label of a run is the behavior that was planted when it was built.

Run (from src/):  python3 step_01_self_report.py
"""
from collections import Counter

from common import load_all


def main() -> None:
    tasks, runs = load_all()
    accepted = [r for r in runs if r["final"]]
    bad = [r for r in accepted if r["truth"] == "fail"]
    sound = sum(1 for r in runs if r["truth"] == "pass")
    print("STEP 1 - the agent's closing message is the only evidence")
    print(f"  tasks: {len(tasks)}   recorded runs: {len(runs)}   planted: {sound} sound, {len(runs) - sound} defective")
    print(f"  runs accepted because the agent returned a final answer: {len(accepted)} of {len(runs)}")
    print(f"  accepted runs that were defective: {len(bad)} of {len(accepted)}")
    print("  by planted behavior: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(r["profile"] for r in bad).items())))
    print("  Nobody sees a skipped check, an action taken before its approval or a forbidden call.")


if __name__ == "__main__":
    main()
