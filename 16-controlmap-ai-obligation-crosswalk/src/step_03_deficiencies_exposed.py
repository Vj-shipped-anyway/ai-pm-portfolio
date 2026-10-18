"""Step 3 - Where the keyword sheet breaks: six named deficiencies, each with a count.

Same synthetic data, same sheet as step 2. This script scores the sheet against data/truth_map.csv
and counts six specific ways it fails:

  (a) lookalike words counted as coverage (homonyms and generic wording)
  (b) synonym misses: a control truly meets the obligation but uses different words
  (c) partial coverage shown as covered (the control's scope misses a class the obligation covers)
  (d) stale evidence hiding behind "covered" (the sheet carries no evidence date)
  (e) orphan controls: controls that meet no obligation, which the sheet cannot list and which its
      word matching links to obligations anyway
  (f) the same theme asked for as separate evidence requests by different frameworks

The truth is known because the data is synthetic: the generator decided which control meets which
obligation. Evidence is stale when its latest item is older than 1.5 times the control's test cycle,
measured at the fixed date AS_OF in step 1.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_summary.json.
"""

from __future__ import annotations

import json
from collections import Counter

from step_01_status_quo import OUT_DIR, load_all, summarize as summarize_step1, truth_statuses
from step_02_keyword_crosswalk import keyword_matches


def pct(a: int, b: int) -> float:
    return round(a / b * 100, 1)


def summarize(data: dict) -> dict:
    m = keyword_matches(data)
    ts = truth_statuses(data)
    fresh = data["fresh"]
    tb = data["truth_by_ob"]
    truth_pairs = {(o, c) for o, d in tb.items() for c in d}
    sheet_pairs = {(o, c) for o, h in m.items() for c in h}
    n_ob = len(data["obligations"])

    # (a) lookalike words counted as coverage
    false_pairs = sheet_pairs - truth_pairs
    only_false = [o for o, h in m.items() if h and not (set(h) & set(tb.get(o, {})))]
    only_false_uncovered = [o for o in only_false if ts[o][0] == "UNCOVERED"]
    uncovered = [o for o, v in ts.items() if v[0] == "UNCOVERED"]
    uncovered_marked = [o for o in uncovered if m[o]]
    by_control = Counter(c for _, c in sorted(false_pairs))
    worst = by_control.most_common(1)[0]

    # (b) synonym misses
    missed_pairs = truth_pairs - sheet_pairs
    truth_obs = [o for o in tb if tb[o]]
    none_found = [o for o in truth_obs if not (set(m[o]) & set(tb[o]))]
    none_found_blank = [o for o in none_found if not m[o]]
    missed_by_control = Counter(c for _, c in sorted(missed_pairs))

    # (c) partial coverage shown as covered
    partial_obs = [o for o, v in ts.items() if v[0] == "PARTIAL"]
    partial_marked = [o for o in partial_obs if m[o]]

    # (d) covered obligations with no fresh evidence behind any linked control
    marked = [o for o, h in m.items() if h]
    no_fresh = [o for o in marked if not any(fresh[c]["state"] == "fresh" for c in m[o])]
    stale_truth = [o for o, v in ts.items() if v[0] == "STALE"]
    stale_marked = [o for o in stale_truth if m[o]]
    stale_in_no_fresh = [o for o in stale_truth if o in no_fresh]

    # (e) orphan controls
    linked_ct = {c for _, c in truth_pairs}
    orphans = [c["control_id"] for c in data["controls"] if c["control_id"] not in linked_ct]
    orphans_linked = [c for c in orphans if any(c in h for h in m.values())]
    orphan_links = sum(1 for o, h in m.items() for c in h if c in set(orphans))
    orphans_active = [c for c in orphans if data["ct_by_id"][c]["active"]]

    # (f) cross-framework duplicates asked as separate evidence requests
    s1 = summarize_step1(data)

    # examples printed under each deficiency
    ct = data["ct_by_id"]
    truth_count = Counter(c for _, c in sorted(truth_pairs))
    b_examples = [(c, n, truth_count[c]) for c, n in missed_by_control.most_common() if n == truth_count[c]][:4]
    c_examples = []
    for o in partial_obs:
        ob = data["ob_by_id"][o]
        true_named = sorted(c for c in m[o] if c in tb[o])
        c_examples.append((o, ob["theme"], sorted(ob["classes"]), len(m[o]), true_named))
    d_examples = []
    for o in stale_truth:
        full = [c for c, v in tb[o].items() if v == "full"]
        best = min(full, key=lambda c: fresh[c]["age"] if fresh[c]["age"] is not None else 10 ** 6)
        d_examples.append((o, data["ob_by_id"][o]["theme"], fresh[best]["age"], int(fresh[best]["limit"]), len(m[o])))
    e_examples = []
    for cid in orphans_linked:
        hits = [(o, h[cid]) for o, h in m.items() if cid in h]
        e_examples.append((cid, hits))
    return {
        "b_examples": b_examples, "c_examples": c_examples, "d_examples": d_examples, "e_examples": e_examples,
        "obligations": n_ob,
        "a_false_pairs": len(false_pairs), "a_sheet_pairs": len(sheet_pairs),
        "a_only_false": len(only_false), "a_marked": len(marked),
        "a_only_false_uncovered": len(only_false_uncovered),
        "a_uncovered": len(uncovered), "a_uncovered_marked": len(uncovered_marked),
        "a_worst_control": worst[0], "a_worst_count": worst[1],
        "a_worst_name": data["ct_by_id"][worst[0]]["name"],
        "b_missed_pairs": len(missed_pairs), "b_truth_pairs": len(truth_pairs),
        "b_none_found": len(none_found), "b_truth_obs": len(truth_obs),
        "b_none_found_blank": len(none_found_blank), "b_none_found_hidden": len(none_found) - len(none_found_blank),
        "b_top_missed": [(c, n) for c, n in missed_by_control.most_common(3)],
        "c_partial": len(partial_obs), "c_partial_marked": len(partial_marked),
        "d_no_fresh": len(no_fresh), "d_marked": len(marked),
        "d_stale_truth": len(stale_truth), "d_stale_marked": len(stale_marked), "d_stale_in_no_fresh": len(stale_in_no_fresh),
        "e_orphans": len(orphans), "e_orphans_active": len(orphans_active), "e_orphans_linked": len(orphans_linked),
        "e_orphan_links": orphan_links, "e_linked_ids": orphans_linked,
        "f_requests": s1["requests_per_framework"], "f_themes": s1["requests_per_theme"],
        "f_repeat": s1["repeat_requests"], "f_repeat_pct": s1["repeat_pct"],
        "ids": {"only_false": only_false, "none_found": none_found, "partial_marked": partial_marked,
                "no_fresh": no_fresh, "stale_truth": stale_truth},
    }


def main() -> None:
    data = load_all()
    s = summarize(data)
    ct = data["ct_by_id"]
    print("STEP 3 - Where the keyword sheet breaks: 6 named deficiencies")
    print("  (same sheet as step 2, scored against data/truth_map.csv; the truth is known because the data is synthetic)")
    print()
    print("(a) Lookalike words are counted as coverage")
    print(f"    {s['a_false_pairs']} of {s['a_sheet_pairs']} ({pct(s['a_false_pairs'], s['a_sheet_pairs'])}%) links the sheet makes are to controls that do not meet the obligation.")
    print(f"    {s['a_only_false']} of {s['a_marked']} ({pct(s['a_only_false'], s['a_marked'])}%) 'covered' obligations are covered only by such controls.")
    print(f"    {s['a_uncovered_marked']} of the {s['a_uncovered']} ({pct(s['a_uncovered_marked'], s['a_uncovered'])}%) obligations with no meeting control are marked covered.")
    print(f"    Worst case: {s['a_worst_control']} {s['a_worst_name']} is linked to {s['a_worst_count']} obligations it does not meet.")
    print()
    print("(b) Synonym misses: the right control uses different words")
    print(f"    {s['b_missed_pairs']} of {s['b_truth_pairs']} ({pct(s['b_missed_pairs'], s['b_truth_pairs'])}%) true pairs are not linked by the sheet.")
    print(f"    For {s['b_none_found']} of {s['b_truth_obs']} ({pct(s['b_none_found'], s['b_truth_obs'])}%) obligations that have a meeting control, the sheet finds none of them")
    print(f"    ({s['b_none_found_blank']} are shown as not covered, {s['b_none_found_hidden']} look covered through other controls).")
    print("    Controls whose every true pair is missed (different words, same meaning):")
    for cid, n, tot in s["b_examples"]:
        print(f"      {cid} {ct[cid]['name']:<38} {n} of {tot} true pairs missed")
    print()
    print("(c) Partial coverage is shown as covered")
    print(f"    {s['c_partial_marked']} of {s['c_partial']} ({pct(s['c_partial_marked'], s['c_partial'])}%) obligations whose only meeting controls miss part of their scope are marked covered.")
    for o, theme, need, n_links, true_named in s["c_examples"]:
        plural = "control" if n_links == 1 else "controls"
        if not n_links:
            tail = "the sheet marks it not covered"
        elif true_named:
            tail = f"marked covered via {n_links} {plural}; true partial: {true_named[0]} (scope {ct[true_named[0]]['scope']})"
        else:
            tail = f"marked covered via {n_links} {plural}, none a true partial"
        need_text = "all classes" if len(need) == 4 else ", ".join(need)
        print(f"      {o} {theme:<30} needs {need_text}; {tail}")
    print()
    print("(d) Stale evidence hides behind 'covered'")
    print(f"    {s['d_stale_marked']} of {s['d_stale_truth']} ({pct(s['d_stale_marked'], s['d_stale_truth'])}%) obligations whose full-scope controls all have stale or missing evidence are marked covered.")
    print(f"    A freshness filter on the sheet's own links would flag {s['d_stale_in_no_fresh']} of those {s['d_stale_truth']}: lookalike links to unrelated fresh controls hide the rest.")
    print(f"    Across all {s['d_marked']} obligations marked covered, {s['d_no_fresh']} have no linked control with fresh evidence.")
    for o, theme, age, limit, n_links in s["d_examples"]:
        print(f"      {o} {theme:<32} newest full-scope evidence {age} days old, limit {limit}; the sheet links {n_links} control{'s' if n_links != 1 else ''}")
    print()
    print("(e) Orphan controls are hidden")
    print(f"    {s['e_orphans']} controls meet no obligation ({s['e_orphans_active']} active). The sheet has no view that lists them.")
    print(f"    Its word matching links {s['e_orphans_linked']} of the {s['e_orphans']} ({pct(s['e_orphans_linked'], s['e_orphans'])}%) to at least one obligation ({s['e_orphan_links']} links), so they look useful.")
    for cid, hits in s["e_examples"]:
        shown = "; ".join(f"{o} on {', '.join(w)}" for o, w in hits[:2])
        print(f"      {cid} {ct[cid]['name']:<36} {shown}")
    print()
    print("(f) The same theme is asked for as separate evidence requests")
    print(f"    {s['f_requests']} requests go out, one per obligation row, for {s['f_themes']} distinct themes.")
    print(f"    {s['f_repeat']} of {s['f_requests']} ({s['f_repeat_pct']}%) repeat a theme another row has already asked for.")
    print()
    print("Top controls the sheet links wrongly (obligations linked that the control does not meet):")
    fp = Counter()
    for o, h in keyword_matches(data).items():
        for c in h:
            if c not in data["truth_by_ob"].get(o, {}):
                fp[c] += 1
    for c, n in fp.most_common(5):
        print(f"    {c} {ct[c]['name']:<36} {n}")

    OUT_DIR.mkdir(exist_ok=True)
    keep = {k: v for k, v in s.items() if k != "ids"}
    (OUT_DIR / "step_03_summary.json").write_text(json.dumps(keep, indent=2), encoding="utf-8")
    print("\nWrote step_03_summary.json in src/out/")


if __name__ == "__main__":
    main()
