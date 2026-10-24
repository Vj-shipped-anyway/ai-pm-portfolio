"""Step 3 - Where trajectory checks fail when they are simple.

Two checks that look at the calls, each with one idea:
  exact sequence   the run must make the reference tool calls in the reference order, nothing else
  tools present    every required tool must appear somewhere in the run, in any order, with any arguments

The truth is known, so each check is scored on the same 240 runs, split into the defective ones and
the sound ones that differ from the reference on purpose (the hard negatives). KNOWN LIMIT, left in
on purpose: sensitive text inside a free-text argument of a correct call ("note_leak") is caught by
neither check, and step 4 does not catch it either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_all, HARD_NEGATIVES
from trajectory_eval import grade_run


def exact_sequence(task: dict, run: dict) -> bool:
    """True when the run is flagged."""
    return [c["tool"] for c in run["trace"]] != [st["tools"][0] for st in task["steps"]]


def tools_present(task: dict, run: dict) -> bool:
    """True when the run is flagged."""
    seen = {c["tool"] for c in run["trace"]}
    return any(not seen & set(st["tools"]) for st in task["steps"])


def main() -> None:
    tasks, runs = load_all()
    checks = (("exact sequence", exact_sequence), ("tools present", tools_present))
    flags = {name: {r["run_id"]: fn(tasks[r["task_id"]], r) for r in runs} for name, fn in checks}
    bad = [r for r in runs if r["truth"] == "fail"]
    hard = [r for r in runs if r["profile"] in HARD_NEGATIVES]
    clean = [r for r in runs if r["profile"] == "faithful"]
    print("STEP 3 - each trajectory check alone")
    for name, _ in checks:
        f = flags[name]
        print(f"  {name}")
        print(f"    defective runs flagged: {sum(1 for r in bad if f[r['run_id']])} of {len(bad)}")
        print(f"    reference-path runs flagged: {sum(1 for r in clean if f[r['run_id']])} of {len(clean)}")
        print(f"    hard negatives flagged (sound, but unlike the reference): {sum(1 for r in hard if f[r['run_id']])} of {len(hard)}")
    print("  flags by planted behavior (exact sequence, tools present):")
    count = Counter(r["profile"] for r in runs)
    for profile in sorted(count):
        mine = [r for r in runs if r["profile"] == profile]
        print(f"    {profile:<19} runs {count[profile]:>2}   "
              + "   ".join(f"{sum(1 for r in mine if flags[name][r['run_id']]):>2}" for name, _ in checks))
    leaks = [r for r in runs if r["profile"] == "note_leak"]
    through = [r for r in leaks if not any(flags[name][r["run_id"]] for name, _ in checks) and grade_run(tasks[r["task_id"]], r)["passed"]]
    print(f"  KNOWN LIMIT: sensitive text in a free-text argument passes every check here and in step 4: {len(through)} of {len(leaks)}")
    print("  Exact sequence punishes any difference from the reference; tools present cannot see order, arguments or extra calls.")


if __name__ == "__main__":
    main()
