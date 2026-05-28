"""
Step 1 — Before defense: a raw LLM endpoint behind a thin Flask wrapper.

This is what happens today at most BFSI shops that have stood up an
internal copilot without a gateway in front of it. The LLM endpoint
accepts user input, dutifully concatenates it with the retrieved
context, and follows whatever instruction it finds in the context
window — regardless of whether the instruction came from the banker
or from a malicious document the banker happens to be reading.

This script does NOT actually call a foundation model. It simulates
the deterministic "raw LLM" behavior — the model follows every
instruction it sees. That is the worst-case baseline. Catch rate ≈ 0%.

The point: name the bleed in numbers. 100 attacks, 0 caught. Plus 200
legitimate prompts allowed correctly (because there is no filter to
trip). The defense-in-depth story in Steps 2-4 is what we'd build to
fix this.

Run:
    python step_01_no_defense.py

Output:
  - prints per-class catch rate (will be 0%)
  - writes src/out/step_01_attack_outcomes.csv with one row per attack
  - writes src/out/step_01_summary.json
"""

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


def load_corpus(name: str) -> list[dict]:
    with open(DATA_DIR / name) as f:
        return list(csv.DictReader(f))


def raw_llm_response(attack_text: str) -> dict:
    """Simulates a defenseless LLM endpoint.

    Real production behavior on a defenseless endpoint: model follows every
    instruction in its context window. We encode that as: every attack
    succeeds (the gateway returns 'executed') and zero are caught.

    Note: this is a deterministic simulation, not a real model call. The
    purpose is to print the catch-rate floor (0%), not to evaluate any
    specific foundation model.
    """
    return {
        "blocked": False,
        "reason": "no_defense_layer",
        "response_excerpt": "model_followed_instruction_in_context",
    }


def main():
    print("\n" + "=" * 80)
    print("Step 1 — Raw LLM endpoint with no defense layer")
    print("=" * 80)
    print()
    print("Scenario: an internal RM copilot is deployed straight onto a foundation")
    print("model endpoint. No input sanitization. No retrieval scanning. No tool")
    print("gate. No egress filter. The model follows every instruction it sees.")
    print()
    print("This is the worst-case baseline. Catch rate ≈ 0%. FP rate ≈ 0% (no")
    print("filter to trip).")
    print()

    attacks = load_corpus("attack_corpus.csv")
    legit = load_corpus("legitimate_prompts.csv")

    outcomes = []
    blocked = 0
    by_class: dict[str, dict[str, int]] = {}
    for atk in attacks:
        verdict = raw_llm_response(atk["attack_text"])
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
            "expected": atk["expected_block"],
            "got_action": "block" if verdict["blocked"] else "allow",
            "outcome": "BLOCKED" if verdict["blocked"] else "PASSED_THROUGH",
            "reason": verdict["reason"],
        })

    # Legitimate prompts — every one passes through (there is no filter).
    legit_outcomes = []
    legit_fp = 0
    for p in legit:
        legit_outcomes.append({
            "prompt_id": p["prompt_id"],
            "expected": p["expected_action"],
            "got_action": "allow",
            "outcome": "ALLOWED",
        })
        if p["expected_action"] != "allow":
            legit_fp += 1

    # Print per-class table
    print("Per-attack-class catch rate")
    print("-" * 80)
    print(f"  {'Attack class':<30} {'Caught':>10} {'Total':>10} {'Catch %':>10}")
    for cls, stats in by_class.items():
        rate = (stats["caught"] / stats["total"] * 100) if stats["total"] else 0
        print(f"  {cls:<30} {stats['caught']:>10} {stats['total']:>10} {rate:>9.1f}%")
    print("-" * 80)
    total = sum(s["total"] for s in by_class.values())
    print(f"  {'TOTAL':<30} {blocked:>10} {total:>10} {blocked/total*100:>9.1f}%")
    print()

    fp_rate = legit_fp / len(legit) * 100 if legit else 0
    print(f"Legitimate-prompt corpus ({len(legit)} rows): "
          f"{len(legit) - legit_fp} allowed, {legit_fp} blocked, FP rate {fp_rate:.1f}%")
    print()
    print("Modeled exposure on a defenseless internal copilot")
    print("-" * 80)
    print("  - Every direct injection is a system-prompt leak.")
    print("  - Every indirect injection (in a retrieved customer doc) is a")
    print("    potential exfiltration.")
    print("  - Every tool call is honored without sender validation.")
    print("  - Single successful exfiltration = customer-data breach +")
    print("    regulator disclosure (GLBA, state breach laws) + brand event.")
    print()
    print("This is the bleed Steps 2-4 are here to compress.")
    print()

    # Write outputs
    out_csv = OUT_DIR / "step_01_attack_outcomes.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(outcomes[0].keys()))
        w.writeheader()
        w.writerows(outcomes)

    out_legit_csv = OUT_DIR / "step_01_legitimate_outcomes.csv"
    with open(out_legit_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(legit_outcomes[0].keys()))
        w.writeheader()
        w.writerows(legit_outcomes)

    summary = {
        "stage": "step_01_no_defense",
        "attacks_total": total,
        "attacks_caught": blocked,
        "catch_rate_pct": round(blocked / total * 100, 2),
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
    out_json = OUT_DIR / "step_01_summary.json"
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_legit_csv}")
    print(f"Wrote: {out_json}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
