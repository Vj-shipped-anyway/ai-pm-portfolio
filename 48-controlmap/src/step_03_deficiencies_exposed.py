"""Step 3 - Where the keyword sheet and a bare dictionary fail.

Seven named deficiencies, each counted against the planted truth:
  1 lookalike words      the sheet links controls that serve nothing, or serve another theme
  2 different words      the sheet misses controls that mean the same in other words
  3 wrong scope          a control that covers only part of the obligation reads as covered
  4 stale evidence       a control with old evidence reads as covered
  5 retired controls     the sheet links a retired control, and some obligations rest on nothing else
  6 denied phrases       a dictionary alone links a control that only says it is NOT the thing
  7 a missing theme      a dictionary with no row for a theme reads as a gap

KNOWN LIMIT, left in on purpose: a control that uses a dictionary phrase in another sense ("drift dashboard"
for network switch settings) is linked by the dictionary, and neither the dictionary nor the negation rule
can see it. Step 4 does not fix it. The script prints those links.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_all, sheet_links, covered_or_not, count_by
from controlmap import analyze

data = load_all()
obs, truth, kind = data["obligations"], data["truth_status"], data["kind"]
links = sheet_links(data)
sheet_pairs = {(oid, cid) for oid, cids in links.items() for cid in cids}
truth_pairs = set(data["truth_pairs"])
false_pairs = sheet_pairs - truth_pairs
sheet_status = {oid: covered_or_not(v) for oid, v in links.items()}
grace = data["meta"]["grace"]
cm = analyze(obs, data["controls"], data["terms"], grace)
raw = analyze(obs, data["controls"], data["terms"], grace, negation=False)


def of_truth(status):
    return [o["obligation_id"] for o in obs if truth[o["obligation_id"]] == status]


print("STEP 3 - deficiencies exposed")
print("  1. lookalike words")
by_kind = count_by(kind[cid] if data["ctl_by_id"][cid]["active"] else "retired" for _o, cid in false_pairs)
print(f"     sheet links that are not true pairs: {len(false_pairs)} of {len(sheet_pairs)}")
print("     by the kind of control linked: " + ", ".join(f"{k} {n}" for k, n in sorted(by_kind.items())))
print("  2. different words")
missed = truth_pairs - sheet_pairs
miss_kind = count_by(kind[cid] for _o, cid in missed)
print(f"     true pairs the sheet misses: {len(missed)} of {len(truth_pairs)}")
print("     by the kind of control missed: " + ", ".join(f"{k} {n}" for k, n in sorted(miss_kind.items())))
print("  3. wrong scope")
part = of_truth("PARTIAL")
print(f"     PARTIAL obligations the sheet shows as covered: {sum(1 for o in part if sheet_status[o] == 'COVERED')} of {len(part)}")
print("  4. stale evidence")
stale = of_truth("STALE")
print(f"     STALE obligations the sheet shows as covered: {sum(1 for o in stale if sheet_status[o] == 'COVERED')} of {len(stale)}")
print("  5. retired controls")
ret_links = [(o, c) for o, c in sheet_pairs if not data["ctl_by_id"][c]["active"]]
print(f"     sheet links to retired controls: {len(ret_links)} across {len({o for o, _c in ret_links})} obligations")
no_real = [o for o in of_truth("UNCOVERED") if sheet_status[o] == "COVERED"]
print(f"     UNCOVERED obligations the sheet shows as covered: {len(no_real)} of {len(of_truth('UNCOVERED'))}")
print("  6. denied phrases (dictionary, negation rule switched off)")
decoys = {c for c, k in kind.items() if k == "negated_decoy"}
raw_decoy = {(r["obligation_id"], l["control_id"]) for r in raw["rows"] for l in r["links"] if l["control_id"] in decoys}
cm_decoy = {(r["obligation_id"], l["control_id"]) for r in cm["rows"] for l in r["links"] if l["control_id"] in decoys}
print(f"     links to controls that only deny a phrase: {len(raw_decoy)} without the negation rule, {len(cm_decoy)} with it")
print("  7. a missing theme")
unmapped = [r["obligation_id"] for r in cm["rows"] if r["status"] == "UNMAPPED"]
hidden = [o for o in unmapped if truth[o] != "UNCOVERED"]
print(f"     obligations whose theme has no dictionary row: {len(unmapped)}; read as a gap they would be wrong for {len(hidden)}")
print("     ControlMap reports them as UNMAPPED instead of UNCOVERED, so the dictionary row gets written.")
wrong = {c for c, k in kind.items() if k == "wrong_sense"}
wl = sorted({(l["control_id"], r["obligation_id"]) for r in cm["rows"] for l in r["links"] if l["control_id"] in wrong})
print("  KNOWN LIMIT (not fixed in step 4): a dictionary phrase used in another sense")
for cid in sorted(wrong):
    ob = [o for c, o in wl if c == cid]
    print(f"     {cid} {data['ctl_by_id'][cid]['name']} is linked to {len(ob)} obligations: {', '.join(ob)}")
