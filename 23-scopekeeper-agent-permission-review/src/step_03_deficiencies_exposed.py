"""Step 3 - Where annual recertification breaks: six named deficiencies, each with a count.

Step 2 showed that the review approves almost everything on the list. This step asks what the
review cannot see, using the same grants, the 90 days of calls and, for scoring only, the truth
file the generator wrote (data/needed_truth.csv).

  (1) Grants never used in 90 days.
  (2) Over-broad scopes: wildcard grants where calls touched only one or two specific scopes.
  (3) Privilege creep: grants added after launch and not used.
  (4) Shared service account: calls that cannot be attributed to one agent.
  (5) High-impact calls made without the human approval the catalog requires.
  (6) Recertification removed almost nothing although the usage diff finds many unused grants.

Counts of use come from the call log. A call with no agent tag is credited to every agent on its
service account who could have made it (see usage_index in step 1).

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deficiencies.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

from step_01_status_quo import IMPACT_ORDER, OUT_DIR, grant_usage, load_all, usage_index
from step_02_annual_recertification import summarize as summarize_step2


def pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def summarize(data: dict) -> dict:
    u = usage_index(data)
    gu = grant_usage(data, u)
    n = len(gu)
    unused = [g for g in gu if not g["used"]]
    wild = [g for g in gu if g["wildcard"]]

    # (1) never used
    s1 = {"unused": len(unused), "unused_pct": pct(len(unused), n),
          "unused_high_impact": sum(1 for g in unused if g["needs_approval"]),
          "unused_by_impact": {k: sum(1 for g in unused if g["impact"] == k) for k in IMPACT_ORDER},
          "unused_money_or_message": sum(1 for g in unused if g["impact"] in ("money_movement", "external_message"))}

    # (2) over-broad wildcards
    over = [g for g in wild if 1 <= len(g["touched"]) <= 2]
    masked = [g for g in wild if len(g["touched_tagged"]) <= 2 and len(g["touched"]) > 2]
    s2 = {"wildcards": len(wild), "over_broad": len(over),
          "over_broad_list": [(g["agent_id"], g["scope"], len(g["touched"]), g["reach"]) for g in over],
          "excess_reach": sum(g["reach"] - len(g["touched"]) for g in over),
          "unused_wildcards": sum(1 for g in wild if not g["touched"]),
          "wide_use_wildcards": sum(1 for g in wild if len(g["touched"]) > 2),
          "masked": len(masked), "masked_list": [(g["agent_id"], g["scope"]) for g in masked]}

    # (3) privilege creep
    post = [g for g in gu if g["post_launch"]]
    launch = [g for g in gu if not g["post_launch"]]
    post_unused = [g for g in post if not g["used"]]
    s3 = {"post_launch": len(post), "post_launch_pct": pct(len(post), n),
          "post_launch_unused": len(post_unused), "post_launch_unused_pct": pct(len(post_unused), len(post)),
          "launch_unused": sum(1 for g in launch if not g["used"]), "launch": len(launch),
          "launch_unused_pct": pct(sum(1 for g in launch if not g["used"]), len(launch)),
          "post_unused_high_impact": sum(1 for g in post_unused if g["needs_approval"]),
          "post_unused_money": sum(1 for g in post_unused if g["impact"] == "money_movement")}

    # (4) shared service accounts
    calls = data["calls"]
    unattr = [c for c in calls if not c["agent_id"]]
    only_shared = [g for g in gu if g["only_shared"]]
    by_acct = Counter(c["service_account"] for c in unattr)
    s4 = {"unattributed": len(unattr), "unattributed_pct": pct(len(unattr), len(calls)), "calls": len(calls),
          "shared_accounts": len(data["shared_accounts"]),
          "agents_on_shared": sum(len(data["sa_agents"][s]) for s in data["shared_accounts"]),
          "by_account": {k: by_acct.get(k, 0) for k in data["shared_accounts"]},
          "unattributed_needs_approval": sum(1 for c in unattr if data["catalog"][c["scope"]]["needs_approval"]),
          "only_shared": len(only_shared),
          "only_shared_unneeded": sum(1 for g in only_shared
                                      if not data["needed"][(g["agent_id"], g["scope"])]["needed"])}

    # (5) high-impact calls without the required approval
    req = [c for c in calls if data["catalog"][c["scope"]]["needs_approval"]]
    bad = [c for c in req if c["human_approved"] == "no"]
    by_agent = Counter(c["agent_id"] or "(no tag)" for c in bad)
    s5 = {"approval_required_calls": len(req), "unapproved": len(bad), "unapproved_pct": pct(len(bad), len(req)),
          "unapproved_by_impact": {k: sum(1 for c in bad if data["catalog"][c["scope"]]["impact"] == k)
                                   for k in IMPACT_ORDER if k != "read"},
          "unapproved_untagged": sum(1 for c in bad if not c["agent_id"]),
          "agents_with_unapproved": len({c["agent_id"] for c in bad if c["agent_id"]}),
          "top_agents": by_agent.most_common(4)}

    # (6) recertification vs the usage diff
    s2r = summarize_step2(data)
    unused_ids = {(g["agent_id"], g["scope"]) for g in unused}
    removed_unused = sum(1 for r in s2r["removed_list"] if (r["agent_id"], r["scope"]) in unused_ids)
    s6 = {"recert_removed": s2r["removed"], "usage_unused": len(unused), "recert_removed_unused": removed_unused,
          "recert_removed_unused_pct": pct(removed_unused, len(unused)),
          "recert_removed_in_use": s2r["removed_in_use"], "recert_denied_calls": s2r["replay_denied"],
          "grants": n}
    return {"d1": s1, "d2": s2, "d3": s3, "d4": s4, "d5": s5, "d6": s6, "grants": n}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)
    d1, d2, d3, d4, d5, d6 = s["d1"], s["d2"], s["d3"], s["d4"], s["d5"], s["d6"]
    n = s["grants"]

    print("\n" + "=" * 78)
    print("Step 3 - Where annual recertification breaks: six named deficiencies")
    print("=" * 78)
    print(f"\n{n} grants, {d4['calls']:,} calls over 90 days. Data is synthetic and seeded.\n")

    print("(1) Grants that were never used in 90 days")
    print(f"    {d1['unused']} of {n} grants ({d1['unused_pct']}%) have no call in the window, directly or through a shared account.")
    print("    By impact: " + ", ".join(f"{k} {v}" for k, v in d1["unused_by_impact"].items()) + ".")
    print(f"    {d1['unused_high_impact']} of them are high-impact (the catalog says a human must approve the call).")

    print("\n(2) Over-broad scopes: a wildcard grant where calls touched one or two specific scopes")
    print(f"    {d2['over_broad']} of {d2['wildcards']} wildcard grants touched only 1 or 2 of the scopes they reach; "
          f"{d2['unused_wildcards']} touched none, {d2['wide_use_wildcards']} touched 3 or more.")
    for a, sc, k, r in d2["over_broad_list"]:
        print(f"      {a} {sc:<12} touched {k} of {r}")
    print(f"    Narrowing those {d2['over_broad']} wildcards to the scopes used cuts {d2['excess_reach']} entitlements.")
    print(f"    {d2['masked']} more wildcard grant{'s' if d2['masked'] != 1 else ''} look{'s' if d2['masked'] == 1 else ''} "
          "wider in use only because siblings on the shared account called through it.")

    print("\n(3) Privilege creep: grants added after launch that were never used")
    print(f"    {d3['post_launch']} of {n} grants ({d3['post_launch_pct']}%) were added after launch.")
    print(f"    {d3['post_launch_unused']} of those {d3['post_launch']} ({d3['post_launch_unused_pct']}%) have no call in the window; "
          f"launch grants: {d3['launch_unused']} of {d3['launch']} ({d3['launch_unused_pct']}%).")
    print(f"    Of the unused after-launch grants, {d3['post_unused_high_impact']} are high-impact and {d3['post_unused_money']} move money.")

    print("\n(4) Shared service account: calls that cannot be attributed to one agent")
    print(f"    {d4['agents_on_shared']} agents share {d4['shared_accounts']} service accounts. "
          f"{d4['unattributed']:,} of {d4['calls']:,} calls ({d4['unattributed_pct']}%) carry no agent tag.")
    print("    By account: " + ", ".join(f"{k} {v}" for k, v in d4["by_account"].items()) + ".")
    print(f"    {d4['unattributed_needs_approval']} of those calls are to scopes that need human approval.")
    print(f"    {d4['only_shared']} grants look used only because of untagged calls; "
          f"by the generator's truth {d4['only_shared_unneeded']} of them are not needed by that agent.")

    print("\n(5) High-impact calls made without the human approval the catalog requires")
    print(f"    {d5['unapproved']} of {d5['approval_required_calls']:,} calls to approval-required scopes "
          f"({d5['unapproved_pct']}%) were logged with no human approval.")
    print("    By impact: " + ", ".join(f"{k} {v}" for k, v in d5["unapproved_by_impact"].items()) + ".")
    print(f"    {d5['agents_with_unapproved']} agents, plus {d5['unapproved_untagged']} calls with no agent tag. "
          "Largest: " + ", ".join(f"{a} {c}" for a, c in d5["top_agents"]) + ".")
    print("    The recertification list has no column for this; the grants were approved all the same.")

    print("\n(6) Recertification removed almost nothing, although the usage diff finds many unused grants")
    print(f"    Recertification removed {d6['recert_removed']} of {n} grants; the usage diff finds {d6['usage_unused']} unused.")
    print(f"    Of the {d6['usage_unused']} unused grants, recertification removed {d6['recert_removed_unused']} "
          f"({d6['recert_removed_unused_pct']}%).")
    print(f"    {d6['recert_removed_in_use']} of its {d6['recert_removed']} removals hit a grant that was in use; "
          f"replaying the 90 days under that result denies {d6['recert_denied_calls']} calls.")

    print("\nRecertification checks that a ticket exists. It does not check that the access is used.")

    rows = [
        ("1", "Grants never used in 90 days", d1["unused"], n),
        ("2", "Over-broad wildcard grants (1 or 2 scopes touched)", d2["over_broad"], d2["wildcards"]),
        ("3", "Unused grants added after launch", d3["post_launch_unused"], d3["post_launch"]),
        ("4", "Calls with no agent tag on a shared account", d4["unattributed"], d4["calls"]),
        ("5", "Approval-required calls with no approval", d5["unapproved"], d5["approval_required_calls"]),
        ("6", "Unused grants removed by recertification", d6["recert_removed_unused"], d6["usage_unused"]),
    ]
    with open(OUT_DIR / "step_03_deficiencies.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["number", "deficiency", "count", "out_of"])
        w.writerows(rows)
    with open(OUT_DIR / "step_03_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_03_deficiencies.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
