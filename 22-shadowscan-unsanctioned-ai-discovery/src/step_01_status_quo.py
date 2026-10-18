"""Step 1 - Before ShadowScan: the proxy report shows hits by domain, and nobody reviews AI use.

A modeled bank has a sanctioned catalog of approved tools. Staff also use AI tools nobody approved.
The only view the security team has today is the proxy report: domains ranked by hits. This script
reads the synthetic logs and shows what that report looks like, and how much AI use sits in it
unreviewed. The truth labels (data/truth_sessions.csv) say which domains are unsanctioned AI tools;
the truth is known because the data is synthetic. Nothing here is a real bank, product or log.
No model is used anywhere in this repo.

PREMISE (modeled, not measured): no process in this modeled bank reviews AI-looking traffic. The
report is read for volume and for known-bad domains only.

Run (from src/):
    python3 step_01_status_quo.py

Output: a readable summary, plus out/step_01_top_domains.csv and out/step_01_summary.json.
This file also holds the shared loaders and the exposure formula that later steps and the app import.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

LABELS = ["sanctioned_ai", "unsanctioned_ai", "embedded_ai_in_approved_saas", "benign_lookalike", "other", "off_network"]
TOP_N_REPORT = 15


# ---------------------------------------------------------------------------
# Shared loaders (later steps and the app import these)
# ---------------------------------------------------------------------------
def reg_domain(host: str) -> str:
    """The registered domain of a host: the last two labels (every domain here ends in .example)."""
    return ".".join(host.split(".")[-2:])


def _read(path: Path) -> list:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load every CSV into plain dicts. No pandas needed."""
    depts = {r["dept"]: {"name": r["dept_name"], "weight": int(r["sensitivity_weight"])}
             for r in _read(data_dir / "dept_sensitivity.csv")}
    users = {r["user_id"]: {"dept": r["dept"], "site": r["site"]} for r in _read(data_dir / "users.csv")}

    catalog = []
    for r in _read(data_dir / "sanctioned_catalog.csv"):
        catalog.append({"tool": r["tool"], "domains": r["domains"].split(";"), "approved_data_class": r["approved_data_class"],
                        "ai_in_scope": r["ai_in_scope"] == "yes", "use_case": r["use_case"]})
    catalog_by_domain = {d: c for c in catalog for d in c["domains"]}
    feed = {r["domain"]: r["category"] for r in _read(data_dir / "known_ai_domains.csv")}
    blocklist = _read(data_dir / "blocklist.csv")

    proxy = []
    for i, r in enumerate(_read(data_dir / "proxy_log.csv"), 1):
        proxy.append({"sid": f"P{i}", "src": "proxy", "hour": int(r["hour"]), "user": r["user_id"], "dept": r["dept"],
                      "host": r["domain"], "domain": reg_domain(r["domain"]), "path": r["path"],
                      "out": int(r["bytes_out"]), "inn": int(r["bytes_in"]), "client": r["client_class"]})
    dns = []
    for i, r in enumerate(_read(data_dir / "dns_log.csv"), 1):
        dns.append({"sid": f"D{i}", "src": "dns", "hour": int(r["hour"]), "user": r["user_id"],
                    "dept": users[r["user_id"]]["dept"], "host": r["domain"], "domain": reg_domain(r["domain"]),
                    "path": None, "out": None, "inn": None, "client": None})
    truth, offnet = {}, []
    for r in _read(data_dir / "truth_sessions.csv"):
        t = {"label": r["true_label"], "out": int(r["true_bytes_out"]) if r["true_bytes_out"] else None,
             "user": r["user_id"] or None, "host": r["domain"] or None}
        truth[r["session_id"]] = t
        if r["true_label"] == "off_network":
            offnet.append({"sid": r["session_id"], "user": r["user_id"], "dept": users[r["user_id"]]["dept"],
                           "host": r["domain"], "domain": reg_domain(r["domain"]), "out": int(r["true_bytes_out"])})
    return {"depts": depts, "users": users, "catalog": catalog, "catalog_by_domain": catalog_by_domain, "feed": feed,
            "blocklist": blocklist, "proxy": proxy, "dns": dns, "truth": truth, "offnet": offnet,
            "weights": {k: v["weight"] for k, v in depts.items()}}


def visible_sessions(data: dict) -> list:
    """Every session that appears in some log: proxy rows then DNS rows."""
    return data["proxy"] + data["dns"]


def true_label(data: dict, s: dict) -> str:
    return data["truth"][s["sid"]]["label"]


def exposure_index(sessions: list, weights: dict) -> dict:
    """Exposure of one domain = (sum of bytes out x department weight) x distinct users, in
    MB x weight x users. It is a ranking index, not a measure of leaked data. Sessions need
    'out' (bytes), 'dept' and 'user'. Sessions with no byte count (DNS) add nothing."""
    wb = sum((s["out"] or 0) * weights[s["dept"]] for s in sessions)
    users = {s["user"] for s in sessions}
    mb = sum((s["out"] or 0) for s in sessions) / 1e6
    return {"weighted_mb": wb / 1e6, "mb_out": mb, "users": len(users), "sessions": len(sessions),
            "exposure": wb / 1e6 * len(users)}


def by_domain(sessions: list) -> dict:
    out: dict = defaultdict(list)
    for s in sessions:
        out[s["domain"]].append(s)
    return dict(out)


def fmt_int(n) -> str:
    return f"{int(n):,}"


# ---------------------------------------------------------------------------
# Step 1 measurements
# ---------------------------------------------------------------------------
def summarize(data: dict) -> dict:
    proxy, dns, truth = data["proxy"], data["dns"], data["truth"]
    vis = visible_sessions(data)
    labels = Counter(truth[s["sid"]]["label"] for s in vis)
    n_off = len(data["offnet"])

    # The report: top domains by hits in the proxy log
    dom = by_domain(proxy)
    ranked = sorted(dom, key=lambda d: (-len(dom[d]), d))
    report = []
    for rank, d in enumerate(ranked[:TOP_N_REPORT], 1):
        lab = Counter(truth[s["sid"]]["label"] for s in dom[d])
        main, main_n = lab.most_common(1)[0]
        report.append({"rank": rank, "domain": d, "hits": len(dom[d]), "users": len({s["user"] for s in dom[d]}),
                       "truth_main": main, "truth_main_share": main_n / len(dom[d])})

    # Unsanctioned AI domains: where do they sit in this report?
    unsanc_domains = sorted({s["domain"] for s in proxy if truth[s["sid"]]["label"] == "unsanctioned_ai"})
    rank_of = {d: i for i, d in enumerate(ranked, 1)}
    in_top = [d for d in unsanc_domains if rank_of[d] <= TOP_N_REPORT]
    best_rank = min(rank_of[d] for d in unsanc_domains)

    outside = [s for s in vis if truth[s["sid"]]["label"] in ("unsanctioned_ai", "embedded_ai_in_approved_saas")]
    users_outside = {s["user"] for s in outside}
    return {
        "proxy_rows": len(proxy), "dns_rows": len(dns), "users": len(data["users"]), "depts": len(data["depts"]),
        "proxy_domains": len(dom), "catalog_tools": len(data["catalog"]),
        "labels_visible": {k: labels.get(k, 0) for k in LABELS if k != "off_network"},
        "off_network": n_off, "report": report,
        "unsanctioned_domains": len(unsanc_domains), "unsanctioned_in_top": len(in_top), "unsanctioned_best_rank": best_rank,
        "unsanctioned_sessions_visible": labels["unsanctioned_ai"], "embedded_sessions_visible": labels["embedded_ai_in_approved_saas"],
        "outside_catalog_visible": len(outside), "outside_catalog_share": len(outside) / len(vis),
        "visible_total": len(vis), "users_outside": len(users_outside), "users_outside_share": len(users_outside) / len(data["users"]),
        "top_n_report": TOP_N_REPORT, "top_n_report_unsanctioned": sum(1 for r in report if r["truth_main"] == "unsanctioned_ai"),
    }


def write_outputs(s: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_01_top_domains.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "domain", "hits", "users", "truth_main"])
        for r in s["report"]:
            w.writerow([r["rank"], r["domain"], r["hits"], r["users"], r["truth_main"]])
    with open(OUT_DIR / "step_01_summary.json", "w") as f:
        json.dump({k: v for k, v in s.items() if k != "report"}, f, indent=2)


def main() -> None:
    data = load_all()
    s = summarize(data)
    write_outputs(s)
    print("STEP 1 - BEFORE SHADOWSCAN: what the proxy report shows today")
    print("Synthetic data from data/_generate.py. No real bank, product or log. No model is used.")
    print()
    print("THE EXTRACT")
    print(f"  Proxy log rows: {fmt_int(s['proxy_rows'])} (headquarters staff; domain, path, bytes out and in)")
    print(f"  DNS log rows:   {fmt_int(s['dns_rows'])} (branch staff; a domain name only, no path, no sizes)")
    print(f"  Staff: {s['users']} in {s['depts']} departments. Catalog: {s['catalog_tools']} approved tools. Distinct domains in the proxy log: {s['proxy_domains']}.")
    print()
    print(f"WHAT THE REPORT SHOWS: top {s['top_n_report']} domains by hits in the proxy log")
    print("  (the third column is the report; the last column is the truth, which the report does not have)")
    print(f"  {'rank':>4}  {'domain':<28} {'hits':>5} {'users':>5}  truth (main label of its sessions)")
    for r in s["report"]:
        print(f"  {r['rank']:>4}  {r['domain']:<28} {r['hits']:>5} {r['users']:>5}  {r['truth_main']}")
    print()
    print("AI-LOOKING TRAFFIC THAT NOBODY REVIEWS (truth labels; premise: no review process exists)")
    lv = s["labels_visible"]
    print(f"  Sessions visible in some log: {fmt_int(s['visible_total'])}")
    print(f"    sanctioned AI tools:                   {fmt_int(lv['sanctioned_ai'])}")
    print(f"    unsanctioned AI tools:                 {fmt_int(lv['unsanctioned_ai'])} across {s['unsanctioned_domains']} domains")
    print(f"    AI features inside approved SaaS:      {fmt_int(lv['embedded_ai_in_approved_saas'])}")
    print(f"    benign look-alike names:               {fmt_int(lv['benign_lookalike'])}")
    print(f"    everything else:                       {fmt_int(lv['other'])}")
    print(f"  AI use outside the catalog's scope that a log can see: {fmt_int(s['outside_catalog_visible'])} sessions ({s['outside_catalog_share']*100:.1f}% of visible sessions)")
    print(f"  Staff with at least one such session: {s['users_outside']} of {s['users']} ({s['users_outside_share']*100:.1f}%)")
    print(f"  Plus {s['off_network']} sessions on personal devices or off the network that no log shows (truth only).")
    print()
    print("RESULT")
    print(f"  Unsanctioned AI domains in the top {s['top_n_report']} of the hit-count report: {s['unsanctioned_in_top']} of {s['unsanctioned_domains']}; the best-ranked sits at #{s['unsanctioned_best_rank']}.")
    print(f"  The report gives a name and a count: no sign of what left, from which department, or whether the tool is approved.")


if __name__ == "__main__":
    main()
