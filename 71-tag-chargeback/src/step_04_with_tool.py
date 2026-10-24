"""Step 4 - The fix: the allocation tool on the full bill, scored against the planted owners.

Rules in order: zero-cost lines are set aside, the cost-center tag decides when it is present (a
present tag that is unknown, closed or contradictory is refused, not overridden), shared services
are split in proportion to what the other rules allocated, untagged lines inherit from tagged lines
of the same resource, and the account default is the last resort. This step prints the hard
negatives (lines that look like problems and are not), the hard cases the rules miss, and writes
what the demo page needs to out/.

Run (from src/):  python3 step_04_with_tool.py
"""
import csv
import json
import os

from common import (OUT_DIR, allocate, compliance_summary, ensure_out, fmt_usd, load_world, pct, plain_usd, score,
                    summarize)

w = load_world()
bill, policy, registry, accounts, truth = w["bill"], w["policy"], w["registry"], w["accounts"], w["truth"]
results = allocate(bill, policy, registry, accounts)
summ = summarize(bill, results)
sc = score(bill, results, truth)
comp = compliance_summary(bill, policy, registry)
total, unalloc = summ["total"], summ["unallocated"]
reconciled = sum(usd for r in results for _, usd in r["shares"]) + unalloc == total
by = sc["by_defect"]

print("STEP 4 - the allocation tool on the full bill")
print(f"  net spend: {fmt_usd(total)}   allocated: {fmt_usd(summ['allocated'])} ({pct(summ['allocated'], total)})   "
      f"unallocated: {fmt_usd(unalloc)} ({pct(unalloc, total)})   limit in the policy: {policy['max_unallocated_pct']:.1f}%")
print(f"  allocated plus unallocated equals the bill to the cent: {'yes' if reconciled else 'NO'}")
print(f"  against the planted owners: correct {fmt_usd(sc['correct'])} ({pct(sc['correct'], total)}), "
      f"wrong {fmt_usd(sc['wrong'])} ({pct(sc['wrong'], total)}), left for a person {fmt_usd(sc['left'])} ({pct(sc['left'], total)})")
print(f"  tag compliance: {comp['strict']} of {comp['lines']} lines strict ({pct(comp['strict_usd'], comp['usd'])} of dollars); "
      f"{comp['repaired']} of {comp['lines']} after repair ({pct(comp['repaired_usd'], comp['usd'])})")
print("  unallocated by reason:")
for reason, (n, usd) in sorted(summ["by_reason"].items(), key=lambda kv: (-kv[1][1], kv[0])):
    print(f"    {reason:<22}{n:>5} lines{fmt_usd(usd):>14}")

untagged = [b for b in bill if not b["tags"].get("cost-center", "").strip()]
needs_none = [b for b in untagged if b["usd"] == 0 or b["service"] in policy["shared_services"]]
print("  hard negatives, lines that look like problems and are not:")
print(f"    a plain count of lines without the cost-center key flags {len(untagged)}; {len(needs_none)} of them need no tag "
      f"(zero cost or shared service), so the tool asks for a fix on {len(untagged) - len(needs_none)}")
for kind, text in (("zero_cost", "zero-cost untagged lines"), ("shared_service", "shared-service lines, split by proportion"),
                   ("credit", "credit lines allocated to the planted owner"),
                   ("foreign_tagged", "lines of resources tagged for their own team inside another team's account"),
                   ("value_format", "tags in another case or with spaces"), ("alias_key", "tags under a listed alias key")):
    d = by[kind]
    print(f"    {text}: {d['n_correct']} of {d['lines']} handled correctly ({fmt_usd(d['usd'])})")
print("  hard cases the rules miss:")
for kind, text in (("wrong_valid", "valid tag, wrong cost center"), ("wrong_default", "untagged resource of another team in a dedicated account"),
                   ("alias_unlisted", "cost-center key spelled in a way the policy does not list"),
                   ("value_nohyphen", "cost-center value with the hyphen dropped")):
    d = by[kind]
    print(f"    {text}: {d['lines']} lines, correct {fmt_usd(d['correct'])}, wrong {fmt_usd(d['wrong'])}, left {fmt_usd(d['left'])}")
print("  by planted defect (lines, spend, correct, wrong, left):")
for kind in sorted(by):
    d = by[kind]
    print(f"    {kind:<16}{d['lines']:>5}{fmt_usd(d['usd']):>14}{fmt_usd(d['correct']):>14}{fmt_usd(d['wrong']):>12}{fmt_usd(d['left']):>12}")

ensure_out()
own = {}
for b in bill:
    cc = truth[b["line_id"]]["cc"]
    own[cc] = own.get(cc, 0) + b["usd"]
with open(os.path.join(OUT_DIR, "step_04_chargeback.csv"), "w", newline="", encoding="utf-8") as fh:
    out = csv.writer(fh, lineterminator="\n")
    out.writerow(["cost_center", "name", "active", "direct", "inherit", "account_default", "shared", "total", "planted_own_spend"])
    for rec in registry.values():
        row = summ["chargeback"].get(rec["cost_center"], {"direct": 0, "inherit": 0, "account_default": 0, "shared": 0})
        out.writerow([rec["cost_center"], rec["name"], rec["active"]] + [plain_usd(row[k]) for k in ("direct", "inherit", "account_default", "shared")]
                     + [plain_usd(sum(row.values())), plain_usd(own.get(rec["cost_center"], 0))])
with open(os.path.join(OUT_DIR, "step_04_defects.csv"), "w", newline="", encoding="utf-8") as fh:
    out = csv.writer(fh, lineterminator="\n")
    out.writerow(["defect", "lines", "usd", "correct", "wrong", "left"])
    for kind in sorted(by):
        d = by[kind]
        out.writerow([kind, d["lines"], plain_usd(d["usd"]), plain_usd(d["correct"]), plain_usd(d["wrong"]), plain_usd(d["left"])])
with open(os.path.join(OUT_DIR, "step_04_reasons.csv"), "w", newline="", encoding="utf-8") as fh:
    out = csv.writer(fh, lineterminator="\n")
    out.writerow(["reason", "lines", "usd"])
    for reason, (n, usd) in sorted(summ["by_reason"].items(), key=lambda kv: (-kv[1][1], kv[0])):
        out.writerow([reason, n, plain_usd(usd)])
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump({"lines": len(bill), "net_spend": plain_usd(total), "allocated": plain_usd(summ["allocated"]), "unallocated": plain_usd(unalloc),
               "unallocated_pct": pct(unalloc, total), "correct": plain_usd(sc["correct"]), "correct_pct": pct(sc["correct"], total),
               "wrong": plain_usd(sc["wrong"]), "wrong_pct": pct(sc["wrong"], total), "left": plain_usd(sc["left"]),
               "left_pct": pct(sc["left"], total), "compliance_strict": pct(comp["strict_usd"], comp["usd"]),
               "compliance_repaired": pct(comp["repaired_usd"], comp["usd"]), "limit_pct": "%.1f%%" % policy["max_unallocated_pct"]},
              fh, indent=1, sort_keys=True)
    fh.write("\n")
print("  wrote out/step_04_chargeback.csv, step_04_defects.csv, step_04_reasons.csv, step_04_summary.json")
