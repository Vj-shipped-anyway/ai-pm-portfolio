"""Step 4 - The fix: the full trace, with the known limit printed.

The tool as it ships: sentences split with abbreviations and trailing citations handled, every cited ID
looked up in the case, and the amount, date, party, direction, channel and count in each sentence
compared with the cited records. Decision per sentence: traced, unchecked (cites a record, states
nothing checkable) or not traced (uncited, dangling, other case, mismatch).

KNOWN LIMIT, left in on purpose: a sentence that cites a real record and says something no field can
confirm (laundered), and a sentence whose figures are right but bound to the wrong record
(mixed_record), are not flagged by default. The script prints every one of them. --fail-on unchecked
reaches the first kind, at the price of also flagging fine connecting sentences.

Run (from src/):  python3 step_04_with_trace.py
Output: a report, plus out/step_04_sentences.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import OUT_DIR, ensure_out, load_corpus, locate, misses, false_alarms, score, tally, tool_flagger
from narrative_trace import analyse, split_sentences

ledger, narratives, truth = load_corpus()
flags, stray = score(narratives, truth, tool_flagger(ledger))
t = tally(truth, flags, stray)
s_flags, s_stray = score(narratives, truth, tool_flagger(ledger, strict=True))
strict = tally(truth, s_flags, s_stray)

rows, agree, statuses = [], 0, Counter()
for n in narratives:
    spans = {(r["start"], r["end"]): r for r in truth[n["case_id"]]}
    agree += sum(1 for s in split_sentences(n["text"]) if (s["start"], s["end"]) in spans)
    for res in analyse(n["text"], ledger, n["case_id"]):
        row = locate(truth[n["case_id"]], res["start"])
        statuses[res["status"]] += 1
        rows.append({"case_id": n["case_id"], "sent_no": row["sent_no"], "kind": row["kind"], "expected": row["expected"],
                     "status": res["status"], "findings": "; ".join(sorted({k for k, _ in res["findings"]})) or "none",
                     "text": " ".join(res["text"].split())})
total = t["defects"] + t["fine"]
to_read = sum(1 for r in rows if r["status"] not in ("traced",))
unchecked_bad = sum(1 for r in rows if r["status"] == "unchecked" and r["expected"] == "flag")
unchecked_ok = sum(1 for r in rows if r["status"] == "unchecked" and r["expected"] == "ok")
missed = [r for r in rows if r["expected"] == "flag" and r["status"] in ("traced", "unchecked")]

print("STEP 4 - the full trace")
print(f"  planted defects flagged: {t['caught']} of {t['defects']}")
print(f"  fine sentences flagged: {t['false_alarms']} of {t['fine']} ({false_alarms(t)})")
print(f"  sentences the splitter cut where the planted sentence ends: {agree} of {total}")
print(f"  sentences a person has to read: {to_read} of {total} (step 1: {total})")
print(f"  verdicts: {statuses['traced']} traced, {statuses['unchecked']} unchecked, "
      f"{sum(statuses[k] for k in ('uncited', 'dangling', 'other_case', 'mismatch'))} not traced")
print("  by planted kind (flagged of total):")
for kind, v in sorted(t["by_kind"].items()):
    print(f"    {kind:<18} {v['flagged']:>3} of {v['total']:<3} {'defect' if v['expected'] == 'flag' else 'fine'}")
print(f"  KNOWN LIMIT: defects that pass by default: {len(missed)} of {t['defects']} ({misses(t)})")
for kind in sorted({r["kind"] for r in missed}):
    print(f"    {kind}: " + ", ".join(f"{r['case_id']} s{r['sent_no']}" for r in missed if r["kind"] == kind))
print(f"  of the unchecked verdicts, {unchecked_bad} are planted defects and {unchecked_ok} are fine sentences the tool cannot tell apart")
print(f"  with --fail-on unchecked: defects flagged {strict['caught']} of {strict['defects']}, fine sentences flagged {strict['false_alarms']} of {strict['fine']}")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_sentences.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {"defects": t["defects"], "caught": t["caught"], "fine": t["fine"], "false_alarms": t["false_alarms"],
           "sentences": total, "to_read": to_read, "missed": len(missed), "strict_caught": strict["caught"],
           "strict_false_alarms": strict["false_alarms"], "splitter_agrees": agree,
           "verdicts": dict(sorted(statuses.items()))}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_sentences.csv and step_04_summary.json in src/out/")
