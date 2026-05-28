"""
Step 2 — Basic regex/keyword input filter.

This is what "we have prompt-injection defense" usually means at a
BFSI shop today: a list of suspicious strings (`ignore previous`,
`disregard`, `system prompt`, `DAN`, `jailbreak`, ...) and a regex
gate that blocks any user input matching one of them.

The catch rate floor of basic regex/keyword filtering on novel
attacks is well-published: roughly 30-50% on OWASP-LLM01-style
suites. The false-positive rate is also non-trivial — banker
queries that legitimately contain words like "previous quarter,"
"override approval," or "redacted version" trip the filter and
get blocked.

This script encodes the basic filter and runs it against:
  - attack_corpus.csv     -> measure catch rate
  - legitimate_prompts.csv -> measure false-positive rate

Expected: ~30-50% catch on attacks, ~10-15% FP on legit.

Run:
    python step_02_regex_keyword_filter.py

Output:
  - prints per-class catch rate and overall FP rate
  - writes src/out/step_02_attack_outcomes.csv
  - writes src/out/step_02_legitimate_outcomes.csv
  - writes src/out/step_02_summary.json
"""

import csv
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


# A representative basic blocklist. Names what a typical BFSI shop's
# "we have prompt-injection defense" actually does: a small regex pack
# tuned by hand. The list is deliberately incomplete — that is the point.
BASIC_TRIGGERS = [
    r"\bignore (the )?(previous|prior|all)\b.*\binstruction",
    r"\bdisregard (all )?(previous|prior)\b",
    r"\bsystem prompt\b",
    r"\bjailbreak\b",
    r"\bDAN\b",
    r"\bdeveloper mode\b",
    r"\boverride\b",
    r"\bunrestricted mode\b",
    r"\bend of system prompt\b",
    r"\bforget\b",
    r"\battacker@\S+",
    r"\bevil\.[a-z]+\b",
    r"\bbad\.com\b",
    r"\bpretend\b",
    r"\broleplay\b",
    r"\bhypothetical(ly)?\b",
    r"\bSSN\b",
    r"\bredacted\b",
    r"\bprevious\b",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in BASIC_TRIGGERS]


def basic_filter(text: str) -> dict:
    """Returns {blocked: bool, matched_pattern: str | None}."""
    for pat in COMPILED:
        if pat.search(text):
            return {"blocked": True, "matched_pattern": pat.pattern}
    return {"blocked": False, "matched_pattern": None}


def load_corpus(name: str) -> list[dict]:
    with open(DATA_DIR / name) as f:
        return list(csv.DictReader(f))


def main():
    print("\n" + "=" * 80)
    print("Step 2 — Basic regex/keyword input filter")
    print("=" * 80)
    print()
    print(f"Filter: {len(BASIC_TRIGGERS)} hand-tuned regex/keyword triggers.")
    print("Representative of what most BFSI shops' 'we have prompt-injection")
    print("defense' actually means today. Public OWASP-LLM01 benchmarks for")
    print("this approach: ~30-50% catch rate on attacks, ~10-15% FP rate on")
    print("legitimate queries that happen to contain trigger words.")
    print()

    attacks = load_corpus("attack_corpus.csv")
    legit = load_corpus("legitimate_prompts.csv")

    # === Attacks ===
    outcomes = []
    blocked = 0
    by_class: dict[str, dict[str, int]] = {}
    for atk in attacks:
        verdict = basic_filter(atk["attack_text"])
        cls = atk["attack_class"]
        by_class.setdefault(cls, {"total": 0, "caught": 0})
        by_class[cls]["total"] += 1
        if verdict["blocked"]:
            blocked += 1
            by_class[cls]["caught"] += 1
        outcomes.append({
            "attack_id": atk["attack_id"],
            "attack_class": cls,
            "severity": atk["severity"],
            "got_action": "block" if verdict["blocked"] else "allow",
            "outcome": "BLOCKED" if verdict["blocked"] else "MISSED",
            "matched_pattern": verdict["matched_pattern"] or "",
        })

    # === Legitimate ===
    legit_outcomes = []
    legit_fp = 0
    for p in legit:
        verdict = basic_filter(p["prompt_text"])
        legit_outcomes.append({
            "prompt_id": p["prompt_id"],
            "intent": p["intent"],
            "got_action": "block" if verdict["blocked"] else "allow",
            "outcome": "FALSE_POSITIVE_BLOCKED" if verdict["blocked"] else "ALLOWED",
            "matched_pattern": verdict["matched_pattern"] or "",
        })
        if verdict["blocked"]:
            legit_fp += 1

    # === Print ===
    print("Per-attack-class catch rate")
    print("-" * 80)
    print(f"  {'Attack class':<30} {'Caught':>10} {'Total':>10} {'Catch %':>10}")
    for cls in ["direct_injection", "indirect_injection", "tool_call_abuse",
                "egress_attack", "cross_session_leak", "jailbreak_roleplay"]:
        s = by_class.get(cls, {"caught": 0, "total": 0})
        rate = (s["caught"] / s["total"] * 100) if s["total"] else 0
        print(f"  {cls:<30} {s['caught']:>10} {s['total']:>10} {rate:>9.1f}%")
    print("-" * 80)
    total = sum(s["total"] for s in by_class.values())
    overall_pct = blocked / total * 100 if total else 0
    print(f"  {'TOTAL':<30} {blocked:>10} {total:>10} {overall_pct:>9.1f}%")
    print()

    fp_rate = legit_fp / len(legit) * 100 if legit else 0
    print(f"Legitimate-prompt corpus ({len(legit)} rows): "
          f"{len(legit) - legit_fp} allowed, {legit_fp} blocked → FP rate {fp_rate:.1f}%")
    print()

    # Sample of FPs — banker queries the filter wrongly blocked
    fp_samples = [r for r in legit_outcomes if r["outcome"] == "FALSE_POSITIVE_BLOCKED"][:5]
    if fp_samples:
        print("Sample false positives (banker queries blocked unnecessarily):")
        for r in fp_samples:
            # find prompt text
            text = next(p["prompt_text"] for p in legit if p["prompt_id"] == r["prompt_id"])
            print(f"  - {r['prompt_id']} [{r['intent']}] : matched /{r['matched_pattern']}/")
            print(f"    → \"{text[:100]}{'...' if len(text) > 100 else ''}\"")
        print()

    # Note the deficiencies still open
    print("Where this still breaks (Step 3 names them):")
    print("  - Indirect injection in retrieved documents — the filter never")
    print("    sees the retrieved content; it inspects only user input.")
    print("  - Encoded / obfuscated attacks — base64, rot-13, pig latin slip")
    print("    every keyword.")
    print("  - Multi-turn drift — first prompt is benign, fourth turn flips.")
    print("  - Tool-call abuse — model invokes an outbound tool with attacker-")
    print("    controlled args; the filter is on the input path, not the tool")
    print("    boundary.")
    print("  - Egress channel — model's response contains exfil payloads; the")
    print("    filter never inspects responses.")
    print("  - Cross-session leakage — no concept of session boundary at all.")
    print()

    # === Writes ===
    out_csv = OUT_DIR / "step_02_attack_outcomes.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(outcomes[0].keys()))
        w.writeheader()
        w.writerows(outcomes)
    out_legit_csv = OUT_DIR / "step_02_legitimate_outcomes.csv"
    with open(out_legit_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(legit_outcomes[0].keys()))
        w.writeheader()
        w.writerows(legit_outcomes)

    summary = {
        "stage": "step_02_regex_keyword_filter",
        "attacks_total": total,
        "attacks_caught": blocked,
        "catch_rate_pct": round(overall_pct, 2),
        "legitimate_total": len(legit),
        "false_positives": legit_fp,
        "false_positive_rate_pct": round(fp_rate, 2),
        "per_class": {
            cls: {
                "total": s["total"],
                "caught": s["caught"],
                "catch_rate_pct": round(s["caught"] / s["total"] * 100, 1) if s["total"] else 0,
            }
            for cls, s in by_class.items()
        },
    }
    out_json = OUT_DIR / "step_02_summary.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_legit_csv}")
    print(f"Wrote: {out_json}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
