"""Shared loading and scoring for the four step scripts of project 66."""
import csv
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from deprecation_impact import DEMO_AS_OF, analyze, load_aliases, load_features, load_models, load_policy, load_usages  # noqa: E402


def read_csv(name: str) -> list:
    """A file from data/ exactly as a spreadsheet export gives it: strings, nothing trimmed or resolved."""
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_truth() -> list:
    return read_csv("truth_dependencies.csv")


def affected_keys(truth: list) -> set:
    """(feature_id, role) of every dependency that really reaches a retiring model while the feature is still running."""
    return {(r["feature_id"], r["role"]) for r in truth if r["affected"] == "yes"}


def score(flagged: set, truth: list) -> dict:
    aff = affected_keys(truth)
    return {"affected": len(aff), "found": len(flagged & aff), "flagged": len(flagged), "false": len(flagged - aff), "missed": len(aff - flagged)}


def noticed_models() -> list:
    """Models that carry a retirement notice of their own."""
    return [m for m in read_csv("models.csv") if m["retire_date"]]


def family_search() -> set:
    """What a search for the family name of each retiring model finds over every usage string, in any role."""
    families = sorted({m["family"].casefold() for m in noticed_models()})
    return {(u["feature_id"], u["role"]) for u in read_csv("usages.csv") if any(f in u["model_ref"].casefold() for f in families)}


def kinds(keys: set, truth: list) -> str:
    """'kind count, kind count' for a set of (feature_id, role) keys, using the planted kind."""
    by_key = {(r["feature_id"], r["role"]): r["kind"] for r in truth}
    counts = {}
    for k in keys:
        counts[by_key.get(k, "no truth row")] = counts.get(by_key.get(k, "no truth row"), 0) + 1
    return ", ".join(f"{k} {counts[k]}" for k in sorted(counts)) or "none"


def tool_result(only_model=None) -> dict:
    """The tool on the full synthetic registry, as of the demo date."""
    models = load_models(os.path.join(DATA, "models.csv"))
    aliases = load_aliases(os.path.join(DATA, "aliases.csv"), models)
    features = load_features(os.path.join(DATA, "features.csv"))
    usages = load_usages(os.path.join(DATA, "usages.csv"), features)
    return analyze(features, usages, models, aliases, datetime.date.fromisoformat(DEMO_AS_OF), load_policy(None), only_model)


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
