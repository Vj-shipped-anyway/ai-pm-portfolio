"""A stand-in checker for the demo ledger, with two rule sets so the answer key can show whether a change helped.

  naive   what a first version usually looks like: same account, merchant, amount and day means duplicate;
          any amount over 1000 is high; posted before the purchase day is backdated; the words "ignore"
          and "previous" close together mean an injected instruction
  tuned   duplicate means the same reference seen twice; high means over a ceiling per merchant;
          the injection pattern needs the words "previous instructions"

The utilities ceiling is set a little under the top of the demo's utilities amounts, so the key has a false
alarm to find. The ceilings are not read from the spec: the checker and the generator share nothing but the
column names. The author is the same, which is why the scores in this project are a ceiling.
"""
from __future__ import annotations

import re

CEILING = {"grocery": 400.0, "fuel": 200.0, "pharmacy": 200.0, "transit": 80.0, "utilities": 200.0, "rent": 3000.0}
INJECTION = {"naive": re.compile(r"ignore\b.{0,25}previous", re.I),
             "tuned": re.compile(r"ignore\b.{0,25}previous\s+instructions", re.I)}


def flag_rows(rows: list, level: str) -> dict:
    """Return {row_id: [rule names]} for the rows the checker flags. rows are dicts of text; level is naive or tuned."""
    if level not in INJECTION:
        raise ValueError("level must be naive or tuned")
    flagged, seen = {}, set()
    for r in rows:
        key = (r["account_id"], r["merchant"], r["amount"], r["day"]) if level == "naive" else r["ref"]
        rules = []
        if key in seen:
            rules.append("duplicate")
        if float(r["amount"]) > (1000.0 if level == "naive" else CEILING.get(r["merchant"], 1000.0)):
            rules.append("amount_high")
        if int(r["posted_day"]) < int(r["day"]):
            rules.append("backdated")
        if INJECTION[level].search(r["memo"]):
            rules.append("injection")
        seen.add(key)
        if rules:
            flagged[int(r["row_id"])] = rules
    return flagged
