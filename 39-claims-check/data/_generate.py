"""Generate the synthetic data for project 39: 40 small projects, each with a README whose green
bullets cite numbers and the text that project's scripts printed, plus the planted truth per bullet.

Everything is seeded, so the files are byte-for-byte reproducible. The truth of a bullet comes from how
it was built (the number was copied from the output, or it was altered on purpose), not from the
checker. Some kinds are hard on purpose. A grep for the number passes a number that is only a piece
of a longer one, a rounded figure, and a pair that is never printed together. A strict checker flags
a pair that is printed as two separate lines. Two kinds slip past every rule in src/: a wrong number
that equals another printed number, and a wrong single-digit number.

Run (from data/):  python3 _generate.py
Writes:  projects.json, truth.csv, example_claims.md, example_output.txt
"""
from __future__ import annotations

import csv
import json
import random
import re

SEED = 39
N_PROJECTS = 40

KIND_COUNTS = [
    ("exact", 90), ("comma", 12), ("trailing_period", 12), ("trailing_zero", 10), ("inert_digits", 24),
    ("wrapped_ok", 10), ("not_green", 12), ("small_numeral", 8), ("pair_split", 8),
    ("typo", 14), ("stale", 14), ("invented", 10), ("substring_trap", 14), ("rounded", 8),
    ("pair_broken", 12), ("wrapped_bad", 8), ("coincidence", 10), ("single_digit", 8),
]
SUPPORTED = {"exact", "comma", "trailing_period", "trailing_zero", "inert_digits", "wrapped_ok", "not_green",
             "small_numeral", "pair_split"}

OBJECTS = ["payment exceptions", "reconciliation breaks", "KYC documents", "dispute cases", "screening alerts",
           "loan files", "wire repairs", "account statements", "complaints", "invoices", "chargeback cases",
           "onboarding cases"]
MEASURES = [("routed to the right queue", "routed"), ("closed on first touch", "closed first touch"),
            ("reopened within a week", "reopened"), ("held past the cut-off", "held"),
            ("matched without a person", "auto-matched")]
COMBOS = [(f"{o} {long}", f"{o} {short}") for o in OBJECTS for long, short in MEASURES]

NUMRE = r"[0-9][0-9,]*(?:\.[0-9]+)?"


class Retry(Exception):
    """The random draw could not satisfy a rule for this kind; draw the project again."""


def strip0(token):
    token = token.replace(",", "")
    return token.rstrip("0").rstrip(".") if "." in token else token


class Guard:
    """Generator-side checks on the finished evidence text, used to keep a planted number honest."""

    def __init__(self, text):
        self.flat = text.replace(",", "")
        self.tokens = {strip0(t) for t in re.findall(NUMRE, text)}
        self.pairs = {(strip0(a), strip0(b)) for a, b in re.findall("(" + NUMRE + r")\s*(?:of|/)\s*(" + NUMRE + ")", text)}

    def absent(self, s):
        return s not in self.flat

    def piece_only(self, s):
        return s in self.flat and s not in self.tokens


def pick(make, ok, tries=60):
    for _ in range(tries):
        candidate = make()
        if ok(candidate):
            return candidate
    raise Retry()


def new_metric(rng, vtype, combo, lo=None, hi=None):
    m = {"vtype": vtype, "subject": combo[0], "label": combo[1], "second": None, "suffix": "", "slash": False}
    if vtype == "ratio":
        b = rng.randint(lo or 20, hi or 400)
        m["main"], m["second"] = str(rng.randint(10, b - 5)), str(b)
    elif vtype == "count":
        m["main"] = str(rng.randint(lo or 12, hi or 9800))
    elif vtype == "percent":
        t = rng.randint(lo or 51, hi or 949)
        t += 1 if t % 10 == 0 else 0
        m["main"], m["suffix"] = f"{t / 10:.1f}", "%"
    else:
        t = rng.randint(lo or 121, hi or 2399)
        t += 1 if t % 10 == 0 else 0
        m["main"], m["suffix"] = f"{t / 100:.2f}", " days"
    return m


def show(m, main=None):
    main = m["main"] if main is None else main
    return f"{main} of {m['second']}" if m["vtype"] == "ratio" else f"{main}{m['suffix']}"


def ev_line(m, printed=None):
    if printed is None:
        printed = f"{m['main']}/{m['second']}" if m["slash"] else show(m)
    return f"  {m['label']}: {printed}"


def valid(m, c):
    if len(c.replace(".", "")) < 2 or c[0] == "0":
        return False
    if m["vtype"] == "ratio":
        return int(c) <= int(m["second"])
    if m["vtype"] == "percent":
        return float(c) < 100
    return True


def edit_digit(rng, s):
    idx = [i for i, ch in enumerate(s) if ch.isdigit()]
    i = rng.choice(idx)
    return s[:i] + rng.choice("0123456789".replace(s[i], "")) + s[i + 1:]


def shift(rng, s):
    places = len(s.split(".")[1]) if "." in s else 0
    y = float(s) * (1 + rng.uniform(0.05, 0.25) * rng.choice([-1, 1]))
    return f"{y:.{places}f}"


def cap(s):
    return s[0].upper() + s[1:]


def bullet(rng, subject, value, tail="", period=False):
    k = rng.randint(0, 1 if period else 2)
    end = "." if period else ""
    if k == 0:
        return f"- \U0001F7E2 {cap(subject)}: {value}{tail}{end}"
    if k == 1:
        return f"- \U0001F7E2 Measured: {subject} came to {value}{tail}{end}"
    return f"- \U0001F7E2 {cap(subject)}, {value}, on the synthetic set{tail}{end}"


def build_project(pid, kinds, attempt):
    rng = random.Random(f"{SEED}:{pid}:{attempt}")
    pool = rng.sample(COMBOS, 2 + 2 * len(kinds))
    vt = lambda: rng.choices(["ratio", "count", "percent", "decimal"], [4, 3, 2, 1])[0]  # noqa: E731
    seed_rows, batches = rng.choice([1000, 2000, 4000, 5000]), rng.randint(10, 40)
    evidence = [f"  seed: {SEED}", f"  rows generated: {seed_rows}", f"  batches: {batches}"]
    distractors = [str(SEED), str(seed_rows), str(batches)]
    partner = new_metric(rng, "ratio", pool.pop(), 450, 900)
    evidence += [ev_line(partner), ev_line(new_metric(rng, "count", pool.pop()))]

    plans = []
    for kind in kinds:
        p = {"kind": kind}
        two = kind in ("wrapped_ok", "wrapped_bad")
        if kind == "comma":
            p["m"] = new_metric(rng, "count", pool.pop(), 1000, 9800)
            p["comma_in_evidence"] = rng.random() < 0.5
            evidence.append(ev_line(p["m"], f"{int(p['m']['main']):,}" if p["comma_in_evidence"] else None))
        elif kind == "trailing_zero":
            m = new_metric(rng, rng.choice(["percent", "count"]), pool.pop())
            p["m"] = m
            evidence.append(ev_line(m, m["main"] + "0%" if m["vtype"] == "percent" else m["main"] + ".0"))
        elif kind == "pair_split":
            m = new_metric(rng, "ratio", pool.pop())
            p["m"] = m
            evidence += [f"  {m['label']} passed: {m['main']}", f"  {m['label']} total: {m['second']}"]
        elif kind == "substring_trap":
            p["m"] = new_metric(rng, "count", pool.pop(), 100, 9800)
            evidence.append(ev_line(p["m"]))
        elif kind == "rounded":
            p["m"] = new_metric(rng, rng.choice(["percent", "decimal"]), pool.pop(), 101, 949)
            evidence.append(ev_line(p["m"]))
        elif kind == "pair_broken":
            p["m"] = new_metric(rng, "ratio", pool.pop(), 20, 400)
            evidence.append(ev_line(p["m"]))
        elif kind == "coincidence":
            p["m"] = new_metric(rng, "count", pool.pop())
            evidence.append(ev_line(p["m"]))
        elif kind == "single_digit":
            p["m"] = new_metric(rng, "count", pool.pop(), 2, 9)
            evidence.append(ev_line(p["m"]))
        elif kind == "invented":
            p["m"] = new_metric(rng, vt(), pool.pop())
        elif kind == "not_green":
            p["form"] = rng.choice(["yellow", "red", "mixed"])
            p["m"] = new_metric(rng, vt(), pool.pop())
            if p["form"] == "mixed":
                evidence.append(ev_line(p["m"]))
        else:
            m = new_metric(rng, vt(), pool.pop())
            m["slash"] = kind == "exact" and m["vtype"] == "ratio" and rng.random() < 0.25
            p["m"] = m
            evidence.append(ev_line(m))
            if two:
                p["m2"] = new_metric(rng, vt(), pool.pop())
                evidence.append(ev_line(p["m2"]))
        plans.append(p)

    rng.shuffle(evidence)
    text = f"{pid} script output\n" + "\n".join(evidence) + "\n"
    g = Guard(text)

    lines = [f"# Project {pid}: {rng.choice(OBJECTS)}", "",
             f"Synthetic. Seed {SEED}, {seed_rows} rows generated, nothing here is real.", "", "```text",
             evidence[0].strip(), "```", "", "**What it shows:**", ""]
    rows = []
    for p in plans:
        kind, m = p["kind"], p["m"]
        start = len(lines) + 1
        if kind in ("exact", "trailing_zero", "pair_split"):
            lines.append(bullet(rng, m["subject"], show(m)))
        elif kind == "comma":
            plain = m["main"] if p["comma_in_evidence"] else f"{int(m['main']):,}"
            lines.append(bullet(rng, m["subject"], plain))
        elif kind == "trailing_period":
            lines.append(bullet(rng, m["subject"], show(m), period=True))
        elif kind == "inert_digits":
            tail = f" (`step_0{rng.randint(1, 4)}`)" if rng.random() < 0.5 else f" ([log](./logs/run_{rng.randint(10, 99)}.txt))"
            lines.append(bullet(rng, m["subject"], show(m), tail))
        elif kind == "wrapped_ok":
            lines += [bullet(rng, m["subject"], show(m), ", and"), f"  {p['m2']['subject']}: {show(p['m2'])}"]
        elif kind == "wrapped_bad":
            m2 = p["m2"]
            bad = pick(lambda: edit_digit(rng, m2["main"]), lambda c: valid(m2, c) and g.absent(c))
            lines += [bullet(rng, m["subject"], show(m), ", and"), f"  {m2['subject']}: {show(m2, bad)}"]
        elif kind == "not_green":
            x = pick(lambda: str(rng.randint(10, 90)), g.absent)
            if p["form"] == "yellow":
                lines.append(f"- \U0001F7E1 Modeled: {m['subject']} would fall by {x}% if the queue were split (assumption, not measured)")
            elif p["form"] == "red":
                lines.append(f"- \U0001F534 Hypothetical: {x} fewer reviews a week if every {m['subject'].split()[0]} case were routed")
            else:
                lines.append(bullet(rng, m["subject"], show(m), f" \U0001F7E1 assumed {x}% share of volume"))
        elif kind == "small_numeral":
            d = pick(lambda: str(rng.randint(2, 9)), lambda c: c not in g.tokens)
            lines.append(bullet(rng, m["subject"], show(m), f", across {d} tools"))
        elif kind == "typo":
            bad = pick(lambda: edit_digit(rng, m["main"]), lambda c: valid(m, c) and g.absent(c))
            lines.append(bullet(rng, m["subject"], show(m, bad)))
        elif kind == "stale":
            bad = pick(lambda: shift(rng, m["main"]), lambda c: valid(m, c) and c != m["main"] and g.absent(c))
            lines.append(bullet(rng, m["subject"], show(m, bad)))
        elif kind == "invented":
            fresh = pick(lambda: new_metric(rng, vt(), ("unlisted " + m["subject"], "")),
                         lambda c: g.absent(c["main"]) and (c["second"] is None or g.absent(c["second"])))
            lines.append(bullet(rng, fresh["subject"], show(fresh)))
        elif kind == "substring_trap":
            n = m["main"]
            bad = pick(lambda: rng.choice([n[1:], n[:-1]]), lambda c: len(c) >= 2 and c[0] != "0" and g.piece_only(c))
            lines.append(bullet(rng, m["subject"], show(m, bad)))
        elif kind == "rounded":
            n = m["main"]
            bad = pick(lambda: n.split(".")[0] if m["vtype"] == "percent" else n[:-1], lambda c: g.piece_only(c))
            lines.append(bullet(rng, m["subject"], show(m, bad)))
        elif kind == "pair_broken":
            if (m["main"], partner["second"]) in g.pairs or m["main"] not in g.tokens or partner["second"] not in g.tokens:
                raise Retry()
            lines.append(bullet(rng, m["subject"], f"{m['main']} of {partner['second']}"))
        elif kind == "coincidence":
            d = pick(lambda: rng.choice(distractors), lambda c: c != m["main"])
            lines.append(bullet(rng, m["subject"], show(m, d)))
        else:
            w = pick(lambda: str(rng.randint(2, 9)), lambda c: c != m["main"] and c not in g.tokens)
            lines.append(bullet(rng, m["subject"], w))
        rows.append((start, len(lines), kind))
    lines += ["", f"Rerun the scripts after any change. The last full run covered {batches} batches.", ""]
    return {"project_id": pid, "readme": "\n".join(lines), "evidence": text}, rows


EXAMPLE_CLAIMS = """# Example project

Synthetic. Not a real system.

- \U0001F7E2 Cases routed to the right queue: 412 of 480 (`step_02`)
- \U0001F7E2 Median days to close: 3.4
- \U0001F7E2 Rows loaded: 1,240.
- \U0001F7E2 Documents classified without a person: 14 of 480
- \U0001F7E2 Disputes reopened within a week: 58
- \U0001F7E1 Modeled: 20% fewer reviews if the queue is split (assumption)
- \U0001F7E2 Alerts closed on first touch: 37 of 91, and
  checked by 3 reviewers
"""

EXAMPLE_OUTPUT = """cases routed to the right queue: 412 of 480
median days to close: 3.42
rows loaded: 1240
documents classified without a person: 14 of 50
disputes reopened within a week: 158
alerts closed on first touch: 37/91
"""


def main():
    kinds = [k for k, n in KIND_COUNTS for _ in range(n)]
    random.Random(SEED).shuffle(kinds)
    base, extra = divmod(len(kinds), N_PROJECTS)
    projects, truth, at = [], [], 0
    for i in range(N_PROJECTS):
        size = base + (1 if i < extra else 0)
        mine, at = kinds[at:at + size], at + size
        pid = f"P{i + 1:02d}"
        attempt = 0
        while True:
            try:
                project, rows = build_project(pid, mine, attempt)
                break
            except Retry:
                attempt += 1
        projects.append(project)
        truth += [(pid, a, b, k, "ok" if k in SUPPORTED else "flag") for a, b, k in rows]
    with open("projects.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(projects, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    with open("truth.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["project_id", "line_start", "line_end", "kind", "expected"])
        w.writerows(truth)
    with open("example_claims.md", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(EXAMPLE_CLAIMS)
    with open("example_output.txt", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(EXAMPLE_OUTPUT)
    flagged = sum(1 for t in truth if t[4] == "flag")
    print(f"wrote {len(projects)} projects, {len(truth)} bullets ({flagged} unsupported, {len(truth) - flagged} supported)")


if __name__ == "__main__":
    main()
