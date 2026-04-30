# `src/` — LeaseGuard runnable code

Four step scripts that mirror the four-act story in the parent README, plus a polished Streamlit prototype.

## Run order

```bash
cd src
pip install -r requirements.txt

python step_01_manual_abstraction.py        # baseline cost / time / accuracy
python step_02_deployed_lease_nlp.py        # SOTA: deployed Claude-Sonnet-over-OCR
python step_03_deficiencies_exposed.py      # the six failure modes, with worked examples
python step_04_with_leaseguard.py           # ensemble verification + triage queue

streamlit run app.py                        # the document-viewer prototype
```

`step_03` and `step_04` depend on the CSVs `step_02` writes to `out/`, so run them in order.

## What each script writes

| Script | Output |
| --- | --- |
| `step_01_manual_abstraction.py` | `out/step_01_results.csv` — per-lease time, cost, accuracy assumption |
| `step_02_deployed_lease_nlp.py` | `out/step_02_results.csv` — per-lease per-field extraction graded against ground truth |
| `step_03_deficiencies_exposed.py` | (prints categorized failure list to stdout; reads `out/step_02_results.csv`) |
| `step_04_with_leaseguard.py` | `out/step_04_results.csv` and `out/step_04_triage_queue.csv` |

## Mock vs real model calls

All four scripts run with stdlib only (no API keys, no network). The "extraction" outputs are mocked to mirror what real Claude-Sonnet-over-OCR and GPT-4o produce on these exact lease patterns. To swap in real model calls:

- Replace the `MOCK_EXTRACTIONS` dict in `step_02_deployed_lease_nlp.py` with a LangChain extraction chain (`langchain.chains.create_extraction_chain` over a prompt template).
- Replace the `SECONDARY_EXTRACTIONS` dict in `step_04_with_leaseguard.py` with a second model call (GPT-4o via `openai`, or a vLLM-served Mistral 7B Instruct fine-tuned on lease language).
- The rule-based validators in `step_04` are real code already and need no swap.

## Streamlit prototype

`app.py` is a three-column document-viewer:

- Left: the source lease, with key clauses highlighted by criticality
- Middle: the primary extraction (deployed NLP), color-coded by correctness
- Right: the LeaseGuard verification status per field, plus the triage queue

It reads from `data/expected_extractions.csv` and `data/deficiency_classes.csv` and the mock extractions in `step_02_deployed_lease_nlp.py` / `step_04_with_leaseguard.py`. Run any step script first if you want the `out/` CSVs cached.
