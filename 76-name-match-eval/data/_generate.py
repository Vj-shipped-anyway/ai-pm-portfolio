"""Generate the synthetic data for project 76: a watchlist of invented parties and 400 customer names.
Each customer is planted either as the same party as a listed entity, spelled differently, or as a
different person.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth label of a customer
comes from the process that planted it, never from a matcher, and this file imports none. Spelling
variants come from the two swap tables below. The matcher in src/ folds the COMMON table and does not
know the RARE table, so some planted matches are hard on purpose. Three kinds of customer are hard on
purpose: translit_heavy (three rare swaps), alias_unlisted (the party is known by a name that is not on
the list) and particle_joined ("Al Tavari" written "Altavari"). Two clear kinds are hard negatives:
near_name (a different surname one letter away from a listed one) and namesake (the same name as a
listed party, a different person).

Run (from data/):  python3 _generate.py
Writes:  watchlist.csv, customers.csv, truth.csv, example_watchlist.csv, example_customers.csv,
         example_truth.csv
"""
from __future__ import annotations

import csv
import random
import re

rng = random.Random(76)

GIVEN = ["hasan", "yusuf", "khalid", "omar", "ahmed", "ivan", "viktor", "tomas", "samir", "wasim", "karim",
         "josef", "pavel", "david", "jonas", "dmitri", "nikolai", "fyodor", "tariq", "bashir", "farid", "malik",
         "anna", "lena", "marta", "nadia", "rania", "leila", "amira", "elena", "irina", "olga", "katya", "sofia"]
WEIGHTS = [1.0 / (i + 3) for i in range(len(GIVEN))]
ONSET = ["k", "kh", "b", "d", "j", "m", "n", "r", "s", "sh", "t", "v", "w", "z", "h", "g", "p", "f", "l", "q"]
SINGLE = ["k", "b", "d", "j", "m", "n", "r", "s", "t", "v", "w", "z", "h", "g", "p", "f", "l"]
VOWEL = ["a", "e", "i", "o", "u", "ou", "ee", "a", "i", "o"]
CODA = ["", "", "n", "r", "l", "m", "s", "d", "k", "ck", "ss"]
SUFFIX = ["", "", "ov", "ev", "ski", "ani", "ouf", "yan", "i"]
COMMON_CORES = ["marov", "hadani", "belkor", "zandri", "tavari", "norvel"]
PARTICLES = ["al", "van", "de"]

COMMON_SWAPS = [("kh", "h"), ("ou", "u"), ("ee", "i"), ("y", "i"), ("w", "v"), ("ph", "f"), ("ck", "k"),
                ("dj", "j"), ("ie", "i"), ("q", "k"), ("oo", "u"), ("ss", "s"), ("ll", "l"), ("tt", "t")]
RARE_SWAPS = [("sh", "ch"), ("z", "s"), ("o", "u"), ("e", "a"), ("th", "t"), ("gh", "g"), ("x", "ks"),
              ("ts", "c"), ("v", "f"), ("b", "p"), ("d", "t"), ("g", "k")]

PLAN = [("format_only", "match", 16), ("order_swap", "match", 24), ("translit", "match", 22),
        ("translit_order", "match", 18), ("dropped_middle", "match", 14), ("initial", "match", 14),
        ("typo", "match", 14), ("particle_joined", "match", 8), ("translit_heavy", "match", 10),
        ("alias_unlisted", "match", 10), ("random", "clear", 100), ("shared_surname", "clear", 56),
        ("shared_given", "clear", 56), ("near_name", "clear", 30), ("namesake", "clear", 8)]
N_ENTITIES = 60
ACCENT = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}


def pick_given():
    return rng.choices(GIVEN, weights=WEIGHTS)[0]


def syllable():
    return rng.choice(ONSET) + rng.choice(VOWEL) + rng.choice(CODA)


def invent_core(taken):
    for _ in range(1000):
        s = syllable() + syllable() + rng.choice(SUFFIX)
        if 5 <= len(s) <= 10 and s not in taken:
            taken.add(s)
            return s
    raise RuntimeError("could not invent a surname")


def title(tokens):
    return " ".join(t.capitalize() for t in tokens)


def render(g, s, style):
    if style == "gf":
        return title(g + s)
    if style == "sf":
        return title(s + g)
    if style == "sfc":
        return title(s) + ", " + title(g)
    return title(g[:1] + s + g[1:])


def swap_once(token, a, b):
    """Replace one occurrence of a by b, or of b by a. None when neither is present."""
    cand = []
    for x, y in ((a, b), (b, a)):
        start = 0
        while True:
            i = token.find(x, start)
            if i < 0:
                break
            new = token[:i] + y + token[i + len(x):]
            if not re.search(r"(.)\1\1", new):
                cand.append(new)
            start = i + 1
    return rng.choice(cand) if cand else None


def apply_rules(tokens, pool, k):
    """Apply up to k different swap rules, each once. Returns (tokens, number applied)."""
    pool = pool[:]
    rng.shuffle(pool)
    tokens = list(tokens)
    done = 0
    for a, b in pool:
        if done == k:
            break
        idx = list(range(len(tokens)))
        rng.shuffle(idx)
        for i in idx:
            new = swap_once(tokens[i], a, b)
            if new is not None:
                tokens[i] = new
                done += 1
                break
    return tokens, done


def typo(tokens):
    for _ in range(100):
        i = rng.randrange(len(tokens))
        t = tokens[i]
        if len(t) < 4:
            continue
        p = rng.randrange(1, len(t))
        op = rng.choice(["del", "ins", "sub", "swap"])
        if op == "del":
            n = t[:p] + t[p + 1:]
        elif op == "ins":
            n = t[:p] + rng.choice("aeioulnrst") + t[p:]
        elif op == "sub":
            n = t[:p] + rng.choice("aeioulnrst") + t[p + 1:]
        elif p + 1 < len(t):
            n = t[:p] + t[p + 1] + t[p] + t[p + 2:]
        else:
            continue
        if n != t:
            out = list(tokens)
            out[i] = n
            return out
    raise RuntimeError("could not plant a typo")


def make_entities(taken):
    ents, seen = [], set()
    while len(ents) < N_ENTITIES:
        given = pick_given()
        middle = pick_given() if rng.random() < 0.4 else ""
        if middle == given:
            middle = ""
        core = rng.choice(COMMON_CORES) if rng.random() < 0.3 else invent_core(taken)
        parts = [rng.choice(PARTICLES), core] if rng.random() < 0.2 else [core]
        key = (given, middle, tuple(parts))
        if key in seen:
            continue
        seen.add(key)
        ents.append({"id": "E%03d" % (len(ents) + 1), "g": [given] + ([middle] if middle else []), "s": parts})
    return ents


def make_aliases(e):
    n = rng.choices([0, 1, 2], [50, 35, 15])[0]
    out, seen = [], {" ".join(e["g"] + e["s"])}
    for _ in range(n):
        for _try in range(30):
            kind = rng.choice(["translit", "no_middle", "comma"])
            if kind == "translit":
                toks, done = apply_rules(e["g"] + e["s"], COMMON_SWAPS + RARE_SWAPS, 1)
                if not done:
                    continue
                text = title(toks)
            elif kind == "no_middle":
                if len(e["g"]) < 2:
                    continue
                text = title(e["g"][:1] + e["s"])
            else:
                text = title(e["s"]) + ", " + title(e["g"])
            c = re.sub(r"[^a-z ]", "", text.lower())
            if c in seen:
                continue
            seen.add(c)
            out.append(text)
            break
    return out


def split(e, tokens):
    return tokens[:len(e["g"])], tokens[len(e["g"]):]


def format_only(e):
    text = render(e["g"], e["s"], "gf")
    style = rng.choice(["upper", "accent", "dotted"])
    if style == "upper":
        return "  ".join(text.upper().split(" "))
    if style == "dotted":
        return text + "."
    spots = [i for i, c in enumerate(text.lower()) if c in ACCENT]
    i = rng.choice(spots)
    return text[:i] + ACCENT[text[i].lower()] + text[i + 1:]


def build_match(kind, ents, taken):
    """One planted match: returns (name as recorded, entity id)."""
    if kind == "alias_unlisted":
        return render([pick_given()], [invent_core(taken)], "gf"), rng.choice(ents)["id"]
    for _ in range(1000):
        e = rng.choice(ents)
        g, s = e["g"], e["s"]
        if kind == "format_only":
            return format_only(e), e["id"]
        if kind == "order_swap":
            style = rng.choice(["sf", "sfc"] + (["rot"] if len(g) > 1 else []))
            return render(g, s, style), e["id"]
        if kind in ("translit", "translit_order"):
            toks, done = apply_rules(g + s, COMMON_SWAPS + RARE_SWAPS, 1)
            if done:
                g2, s2 = split(e, toks)
                return render(g2, s2, "gf" if kind == "translit" else rng.choice(["sf", "sfc"])), e["id"]
        elif kind == "translit_heavy":
            toks, done = apply_rules(g + s, RARE_SWAPS, 3)
            if done == 3:
                g2, s2 = split(e, toks)
                return render(g2, s2, "gf"), e["id"]
        elif kind == "dropped_middle":
            if len(g) > 1:
                return render(g[:1], s, "gf"), e["id"]
        elif kind == "initial":
            g2 = [g[0][0] + "."] + (g[1:] if rng.random() < 0.5 else [])
            return render(g2, s, rng.choice(["gf", "sfc"])), e["id"]
        elif kind == "typo":
            g2, s2 = split(e, typo(g + s))
            return render(g2, s2, "gf"), e["id"]
        elif kind == "particle_joined":
            if len(s) == 2:
                return render(g, ["".join(s)], "gf"), e["id"]
    raise RuntimeError("could not build " + kind)


def build_clear(kind, ents, taken, listed_keys, namesakes):
    """One planted different person: returns the name as recorded."""
    common = [e for e in ents if e["s"][-1] in COMMON_CORES]
    given_count = {}
    for e in ents:
        given_count[e["g"][0]] = given_count.get(e["g"][0], 0) + 1
    frequent = [e for e in ents if given_count[e["g"][0]] > 1]
    for _ in range(1000):
        if kind == "random":
            s = [rng.choice(PARTICLES), invent_core(taken)] if rng.random() < 0.2 else [invent_core(taken)]
            text = render([pick_given()], s, rng.choice(["gf", "gf", "gf", "sf"]))
        elif kind == "shared_surname":
            e = rng.choice(common) if rng.random() < 0.6 else rng.choice(ents)
            g = pick_given()
            if g in e["g"]:
                continue
            text = render([g], e["s"], rng.choice(["gf", "gf", "sf"]))
        elif kind == "shared_given":
            e = rng.choice(frequent) if rng.random() < 0.7 else rng.choice(ents)
            core = e["s"][-1]
            tail = syllable() + rng.choice(SUFFIX)
            new = core[:3] + tail
            if new == core or new in taken or not 5 <= len(new) <= 10:
                continue
            text = render(e["g"][:1], e["s"][:-1] + [new], "gf")
        elif kind == "near_name":
            e = rng.choice(ents)
            core = e["s"][-1]
            new = rng.choice(SINGLE) + core[1:]
            if new == core or new in taken:
                continue
            text = render(e["g"], e["s"][:-1] + [new], "gf")
        else:
            e = namesakes.pop()
            return render(e["g"], e["s"], "gf")
        toks = sorted(re.sub(r"[^a-z]", "", t) for t in text.lower().split())
        if tuple(toks) in listed_keys:
            continue
        return text
    raise RuntimeError("could not build " + kind)


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    taken = set(COMMON_CORES)
    ents = make_entities(taken)
    entries = []
    for e in ents:
        entries.append((e["id"], title(e["g"] + e["s"]), "primary"))
        for alias in make_aliases(e):
            entries.append((e["id"], alias, "alias"))
    write_csv("watchlist.csv", ["entry_id", "entity_id", "listed_name", "name_type"],
              [("L%03d" % (i + 1), ent, name, kind) for i, (ent, name, kind) in enumerate(entries)])
    listed_keys = set()
    for _ent, name, _kind in entries:
        listed_keys.add(tuple(sorted(re.sub(r"[^a-z]", "", t) for t in name.lower().split())))
    namesakes = rng.sample(ents, dict((k, c) for k, _t, c in PLAN)["namesake"])
    customers = []
    for kind, truth, count in PLAN:
        for _ in range(count):
            if truth == "match":
                name, ent = build_match(kind, ents, taken)
            else:
                name, ent = build_clear(kind, ents, taken, listed_keys, namesakes), ""
            customers.append((name, truth, ent, kind))
    rng.shuffle(customers)
    write_csv("customers.csv", ["customer_id", "name"], [("C%04d" % (i + 1), c[0]) for i, c in enumerate(customers)])
    write_csv("truth.csv", ["customer_id", "truth", "entity_id", "planted_as"],
              [("C%04d" % (i + 1), c[1], c[2], c[3]) for i, c in enumerate(customers)])

    # The worked example behind `python3 name_match_eval.py --demo`: written by hand, not drawn from the generator.
    write_csv("example_watchlist.csv", ["entry_id", "entity_id", "listed_name", "name_type"], [
        ("X01", "EX1", "Yusuf Belkor", "primary"), ("X02", "EX2", "Nadia Hadani", "primary"),
        ("X03", "EX3", "Khalid Samir Zandri", "primary"), ("X04", "EX4", "Viktor Norvel", "primary"),
        ("X05", "EX5", "Omar Al Tavari", "primary"), ("X06", "EX5", "Omar Tavari", "alias")])
    example = [
        ("Belkor, Yusuf", "match", "EX1", "order_swap"), ("Yousef Belkor", "match", "EX1", "translit"),
        ("N. Hadani", "match", "EX2", "initial"), ("Khalid Zandri", "match", "EX3", "dropped_middle"),
        ("Boris Tolman", "match", "EX4", "alias_unlisted"), ("Wasim Norvel", "clear", "", "shared_surname"),
        ("Yusuf Belkar", "clear", "", "near_name"), ("Samir Wahabi", "clear", "", "random"),
        ("Viktor Dalmen", "clear", "", "random"), ("Lena Hadani", "clear", "", "shared_surname"),
        ("Marta Kasimov", "clear", "", "random"), ("Ivan Zandrov", "clear", "", "random")]
    write_csv("example_customers.csv", ["customer_id", "name"], [("S%02d" % (i + 1), c[0]) for i, c in enumerate(example)])
    write_csv("example_truth.csv", ["customer_id", "truth", "entity_id", "planted_as"],
              [("S%02d" % (i + 1), c[1], c[2], c[3]) for i, c in enumerate(example)])


if __name__ == "__main__":
    main()
