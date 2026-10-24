"""Produce the synthetic data for project 51: 28 credit memos in markdown, each written from a made-up
three-year spread, with 308 planted figures and the truth about each one.

Everything is seeded, so the files are byte-for-byte reproducible. The truth of a figure comes from how
it was built (the true value written at the precision shown, or altered on purpose), not from the checker,
and the arithmetic here uses exact fractions where memo_tieout.py uses decimals. Some kinds are hard on
purpose. Fine figures that could raise a false alarm: a one-decimal million figure sitting exactly on a
rounding boundary, proposed terms and ownership shares that are not in any spread, and years, counts and
section numbers in the prose. Wrong figures the rules should miss: a tie whose number and tag agree but
whose sentence names another line, and a figure written in words or with a USD prefix, which the reader
does not parse.

Run (from data/):  python3 _generate.py
Writes:  spreads.csv, memos.json, truth.csv, example_memo.md, example_spread.csv
"""
from __future__ import annotations

import csv
import json
import random
from fractions import Fraction

SEED = 51
N_MEMOS = 28
PERIODS = [("FY2022", "2022-12-31"), ("FY2023", "2023-12-31"), ("FY2024", "2024-12-31")]
BASE = ["revenue", "cogs", "opex", "depreciation", "interest_expense", "taxes", "net_income", "cash", "current_assets",
        "current_liabilities", "total_debt", "total_equity", "capex", "principal_payments"]

KIND_COUNTS = [
    ("exact_thousand", 30), ("million_rounded", 30), ("dollars_plain", 10), ("ratio_ok", 30), ("pct_ok", 30),
    ("growth_ok", 16), ("half_up_edge", 10), ("term_marked", 16), ("term_untagged", 12),
    ("typo", 14), ("wrong_period", 14), ("wrong_line", 12), ("unit_slip", 12), ("stale_denominator", 10),
    ("covenant_round", 10), ("growth_wrong", 8), ("bad_tag", 8), ("untied", 16),
    ("prose_tag_mismatch", 10), ("unparsed_form", 10),
]
OK_KINDS = {"exact_thousand", "million_rounded", "dollars_plain", "ratio_ok", "pct_ok", "growth_ok", "half_up_edge",
            "term_marked", "term_untagged"}

LABEL = {
    "revenue": "revenue", "cogs": "cost of goods sold", "opex": "operating expenses", "depreciation": "depreciation",
    "interest_expense": "interest expense", "taxes": "income taxes", "net_income": "net income", "cash": "cash",
    "current_assets": "current assets", "current_liabilities": "current liabilities", "total_debt": "total debt",
    "total_equity": "total equity", "capex": "capital expenditure", "principal_payments": "scheduled principal payments",
    "gross_profit": "gross profit", "ebitda": "EBITDA", "gross_margin_pct": "gross margin",
    "ebitda_margin_pct": "EBITDA margin", "net_margin_pct": "net margin", "revenue_growth_pct": "revenue growth",
    "debt_ebitda_x": "total debt to EBITDA", "current_ratio_x": "current ratio", "dscr_x": "debt service coverage",
    "debt_to_equity_x": "debt to equity",
}
MONEY = BASE + ["gross_profit", "ebitda"]
PCT = ["gross_margin_pct", "ebitda_margin_pct", "net_margin_pct", "revenue_growth_pct"]
XS = ["debt_ebitda_x", "current_ratio_x", "dscr_x", "debt_to_equity_x"]
GROUPS = {"money": MONEY, "pct": PCT, "x": XS}

FIRST = ["Harbor", "Cedar", "Copper", "Northgate", "Alder", "Granite", "Willow", "Lantern", "Marlow", "Tamsin", "Birchwell", "Quarry"]
SECOND = ["Quay", "Ridge", "Fold", "Mills", "Point", "Field", "Row", "Gate", "Bend", "Hollow"]
TRADE = ["Tooling", "Packaging", "Plastics", "Logistics", "Foods", "Textiles", "Electrical", "Signage", "Fasteners", "Coatings"]
BLURB = ["makes machined parts for equipment makers", "runs contract packaging lines", "moulds plastic components",
         "operates refrigerated delivery routes", "bakes and packs frozen bread", "weaves and finishes technical fabrics",
         "assembles switchgear panels", "makes illuminated signs", "supplies fasteners to repair shops", "applies industrial coatings"]


class Retry(Exception):
    """The draw could not satisfy a rule for this kind; draw again."""


# ---------------------------------------------------------------- exact arithmetic and text
def fixed(fr: Fraction, decimals: int) -> str:
    """fr rounded half away from zero to a number of decimals, as text with its sign."""
    n = int(abs(Fraction(fr)) * 10 ** decimals + Fraction(1, 2))
    body = f"{n // 10 ** decimals}.{n % 10 ** decimals:0{decimals}d}" if decimals else str(n)
    return ("-" if fr < 0 and n else "") + body


def commas(s: str) -> str:
    whole, _, frac = s.partition(".")
    return f"{int(whole):,}" + ("." + frac if frac else "")


def money(v, style: str) -> str:
    """v is in thousands of dollars."""
    if style == "thousand":
        return f"${commas(fixed(v, 0))} thousand"
    if style == "million1":
        return f"${commas(fixed(Fraction(v, 1000), 1))} million"
    if style == "million2":
        return f"${commas(fixed(Fraction(v, 1000), 2))} million"
    return f"${commas(fixed(Fraction(v * 1000), 0))}"


def figure(kind: str, value, style) -> str:
    if kind == "money":
        return money(value, style)
    return fixed(value, style) + ("%" if kind == "pct" else "x")


def cap(s: str) -> str:
    return s[0].upper() + s[1:]


# ---------------------------------------------------------------- spreads
def _ebitda(s, i):
    return s["revenue"][i] - s["cogs"][i] - s["opex"][i]


METRIC = {
    "gross_profit": ("money", lambda s, i: s["revenue"][i] - s["cogs"][i]),
    "ebitda": ("money", _ebitda),
    "gross_margin_pct": ("pct", lambda s, i: Fraction(100 * (s["revenue"][i] - s["cogs"][i]), s["revenue"][i])),
    "ebitda_margin_pct": ("pct", lambda s, i: Fraction(100 * _ebitda(s, i), s["revenue"][i])),
    "net_margin_pct": ("pct", lambda s, i: Fraction(100 * s["net_income"][i], s["revenue"][i])),
    "revenue_growth_pct": ("pct", lambda s, i: (Fraction(s["revenue"][i], s["revenue"][i - 1]) - 1) * 100),
    "debt_ebitda_x": ("x", lambda s, i: Fraction(s["total_debt"][i], _ebitda(s, i))),
    "current_ratio_x": ("x", lambda s, i: Fraction(s["current_assets"][i], s["current_liabilities"][i])),
    "dscr_x": ("x", lambda s, i: Fraction(_ebitda(s, i), s["interest_expense"][i] + s["principal_payments"][i])),
    "debt_to_equity_x": ("x", lambda s, i: Fraction(s["total_debt"][i], s["total_equity"][i])),
}


def kind_of(name: str) -> str:
    return "money" if name in BASE else METRIC[name][0]


def value_of(s, name: str, i: int):
    return s[name][i] if name in BASE else METRIC[name][1](s, i)


def make_spread(rng) -> dict:
    """Three years of lines in thousands of dollars. Capital expenditure always ends in 50, so a one-decimal
    million figure for it sits exactly on a rounding boundary."""
    s = {k: [] for k in BASE}
    rev = rng.randint(18000, 90000)
    debt = None
    for i in range(3):
        if i:
            rev = rev * (1000 + rng.randint(-30, 140)) // 1000
        cogs = rev * rng.randint(550, 700) // 1000
        opex = rev * rng.randint(120, 200) // 1000
        ebitda = rev - cogs - opex
        dep = rev * rng.randint(20, 40) // 1000
        if debt is None:
            debt = ebitda * rng.randint(180, 420) // 100
        principal = debt * rng.randint(60, 120) // 1000
        interest = debt * rng.randint(50, 70) // 1000
        tax = max(0, (ebitda - dep - interest) * 25 // 100)
        cash = rev * rng.randint(40, 120) // 1000
        assets = cash + rev * rng.randint(120, 200) // 1000
        row = dict(revenue=rev, cogs=cogs, opex=opex, depreciation=dep, interest_expense=interest, taxes=tax,
                   net_income=ebitda - dep - interest - tax, cash=cash, current_assets=assets,
                   current_liabilities=assets * 1000 // rng.randint(1100, 1900), total_debt=debt,
                   total_equity=rev * rng.randint(250, 500) // 1000,
                   capex=(rev * rng.randint(20, 45) // 1000) // 100 * 100 + 50, principal_payments=principal)
        if row["net_income"] <= 0:
            raise Retry()
        for k in BASE:
            s[k].append(row[k])
        debt -= principal
    return s


def spread_rows(memo_id: str, s: dict, unit: str) -> list:
    out = []
    for name in BASE:
        for i, (period, end) in enumerate(PERIODS):
            v = s[name][i]
            text = str(v * 1000) if unit == "usd" else f"{v // 1000}.{v % 1000:03d}" if unit == "usd_millions" else str(v)
            out.append([memo_id, period, end, name, text, unit])
    return out


# ---------------------------------------------------------------- one planted figure
def pick(rng, group: str, growth_ok: bool = True):
    names = [n for n in GROUPS[group] if growth_ok or n != "revenue_growth_pct"]
    name = rng.choice(names)
    return name, rng.randint(1 if name == "revenue_growth_pct" else 0, 2)


def style_for(rng, kind: str):
    return rng.choice(["thousand", "million1", "million2", "dollars"]) if kind == "money" else rng.choice([1, 2]) if kind == "x" else 1


def differs(a: str, b: str) -> str:
    if a == b:
        raise Retry()
    return a


def mutate(rng, v: int) -> int:
    digits = list(str(v))
    if rng.random() < 0.5:
        i = rng.randrange(len(digits) - 1)
        digits[i], digits[i + 1] = digits[i + 1], digits[i]
    else:
        i = rng.randrange(1, len(digits))
        digits[i] = rng.choice([d for d in "0123456789" if d != digits[i]])
    out = int("".join(digits))
    if out == v or len(str(out)) != len(str(v)):
        raise Retry()
    return out


def mangle(name: str) -> str:
    """A near miss of a valid name: two letters swapped."""
    for i in range(len(name) - 1):
        if name[i] != name[i + 1] and name[i].isalpha() and name[i + 1].isalpha():
            out = name[:i] + name[i + 1] + name[i] + name[i + 2:]
            if out in BASE or out in METRIC:
                raise Retry()
            return out
    raise Retry()


def build_figure(rng, s: dict, kind: str) -> dict:
    """Returns {name, i, label, fig, tag (the target after spread:, or None for no mark), term (a term name or None), section}."""
    out = {"tag": None, "term": None, "section": "Performance and coverage"}

    def at(name, i, text, label=None, tag="same"):
        out.update(name=name, i=i, label=label or name, fig=text, section="Financial position" if kind_of(name) == "money" else out["section"])
        out["tag"] = f"{name}/{PERIODS[i][0]}" if tag == "same" else tag
        return out

    if kind in ("exact_thousand", "million_rounded", "dollars_plain", "ratio_ok", "pct_ok", "growth_ok", "untied",
                "unparsed_form", "half_up_edge"):
        group = {"exact_thousand": "money", "million_rounded": "money", "dollars_plain": "money", "ratio_ok": "x",
                 "pct_ok": "pct", "growth_ok": "pct", "half_up_edge": "money"}.get(kind) or rng.choice(["money", "pct", "x"])
        name, i = pick(rng, group, growth_ok=kind in ("growth_ok", "untied", "unparsed_form"))
        if kind == "growth_ok":
            name, i = "revenue_growth_pct", rng.randint(1, 2)
        if kind == "half_up_edge":
            name, i = "capex", rng.randint(1, 2)
        k = kind_of(name)
        style = {"exact_thousand": "thousand", "million_rounded": rng.choice(["million1", "million2"]), "dollars_plain": "dollars",
                 "half_up_edge": "million1"}.get(kind) or style_for(rng, k)
        v = value_of(s, name, i)
        if kind == "unparsed_form":
            words = {"money": [f"USD {fixed(Fraction(v, 1000), 1)}m", f"{fixed(Fraction(v, 1000), 1)} million dollars"],
                     "pct": [f"{fixed(v, 1)} percent", f"{fixed(v, 1)} per cent"],
                     "x": [f"{fixed(v, 1)} times", f"{fixed(v, 1)} turns"]}[k]
            at(name, i, rng.choice(words), tag=None)
        else:
            at(name, i, figure(k, v, style), tag=None if kind == "untied" else "same")
        return out
    if kind == "typo":
        name, i = pick(rng, "money")
        if name in ("ebitda", "gross_profit"):
            raise Retry()
        v = value_of(s, name, i)
        return at(name, i, money(mutate(rng, int(v)), "thousand"))
    if kind == "wrong_period":
        group = rng.choice(["money", "pct", "x"])
        name, i = pick(rng, group)
        j = rng.choice([x for x in range(3) if x != i and not (name == "revenue_growth_pct" and x == 0)])
        k = kind_of(name)
        style = style_for(rng, k)
        return at(name, i, differs(figure(k, value_of(s, name, j), style), figure(k, value_of(s, name, i), style)))
    if kind == "wrong_line":
        group = rng.choice(["money", "pct", "x"])
        name, i = pick(rng, group)
        other = rng.choice([n for n in GROUPS[group] if n != name and not (n == "revenue_growth_pct" and i == 0)])
        k = kind_of(name)
        style = style_for(rng, k)
        return at(name, i, differs(figure(k, value_of(s, other, i), style), figure(k, value_of(s, name, i), style)))
    if kind == "unit_slip":
        name, i = pick(rng, "money")
        v = value_of(s, name, i)
        if rng.random() < 0.5:
            text = f"${commas(fixed(v, 0))} million"
        else:
            text = money(v * rng.choice([10, Fraction(1, 10)]), "million1")
        return at(name, i, differs(text, money(v, "million1")))
    if kind == "stale_denominator":
        name, i = rng.choice(["debt_ebitda_x", "dscr_x"]), rng.randint(1, 2)
        old = Fraction(s["total_debt"][i], _ebitda(s, i - 1)) if name == "debt_ebitda_x" else \
            Fraction(_ebitda(s, i - 1), s["interest_expense"][i] + s["principal_payments"][i])
        style = rng.choice([1, 2])
        return at(name, i, differs(figure("x", old, style), figure("x", value_of(s, name, i), style)))
    if kind == "covenant_round":
        name, i = rng.choice(XS), rng.randint(0, 2)
        step = Fraction(1, 100) if name in ("current_ratio_x", "dscr_x") else Fraction(-1, 100)
        shown = Fraction(fixed(value_of(s, name, i), 2)) + step
        return at(name, i, figure("x", shown, 2))
    if kind == "growth_wrong":
        i = rng.randint(1, 2)
        if i == 2 and rng.random() < 0.5:
            wrong = (Fraction(s["revenue"][2], s["revenue"][0]) - 1) * 100
        else:
            wrong = (Fraction(_ebitda(s, i), _ebitda(s, i - 1)) - 1) * 100
        return at("revenue_growth_pct", i, differs(figure("pct", wrong, 1), figure("pct", value_of(s, "revenue_growth_pct", i), 1)))
    if kind == "bad_tag":
        variant = rng.choice(["line", "period", "form"])
        name, i = pick(rng, rng.choice(["money", "pct", "x"]), growth_ok=False)
        k = kind_of(name)
        text = figure(k, value_of(s, name, i), style_for(rng, k))
        if variant == "line":
            return at(name, i, text, tag=f"{mangle(name)}/{PERIODS[i][0]}")
        if variant == "period":
            return at(name, i, text, tag=f"{name}/{rng.choice(['FY2025', str(2022 + i)])}")
        wrong_kind = rng.choice([x for x in ("money", "pct", "x") if x != k])
        other, _ = pick(rng, wrong_kind, growth_ok=False)
        return at(name, i, figure(wrong_kind, value_of(s, other, i), style_for(rng, wrong_kind)))
    if kind == "prose_tag_mismatch":
        group = rng.choice(["money", "pct", "x"])
        name, i = pick(rng, group)
        other = rng.choice([n for n in GROUPS[group] if n != name and not (n == "revenue_growth_pct" and i == 0)])
        k = kind_of(name)
        return at(name, i, figure(k, value_of(s, name, i), style_for(rng, k)), label=other)
    raise ValueError(kind)


TERMS = [
    ("facility_amount", "Requested facility: {F} senior term loan.", lambda rng: f"${rng.choice(['2.5', '3.0', '4.0', '5.0', '7.5', '10.0', '12.5'])} million"),
    ("margin", "Pricing: base rate plus {F}.", lambda rng: f"{rng.choice(['2.25', '2.75', '3.25', '3.75'])}%"),
    ("min_coverage", "Minimum coverage covenant of {F}.", lambda rng: f"{rng.choice(['1.20', '1.25', '1.35'])}x"),
    ("sponsor_stake", "The sponsor owns {F} of the equity.", lambda rng: f"{rng.choice([40, 51, 60, 75, 80])}%"),
]
SENTENCES = ["{Cap} in {P} was {F}.", "For {P}, {label} came to {F}.", "The spread puts {label} at {F} in {P}."]


def line_for(rng, kind: str, spec: dict) -> dict:
    """The memo bullet for one figure: its text, the 1-based column where the figure starts, and its section."""
    if spec.get("term"):
        name, template = spec["term"][0], spec["term"][1]
        pre, post = template.split("{F}")
        fig = spec["fig"]
        marked = kind == "term_marked"
        line = "- " + pre + (f"[{fig}](term:{name})" if marked else fig) + post
        return {"line": line, "col": 2 + len(pre) + (1 if marked else 0) + 1, "fig": fig, "section": "Proposed terms"}
    label = LABEL[spec["label"]]
    pre, post = rng.choice(SENTENCES).format(Cap=cap(label), label=label, P=PERIODS[spec["i"]][0], F="{F}").split("{F}")
    tagged = spec["tag"] is not None
    markup = f"[{spec['fig']}](spread:{spec['tag']})" if tagged else spec["fig"]
    return {"line": "- " + pre + markup + post, "col": 2 + len(pre) + (1 if tagged else 0) + 1, "fig": spec["fig"],
            "section": spec["section"]}


def plant(rng, s: dict, kind: str) -> dict:
    for _ in range(80):
        try:
            if kind in ("term_marked", "term_untagged"):
                name, template, make = rng.choice(TERMS)
                spec = {"term": (name, template), "fig": make(rng)}
            else:
                spec = build_figure(rng, s, kind)
            return dict(line_for(rng, kind, spec), kind=kind, expected="ok" if kind in OK_KINDS else "flag")
        except Retry:
            continue
    raise RuntimeError(f"could not plant {kind}")


# ---------------------------------------------------------------- memos
def build_memo(rng, memo_id: str, name: str, blurb: str, s: dict, kinds: list) -> tuple:
    planted = [plant(rng, s, k) for k in kinds]
    lines = [f"# Credit memo: {name} ({memo_id})", "",
             f"{name} {blurb}. It was founded in {rng.randint(1994, 2016)} and operates {rng.randint(3, 22)} locations. "
             f"Amounts below come from the spread for FY2022 to FY2024.", ""]
    truth = []
    for section in ("Financial position", "Performance and coverage", "Proposed terms"):
        mine = [p for p in planted if p["section"] == section]
        if not mine:
            continue
        lines += [f"## {section}", ""]
        for p in mine:
            lines.append(p["line"])
            truth.append([memo_id, len(lines), p["col"], p["kind"], p["expected"], p["fig"]])
        lines.append("")
    lines += [f"Tenor is {rng.randint(3, 7)} years with quarterly amortization. The covenant package is in Section 4.2 and the next review falls in Q3.", ""]
    return "\n".join(lines), truth


EXAMPLE_SPREAD = {
    "revenue": [41200, 43850, 47320], "cogs": [27500, 29100, 31400], "opex": [7900, 8300, 8800],
    "depreciation": [1350, 1420, 1500], "interest_expense": [1320, 1250, 1140], "taxes": [1030, 1080, 1250],
    "net_income": [2100, 2700, 3230], "cash": [2900, 3300, 4100], "current_assets": [12400, 13100, 14300],
    "current_liabilities": [8100, 8500, 8800], "total_debt": [17600, 16600, 15400], "total_equity": [14800, 17500, 20730],
    "capex": [1450, 1550, 1650], "principal_payments": [1000, 1000, 1200],
}
EXAMPLE_MEMO = """# Credit memo: Alder Quay Tooling (worked example)

Alder Quay Tooling makes machined parts for equipment makers. It was founded in 2009 and operates 6 locations. Amounts below come from the spread for FY2022 to FY2024.

## Financial position

- Revenue in FY2024 was [$47.3 million](spread:revenue/FY2024).
- For FY2024, EBITDA came to [$6,450 thousand](spread:ebitda/FY2024).
- Cash in FY2024 was $4.1 million.
- Net income in FY2024 was [$3.2 million](spread:netincome/FY2024).

## Performance and coverage

- Revenue growth in FY2024 was [7.9%](spread:revenue_growth_pct/FY2024).
- Total debt to EBITDA in FY2024 was [2.4x](spread:debt_ebitda_x/FY2024).
- Debt service coverage in FY2024 was [3.04x](spread:dscr_x/FY2024).
- The current ratio in FY2024 was [1.63x](spread:current_ratio_x/FY2024).

## Proposed terms

- Requested facility: [$5.0 million](term:facility_amount) senior term loan.
- Pricing: base rate plus 2.75%.
"""


def write_csv(path: str, header: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    rng = random.Random(SEED)
    kinds = [k for k, n in KIND_COUNTS for _ in range(n)]
    rng.shuffle(kinds)
    per = len(kinds) // N_MEMOS
    names = rng.sample([f"{a} {b} {t}" for a in FIRST for b in SECOND for t in TRADE], N_MEMOS)
    spreads, memos, truth = [], [], []
    for n in range(N_MEMOS):
        memo_id = f"M{n + 1:02d}"
        while True:
            try:
                s = make_spread(rng)
                break
            except Retry:
                continue
        unit = rng.choices(["usd_thousands", "usd", "usd_millions"], [20, 5, 3])[0]
        spreads += spread_rows(memo_id, s, unit)
        text, rows = build_memo(rng, memo_id, names[n], rng.choice(BLURB), s, kinds[n * per:(n + 1) * per])
        memos.append({"memo_id": memo_id, "borrower": names[n], "memo": text})
        truth += rows
    write_csv("spreads.csv", ["memo_id", "period", "period_end", "line", "value", "unit"], spreads)
    write_csv("truth.csv", ["memo_id", "line", "col", "kind", "expected", "text"], truth)
    with open("memos.json", "w", encoding="utf-8") as fh:
        json.dump(memos, fh, indent=1, sort_keys=True)
        fh.write("\n")
    write_csv("example_spread.csv", ["period", "period_end", "line", "value", "unit"],
              [r[1:] for r in spread_rows("", EXAMPLE_SPREAD, "usd_thousands")])
    with open("example_memo.md", "w", encoding="utf-8") as fh:
        fh.write(EXAMPLE_MEMO)


if __name__ == "__main__":
    main()
