# Sample Data

Four CSVs that drive the walkthrough. All synthetic but realistic — modeled on what an actual mid-tier US retail bank would publish in customer-facing rate sheets and product disclosures.

| File | What's in it | Rows |
| --- | --- | --- |
| `products.csv` | The 12 bank products the chatbot answers questions about | 12 |
| `rates.csv` | Current rates by product, tiered where applicable, with effective date | 14 |
| `fees.csv` | Fee schedule by product | 17 |
| `queries.csv` | 30 hand-curated customer questions with correct answers and the failure mode each probes | 30 |

The `queries.csv` is the eval set. Each query is tagged with the foundation-model failure mode it's designed to expose:

- `paraphrase_blindness` — natural-language paraphrase that loses literal token overlap
- `negation_flip` — small wording change that flips the meaning
- `jurisdiction` — state-specific availability
- `citation_fabrication` — regulation/CFR section the model is tempted to invent
- `multihop` — answer requires combining 2-3 facts
- `currency_unit` — bps vs percentage points

Queries per failure class: `negation_flip` 8, `multihop` 7, `paraphrase_blindness` 6, `citation_fabrication` 4, `jurisdiction` 3, `currency_unit` 2. The taxonomy also names `time_staleness` and `confident_and_wrong`, which have no queries in this file.

The `probes/` folder holds 15 sample probe records (5 each for paraphrase blindness, negation flip, and citation fabrication), not one per query. See [`probes/README.md`](../probes/README.md).

## Model labels

Hosted-model names in this project are neutral labels, not product ids. The probe runner example uses `vendor-balanced-4`, and the app shows the pinned snapshot `vendor-balanced-4-20250215`. In prose the chatbot model is "the hosted vendor model", and the Step 3 comparison table calls its column "Vendor model" (stored values, not run in this repo). GPT-4o and Llama keep their real names. No number in this project depends on the label.
