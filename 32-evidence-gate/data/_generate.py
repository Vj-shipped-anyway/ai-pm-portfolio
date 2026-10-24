"""Generate the synthetic data for project 32: 107 pull-request descriptions that each carry an AI change
record, a registry of use cases, the tier-to-evidence table and the file listing of a made-up repository.

Everything is seeded, so the files are byte-for-byte reproducible. The truth label of each pull request
comes from the planted state of its evidence (which item is really missing, stale, unusable or fine, at
the use case's TRUE tier), computed here from structured specs before any text is rendered. The gate in
src/ never sees this state; it parses the rendered text. Hard cases are planted on purpose:

  hard negatives (the gate should not raise an alarm): CRLF line endings, [X], bold labels, lower-case ids,
    dates without a leading zero, evidence dated exactly on its last valid day, an external link, a use case
    not yet in the registry that declares its true tier, a template comment that holds an example line
  hard positives (the gate should stop them): an evidence line only inside a comment or a code fence, a
    date in the future, a date nobody can read, a reference to a file that is not in the repository, a
    declared tier below the registry's
  a false alarm the gate raises: the evidence written as a markdown table instead of the template's lines
  known misses (no rule here can see them): a reference to a real file that holds another use case's
    evidence, a registry that holds a use case one tier too low, and an unregistered use case that
    declares a tier below its true one

Run (from data/):  python3 _generate.py
Writes: tier_evidence.csv, registry.csv, use_cases.csv, pr_cases.csv, pr_truth.csv, repo_files.txt,
        example_pr_body.md, as_of.txt
"""
from __future__ import annotations

import csv
import datetime
import random

SEED = 32
AS_OF = datetime.date(2026, 10, 16)

# id, item, first tier, max age in days, file slug. The ids and names follow the checklist in project 11;
# max_age_days is an assumption of this project (the idea of a freshness limit comes from project 24).
ITEMS = [
    ("E01", "Use-case card with named line-1 owner", 1, 365, "use-case-card"),
    ("E02", "Data-source attestation (dataset names and classes)", 1, 180, "data-source-attestation"),
    ("E03", "Evaluation plan and results summary", 2, 90, "evaluation-results"),
    ("E04", "Privacy and data-handling review", 2, 365, "privacy-review"),
    ("E05", "Independent validation with effective challenge", 3, 180, "independent-validation"),
    ("E06", "Human review design for the tier", 3, 180, "human-review-design"),
    ("E07", "Decision logging and lineage plan", 3, 180, "decision-logging-plan"),
    ("E08", "Vendor and third-party due diligence", 3, 365, "vendor-due-diligence"),
    ("E09", "Regulatory-scope legal review", 4, 365, "legal-review"),
    ("E10", "Fallback and exit plan", 4, 180, "fallback-exit-plan"),
    ("E11", "CRO sign-off", 4, 90, "cro-signoff"),
]
OWNER_UNITS = ["Retail Banking", "Cards", "Payments", "Lending Operations", "Fraud Operations",
               "Customer Service", "Treasury Operations", "Compliance Operations"]
SENTENCES = [
    "Adds a retry step to the dispute summary prompt.",
    "Moves the triage model to the new gateway route.",
    "Raises the retrieval cut-off from 5 to 8 passages.",
    "Adds a reviewer queue for low-confidence answers.",
    "Replaces the keyword filter with the shared classifier.",
    "Logs the prompt version with every decision record.",
    "Narrows the tool list the assistant can call.",
    "Updates the evaluation set with this quarter's cases.",
]
NO_RECORD_BODIES = ["", "Small fix to the prompt wording. No other changes.", "## AI change record\n\n(to be completed)"]
BASE_FILES = ["README.md", ".github/pull_request_template.md", "docs/model-risk-policy.md", "src/app.py",
              "src/prompts/dispute_summary.txt", "src/prompts/triage.txt", "tests/test_prompts.py"]
COMMENT = ["<!-- One line per evidence item, for example:",
           "- [x] E01 Use-case card | ref: evidence/UC-000/E01-use-case-card.md | date: 2026-01-31",
           "Delete this comment before you submit. -->"]

# kind, planted truth label, count
QUOTA = [
    ("complete", "fine", 22), ("complete_formatted", "fine", 8), ("at_limit", "fine", 2),
    ("external_link", "fine", 4), ("unregistered_honest", "fine", 3), ("table_format", "fine", 3),
    ("label_mismatch", "needs_review", 6),
    ("missing_item", "should_block", 7), ("unchecked_box", "should_block", 5), ("no_reference", "should_block", 5),
    ("missing_ref_file", "should_block", 5), ("stale_evidence", "should_block", 6), ("future_date", "should_block", 3),
    ("bad_date", "should_block", 3), ("tier_understated", "should_block", 8), ("comment_only", "should_block", 4),
    ("no_record", "should_block", 3), ("wrong_content", "should_block", 4), ("stale_registry", "should_block", 3),
    ("unregistered_understated", "should_block", 3),
]


def required(tier):
    return [i for i in ITEMS if i[2] <= tier]


def make_world(rng):
    """40 use cases: 30 registered correctly, 3 registered one tier too low, 7 not yet registered."""
    tiers = [1] * 8 + [2] * 9 + [3] * 8 + [4] * 5
    rng.shuffle(tiers)
    world = [{"id": f"UC-{n:03d}", "true": t, "reg": t, "status": "current"} for n, t in enumerate(tiers, 1)]
    for n, (true, reg) in enumerate([(3, 2), (3, 2), (4, 3)], 31):
        world.append({"id": f"UC-{n:03d}", "true": true, "reg": reg, "status": "stale_understated"})
    for n, true in enumerate([1, 2, 3, 3, 2, 4, 3], 34):
        world.append({"id": f"UC-{n:03d}", "true": true, "reg": None, "status": "unregistered"})
    for u in world:
        u["unit"] = rng.choice(OWNER_UNITS)
    return world


def good(rng, files, uc_id, item, age=None):
    """An evidence line whose file exists, is ticked and is in date."""
    eid, name, _tier, max_age, slug = item
    path = f"evidence/{uc_id}/{eid}-{slug}.md"
    files.add(path)
    age = rng.randint(3, max_age - 3) if age is None else age
    return {"id": eid, "name": name, "ticked": True, "ref": path, "valid": True,
            "date": (AS_OF - datetime.timedelta(days=age)).isoformat()}


def render(spec):
    formatted = spec["style"] == "formatted"
    nl = "\r\n" if formatted else "\n"
    if spec["body"] is not None:
        return spec["body"]

    def line_for(it):
        box = ("X" if formatted else "x") if it["ticked"] else " "
        parts = [f"{'*' if formatted else '-'} [{box}] {it['id'].lower() if formatted else it['id']} {it['name']}"]
        if it["ref"] is not None:
            parts.append(f"ref: {it['ref']}")
        if it["date"] is not None:
            d = it["date"]
            if formatted and d[:4].isdigit() and d.count("-") == 2:
                y, m, dd = d.split("-")
                d = f"{y}-{int(m)}-{int(dd)}"
            parts.append(f"date: {d}")
        return ("  |  " if formatted else " | ").join(parts)

    lines = ["## AI change record", ""]
    if spec["comment"]:
        lines += COMMENT + [""]
    lines += [("**Use case:** " if formatted else "Use case: ") + spec["uc"]["id"],
              ("**Declared tier:** " if formatted else "Declared tier: ") + str(spec["declared"]), "", "### Evidence"]
    if spec["table"]:
        lines += ["| Item | Ref | Date |", "|---|---|---|"]
        lines += [f"| {it['id']} | {it['ref']} | {it['date']} |" for it in spec["items"]]
    else:
        lines += [line_for(it) for it in spec["items"]]
    for it, mode in spec["hidden"]:
        if mode == "comment":
            lines += ["<!--", line_for(it), "-->"]
        else:
            lines += ["Format I used for this one:", "```", line_for(it), "```"]
    lines += ["", "### What changed", spec["sentence"]]
    return nl.join(lines)


def build(kind, n, rng, files, world):
    """One pull-request spec of this kind; n counts the specs of the kind already built."""
    cur = [u for u in world if u["status"] == "current"]
    unreg = [u for u in world if u["status"] == "unregistered"]
    stale = [u for u in world if u["status"] == "stale_understated"]

    def pick(pool, lo=1, hi=4):
        return rng.choice([u for u in pool if lo <= u["true"] <= hi])

    spec = {"kind": kind, "style": "formatted" if kind == "complete_formatted" else "plain", "body": None,
            "comment": rng.random() < 0.5, "sentence": rng.choice(SENTENCES), "hidden": [], "declared": None,
            "table": kind == "table_format"}
    if kind == "no_record":
        spec.update(uc=pick(cur), items=[], body=rng.choice(NO_RECORD_BODIES))
        return spec
    if kind in ("complete", "complete_formatted", "at_limit", "external_link", "table_format"):
        uc = pick(cur)
    elif kind == "label_mismatch":
        uc = pick(cur, 2, 3)
    elif kind in ("missing_item", "tier_understated", "comment_only"):
        uc = pick(cur, 2, 4)
    elif kind in ("unchecked_box", "no_reference", "missing_ref_file", "stale_evidence", "future_date", "bad_date", "wrong_content"):
        uc = pick(cur)
    elif kind == "stale_registry":
        uc = stale[n % len(stale)]
    elif kind == "unregistered_honest":
        uc = pick(unreg)
    else:  # unregistered_understated
        uc = pick(unreg, 2, 4)
    spec["uc"] = uc
    tier = uc["true"]
    declared = tier
    shown = required(tier)
    if kind == "tier_understated":
        declared = tier - rng.randint(1, min(tier - 1, 2))
        shown = required(declared)
    elif kind == "unregistered_understated":
        declared = tier - 1
        shown = required(declared)
    elif kind == "stale_registry":
        declared = uc["reg"]
        shown = required(declared)
    elif kind == "label_mismatch":
        declared = tier - 1 if n % 2 == 0 else tier + 1
        shown = required(tier)
    spec["declared"] = declared
    items = [good(rng, files, uc["id"], it) for it in shown]
    spec["items"] = items
    pos = rng.randrange(len(items))
    target = items[pos]
    if kind == "at_limit":
        item = next(i for i in ITEMS if i[0] == target["id"])
        target["date"] = (AS_OF - datetime.timedelta(days=item[3])).isoformat()
    elif kind == "external_link":
        target["ref"] = f"https://wiki.example.invalid/ai/{uc['id']}/{target['id']}"
    elif kind == "missing_item":
        for it in rng.sample(items, 1 if len(items) < 4 else 2):
            it["valid"] = False
        spec["items"] = [it for it in items if it["valid"]]
    elif kind == "unchecked_box":
        for it in rng.sample(items, 1 if len(items) < 4 else 2):
            it.update(ticked=False, valid=False)
    elif kind == "no_reference":
        for it in rng.sample(items, 1 if len(items) < 4 else 2):
            it.update(ref=rng.choice([None, ""]), valid=False)
    elif kind == "missing_ref_file":
        target.update(ref=target["ref"].replace(".md", "-v2.md"), valid=False)
    elif kind == "stale_evidence":
        item = next(i for i in ITEMS if i[0] == target["id"])
        extra = 1 if n < 2 else rng.randint(2, 150)
        target.update(date=(AS_OF - datetime.timedelta(days=item[3] + extra)).isoformat(), valid=False)
    elif kind == "future_date":
        target.update(date=(AS_OF + datetime.timedelta(days=rng.randint(200, 400))).isoformat(), valid=False)
    elif kind == "bad_date":
        target.update(date=["TBD", "03/09/2026", None][n], valid=False)
    elif kind == "comment_only":
        mode = "comment" if n < 2 else "fence"
        target["valid"] = False
        spec["items"] = [it for it in items if it is not target]
        spec["hidden"] = [(target, mode)]
    elif kind == "wrong_content":
        other = rng.choice([u for u in world if u["id"] != uc["id"]])
        item = next(i for i in ITEMS if i[0] == target["id"])
        target.update(ref=f"evidence/{other['id']}/{item[0]}-{item[4]}.md", valid=False)
        files.add(target["ref"])
    return spec



def truth_of(spec):
    """(truth class, bad items) from the planted state, at the use case's true tier."""
    valid = {it["id"] for it in spec["items"] if it["valid"]}
    bad = [i[0] for i in required(spec["uc"]["true"]) if i[0] not in valid]
    if bad:
        return "should_block", bad
    if spec["declared"] != spec["uc"]["true"]:
        return "needs_review", []
    return "fine", []


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    rng = random.Random(SEED)
    world = make_world(rng)
    files = set(BASE_FILES)
    specs = []
    for kind, _label, count in QUOTA:
        for n in range(count):
            specs.append(build(kind, n, rng, files, world))
    order = list(range(len(specs)))
    rng.shuffle(order)

    # the worked example behind --demo: a tier-3 use case declared at tier 2, with one stale item
    ex_rng = random.Random(SEED + 1)
    ex_uc = next(u for u in world if u["status"] == "current" and u["true"] == 3)
    ex_items = [good(ex_rng, files, ex_uc["id"], it, age=(130 if it[0] == "E03" else None)) for it in required(2)]
    example = render({"style": "plain", "body": None, "comment": False, "sentence": SENTENCES[0], "hidden": [], "table": False,
                      "uc": ex_uc, "declared": 2, "items": ex_items})

    write_csv("tier_evidence.csv", ["evidence_id", "evidence_item", "first_tier", "max_age_days"],
              [(i[0], i[1], i[2], i[3]) for i in ITEMS])
    write_csv("registry.csv", ["use_case_id", "tier", "owner_unit"],
              [(u["id"], u["reg"], u["unit"]) for u in world if u["reg"] is not None])
    write_csv("use_cases.csv", ["use_case_id", "true_tier", "registry_tier", "registry_status"],
              [(u["id"], u["true"], u["reg"] if u["reg"] is not None else "", u["status"]) for u in world])
    cases, truth = [], []
    for n, j in enumerate(order, 1):
        spec = specs[j]
        pid = f"PR-{n:03d}"
        label, bad = truth_of(spec)
        cases.append((pid, render(spec)))
        truth.append((pid, spec["uc"]["id"], spec["uc"]["true"], spec["kind"], label, ";".join(bad)))
    write_csv("pr_cases.csv", ["pr_id", "body"], cases)
    write_csv("pr_truth.csv", ["pr_id", "use_case_id", "true_tier", "defect_kind", "truth_class", "bad_items"], truth)
    with open("repo_files.txt", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(sorted(files)) + "\n")
    with open("example_pr_body.md", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(example + "\n")
    with open("as_of.txt", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(AS_OF.isoformat() + "\n")
    print(f"wrote {len(cases)} pull requests, {len(world)} use cases and {len(files)} repository files")


if __name__ == "__main__":
    main()
