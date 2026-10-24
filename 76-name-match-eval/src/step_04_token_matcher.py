"""Step 4 - The fix: words folded to a spelling-insensitive key, aligned in any order, rare words weighted up.

Three parts, added one at a time so the table shows what each buys:
  edit          step 2, the whole-name character score
  tokens-flat   words folded and aligned in any order, initials credited, every word weighs 1
  tokens        the same, with each word weighted by how rare it is on the watchlist

The targets are assumptions (common.py): false alerts on at most 10.0% of clear names, recall of at
least 85.0%. The command-line tool (name_match_eval.py) runs exactly this code.

KNOWN LIMIT, left in on purpose: a party known by a name that is not on the list is not caught, a
different person with a listed party's exact name always alerts, and a surname joined to its particle
("Altavari" for "Al Tavari") is caught less often than by the edit matcher. The script prints all three.

Run (from src/):  python3 step_04_token_matcher.py
Output: a report, plus out/step_04_sweep.csv, out/step_04_summary.json and out/step_04_demo.json
"""
import csv
import json
import os
from collections import Counter

from common import (load, records_for, format_sweep, metrics_at, by_kind_at, kinds_of, modeled_line, ensure_out, OUT_DIR, FINE,
                    lowest_threshold_with_false_rate_at_most, highest_threshold_with_recall_at_least, pct,
                    TARGET_RECALL, TARGET_FALSE_ALERT, BASE_RATE)

KINDS = ("edit", "tokens-flat", "tokens")


def main() -> None:
    data = load()
    recs = {k: records_for(k, data) for k in KINDS}
    rec = recs["tokens"]
    match_kinds, clear_kinds = kinds_of(rec)
    text, ok = format_sweep("tokens", rec, len(data[0]), TARGET_RECALL, TARGET_FALSE_ALERT)
    print("STEP 4 - words folded, aligned in any order, rare words weighted up")
    print(text)
    a = lowest_threshold_with_false_rate_at_most(rec, TARGET_FALSE_ALERT)
    b = highest_threshold_with_recall_at_least(rec, TARGET_RECALL)
    print("each part, at the two targets:")
    for k in KINDS:
        ka = lowest_threshold_with_false_rate_at_most(recs[k], TARGET_FALSE_ALERT)
        kb = highest_threshold_with_recall_at_least(recs[k], TARGET_RECALL)
        line_b = ("threshold %.2f, false alerts %s" % (kb["threshold"], pct(kb["false_alerts"], kb["clear"]))
                  if kb else "recall target not reachable")
        print("  %-12s false alerts <= %s: threshold %.2f, recall %s | recall >= %s: %s"
              % (k, "%.1f%%" % (100 * TARGET_FALSE_ALERT), ka["threshold"], pct(ka["caught"], ka["matches"]),
                 "%.1f%%" % (100 * TARGET_RECALL), line_b))
    ea = lowest_threshold_with_false_rate_at_most(recs["edit"], TARGET_FALSE_ALERT)
    print("at the false-alert target: edit catches %d of %d with %d false alerts; tokens catches %d of %d with %d false alerts"
          % (ea["caught"], ea["matches"], ea["false_alerts"], a["caught"], a["matches"], a["false_alerts"]))
    for label, m in (("false-alert target", a), ("recall target", b)):
        by = by_kind_at(rec, m["threshold"])
        print("tokens at the %s, threshold %.2f:" % (label, m["threshold"]))
        print("  matches caught: " + ", ".join("%s %d of %d" % (k, by[k][0], by[k][1]) for k in match_kinds))
        print("  clear names alerting: " + ", ".join("%s %d of %d" % (k, by[k][0], by[k][1]) for k in clear_kinds))
    print("modeled, at an assumed %d real match in every 10,000 customers: at threshold %.2f, %s; at threshold %.2f, %s"
          % (round(BASE_RATE * 10000), a["threshold"], modeled_line(a), b["threshold"], modeled_line(b)))
    low, top = {k: by_kind_at(recs[k], 0.50) for k in KINDS}, {k: by_kind_at(recs[k], 1.0) for k in KINDS}
    mid = {k: by_kind_at(recs[k], 0.75) for k in KINDS}
    print("KNOWN LIMIT, left in on purpose:")
    print("  alias_unlisted caught at 0.50: %d of %d" % low["tokens"]["alias_unlisted"])
    print("  namesake alerts at 1.00: %d of %d" % top["tokens"]["namesake"])
    print("  near_name alerts at 0.85: %d of %d (a one-letter-different surname looks like a typo)" % by_kind_at(rec, 0.85)["near_name"])
    print("  particle_joined caught at 0.75: tokens %d of %d, edit %d of %d" % (mid["tokens"]["particle_joined"] + mid["edit"]["particle_joined"]))
    print("  translit_heavy caught at 0.75: tokens %d of %d, edit %d of %d" % (mid["tokens"]["translit_heavy"] + mid["edit"]["translit_heavy"]))

    ensure_out()
    with open(os.path.join(OUT_DIR, "step_04_sweep.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["matcher", "threshold", "caught", "matches", "false_alerts", "clear", "alerts"])
        for k in KINDS:
            for t in FINE:
                m = metrics_at(recs[k], t)
                w.writerow([k, "%.2f" % t, m["caught"], m["matches"], m["false_alerts"], m["clear"], m["alerts"]])
    summary = {"false_alert_target": TARGET_FALSE_ALERT, "recall_target": TARGET_RECALL,
               "tokens_at_false_alert_target": {"threshold": a["threshold"], "caught": a["caught"], "matches": a["matches"],
                                                "false_alerts": a["false_alerts"], "clear": a["clear"]},
               "tokens_at_recall_target": {"threshold": b["threshold"], "caught": b["caught"], "matches": b["matches"],
                                           "false_alerts": b["false_alerts"], "clear": b["clear"]},
               "both_targets_met": ok}
    with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    demo = {"targets": {"recall": TARGET_RECALL, "false_alert": TARGET_FALSE_ALERT},
            "kinds": {"match": match_kinds, "clear": clear_kinds},
            "counts": dict(sorted(Counter(r["kind"] for r in rec).items())),
            "matchers": {k: [dict(metrics_at(recs[k], t), kinds={kind: h for kind, (h, _n) in by_kind_at(recs[k], t).items()})
                             for t in FINE] for k in KINDS}}
    with open(os.path.join(OUT_DIR, "step_04_demo.json"), "w", encoding="utf-8") as fh:
        json.dump(demo, fh, sort_keys=True)
    print("Wrote step_04_sweep.csv, step_04_summary.json and step_04_demo.json in src/out/")


if __name__ == "__main__":
    main()
