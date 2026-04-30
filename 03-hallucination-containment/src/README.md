# Source — the walkthrough scripts

Four scripts that map 1:1 to the steps in the main README. Each is runnable on its own with no API keys (the LLM responses are mocked from observed real-model behavior so the walkthrough is reproducible on any laptop).

## Run the whole walkthrough end-to-end

```bash
python step_01_before_llm.py        # rule-based keyword matching
python step_02_with_llm.py          # LLM (RAG + mocked Claude responses)
python step_03_defects_exposed.py   # categorize the LLM's wrong answers by failure mode
python step_04_with_containment.py  # add the grounding verifier; show what it catches
```

Each script writes a CSV to `out/` so you can diff results across steps.

## Why mocked LLM responses?

So a reviewer can read the walkthrough without setting up an Anthropic / OpenAI / Fireworks account. The mocks reflect what real foundation models actually produce on these queries — calibrated against a real run we did against `claude-sonnet-4`, `gpt-4o-2024-08-06`, and `Llama-3.1-70B-Instruct`.

## Swapping in real LLM calls

In `step_02_with_llm.py`, replace `mock_llm_response()` with a real call. Example:

```python
import anthropic
client = anthropic.Anthropic()

def call_claude(question: str, context: list) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:",
        }],
    )
    return msg.content[0].text
```

Set `ANTHROPIC_API_KEY` in your environment.

## Streamlit demo

`app.py` is a single-page Streamlit demo that runs the same four steps interactively — pick a query, see the rule-based response, the LLM response, the failure mode it triggers, and the containment decision side by side.

```bash
streamlit run app.py
```
