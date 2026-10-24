"""Write the synthetic data for project 58 from data/demo_spec.json.

The generator is the tool itself (src/plant.py): a spec in, three files out. A rerun reproduces every
file byte for byte, because every draw comes from a seed in the spec. The flags file is what the naive
stand-in checker (src/_ledger_rules.py) flags, so `plant.py score` has something to read.

Run (from data/):  python3 _generate.py
Writes:  demo_data.csv, demo_truth.csv, demo_manifest.json, demo_flags_naive.csv
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import plant  # noqa: E402
from _ledger_rules import flag_rows  # noqa: E402

result = plant.build(plant.load_spec(os.path.join(HERE, "demo_spec.json")))
plant.write_outputs(result, HERE)
with open(os.path.join(HERE, "demo_flags_naive.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["row_id", "rules"])
    for row_id, rules in sorted(flag_rows(result["rows"], "naive").items()):
        w.writerow([row_id, "+".join(rules)])
print("Wrote demo_data.csv, demo_truth.csv, demo_manifest.json, demo_flags_naive.csv")
