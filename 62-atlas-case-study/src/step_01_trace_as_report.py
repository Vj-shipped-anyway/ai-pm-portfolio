"""Step 1 - Status quo: the incident is a ticket and a raw trace.

An alert flags 60 agent runs. For each one an on-call engineer wrote a ticket note, and the trace sits
in the log. Nobody turns any of it into a case study, so nothing is shared outside the team. This step
counts what a reader would face if the trace and the ticket were the report. The data is synthetic
(data/_generate.py); which runs were failures is the scenario that was planted, not a judgment by a
script.

Run (from src/):  python3 step_01_trace_as_report.py
"""
from statistics import median_low

from common import load_runs

runs = load_runs()
rows = sum(r["n_calls"] for r in runs)
rows_with_id = sum(1 for r in runs for c in r["bundle"]["calls"] if any(c["args"].get(k) for k in r["bundle"]["identifier_keys"]))
worthy = sum(1 for r in runs if r["worthy"])
planted = sum(1 for r in runs if r["planted"])

print("STEP 1 - the incident as a ticket and a raw trace")
print(f"  runs flagged by an alert: {len(runs)}   tool-call rows: {rows}")
print(f"  case studies written: 0 of {len(runs)}")
print(f"  failures among the flagged runs: {worthy} of {len(runs)}; the alert does not say which")
print(f"  rows a reader scans to follow one run: median {median_low([r['n_calls'] for r in runs])}, longest {max(r['n_calls'] for r in runs)}")
print(f"  trace rows that carry a declared identifier in their arguments: {rows_with_id} of {rows}")
print(f"  tickets that carry an identifier or a person's name: {planted} of {len(runs)}")
print("  The trace cannot be posted as it stands, and the ticket does not map to anything a catalog can use.")
