"""Step 4 - With ShadowScan: classify every domain and path, rank by data exposure, score against truth.

ShadowScan reads the same logs the blocklist read and applies plain rules. There is no model: the
rules are a catalog lookup, a feed lookup, a path pattern and a byte-ratio test. Thresholds are
assumptions of a modeled bank, not advice.

RULES (a session is one log row)
  R1  host in the sanctioned catalog, approved as an AI tool                 -> sanctioned_ai
  R2  host in the catalog, approved as ordinary SaaS: if the proxy path looks like
      generation -> embedded_ai_in_approved_saas, else other
  R3  registered domain in the known-AI feed                                 -> unsanctioned_ai
  R4  any other domain that the heuristics discover: at least PROMOTE_MIN_FLAGGED of its proxy
      sessions, and at least PROMOTE_MIN_SHARE of all its proxy sessions, trip a generation-style
      path or an upload-heavy ratio                                          -> unsanctioned_ai
  R5  anything else                                                          -> other
DNS rows carry a name only, so R2 cannot fire on them; R1, R3 and R4 apply (R4 uses domains that
the proxy rows discovered).

EXPOSURE of a discovered domain = (sum of bytes out x department sensitivity weight, in MB) x distinct
users, from proxy rows only (DNS has no sizes). It is a ranking index, not a measure of leaked data.

NEXT ACTION (assumptions of a modeled bank): block when the domain is in the top BLOCK_TOP_RANK by
exposure and departments weighted 4 or 5 send at least BLOCK_MIN_SENS_SHARE of the bytes; sanction when
at least SANCTION_MIN_USERS staff use it and that share is below SANCTION_MAX_SENS_SHARE (broad,
low-sensitivity use: take it to intake and due diligence); otherwise coach.

Scoring uses data/truth_sessions.csv. The truth is known because the data is synthetic.

Run (from src/):
    python3 step_04_with_shadowscan.py

Output: a readable summary, plus out/step_04_exposure_ranking.csv, out/step_04_confusion.csv,
out/step_04_picks.txt (the sentences the app and the demo show for every pick) and out/step_04_summary.json.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict

from step_01_status_quo import (
    OUT_DIR, exposure_index, fmt_int, load_all, true_label, visible_sessions,
)
from step_02_blocklist_baseline import run_blocklist
from step_02_blocklist_baseline import summarize as summarize_step2

GEN_PATH = re.compile(r"/(?:v\d+/)?(?:chat/)?(?:generate|complet(?:e|ion|ions)|summari[sz]e|prompt|llm|infer(?:ence)?|assist(?:ant)?|rewrite|ai)\b", re.I)
RATIO_MIN_OUT = 100_000          # bytes out for an upload-heavy session
RATIO_MIN_X = 5                  # and at least this many times the bytes in
PROMOTE_MIN_FLAGGED = 3
PROMOTE_MIN_SHARE = 0.25
HIGH_SENS_WEIGHT = 4             # departments weighted 4 or 5 count as high sensitivity
BLOCK_TOP_RANK = 10
BLOCK_MIN_SENS_SHARE = 0.5
SANCTION_MIN_USERS = 25
SANCTION_MAX_SENS_SHARE = 0.3
MODELED_STAFF = 10_000           # assumption: size of a modeled bank
MODELED_OUTSIDE_SHARE = 0.15     # assumption: share of staff using AI outside the catalog
CLASSES = ["sanctioned_ai", "unsanctioned_ai", "embedded_ai_in_approved_saas", "other"]
TRUTH_ROWS = ["sanctioned_ai", "unsanctioned_ai", "embedded_ai_in_approved_saas", "benign_lookalike", "other"]
SELFTEST_PATHS = [("/v1/chat/completions", True), ("/api/ai/suggest", True), ("/statements/generate-pdf", True),
                  ("/assistant/complete", True), ("/chat", False), ("/airfare/list", False), ("/generator", False),
                  ("/records/1234", False), ("-", False)]


def path_flag(path) -> bool:
    return path is not None and path != "-" and GEN_PATH.search(path) is not None


def ratio_flag(out, inn) -> bool:
    return out is not None and out >= RATIO_MIN_OUT and out >= RATIO_MIN_X * inn


def rule_selftest() -> tuple:
    ok = sum(1 for p, want in SELFTEST_PATHS if path_flag(p) == want)
    return ok, len(SELFTEST_PATHS)


def discover_domains(data: dict) -> dict:
    """R4: domains outside the catalog and the feed whose proxy sessions trip a rule often enough."""
    st: dict = defaultdict(lambda: {"n": 0, "path": 0, "ratio": 0, "flagged": 0})
    for s in data["proxy"]:
        d = s["domain"]
        if d in data["catalog_by_domain"] or d in data["feed"]:
            continue
        p, r = path_flag(s["path"]), ratio_flag(s["out"], s["inn"])
        x = st[d]
        x["n"] += 1
        x["path"] += p
        x["ratio"] += r
        x["flagged"] += p or r
    found = {}
    for d, x in st.items():
        if x["flagged"] >= PROMOTE_MIN_FLAGGED and x["flagged"] / x["n"] >= PROMOTE_MIN_SHARE:
            if x["path"] >= PROMOTE_MIN_FLAGGED and x["ratio"] >= PROMOTE_MIN_FLAGGED:
                ev = "path+ratio"
            elif x["path"] >= PROMOTE_MIN_FLAGGED:
                ev = "path"
            elif x["ratio"] >= PROMOTE_MIN_FLAGGED:
                ev = "ratio"
            else:
                ev = "mixed"
            found[d] = {**x, "share": x["flagged"] / x["n"], "evidence": ev}
    return found


def classify(data: dict, discovered: dict) -> dict:
    """{sid: {'cls': ..., 'evidence': ...}} for every log row."""
    out = {}
    for s in visible_sessions(data):
        d = s["domain"]
        cat = data["catalog_by_domain"].get(d)
        if cat is not None:
            if cat["ai_in_scope"]:
                c, ev = "sanctioned_ai", "catalog"
            elif s["src"] == "proxy" and path_flag(s["path"]):
                c, ev = "embedded_ai_in_approved_saas", "path in approved SaaS"
            else:
                c, ev = "other", "catalog"
        elif d in data["feed"]:
            c, ev = "unsanctioned_ai", "feed"
        elif d in discovered:
            c, ev = "unsanctioned_ai", discovered[d]["evidence"]
        else:
            c, ev = "other", "none"
        out[s["sid"]] = {"cls": c, "evidence": ev}
    return out


def alternative(data: dict, category) -> str:
    """The sanctioned AI tool that does the same job, if the catalog has one."""
    for c in data["catalog"]:
        if c["ai_in_scope"] and c["use_case"] == category:
            return c["tool"]
    return ""


def build_items(data: dict, cls: dict) -> list:
    """One item per discovered domain (an unsanctioned AI tool or an AI feature in approved SaaS)."""
    w = data["weights"]
    sess: dict = defaultdict(list)
    for s in visible_sessions(data):
        c = cls[s["sid"]]["cls"]
        if c in ("unsanctioned_ai", "embedded_ai_in_approved_saas"):
            sess[(s["domain"], c)].append(s)
    items = []
    for (d, c), ss in sess.items():
        proxy = [s for s in ss if s["src"] == "proxy"]
        e = exposure_index(proxy, w)
        dept_wb: Counter = Counter()
        for s in proxy:
            dept_wb[s["dept"]] += s["out"] * w[s["dept"]]
        owner = sorted(dept_wb, key=lambda k: (-dept_wb[k], k))[0] if dept_wb else ""
        tot = sum(s["out"] for s in proxy)
        hi = sum(s["out"] for s in proxy if w[s["dept"]] >= HIGH_SENS_WEIGHT)
        evid = Counter(cls[s["sid"]]["evidence"] for s in ss).most_common(1)[0][0]
        category = data["feed"].get(d, "")
        items.append({"domain": d, "kind": c, "evidence": evid, "sessions": len(ss), "proxy_sessions": len(proxy),
                      "dns_sessions": len(ss) - len(proxy), "users": e["users"], "mb_out": e["mb_out"],
                      "weighted_mb": e["weighted_mb"], "exposure": e["exposure"], "owner": owner,
                      "sens_share": (hi / tot) if tot else 0.0, "category": category,
                      "tool": data["catalog_by_domain"][d]["tool"] if d in data["catalog_by_domain"] else ""})
    items.sort(key=lambda r: (-r["exposure"], r["domain"]))
    for i, r in enumerate(items, 1):
        r["rank"] = i
        alt = alternative(data, r["category"])
        owner_name = data["depts"][r["owner"]]["name"] if r["owner"] else "the owning department"
        emb = r["kind"] == "embedded_ai_in_approved_saas"
        if alt:
            alt_txt = f" to use {alt}."
        elif r["category"]:
            alt_txt = "; the catalog has no tool for this job."
        else:
            alt_txt = "; the feed gives no category, so no catalog tool is suggested."
        if r["rank"] <= BLOCK_TOP_RANK and r["sens_share"] >= BLOCK_MIN_SENS_SHARE:
            r["action"] = "block"
            r["next"] = (f"Switch off the AI feature in {r['tool']}; tell {owner_name}." if emb else
                         f"Block at proxy and DNS; tell {owner_name}" + alt_txt)
        elif r["users"] >= SANCTION_MIN_USERS and r["sens_share"] < SANCTION_MAX_SENS_SHARE:
            r["action"] = "sanction"
            r["next"] = ("Take the AI feature to intake (TierGate) and due diligence (VendorLens) before approving it." if emb else
                         "Open an intake (TierGate) and due diligence (VendorLens) before approving it.")
        else:
            r["action"] = "coach"
            r["next"] = (f"Coach {owner_name} on the approved scope." if emb else f"Coach {owner_name}" + alt_txt)
    return items


def confusion(data: dict, cls: dict) -> dict:
    m: dict = {t: Counter() for t in TRUTH_ROWS}
    for s in visible_sessions(data):
        m[true_label(data, s)][cls[s["sid"]]["cls"]] += 1
    return m


def prf(tp: int, fp: int, fn: int) -> dict:
    return {"tp": tp, "fp": fp, "fn": fn, "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0}


def analyze(data: dict | None = None) -> dict:
    data = data or load_all()
    vis = visible_sessions(data)
    truth = data["truth"]
    discovered = discover_domains(data)
    cls = classify(data, discovered)
    items = build_items(data, cls)
    conf = confusion(data, cls)
    lab = {s["sid"]: truth[s["sid"]]["label"] for s in vis}
    bl_hits = run_blocklist(data)
    s2 = summarize_step2(data)

    # --- per-class precision and recall over the log-visible sessions ---
    def score(cname):
        tp = sum(1 for s in vis if cls[s["sid"]]["cls"] == cname and lab[s["sid"]] == cname)
        fp = sum(1 for s in vis if cls[s["sid"]]["cls"] == cname and lab[s["sid"]] != cname)
        fn = sum(1 for s in vis if cls[s["sid"]]["cls"] != cname and lab[s["sid"]] == cname)
        return prf(tp, fp, fn)
    unsanc, emb, sanc = score("unsanctioned_ai"), score("embedded_ai_in_approved_saas"), score("sanctioned_ai")

    unsanc_vis = [s for s in vis if lab[s["sid"]] == "unsanctioned_ai"]
    found = [s for s in unsanc_vis if cls[s["sid"]]["cls"] == "unsanctioned_ai"]
    beyond = [s for s in found if s["sid"] not in bl_hits]
    only_bl = [s for s in unsanc_vis if s["sid"] in bl_hits and cls[s["sid"]]["cls"] != "unsanctioned_ai"]
    per_src = {}
    for src in ("proxy", "dns"):
        t = [s for s in unsanc_vis if s["src"] == src]
        per_src[src] = {"truth": len(t), "found": sum(1 for s in t if cls[s["sid"]]["cls"] == "unsanctioned_ai")}

    ev_tp = Counter(cls[s["sid"]]["evidence"] for s in found)

    # --- domain level ---
    true_domains = sorted({s["domain"] for s in unsanc_vis})
    found_domains = {s["domain"] for s in vis if cls[s["sid"]]["cls"] == "unsanctioned_ai"}
    missed_domains = [d for d in true_domains if d not in found_domains]
    bl_domains_hit = len({s["domain"] for s in unsanc_vis if s["sid"] in bl_hits})
    fp_domains = sorted(d for d in found_domains if d not in set(true_domains))
    new_domains = [d for d in true_domains if d not in data["feed"]]
    new_found = [d for d in new_domains if d in found_domains]

    # --- missed unsanctioned sessions: why ---
    miss = [s for s in unsanc_vis if cls[s["sid"]]["cls"] != "unsanctioned_ai"]
    reasons = Counter()
    for s in miss:
        if s["src"] == "dns":
            reasons["dns row on a domain the proxy rows did not discover (a name only)"] += 1
        elif s["path"] == "-":
            reasons["proxy row, path hidden (pinned app or mobile client), normal size"] += 1
        else:
            reasons["proxy row, path and size look ordinary"] += 1
    miss_by_domain = Counter(s["domain"] for s in miss)

    # --- embedded: why missed ---
    emb_vis = [s for s in vis if lab[s["sid"]] == "embedded_ai_in_approved_saas"]
    emb_miss = [s for s in emb_vis if cls[s["sid"]]["cls"] != "embedded_ai_in_approved_saas"]
    emb_reasons = Counter()
    for s in emb_miss:
        if s["src"] == "dns":
            emb_reasons["DNS row: the name of an approved product, no path"] += 1
        elif s["path"] == "-":
            emb_reasons["proxy row, path hidden"] += 1
        else:
            emb_reasons["proxy row, vendor-specific path a pattern cannot match"] += 1

    # --- false positives ---
    fp_rows = [s for s in vis if cls[s["sid"]]["cls"] == "unsanctioned_ai" and lab[s["sid"]] != "unsanctioned_ai"]
    fp_by_domain: dict = defaultdict(lambda: {"sessions": 0, "label": "", "evidence": ""})
    for s in fp_rows:
        x = fp_by_domain[s["domain"]]
        x["sessions"] += 1
        x["label"] = lab[s["sid"]]
        x["evidence"] = cls[s["sid"]]["evidence"]
    fp_emb = [s for s in vis if cls[s["sid"]]["cls"] == "embedded_ai_in_approved_saas" and lab[s["sid"]] != "embedded_ai_in_approved_saas"]
    fp_emb_by_domain = Counter(s["domain"] for s in fp_emb)

    # --- ranking vs truth ranking (same formula on truth-labeled proxy sessions) ---
    w = data["weights"]
    tsess: dict = defaultdict(list)
    for s in data["proxy"]:
        l = lab[s["sid"]]
        if l in ("unsanctioned_ai", "embedded_ai_in_approved_saas"):
            tsess[s["domain"]].append(s)
    texp = sorted(((d, exposure_index(ss, w)["exposure"]) for d, ss in tsess.items()), key=lambda t: (-t[1], t[0]))
    top_true = [d for d, _ in texp[:10]]
    top_found = [r["domain"] for r in items[:10]]
    rank_overlap = len(set(top_true) & set(top_found))
    top10_fp = [r["domain"] for r in items[:10] if r["domain"] in fp_domains]

    # --- dns bytes not in the exposure index ---
    dns_unmeasured = sum(truth[s["sid"]]["out"] for s in vis if s["src"] == "dns" and cls[s["sid"]]["cls"] in ("unsanctioned_ai", "embedded_ai_in_approved_saas"))
    measured = sum(r["mb_out"] for r in items)

    # --- utility ---
    users_unsanc = {s["user"] for s in unsanc_vis}
    u = len(users_unsanc)
    sota = s2["tp"] / u
    mine = unsanc["tp"] / u
    people = int(MODELED_STAFF * MODELED_OUTSIDE_SHARE)
    delta = mine - sota
    off = data["offnet"]
    action_counts = Counter(r["action"] for r in items)

    summary = {
        "visible_sessions": len(vis), "items": len(items), "discovered_by_heuristics": len(discovered),
        "unsanctioned": unsanc, "embedded": emb, "sanctioned": sanc,
        "blocklist_tp": s2["tp"], "blocklist_recall": s2["recall"], "blocklist_precision": s2["precision"],
        "blocklist_hits": s2["hits"], "unsanctioned_visible": len(unsanc_vis),
        "beyond_blocklist": len(beyond), "blocklist_only": len(only_bl), "per_source": per_src,
        "evidence_tp": dict(ev_tp), "blocklist_domains_hit": bl_domains_hit,
        "true_domains": len(true_domains), "found_domains": len(set(true_domains) & found_domains), "missed_domains": missed_domains,
        "fp_domains": fp_domains, "new_domains": len(new_domains), "new_found": len(new_found),
        "fp_sessions": len(fp_rows), "fp_emb_sessions": len(fp_emb), "miss_reasons": dict(reasons),
        "miss_sessions": len(miss), "emb_miss_reasons": dict(emb_reasons), "emb_visible": len(emb_vis),
        "rank_overlap": rank_overlap, "top10_fp": top10_fp,
        "dns_unmeasured_mb": dns_unmeasured / 1e6, "measured_mb": measured,
        "off_sessions": len(off), "off_share": len(off) / (len(off) + len(unsanc_vis)), "off_mb": sum(o["out"] for o in off) / 1e6,
        "users_unsanc": u, "sota_per_user": sota, "mine_per_user": mine, "delta_per_user": delta,
        "modeled_staff": MODELED_STAFF, "modeled_share": MODELED_OUTSIDE_SHARE, "people": people,
        "utility": delta * people, "actions": dict(action_counts),
        "selftest": rule_selftest(),
    }
    return {"data": data, "discovered": discovered, "cls": cls, "items": items, "confusion": conf, "summary": summary,
            "miss_by_domain": miss_by_domain, "fp_by_domain": dict(fp_by_domain), "fp_emb_by_domain": dict(fp_emb_by_domain),
            "bl_hits": bl_hits, "found_domains": found_domains, "missed_domains": missed_domains}


def _truth_kind(labels: Counter) -> str:
    for k in ("unsanctioned_ai", "embedded_ai_in_approved_saas", "benign_lookalike", "sanctioned_ai"):
        if labels.get(k):
            return k
    return "other"


def domain_card(a: dict, domain: str) -> dict:
    """Everything the app and the demo show for one domain: the blocklist verdict, the truth and the
    ShadowScan verdict. All values are computed here from the logs, the truth file and the classifier."""
    data, cls, bl = a["data"], a["cls"], a["bl_hits"]
    truth = data["truth"]
    sess = [s for s in visible_sessions(data) if s["domain"] == domain]
    labels = Counter(truth[s["sid"]]["label"] for s in sess)
    kind = _truth_kind(labels)
    target = sess if kind in ("benign_lookalike", "sanctioned_ai", "other") else [s for s in sess if truth[s["sid"]]["label"] == kind]
    proxy = [s for s in target if s["src"] == "proxy"]
    dns = [s for s in target if s["src"] == "dns"]
    off = [o for o in data["offnet"] if o["domain"] == domain]
    want = {"unsanctioned_ai": "unsanctioned_ai", "embedded_ai_in_approved_saas": "embedded_ai_in_approved_saas"}.get(kind)
    item = next((r for r in a["items"] if r["domain"] == domain), None)
    bl_entries = Counter(bl[s["sid"]]["entry"] + (" (exact entry)" if bl[s["sid"]]["match_type"] == "domain" else " (keyword rule)") for s in sess if s["sid"] in bl)
    owner_wb: Counter = Counter()
    for s in proxy:
        owner_wb[s["dept"]] += s["out"] * data["weights"][s["dept"]]
    return {
        "domain": domain, "truth_kind": kind, "tool": data["catalog_by_domain"][domain]["tool"] if domain in data["catalog_by_domain"] else "",
        "target_sessions": len(target), "proxy_sessions": len(proxy), "dns_sessions": len(dns), "off_sessions": len(off),
        "users": len({s["user"] for s in target}),
        "proxy_mb": sum(s["out"] for s in proxy) / 1e6, "dns_true_mb": sum(truth[s["sid"]]["out"] for s in dns) / 1e6,
        "off_mb": sum(o["out"] for o in off) / 1e6,
        "blocklist_hits": sum(1 for s in sess if s["sid"] in bl), "blocklist_hits_on_target": sum(1 for s in target if s["sid"] in bl),
        "blocklist_entries": dict(bl_entries), "in_feed": domain in data["feed"], "on_exact_list": any(
            e["match_type"] == "domain" and (domain == e["entry"]) for e in data["blocklist"]),
        "shadow_found": sum(1 for s in target if want and cls[s["sid"]]["cls"] == want),
        "shadow_classes": dict(Counter(cls[s["sid"]]["cls"] for s in target)),
        "shadow_flagged_sessions": sum(1 for s in sess if cls[s["sid"]]["cls"] in ("unsanctioned_ai", "embedded_ai_in_approved_saas")),
        "item": item, "top_depts": [(d, data["depts"][d]["name"]) for d, _ in owner_wb.most_common(3)],
        "reason_missed": ("proxy paths look ordinary and sizes are small, so no rule fires" if domain in a["missed_domains"] else ""),
    }


def dept_card(a: dict, dept: str) -> dict:
    data, cls, bl = a["data"], a["cls"], a["bl_hits"]
    truth = data["truth"]
    vis = [s for s in visible_sessions(data) if s["dept"] == dept]
    lab = {s["sid"]: truth[s["sid"]]["label"] for s in vis}
    un = [s for s in vis if lab[s["sid"]] == "unsanctioned_ai"]
    em = [s for s in vis if lab[s["sid"]] == "embedded_ai_in_approved_saas"]
    owned = [r for r in a["items"] if r["owner"] == dept]
    item_of = {r["domain"]: r for r in a["items"]}
    dept_wb: Counter = Counter()
    dept_mb: Counter = Counter()
    for s in vis:
        if s["src"] == "proxy" and cls[s["sid"]]["cls"] in ("unsanctioned_ai", "embedded_ai_in_approved_saas"):
            dept_wb[s["domain"]] += s["out"]
            dept_mb[s["domain"]] += s["out"]
    top_domains = [{"rank": item_of[d]["rank"], "domain": d, "mb": dept_mb[d] / 1e6, "action": item_of[d]["action"]}
                   for d, _ in sorted(dept_wb.items(), key=lambda t: (-t[1], t[0]))[:3]]
    off = [o for o in data["offnet"] if o["dept"] == dept]
    users = [u for u, v in data["users"].items() if v["dept"] == dept]
    return {
        "dept": dept, "name": data["depts"][dept]["name"], "weight": data["depts"][dept]["weight"], "staff": len(users),
        "unsanctioned_sessions": len(un), "blocklist_found": sum(1 for s in un if s["sid"] in bl),
        "shadow_found": sum(1 for s in un if cls[s["sid"]]["cls"] == "unsanctioned_ai"),
        "lookalike_false_alarms": sum(1 for s in vis if s["sid"] in bl and lab[s["sid"]] == "benign_lookalike"),
        "embedded_sessions": len(em), "embedded_found": sum(1 for s in em if cls[s["sid"]]["cls"] == "embedded_ai_in_approved_saas"),
        "off_sessions": len(off), "off_mb": sum(o["out"] for o in off) / 1e6,
        "staff_using": len({s["user"] for s in un + em}),
        "proxy_mb": sum(s["out"] for s in un if s["src"] == "proxy") / 1e6,
        "top_domains": top_domains,
        "owned": [{"rank": r["rank"], "domain": r["domain"], "action": r["action"], "exposure": r["exposure"]} for r in owned[:3]],
        "owned_count": len(owned), "owned_actions": dict(Counter(r["action"] for r in owned)),
    }


def scenario_options(a: dict) -> list:
    """The picker: the top-ranked discovered domains, a few edge cases, then each department.
    Each option is {'key', 'label', 'kind': 'domain'|'dept', 'target'}."""
    data, items = a["data"], a["items"]
    opts = []
    for r in items[:BLOCK_TOP_RANK]:
        opts.append({"kind": "domain", "target": r["domain"], "label": f"#{r['rank']} {r['domain']} - {r['action']}"})
    first_sanction = next((r for r in items if r["action"] == "sanction"), None)
    first_emb = next((r for r in items if r["kind"] == "embedded_ai_in_approved_saas"), None)
    for tag, r in (("sanction candidate", first_sanction), ("AI feature in approved SaaS", first_emb)):
        if r is not None:
            opts.append({"kind": "domain", "target": r["domain"], "label": f"#{r['rank']} {r['domain']} - {r['action']} ({tag})"})
    if a["missed_domains"]:
        d = max(a["missed_domains"], key=lambda x: (a["miss_by_domain"][x], x))
        opts.append({"kind": "domain", "target": d, "label": f"{d} - not found (known limit)"})
    look = Counter(s["domain"] for s in visible_sessions(data) if s["sid"] in a["bl_hits"] and data["truth"][s["sid"]]["label"] == "benign_lookalike")
    if look:
        d = sorted(look, key=lambda x: (-look[x], x))[0]
        opts.append({"kind": "domain", "target": d, "label": f"{d} - blocklist false alarm"})
    for code in data["depts"]:
        opts.append({"kind": "dept", "target": code, "label": f"Department: {data['depts'][code]['name']}"})
    for i, o in enumerate(opts):
        o["key"] = i
    return opts


def describe_option(a: dict, opt: dict) -> dict:
    """Wording for one picker option, shared by the Streamlit app and demo.html so both show the same
    sentences and the same numbers. Every figure comes from domain_card, dept_card or the summary."""
    data, s = a["data"], a["summary"]
    n_items = len(a["items"])
    if opt["kind"] == "dept":
        c = dept_card(a, opt["target"])
        un, bf, sf = c["unsanctioned_sessions"], c["blocklist_found"], c["shadow_found"]
        em, ef = c["embedded_sessions"], c["embedded_found"]
        tops = ", ".join(f"#{r['rank']} {r['domain']} {r['mb']:.1f} MB ({r['action']})" for r in c["top_domains"]) or "none"
        return {
            "title": f"Department: {c['name']}", "kind": "dept", "target": opt["target"],
            "meta": (f"{c['name']}: {c['staff']} staff, sensitivity weight {c['weight']} of 5. "
                     f"{c['staff_using']} of them used AI outside the catalog in the logs."),
            "before": ["The proxy report ranks domains by hits. It has no department view.",
                       "Nobody can say from it which department sends what to which tool."],
            "red": {"tag": "PARTLY SEEN", "tone": "bad", "lines": [
                f"The blocklist found {fmt_int(bf)} of {fmt_int(un)} unsanctioned AI sessions ({pct(bf / un) if un else '0.0%'}).",
                f"It found 0 of {fmt_int(em)} AI-feature sessions inside approved SaaS.",
                f"It raised {fmt_int(c['lookalike_false_alarms'])} false alarms on look-alike names for this department."]},
            "blue": [f"Truth (synthetic): {fmt_int(un)} unsanctioned AI sessions and {fmt_int(em)} AI-feature sessions in the logs, "
                     f"{c['proxy_mb']:.1f} MB out in the proxy log for the unsanctioned ones.",
                     f"{fmt_int(c['off_sessions'])} more sessions ({c['off_mb']:.1f} MB) on personal devices or off the network. No log shows them."],
            "green": {"tag": "FLAGGED", "tone": "good", "lines": [
                f"ShadowScan found {fmt_int(sf)} of {fmt_int(un)} unsanctioned AI sessions ({pct(sf / un) if un else '0.0%'}) and {fmt_int(ef)} of {fmt_int(em)} AI-feature sessions.",
                f"Where this department's bytes go, top three by size (rank, domain, MB out, action): {tops}.",
                f"It owns {c['owned_count']} of the {n_items} ranked items. Still invisible: {fmt_int(c['off_sessions'])} off-network sessions."],
                "next": "Take the top three to their owners; start with any marked block.", "note": ""},
            "card": c,
        }
    d = opt["target"]
    c = domain_card(a, d)
    it = c["item"]
    kind = c["truth_kind"]
    counts = Counter(s2["domain"] for s2 in data["proxy"])
    ranked = sorted(counts, key=lambda x: (-counts[x], x))
    hit_rank = ranked.index(d) + 1 if d in counts else None
    before = ([f"The proxy report lists {d}: {counts[d]} hits, rank #{hit_rank} of {len(counts)} domains by hits."]
              if hit_rank else [f"{d} does not appear in the proxy report."])
    before.append("It shows a name and a count. It does not show who sent what, how much, or whether the tool is approved.")
    ent = ", ".join(c["blocklist_entries"])
    tot_mb = c["proxy_mb"] + c["dns_true_mb"] + c["off_mb"]
    hidden_mb = c["dns_true_mb"] + c["off_mb"]
    if kind == "unsanctioned_ai":
        if c["blocklist_hits_on_target"]:
            red = {"tag": "HIT: A COUNT, NOTHING MORE", "tone": "bad", "lines": [
                f"{fmt_int(c['blocklist_hits_on_target'])} hits on the blocklist, matching {ent}.",
                f"The count does not say how much data left ({c['proxy_mb']:.1f} MB in the proxy log), from which department, or what to do about it."]}
        else:
            red = {"tag": "MISSED", "tone": "bad", "lines": [
                "0 hits. The domain is not on the list and no keyword rule matches its name.",
                ("The known-AI feed lists it, but nobody copied it to the blocklist." if c["in_feed"] else "It is in neither the known-AI feed nor the list.")]}
        blue = [f"Truth (synthetic): an AI tool nobody approved. {fmt_int(c['target_sessions'])} sessions in the logs ({fmt_int(c['proxy_sessions'])} proxy, {fmt_int(c['dns_sessions'])} DNS) by {c['users']} staff.",
                f"{c['proxy_mb']:.1f} MB out in the proxy log; {c['dns_true_mb']:.1f} MB more in DNS sessions that show no size."]
        if c["off_sessions"]:
            blue.append(f"{fmt_int(c['off_sessions'])} more sessions ({c['off_mb']:.1f} MB) on personal devices that no log shows.")
        if it is None:
            green = {"tag": "MISSED: KNOWN LIMIT", "tone": "warn", "lines": [
                f"Class: other. 0 of {fmt_int(c['target_sessions'])} sessions found.", "Why: " + c["reason_missed"] + "."],
                "next": "None. ShadowScan does not know this domain exists.",
                "note": "Known limit: a chat tool on ordinary paths with small payloads and a hidden path is invisible to these rules."}
        else:
            owner = data["depts"][it["owner"]]["name"]
            green = {"tag": "CAUGHT", "tone": "good", "lines": [
                f"Class: unsanctioned AI (evidence: {it['evidence']}). Found {fmt_int(c['shadow_found'])} of {fmt_int(c['target_sessions'])} sessions.",
                f"Exposure rank #{it['rank']} of {n_items}: index {it['exposure']:,.0f} = {it['weighted_mb']:,.1f} weighted MB x {it['users']} staff (proxy rows only).",
                f"Owner: {owner}. {it['sens_share']*100:.0f}% of the bytes come from departments weighted 4 or 5."],
                "next": f"{it['action'].upper()}: {it['next']}", "note": ""}
    elif kind == "embedded_ai_in_approved_saas":
        red = {"tag": "MISSED: LOOKS APPROVED", "tone": "bad", "lines": [
            f"0 hits. {c['tool']} is in the sanctioned catalog, so the domain looks approved.",
            "The AI feature inside it is invisible by domain."]}
        blue = [f"Truth (synthetic): the domain belongs to the approved product {c['tool']}, but {fmt_int(c['target_sessions'])} of its sessions use an AI feature ({fmt_int(c['proxy_sessions'])} proxy, {fmt_int(c['dns_sessions'])} DNS) by {c['users']} staff.",
                f"{c['proxy_mb']:.1f} MB out in the proxy log for those sessions."]
        owner = data["depts"][it["owner"]]["name"] if it else ""
        green = {"tag": "FLAGGED", "tone": "good", "lines": [
            f"Class: AI feature inside approved SaaS (evidence: {it['evidence']}). Found {fmt_int(c['shadow_found'])} of {fmt_int(c['target_sessions'])} sessions.",
            f"Exposure rank #{it['rank']} of {n_items}: index {it['exposure']:,.0f}. Owner: {owner}.",
            f"The other {fmt_int(c['target_sessions'] - c['shadow_found'])} sessions use a vendor-specific path or a DNS row, which a path pattern cannot read."],
            "next": f"{it['action'].upper()}: {it['next']}", "note": ""} if it else {"tag": "MISSED", "tone": "warn", "lines": ["Not found."], "next": "", "note": ""}
    elif kind == "benign_lookalike":
        if c["blocklist_hits"]:
            red = {"tag": "FALSE ALARM", "tone": "bad", "lines": [
                f"{fmt_int(c['blocklist_hits'])} hits, matching {ent}.",
                "The name contains the letters 'ai'. The site is not an AI service. Someone has to triage the hits by hand."]}
        else:
            red = {"tag": "NO HIT", "tone": "good", "lines": ["0 hits."]}
        blue = [f"Truth (synthetic): not an AI service. {fmt_int(c['target_sessions'])} sessions of ordinary use ({fmt_int(c['proxy_sessions'])} proxy, {fmt_int(c['dns_sessions'])} DNS) by {c['users']} staff."]
        green = {"tag": "IGNORED (CORRECT)", "tone": "good", "lines": [
            "Class: other. No catalog or feed match, and its paths and sizes are ordinary.",
            "ShadowScan does not read names, so the look-alike costs it nothing."],
            "next": "None.", "note": ""}
    else:
        red = {"tag": "NO HIT (CORRECT)", "tone": "good", "lines": ["0 hits. The list is right about this domain: it is an ordinary site."]}
        blue = [f"Truth (synthetic): not an AI tool. {fmt_int(c['target_sessions'])} sessions ({fmt_int(c['proxy_sessions'])} proxy, {fmt_int(c['dns_sessions'])} DNS) by {c['users']} staff."]
        if it is not None:
            owner = data["depts"][it["owner"]]["name"]
            green = {"tag": "WRONG: FALSE POSITIVE", "tone": "warn", "lines": [
                f"Class: unsanctioned AI (evidence: {it['evidence']}). Exposure rank #{it['rank']} of {n_items}: index {it['exposure']:,.0f}.",
                f"Owner: {owner}. Flagged {fmt_int(c['shadow_flagged_sessions'])} sessions by name once the rules fired on its proxy rows."],
                "next": f"{it['action'].upper()}: {it['next']}",
                "note": "False positive of the path and ratio rules. The action is a recommendation that a person reviews, not an automatic block."}
        else:
            green = {"tag": "IGNORED (CORRECT)", "tone": "good", "lines": ["Class: other."], "next": "None.", "note": ""}
    kind_words = {"unsanctioned_ai": "an unsanctioned AI tool", "embedded_ai_in_approved_saas": "an approved product with an AI feature",
                  "benign_lookalike": "a benign look-alike name", "sanctioned_ai": "a sanctioned AI tool", "other": "an ordinary site"}[kind]
    meta = (f"{d}: truth is {kind_words}. {fmt_int(c['target_sessions'])} sessions in the logs"
            + (f", {fmt_int(c['off_sessions'])} more off the network" if c["off_sessions"] else "")
            + (f"; {hidden_mb:.1f} of {tot_mb:.1f} MB out is invisible to the proxy." if kind == "unsanctioned_ai" and hidden_mb > 0 else "."))
    return {"title": d, "kind": "domain", "target": d, "meta": meta, "before": before, "red": red, "blue": blue, "green": green, "card": c}


def write_outputs(a: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_04_exposure_ranking.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "domain", "kind", "evidence", "proxy_sessions", "dns_sessions", "users", "mb_out", "exposure", "owner_dept", "high_sens_share", "action"])
        for r in a["items"]:
            w.writerow([r["rank"], r["domain"], r["kind"], r["evidence"], r["proxy_sessions"], r["dns_sessions"], r["users"],
                        f"{r['mb_out']:.3f}", f"{r['exposure']:.1f}", r["owner"], f"{r['sens_share']:.3f}", r["action"]])
    with open(OUT_DIR / "step_04_confusion.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["truth"] + CLASSES)
        for t in TRUTH_ROWS:
            w.writerow([t] + [a["confusion"][t].get(c, 0) for c in CLASSES])
    with open(OUT_DIR / "step_04_summary.json", "w") as f:
        json.dump(a["summary"], f, indent=2)
    # Every pick the app and the demo offer, with the sentences they show.
    with open(OUT_DIR / "step_04_picks.txt", "w", encoding="utf-8") as f:
        for o in scenario_options(a):
            d = describe_option(a, o)
            f.write(f"PICK {o['key']}: {o['label']}\n  {d['meta']}\n")
            for line in d["before"]:
                f.write(f"  Report: {line}\n")
            f.write(f"  Blocklist ({d['red']['tag']}): {' '.join(d['red']['lines'])}\n")
            f.write(f"  Truth: {' '.join(d['blue'])}\n")
            f.write(f"  ShadowScan ({d['green']['tag']}): {' '.join(d['green']['lines'])}\n")
            f.write(f"  Next action: {d['green']['next']} {d['green']['note']}\n\n")


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def main() -> None:
    a = analyze()
    write_outputs(a)
    s, data = a["summary"], a["data"]
    ok, n_st = s["selftest"]
    print("STEP 4 - WITH SHADOWSCAN: classify, rank by data exposure, score against truth")
    print("Synthetic data. Plain rules, no model. Thresholds are assumptions of a modeled bank, not advice.")
    print(f"Path rule self-check: {ok} of {n_st} sample paths behave as intended.")
    print()
    print("RULES (thresholds are assumptions of a modeled bank)")
    print("  R1  catalog domain, AI behavior reviewed                  -> sanctioned_ai")
    print("  R2  catalog domain, approved as ordinary software         -> embedded_ai_in_approved_saas if the proxy path looks like generation, else other")
    print("  R3  domain in the known-AI feed                           -> unsanctioned_ai")
    print(f"  R4  any other domain: a session is flagged by a generation-style path, or by at least {fmt_int(RATIO_MIN_OUT)} bytes out and {RATIO_MIN_X}x the bytes in;")
    print(f"      the domain is promoted when at least {PROMOTE_MIN_FLAGGED} of its proxy sessions, and at least {int(PROMOTE_MIN_SHARE*100)}% of them, are flagged -> unsanctioned_ai")
    print("  R5  anything else                                         -> other")
    print(f"  Next action: block = top {BLOCK_TOP_RANK} by exposure and at least {int(BLOCK_MIN_SENS_SHARE*100)}% of bytes from departments weighted {HIGH_SENS_WEIGHT} or 5;")
    print(f"               sanction = at least {SANCTION_MIN_USERS} staff and under {int(SANCTION_MAX_SENS_SHARE*100)}% of bytes from those departments; otherwise coach")
    print()
    print("DOMAINS THE HEURISTICS DISCOVER (not in the catalog or the feed)")
    print(f"  {'domain':<28} {'sessions':>8} {'flagged':>7} {'share':>6}  {'evidence':<11} truth")
    truth_domain = {}
    for sess in data["proxy"]:
        truth_domain.setdefault(sess["domain"], Counter())[true_label(data, sess)] += 1
    for d, x in sorted(a["discovered"].items(), key=lambda t: (-t[1]["flagged"], t[0])):
        tl = truth_domain[d].most_common(1)[0][0]
        print(f"  {d:<28} {x['n']:>8} {x['flagged']:>7} {x['share']*100:>5.0f}%  {x['evidence']:<11} {tl}")
    print()
    print(f"EXPOSURE RANKING (top 12 of {s['items']} discovered items; index = MB x weight x users, proxy rows only)")
    print(f"  {'#':>2} {'domain':<28} {'kind':<9} {'evidence':<11} {'users':>5} {'MB out':>8} {'exposure':>9} {'owner':<5} {'hi-sens':>7}  action")
    for r in a["items"][:12]:
        kind = "embedded" if r["kind"].startswith("embedded") else "tool"
        print(f"  {r['rank']:>2} {r['domain']:<28} {kind:<9} {r['evidence']:<11} {r['users']:>5} {r['mb_out']:>8.1f} {r['exposure']:>9.0f} {r['owner']:<5} {r['sens_share']*100:>6.0f}%  {r['action']}")
    ac = s["actions"]
    print(f"  Next actions across all {s['items']} items: block {ac.get('block', 0)}, sanction {ac.get('sanction', 0)}, coach {ac.get('coach', 0)}")
    print()
    print("WHAT THE APP AND THE DEMO SHOW (four of the picks; the same sentences, the same numbers)")
    opts = scenario_options(a)
    picks = [opts[0],
             next(o for o in opts if o["kind"] == "domain" and o["target"] in s["fp_domains"]),
             next(o for o in opts if "approved SaaS" in o["label"]),
             next(o for o in opts if "not found" in o["label"])]
    for o in picks:
        d = describe_option(a, o)
        print(f"  PICK: {o['label']}")
        print(f"    Report:      {d['before'][0]}")
        print(f"    Blocklist ({d['red']['tag']}): {' '.join(d['red']['lines'])}")
        print(f"    Blue card:   {' '.join(d['blue'])}")
        print(f"    ShadowScan ({d['green']['tag']}): {' '.join(d['green']['lines'])}")
        print(f"    Next action: {d['green']['next']}" + (f" Note: {d['green']['note']}" if d["green"]["note"] else ""))
    print()
    print("MEASURED AGAINST TRUTH (log-visible sessions)")
    u, e = s["unsanctioned"], s["embedded"]
    print(f"  Unsanctioned AI sessions: found {fmt_int(u['tp'])} of {fmt_int(s['unsanctioned_visible'])} (recall {pct(u['recall'])}); false positives {fmt_int(u['fp'])} (precision {pct(u['precision'])})")
    print(f"    the blocklist found {fmt_int(s['blocklist_tp'])} of {fmt_int(s['unsanctioned_visible'])} (recall {pct(s['blocklist_recall'])}); ShadowScan found {fmt_int(s['beyond_blocklist'])} that the list missed and lost {s['blocklist_only']} that the list hit")
    for src, label in (("proxy", "proxy log"), ("dns", "DNS log")):
        d = s["per_source"][src]
        print(f"    {label}: {fmt_int(d['found'])} of {fmt_int(d['truth'])} found")
    print(f"  Unsanctioned AI domains found: {s['found_domains']} of {s['true_domains']}; of the {s['new_domains']} in neither the feed nor the list, {s['new_found']} found")
    et = s["evidence_tp"]
    heur = sum(v for k, v in et.items() if k != "feed")
    print(f"  How the {fmt_int(u['tp'])} correct finds were made: {fmt_int(et.get('feed', 0))} by the feed, {fmt_int(heur)} by the path and ratio rules on domains the feed lacks")
    print(f"  The feed alone would find {fmt_int(et.get('feed', 0))} of {fmt_int(s['unsanctioned_visible'])} ({pct(et.get('feed', 0) / s['unsanctioned_visible'])}); it lists {s['true_domains'] - s['new_domains']} of the {s['true_domains']} domains by the generator's design, so that part is by construction")
    print(f"  Unsanctioned AI domains the blocklist hits at all: {s['blocklist_domains_hit']} of {s['true_domains']}")
    print(f"  Embedded AI in approved SaaS: found {fmt_int(e['tp'])} of {fmt_int(s['emb_visible'])} sessions (recall {pct(e['recall'])}); false positives {e['fp']} (precision {pct(e['precision'])}); the blocklist found 0")
    sa = s["sanctioned"]
    print(f"  Sanctioned AI sessions recognized: {fmt_int(sa['tp'])} of {fmt_int(sa['tp'] + sa['fn'])} (a catalog lookup, so by construction)")
    print(f"  Top 10 by exposure vs the truth ranking (same formula on truth-labeled proxy sessions): {s['rank_overlap']} of 10 shared")
    print()
    print("Confusion matrix (rows: truth; columns: what ShadowScan said)")
    print(f"  {'':<30}" + "".join(f"{c.replace('embedded_ai_in_approved_saas', 'embedded_ai'):>16}" for c in CLASSES))
    for t in TRUTH_ROWS:
        print(f"  {t:<30}" + "".join(f"{a['confusion'][t].get(c, 0):>16,}" for c in CLASSES))
    print()
    print("WHAT IT STILL GETS WRONG (known limit, left in on purpose)")
    print(f"  1. Off-network and personal-device sessions: {s['off_sessions']} sessions, {pct(s['off_share'])} of all unsanctioned AI sessions ({s['off_sessions']} of {fmt_int(s['off_sessions'] + s['unsanctioned_visible'])}), {s['off_mb']:.1f} MB out. No log has them, so no rule can find them.")
    print(f"  2. Unsanctioned AI sessions missed: {fmt_int(s['miss_sessions'])} of {fmt_int(s['unsanctioned_visible'])}. Why:")
    for k, v in sorted(s["miss_reasons"].items(), key=lambda t: (-t[1], t[0])):
        print(f"       {fmt_int(v):>6}  {k}")
    if a["missed_domains"]:
        print("     Domains never discovered:")
        for d in a["missed_domains"]:
            print(f"       {d:<28} {a['miss_by_domain'][d]:>4} sessions")
    print(f"  3. Embedded AI missed: {fmt_int(e['fn'])} of {fmt_int(s['emb_visible'])} sessions. Why:")
    for k, v in sorted(s["emb_miss_reasons"].items(), key=lambda t: (-t[1], t[0])):
        print(f"       {fmt_int(v):>6}  {k}")
    print(f"  4. False positives of the path and ratio heuristics: {fmt_int(s['fp_sessions'])} sessions on {len(s['fp_domains'])} benign domains were called unsanctioned AI:")
    for d in s["fp_domains"]:
        x = a["fp_by_domain"][d]
        rank = next(r["rank"] for r in a["items"] if r["domain"] == d)
        print(f"       {d:<28} {x['sessions']:>4} sessions  rule: {x['evidence']:<11} truth: {x['label']}  exposure rank #{rank}")
    print(f"     Benign sessions called embedded AI (an ordinary page whose path looks like generation): {s['fp_emb_sessions']}")
    for d, n in sorted(a["fp_emb_by_domain"].items(), key=lambda t: (-t[1], t[0])):
        print(f"       {d:<28} {n:>4} sessions")
    print(f"  5. Exposure leaves out DNS-only bytes: {s['dns_unmeasured_mb']:.1f} MB (truth) in discovered sessions that have no size in the log, against {s['measured_mb']:,.1f} MB measured.")
    print("  6. Content is not read. A tool on an ordinary-looking path with small payloads and a hidden path is invisible.")
    print()
    print("UTILITY (the delta is measured; the number of people is an assumption)")
    print(f"  Staff with at least one visible unsanctioned AI session: {s['users_unsanc']}")
    print(f"  Blocklist: {fmt_int(s['blocklist_tp'])} correct hits = {s['sota_per_user']:.3f} sessions found per such staff member")
    print(f"  ShadowScan: {fmt_int(u['tp'])} correct finds = {s['mine_per_user']:.3f} sessions found per such staff member")
    print(f"  Delta: {s['delta_per_user']:.3f} extra sessions found per staff member in the two-week extract")
    print(f"  Modeled people: {fmt_int(s['modeled_staff'])} staff x {int(s['modeled_share']*100)}% using AI outside the catalog = {fmt_int(s['people'])} (assumption, edit MODELED_STAFF and MODELED_OUTSIDE_SHARE)")
    print(f"  Utility = ({s['mine_per_user']:.3f} - {s['sota_per_user']:.3f}) x {fmt_int(s['people'])} = about {fmt_int(round(s['utility'], -1))} extra unsanctioned AI sessions brought into view per two-week window")
    for staff in (500, 1500, 3000):
        print(f"    sensitivity: {fmt_int(staff)} staff gives about {fmt_int(round(s['delta_per_user'] * staff, -1))}")


if __name__ == "__main__":
    main()
