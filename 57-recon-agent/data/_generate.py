"""Generate the synthetic data for project 57: a bank-statement ledger (A) and a cash-book ledger (B)
for one month, with the answer key.

Everything is seeded, so the files are byte-for-byte reproducible. The answer key comes from the way
the rows were made: the generator first decides what really happened (a payment, a batch, a bank fee,
an outstanding item), then writes each ledger's view of it with that ledger's own noise (date lag,
reference formatting, name abbreviations, a netted fee). It never calls the matching rules. Some kinds
are hard on purpose: look-alike pairs that must not match (hard negatives), and true pairs the rules
cannot find (planted misses).

Amounts are unique across the month except where a kind needs a repeat, so no match arises by accident.

Run (from data/):  python3 _generate.py
Writes:  ledger_a.csv, ledger_b.csv, truth.csv, example_ledger_a.csv, example_ledger_b.csv, example_approvals.csv
"""
import csv
import random
from datetime import date, timedelta

SEED = 57
START = date(2026, 3, 2)
FIRST = ["Bra", "Cor", "Hal", "Opt", "Sun", "Dun", "Mar", "Vel", "Tor", "Kin", "Pra", "Lor", "Fen", "Gal", "Wyn", "Quo", "Ris", "Sel"]
TAIL = ["ndle", "van", "den", "rel", "mere", "vale", "ton", "lin", "mont", "wick"]
KINDS = ["Paper", "Foods", "Ceramics", "Logistics", "Textiles", "Tooling", "Plastics", "Freight", "Services", "International", "Distribution"]
FORMS = ["Limited", "Inc", "LLC", "Co"]
BANK_FORM = {"Limited": "LTD", "Inc": "INC", "LLC": "LLC", "Co": "CO"}
BANK_WORD = {"Services": "SVCS", "International": "INTL", "Distribution": "DIST", "Manufacturing": "MFG"}
FEES = [150, 250, 1500]
OWN_BANK = "FENWICK SAVINGS BANK"
BANK_NARRATIVES = [("MONTHLY ACCOUNT FEE", -1), ("WIRE TRANSFER FEE", -1), ("CARD SETTLEMENT FEE", -1), ("INTEREST CREDIT", 1)]

# (kind, how many). The order only matters for the random draws, which are fixed by the seed.
PLAN = [("exact", 110), ("large", 10), ("date_lag", 60), ("ref_format", 40), ("fee_netted", 20), ("batch", 12),
        ("ref_typo", 15), ("no_ref", 30), ("payer_differs", 8), ("dup_b", 8),
        ("split_no_batch", 4), ("out_of_window", 6), ("ref_garbled", 4), ("no_ref_abbrev", 4),
        ("lookalike_conflict", 10), ("near_ref_distinct", 6), ("twin_payments", 6), ("currency_clash", 5),
        ("a_only", 25), ("b_only", 30)]


class World:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        combos = [f + t for f in FIRST for t in TAIL]
        picked = self.rng.sample(combos, 52)
        self.cps = [{"first": c, "kind": self.rng.choice(KINDS), "form": self.rng.choice(FORMS)} for c in picked[:40]]
        self.mfg = [{"first": c, "kind": "Manufacturing", "form": self.rng.choice(FORMS)} for c in picked[40:44]]
        self.treasuries = [f"{c} Group Treasury" for c in picked[44:52]]
        self.refs, self.amounts, self.batches = set(), set(), set()
        self.items = []

    # ---- draws
    def amount(self, lo=5000, hi=900000):
        while True:
            c = self.rng.randrange(lo, hi)
            if c not in self.amounts:
                self.amounts.add(c)
                return c

    def ref(self, receipt):
        while True:
            r = f"INV-{self.rng.randrange(10000, 20000)}" if receipt else f"PMT-{self.rng.randrange(100, 10000):06d}"
            if r not in self.refs:
                self.refs.add(r)
                return r

    def day(self):
        return START + timedelta(days=self.rng.randrange(28))

    def lag(self, lo, hi):
        return self.rng.choice([-1, 1]) * self.rng.randint(lo, hi)

    @staticmethod
    def name(cp):
        return f"{cp['first']} {cp['kind']} {cp['form']}"

    def bank_name(self, cp, abbreviate):
        word = BANK_WORD.get(cp["kind"], cp["kind"].upper()) if abbreviate else cp["kind"].upper()
        return f"{cp['first'].upper()} {word} {BANK_FORM[cp['form']]}"

    def reformat(self, ref):
        prefix, num = ref.split("-")
        options = [ref.lower(), prefix + num, prefix + " " + num]
        options.append(f"INV-0{num}" if prefix == "INV" else f"PMT-{int(num)}")
        return self.rng.choice(options)

    def one_edit(self, ref):
        """A different invoice number one edit away (a substitution or a swap of two neighbouring digits)."""
        while True:
            digits = list(ref[4:])
            i = self.rng.randrange(1, 4)
            if self.rng.random() < 0.5:
                digits[i] = str(self.rng.choice([d for d in "0123456789" if d != digits[i]]))
            else:
                digits[i], digits[i + 1] = digits[i + 1], digits[i]
            r = "INV-" + "".join(digits)
            if r != ref and r not in self.refs:
                self.refs.add(r)
                return r

    def two_edits(self, ref):
        """A different invoice number two substitutions away, never on the first digit and never next to each other."""
        while True:
            digits = list(ref[4:])
            i, j = self.rng.choice([(1, 3), (1, 4), (2, 4)])
            for k in (i, j):
                digits[k] = str(self.rng.choice([d for d in "0123456789" if d != digits[k]]))
            r = "INV-" + "".join(digits)
            if r not in self.refs:
                self.refs.add(r)
                return r

    # ---- rows and links
    @staticmethod
    def a_row(day, cents, name, narrative, ref, ccy="USD"):
        return {"side": "A", "date": day, "cents": cents, "ccy": ccy, "name": name, "narr": narrative, "ref": ref}

    @staticmethod
    def b_row(day, cents, name, ref, memo, batch="", ccy="USD"):
        return {"side": "B", "date": day, "cents": cents, "ccy": ccy, "name": name, "ref": ref, "batch": batch, "memo": memo}

    def narrative(self, cents, name):
        return f"{'CREDIT' if cents > 0 else 'DEBIT'} TRANSFER {name}"

    def memo(self, cents, cp):
        return f"{'Receipt from' if cents > 0 else 'Payment to'} {self.name(cp)}"

    def add(self, rows, links):
        self.items.append({"rows": rows, "links": links})

    # ---- one builder per kind
    def pair(self, kind, lag=0, lo=5000, hi=900000, ref_a=None, ref_blank="", name_a=None, cp=None, abbreviate=None,
             cents_a=None, receipt=None):
        cp = cp or self.rng.choice(self.cps)
        receipt = self.rng.random() < 0.65 if receipt is None else receipt
        cents = self.amount(lo, hi) * (1 if receipt else -1)
        ref = self.ref(receipt)
        day = self.day()
        if abbreviate is None:
            abbreviate = self.rng.random() < 0.4
        a_cents = cents if cents_a is None else cents_a
        a_name = name_a or self.bank_name(cp, abbreviate)
        a_ref = ref if ref_a is None else ref_a
        b_ref = ref
        if ref_blank == "a":
            a_ref = ""
        elif ref_blank == "b":
            b_ref = ""
        a = self.a_row(day, a_cents, a_name, self.narrative(a_cents, a_name), a_ref)
        b = self.b_row(day + timedelta(days=lag), cents, self.name(cp), b_ref, self.memo(cents, cp))
        self.add([a, b], [(kind, "match", [a], [b])])
        return a, b, ref

    def build(self, kind):
        r = self.rng
        if kind == "exact":
            self.pair(kind)
        elif kind == "large":
            self.pair(kind, lo=1000100, hi=6000000)
        elif kind == "date_lag":
            self.pair(kind, lag=self.lag(1, 3))
        elif kind == "ref_format":
            a, b, _ = self.pair(kind, lag=r.choice([0, 1, -1]), ref_a="x")
            a["ref"] = self.reformat(b["ref"])
        elif kind == "fee_netted":
            fee = r.choice(FEES)
            a, b, _ = self.pair(kind, lag=r.choice([0, 1, 2]), lo=10000, receipt=True)
            a["cents"] = b["cents"] - fee
            a["narr"] = self.narrative(a["cents"], a["name"])
            self.amounts.add(a["cents"])
        elif kind == "batch":
            self.batch()
        elif kind == "ref_typo":
            a, b, _ = self.pair(kind, lag=r.choice([0, 1, 2, 3]), receipt=True, ref_a="x")
            a["ref"] = self.one_edit(b["ref"])
        elif kind == "no_ref":
            self.pair(kind, lag=r.choice([0, 1, 2, 3]), ref_blank="a" if r.random() < 2 / 3 else "b")
        elif kind == "payer_differs":
            self.pair(kind, lag=r.choice([0, 1, 2]), name_a=r.choice(self.treasuries).upper())
        elif kind == "dup_b":
            a, b, _ = self.pair(kind, lag=r.choice([0, 1]))
            dup = dict(b)
            self.items[-1]["rows"].append(dup)
            self.items[-1]["links"].append((kind, "b_only", [], [dup]))
        elif kind == "split_no_batch":
            self.split()
        elif kind == "out_of_window":
            self.pair(kind, lag=self.lag(4, 6))
        elif kind == "ref_garbled":
            a, b, _ = self.pair(kind, lag=r.choice([0, 1]), receipt=True, ref_a="x")
            a["ref"] = self.two_edits(b["ref"])
        elif kind == "no_ref_abbrev":
            cp = self.mfg[len([i for i in self.items if i["links"][0][0] == kind]) % len(self.mfg)]
            self.pair(kind, lag=r.choice([0, 1, 2]), cp=cp, ref_blank="a", abbreviate=True)
        elif kind in ("lookalike_conflict", "near_ref_distinct", "currency_clash"):
            self.lookalike(kind)
        elif kind == "twin_payments":
            self.twin()
        elif kind == "a_only":
            text, sign = r.choice(BANK_NARRATIVES)
            cents = sign * self.amount(500, 20000)
            a = self.a_row(self.day(), cents, OWN_BANK, text, "")
            self.add([a], [(kind, "a_only", [a], [])])
        elif kind == "b_only":
            cp = r.choice(self.cps)
            cents = -self.amount()
            b = self.b_row(self.day(), cents, self.name(cp), self.ref(False), self.memo(cents, cp))
            self.add([b], [(kind, "b_only", [], [b])])

    def batch(self, kind="batch", blank=False):
        r = self.rng
        cp = r.choice(self.cps)
        receipt = r.random() < 0.5
        sign = 1 if receipt else -1
        n = r.choice([3, 4]) if not blank else r.choice([2, 3])
        while True:
            tag = f"BT-{r.randrange(1000, 10000)}"
            if tag not in self.batches:
                self.batches.add(tag)
                break
        day = self.day()
        lines = [sign * self.amount(5000, 300000) for _ in range(n)]
        total = sum(lines)
        self.amounts.add(abs(total))
        bs = [self.b_row(day, c, self.name(cp), self.ref(receipt), self.memo(c, cp), "" if blank else tag) for c in lines]
        a_name = self.bank_name(cp, False)
        a = self.a_row(day + timedelta(days=r.choice([0, 1, 2])), total, a_name, self.narrative(total, a_name), "" if blank else tag)
        self.add([a] + bs, [(kind, "match", [a], bs)])

    def split(self):
        self.batch(kind="split_no_batch", blank=True)

    def lookalike(self, kind):
        r = self.rng
        cp = r.choice(self.cps)
        receipt = True if kind == "near_ref_distinct" else r.random() < 0.65
        cents = self.amount() * (1 if receipt else -1)
        day = self.day()
        ref_b = self.ref(receipt)
        if kind == "lookalike_conflict":
            ref_a = self.ref(receipt)
            while sum(1 for x, y in zip(ref_a, ref_b) if x != y) < 3:
                ref_a = self.ref(receipt)
            lag = r.choice([0, 1, 2, -1])
        elif kind == "near_ref_distinct":
            ref_a = self.one_edit(ref_b)
            lag = r.choice([0, 1])
        else:
            ref_a, lag = ref_b, r.choice([0, 1])
        name_a = self.bank_name(cp, False)
        a = self.a_row(day, cents, name_a, self.narrative(cents, name_a), ref_a)
        b = self.b_row(day + timedelta(days=lag), cents, self.name(cp), ref_b, self.memo(cents, cp), ccy="EUR" if kind == "currency_clash" else "USD")
        self.add([a, b], [(kind, "a_only", [a], []), (kind, "b_only", [], [b])])

    def twin(self):
        r = self.rng
        cp = r.choice(self.cps)
        cents = self.amount() * r.choice([1, -1])
        day = self.day()
        name_a = self.bank_name(cp, False)
        a = self.a_row(day + timedelta(days=1), cents, name_a, self.narrative(cents, name_a), "")
        b1 = self.b_row(day, cents, self.name(cp), "", self.memo(cents, cp))
        b2 = self.b_row(day + timedelta(days=2), cents, self.name(cp), "", self.memo(cents, cp))
        real, other = r.sample([b1, b2], 2)
        self.add([a, b1, b2], [("twin_payments", "match", [a], [real]), ("twin_payments", "b_only", [], [other])])

    def finish(self):
        self.rng.shuffle(self.items)
        rows = [row for item in self.items for row in item["rows"]]
        a_rows = sorted([x for x in rows if x["side"] == "A"], key=lambda x: x["date"])
        b_rows = sorted([x for x in rows if x["side"] == "B"], key=lambda x: x["date"])
        for i, x in enumerate(a_rows, 1):
            x["id"] = f"BK-{i:06d}"
        for i, x in enumerate(b_rows, 1):
            x["id"] = f"GL-{i:06d}"
        return a_rows, b_rows


def money(c):
    return f"{'-' if c < 0 else ''}{abs(c) // 100}.{abs(c) % 100:02d}"


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


A_HEAD = ["a_id", "value_date", "amount", "currency", "counterparty", "narrative", "customer_ref"]
B_HEAD = ["b_id", "posting_date", "amount", "currency", "counterparty", "reference", "batch_id", "memo"]


def a_line(x):
    return [x["id"], x["date"].isoformat(), money(x["cents"]), x["ccy"], x["name"], x["narr"], x["ref"]]


def b_line(x):
    return [x["id"], x["date"].isoformat(), money(x["cents"]), x["ccy"], x["name"], x["ref"], x["batch"], x["memo"]]


def write_example():
    """A hand-made month of 11 bank lines and 15 book lines that shows every outcome once."""
    a = [("BK-000001", "2026-03-02", "1250.00", "BRINDLE FOODS LTD", "CREDIT TRANSFER BRINDLE FOODS LTD", "inv-10453"),
         ("BK-000002", "2026-03-03", "4998.50", "CORVAN TEXTILES INC", "CREDIT TRANSFER CORVAN TEXTILES INC", "INV-10460"),
         ("BK-000003", "2026-03-04", "3000.00", "HALDEN FREIGHT CO", "CREDIT TRANSFER HALDEN FREIGHT CO", "BT-0304"),
         ("BK-000004", "2026-03-05", "-780.00", "OPTREL PLASTICS LLC", "DEBIT TRANSFER OPTREL PLASTICS LLC", "PMT-004517"),
         ("BK-000005", "2026-03-06", "2200.00", "SUNMERE TOOLING LTD", "CREDIT TRANSFER SUNMERE TOOLING LTD", "INV-10481"),
         ("BK-000006", "2026-03-09", "6400.00", "BRINDLE FOODS LTD", "CREDIT TRANSFER BRINDLE FOODS LTD", ""),
         ("BK-000007", "2026-03-10", "900.00", "CORVAN TEXTILES INC", "CREDIT TRANSFER CORVAN TEXTILES INC", ""),
         ("BK-000008", "2026-03-12", "-35.00", OWN_BANK, "MONTHLY ACCOUNT FEE", ""),
         ("BK-000009", "2026-03-16", "1200.00", "OPTREL PLASTICS LLC", "CREDIT TRANSFER OPTREL PLASTICS LLC", "INV-11204"),
         ("BK-000010", "2026-03-18", "15000.00", "SUNMERE TOOLING LTD", "CREDIT TRANSFER SUNMERE TOOLING LTD", "INV-10500"),
         ("BK-000011", "2026-03-20", "410.00", "BRINDLE FOODS LTD", "CREDIT TRANSFER BRINDLE FOODS LTD", "INV-10490")]
    b = [("GL-000001", "2026-03-02", "1250.00", "Brindle Foods Limited", "INV-10453", "", "Receipt from Brindle Foods Limited"),
         ("GL-000002", "2026-03-03", "5000.00", "Corvan Textiles Inc", "INV-10460", "", "Receipt from Corvan Textiles Inc"),
         ("GL-000003", "2026-03-04", "1000.00", "Halden Freight Co", "INV-10462", "BT-0304", "Receipt from Halden Freight Co"),
         ("GL-000004", "2026-03-04", "1200.00", "Halden Freight Co", "INV-10463", "BT-0304", "Receipt from Halden Freight Co"),
         ("GL-000005", "2026-03-04", "800.00", "Halden Freight Co", "INV-10464", "BT-0304", "Receipt from Halden Freight Co"),
         ("GL-000006", "2026-03-04", "-780.00", "Optrel Plastics LLC", "PMT-4517", "", "Payment to Optrel Plastics LLC"),
         ("GL-000007", "2026-03-06", "2200.00", "Sunmere Tooling Limited", "INV-10418", "", "Receipt from Sunmere Tooling Limited"),
         ("GL-000008", "2026-03-09", "6400.00", "Brindle Foods Limited", "INV-10477", "", "Receipt from Brindle Foods Limited"),
         ("GL-000009", "2026-03-09", "900.00", "Corvan Textiles Inc", "", "", "Receipt from Corvan Textiles Inc"),
         ("GL-000010", "2026-03-11", "900.00", "Corvan Textiles Inc", "", "", "Receipt from Corvan Textiles Inc"),
         ("GL-000011", "2026-03-13", "-2150.00", "Halden Freight Co", "PMT-004530", "", "Payment to Halden Freight Co"),
         ("GL-000012", "2026-03-16", "1200.00", "Optrel Plastics LLC", "INV-11911", "", "Receipt from Optrel Plastics LLC"),
         ("GL-000013", "2026-03-18", "15000.00", "Sunmere Tooling Limited", "INV-10500", "", "Receipt from Sunmere Tooling Limited"),
         ("GL-000014", "2026-03-20", "410.00", "Brindle Foods Limited", "INV-10490", "", "Receipt from Brindle Foods Limited"),
         ("GL-000015", "2026-03-20", "410.00", "Brindle Foods Limited", "INV-10490", "", "Receipt from Brindle Foods Limited")]
    write_csv("example_ledger_a.csv", A_HEAD, [[i, d, m, "USD", n, t, r] for i, d, m, n, t, r in a])
    write_csv("example_ledger_b.csv", B_HEAD, [[i, d, m, "USD", n, r, bt, memo] for i, d, m, n, r, bt, memo in b])
    write_csv("example_approvals.csv", ["key", "decision", "approver", "note"], [
        ["ref_fee:BK-000002:GL-000002:499850", "approve", "reviewer-1", "remittance advice shows a 1.50 fee"],
        ["batch_sum:BK-000003:GL-000003+GL-000004+GL-000005:300000", "approve", "reviewer-1", "three invoices in one remittance"],
        ["ref_near:BK-000005:GL-000007:220000", "reject", "reviewer-2", "two different invoices"],
        ["name_amount:BK-000006:GL-000016:640000", "approve", "reviewer-1", "approved against a line that is not the one proposed"],
        ["ref_exact:BK-000010:GL-000013:1500000", "approve", "recon-agent", "above the limit"]])


def main():
    world = World(SEED)
    for kind, count in PLAN:
        for _ in range(count):
            world.build(kind)
    a_rows, b_rows = world.finish()
    write_csv("ledger_a.csv", A_HEAD, [a_line(x) for x in a_rows])
    write_csv("ledger_b.csv", B_HEAD, [b_line(x) for x in b_rows])
    truth = []
    for item in world.items:
        for kind, status, la, lb in item["links"]:
            truth.append([kind, status, "+".join(sorted(x["id"] for x in la)), "+".join(sorted(x["id"] for x in lb))])
    truth.sort(key=lambda t: (t[2] or "zzz", t[3]))
    write_csv("truth.csv", ["link_id", "kind", "truth_status", "a_ids", "b_ids"], [[f"L-{i:04d}"] + t for i, t in enumerate(truth, 1)])
    write_example()
    print(f"wrote {len(a_rows)} bank lines, {len(b_rows)} book lines and {len(truth)} truth links")


if __name__ == "__main__":
    main()
