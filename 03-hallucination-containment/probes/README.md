# Probe Set

The actual diagnostic test corpus. 1,260 hand-curated examples across the eight chatbot hallucination deficiencies.

## Files

| File | Deficiency | Probe count | Status |
|------|------------|-------------|--------|
| `01_paraphrase_blindness.jsonl` | Paraphrase blindness | 220 | committed (sample of 5 included) |
| `02_negation_flip.jsonl` | Negation flip | 180 | committed (sample of 5 included) |
| `03_time_staleness.jsonl` | Time staleness | 90 | not yet committed |
| `04_multihop_failure.jsonl` | Multi-hop failure | 280 | not yet committed |
| `05_currency_unit_confusion.jsonl` | Currency-unit confusion | 80 | not yet committed |
| `06_reg_citation_fabrication.jsonl` | Reg-citation fabrication | 90 | committed (sample of 5 included) |
| `07_jurisdiction_confusion.jsonl` | Jurisdiction confusion | 140 | not yet committed |
| `08_confident_and_wrong.jsonl` | Confident-and-wrong | 180 | not yet committed |

The committed samples are illustrative slices. The full probe corpus is what I'd build out in the seat — the design is to expand each deficiency file to the counts above using the schema below. What's committed is enough to demonstrate the schema, the deficiency taxonomy, and the prototype.

## Schema

Each line is a JSON object with the following keys:

- `id` — stable identifier of the form `P{deficiency}-{seq}`.
- `input` — the customer-facing question, exactly as a chatbot would receive it.
- `retrieved_context` — what the RAG layer actually surfaced. The probe locks in the retrieval state so that variation is in generation, not retrieval.
- `expected_grounded` — boolean. Whether a correct response *can* be produced from this context. (Some probes deliberately test what happens when retrieval succeeds but the model still hallucinates.)
- `valid_responses` — paraphrastic equivalents of the correct answer. Substring match against any one of these = pass.
- `invalid_responses` — known wrong patterns. Substring match against any of these = fail.
- `deficiency_tested` — the slice this probe belongs to.
- `real_world_source` — when applicable, points to the incident log entry that motivated this probe.

## Running

```bash
./scripts/run-probes.sh --model claude-sonnet-4 --probes probes/
```

Outputs a per-deficiency accuracy report plus a CSV of every probe with the model's response and pass/fail. CI runs this nightly on a stable subset.

## How to extend

When a new hallucination type shows up in production:

1. File a probe-request issue with the offending input/context/response triplet.
2. Add 30-50 hand-crafted variants under the right deficiency file (or open a new one if it's a genuinely new failure mode).
3. Run the suite against the production verifier to baseline.
4. If accuracy is below threshold, add the new examples to the training mix and retrain.

This is the part that's a permanent function, not a project. Plan accordingly.
