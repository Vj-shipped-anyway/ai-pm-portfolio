"""Generates the PolicyNeedle synthetic data. Standard library only.

Seeded and deterministic: running it twice writes byte-identical files.

    python3 _generate.py

Writes into this folder:
  manuals/manual_006p.txt, manual_040p.txt, manual_120p.txt, manual_240p.txt
  manuals.csv      one row per manual
  probes.csv       the question set, with exact expected answers
  probe_types.csv  the probe types, and which of them exact-match scoring can score

Everything here is invented: the products, amounts, rules and the manuals.
No real institution, customer, product or system is described.

One synthetic "page" is 1,800 characters (about 300 words). That is a
convention of this repo, not the layout of any real manual.

Facts are planted at controlled depth (0, 25, 50, 75, 100 percent of the
document) in six forms: plain clause, superseded clause (the amendment sits
in an appendix at the end), exception in a footnote, value in a table, a fact
that needs two clauses from different sections, and a near-duplicate
distractor clause for a sibling product.
"""

from __future__ import annotations

import csv
import random
import re
from bisect import bisect_left
from pathlib import Path

OUT = Path(__file__).resolve().parent
MANUAL_DIR = OUT / "manuals"

SEED = 20261014
PAGE_CHARS = 1800
SHORT_PAGES = 6
LONG_PAGES = [40, 120, 240]
DEPTHS = [0, 25, 50, 75, 100]
REPS = 3
CALIBRATION = 1200  # nudges the total length onto the nominal page count

# (form name, code). Order matters: it is the slice order used everywhere.
FORMS = [
    ("plain", "PLN"),
    ("superseded", "SUP"),
    ("exception", "EXC"),
    ("table", "TBL"),
    ("two_section", "TWO"),
    ("distractor", "DST"),
]

# The keyword-window rule the stub readers use. Copied from src/harness.py so
# this file stays standalone. Step 4 re-runs the audit with the harness copy.
STOPWORDS = frozenset(
    "what is the for on of a an when because at in to and or by with per how "
    "much many which are does do it its this that".split()
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
MATCH_NUM, MATCH_DEN = 4, 5  # a block is a candidate when it holds 4/5 of the question words

# How many blocks the keyword rule should find for each form (the audit).
EXPECTED_CANDIDATES = {
    "plain": 1,
    "superseded": 2,   # original clause + amendment
    "exception": 2,    # main clause + footnote
    "table": 1,
    "two_section": 1,  # the discount clause; the base clause lacks the product
    "distractor": 3,   # the true clause + two sibling products
}

BRANDS = [
    "Alder", "Birch", "Cobalt", "Dune", "Ember", "Fjord", "Gable", "Heron", "Iris", "Jasper",
    "Kite", "Larch", "Moss", "Nettle", "Oak", "Pine", "Quill", "Reed", "Sorrel", "Thistle",
    "Umber", "Vetch", "Wren", "Yarrow", "Zinnia", "Briar", "Cedar", "Dahlia", "Elm", "Fern",
    "Gorse", "Hazel", "Ivy", "Juniper", "Linden", "Maple", "Nutmeg", "Olive", "Poppy", "Rowan",
    "Sage", "Tansy", "Willow", "Aspen", "Basil", "Clover", "Daisy", "Fennel", "Ginger", "Holly",
]
DECOY_BRANDS = [
    "Acorn", "Bramble", "Cypress", "Dogwood", "Elder", "Foxglove", "Garnet", "Hickory", "Indigo", "Jade",
]
TYPES = ["Checking", "Savings", "Card", "Certificate", "Mortgage"]
MODIFIERS = ["Business", "Student", "Premier", "Basic", "Senior", "Youth", "Plus", "Select"]

LIMIT_ATTRS = [
    f"{tf} {obj} limit"
    for tf in ("daily", "weekly", "monthly")
    for obj in ("wire transfer", "ATM withdrawal", "card purchase", "cash deposit", "mobile deposit",
                "bill payment", "peer transfer", "check deposit", "branch withdrawal")
]
FEE_ATTRS = [
    f"{tf} {what} fee"
    for tf in ("monthly", "annual", "quarterly")
    for what in ("maintenance", "service", "membership", "statement", "research", "replacement",
                 "courier", "notary", "vault", "archive", "reissue", "verification")
]
RATE_ATTRS = [
    f"{a} {b} rate"
    for a in ("base", "bonus", "penalty", "promotional")
    for b in ("interest", "cashback", "rewards", "overdraft")
]
DAYS_ATTRS = [
    f"{x} {y}"
    for x in ("check hold", "dispute filing", "refund processing", "card replacement",
              "statement correction", "wire recall", "account review", "deposit clearing",
              "payment posting", "complaint response")
    for y in ("window", "period")
]

# (fee phrase, event phrase) for exception probes.
EXC_PAIRS = [
    ("early closure fee", "the account is closed early"),
    ("returned item fee", "a deposited item is returned"),
    ("inactivity fee", "the account stays inactive"),
    ("paper statement fee", "a statement is mailed on paper"),
    ("early replacement fee", "a card is replaced early"),
    ("wire recall fee", "an outgoing wire is recalled"),
    ("overdraft protection fee", "overdraft protection is used"),
    ("stop payment fee", "a stop payment order is placed"),
    ("rush delivery fee", "a replacement card is rushed"),
    ("check image fee", "a check image is requested"),
    ("account research fee", "staff research an account"),
    ("balance inquiry fee", "a balance is requested at a partner terminal"),
    ("paper check fee", "a bill payment is sent by paper check"),
    ("cash advance fee", "a cash advance is taken"),
    ("late payment fee", "a payment is received late"),
    ("over limit fee", "the credit limit is exceeded"),
    ("loan prepayment fee", "the loan is prepaid in full"),
    ("certificate withdrawal fee", "a certificate is withdrawn early"),
    ("dormant account fee", "the account becomes dormant"),
    ("duplicate statement fee", "a duplicate statement is requested"),
]
COVERED_REASONS = ["relocation", "bereavement", "deployment", "hardship", "disability", "disaster", "illness", "error"]
UNCOVERED_REASONS = ["convenience", "dissatisfaction", "promotion", "travel", "preference", "curiosity"]

TOPICS = [
    "Account Opening", "Identity Verification", "Funds Availability", "Deposit Handling",
    "Cash Management", "Card Services", "Dispute Handling", "Complaint Handling",
    "Record Retention", "Fee Administration", "Customer Notices", "Branch Security",
    "Vendor Oversight", "Privacy and Consent", "Training and Attestation", "Exception Approval",
    "Account Maintenance", "Closure and Escheatment", "Fraud Review", "Wire Operations",
    "Statement Production", "Collateral Handling", "Rate Changes", "Document Control Reviews",
    "Safe Deposit Operations", "Dormant Accounts", "Overdraft Handling", "Account Takeover Response",
]
ASPECTS = ["Standards", "Procedures", "Controls"]

WHO = [
    "The branch operations manager", "Each relationship banker", "The deposit operations team",
    "The compliance officer on duty", "A contact center team lead", "The records custodian",
    "The regional controller", "The fraud review analyst", "The onboarding specialist",
    "The product owner", "The service desk coordinator", "The quality reviewer",
]
MODAL = ["must", "shall", "is required to", "is expected to"]
VERB = ["verify", "document", "review", "reconcile", "approve", "file", "log", "confirm",
        "archive", "sample", "escalate", "report"]
OBJ = [
    "the signed intake checklist", "the exception report", "the identity verification record",
    "the daily balancing sheet", "the call recording index", "the vendor access list",
    "the branch cash count", "the training attestation", "the system access review",
    "the complaint tracking entry", "the disclosure acknowledgment", "the audit trail extract",
    "the dual control sign-off", "the key custody record", "the incident summary",
]
WHEN = [
    "at the start of each shift", "before the end of the business day", "each calendar month",
    "at least once each quarter", "within five business days of the request",
    "after every system release", "on the first business day of the week",
    "before any change is approved",
]
COND = [
    "a control owner changes", "a system outage lasts more than one shift", "a reviewer is unavailable",
    "a supervisor disputes the result", "a source document is missing",
]
DEADLINE = ["next business day closes", "next review cycle begins", "month-end close starts"]
YEARS = ["three", "five", "seven", "ten"]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def lower_first(s: str) -> str:
    return s[0].lower() + s[1:]


def cap_first(s: str) -> str:
    return s[0].upper() + s[1:]


def fmt_money(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return "${:,}".format(int(round(x)))
    return "${:,.2f}".format(x)


def fmt_percent(x: float) -> str:
    return "{:g}%".format(x)


def question_words(q: str) -> set:
    return {t for t in TOKEN_RE.findall(q.lower()) if t not in STOPWORDS}


def draw_date(rng: random.Random) -> str:
    """An effective date that is already in force when the manual is issued (2026-07-01)."""
    year = rng.choice([2025, 2026])
    month = rng.randint(1, 12) if year == 2025 else rng.randint(1, 6)
    return "{}-{:02d}-{:02d}".format(year, month, rng.randint(1, 28))


def clause_text(rng: random.Random) -> str:
    pick = rng.randrange(4)
    if pick == 0:
        return "{} {} {} {} {}.".format(
            rng.choice(WHO), rng.choice(MODAL), rng.choice(VERB), rng.choice(OBJ), rng.choice(WHEN))
    if pick == 1:
        return "Each {} is kept for {} years and is made available to internal audit on request.".format(
            rng.choice(OBJ)[4:], rng.choice(YEARS))
    if pick == 2:
        return "If {}, {} {} {} {} before the {}.".format(
            rng.choice(COND), lower_first(rng.choice(WHO)), rng.choice(MODAL), rng.choice(VERB),
            rng.choice(OBJ), rng.choice(DEADLINE))
    return "{} {} be retained by {} and reviewed {}.".format(
        cap_first(rng.choice(OBJ)), rng.choice(["must", "shall"]), lower_first(rng.choice(WHO)), rng.choice(WHEN))


# ---------------------------------------------------------------------------
# fact planning
# ---------------------------------------------------------------------------
class Pools:
    """Draws unique products, attribute phrases and exception pairs for one manual."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        combos = [(b, t) for b in BRANDS for t in TYPES]
        rng.shuffle(combos)
        self.products = combos
        fee = FEE_ATTRS[:]
        rng.shuffle(fee)
        self.fee_attrs = fee                       # tables and two-section facts draw from here first
        other = LIMIT_ATTRS + RATE_ATTRS + DAYS_ATTRS
        rng.shuffle(other)
        self.other_attrs = other
        pairs = EXC_PAIRS[:]
        rng.shuffle(pairs)
        self.pairs = pairs

    def product(self) -> tuple:
        return self.products.pop()

    def fee_attr(self) -> str:
        return self.fee_attrs.pop()

    def any_attr(self) -> str:
        if self.other_attrs:
            return self.other_attrs.pop()
        return self.fee_attrs.pop()

    def pair(self) -> tuple:
        return self.pairs.pop()


def attr_kind(attr: str) -> str:
    if attr in LIMIT_ATTRS:
        return "money_limit"
    if attr in FEE_ATTRS:
        return "money_fee"
    if attr in RATE_ATTRS:
        return "percent"
    return "days"


def draw_value(rng: random.Random, kind: str, avoid: tuple = ()) -> str:
    for _ in range(50):
        if kind == "money_limit":
            v = fmt_money(rng.choice([1000, 2500, 5000, 7500, 10000, 15000, 25000, 40000, 50000, 75000, 100000]))
        elif kind == "money_fee":
            v = fmt_money(rng.choice([3, 5, 8, 10, 12, 15, 18, 20, 25, 30, 35, 45]))
        elif kind == "percent":
            v = fmt_percent(rng.choice([0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4.25, 5]))
        else:
            v = "{} {}".format(rng.choice([2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90]),
                               rng.choice(["days", "business days"]))
        if v not in avoid:
            return v
    raise RuntimeError("could not draw a distinct value")


def sentence(rng: random.Random, attr: str, product: str, value: str) -> str:
    pick = rng.randrange(3)
    if pick == 0:
        return "The {} for {} is {}.".format(attr, product, value)
    if pick == 1:
        return "For {}, the {} is {}.".format(product, attr, value)
    return "{} carries a {} of {}.".format(product, attr, value)


def plan_facts(rng: random.Random, plain_only: bool, reps: int) -> list:
    """One dict per planted fact. Blocks carry @@ tokens that are filled in after numbering."""
    pools = Pools(rng)
    facts = []
    forms = FORMS[:1] if plain_only else FORMS
    for depth in DEPTHS:
        for fi, (form, code) in enumerate(forms):
            for rep in range(reps):
                key = "{}-{}-{}".format(code, depth, rep + 1)
                f = {"key": key, "form": form, "code": code, "depth": depth, "rep": rep + 1,
                     "slot": fi * reps + rep}
                if form == "plain":
                    brand, typ = pools.product()
                    product = "{} {}".format(brand, typ)
                    attr = pools.any_attr()
                    value = draw_value(rng, attr_kind(attr))
                    f.update(question="What is the {} for {}?".format(attr, product), expected=value,
                             answer_kind=attr_kind(attr), trap_label="none", trap_answers="",
                             anchor="@@NUM@@ " + sentence(rng, attr, product, value))
                elif form == "superseded":
                    brand, typ = pools.product()
                    product = "{} {}".format(brand, typ)
                    attr = pools.any_attr()
                    kind = attr_kind(attr)
                    v0 = draw_value(rng, kind)
                    v1 = draw_value(rng, kind, avoid=(v0,))
                    date = draw_date(rng)
                    f.update(question="What is the {} for {}?".format(attr, product), expected=v1,
                             answer_kind=kind, trap_label="stale_version", trap_answers=v0,
                             anchor="@@NUM@@ " + sentence(rng, attr, product, v0),
                             date=date,
                             amendment="Amendment @@AMD@@ (effective {}) replaces clause @@REF:{}@@. "
                                       "The {} for {} is {}.".format(date, key, attr, product, v1))
                elif form == "exception":
                    brand, typ = pools.product()
                    product = "{} {}".format(brand, typ)
                    fee, event = pools.pair()
                    covered = rep < reps - 1  # the last replicate asks about a reason the footnote does not cover
                    reason = rng.choice(COVERED_REASONS if covered else UNCOVERED_REASONS)
                    footnote_reason = reason if covered else rng.choice(COVERED_REASONS)
                    value = draw_value(rng, "money_fee")
                    expected = "no" if covered else "yes"
                    f.update(question="Is the {} on {} charged when {} because of {}?".format(fee, product, event, reason),
                             expected=expected, answer_kind="yes_no",
                             trap_label="exception_missed" if covered else "exception_over_applied",
                             trap_answers="yes" if covered else "no",
                             anchor="@@NUM@@ The {} on {} is {} and is charged when {}.".format(fee, product, value, event),
                             note="Note to clause @@REF:{}@@: The {} on {} is not charged when {} because of {}.".format(
                                 key, fee, product, event, footnote_reason))
                elif form == "table":
                    brand, typ = pools.product()
                    product = "{} {}".format(brand, typ)
                    attr = pools.fee_attr()
                    t1 = rng.choice([10, 12, 15, 18, 20, 25, 30, 35])
                    tiers = [t1, int(round(t1 * 0.6)), max(2, int(round(t1 * 0.25)))]
                    ask = rng.choice([2, 3])
                    decoy_rows = []
                    for db in rng.sample(DECOY_BRANDS, 2):
                        d1 = rng.choice([10, 12, 15, 18, 20, 25, 30, 35])
                        # decoy rows share the target's product type, so one table never mixes type words
                        decoy_rows.append("| {} {} | {} | {} | {} |".format(
                            db, typ, fmt_money(d1), fmt_money(int(round(d1 * 0.6))), fmt_money(max(2, int(round(d1 * 0.25))))))
                    row = "| {} | {} | {} | {} |".format(product, *[fmt_money(t) for t in tiers])
                    rows = decoy_rows[:]
                    rows.insert(rng.randrange(3), row)
                    table = "Table @@NUM@@. {} by balance tier\n| Product | Tier 1 | Tier 2 | Tier 3 |\n{}".format(
                        cap_first(attr), "\n".join(rows))
                    f.update(question="What is the {} for {} at Tier {}?".format(attr, product, ask),
                             expected=fmt_money(tiers[ask - 1]), answer_kind="money_fee",
                             trap_label="wrong_column", trap_answers=fmt_money(tiers[0]), anchor=table)
                elif form == "two_section":
                    brand, typ = pools.product()
                    product = "{} {}".format(brand, typ)
                    attr = pools.fee_attr()
                    base = rng.choice([20, 40, 60, 80])
                    pct = rng.choice([25, 50])
                    f.update(question="What is the {} for {}?".format(attr, product),
                             expected=fmt_money(base * (100 - pct) / 100.0), answer_kind="money_fee",
                             trap_label="single_clause",
                             trap_answers="{}|{}".format(fmt_percent(pct), fmt_money(base)),
                             anchor="@@NUM@@ The standard {} is {}.".format(attr, fmt_money(base)),
                             second="@@NUM@@ {} receives {} off the standard {}.".format(product, fmt_percent(pct), attr))
                else:  # distractor
                    brand, typ = pools.product()
                    product = "{} {}".format(brand, typ)
                    attr = pools.any_attr()
                    kind = attr_kind(attr)
                    mods = rng.sample(MODIFIERS, 2)
                    value = draw_value(rng, kind)
                    s1 = draw_value(rng, kind, avoid=(value,))
                    s2 = draw_value(rng, kind, avoid=(value, s1))
                    sib1 = "{} {} {}".format(brand, mods[0], typ)
                    sib2 = "{} {} {}".format(brand, mods[1], typ)
                    f.update(question="What is the {} for {}?".format(attr, product), expected=value,
                             answer_kind=kind, trap_label="sibling_answer", trap_answers="{}|{}".format(s1, s2),
                             anchor="@@NUM@@ " + sentence(rng, attr, product, value),
                             before="@@NUM@@ " + sentence(rng, attr, sib1, s1),
                             after="@@NUM@@ " + sentence(rng, attr, sib2, s2))
                facts.append(f)
    return facts


# ---------------------------------------------------------------------------
# manual assembly
# ---------------------------------------------------------------------------
def build_filler(rng: random.Random, target_chars: int, n_sections: int) -> list:
    headings = ["{} {}".format(t, a) for t in TOPICS for a in ASPECTS]
    rng.shuffle(headings)
    blocks = []
    per_section = target_chars / float(n_sections)
    for s in range(n_sections):
        blocks.append({"kind": "heading", "text": "Section @@SEC@@. " + headings[s]})
        size = 0
        while size < per_section:
            t = "@@NUM@@ " + clause_text(rng)
            blocks.append({"kind": "clause", "text": t})
            size += len(t) + 2
    blocks.append({"kind": "heading", "text": "Section @@SEC@@. Document Control"})
    for _ in range(4):
        blocks.append({"kind": "clause", "text": "@@NUM@@ " + clause_text(rng)})
    return blocks


def assemble(pages: int, with_register: bool, attempt: int, audit: bool = True) -> tuple:
    """Build one manual. Returns (text, facts, spans, n_blocks, n_sections, register_start); raises ValueError if the probe audit fails."""
    rng = random.Random(SEED + pages * 1000 + attempt)
    plain_only = pages == SHORT_PAGES
    reps = 2 if plain_only else REPS
    facts = plan_facts(rng, plain_only, reps)

    front = [
        {"kind": "front", "text": "Retail and Business Banking Policy Manual"},
        {"kind": "front", "text": "Version 14.2, issued 2026-07-01. Synthetic test document generated for PolicyNeedle."},
        {"kind": "front", "text": "This is a synthetic document. Every product name, amount and rule in it is "
                                  "invented. No real institution, customer or system is described."},
        {"kind": "front", "text": "How to read this manual. Clauses are numbered by section. " + (
            "Where an amendment listed in Appendix A replaces a clause, the amendment governs. " if with_register else "")
            + "A note that cites a clause applies to that clause."},
    ]

    # --- sizes -----------------------------------------------------------
    target_total = pages * PAGE_CHARS
    planted_chars = 0
    for f in facts:
        for k in ("anchor", "amendment", "note", "second", "before", "after"):
            if k in f:
                planted_chars += len(f[k]) + 2
    n_fill_amend = 0 if not with_register else pages // 4
    register_chars = 0
    if with_register:
        register_chars = 40 + n_fill_amend * 190
    front_chars = sum(len(b["text"]) + 2 for b in front)
    doc_control_chars = 700
    filler_target = max(2000, target_total - front_chars - planted_chars - register_chars - doc_control_chars + (CALIBRATION if pages > SHORT_PAGES else 0))
    n_sections = max(3, pages // 3 + 2) if pages > SHORT_PAGES else 3
    filler = build_filler(rng, filler_target, n_sections)

    starts = []
    pos = 0
    for b in filler:
        starts.append(pos)
        pos += len(b["text"]) + 2
    heading_idx = [i for i, b in enumerate(filler) if b["kind"] == "heading"]
    doc_ctrl_idx = heading_idx[-1]
    main_len = starts[doc_ctrl_idx]

    def clause_at(target: float) -> int:
        i = bisect_left(starts, target)
        i = min(i, doc_ctrl_idx - 1)
        while filler[i]["kind"] != "clause":
            i += 1
        return i

    def next_heading(i: int) -> int:
        return heading_idx[bisect_left(heading_idx, i + 1)]

    inserts = []  # (index, seq, block)
    seq = 0

    def add(idx: int, block: dict) -> None:
        nonlocal seq
        seq += 1
        inserts.append((idx, seq, block))

    amendments = []
    for f in facts:
        depth, slot = f["depth"], f["slot"]
        if depth == 0:
            target = slot * 130.0
        elif depth == 100:
            target = main_len - 2800.0 + slot * 130.0
        else:
            target = depth / 100.0 * main_len + (slot - 8.5) * 130.0
        key = f["key"]
        if f["form"] == "two_section":
            if depth == 0:
                aidx, sidx = 1, heading_idx[1] + 1
            else:
                i = clause_at(target)
                h_next = next_heading(i)
                h_prev = max(h for h in heading_idx if h <= i)
                # nearest section boundary to the target; anchor goes at the end of the section before it
                if abs(starts[h_next] - target) <= abs(starts[h_prev] - target) or h_prev == 0:
                    aidx = h_next
                else:
                    aidx = h_prev
                sidx = aidx + 1
            add(aidx, {"kind": "clause", "text": f["anchor"], "key": key, "role": "anchor"})
            add(sidx, {"kind": "clause", "text": f["second"], "key": key, "role": "second"})
            continue
        i = clause_at(target)
        if f["form"] == "distractor":
            add(i, {"kind": "clause", "text": f["before"], "key": key, "role": "before"})
            add(i, {"kind": "clause", "text": f["anchor"], "key": key, "role": "anchor"})
            add(i, {"kind": "clause", "text": f["after"], "key": key, "role": "after"})
            continue
        kind = "table" if f["form"] == "table" else "clause"
        add(i, {"kind": kind, "text": f["anchor"], "key": key, "role": "anchor"})
        if f["form"] == "exception":
            nidx = min(i + rng.randint(3, 8), next_heading(i))
            add(nidx, {"kind": "note", "text": f["note"], "key": key, "role": "note"})
        if f["form"] == "superseded":
            amendments.append({"kind": "amendment", "text": f["amendment"], "key": key, "role": "amendment",
                               "date": f["date"]})

    inserts.sort(key=lambda t: (t[0], t[1]))
    body = []
    j = 0
    for idx, b in enumerate(filler):
        while j < len(inserts) and inserts[j][0] <= idx:
            body.append(dict(inserts[j][2]))
            j += 1
        body.append(dict(b))
    while j < len(inserts):
        body.append(dict(inserts[j][2]))
        j += 1

    # --- numbering --------------------------------------------------------
    sec = 0
    k = 0
    nums = {}
    for b in body:
        if b["kind"] == "heading":
            sec += 1
            k = 0
            b["text"] = b["text"].replace("@@SEC@@", str(sec))
        elif "@@NUM@@" in b["text"]:
            k += 1
            num = "{}.{}".format(sec, k)
            b["text"] = b["text"].replace("@@NUM@@", num)
            if b.get("role") == "anchor":
                nums[b["key"]] = num

    # --- register ---------------------------------------------------------
    register = []
    if with_register:
        items = amendments[:]
        filler_nums = [b["text"].split(" ", 1)[0] for b in body if b["kind"] == "clause" and "key" not in b]
        for _ in range(n_fill_amend):
            date = draw_date(rng)
            items.append({"kind": "amendment", "role": "register_filler", "date": date, "text":
                          "Amendment @@AMD@@ (effective {}) replaces clause {}. {}".format(
                              date, rng.choice(filler_nums), clause_text(rng))})
        items.sort(key=lambda b: b["date"])
        register.append({"kind": "heading", "text": "Appendix A. Amendment Register"})
        for n, b in enumerate(items, start=1):
            b["text"] = b["text"].replace("@@AMD@@", str(n))
            register.append(b)

    all_blocks = front + body + register
    for b in all_blocks:
        text = b["text"]
        for key, num in nums.items():
            text = text.replace("@@REF:{}@@".format(key), num)
        b["text"] = text
        assert "@@" not in text, text

    # --- text and evidence offsets ---------------------------------------
    pos = 0
    parts = []
    spans = {}
    for b in all_blocks:
        parts.append(b["text"])
        if b.get("key"):
            spans.setdefault(b["key"], {})[b["role"]] = (pos, pos + len(b["text"]))
        pos += len(b["text"]) + 2
    text = "\n\n".join(parts) + "\n"

    # --- audit: the keyword rule must find exactly the intended blocks -----
    block_tokens = [(b["text"], set(TOKEN_RE.findall(b["text"].lower()))) for b in all_blocks]
    for f in facts:
        qw = question_words(f["question"])
        cands = [t for t, toks in block_tokens if MATCH_DEN * len(qw & toks) >= MATCH_NUM * len(qw)]
        if audit and len(cands) != EXPECTED_CANDIDATES[f["form"]]:
            raise ValueError("audit failed for {} (attempt {}): {} candidates".format(f["key"], attempt, len(cands)))

    return text, facts, spans, len(front) + len(body) + len(register), sec, register_start(all_blocks)


def register_start(all_blocks: list) -> int:
    pos = 0
    for b in all_blocks:
        if b["kind"] == "heading" and b["text"].startswith("Appendix A."):
            return pos
        pos += len(b["text"]) + 2
    return -1


def build_manual(pages: int, with_register: bool) -> tuple:
    for attempt in range(40):
        try:
            return assemble(pages, with_register, attempt) + (attempt,)
        except ValueError:
            continue
    raise RuntimeError("no clean draw for {} pages".format(pages))


# ---------------------------------------------------------------------------
# outputs
# ---------------------------------------------------------------------------
def evidence_for(f: dict, spans: dict) -> tuple:
    """(primary start, required evidence end, spans text) for one probe."""
    sp = spans[f["key"]]
    start = sp["anchor"][0]
    form = f["form"]
    if form == "superseded":
        end = sp["amendment"][1]
    elif form == "exception":
        end = sp["note"][1] if f["expected"] == "no" else sp["anchor"][1]
    elif form == "two_section":
        end = sp["second"][1]
    else:
        end = sp["anchor"][1]
    text = ";".join("{}:{}-{}".format(role, a, b) for role, (a, b) in sorted(sp.items(), key=lambda kv: kv[1][0]))
    return start, end, text


def main() -> None:
    MANUAL_DIR.mkdir(exist_ok=True)
    manuals_rows = []
    probe_rows = []
    for pages, code, with_register, probe_set in (
        [(SHORT_PAGES, "S", False, "short_spot")] + [(p, "L", True, "long_sweep") for p in LONG_PAGES]
    ):
        text, facts, spans, n_blocks, n_sections, reg_start, attempt = build_manual(pages, with_register)
        manual_id = "manual_{:03d}p".format(pages)
        with open(MANUAL_DIR / (manual_id + ".txt"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        chars = len(text)
        manuals_rows.append({
            "manual_id": manual_id, "file": "manuals/{}.txt".format(manual_id), "nominal_pages": pages,
            "chars": chars, "approx_pages": "{:.1f}".format(chars / float(PAGE_CHARS)), "sections": n_sections,
            "blocks": n_blocks, "planted_facts": len(facts),
            "register_start_char": reg_start if reg_start >= 0 else "", "draw": attempt,
        })
        for f in facts:
            start, end, span_text = evidence_for(f, spans)
            probe_rows.append({
                "probe_id": "{}{:03d}-{}-{:03d}-{}".format(code, pages, f["code"], f["depth"], f["rep"]),
                "probe_set": probe_set, "manual_id": manual_id, "length_pages": pages, "doc_chars": chars,
                "form": f["form"], "depth_pct": f["depth"],
                "position_pct": "{:.1f}".format(100.0 * start / chars),
                "question": f["question"], "expected_answer": f["expected"], "answer_kind": f["answer_kind"],
                "evidence_start": start, "evidence_end": end, "evidence_spans": span_text,
                "trap_label": f["trap_label"], "trap_answers": f["trap_answers"], "scoring": "exact",
            })

    with open(OUT / "manuals.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manuals_rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(manuals_rows)
    with open(OUT / "probes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(probe_rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(probe_rows)

    counts = {}
    for r in probe_rows:
        counts[r["form"]] = counts.get(r["form"], 0) + 1
    types = [
        ("plain", "yes", "A single clause holds the answer."),
        ("superseded", "yes", "An amendment later in the document replaces the clause."),
        ("exception", "yes", "A footnote carves out an exception; the answer is yes or no."),
        ("table", "yes", "The answer is one cell of a tier table."),
        ("two_section", "yes", "The answer needs two clauses from different sections."),
        ("distractor", "yes", "A near-duplicate clause for a sibling product sits next to the true clause."),
    ]
    rows = [{"probe_type": n, "scorable_by_exact_match": s, "n_probes": counts.get(n, 0), "description": d}
            for n, s, d in types]
    unscorable = [
        ("paraphrased_answer", "The right value stated in other words, for example twenty-five thousand dollars."),
        ("unit_converted_answer", "The right value in another unit, for example 48 hours for 2 days."),
        ("verbose_or_hedged_answer", "The right value inside a full sentence, or with a caveat."),
        ("multi_value_answer", "Several values that can be listed in any order."),
        ("free_text_explanation", "An explanation or a clause citation that has no single string to match."),
    ]
    for n, d in unscorable:
        rows.append({"probe_type": n, "scorable_by_exact_match": "no", "n_probes": 0, "description": d})
    with open(OUT / "probe_types.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["probe_type", "scorable_by_exact_match", "n_probes", "description"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print("manuals:")
    for m in manuals_rows:
        print("  {manual_id}: {chars} chars, about {approx_pages} pages, {sections} sections, "
              "{planted_facts} planted facts, draw {draw}".format(**m))
    print("probes: {} ({} short spot test, {} long sweep)".format(
        len(probe_rows), sum(1 for r in probe_rows if r["probe_set"] == "short_spot"),
        sum(1 for r in probe_rows if r["probe_set"] == "long_sweep")))


if __name__ == "__main__":
    main()
