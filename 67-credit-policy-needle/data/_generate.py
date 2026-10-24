#!/usr/bin/env python3
"""Generate the synthetic credit policy manuals, question sets and truth tables for project 67.

Standard library only, seeded: a rerun writes every file byte for byte.

    python3 _generate.py        (from data/)

Writes into this folder:
  manuals/manual_050p.txt, manual_150p.txt, manual_300p.txt   the documents an assistant is given
  manuals.csv          one row per manual
  probes.csv           210 questions with exact expected answers, and where the evidence sits
  exceptions_truth.csv every planted exception clause and every look-alike that is not one
  example_manual.txt, example_probes.csv, example_answers.csv   the small set behind `--demo`

Everything is invented: the lender, the products, the limits and the clauses. One synthetic page
is 1,800 characters, a convention borrowed from project 14, not the layout of a real manual.

A rule is a limit stated in one clause ("The maximum loan term for Alder Personal Loan is 60 months").
An exception changes that limit for an applicant who meets a condition. It is planted in one of six
places, and a plain rule with no exception is the control:
  inline     inside the rule clause
  adjacent   in the clause that follows, naming the product
  crossref   in another section, citing the rule by clause number only
  restated   in another section, as a restated limit with no exception wording
  register   as an entry in the register at the back
  nested     an adjacent exception, plus a far clause saying it does not apply in one case
Each exception has two questions: an applicant who meets the condition, and one who does not (or,
for nested, one for whom the carve-out applies). The depth label is where the rule clause sits.
"""
from __future__ import annotations

import csv
import datetime
import os
import random
import re

SEED = 67067
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_CHARS = 1800
SECTION_SIZE = 28
DEPTHS = [0, 25, 50, 75, 100]
LENGTHS = [50, 150, 300]
# Where the far clause of a crossref, restated or nested rule sits, as a percent of the body.
FAR = {0: 50, 25: 75, 50: 0, 75: 25, 100: 50}
EXC_FORMS = ["inline", "adjacent", "crossref", "restated", "register", "nested"]
CODE = {"plain": "PLN", "inline": "INL", "adjacent": "ADJ", "crossref": "XRF",
        "restated": "RST", "register": "REG", "nested": "NST"}

BRANDS = ("Alder Basalt Cobalt Dune Ember Fjord Garnet Harbor Indigo Juniper Kestrel Larch Marble Nutmeg "
          "Onyx Pewter Quill Russet Sable Tamarack Umber Velvet Willow Xenon Yarrow Zephyr Amber Birch "
          "Cedar Dahlia Elm Fennel Granite Hazel Iris Jasper Kelp Lupine Maple Nectar").split()
TYPE_ATTRS = {"Personal Loan": ["dti", "score", "term", "loan_amount"],
              "Auto Loan": ["dti", "score", "term", "loan_amount"],
              "Credit Card": ["dti", "score", "credit_limit"],
              "Business Line": ["score", "term", "credit_limit"]}
TYPE_FACTS = {"Personal Loan": ["relationship", "income"], "Auto Loan": ["down_payment", "relationship"],
              "Credit Card": ["relationship", "income"], "Business Line": ["revenue", "relationship"]}
ATTR_PHRASE = {"dti": "maximum debt-to-income ratio", "score": "minimum credit score",
               "term": "maximum loan term", "loan_amount": "maximum loan amount",
               "credit_limit": "maximum credit limit"}
ATTR_KIND = {"dti": "percent", "score": "points", "term": "months", "loan_amount": "dollars",
             "credit_limit": "dollars"}


def money(v: int) -> str:
    return "${:,}".format(v)


FACTS = {
    "relationship": {"noun": "a customer relationship", "suffix": "", "fmt": lambda v: "%d months" % v,
                     "t": [12, 18, 24, 36], "up": [3, 6, 12], "down": [3, 6]},
    "income": {"noun": "verified annual income", "suffix": "", "fmt": money,
               "t": [30000, 40000, 50000, 60000], "up": [5000, 10000, 15000], "down": [5000, 10000]},
    "down_payment": {"noun": "an initial payment", "suffix": " of the purchase price", "fmt": lambda v: "%d%%" % v,
                     "t": [10, 15, 20, 25], "up": [5, 10], "down": [3, 5]},
    "revenue": {"noun": "annual business revenue", "suffix": "", "fmt": money,
                "t": [100000, 150000, 250000, 400000], "up": [25000, 50000], "down": [25000, 50000]},
}

SUBJECTS = ["The file reviewer", "The credit analyst", "The underwriting lead", "The servicing team",
            "The collections desk", "The documentation clerk", "The branch officer", "The quality reviewer",
            "The operations lead", "The case handler", "The approving officer", "The verification team"]
ACTIONS = ["checks the file for missing pages before it moves on",
           "records the outcome in the case log on the day it is known",
           "returns an incomplete file to the sender with a note of what is missing",
           "keeps the signed copy in the folder set up for that purpose",
           "confirms that each identity check on the file is dated and initialed",
           "passes the file to the next reviewer once the checks are complete",
           "notes the reason for any delay in the case log",
           "files the correspondence in the order it was received",
           "sends a reminder to the sender when a document is overdue",
           "updates the status of the file at each stage",
           "marks the file for second review when the documents do not agree",
           "closes the task in the queue after the record is saved"]
TAILS = ["", "", " and signs the record", ", and the date is entered in full", " before the end of the working day",
         " as the procedure sheet describes", " and keeps a note of who acted", ", and the queue is cleared each day"]
TOPICS = ["File Review", "Document Retention", "Case Handling", "Servicing Queues", "Record Keeping",
          "Quality Checks", "Staff Training", "Channel Procedures", "Escalation Paths", "Correspondence",
          "Identity Checks", "Archive Handling"]
SCOPES = ["Consumer Lending", "Small Business Lending", "Card Services", "Auto Finance"]
GENERIC_EXCEPT = ["Except for the cover sheet, each sheet of the file shows the case number in the margin.",
                  "Except for the routing slip, every page of the file carries the reviewer's initials.",
                  "Except for the index page, each page of the file is numbered in the footer.",
                  "Except for the envelope, every item in the file is logged on receipt."]
FRONT = ["Synthetic Credit Policy Manual, Issue 14. Effective 2026-07-01. This is invented text for a test. "
         "It describes no real lender, customer or product.",
         "A limit stated in a clause can be changed by an exception. The exception may sit inside the clause, in "
         "the clause that follows, in another section that cites the clause number, or as an entry in the "
         "register in Appendix A. Entries in the register are effective from the date shown."]
REGISTER_HEADING = "Appendix A. Standing Exceptions Register"
BANNED_IN_FILLER = re.compile(r"\d|\$|%|clause|except|notwithstanding|apply|register|relationship|income|payment|"
                              r"revenue|default|limit|score", re.I)


def draw_values(rng: random.Random, attr: str):
    """(rule value, exception value) as written in the manual. Every exception loosens the rule."""
    if attr == "dti":
        b = rng.randint(34, 46)
        x = b + rng.choice([3, 4, 5, 6])
        return "%d%%" % b, "%d%%" % x
    if attr == "score":
        b = rng.choice([640, 660, 680, 700, 720])
        return "%d points" % b, "%d points" % (b - rng.choice([20, 30, 40]))
    if attr == "term":
        b = rng.choice([36, 48, 60, 72])
        return "%d months" % b, "%d months" % (b + rng.choice([12, 24]))
    if attr == "loan_amount":
        b = rng.choice(range(5000, 40001, 2500))
        return money(b), money(b + rng.choice([5000, 7500, 10000]))
    b = rng.choice(range(2000, 20001, 1000))
    return money(b), money(b + rng.choice([2000, 3000, 5000]))


def make_rule(rng: random.Random, brands: list, seq: int, form: str, depth: int, k: int) -> dict:
    ptype = rng.choice(sorted(TYPE_ATTRS))
    attr = rng.choice(TYPE_ATTRS[ptype])
    fact = rng.choice(TYPE_FACTS[ptype])
    base, exc = draw_values(rng, attr)
    f = FACTS[fact]
    t = rng.choice(f["t"])
    return {"key": "r%d" % seq, "form": form, "depth": depth, "k": k, "product": "%s %s" % (brands.pop(), ptype),
            "attr": attr, "base": base, "exc": exc, "fact": fact, "t": t, "met": t + rng.choice(f["up"]),
            "not_met": t - rng.choice(f["down"]), "g": rng.choice([2, 3, 5, 8])}


def cond_text(rule: dict) -> str:
    f = FACTS[rule["fact"]]
    return "%s of at least %s%s" % (f["noun"], f["fmt"](rule["t"]), f["suffix"])


def fact_question(rule: dict, value: int) -> str:
    f = FACTS[rule["fact"]]
    return "%s of %s%s" % (f["noun"], f["fmt"](value), f["suffix"])


def rule_items(rule: dict, date: str):
    """(groups, register items) for one rule. A group is (target percent, [items]); text may hold @@key@@."""
    k, form = rule["key"], rule["form"]
    phrase, prod, cond = ATTR_PHRASE[rule["attr"]], rule["product"], cond_text(rule)
    base_text = "The %s for %s is %s." % (phrase, prod, rule["base"])
    if form == "inline":
        base_text = "The %s for %s is %s, except that it is %s for an applicant with %s." % (
            phrase, prod, rule["base"], rule["exc"], cond)
    base = {"key": k + "b", "text": base_text}
    d = rule["depth"]
    if form in ("plain", "inline"):
        return [(d, [base])], []
    if form in ("adjacent", "nested"):
        exc = {"key": k + "x", "text": "Exception to clause @@%sb@@: the %s for %s is %s for an applicant with %s." % (
            k, phrase, prod, rule["exc"], cond)}
        groups = [(d, [base, exc])]
        if form == "nested":
            groups.append((FAR[d], [{"key": k + "c", "text": "Clause @@%sx@@ does not apply to an applicant with a "
                                     "payment default recorded in the prior 12 months." % k}]))
        return groups, []
    if form == "crossref":
        far = {"key": k + "x", "text": "Notwithstanding clause @@%sb@@, the limit stated there is %s for an applicant "
               "with %s." % (k, rule["exc"], cond)}
        return [(d, [base]), (FAR[d], [far])], []
    if form == "restated":
        far = {"key": k + "x", "text": "For an applicant with %s, the limit in clause @@%sb@@ is %s." % (
            cond, k, rule["exc"])}
        return [(d, [base]), (FAR[d], [far])], []
    entry = {"key": k + "r", "text": "Register entry (effective %s): clause @@%sb@@ is %s for an applicant with %s." % (
        date, k, rule["exc"], cond)}
    return [(d, [base])], [entry]


def filler(rng: random.Random) -> str:
    sents = []
    for _ in range(rng.choice([1, 2, 2, 3])):
        sents.append("%s %s%s." % (rng.choice(SUBJECTS), rng.choice(ACTIONS), rng.choice(TAILS)))
    return " ".join(sents)


def build(mid: str, pages: int, plan: list, n_decoy: int, rng: random.Random, probe_prefix: str):
    """Assemble one manual. Returns (text, manual row, probe rows, truth rows)."""
    brands = list(BRANDS)
    rng.shuffle(brands)
    rules = [make_rule(rng, brands, i, form, depth, k) for i, (form, depth, k) in enumerate(plan)]
    day = datetime.date(2025, 9, 1)
    groups, reg_items = [], []
    for rule in rules:
        if rule["form"] == "register":
            day = day + datetime.timedelta(days=40 + rng.randint(0, 20))
        g, r = rule_items(rule, day.isoformat())
        groups.extend(g)
        reg_items.extend(r)
    planted = [it for _p, items in groups for it in items]
    planted_chars = sum(len(it["text"]) + 9 for it in planted) + sum(len(it["text"]) + 12 for it in reg_items)
    planted_chars += n_decoy * 3 * 110 + sum(len(x) for x in FRONT) + len(REGISTER_HEADING) + 20
    target_body = pages * PAGE_CHARS - planted_chars
    body_filler, size = [], 0
    while size < target_body:
        text = filler(rng)
        assert not BANNED_IN_FILLER.search(text), text
        body_filler.append({"key": "f%d" % len(body_filler), "text": text})
        size += len(text) + 9
    n = len(body_filler)
    decoys = []
    for i in range(n_decoy):
        ref = rng.choice(body_filler)["key"]
        decoys.append(("decoy_prohibition", {"key": "dp%d" % i, "text": "No exception to clause @@%s@@ is permitted "
                                             "without the written approval of the credit committee." % ref}))
        decoys.append(("decoy_generic", {"key": "dg%d" % i, "text": GENERIC_EXCEPT[i % len(GENERIC_EXCEPT)]}))
        ref = rng.choice(body_filler)["key"]
        decoys.append(("decoy_pointer", {"key": "dq%d" % i, "text": "Reviewers cite clause @@%s@@ in the case log, "
                                         "except for files closed with no decision." % ref}))
    placed = []
    spread = max(10, n // 60)
    for pct, items in groups:
        lo, hi = (0 if pct == 0 else -spread), (0 if pct == 100 else spread)
        placed.append((min(n - 1, max(0, round(pct / 100 * (n - 1)) + rng.randint(lo, hi))), items))
    for _kind, item in decoys:
        placed.append((rng.randint(0, n - 1), [item]))
    by_index = {}
    for seq, (idx, items) in enumerate(placed):
        by_index.setdefault(idx, []).append((seq, items))
    body = []
    for i, f in enumerate(body_filler):
        for _seq, items in sorted(by_index.get(i, []), key=lambda x: x[0]):
            body.extend(items)
        body.append(f)
    blocks = [{"key": None, "text": t} for t in FRONT]
    ids = {}
    n_sections = 0
    for s in range(0, len(body), SECTION_SIZE):
        n_sections += 1
        blocks.append({"key": None, "text": "Section %d. %s: %s" % (n_sections, rng.choice(TOPICS), rng.choice(SCOPES))})
        for k, item in enumerate(body[s:s + SECTION_SIZE], 1):
            ids[item["key"]] = "%d.%d" % (n_sections, k)
            blocks.append({"key": item["key"], "text": item["text"], "id": ids[item["key"]]})
    blocks.append({"key": None, "text": REGISTER_HEADING, "register_heading": True})
    for j, item in enumerate(reg_items, 1):
        ids[item["key"]] = "R-%d" % j
        blocks.append({"key": item["key"], "text": item["text"], "id": ids[item["key"]]})
    pos, loc, out = 0, {}, []
    register_at = 0
    for b in blocks:
        if "id" in b:
            b["text"] = b["id"] + " " + re.sub(r"@@(\w+)@@", lambda m: ids[m.group(1)], b["text"])
        if b.get("register_heading"):
            register_at = pos
        if b["key"]:
            loc[b["key"]] = (b["id"], pos, pos + len(b["text"]))
        out.append(b["text"])
        pos += len(b["text"]) + 2
    text = "\n\n".join(out)
    doc_chars = len(text)
    assert all(not re.search(r"@@", t) for t in out)

    probes, truth = [], []
    for rule in rules:
        probes.extend(probe_rows(rule, loc, mid, pages, doc_chars, probe_prefix))
        truth.extend(truth_rows(rule, loc, mid))
    for kind, item in decoys:
        truth.append([mid, loc[item["key"]][0], kind, 0, ""])
    clauses = sum(1 for b in blocks if b.get("id", "")[:1].isdigit())
    n_exc = sum(1 for r in truth if r[3] == 1)
    manual = [mid, "manuals/%s.txt" % mid if mid != "example_manual" else "example_manual.txt", pages, doc_chars,
              "%.1f" % (doc_chars / PAGE_CHARS), n_sections, clauses, n_exc, len(decoys), register_at]
    return text, manual, probes, truth


def probe_rows(rule: dict, loc: dict, mid: str, pages: int, doc_chars: int, prefix: str) -> list:
    k, form = rule["key"], rule["form"]
    bid, bs, be = loc[k + "b"]
    if form in ("plain", "inline"):
        xid, xs, xe = bid, bs, be
    elif form == "register":
        xid, xs, xe = loc[k + "r"]
    else:
        xid, xs, xe = loc[k + "x"]
    cid, ce = (loc[k + "c"][0], loc[k + "c"][2]) if form == "nested" else ("", "")
    phrase, prod, kind = ATTR_PHRASE[rule["attr"]], rule["product"], ATTR_KIND[rule["attr"]]
    q = "What is the %s for %s" % (phrase, prod)
    if form == "plain":
        variants = [("plain", q + "?", rule["base"], "", rule["k"])]
    elif form == "nested":
        variants = [("applies", q + " for an applicant with %s and no recorded payment default?" % fact_question(rule, rule["met"]),
                     rule["exc"], rule["base"], 1),
                    ("carved_out", q + " for an applicant with %s and a payment default recorded %d months ago?" % (
                        fact_question(rule, rule["met"]), rule["g"]), rule["base"], rule["exc"], 2)]
    else:
        variants = [("applies", q + " for an applicant with %s?" % fact_question(rule, rule["met"]), rule["exc"], rule["base"], 1),
                    ("not_met", q + " for an applicant with %s?" % fact_question(rule, rule["not_met"]), rule["base"], rule["exc"], 2)]
    rows = []
    for variant, question, expected, trap, j in variants:
        rows.append(["%s-%s-%03d-%d" % (prefix, CODE[form], rule["depth"], j), mid, pages, doc_chars, form,
                     rule["depth"], variant, question, expected, kind, trap, bid, xid if form != "plain" else "", cid,
                     "%.1f" % (100 * bs / doc_chars), "%.1f" % (100 * xs / doc_chars) if form != "plain" else "",
                     be, xe if form != "plain" else "", ce])
    return rows


def truth_rows(rule: dict, loc: dict, mid: str) -> list:
    k, form = rule["key"], rule["form"]
    if form == "plain":
        return []
    if form == "inline":
        return [[mid, loc[k + "b"][0], "inline", 1, ""]]
    if form == "register":
        return [[mid, loc[k + "r"][0], "register", 1, loc[k + "b"][0]]]
    rows = [[mid, loc[k + "x"][0], "nested_exception" if form == "nested" else form, 1, loc[k + "b"][0]]]
    if form == "nested":
        rows.append([mid, loc[k + "c"][0], "carve_out", 1, loc[k + "x"][0]])
    return rows


def write_csv(path: str, header: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_text(path: str, text: str) -> None:
    with open(path, "w", newline="\n", encoding="utf-8") as fh:
        fh.write(text + "\n")


PROBE_HEADER = ["probe_id", "manual_id", "length_pages", "doc_chars", "form", "depth_pct", "variant", "question",
                "expected_answer", "answer_kind", "trap_answer", "base_id", "exception_id", "carve_id", "base_pct",
                "exception_pct", "base_end", "exception_end", "carve_end"]


def main() -> None:
    os.makedirs(os.path.join(HERE, "manuals"), exist_ok=True)
    manual_rows, all_probes, all_truth = [], [], []
    for i, pages in enumerate(LENGTHS):
        plan = []
        for depth in DEPTHS:
            plan += [("plain", depth, 1), ("plain", depth, 2)]
            plan += [(form, depth, 0) for form in EXC_FORMS]
        mid = "manual_%03dp" % pages
        text, manual, probes, truth = build(mid, pages, plan, 4, random.Random(SEED + i), "P%03d" % pages)
        write_text(os.path.join(HERE, "manuals", mid + ".txt"), text)
        manual_rows.append(manual)
        all_probes += probes
        all_truth += truth
    write_csv(os.path.join(HERE, "manuals.csv"),
              ["manual_id", "file", "length_pages", "chars", "approx_pages", "sections", "clauses",
               "exception_blocks", "decoys", "register_starts_at"], manual_rows)
    write_csv(os.path.join(HERE, "probes.csv"), PROBE_HEADER, all_probes)
    write_csv(os.path.join(HERE, "exceptions_truth.csv"), ["manual_id", "block_id", "kind", "is_exception", "cites"], all_truth)

    ex_plan = [("inline", 25, 0), ("adjacent", 50, 0), ("crossref", 75, 0), ("register", 50, 0)]
    text, _manual, probes, _truth = build("example_manual", 8, ex_plan, 1, random.Random(SEED + 9), "EX")
    write_text(os.path.join(HERE, "example_manual.txt"), text)
    write_csv(os.path.join(HERE, "example_probes.csv"), PROBE_HEADER, probes)
    # What an assistant that searches on the rule's own words would say: the rule value whenever the
    # exception sits away from the rule. Written here by hand, not produced by the readers in src/common.py.
    answers = [[p[0], p[10] if p[4] in ("crossref", "register") and p[6] == "applies" else p[8]] for p in probes]
    write_csv(os.path.join(HERE, "example_answers.csv"), ["probe_id", "answer"], answers)


if __name__ == "__main__":
    main()
