#!/usr/bin/env bash
# Run the full probe suite against a target model and emit an accuracy report.
#
# Usage:
#   ./run-probes.sh --model claude-sonnet-4 --probes ../probes/
#   ./run-probes.sh --model gpt-4o-2024-08-06 --probes ../probes/ --slice 04
#
# Env vars expected:
#   ANTHROPIC_API_KEY     for claude-* models
#   OPENAI_API_KEY        for gpt-* models
#   FIREWORKS_API_KEY     for Llama/Mistral via Fireworks
#
# Output:
#   stdout: per-deficiency accuracy summary
#   ./out/probe-run-<timestamp>.csv: every probe with model response and pass/fail
#   ./out/probe-run-<timestamp>.json: structured summary for CI gating

set -euo pipefail

MODEL=""
PROBES_DIR="../probes"
SLICE=""
OUT_DIR="./out"

while [[ $# -gt 0 ]]; do
  case $1 in
    --model) MODEL="$2"; shift 2 ;;
    --probes) PROBES_DIR="$2"; shift 2 ;;
    --slice) SLICE="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$MODEL" ]]; then
  echo "error: --model is required"
  echo "examples: claude-sonnet-4, gpt-4o-2024-08-06, accounts/fireworks/models/llama-v3p1-70b-instruct"
  exit 1
fi

mkdir -p "$OUT_DIR"
TS=$(date +%Y%m%dT%H%M%S)
CSV="$OUT_DIR/probe-run-$TS.csv"
JSON="$OUT_DIR/probe-run-$TS.json"

echo "model: $MODEL"
echo "probes: $PROBES_DIR"
echo "output: $CSV"
echo

python3 ./run_probes.py \
  --model "$MODEL" \
  --probes-dir "$PROBES_DIR" \
  --slice "$SLICE" \
  --out-csv "$CSV" \
  --out-json "$JSON"

echo
echo "Per-deficiency accuracy:"
python3 -c "
import json
with open('$JSON') as f:
    summary = json.load(f)
for slice_name, stats in summary['by_deficiency'].items():
    n = stats['n']
    acc = stats['accuracy'] * 100
    print(f'  {slice_name:35s}  {acc:5.1f}%  (n={n})')
print()
print(f'  overall                            {summary[\"overall_accuracy\"]*100:5.1f}%  (n={summary[\"overall_n\"]})')
"

# CI gate: fail if overall accuracy below threshold (default 0.85)
THRESHOLD="${PROBE_THRESHOLD:-0.85}"
ACC=$(python3 -c "import json; print(json.load(open('$JSON'))['overall_accuracy'])")
python3 -c "
import sys
acc = float('$ACC')
threshold = float('$THRESHOLD')
if acc < threshold:
    print(f'FAIL: overall accuracy {acc:.3f} below threshold {threshold:.3f}', file=sys.stderr)
    sys.exit(1)
print(f'PASS: overall accuracy {acc:.3f} meets threshold {threshold:.3f}')
"

# _subfolder_description 2026-05-04-093710 : HalluGuard: probe runner script with CI gate
