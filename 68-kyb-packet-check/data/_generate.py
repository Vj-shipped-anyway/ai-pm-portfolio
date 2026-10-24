"""Generate the synthetic data for project 68: 75 business-onboarding packets, the text of each
filing, what a model extracted from each filing, and the truth that was planted.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth of each packet
comes from how it was built here: the owners are chosen first, the filing text is rendered from
them, and the misreads are applied to the extraction afterwards. No checker rule is used to decide
what counts as a defect. Three kinds are hard on purpose:
  - clean packets that a careless rule would flag (thirds that add to 99.99, names written in a
    different form, an entity holding 20 percent with no look-through shown, a 24 percent
    individual behind an entity);
  - a misread that keeps every number on the schedule adding to 100 (swapped percents);
  - a filing note that changes who the owner is, which no rule in src/ reads (nominee_note).

Run (from data/):  python3 _generate.py
Writes:  packets.csv, extractions.csv, truth.csv, example_source.txt, example_extracted.json
"""
from __future__ import annotations

import csv
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))

FIRST = ["Dana", "Tomas", "Priya", "Marcus", "Elena", "Kofi", "Lucia", "Hiro", "Amara", "Declan", "Noor", "Ivan",
         "Sofia", "Mateo", "Leila", "Owen", "Rosa", "Anil", "Greta", "Jonas", "Mei", "Tariq", "Bianca", "Felix",
         "Nadia", "Ravi", "Clara", "Dmitri", "Imani", "Oscar"]
LAST = ["Whitfield", "Reyes", "Nair", "Okafor", "Lindqvist", "Moreau", "Tanaka", "Haddad", "Brennan", "Castellanos",
        "Volkov", "Adeyemi", "Marsh", "Petrov", "Quigley", "Santoro", "Ibarra", "Kessler", "Mbeki", "Novak", "Osei",
        "Prescott", "Ramanathan", "Sorensen", "Takahashi", "Underhill", "Vargas", "Weller", "Yilmaz", "Zielinski"]
MIDDLE = list("ABCDEFGHJKLMNPRST")
PLACE = ["Harbor Lane", "Cedar Ridge", "Northgate", "Millbrook", "Larkspur", "Quarry Hill", "Ironwood", "Bayfield",
         "Stonebridge", "Redfern", "Alder Point", "Foxglove", "Tidewater", "Kestrel", "Pinecrest"]
NOUN = ["Supply", "Logistics", "Dental Group", "Printing", "Bakery", "Landscaping", "Freight", "Tool and Die",
        "Electric", "Foods", "Cleaning Services", "Machine Works"]
SUFFIX = ["LLC", "Inc.", "Corp.", "LLC"]
STATE = ["Ohio", "Delaware", "Texas", "Colorado", "Georgia", "Oregon", "Nevada", "Michigan"]
STREET = ["Oak", "Maple", "Cedar", "Birch", "Willow", "Elm", "Lakeview", "Highland", "Sycamore", "Juniper", "Ridge", "Meadow"]
STREET_KIND = ["Street", "Avenue", "Road", "Lane", "Drive"]
CITY = [("Fairview", "OH"), ("Lakeside", "TX"), ("Riverton", "CO"), ("Brookfield", "GA"), ("Oakdale", "OR"),
        ("Westport", "NV"), ("Clearwater", "MI"), ("Ashford", "DE")]
TITLE = ["Managing Member", "President", "Chief Executive Officer", "Manager", "Chief Financial Officer"]

# individuals only, percent of the customer; the first twelve are used in order by clean_direct
DIRECT_ORDER = [(55, 25, 20), (51, 25, 24), (25, 25, 25, 25), (50, 25, 25), (60, 40), (50, 50), (45, 30, 15, 10),
                (80, 10, 10), (75, 25), (30, 30, 20, 20), (65, 20, 15), (70, 20, 10)]
DIRECT_ANY = DIRECT_ORDER + [(40, 35, 25), (35, 25, 20, 20), (45, 35, 20), (55, 30, 15)]
CROSS = [(55, 25, 20), (45, 30, 15, 10), (70, 20, 10), (65, 20, 15)]      # a holder at 25 or more and one below
SAME_SIDE = [(60, 40), (70, 30)]                                           # two holders at 25 or more, different
# one entity holder with look-through: direct individuals, entity percent, look-through percents
SHAPES = {
    "L1": dict(direct=[30], entity=70, lt=[50, 50]),
    "L2": dict(direct=[15, 45], entity=40, lt=[50, 50], agg=True),         # first direct holder is also in the entity
    "L3": dict(direct=[40], entity=60, lt=[40, 30, 30]),                    # 24, 18, 18 after look-through
    "L4": dict(direct=[20, 30], entity=50, lt=[60, 40]),
    "L5": dict(direct=[25], entity=75, lt=[100]),
    "L6": dict(direct=[10, 10], entity=80, lt=[50, 50]),
}

QUOTA = [("clean_direct", 12), ("clean_lookthrough", 8), ("clean_rounding", 4), ("clean_name_variant", 5),
         ("clean_entity_minor", 3),
         ("pct_decimal_slip", 5), ("owner_dropped", 5), ("pct_swapped", 6), ("entity_no_lookthrough", 4),
         ("control_person_missing", 4), ("field_missing", 5), ("name_misread", 4), ("dob_misread", 4),
         ("cert_incomplete", 3), ("nominee_note", 3)]


def fmt_pct(x) -> str:
    return ("%.2f" % x).rstrip("0").rstrip(".")


def display(p) -> str:
    return f"{p['first']} {p['mid']}. {p['last']}" if p["mid"] else f"{p['first']} {p['last']}"


def inverted(p) -> str:
    return f"{p['last']}, {p['first']} {p['mid']}." if p["mid"] else f"{p['last']}, {p['first']}"


def plain(p) -> str:
    return f"{p['first']} {p['last']}"


# ---------------------------------------------------------------- planted truth
def owners(holders, lookthrough) -> dict:
    """Effective percent of the customer per individual, by exact name."""
    via = {}
    for h in holders:
        if h["kind"] == "entity":
            via[h["name"]] = via.get(h["name"], 0) + h["pct"]
    eff = {}
    for h in holders:
        if h["kind"] == "individual":
            eff[h["name"]] = eff.get(h["name"], 0) + h["pct"]
    for r in lookthrough:
        eff[r["name"]] = eff.get(r["name"], 0) + via[r["entity"]] * r["pct"] / 100
    return {n: round(v, 6) for n, v in eff.items()}


def beneficial(eff) -> list:
    return sorted(n for n, v in eff.items() if v >= 25 - 1e-9)


def new_packet(rng, pid, initials) -> dict:
    places = rng.sample(PLACE, 2)
    suffix = rng.choice(SUFFIX)
    pool = []
    for f, l in zip(rng.sample(FIRST, 9), rng.sample(LAST, 9)):
        mid = rng.choice(MIDDLE) if (initials or rng.random() < 0.5) else ""
        pool.append({"first": f, "mid": mid, "last": l})
    return {"packet_id": pid, "pool": pool, "parts": {},
            "entity": {"name": f"{places[0]} {rng.choice(NOUN)} {suffix}", "state": rng.choice(STATE),
                       "type": "Limited liability company" if suffix == "LLC" else "Corporation",
                       "units": "membership interests" if suffix == "LLC" else "shares"},
            "date": f"2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}", "holding": f"{places[1]} Holdings Ltd",
            "holders": [], "lookthrough": [], "people": [], "control": None, "note": "", "bo_override": None}


def take(t) -> str:
    p = t["pool"].pop(0)
    t["parts"][display(p)] = p
    return display(p)


def fill_direct(t, partition) -> None:
    t["holders"] = [{"name": take(t), "kind": "individual", "pct": p} for p in partition]


def fill_shape(t, shape) -> None:
    holders = [{"name": take(t), "kind": "individual", "pct": p} for p in shape["direct"]]
    lt = []
    for k, p in enumerate(shape["lt"]):
        who = holders[0]["name"] if (shape.get("agg") and k == 0) else take(t)
        lt.append({"entity": t["holding"], "name": who, "pct": p})
    t["holders"] = holders + [{"name": t["holding"], "kind": "entity", "pct": shape["entity"]}]
    t["lookthrough"] = lt


def details(rng) -> dict:
    n = rng.randint(1, 999)
    city, st = rng.choice(CITY)
    return {"address": f"{n} {rng.choice(STREET)} {rng.choice(STREET_KIND)}, {city} {st} {rng.randint(10000, 99999)}",
            "dob": f"{rng.randint(1955, 1992)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "id_last4": f"{rng.randrange(10000):04d}"}


def finish(t, rng, control=None, everyone=False) -> None:
    """Pick the control person, then give each beneficial owner and the control person a details line."""
    eff = owners(t["holders"], t["lookthrough"])
    bos = sorted(beneficial(eff), key=lambda n: (-eff[n], n))
    if control is None:
        direct = [h["name"] for h in sorted(t["holders"], key=lambda h: -h["pct"]) if h["kind"] == "individual" and h["name"] in bos]
        control = direct[0] if direct and rng.random() < 0.5 else take(t)
    t["control"] = {"name": control, "title": rng.choice(TITLE)}
    names = [h["name"] for h in t["holders"] if h["kind"] == "individual"] if everyone else list(bos)
    if control not in names:
        names.append(control)
    t["people"] = [dict(name=n, **details(rng)) for n in names]


# ---------------------------------------------------------------- rendering
def holder_line(h, t, style) -> str:
    units = t["entity"]["units"]
    if style == 0:
        return f"{h['name']} ({h['kind']}) holds {fmt_pct(h['pct'])}% of the {units}."
    if style == 1:
        name = inverted(t["parts"][h["name"]]) if h["kind"] == "individual" else h["name"]
        return f"{fmt_pct(h['pct'])}%  {name} [{h['kind']}]"
    return f"Holder: {h['name']} | {h['kind']} | {fmt_pct(h['pct'])}%"


def person_line(p, t, style) -> str:
    if style == 0:
        return f"Person: {p['name']} | DOB {p['dob']} | {p['address']} | ID ending {p['id_last4']}"
    return f"{inverted(t['parts'][p['name']])} - born {p['dob']} - residing at {p['address']} - ID last four {p['id_last4']}"


def render_source(t, hstyle, pstyle) -> str:
    e, c = t["entity"], t["control"]
    out = [e["name"], f"Entity type: {e['type']}, formed in {e['state']}. Application dated {t['date']}.", "",
           f"Ownership of the customer ({e['units']}):"]
    out += [holder_line(h, t, hstyle) for h in t["holders"]]
    out += [f"Look-through: {r['name']} holds {fmt_pct(r['pct'])}% of {r['entity']}." for r in t["lookthrough"]]
    out += ["", "Individuals named in this packet:"] + [person_line(p, t, pstyle) for p in t["people"]]
    out += ["", f"Control person: {c['name']}, {c['title']}.",
            f"Certification: I certify that the information above is accurate. Signed by {c['name']}, {c['title']}, on {t['date']}."]
    if t["note"]:
        out.append(t["note"])
    return "\n".join(out) + "\n"


def faithful(t) -> dict:
    return {"packet_id": t["packet_id"], "legal_name": t["entity"]["name"],
            "holders": [dict(h) for h in t["holders"]], "lookthrough": [dict(r) for r in t["lookthrough"]],
            "people": [dict(p) for p in t["people"]],
            "control_person": dict(t["control"]),
            "certification": {"signed_by": t["control"]["name"], "date": t["date"]}}


# ---------------------------------------------------------------- planted misreads (applied to the extraction)
def respell(word) -> str:
    """Change one letter the way a bad read of a scan would."""
    for a, b in (("o", "a"), ("a", "o"), ("e", "c"), ("i", "l"), ("u", "v")):
        k = word.rfind(a)
        if k > 0:
            return word[:k] + b + word[k + 1:]
    return word + "e"


def rename_all(ex, old, new) -> None:
    for h in ex["holders"]:
        h["name"] = h["name"].replace(old, new)
    for r in ex["lookthrough"]:
        r["name"] = r["name"].replace(old, new)
        r["entity"] = r["entity"].replace(old, new)
    for p in ex["people"]:
        p["name"] = p["name"].replace(old, new)
    if ex["control_person"]:
        ex["control_person"]["name"] = ex["control_person"]["name"].replace(old, new)
    ex["certification"]["signed_by"] = ex["certification"]["signed_by"].replace(old, new)


def vary_names(ex, t, k) -> None:
    """Write individual names in another form. Same people, so a correct check must not flag it."""
    def form(name, how):
        p = t["parts"].get(name)
        return name if p is None else (plain(p) if how == "plain" else inverted(p))
    for rows in (ex["holders"], ex["lookthrough"], ex["people"]):
        for r in rows:
            if k == 0:
                r["name"] = form(r["name"], "plain")
            elif k == 1:
                r["name"] = form(r["name"], "inverted")
            elif k in (2, 4) and rows is not ex["people"]:
                r["name"] = form(r["name"], "plain")
            elif k == 3 and rows is ex["people"]:
                r["name"] = form(r["name"], "inverted")
    if k in (1, 4):
        ex["control_person"]["name"] = form(ex["control_person"]["name"], "inverted")
        ex["certification"]["signed_by"] = form(ex["certification"]["signed_by"], "inverted")
    if k == 0:
        ex["control_person"]["name"] = form(ex["control_person"]["name"], "plain")
        ex["certification"]["signed_by"] = form(ex["certification"]["signed_by"], "plain")


def plant(kind, i, t, ex) -> str:
    """Apply one misread to the extraction. Returns a one-line description for truth.csv."""
    holders, lt = ex["holders"], ex["lookthrough"]
    ind = [h for h in holders if h["kind"] == "individual"]
    if kind == "pct_decimal_slip":
        row = max(lt, key=lambda r: r["pct"]) if i % 2 else max(ind, key=lambda h: h["pct"])
        old = row["pct"]
        row["pct"] = round(old / 10, 2)
        return f"{row['name']} {old} read as {row['pct']}"
    if kind == "owner_dropped":
        gone = ind[(i // 2) % len(ind)] if i % 2 else ind[i % len(ind)]
        ex["holders"] = [h for h in holders if h is not gone]
        ex["people"] = [p for p in ex["people"] if p["name"] != gone["name"]]
        return f"{gone['name']} ({gone['pct']}) left out"
    if kind == "pct_swapped":
        if i < 4:
            a = min((h for h in ind if h["pct"] >= 25), key=lambda h: h["pct"])
            b = max((h for h in ind if h["pct"] < 25), key=lambda h: h["pct"])
        else:
            a, b = sorted((h for h in ind if h["pct"] >= 25), key=lambda h: h["pct"])[:2]
        a["pct"], b["pct"] = b["pct"], a["pct"]
        return f"percents of {a['name']} and {b['name']} swapped"
    if kind == "entity_no_lookthrough":
        shown = {r["name"] for r in lt}
        ex["lookthrough"] = []
        ex["people"] = [p for p in ex["people"] if p["name"] not in shown or p["name"] in {h["name"] for h in holders}]
        return "entity listed as the owner, individuals behind it not read"
    if kind == "control_person_missing":
        ex["control_person"] = None
        return "control person not read"
    if kind == "field_missing":
        p = ex["people"][i % len(ex["people"])]
        f = ("address", "dob", "id_last4")[i % 3]
        if i % 2:
            del p[f]
        else:
            p[f] = ""
        return f"{f} of {p['name']} not read"
    if kind == "name_misread":
        if i == 2:
            word = ex["legal_name"].split()[0]
            ex["legal_name"] = ex["legal_name"].replace(word, respell(word), 1)
            return f"legal name misread ({word})"
        target = ex["people"][i % len(ex["people"]) if i < 2 else -1]["name"]
        word = target.split()[-1].rstrip(",") if "," not in target else target.split(",")[0]
        rename_all(ex, word, respell(word))
        return f"surname {word} misread"
    if kind == "dob_misread":
        p = ex["people"][i % len(ex["people"])]
        y, m, d = p["dob"].split("-")
        p["dob"] = f"{y}-{d}-{m}"
        return f"month and day of {p['name']} swapped"
    if kind == "cert_incomplete":
        c = ex["certification"]
        if i % 3 == 0:
            c["signed_by"] = ""
        elif i % 3 == 1:
            del c["date"]
        else:
            ex["certification"] = None
        return "signature or date not read"
    return ""


# ---------------------------------------------------------------- one packet per scenario
def build(kind, i, rng, pid):
    t = new_packet(rng, pid, initials=(kind == "clean_name_variant"))
    lookthrough_base = kind == "entity_no_lookthrough" or (i % 2 == 1 and kind in (
        "pct_decimal_slip", "owner_dropped", "control_person_missing", "field_missing", "name_misread", "dob_misread", "cert_incomplete"))
    if kind == "clean_direct":
        fill_direct(t, DIRECT_ORDER[i])
    elif kind == "clean_lookthrough":
        fill_shape(t, SHAPES[("L1", "L2", "L3", "L4", "L5", "L6")[i % 6]])
    elif kind == "clean_rounding":
        fill_direct(t, [(33.33, 33.33, 33.33), (33.33, 33.33, 33.33), (16.67,) * 6, (16.67,) * 6][i])
    elif kind == "clean_name_variant":
        fill_direct(t, DIRECT_ORDER[i % 5])
    elif kind == "clean_entity_minor":
        fill_direct(t, [(45, 35), (50, 30), (55, 25)][i])
        t["holders"].append({"name": t["holding"], "kind": "entity", "pct": 20})
    elif kind == "pct_swapped":
        fill_direct(t, CROSS[i] if i < 4 else SAME_SIDE[i - 4])
    elif kind == "entity_no_lookthrough":
        fill_shape(t, SHAPES[("L1", "L4", "L5", "L6")[i]])
    elif lookthrough_base:
        fill_shape(t, SHAPES[("L1", "L2", "L4", "L6")[(i // 2) % 4]])
    else:
        fill_direct(t, rng.choice(DIRECT_ANY))
    finish(t, rng)
    if kind == "dob_misread":
        # the target person needs a day of 12 or less that differs from the month, so the swap stays a valid date
        k = i % len(t["people"])
        y, m, _ = t["people"][k]["dob"].split("-")
        t["people"][k]["dob"] = f"{y}-{m}-{(int(m) % 12) + 1:02d}"
    if kind == "nominee_note":
        holder = max((h for h in t["holders"] if h["kind"] == "individual"), key=lambda h: h["pct"])
        principal = take(t)
        t["note"] = f"Note: {holder['name']} holds these interests as nominee for {principal}, who is not listed above."
        t["bo_override"] = {holder["name"]: principal}
        detail = f"{holder['name']} holds {holder['pct']} percent as nominee for {principal}"
    hstyle, pstyle = rng.randrange(3), rng.randrange(2)
    source = render_source(t, hstyle, pstyle)
    ex = faithful(t)
    if kind == "clean_name_variant":
        vary_names(ex, t, i)
        detail = f"names written in form {i}"
    elif kind != "nominee_note":
        detail = plant(kind, i, t, ex)
    eff = owners(t["holders"], t["lookthrough"])
    bos = [t["bo_override"].get(n, n) if t["bo_override"] else n for n in beneficial(eff)]
    return t, source, ex, sorted(bos), detail


def example() -> tuple:
    """A fixed packet for `--demo`: the percents of two holders swapped, every other value read correctly."""
    rng = random.Random(6801)
    t = new_packet(rng, "KYB-EX01", False)
    t["entity"].update(name="Harbor Lane Supply LLC", state="Ohio", type="Limited liability company", units="membership interests")
    t["date"] = "2026-03-02"
    fill_direct(t, (50, 30, 20))
    finish(t, rng, control=t["holders"][0]["name"], everyone=True)
    source = render_source(t, 0, 0)
    ex = faithful(t)
    ex["holders"][1]["pct"], ex["holders"][2]["pct"] = 20, 30
    return source, ex


def write_csv(name, header, rows) -> None:
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    rng = random.Random(68)
    plan = [(k, i) for k, n in QUOTA for i in range(n)]
    rng.shuffle(plan)
    packets, extractions, truth = [], [], []
    for n, (kind, i) in enumerate(plan, start=1):
        pid = f"KYB-{n:03d}"
        t, source, ex, bos, detail = build(kind, i, rng, pid)
        packets.append([pid, source])
        extractions.append([pid, json.dumps(ex, sort_keys=True)])
        truth.append([pid, t["entity"]["name"], kind, 0 if kind.startswith("clean_") else 1, "; ".join(bos),
                      t["control"]["name"], detail])
    packets.sort()
    extractions.sort()
    truth.sort()
    write_csv("packets.csv", ["packet_id", "source_text"], packets)
    write_csv("extractions.csv", ["packet_id", "extraction_json"], extractions)
    write_csv("truth.csv", ["packet_id", "entity", "scenario", "defect", "true_beneficial_owners", "true_control_person",
                            "planted_detail"], truth)
    source, ex = example()
    with open(os.path.join(HERE, "example_source.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(source)
    with open(os.path.join(HERE, "example_extracted.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(ex, fh, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main()
