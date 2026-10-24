"""Step 3 - What each added check buys, and where the whole ladder still fails.

Four versions of the check, each adding one idea, scored on the same sentences:
  A  a citation bracket is present                    (the tool's splitter, so abbreviations are not the problem)
  B  + every cited ID exists and belongs to the case
  C  + the facts in the sentence match the cited record, each figure to the cent, no sums
  D  + a figure may be rounded to the precision written, and may match the sum of the cited records

KNOWN LIMIT, left in on purpose: D still passes a sentence that cites a real record and states nothing
the record can confirm (laundered), and a sentence whose figures are each right but bound to the wrong
record (mixed_record). Step 4 does not catch either by default.

Run (from src/):  python3 step_03_deficiencies_exposed.py
Output: a report, plus out/step_03_ladder.json
"""
import json
import os

from common import OUT_DIR, ensure_out, false_alarms, load_corpus, misses, score, tally, tool_flagger
from narrative_trace import FACTS

ledger, narratives, truth = load_corpus()
ladder = [("A", "bracket present", dict(resolve=False, facts=())),
          ("B", "+ IDs exist in the case", dict(resolve=True, facts=())),
          ("C", "+ facts, to the cent, no sums", dict(resolve=True, facts=FACTS, sums=False, rounding=False)),
          ("D", "+ rounding and sums", dict(resolve=True, facts=FACTS, sums=True, rounding=True))]

print(f"STEP 3 - each version of the check on the same {sum(len(r) for r in truth.values())} sentences")
rows, last = [], None
for letter, name, options in ladder:
    flags, stray = score(narratives, truth, tool_flagger(ledger, **options))
    t = tally(truth, flags, stray)
    last = (t, flags)
    rows.append({"version": letter, "name": name, "caught": t["caught"], "defects": t["defects"],
                 "false_alarms": t["false_alarms"], "fine": t["fine"]})
    print(f"  {letter}  {name:<30} defects caught {t['caught']:>3} of {t['defects']}   fine sentences flagged {t['false_alarms']:>2} of {t['fine']}")
    print(f"       passes: {misses(t)}")
    print(f"       false alarms: {false_alarms(t)}")

t, flags = last
hard = [(k, v) for k, v in sorted(t["by_kind"].items()) if k in ("laundered", "mixed_record")]
print("  KNOWN LIMIT, left in on purpose:")
for kind, v in hard:
    print(f"    {kind}: {v['total'] - v['flagged']} of {v['total']} pass version D")
print("    laundered cites a real record and says something no field of it can confirm.")
print("    mixed_record states amounts and dates that are each right for some cited record, bound to the wrong one.")
ensure_out()
with open(os.path.join(OUT_DIR, "step_03_ladder.json"), "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1, sort_keys=True)
print("Wrote step_03_ladder.json in src/out/")
