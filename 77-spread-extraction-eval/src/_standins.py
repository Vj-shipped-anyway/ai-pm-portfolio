"""Two stand-in extractors for the harness to score. They are rules, not a model.

A real model drifts for reasons these rules do not have. What carries over to a real model is the
harness: the same documents, the same field-level scoring, the same gate.

    fixed_label   written against one layout (plain_two_column): exact label text, the first two
                  numbers on the line are the current and the prior period, nothing else is read.
    alias_aware   written after reading the error classes fixed_label produced on the other four
                  development layouts: a scale header, header years for column order, parentheses and
                  dashes, label aliases, wrapped labels, footnote markers, dot leaders and a balance
                  sheet printed in two halves. It still takes the first two numbers after the label,
                  so a column of note numbers in front of the values defeats it.

Both take the text of one statement and return {(field, period): int}. A field they cannot read is
absent from the result.
"""
from __future__ import annotations

import re

# label (as printed in the layout it was written against) -> field
_FIXED = {"revenue": "revenue", "cost of sales": "cost_of_sales", "gross profit": "gross_profit",
          "operating expenses": "operating_expenses", "operating income": "operating_income",
          "interest expense": "interest_expense", "income before tax": "pretax_income", "income tax": "income_tax",
          "net income": "net_income", "cash": "cash", "accounts receivable": "accounts_receivable",
          "inventory": "inventory", "total current assets": "total_current_assets",
          "fixed assets, net": "fixed_assets_net", "total assets": "total_assets", "accounts payable": "accounts_payable",
          "short-term debt": "short_term_debt", "total current liabilities": "total_current_liabilities",
          "long-term debt": "long_term_debt", "total liabilities": "total_liabilities", "total equity": "total_equity",
          "total liabilities and equity": "total_liabilities_and_equity"}

_ALIAS_TEXT = {
    "revenue": ("Revenue", "Net sales"),
    "cost_of_sales": ("Cost of sales", "Cost of goods sold"),
    "gross_profit": ("Gross profit", "Gross margin"),
    "operating_expenses": ("Operating expenses", "Selling, general and administrative expenses"),
    "operating_income": ("Operating income", "Operating profit"),
    "interest_expense": ("Interest expense", "Finance costs"),
    "pretax_income": ("Income before tax", "Profit before taxation"),
    "income_tax": ("Income tax", "Taxation"),
    "net_income": ("Net income", "Profit for the year"),
    "cash": ("Cash", "Cash and cash equivalents"),
    "accounts_receivable": ("Accounts receivable", "Trade receivables"),
    "inventory": ("Inventory", "Inventories"),
    "total_current_assets": ("Total current assets",),
    "fixed_assets_net": ("Fixed assets, net", "Property, plant and equipment, net"),
    "total_assets": ("Total assets",),
    "accounts_payable": ("Accounts payable", "Trade payables"),
    "short_term_debt": ("Short-term debt", "Bank borrowings, current"),
    "total_current_liabilities": ("Total current liabilities",),
    "long_term_debt": ("Long-term debt", "Bank borrowings, non-current"),
    "total_liabilities": ("Total liabilities",),
    "total_equity": ("Total equity", "Shareholders' equity"),
    "total_liabilities_and_equity": ("Total liabilities and equity", "Total liabilities and shareholders' equity"),
}

_LABEL_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z ,'&-]*?)\s{2,}(.*)$")
_PLAIN_NUM = re.compile(r"-?\d[\d,]{0,15}")

_NUM = re.compile(r"(?<![\w,.])(?:\$\s?)?(\()?(-)?(\d{1,3}(?:,\d{3})+|\d{1,15})(\))?(?![\w,])|(?<!\S)[—–-](?!\S)")
_YEARS = re.compile(r"^\s*(?:notes?\s+)?((?:19|20)\d\d(?:\s+(?:19|20)\d\d)+)\s*$", re.I)
_LEADERS = re.compile(r"\.{2,}")
_FOOTNOTE = re.compile(r"(?<=[A-Za-z]) \(\d{1,2}\)(?=\s)")
_GAP = re.compile(r"(?<=[\d)])\s{3,}(?=[A-Za-z])")
_SCALE = re.compile(r"\bin\s+(thousands|millions)\b", re.I)


def _norm(label: str) -> str:
    s = re.sub(r"[^a-z0-9 ]+", " ", label.lower().replace("’", "'"))
    return " ".join(s.split())


_ALIASES = {_norm(text): field for field, texts in _ALIAS_TEXT.items() for text in texts}


def _int(token: str) -> int:
    return int(token.replace(",", ""))


def fixed_label(text: str) -> dict:
    out = {}
    for line in text.split("\n"):
        m = _LABEL_LINE.match(line)
        if not m:
            continue
        field = _FIXED.get(m.group(1).lower())
        nums = _PLAIN_NUM.findall(m.group(2))
        if field is None or len(nums) < 2 or (field, "current") in out:
            continue
        out[(field, "current")] = _int(nums[0])
        out[(field, "prior")] = _int(nums[1])
    return out


def _value(m, scale: int) -> int:
    if m.group(3) is None:
        return 0
    v = _int(m.group(3)) * scale
    return -v if m.group(1) or m.group(2) else v


def alias_aware(text: str) -> dict:
    found = _SCALE.search(text)
    scale = 1 if not found else 1000 if found.group(1).lower() == "thousands" else 1_000_000
    order = ("current", "prior")
    pending = ""
    out = {}
    for raw in text.split("\n"):
        header = _YEARS.match(raw)
        if header:
            years = [int(y) for y in header.group(1).split()]
            order = ("current", "prior") if years[0] >= years[1] else ("prior", "current")
            pending = ""
            continue
        line = _FOOTNOTE.sub("", _LEADERS.sub(" ", raw))
        previous, pending = pending, ""
        for seg in _GAP.split(line):
            tokens = list(_NUM.finditer(seg))
            if not tokens:
                pending = _norm(seg)
                continue
            label = _norm(seg[:tokens[0].start()])
            field = _ALIASES.get(label) or (_ALIASES.get(_norm(previous + " " + label)) if previous else None)
            if field is None or len(tokens) < 2 or (field, order[0]) in out:
                continue
            out[(field, order[0])] = _value(tokens[0], scale)
            out[(field, order[1])] = _value(tokens[1], scale)
    return out


EXTRACTORS = {"fixed_label": fixed_label, "alias_aware": alias_aware}
