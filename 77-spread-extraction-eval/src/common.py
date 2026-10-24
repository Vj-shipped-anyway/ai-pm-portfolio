"""Shared loading for the four step scripts of project 77."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from spread_eval import EXTRACTORS, evaluate, gate, load_docs, load_truth, pct, predictions_for  # noqa: E402,F401


def load_corpus() -> tuple:
    """(docs, truth). Each document is a dict with doc_id, layout, split, company and text."""
    docs = load_docs(os.path.join(DATA, "statements.csv"), need_text=True)
    return docs, load_truth(os.path.join(DATA, "truth.csv"))


def evaluate_on(docs: list, truth: dict, preds: dict, layouts=None) -> dict:
    """evaluate() restricted to the documents of the named layouts (all layouts when None)."""
    keep = {d["doc_id"]: d["layout"] for d in docs if layouts is None or d["layout"] in layouts}
    return evaluate(keep, {k: v for k, v in truth.items() if k[0] in keep}, {k: v for k, v in preds.items() if k[0] in keep})


def layouts_with_split(docs: list, split: str) -> list:
    return sorted({d["layout"] for d in docs if d["split"] == split})


def gate_on(res: dict, layouts, floor: float = 95.0, max_gap: float = 3.0, min_docs: int = 10) -> dict:
    """gate() on a subset of the layouts of one evaluation result."""
    return gate({n: res["layouts"][n] for n in layouts}, floor, max_gap, min_docs)


def layout_accuracy(res: dict) -> dict:
    return {n: pct(s["correct"], s["values"]) for n, s in res["layouts"].items()}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def write_json(name: str, obj) -> None:
    ensure_out()
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
    print(f"Wrote {name} in src/out/")
