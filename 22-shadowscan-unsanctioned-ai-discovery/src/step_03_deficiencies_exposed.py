"""Step 3 - Where the blocklist breaks: six named deficiencies, each with a count.

Step 2 showed what a static blocklist catches. This step asks what it cannot do, on the same
synthetic logs, scored against the truth labels in data/truth_sessions.csv (the truth is known
because the data is synthetic).

  (1) A stale blocklist: unsanctioned AI domains that are not on it.
  (2) Embedded AI inside approved SaaS looks sanctioned by domain.
  (3) DNS-only logs show a name but no volume.
  (4) Look-alike benign domains are flagged (false positives).
  (5) Ranking by hit count and ranking by data exposure give different top-10 lists.
  (6) Off-network and personal-device use is invisible.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deficiencies.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics

from step_01_status_quo import (OUT_DIR, by_domain, exposure_index, fmt_int, load_all, true_label,
                                visible_sessions)
from step_02_blocklist_baseline import run_blocklist
from step_02_blocklist_baseline import summarize as summarize_step2

TOP_K = 10


def rank_lists(data: dict) -> dict:
    """Top-10 by hit count vs top-10 by exposure over the true unsanctioned AI domains.

    The domains are picked with the truth label on purpose: discovery is perfect, so any
    difference between the two lists comes from the ranking and not from detection.
    Hits count both logs (what a hit-count report would show). Exposure uses proxy bytes."""
    vis = visible_sessions(data)
    unsanc = [s for s in vis if true_label(data, s) == "unsanctioned_ai"]
    per = by_domain(unsanc)
    proxy_per = by_domain([s for s in unsanc if s["src"] == "proxy"])
    rows = []
    for d, sess in per.items():
        e = exposure_index(proxy_per.get(d, []), data["weights"])
        rows.append({"domain": d, "hits": len(sess), "exposure": e["exposure"], "users": e["users"], "mb_out": e["mb_out"]})
    by_hits = sorted(rows, key=lambda r: (-r["hits"], r["domain"]))
    by_exp = sorted(rows, key=lambda r: (-r["exposure"], r["domain"]))
    for i, r in enumerate(by_hits, 1):
        r["rank_hits"] = i
    for i, r in enumerate(by_exp, 1):
        r["rank_exposure"] = i
    top_h = {r["domain"] for r in by_hits[:TOP_K]}
    top_e = {r["domain"] for r in by_exp[:TOP_K]}
    tot_exp = sum(r["exposure"] for r in rows)
    return {"rows": rows, "by_hits": by_hits, "by_exposure": by_exp, "overlap": len(top_h & top_e),
            "overlap_names": sorted(top_h & top_e),
            "exposure_share_top_hits": sum(r["exposure"] for r in by_hits[:TOP_K]) / tot_exp,
            "exposure_share_top_exposure": sum(r["exposure"] for r in by_exp[:TOP_K]) / tot_exp,
            "n_domains": len(rows)}


def summarize(data: dict) -> dict:
    truth, vis = data["truth"], visible_sessions(data)
    lab = {s["sid"]: truth[s["sid"]]["label"] for s in vis}
    hits = run_blocklist(data)
    s2 = summarize_step2(data)

    # (1) stale blocklist
    unsanc = [s for s in vis if lab[s["sid"]] == "unsanctioned_ai"]
    domains = sorted({s["domain"] for s in unsanc})
    exact = {e["entry"] for e in data["blocklist"] if e["match_type"] == "domain"}
    hit_domains = {s["domain"] for s in unsanc if s["sid"] in hits}
    never_hit = [d for d in domains if d not in hit_domains]
    never_hit_in_feed = [d for d in never_hit if d in data["feed"]]
    never_hit_new = [d for d in never_hit if d not in data["feed"]]
    feed_dead = [d for d in data["feed"] if d not in {s["domain"] for s in vis}]
    d1 = {
        "unsanctioned_domains": len(domains), "not_exact_entries": sum(1 for d in domains if d not in exact),
        "never_hit": len(never_hit), "never_hit_in_feed": len(never_hit_in_feed), "never_hit_new": len(never_hit_new),
        "sessions_pass": s2["missed"], "sessions_total": s2["unsanctioned_visible"],
        "retired_entries": s2["retired_entries"], "exact_entries": s2["exact_entries"],
        "feed_entries": len(data["feed"]), "feed_retired": len(feed_dead),
        "unsanctioned_not_in_feed": sum(1 for d in domains if d not in data["feed"]),
    }

    # (2) embedded AI looks sanctioned by domain
    emb = [s for s in vis if lab[s["sid"]] == "embedded_ai_in_approved_saas"]
    in_catalog = sum(1 for s in emb if s["domain"] in data["catalog_by_domain"])
    d2 = {"embedded_sessions": len(emb), "embedded_proxy": sum(1 for s in emb if s["src"] == "proxy"),
          "embedded_dns": sum(1 for s in emb if s["src"] == "dns"),
          "match_catalog": in_catalog, "blocklist_hits": sum(1 for s in emb if s["sid"] in hits),
          "in_feed": sum(1 for s in emb if s["domain"] in data["feed"]),
          "embedded_domains": len({s["domain"] for s in emb})}

    # (3) DNS-only logs show a name but no volume
    dns_u = [s for s in unsanc if s["src"] == "dns"]
    proxy_u = [s for s in unsanc if s["src"] == "proxy"]
    dns_bytes = [truth[s["sid"]]["out"] for s in dns_u]
    proxy_bytes = sum(s["out"] for s in proxy_u)
    d3 = {"dns_sessions": len(dns_u), "visible_sessions": len(unsanc), "dns_share": len(dns_u) / len(unsanc),
          "dns_true_mb": sum(dns_bytes) / 1e6, "proxy_mb": proxy_bytes / 1e6,
          "dns_byte_share": sum(dns_bytes) / (sum(dns_bytes) + proxy_bytes),
          "dns_min_bytes": min(dns_bytes), "dns_median_bytes": int(statistics.median(dns_bytes)), "dns_max_bytes": max(dns_bytes),
          "dns_domains": len({s["domain"] for s in dns_u}),
          "dns_users": len({s["user"] for s in dns_u})}

    # (4) look-alike false positives
    d4 = {"lookalike_sessions": s2["fp_lookalike"], "lookalike_domains": s2["lookalike_domains_hit"],
          "keyword_hits": s2["keyword_hits"], "keyword_false_share": s2["keyword_lookalike"] / s2["keyword_hits"],
          "blocklist_precision": s2["precision"], "blocklist_hits": s2["hits"], "blocklist_tp": s2["tp"]}

    # (5) hit count vs exposure
    r5 = rank_lists(data)
    top_exp = r5["by_exposure"][0]
    d5 = {"overlap": r5["overlap"], "top_k": TOP_K, "overlap_names": r5["overlap_names"], "n_domains": r5["n_domains"],
          "top_exposure_domain": top_exp["domain"], "top_exposure_rank_by_hits": top_exp["rank_hits"],
          "top_hits_domain": r5["by_hits"][0]["domain"], "top_hits_rank_by_exposure": r5["by_hits"][0]["rank_exposure"],
          "exposure_share_top_hits": r5["exposure_share_top_hits"], "exposure_share_top_exposure": r5["exposure_share_top_exposure"]}

    # (6) off-network
    off = data["offnet"]
    seen_users = {s["user"] for s in unsanc}
    only_off = {o["user"] for o in off} - seen_users
    off_mb = sum(o["out"] for o in off) / 1e6
    d6 = {"off_sessions": len(off), "off_users": len({o["user"] for o in off}), "off_only_users": len(only_off),
          "off_share": len(off) / (len(off) + len(unsanc)), "unsanctioned_visible": len(unsanc),
          "off_mb": off_mb, "visible_mb": (sum(dns_bytes) + proxy_bytes) / 1e6}
    return {"d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5, "d6": d6, "rank": r5}


def write_outputs(s: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    d = s
    rows = [
        (1, "Stale blocklist", d["d1"]["never_hit"], f"unsanctioned AI domains never hit, of {d['d1']['unsanctioned_domains']}"),
        (2, "Embedded AI in approved SaaS looks sanctioned", d["d2"]["match_catalog"], f"embedded-AI sessions that match a catalog domain, of {d['d2']['embedded_sessions']}"),
        (3, "DNS-only logs show no volume", d["d3"]["dns_sessions"], f"unsanctioned AI sessions seen only as a name, of {d['d3']['visible_sessions']}"),
        (4, "Look-alike domains flagged", d["d4"]["lookalike_sessions"], f"false-alarm sessions on {d['d4']['lookalike_domains']} look-alike domains"),
        (5, "Hit count is not exposure", d["d5"]["overlap"], f"domains shared by the top {d['d5']['top_k']} lists"),
        (6, "Off-network use is invisible", d["d6"]["off_sessions"], "injected sessions no log shows"),
    ]
    with open(OUT_DIR / "step_03_deficiencies.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "deficiency", "count", "what_the_count_is"])
        w.writerows(rows)
    with open(OUT_DIR / "step_03_summary.json", "w") as f:
        json.dump({k: v for k, v in s.items() if k != "rank"}, f, indent=2)


def main() -> None:
    data = load_all()
    s = summarize(data)
    write_outputs(s)
    d1, d2, d3, d4, d5, d6 = (s[k] for k in ("d1", "d2", "d3", "d4", "d5", "d6"))
    print("STEP 3 - WHERE THE BLOCKLIST BREAKS: six named deficiencies")
    print("Synthetic data. Counts are scored against truth_sessions.csv. No model is used.")
    print()
    print("(1) A stale blocklist")
    print(f"    {d1['never_hit']} of {d1['unsanctioned_domains']} unsanctioned AI domains are never hit by the list: "
          f"{d1['never_hit_in_feed']} are in the known-AI feed but were never copied to the list, {d1['never_hit_new']} are in neither.")
    print(f"    {fmt_int(d1['sessions_pass'])} of {fmt_int(d1['sessions_total'])} unsanctioned AI sessions pass the list unseen.")
    print(f"    {d1['retired_entries']} of {d1['exact_entries']} exact entries are retired domains. The feed is stale too: {d1['feed_retired']} of {d1['feed_entries']} entries match no traffic, "
          f"and {d1['unsanctioned_not_in_feed']} unsanctioned AI domains are absent from it.")
    print()
    print("(2) Embedded AI inside approved SaaS looks sanctioned by domain")
    print(f"    {fmt_int(d2['embedded_sessions'])} sessions use an AI feature inside {d2['embedded_domains']} approved SaaS products ({fmt_int(d2['embedded_proxy'])} in the proxy log, {fmt_int(d2['embedded_dns'])} in the DNS log).")
    print(f"    {fmt_int(d2['match_catalog'])} of {fmt_int(d2['embedded_sessions'])} match a catalog domain, so they look sanctioned; the blocklist hits {d2['blocklist_hits']}, the feed lists {d2['in_feed']}.")
    print()
    print("(3) DNS-only logs show a name but no volume")
    print(f"    {fmt_int(d3['dns_sessions'])} of {fmt_int(d3['visible_sessions'])} visible unsanctioned AI sessions ({d3['dns_share']*100:.1f}%) are seen only in the DNS log, across {d3['dns_domains']} domains and {d3['dns_users']} staff.")
    print(f"    The truth says they sent {d3['dns_true_mb']:.1f} MB ({d3['dns_byte_share']*100:.1f}% of all bytes out in visible unsanctioned AI sessions). The DNS log shows none of it.")
    print(f"    Bytes out per session range from {fmt_int(d3['dns_min_bytes'])} B to {fmt_int(d3['dns_max_bytes'])} B (median {fmt_int(d3['dns_median_bytes'])} B): one lookup row cannot tell them apart.")
    print()
    print("(4) Look-alike benign domains are flagged")
    print(f"    The keyword rules fire on {fmt_int(d4['lookalike_sessions'])} sessions to {d4['lookalike_domains']} benign look-alike domains.")
    print(f"    {d4['keyword_false_share']*100:.1f}% of keyword hits are false alarms; overall precision of the list is {d4['blocklist_precision']*100:.1f}% ({fmt_int(d4['blocklist_tp'])} of {fmt_int(d4['blocklist_hits'])} hits).")
    print()
    print("(5) Ranking by hit count and ranking by data exposure give different top-10 lists")
    print(f"    Over the {d5['n_domains']} true unsanctioned AI domains (picked by truth, so detection is perfect): the top {d5['top_k']} by hits and the top {d5['top_k']} by exposure share {d5['overlap']} of {d5['top_k']} domains.")
    print(f"    The #1 domain by exposure ({d5['top_exposure_domain']}) is #{d5['top_exposure_rank_by_hits']} by hits; the #1 by hits ({d5['top_hits_domain']}) is #{d5['top_hits_rank_by_exposure']} by exposure.")
    print(f"    The hit-count top {d5['top_k']} holds {d5['exposure_share_top_hits']*100:.1f}% of total exposure; the exposure top {d5['top_k']} holds {d5['exposure_share_top_exposure']*100:.1f}%.")
    print()
    print("(6) Off-network and personal-device use is invisible")
    print(f"    {d6['off_sessions']} unsanctioned AI sessions were injected on personal devices or off the network, by {d6['off_users']} staff. No log row exists for any of them.")
    print(f"    They are {d6['off_share']*100:.1f}% of all unsanctioned AI sessions ({d6['off_sessions']} of {fmt_int(d6['off_sessions'] + d6['unsanctioned_visible'])}). {d6['off_only_users']} of those staff appear in no log as an unsanctioned AI user.")
    print(f"    The truth says they sent {d6['off_mb']:.1f} MB, against {d6['visible_mb']:,.1f} MB in the sessions the logs can show.")
    print()
    print("RESULT")
    print(f"  {'#':<3} {'deficiency':<50} count")
    print(f"  {1:<3} {'Stale blocklist: domains never hit':<50} {d1['never_hit']} of {d1['unsanctioned_domains']}")
    print(f"  {2:<3} {'Embedded AI looks sanctioned by domain':<50} {fmt_int(d2['match_catalog'])} of {fmt_int(d2['embedded_sessions'])} sessions")
    print(f"  {3:<3} {'DNS-only: a name, no volume':<50} {fmt_int(d3['dns_sessions'])} of {fmt_int(d3['visible_sessions'])} sessions")
    print(f"  {4:<3} {'Look-alike domains flagged':<50} {fmt_int(d4['lookalike_sessions'])} sessions on {d4['lookalike_domains']} domains")
    print(f"  {5:<3} {'Hit count vs exposure: top-10 overlap':<50} {d5['overlap']} of {d5['top_k']}")
    print(f"  {6:<3} {'Off-network use: invisible sessions':<50} {d6['off_sessions']}")
    print()
    print("  Top 10 by hits vs top 10 by exposure (true unsanctioned AI domains)")
    print(f"  {'by hits':<28} {'hits':>5}   {'by exposure':<28} {'exposure':>10}")
    for h, e in zip(s["rank"]["by_hits"][:TOP_K], s["rank"]["by_exposure"][:TOP_K]):
        print(f"  {h['domain']:<28} {h['hits']:>5}   {e['domain']:<28} {e['exposure']:>10.0f}")


if __name__ == "__main__":
    main()
