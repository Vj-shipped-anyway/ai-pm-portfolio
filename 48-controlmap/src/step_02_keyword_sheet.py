"""Step 2 - The common basic approach: a keyword sheet.

Link an obligation to every control that shares at least two content words with it (words of four letters
or more, no stop words, a trailing s removed). The sheet knows nothing about status, scope or dates, and it
cannot tell a retired control from a live one. Status is read the same way as in step 1: any link means
covered, none means uncovered. It is scored against the planted truth map.

Run (from src/):  python3 step_02_keyword_sheet.py
"""
from common import load_all, sheet_links, covered_or_not, pair_scores, pct, count_by

data = load_all()
obs, truth = data["obligations"], data["truth_status"]
links = sheet_links(data)
found = {(oid, cid) for oid, cids in links.items() for cid in cids}
right = sum(1 for o in obs if covered_or_not(links[o["obligation_id"]]) == truth[o["obligation_id"]])
mix = count_by(truth.values())
tp, n_found, n_truth = pair_scores(found, data)

print("STEP 2 - keyword sheet (two shared content words)")
print(f"  links: {n_found} across {sum(1 for v in links.values() if v)} of {len(obs)} obligations")
print(f"  true pairs found: {tp} of {n_truth} (recall {pct(tp, n_truth)})")
print(f"  links that are not true pairs: {n_found - tp} of {n_found} (precision {pct(tp, n_found)})")
print(f"  right status: {right} of {len(obs)} ({pct(right, len(obs))})")
print(f"  most a covered or uncovered reading can reach: {mix.get('COVERED', 0) + mix.get('UNCOVERED', 0)} of {len(obs)}")
print("  The sheet has no scope, no evidence date, no retired flag and no list of controls that serve nothing.")
