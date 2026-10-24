"""tprm_gap_map: map a third-party risk guidance text to the evidence a bank would hold for an
AI-enabled vendor, and test candidate high-risk characteristics against a bank's own incident log.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 tprm_gap_map.py --demo
    python3 tprm_gap_map.py map                         the guidance map (data/guidance_map.csv)
    python3 tprm_gap_map.py tier VENDORS.csv [--incidents LOG.csv]
    python3 tprm_gap_map.py terms TEXT_FILE             count AI wording in a text you extracted

The tiering rules are plain rules. The vendors and incidents in data/ are synthetic.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
DD_ITEMS = ("soc_report", "insurance", "financial_ok", "key_personnel")
NAMED_ESSENTIAL = {"core_processing", "cloud_hosting", "compliance_tool", "fintech_partner"}   # the examples the text names
SHARE_HIGH = 30            # a vendor carrying this share of activity or more is treated as higher risk
CONCENTRATION_HIGH = 0.30  # share of an upstream group's activity that sits on one provider
AI_WORDS = re.compile(r"(?i:artificial intelligence|machine learning|generative|algorithm|large language|neural|\bLLM\b)|\bAI\b")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_vendors(path):
    out = []
    for r in read_csv(path):
        r["activity_share_pct"] = int(r["activity_share_pct"])
        for k in ("model_change_notice_days", "bank_data_retained_days"):
            r[k] = int(r[k]) if r.get(k, "") != "" else None
        out.append(r)
    return out


def upstream_shares(vendors):
    """{(service_type, provider): share of that service type's activity that sits on the provider}.
    Grouping by service type keeps model providers and cloud providers apart whatever they are called."""
    total, by = {}, {}
    for v in vendors:
        up = v.get("upstream_provider", "")
        if up:
            key = (v["service_type"], up)
            total[v["service_type"]] = total.get(v["service_type"], 0) + v["activity_share_pct"]
            by[key] = by.get(key, 0) + v["activity_share_pct"]
    return {key: by[key] / total[key[0]] for key in by}


def passes_questionnaire(v) -> bool:
    return all(v[k] == "yes" for k in DD_ITEMS)


def tier_text(v) -> str:
    """HIGH when the vendor is one of the services the text names, or carries a large share of activity."""
    return "HIGH" if v["service_type"] in NAMED_ESSENTIAL or v["activity_share_pct"] >= SHARE_HIGH else "LOWER"


def indicators(v, shares, concentration_high=CONCENTRATION_HIGH) -> dict:
    """AI-specific candidate characteristics. Only AI-enabled services carry them."""
    if v["service_type"] != "ai_enabled_service":
        return {}
    return {"concentrated_upstream": shares.get((v["service_type"], v["upstream_provider"]), 0) >= concentration_high,
            "no_model_change_notice": v["model_change_notice_days"] == 0,
            "trains_on_bank_data": v["trains_on_bank_data"] == "yes",
            "long_data_retention": (v["bank_data_retained_days"] or 0) >= 365}


def tier_ai(v, shares, concentration_high=CONCENTRATION_HIGH) -> str:
    return "HIGH" if tier_text(v) == "HIGH" or any(indicators(v, shares, concentration_high).values()) else "LOWER"


def material_vendors(incidents) -> set:
    return {r["vendor_id"] for r in incidents if r["material"] == "yes"}


def score(flagged: set, truth: set) -> dict:
    tp, fp, fn = len(flagged & truth), len(flagged - truth), len(truth - flagged)
    return {"flagged": len(flagged), "caught": tp, "missed": fn, "false_alarms": fp, "truth": len(truth)}


def run_map() -> int:
    for r in read_csv(os.path.join(DATA, "guidance_map.csv")):
        print(f"{r['stage']}  [{r['section_of_proposed_guidance']}]  text prompts it: {r['how_the_text_prompts_it']}")
        print(f"    AI-enabled vendor evidence: {r['evidence_for_an_ai_enabled_vendor']}")
        if r["note"]:
            print(f"    note: {r['note']}")
    return 0


def run_tier(vendors_path, incidents_path) -> int:
    try:
        vendors = load_vendors(vendors_path)
        incidents = read_csv(incidents_path) if incidents_path else None
    except (OSError, ValueError, KeyError) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    shares = upstream_shares(vendors)
    high_text = {v["vendor_id"] for v in vendors if tier_text(v) == "HIGH"}
    high_ai = {v["vendor_id"] for v in vendors if tier_ai(v, shares) == "HIGH"}
    print(f"vendors: {len(vendors)}   AI-enabled: {sum(1 for v in vendors if v['service_type'] == 'ai_enabled_service')}")
    print(f"HIGH under the text's examples: {len(high_text)}   with AI characteristics added: {len(high_ai)}")
    print("upstream concentration (share of the service type's activity): "
          + ", ".join(f"{k[1]} ({k[0]}) {s:.0%}" for k, s in sorted(shares.items())))
    unknown = [v for v in vendors if v["service_type"] == "ai_enabled_service" and not v["upstream_provider"]]
    if unknown:
        print(f"AI-enabled vendors with no upstream provider on file: {len(unknown)} (they cannot show as concentrated)")
    ind = {v["vendor_id"]: indicators(v, shares) for v in vendors}
    truth = material_vendors(incidents) if incidents else None
    print("candidate characteristic: vendors with it" + (", of which had a material incident" if truth is not None else ""))
    for name in ("concentrated_upstream", "no_model_change_notice", "trains_on_bank_data", "long_data_retention"):
        have = {vid for vid, d in ind.items() if d.get(name)}
        extra = f", {len(have & truth)}" if truth is not None else ""
        print(f"  {name}: {len(have)}{extra}")
    if truth is not None:
        s0, s1 = score(high_text, truth), score(high_ai, truth)
        print(f"material incident in the log: {len(truth)} vendors")
        print(f"text examples catch {s0['caught']} of {s0['truth']}; with AI characteristics {s1['caught']} of {s1['truth']}")
    return 0


def ai_term_hits(text: str) -> list:
    """Occurrences of AI wording: the long phrases in any case, the abbreviation AI only in capitals."""
    return [m.group(0) for m in AI_WORDS.finditer(text)]


def run_terms(path) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    print(f"{len(text.split())} words read; occurrences of AI wording: {len(ai_term_hits(text))}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tprm_gap_map")
    ap.add_argument("--demo", action="store_true", help="tier the bundled synthetic vendors against the bundled incident log")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("map", help="print the guidance map (data/guidance_map.csv)")
    t = sub.add_parser("tier", help="tier your vendors and, with a log, test the characteristics")
    t.add_argument("vendors", help="vendors CSV (columns in data/README.md)")
    t.add_argument("--incidents", help="incident log CSV (columns in data/README.md)")
    x = sub.add_parser("terms", help="count AI wording in a text file you extracted from the guidance")
    x.add_argument("file", help="plain-text file")
    a = ap.parse_args(argv)
    if a.demo:
        return run_tier(os.path.join(DATA, "vendors.csv"), os.path.join(DATA, "incident_log.csv"))
    if a.cmd == "map":
        return run_map()
    if a.cmd == "tier":
        return run_tier(a.vendors, a.incidents)
    if a.cmd == "terms":
        return run_terms(a.file)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
