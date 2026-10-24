"""Step 3 - Where each cheap rule fails when used alone.

Two rules, each with one idea:
  rule-word rule   BLOCK when a removed or changed line contains never, must, always, do not or don't
  tool-name rule   REVIEW when the set of tool names mentioned in the prompt changes
Neither reads the meaning of the change. The truth is known, so each rule is scored on the same pull
requests. KNOWN LIMIT, left in on purpose: some planted risky edits carry no rule word, no tool name and
no number (a one-word swap in a long sentence). They pass both rules here, and step 4 does not catch
them either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
import difflib
import re
from collections import Counter

from common import load_cases, load_world

cases = load_cases()
catalogue, _probes = load_world()
RULE_WORDS = re.compile(r"\b(?:never|must|always|do not|don't)\b", re.I)


def removed_lines(c) -> list:
    diff = difflib.unified_diff(c["old"].splitlines(), c["new"].splitlines(), lineterm="", n=0)
    return [ln[1:] for ln in diff if ln.startswith("-") and not ln.startswith("---") and not ln[1:].lstrip().startswith("#")]


def rule_word_rule(c) -> str:
    return "BLOCK" if any(RULE_WORDS.search(ln) for ln in removed_lines(c)) else "ALLOW"


def tool_names(text) -> set:
    return {n for n in catalogue if n in text}


def tool_name_rule(c) -> str:
    return "REVIEW" if tool_names(c["old"]) != tool_names(c["new"]) else "ALLOW"


def score(name, decide):
    got = {c["pr_id"]: decide(c) for c in cases}
    high = [c for c in cases if c["truth"] == "high"]
    med = [c for c in cases if c["truth"] == "medium"]
    low = [c for c in cases if c["truth"] == "low"]
    print(f"  {name}")
    print(f"    high-risk flagged: {sum(1 for c in high if got[c['pr_id']] != 'ALLOW')} of {len(high)}")
    print(f"    medium-risk flagged: {sum(1 for c in med if got[c['pr_id']] != 'ALLOW')} of {len(med)}")
    print(f"    harmless pull requests flagged: {sum(1 for c in low if got[c['pr_id']] != 'ALLOW')} of {len(low)}")
    return got


print("STEP 3 - each rule alone")
by_word = score("rule-word rule", rule_word_rule)
by_tool = score("tool-name rule", tool_name_rule)
risky = [c for c in cases if c["truth"] != "low"]
missed = [c for c in risky if by_word[c["pr_id"]] == "ALLOW" and by_tool[c["pr_id"]] == "ALLOW"]
print(f"  risky pull requests that pass both rules: {len(missed)} of {len(risky)}")
print("  by planted edit: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in missed).items())))
print("  A rule word says a rule moved, not which way; a tool name says a grant moved, not whether it writes. Scope, tone, numbers and routing pass.")
