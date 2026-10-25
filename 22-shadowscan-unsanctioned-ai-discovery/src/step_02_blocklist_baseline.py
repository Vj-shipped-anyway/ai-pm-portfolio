"""Step 2 - The basic approach: a static blocklist of known AI domains.

The control today is a list. Exact entries match a host or any subdomain of it; keyword entries
match a substring of the host name (the rule teams add when the list goes stale). A hit is counted
in a report. This script runs the list over both logs and scores it against the truth labels: how
many of the hits are unsanctioned AI sessions, how many are false alarms, and how many unsanctioned
AI sessions the list never sees.

The list is a stand-in written for this exercise: 13 exact entries and 2 keyword entries. Nothing
here is a real product list. Bytes out in the log are the bytes the client sent, whether or not a block
page came back; this prototype does not model blocking. No model is used anywhere in this repo.

Run (from src/):
    python3 step_02_blocklist_baseline.py

Output: a readable summary, plus out/step_02_blocklist_hits.csv and out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

from step_01_status_quo import OUT_DIR, fmt_int, load_all, true_label, visible_sessions


def blocklist_match(host: str, blocklist: list):
    """The first matching entry for a host (exact entries first), or None."""
    name = ".".join(host.split(".")[:-1])          # host without the .example suffix
    for e in blocklist:
        if e["match_type"] == "domain" and (host == e["entry"] or host.endswith("." + e["entry"])):
            return e
    for e in blocklist:
        if e["match_type"] == "keyword" and e["entry"] in name:
            return e
    return None


def run_blocklist(data: dict) -> dict:
    """Apply the list to every log row. Returns {sid: entry} for the rows it hits."""
    hits = {}
    for s in visible_sessions(data):
        e = blocklist_match(s["host"], data["blocklist"])
        if e is not None:
            hits[s["sid"]] = e
    return hits


def summarize(data: dict) -> dict:
    vis = visible_sessions(data)
    hits = run_blocklist(data)
    lab = {s["sid"]: true_label(data, s) for s in vis}
    truth_unsanc = [s for s in vis if lab[s["sid"]] == "unsanctioned_ai"]
    hit_labels = Counter(lab[sid] for sid in hits)
    tp = hit_labels["unsanctioned_ai"]
    fp_look = hit_labels["benign_lookalike"]
    fp_other = sum(n for k, n in hit_labels.items() if k not in ("unsanctioned_ai", "benign_lookalike"))
    n_unsanc = len(truth_unsanc)

    by_entry: dict = {}
    for e in data["blocklist"]:
        by_entry[e["entry"]] = {"entry": e["entry"], "match_type": e["match_type"], "hits": 0, "tp": 0, "lookalike": 0}
    for sid, e in hits.items():
        row = by_entry[e["entry"]]
        row["hits"] += 1
        row["tp"] += lab[sid] == "unsanctioned_ai"
        row["lookalike"] += lab[sid] == "benign_lookalike"
    exact = [e for e in data["blocklist"] if e["match_type"] == "domain"]
    retired = [e["entry"] for e in exact if by_entry[e["entry"]]["hits"] == 0]

    kw_entries = [e["entry"] for e in data["blocklist"] if e["match_type"] == "keyword"]
    ai_domains = {s["domain"] for s in truth_unsanc}
    kw_name = {d for d in ai_domains if any(k in ".".join(d.split(".")[:-1]) for k in kw_entries)}
    kw_name_domains = len(kw_name)
    kw_also_exact = len(kw_name & {e["entry"] for e in exact})
    kw_hits = [sid for sid, e in hits.items() if e["match_type"] == "keyword"]
    kw_tp = sum(1 for sid in kw_hits if lab[sid] == "unsanctioned_ai")
    kw_look = sum(1 for sid in kw_hits if lab[sid] == "benign_lookalike")
    look_domains = {s["domain"] for s in vis if s["sid"] in hits and lab[s["sid"]] == "benign_lookalike"}

    per_src = {}
    for src in ("proxy", "dns"):
        t = [s for s in truth_unsanc if s["src"] == src]
        found = sum(1 for s in t if s["sid"] in hits)
        per_src[src] = {"unsanctioned": len(t), "found": found}

    return {
        "list_entries": len(data["blocklist"]), "exact_entries": len(exact),
        "keyword_entries": len(data["blocklist"]) - len(exact),
        "retired_entries": len(retired), "retired_names": retired,
        "hits": len(hits), "tp": tp, "fp_lookalike": fp_look, "fp_other": fp_other,
        "precision": tp / len(hits), "unsanctioned_visible": n_unsanc, "missed": n_unsanc - tp, "recall": tp / n_unsanc,
        "off_network": len(data["offnet"]),
        "live_exact_entries": len(exact) - len(retired), "keyword_name_domains": kw_name_domains, "keyword_also_exact": kw_also_exact, "ai_domains": len(ai_domains),
        "keyword_hits": len(kw_hits), "keyword_tp": kw_tp, "keyword_lookalike": kw_look, "lookalike_domains_hit": len(look_domains),
        "per_source": per_src, "by_entry": list(by_entry.values()),
        "hit_sids": sorted(hits),
    }


def write_outputs(s: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_02_blocklist_hits.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["entry", "match_type", "hits", "true_unsanctioned_ai", "benign_lookalike"])
        for r in sorted(s["by_entry"], key=lambda r: (-r["hits"], r["entry"])):
            w.writerow([r["entry"], r["match_type"], r["hits"], r["tp"], r["lookalike"]])
    with open(OUT_DIR / "step_02_summary.json", "w") as f:
        json.dump({k: v for k, v in s.items() if k not in ("hit_sids", "by_entry")}, f, indent=2)


def main() -> None:
    data = load_all()
    s = summarize(data)
    write_outputs(s)
    print("STEP 2 - THE BASIC APPROACH: a static blocklist")
    print("Synthetic data. The list is a stand-in written for this exercise. No model is used.")
    print()
    print(f"THE LIST: {s['list_entries']} entries = {s['exact_entries']} exact domains + {s['keyword_entries']} keyword rules")
    print(f"  {s['retired_entries']} of the {s['exact_entries']} exact entries are retired domains that match no traffic in either log; {s['live_exact_entries']} are live.")
    print()
    print("HITS BY ENTRY (entries with at least one hit)")
    print(f"  {'entry':<28} {'type':<8} {'hits':>5} {'true AI':>8} {'look-alike':>11}")
    for r in sorted(s["by_entry"], key=lambda r: (-r["hits"], r["entry"])):
        if r["hits"]:
            print(f"  {r['entry']:<28} {r['match_type']:<8} {r['hits']:>5} {r['tp']:>8} {r['lookalike']:>11}")
    print()
    print("RESULT (both logs, scored against truth_sessions.csv)")
    print(f"  Blocklist hits: {fmt_int(s['hits'])}")
    print(f"    unsanctioned AI sessions (correct hits): {fmt_int(s['tp'])} of {fmt_int(s['hits'])} hits ({s['precision']*100:.1f}% precision)")
    print(f"    benign look-alike sessions (false alarms): {fmt_int(s['fp_lookalike'])} on {s['lookalike_domains_hit']} look-alike domains ({fmt_int(s['keyword_lookalike'])} from the keyword rules)")
    print(f"    other false alarms: {s['fp_other']}")
    print(f"  Unsanctioned AI sessions visible in the logs: {fmt_int(s['unsanctioned_visible'])}")
    print(f"    found by the list: {fmt_int(s['tp'])} ({s['recall']*100:.1f}% recall); missed: {fmt_int(s['missed'])}")
    for src, label in (("proxy", "proxy log"), ("dns", "DNS log")):
        d = s["per_source"][src]
        print(f"    {label}: {fmt_int(d['found'])} of {fmt_int(d['unsanctioned'])} found")
    print(f"  {s['keyword_name_domains']} of the {s['ai_domains']} unsanctioned AI domains have a keyword in their name (also exact entries: {s['keyword_also_exact']}).")
    print(f"  Keyword rules: {fmt_int(s['keyword_hits'])} hits; {fmt_int(s['keyword_tp'])} were AI tools whose name contains the keyword, {fmt_int(s['keyword_lookalike'])} were look-alikes.")
    print(f"  Sessions on personal devices or off the network: {s['off_network']} (no log has them, so no list can hit them).")
    print("  A hit count says a domain was reached. It does not say how much data left, from which department, or whether the tool is approved.")


if __name__ == "__main__":
    main()
