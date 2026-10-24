"""Generate the synthetic data for project 77: 120 financial statements (an income statement and a
balance sheet, two periods each) rendered as plain text in six layouts, plus the true value of every
field.

Everything is seeded, so the files are byte-for-byte reproducible. The truth comes from the generator
that builds each company, not from any extractor. Every statement satisfies ten accounting identities
in both periods (gross profit = revenue - cost of sales, assets = liabilities + equity, and so on).

Five layouts are the ones the stand-in extractors were written against. The sixth (note_column) is
held out: no extractor was written with it in front of the author. Hard cases on purpose: loss-making
companies (negative values in the layouts that use parentheses), a zero shown as a dash, a company
with negative equity, labels that wrap, footnote markers and dot leaders, a balance sheet printed side
by side, figures stated in thousands, and a column of note numbers between the label and the values.

Run (from data/):  python3 _generate.py
Writes:  statements.csv (doc_id, layout, split, company, text), truth.csv (doc_id, field, period, value)
"""
import csv
import math
import random

rng = random.Random(77)

DOCS_PER_LAYOUT = 20
LOSS_SLOTS = (3, 8, 13, 18)
DEFICIT_SLOT = 10
YEARS = (2023, 2024, 2025)

IS_FIELDS = ("revenue", "cost_of_sales", "gross_profit", "operating_expenses", "operating_income",
             "interest_expense", "pretax_income", "income_tax", "net_income")
ASSET_FIELDS = ("cash", "accounts_receivable", "inventory", "total_current_assets", "fixed_assets_net", "total_assets")
LE_FIELDS = ("accounts_payable", "short_term_debt", "total_current_liabilities", "long_term_debt",
             "total_liabilities", "total_equity", "total_liabilities_and_equity")
FIELDS = IS_FIELDS + ASSET_FIELDS + LE_FIELDS
PERIODS = ("current", "prior")

STD = {"revenue": "Revenue", "cost_of_sales": "Cost of sales", "gross_profit": "Gross profit",
       "operating_expenses": "Operating expenses", "operating_income": "Operating income",
       "interest_expense": "Interest expense", "pretax_income": "Income before tax", "income_tax": "Income tax",
       "net_income": "Net income", "cash": "Cash", "accounts_receivable": "Accounts receivable",
       "inventory": "Inventory", "total_current_assets": "Total current assets", "fixed_assets_net": "Fixed assets, net",
       "total_assets": "Total assets", "accounts_payable": "Accounts payable", "short_term_debt": "Short-term debt",
       "total_current_liabilities": "Total current liabilities", "long_term_debt": "Long-term debt",
       "total_liabilities": "Total liabilities", "total_equity": "Total equity",
       "total_liabilities_and_equity": "Total liabilities and equity"}
ALT = {"revenue": "Net sales", "cost_of_sales": "Cost of goods sold", "gross_profit": "Gross margin",
       "operating_expenses": "Selling, general and administrative expenses", "operating_income": "Operating profit",
       "interest_expense": "Finance costs", "pretax_income": "Profit before taxation", "income_tax": "Taxation",
       "net_income": "Profit for the year", "cash": "Cash and cash equivalents", "accounts_receivable": "Trade receivables",
       "inventory": "Inventories", "total_current_assets": "Total current assets",
       "fixed_assets_net": "Property, plant and equipment, net", "total_assets": "Total assets",
       "accounts_payable": "Trade payables", "short_term_debt": "Bank borrowings, current",
       "total_current_liabilities": "Total current liabilities", "long_term_debt": "Bank borrowings, non-current",
       "total_liabilities": "Total liabilities", "total_equity": "Shareholders' equity",
       "total_liabilities_and_equity": "Total liabilities and shareholders' equity"}

DOLLAR_ROWS = ("revenue", "net_income", "cash", "total_assets", "accounts_payable", "total_liabilities_and_equity")
FOOTNOTES = (("revenue", 1, "Revenue is shown net of returns."), ("cost_of_sales", 2, "Cost of sales includes depreciation."),
             ("income_tax", 3, "Income tax is the current charge only."),
             ("long_term_debt", 4, "Long-term debt excludes the current portion."))
NOTE_REFS = {"revenue": "3", "accounts_receivable": "5", "inventory": "6", "fixed_assets_net": "7",
             "short_term_debt": "9", "long_term_debt": "10", "income_tax": "12"}

BASE = dict(scale=1, labels=STD, order=PERIODS, neg="minus", dollar=False, zero="0", units=None,
            titles=("INCOME STATEMENT", "BALANCE SHEET"), leaders=False, side=False, notes=False)
LAYOUTS = {
    "plain_two_column": dict(BASE, split="dev"),
    "thousands_parens": dict(BASE, split="dev", scale=1000, order=("prior", "current"), neg="parens", dollar=True,
                             zero="-", units="(in thousands of dollars)"),
    "relabelled": dict(BASE, split="dev", labels=ALT, titles=("STATEMENT OF PROFIT OR LOSS", "STATEMENT OF FINANCIAL POSITION")),
    "side_by_side": dict(BASE, split="dev", side=True),
    "wrapped_footnotes": dict(BASE, split="dev", leaders=True),
    "note_column": dict(BASE, split="holdout", notes=True),
}

PREFIX = ("Tarvane", "Olmeric", "Brask", "Quillon", "Veldor", "Marrowfield", "Hesper", "Dunmoor", "Kestrin",
          "Yarrow Bend", "Ostrel", "Pellam", "Ravenlock", "Sundrel", "Trevane", "Ulmar", "Wexmoor", "Zandry")
SECTOR = ("Freight", "Foods", "Textiles", "Components", "Packaging", "Plastics", "Tooling", "Logistics", "Printing", "Fasteners")
SUFFIX = ("Ltd", "Inc", "Co", "LLC")

LABEL_W = 46
VAL_W = 14


def build_period(revenue, loss, deficit, unit):
    """One period of one company. Every leaf is a multiple of unit; subtotals are sums of leaves."""
    def r(x):
        return int(x / unit + 0.5) * unit
    v = {"revenue": r(revenue)}
    v["cost_of_sales"] = r(v["revenue"] * rng.uniform(0.55, 0.78))
    v["gross_profit"] = v["revenue"] - v["cost_of_sales"]
    v["operating_expenses"] = r(v["gross_profit"] * (rng.uniform(1.03, 1.25) if loss else rng.uniform(0.45, 0.8)))
    v["operating_income"] = v["gross_profit"] - v["operating_expenses"]
    v["interest_expense"] = r(v["revenue"] * rng.uniform(0.002, 0.02)) if loss else r(v["operating_income"] * rng.uniform(0.05, 0.35))
    v["pretax_income"] = v["operating_income"] - v["interest_expense"]
    v["income_tax"] = 0 if v["pretax_income"] <= 0 else r(v["pretax_income"] * 0.25)
    v["net_income"] = v["pretax_income"] - v["income_tax"]
    v["cash"] = r(v["revenue"] * rng.uniform(0.03, 0.15))
    v["accounts_receivable"] = r(v["revenue"] * rng.uniform(0.08, 0.2))
    v["inventory"] = r(v["revenue"] * rng.uniform(0.04, 0.2))
    v["total_current_assets"] = v["cash"] + v["accounts_receivable"] + v["inventory"]
    v["fixed_assets_net"] = r(v["revenue"] * rng.uniform(0.15, 0.6))
    v["total_assets"] = v["total_current_assets"] + v["fixed_assets_net"]
    v["accounts_payable"] = r(v["revenue"] * rng.uniform(0.05, 0.14))
    v["short_term_debt"] = r(v["revenue"] * rng.uniform(0.01, 0.08))
    v["total_current_liabilities"] = v["accounts_payable"] + v["short_term_debt"]
    v["long_term_debt"] = r(v["revenue"] * (rng.uniform(0.7, 0.95) if deficit else rng.uniform(0.05, 0.3)))
    v["total_liabilities"] = v["total_current_liabilities"] + v["long_term_debt"]
    v["total_equity"] = v["total_assets"] - v["total_liabilities"]
    v["total_liabilities_and_equity"] = v["total_liabilities"] + v["total_equity"]
    return v


def build_company(unit, slot):
    revenue = math.exp(rng.uniform(math.log(8e5), math.log(4e7)))
    loss, deficit = slot in LOSS_SLOTS, slot == DEFICIT_SLOT
    cur = build_period(revenue, loss, deficit, unit)
    prior = build_period(revenue / rng.uniform(0.9, 1.12), loss and rng.random() < 0.5, deficit, unit)
    return {(f, p): per[f] for p, per in (("current", cur), ("prior", prior)) for f in FIELDS}


def cell(v, cfg, dollar_row):
    d = v // cfg["scale"]
    if d == 0:
        return cfg["zero"]
    s = f"{abs(d):,}"
    if d < 0:
        s = f"({s})" if cfg["neg"] == "parens" else "-" + s
    return "$ " + s if dollar_row and cfg["dollar"] else s


def year_cells(cfg, years):
    return "".join(years[p].rjust(VAL_W) for p in cfg["order"])


def years_row(cfg, years):
    return (" " * (LABEL_W - 6) + "Note".rjust(6) if cfg["notes"] else " " * LABEL_W) + year_cells(cfg, years)


def statement_lines(doc, cfg, fields, years):
    marks = {f: n for f, n, _ in FOOTNOTES}
    out = []
    for f in fields:
        vals = [cell(doc[(f, p)], cfg, f in DOLLAR_ROWS) for p in cfg["order"]]
        label = cfg["labels"][f]
        if cfg["leaders"]:
            text = label + (f" ({marks[f]})" if f in marks else "")
            if len(text) > 24:
                cut = text.rfind(" ", 0, 25)
                out.append(text[:cut])
                text = text[cut + 1:]
            out.append((text + " ").ljust(LABEL_W, ".") + "".join(v.rjust(VAL_W) for v in vals))
        elif cfg["notes"]:
            out.append(label.ljust(LABEL_W - 6) + NOTE_REFS.get(f, "").rjust(6) + "".join(v.rjust(VAL_W) for v in vals))
        else:
            out.append(label.ljust(LABEL_W) + "".join(v.rjust(VAL_W) for v in vals))
    return out


def side_by_side_lines(doc, cfg, years):
    lw, rw = 24, 44
    out = ["ASSETS".ljust(lw + 2 * VAL_W - 1) + "   " + "LIABILITIES AND EQUITY",
           " " * (lw - 1) + year_cells(cfg, years) + "   " + " " * rw + year_cells(cfg, years)]
    for i in range(len(LE_FIELDS)):
        left = " " * (lw + 2 * VAL_W - 1)
        if i < len(ASSET_FIELDS):
            f = ASSET_FIELDS[i]
            assert len(cfg["labels"][f]) < lw
            left = cfg["labels"][f].ljust(lw - 1) + "".join(cell(doc[(f, p)], cfg, False).rjust(VAL_W) for p in cfg["order"])
        g = LE_FIELDS[i]
        assert len(cfg["labels"][g]) < rw
        out.append((left + "   " + cfg["labels"][g].ljust(rw) + "".join(cell(doc[(g, p)], cfg, False).rjust(VAL_W) for p in cfg["order"])).rstrip())
    return out


def render(company, doc, cfg, cur_year):
    years = {"current": str(cur_year), "prior": str(cur_year - 1)}
    lines = [company, cfg["titles"][0], "For the years ended December 31"]
    if cfg["units"]:
        lines.append(cfg["units"])
    lines.append(years_row(cfg, years))
    lines += statement_lines(doc, cfg, IS_FIELDS, years)
    lines += ["", cfg["titles"][1], "As at December 31"]
    if cfg["units"]:
        lines.append(cfg["units"])
    if cfg["side"]:
        lines += side_by_side_lines(doc, cfg, years)
    else:
        lines.append(years_row(cfg, years))
        lines += statement_lines(doc, cfg, ASSET_FIELDS + LE_FIELDS, years)
    if cfg["leaders"]:
        lines.append("")
        lines += [f"({n}) {t}" for _, n, t in FOOTNOTES]
    return "\n".join(lines) + "\n"


def main():
    slots = [(name, k) for name in LAYOUTS for k in range(DOCS_PER_LAYOUT)]
    rng.shuffle(slots)
    names = [f"{a} {b} {c}" for a in PREFIX for b in SECTOR for c in SUFFIX]
    rng.shuffle(names)
    docs, truth = [], []
    for i, (layout, k) in enumerate(slots):
        cfg = LAYOUTS[layout]
        doc_id = f"S{i + 1:03d}"
        values = build_company(cfg["scale"], k)
        text = render(names[i], values, cfg, rng.choice(YEARS))
        docs.append((doc_id, layout, cfg["split"], names[i], text))
        truth += [(doc_id, f, p, values[(f, p)]) for f in FIELDS for p in PERIODS]
    docs.sort()
    truth.sort(key=lambda t: (t[0], FIELDS.index(t[1]), PERIODS.index(t[2])))
    with open("statements.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["doc_id", "layout", "split", "company", "text"])
        w.writerows(docs)
    with open("truth.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["doc_id", "field", "period", "value"])
        w.writerows(truth)
    print(f"Wrote statements.csv ({len(docs)} documents) and truth.csv ({len(truth)} values)")


if __name__ == "__main__":
    main()
