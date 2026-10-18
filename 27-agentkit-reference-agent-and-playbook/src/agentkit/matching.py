"""Name and account matching used by S05 and S06. Plain rules, standard library only.

Design parameters (not in the build-brief shape, so they live here and in ARCHITECTURE.md):
  CLOSE_AT      similarity at or above this is a close match
  AMBIGUOUS_AT  similarity at or above this, below CLOSE_AT, is ambiguous and goes to a person
  HIT_AT        watch-list similarity at or above this is a hit
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

CLOSE_AT = 0.90
AMBIGUOUS_AT = 0.65
HIT_AT = 0.85

LEGAL_TOKENS = frozenset({"ltd", "limited", "llc", "inc", "incorporated", "corp", "corporation", "gmbh", "plc",
                          "co", "company", "sa", "ag", "bv", "lp", "llp"})
# Five abbreviations. The generator uses eight, so three variants are unknown to this table on purpose.
ABBREVIATIONS = {"svcs": "services", "inds": "industries", "dist": "distribution", "ent": "enterprises",
                 "sys": "systems"}

EXACT, CLOSE, AMBIGUOUS, MISMATCH = "EXACT", "CLOSE", "AMBIGUOUS", "MISMATCH"


def normalize_name(name: str) -> str:
    """Lower-case, strip punctuation, expand known abbreviations, drop legal-form words, sort tokens."""
    text = (name or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    toks = [ABBREVIATIONS.get(t, t) for t in text.split()]
    toks = [t for t in toks if t not in LEGAL_TOKENS]
    return " ".join(sorted(toks))


def name_similarity(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na and not nb:
        return 0.0
    if na == nb:
        return 1.0
    return round(SequenceMatcher(None, na, nb).ratio(), 4)


def classify_name_match(a: str, b: str, close_at: float = CLOSE_AT, ambiguous_at: float = AMBIGUOUS_AT):
    """Return (class, score). EXACT means equal after normalization."""
    score = name_similarity(a, b)
    if score >= 1.0:
        return EXACT, score
    if score >= close_at:
        return CLOSE, score
    if score >= ambiguous_at:
        return AMBIGUOUS, score
    return MISMATCH, score


def luhn_check_digit(body: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def luhn_ok(account: str) -> bool:
    """Check digit test for the synthetic 10-digit account numbers."""
    s = account or ""
    if len(s) < 2 or not s.isdigit():
        return False
    return luhn_check_digit(s[:-1]) == s[-1]


def account_format_ok(account: str) -> bool:
    return bool(account) and account.isdigit() and len(account) == 10


def bank_code_ok(code: str) -> bool:
    return bool(re.fullmatch(r"SYNB\d{4}", code or ""))
