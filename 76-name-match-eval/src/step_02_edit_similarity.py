"""Step 2 - The common basic approach: character edit similarity on the whole name, with a threshold.

Similarity is 1 minus the edit distance over the length of the longer normalised name. A customer is an
alert when its best score against any listed name reaches the threshold. The sweep shows what each
threshold costs. The two targets are assumptions (common.py): false alerts on at most 10.0% of clear
names, and recall of at least 85.0%.

Run (from src/):  python3 step_02_edit_similarity.py
"""
from common import (load, records_for, format_sweep, metrics_at, lowest_threshold_with_false_rate_at_most, modeled_line,
                    pct, TARGET_RECALL, TARGET_FALSE_ALERT, BASE_RATE)


def main() -> None:
    data = load()
    rec = records_for("edit", data)
    text, _ok = format_sweep("edit", rec, len(data[0]), TARGET_RECALL, TARGET_FALSE_ALERT)
    print("STEP 2 - character edit similarity on the whole name")
    print(text)
    low = metrics_at(rec, 0.30)
    print("best recall at the lowest threshold tried (0.30): %s, with false alerts on %s of clear names"
          % (pct(low["caught"], low["matches"]), pct(low["false_alerts"], low["clear"])))
    a = lowest_threshold_with_false_rate_at_most(rec, TARGET_FALSE_ALERT)
    print("modeled, at an assumed %d real match in every 10,000 customers: at threshold %.2f, %s"
          % (round(BASE_RATE * 10000), a["threshold"], modeled_line(a)))


if __name__ == "__main__":
    main()
