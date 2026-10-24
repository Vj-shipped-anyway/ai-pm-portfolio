"""Step 3 - Where the basic approach fails, and what stays missed after the fix.

Seven deficiencies of the link-and-grep script, each counted on the planted rows. Then the KNOWN LIMIT,
left in on purpose: two kinds of defective row pass the basic approach and also pass step 4, because
no rule in aigf_checks.py reads what they would have to read. The script prints those rows.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from common import basic_flags, basic_status, load_all, tool_flags


def rows_of(d: dict, kind: str) -> list:
    return [r for r, t in d["row_truth"].items() if t["kind"] == kind]


def main() -> None:
    d = load_all()
    basic = basic_flags(d)
    stale = rows_of(d, "stale_value")
    traps = [r for r in stale if not basic[r]]
    print("STEP 3 - seven deficiencies of link-and-grep")
    print(f"  (a) a short number is found inside a longer one: {len(traps)} of {len(stale)} stale rows pass")
    for letter, kind, what in (("b", "label_missing", "the label is ignored, so a renamed line passes"),
                               ("c", "no_output", "no output file means the row is skipped, silently"),
                               ("d", "overclaim", "the aspects are not read, so a row marked full passes"),
                               ("e", "duplicate", "a second row for the same claim is not seen"),
                               ("f", "wording_claim", "the note is not read")):
        ids = rows_of(d, kind)
        print(f"  ({letter}) {what}: {sum(1 for r in ids if not basic[r])} of {len(ids)} rows pass")
    reformatted = rows_of(d, "ok_reformatted")
    print(f"  (g) a harmless difference in print format is flagged: {sum(1 for r in reformatted if basic[r])} of {len(reformatted)} rows")
    status = basic_status(d, basic)
    wrong = [r for r in d["risks"] if status[r] != d["risk_truth"][r]]
    print(f"  risks given the wrong status: {len(wrong)} of {len(d['risks'])}")
    print("  " + ", ".join(f"{r} {status[r]} (truth {d['risk_truth'][r]})" for r in wrong))
    flags, _ = tool_flags(d)
    print("KNOWN LIMIT - rows that pass the basic approach and step 4 as well")
    for kind, why in (("wording_paraphrase", "the note overclaims in words the rule does not list"),
                      ("false_declaration", "the registry declares an aspect the check does not exercise")):
        for r in rows_of(d, kind):
            if not flags[r]:
                row = next(x for x in d["rows"] if x["row_id"] == r)
                print(f"  {r} {row['risk_id']} -> {row['check_id']}  {kind}: {why}")


if __name__ == "__main__":
    main()
