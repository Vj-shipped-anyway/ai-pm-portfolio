"""Step 1 - Before ControlMap: one obligation list per framework.

A modeled bank answers four sets of AI-related obligations (EU AI Act, model risk guidance SR 26-2,
NIST AI RMF, ECOA / Regulation B). Today each framework has its own list. Several themes (record-
keeping, human oversight, ongoing monitoring and others) show up in more than one list, and each
list asks the control owners for its own evidence.

This script counts what that looks like on the synthetic data:

  * how many obligations each framework carries
  * how many distinct themes there are, and how many frameworks ask for the same theme
  * how many evidence requests go out if each framework is answered on its own, against once per
    distinct theme

Nothing here is a real bank, regulation text, control library or model. The obligation statements
are paraphrases written for this exercise, not the text of any rule, and data/_generate.py wrote
every row.

RULE USED FOR THE COUNT (a definition, not a statistic):
  R1. Answered on its own, each framework sends one evidence request per obligation row.
  R2. Answered once per distinct theme, the bank sends one request per theme.

This file also holds the shared loaders and helpers that steps 2 to 4 and the app import:
load_all, tokens, freshness, derive_status, truth_statuses.

Run (from src/):
    python3 step_01_status_quo.py

Output: a readable summary, plus out/step_01_framework_lists.csv and out/step_01_summary.json.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

AS_OF = date(2026, 9, 30)      # keep in sync with data/_generate.py
STALE_FACTOR = 1.5             # evidence is stale when older than this many test cycles
CLASSES = ["credit_decision", "customer_chat", "internal_copilot", "fraud_scoring"]
FRAMEWORK_SHORT = {
    "EU AI Act": "EU AI Act",
    "Model risk guidance (SR 26-2)": "SR 26-2",
    "NIST AI RMF": "NIST AI RMF",
    "ECOA / Regulation B": "ECOA / Reg B",
}

STOPWORDS = set(
    "a an the and or of to in on for with that this is are be by as at it its from into each every any all "
    "their they them when what which who how than then so if not no can may must should will would has have "
    "had was were been being per via also both such these those other over under before after until while "
    "about against between through during within without up down out off again further once only own same "
    "too very just but nor yet we our you your he she his her there here where whose whom".split()
)


# ---------------------------------------------------------------------------
# Shared loaders and helpers (later steps and the app import these)
# ---------------------------------------------------------------------------
def parse_scope(text: str) -> set:
    return set(CLASSES) if text == "all" else set(text.split(";"))


def scope_label(text: str) -> str:
    return "all classes" if text == "all" else ", ".join(text.split(";"))


def tokens(text: str) -> set:
    """Lowercase words of 3+ letters or digits, stopwords removed. No stemming."""
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3 and t not in STOPWORDS}


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load the four CSVs into plain dicts. No pandas needed."""
    def rd(name):
        with open(data_dir / name, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    obligations, controls, evidence, truth = rd("obligations.csv"), rd("controls.csv"), rd("evidence.csv"), rd("truth_map.csv")
    for o in obligations:
        o["classes"] = parse_scope(o["applies_to"])
    for c in controls:
        c["freq"] = int(c["test_frequency_days"])
        c["classes"] = parse_scope(c["scope"])
        c["active"] = c["status"] == "active"
    ev_by_ct = defaultdict(list)
    for e in evidence:
        e["date"] = date.fromisoformat(e["collected_on"])
        ev_by_ct[e["control_id"]].append(e)
    for lst in ev_by_ct.values():
        lst.sort(key=lambda e: e["date"], reverse=True)
    truth_by_ob = defaultdict(dict)
    for t in truth:
        truth_by_ob[t["obligation_id"]][t["control_id"]] = t["coverage"]
    data = {
        "obligations": obligations, "controls": controls, "evidence": evidence, "truth": truth,
        "ob_by_id": {o["obligation_id"]: o for o in obligations},
        "ct_by_id": {c["control_id"]: c for c in controls},
        "ev_by_ct": dict(ev_by_ct), "truth_by_ob": dict(truth_by_ob),
    }
    assert all(e["date"] <= AS_OF for e in evidence), "evidence dated after AS_OF"
    data["fresh"] = freshness(data)
    return data


def freshness(data: dict) -> dict:
    """Per control: latest evidence date, age in days at AS_OF, the limit, and fresh / stale / none."""
    out = {}
    for c in data["controls"]:
        items = data["ev_by_ct"].get(c["control_id"], [])
        limit = STALE_FACTOR * c["freq"]
        if not items:
            out[c["control_id"]] = {"latest": None, "age": None, "limit": limit, "state": "none", "items": 0}
            continue
        age = (AS_OF - items[0]["date"]).days
        out[c["control_id"]] = {"latest": items[0]["collected_on"], "age": age, "limit": limit,
                                "state": "fresh" if age <= limit else "stale", "items": len(items)}
    return out


def scope_cover(ob_classes: set, ct_classes: set) -> str:
    """'full' when the control's scope includes every class the obligation applies to, else 'partial'."""
    return "full" if ob_classes <= ct_classes else "partial"


def derive_status(pairs: dict, fresh: dict) -> tuple:
    """pairs: control_id -> 'full' | 'partial'. Returns (status, driving control ids).

    UNCOVERED: no control. COVERED: a full-scope control with fresh evidence. STALE: a full-scope
    control exists but none has fresh evidence. PARTIAL: only partial-scope controls.
    """
    if not pairs:
        return "UNCOVERED", []
    full = sorted(c for c, v in pairs.items() if v == "full")
    if full:
        fresh_full = [c for c in full if fresh[c]["state"] == "fresh"]
        return ("COVERED", fresh_full) if fresh_full else ("STALE", full)
    return "PARTIAL", sorted(pairs)


def truth_statuses(data: dict) -> dict:
    """The generator's answer: obligation_id -> (status, driving controls), from truth_map.csv."""
    return {o["obligation_id"]: derive_status(data["truth_by_ob"].get(o["obligation_id"], {}), data["fresh"])
            for o in data["obligations"]}


def status_ok(pred: tuple, truth: tuple) -> bool:
    """Right status and, unless UNCOVERED, at least one control that really drives that status."""
    if pred[0] != truth[0]:
        return False
    return pred[0] == "UNCOVERED" or bool(set(pred[1]) & set(truth[1]))


# ---------------------------------------------------------------------------
# Step 1 measures
# ---------------------------------------------------------------------------
def summarize(data: dict) -> dict:
    obs = data["obligations"]
    frameworks = list(dict.fromkeys(o["framework"] for o in obs))
    fw_themes = {fw: {o["theme"] for o in obs if o["framework"] == fw} for fw in frameworks}
    theme_fw = defaultdict(set)
    theme_obs = defaultdict(list)
    for o in obs:
        theme_fw[o["theme"]].add(o["framework"])
        theme_obs[o["theme"]].append(o["obligation_id"])
    shared = {t for t, fws in theme_fw.items() if len(fws) > 1}
    rows = []
    for fw in frameworks:
        n = sum(1 for o in obs if o["framework"] == fw)
        rows.append({"framework": fw, "short": FRAMEWORK_SHORT[fw], "obligations": n, "themes": len(fw_themes[fw]),
                     "shared_themes": len(fw_themes[fw] & shared)})
    n_ob, n_theme = len(obs), len(theme_fw)
    return {
        "frameworks": frameworks, "rows": rows, "obligations": n_ob, "themes": n_theme,
        "shared_themes": len(shared), "shared_obligations": sum(len(theme_obs[t]) for t in shared),
        "requests_per_framework": n_ob, "requests_per_theme": n_theme,
        "repeat_requests": n_ob - n_theme, "repeat_pct": round((n_ob - n_theme) / n_ob * 100, 1),
        "theme_rows": sorted(({"theme": t, "frameworks": len(theme_fw[t]), "obligations": len(theme_obs[t])}
                              for t in theme_fw), key=lambda r: (-r["frameworks"], -r["obligations"], r["theme"])),
        "controls": len(data["controls"]), "evidence_items": len(data["evidence"]),
        "as_of": AS_OF.isoformat(),
    }


def main() -> None:
    data = load_all()
    s = summarize(data)
    print("STEP 1 - Before ControlMap: one obligation list per framework")
    print("  (synthetic data: obligation statements are paraphrases written for this exercise, not the text of any rule)")
    print()
    print("ASSUMPTIONS (definitions used for the count):")
    print("  R1  answered on its own, each framework sends one evidence request per obligation row")
    print("  R2  answered once per distinct theme, the bank sends one request per theme")
    print()
    print("FRAMEWORK LISTS (each answered on its own)")
    print(f"  {'framework':<32} {'obligations':>11} {'themes':>7} {'themes also in another list':>29}")
    for r in s["rows"]:
        print(f"  {r['framework']:<32} {r['obligations']:>11} {r['themes']:>7} {r['shared_themes']:>29}")
    print()
    print("THEMES ASKED BY MORE THAN ONE FRAMEWORK")
    print(f"  {'theme':<34} {'frameworks':>10} {'obligations':>12}")
    for r in s["theme_rows"]:
        if r["frameworks"] > 1:
            print(f"  {r['theme']:<34} {r['frameworks']:>10} {r['obligations']:>12}")
    print()
    print("RESULT")
    w = 46

    def line(label: str, value: str) -> None:
        print(f"  {label:<{w}}{value}")

    line(f"Obligations across {len(s['frameworks'])} frameworks:", f"{s['obligations']}")
    line("Distinct themes:", f"{s['themes']}")
    line("Themes asked by more than one framework:", f"{s['shared_themes']} (covering {s['shared_obligations']} of {s['obligations']} obligations)")
    line("Evidence requests, each framework alone:", f"{s['requests_per_framework']} (rule R1)")
    line("Evidence requests, once per theme:", f"{s['requests_per_theme']} (rule R2)")
    line("Requests that repeat a theme already asked:", f"{s['repeat_requests']} of {s['requests_per_framework']} ({s['repeat_pct']}%)")
    line("The register behind the lists:", f"{s['controls']} controls and {s['evidence_items']} evidence items as of {s['as_of']};")
    line("", "the lists carry no control scope and no evidence date.")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_01_framework_lists.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["framework", "obligations", "themes", "shared_themes"], lineterminator="\n")
        w.writeheader()
        for r in s["rows"]:
            w.writerow({k: r[k] for k in ("framework", "obligations", "themes", "shared_themes")})
    (OUT_DIR / "step_01_summary.json").write_text(
        json.dumps({k: v for k, v in s.items() if k not in ("rows", "theme_rows")}, indent=2), encoding="utf-8")
    print("\nWrote step_01_framework_lists.csv and step_01_summary.json in src/out/")


if __name__ == "__main__":
    main()
