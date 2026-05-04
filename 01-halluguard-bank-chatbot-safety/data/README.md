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

Every query in `queries.csv` is also documented in the `probes/` folder with rich JSONL records (full retrieved context, valid response patterns, invalid response patterns).

<!-- _subfolder_description 2026-05-04-093726 : HalluGuard: synthetic test data - rate card, fee schedule, 30 customer queries -->
