"""Generates the ShadowScan synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes the CSV files next to this file)

What it builds (a modeled bank; nothing here is a real bank, product, vendor or log)
  dept_sensitivity.csv   10 departments and a data-sensitivity weight (1 to 5), an assumption.
  users.csv              520 staff: department and site (hq users go through the proxy,
                         branch users are only covered by DNS logging).
  sanctioned_catalog.csv 12 approved tools: 7 approved as AI tools, 5 approved as ordinary SaaS.
  known_ai_domains.csv   a feed of 40 domains that are known AI services, partly out of date.
  blocklist.csv          a static list of 15 entries (13 exact domains and 2 keyword rules).
  proxy_log.csv          15,000 sessions seen by the proxy (domain, path, bytes out and in).
  dns_log.csv            7,500 lookups seen by DNS only (no path, no sizes).
  truth_sessions.csv     the label of every log row, plus 600 sessions no log can see.

The truth is known because the data is synthetic: the generator decides which domain is an
unsanctioned AI tool, which approved-SaaS sessions are an AI feature, which look-alike names
are harmless and which sessions happen on a personal device. No model is used anywhere.
All domains end in .example and are invented.

Design parameters (traffic mix, popularity, byte sizes, path styles) were set from the design
reasoning in data/README.md BEFORE any result was computed. See that file for the seed note.
"""

from __future__ import annotations

import bisect
import csv
import math
import random
from pathlib import Path

SEED = 20261022
OUT = Path(__file__).parent

N_DAYS = 14
N_HOURS = N_DAYS * 24          # hour 0 = Monday 00:00 of the window; hours run 0 to 335
N_PROXY = 15000
N_DNS = 7500
N_OFFNET = 600
# Share of staff who use AI tools beyond the catalog at all (unsanctioned tools, AI features in
# approved SaaS, personal devices). Added after the first run of step 1 showed 93% of staff with at
# least one such session, which was not credible even for a dense test set. See data/README.md.
ADOPTER_SHARE = 0.4

# code, name, sensitivity weight (assumption of a modeled bank), staff, of which branch staff
DEPTS = [
    ("LEG", "Legal and Compliance", 5, 30, 2),
    ("CRD", "Credit Underwriting", 5, 60, 14),
    ("WLT", "Wealth Advisory", 4, 45, 24),
    ("FIN", "Finance and Treasury", 4, 55, 8),
    ("HRP", "People and HR", 4, 25, 2),
    ("FRD", "Fraud and Financial Crime", 4, 40, 4),
    ("ENG", "Technology and Engineering", 3, 110, 4),
    ("OPS", "Operations and Servicing", 3, 80, 48),
    ("MKT", "Marketing and Communications", 2, 40, 6),
    ("FAC", "Facilities and Procurement", 1, 35, 8),
]

# tool, registered domains, approved data class, ai_in_scope, use_case
CATALOG = [
    ("S-01 Enterprise chat assistant", ["assist-s01.example"], "Confidential", "yes", "chat"),
    ("S-02 Code assistant", ["codehelp-s02.example"], "Internal", "yes", "code"),
    ("S-03 Meeting notes summarizer", ["notes-s03.example"], "Internal", "yes", "transcribe"),
    ("S-04 Translation assistant", ["translate-s04.example"], "Public", "yes", "translate"),
    ("S-05 Document summarizer", ["summarize-s05.example"], "Confidential", "yes", "document"),
    ("S-06 Research assistant", ["research-s06.example"], "Public", "yes", "chat"),
    ("S-07 Knowledge base search", ["knowledge-s07.example"], "Confidential", "yes", "chat"),
    ("P-01 Document suite", ["docs-p01.example"], "Confidential", "no", "saas"),
    ("P-02 CRM", ["crm-p02.example"], "Confidential", "no", "saas"),
    ("P-03 Service desk", ["desk-p03.example"], "Internal", "no", "saas"),
    ("P-04 Meetings and video", ["meet-p04.example"], "Internal", "no", "saas"),
    ("P-05 HR portal", ["people-p05.example", "hrdocs-p05.example"], "Restricted", "no", "saas"),
]
# proxy sessions on each sanctioned AI tool (S-01..S-07), total 2,400
SANCTIONED_N = [600, 500, 400, 300, 250, 200, 150]
# per SaaS tool P-01..P-05: ordinary sessions, embedded-AI sessions, share of embedded sessions on
# a generation-style path (the rest use vendor-specific paths a path rule cannot match)
SAAS_ORD_N = [900, 800, 600, 400, 300]                 # 3,000
SAAS_EMB_N = [300, 280, 170, 100, 50]                  # 900
SAAS_EMB_MATCH = [0.8, 0.7, 0.6, 0.9, 0.5]
SAAS_EMB_OUT = [(14000, 1.0), (6000, 0.9), (4000, 0.9), (120000, 0.9), (25000, 0.9)]
# a benign path that looks like generation, per SaaS tool (share of its ordinary sessions)
SAAS_BENIGN_GEN = [("", 0.0), ("/reports/generate", 0.03), ("/queue/assist-requests", 0.04), ("", 0.0), ("", 0.0)]

# code, name, archetype, on blocklist (exact), in feed, proxy sessions, share of sessions on a
# generation-style (API) path. Popularity is set by hand and is independent of the blocklist,
# except that the oldest domains had a head start. Names with "ai" are the ones a keyword rule hits.
UNSANCTIONED = [
    ("u01", "talkwise", "chat", True, True, 260, 0.10),
    ("u02", "askpilot", "chat", True, True, 190, 0.10),
    ("u03", "quickai", "chat", True, True, 150, 0.10),
    ("u04", "chatnest", "chat", True, True, 120, 0.08),
    ("u05", "thinkdesk", "chat", False, True, 210, 0.10),
    ("u06", "wordsmith-ai", "chat", False, True, 140, 0.10),
    ("u07", "bridge-chat", "chat", False, False, 130, 0.60),
    ("u08", "ponder", "chat", False, False, 100, 0.04),
    ("u09", "pdfchat", "document", True, True, 80, 0.10),
    ("u10", "docsense", "document", True, True, 60, 0.10),
    ("u11", "briefreader", "document", False, True, 90, 0.10),
    ("u12", "contract-ai", "document", False, True, 70, 0.10),
    ("u13", "sheetmind", "document", False, True, 75, 0.10),
    ("u14", "notesum", "document", False, True, 55, 0.10),
    ("u15", "paperlens", "document", False, False, 70, 0.10),
    ("u16", "filesage", "document", False, False, 60, 0.10),
    ("u17", "codepal", "code", True, True, 170, 0.70),
    ("u18", "devassist-ai", "code", False, True, 150, 0.70),
    ("u19", "snippetgen", "code", False, True, 130, 0.70),
    ("u20", "refactorly", "code", False, False, 110, 0.70),
    ("u21", "typeahead", "code", False, False, 80, 0.08),
    ("u22", "pixelforge", "image", True, True, 50, 0.60),
    ("u23", "dreamcanvas-ai", "image", False, True, 45, 0.60),
    ("u24", "artspark", "image", False, True, 40, 0.60),
    ("u25", "visualyze", "image", False, False, 35, 0.60),
    ("u26", "voicenote", "transcribe", True, True, 70, 0.05),
    ("u27", "meetscribe", "transcribe", False, True, 80, 0.05),
    ("u28", "transcribo", "transcribe", False, True, 60, 0.05),
    ("u29", "callsummary-ai", "transcribe", False, True, 70, 0.05),
    ("u30", "dictate", "transcribe", False, False, 50, 0.05),
]
UNSANCTIONED_OVERRIDE = {
    # a paste-heavy chat tool used mostly by the review functions
    "u02": {"out": (9000, 1.3), "aff": {"LEG": 3.0, "CRD": 3.0, "FIN": 3.0}},
}
UNSANCTIONED_DNS_FACTOR = 0.4      # DNS lookups per proxy session (branch staff are a smaller group)
N_DEAD_FEED = 11                   # retired or renamed services still in the feed
N_DEAD_BLOCK = 4                   # retired services still on the blocklist

# benign look-alike names: every one contains "ai" and none is an AI service
LOOKALIKES = [
    ("airfare-desk", 140), ("maintenance-log", 120), ("daily-digest", 100), ("training-hub", 100),
    ("supply-chain-view", 80), ("mailroom-track", 70), ("paid-leave-calc", 60),
    ("rain-check-events", 50), ("waiver-claims", 40), ("retail-sync", 40),
]
LOOKALIKE_DNS_N = 350

GENERAL = ["newsdesk", "marketwire", "weatherbit", "mapview", "travelbook", "reference", "wikilike",
           "jobsboard", "videohub", "sportscore", "banknews", "statsportal", "forum", "shopmart",
           "recipes", "devdocs", "qanda", "learnhub", "exchangerates", "fxcharts"]
INTERNAL = ["intranet", "hrforms", "itsupport", "wikiint", "expenses", "directory"]
# name, sessions, share of sessions on a generation-style path (a reports page, not an AI tool)
REPORTS = [("reports", 150, 0.60), ("statements", 120, 0.12), ("invoicing", 80, 0.05)]
# name, sessions, share of sessions that are a large upload (a file share, not an AI tool)
FILESHARE = [("filevault", 150, 0.55), ("backupsync", 130, 0.12), ("shareit", 120, 0.05)]
GENERAL_N, INTERNAL_N = 3050, 1100
# DNS lookups by category
DNS_N = {"sanctioned": 650, "unsanctioned": 1200, "embedded": 300, "lookalike": LOOKALIKE_DNS_N,
         "saas": 1800, "general": 1900, "internal": 700, "reports": 300, "fileshare": 300}

CLIENT_VISIBLE = {"browser": 1.0, "script": 1.0, "desktop_app": 0.35, "mobile_mdm": 0.2}
CL_WEB = [("browser", 0.72), ("desktop_app", 0.14), ("mobile_mdm", 0.14)]
CL_DOC = [("browser", 0.85), ("desktop_app", 0.10), ("mobile_mdm", 0.05)]
CL_CODE = [("script", 0.45), ("desktop_app", 0.45), ("browser", 0.10)]
CL_IMG = [("browser", 0.85), ("desktop_app", 0.15)]
CL_VOICE = [("browser", 0.50), ("desktop_app", 0.30), ("mobile_mdm", 0.20)]
CL_SAAS = [("browser", 0.70), ("desktop_app", 0.20), ("mobile_mdm", 0.10)]
CL_GENERAL = [("browser", 0.80), ("desktop_app", 0.12), ("script", 0.04), ("mobile_mdm", 0.04)]
CL_SANCT = [("browser", 0.60), ("desktop_app", 0.25), ("script", 0.10), ("mobile_mdm", 0.05)]

ARCH = {
    "chat": dict(out=(2500, 0.9), inn=(18000, 0.9), clients=CL_WEB, pool_k=0.4,
                 main=["/chat", "/c/{id}", "/new", "/app", "/history", "/thread/{id}"],
                 alt=["/v1/chat/completions", "/v1/completions", "/api/generate"],
                 aff={"MKT": 1.5}, off=1.5, category="chat"),
    "document": dict(out=(600000, 1.0), inn=(12000, 0.8), clients=CL_DOC, pool_k=0.3,
                     main=["/upload", "/files", "/doc/{id}", "/workspace", "/chat-with-doc/{id}"],
                     alt=["/v1/summarize", "/api/documents/summarize"],
                     aff={"LEG": 3.0, "CRD": 3.0, "FIN": 3.0, "WLT": 2.5, "HRP": 2.5, "FRD": 2.0,
                          "OPS": 0.8, "ENG": 0.4, "MKT": 0.5, "FAC": 0.3}, off=1.5, category="document"),
    "code": dict(out=(30000, 0.9), inn=(6000, 0.8), clients=CL_CODE, pool_k=0.25,
                 main=["/ide/sync", "/v2/edit", "/telemetry/batch", "/session/{id}"],
                 alt=["/v1/completions", "/v1/chat/completions", "/v1/infer"],
                 aff={"ENG": 10.0, "FRD": 1.5, "LEG": 0.15, "CRD": 0.15, "WLT": 0.15, "FIN": 0.15,
                      "HRP": 0.15, "OPS": 0.15, "MKT": 0.15, "FAC": 0.15}, off=0.4, category="code"),
    "image": dict(out=(1200, 0.7), inn=(400000, 0.8), clients=CL_IMG, pool_k=0.35,
                  main=["/create", "/gallery", "/render/{id}", "/p/{id}"],
                  alt=["/generate", "/api/generate"],
                  aff={"MKT": 10.0, "FAC": 0.8, "LEG": 0.2, "CRD": 0.2, "WLT": 0.2, "FIN": 0.2,
                       "HRP": 0.2, "FRD": 0.2, "ENG": 0.2, "OPS": 0.2}, off=1.0, category="image"),
    "transcribe": dict(out=(2500000, 0.8), inn=(8000, 0.8), clients=CL_VOICE, pool_k=0.3,
                       main=["/upload", "/jobs/{id}", "/audio", "/library"],
                       alt=["/v1/transcribe/summarize"],
                       aff={"HRP": 3.0, "WLT": 3.0, "OPS": 2.5, "LEG": 2.5, "CRD": 1.5}, off=1.2,
                       category="transcribe"),
}


class Sampler:
    """Weighted draw from a list using only rng.random(), so results do not depend on the
    Python version's random.choices implementation."""

    def __init__(self, items, weights):
        self.items = list(items)
        self.cum = []
        acc = 0.0
        for w in weights:
            acc += w
            self.cum.append(acc)
        self.total = acc

    def draw(self, rng):
        i = bisect.bisect_left(self.cum, rng.random() * self.total)
        return self.items[min(i, len(self.items) - 1)]


def allocate(total, weights):
    """Split an integer total across weights by the largest-remainder method."""
    s = float(sum(weights))
    raw = [total * w / s for w in weights]
    base = [int(math.floor(r)) for r in raw]
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[: total - sum(base)]:
        base[i] += 1
    return base


def hour_weights(profile):
    w = []
    for h in range(N_HOURS):
        day, hod = divmod(h, 24)
        sat_sun = (day % 7) >= 5
        if profile == "work":
            if not sat_sun:
                wt = 10.0 if 9 <= hod < 17 else (3.0 if 7 <= hod < 9 or 17 <= hod < 20 else 0.4)
            else:
                wt = 1.0 if 10 <= hod < 18 else 0.3
        else:  # personal devices: evenings, Saturdays and Sundays
            if not sat_sun:
                wt = 6.0 if 18 <= hod < 23 else (2.0 if 9 <= hod < 18 else 0.5)
            else:
                wt = 5.0 if 9 <= hod < 22 else 0.5
        w.append(wt)
    return w


def make_spec(reg, out, inn, clients, main, alt=(), p_alt=0.0, prefixes=(("", 1.0),), alt_bytes=None):
    return {
        "reg": reg, "out": out, "inn": inn, "alt_bytes": alt_bytes,
        "clients": Sampler([c for c, _ in clients], [p for _, p in clients]),
        "prefix": Sampler([p for p, _ in prefixes], [w for _, w in prefixes]),
        "main": list(main), "alt": list(alt), "p_alt": p_alt,
    }


def draw_row(rng, spec):
    host = spec["prefix"].draw(rng) + spec["reg"]
    client = spec["clients"].draw(rng)
    use_alt = rng.random() < spec["p_alt"]
    pool = spec["alt"] if (use_alt and spec["alt"]) else spec["main"]
    path = pool[min(int(rng.random() * len(pool)), len(pool) - 1)]
    rid = int(rng.random() * 9000) + 1000
    path = path.replace("{id}", str(rid))
    visible = rng.random() < CLIENT_VISIBLE[client]
    out_p, in_p = spec["out"], spec["inn"]
    if use_alt and spec["alt_bytes"]:
        out_p, in_p = spec["alt_bytes"]
    out = max(80, int(rng.lognormvariate(math.log(out_p[0]), out_p[1])))
    inn = max(80, int(rng.lognormvariate(math.log(in_p[0]), in_p[1])))
    return {"host": host, "path": path if visible else "-", "out": out, "inn": inn, "client": client}


def build_users(rng):
    users = []
    n = 0
    for code, _name, _w, count, branch in DEPTS:
        for i in range(count):
            n += 1
            site = "branch" if i >= count - branch else "hq"
            users.append({"user_id": f"U{n:04d}", "dept": code, "site": site,
                          "prop": rng.lognormvariate(0.0, 0.7), "adopter": rng.random() < ADOPTER_SHARE})
    return users


def weighted_pool(rng, cands, wfun, k):
    keyed = []
    for u in cands:
        keyed.append((rng.random() ** (1.0 / wfun(u)), u["user_id"], u))
    keyed.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in keyed[:k]]


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        w.writerows(rows)


def main():
    rng = random.Random(SEED)
    work_hours = Sampler(range(N_HOURS), hour_weights("work"))
    home_hours = Sampler(range(N_HOURS), hour_weights("home"))

    users = build_users(rng)
    hq = [u for u in users if u["site"] == "hq"]
    branch = [u for u in users if u["site"] == "branch"]
    dept_of = {u["user_id"]: u["dept"] for u in users}

    # ---- name checks: the keyword rule must hit exactly the names meant to be hit ----
    unsanc_domains = {c: f"{n}-{c}.example" for c, n, *_ in UNSANCTIONED}
    ai_named = sorted(c for c, d in unsanc_domains.items() if "ai" in d[: -len(".example")])
    assert ai_named == ["u03", "u06", "u12", "u18", "u23", "u29"], ai_named

    # ---- catalog rows ----
    cat_rows = [(t, ";".join(d), cls, ai, uc) for t, d, cls, ai, uc in CATALOG]
    sanc_tools = [c for c in CATALOG if c[3] == "yes"]
    saas_tools = [c for c in CATALOG if c[3] == "no"]

    # ---- domain universes ----
    lookalike_domains = [f"{n}-l{i + 1:02d}.example" for i, (n, _) in enumerate(LOOKALIKES)]
    general_domains = [f"{n}-g{i + 1:02d}.example" for i, n in enumerate(GENERAL)]
    internal_domains = [f"{n}-i{i + 1:02d}.example" for i, n in enumerate(INTERNAL)]
    report_domains = [f"{n}-r{i + 1:02d}.example" for i, (n, _, _) in enumerate(REPORTS)]
    file_domains = [f"{n}-f{i + 1:02d}.example" for i, (n, _, _) in enumerate(FILESHARE)]
    dead_feed = [f"legacybot-d{i + 1:02d}.example" for i in range(N_DEAD_FEED)]
    dead_block = [f"oldchat-b{i + 1:02d}.example" for i in range(N_DEAD_BLOCK)]

    for d in general_domains + internal_domains + report_domains + file_domains + dead_feed + dead_block:
        assert "ai" not in d[: -len(".example")], d
    for d in [x for c in CATALOG for x in c[1]]:
        assert "ai" not in d[: -len(".example")], d
    for d in lookalike_domains:
        assert "ai" in d[: -len(".example")], d

    sessions = []      # every log-visible and hidden session, before ids are assigned
    # session: dict(src, hour, user, host, path, out, inn, client, label)

    def add(src, label, row, hour, user):
        sessions.append({"src": src, "label": label, "hour": hour, "user": user["user_id"], **row})

    def uniform_sampler(cands):
        return Sampler(cands, [1.0] * len(cands))

    # =====================================================================================
    # Proxy log (hq staff) and DNS log (branch staff) are produced by the same recipe
    # =====================================================================================
    for src, cands in (("proxy", hq), ("dns", branch)):
        is_dns = src == "dns"
        adopters = [u for u in cands if u["adopter"]]

        # --- unsanctioned AI ---
        if is_dns:
            counts = allocate(DNS_N["unsanctioned"], [u[5] for u in UNSANCTIONED])
        else:
            counts = [u[5] for u in UNSANCTIONED]
        for (code, name, arch, _bl, _feed, _n, p_api), n in zip(UNSANCTIONED, counts):
            a = ARCH[arch]
            ov = UNSANCTIONED_OVERRIDE.get(code, {})
            aff = dict(a["aff"])
            aff.update(ov.get("aff", {}))
            out = ov.get("out", a["out"])
            k = min(len(adopters), max(4 if is_dns else 5, int(round(n * a["pool_k"]))))
            pool = weighted_pool(rng, adopters, lambda u: u["prop"] * aff.get(u["dept"], 1.0), k)
            ps = Sampler(pool, [u["prop"] for u in pool])
            sp = make_spec(unsanc_domains[code], out, a["inn"], a["clients"], a["main"], a["alt"], p_api,
                           prefixes=(("", 0.75), ("api.", 0.25)))
            for _ in range(n):
                u = ps.draw(rng)
                add(src, "unsanctioned_ai", draw_row(rng, sp), work_hours.draw(rng), u)

        # --- sanctioned AI tools ---
        counts = SANCTIONED_N if not is_dns else allocate(DNS_N["sanctioned"], SANCTIONED_N)
        for (tool, doms, _cls, _ai, _uc), n in zip(sanc_tools, counts):
            sp = make_spec(doms[0], (2500, 0.9), (18000, 0.9), CL_SANCT, ["/chat", "/c/{id}", "/app"],
                           ["/v1/chat/completions", "/api/summarize"], 0.3,
                           prefixes=(("", 0.5), ("app.", 0.3), ("api.", 0.2)))
            ps = uniform_sampler(cands)
            for _ in range(n):
                add(src, "sanctioned_ai", draw_row(rng, sp), work_hours.draw(rng), ps.draw(rng))

        # --- approved SaaS: embedded AI features and ordinary use ---
        emb_counts = SAAS_EMB_N if not is_dns else allocate(DNS_N["embedded"], SAAS_EMB_N)
        ord_counts = SAAS_ORD_N if not is_dns else allocate(DNS_N["saas"], SAAS_ORD_N)
        saas_aff = {
            "P-01": {}, "P-02": {"OPS": 3.0, "WLT": 3.0, "FIN": 2.0, "ENG": 0.5, "FAC": 0.5, "MKT": 1.0},
            "P-03": {"OPS": 3.0, "ENG": 3.0}, "P-04": {}, "P-05": {"HRP": 6.0},
        }
        for i, (tool, doms, _cls, _ai, _uc) in enumerate(saas_tools):
            key = tool[:4]
            aff = saas_aff[key]
            w_emb = [u["prop"] * aff.get(u["dept"], 1.0) for u in adopters]
            w_ord = [aff.get(u["dept"], 1.0) for u in cands]
            es, os_ = Sampler(adopters, w_emb), Sampler(cands, w_ord)
            sp_emb = make_spec(doms[0], SAAS_EMB_OUT[i], (20000, 0.9), CL_SAAS,
                               ["/features/smart-reply", "/x/compose-magic", "/labs/quick-draft", "/v3/nova/run"],
                               ["/api/v2/assist/summarize", "/ai/draft", "/api/ai/suggest", "/assistant/complete"],
                               SAAS_EMB_MATCH[i], prefixes=(("", 0.5), ("app.", 0.3), ("api.", 0.2)))
            for _ in range(emb_counts[i]):
                add(src, "embedded_ai_in_approved_saas", draw_row(rng, sp_emb), work_hours.draw(rng), es.draw(rng))
            benign_path, benign_p = SAAS_BENIGN_GEN[i]
            alt = [benign_path] if benign_path else []
            sp_ord = make_spec(doms[0], (1800, 0.9), (40000, 1.0), CL_SAAS,
                               ["/records/{id}", "/api/v2/search", "/dashboard", "/calendar", "/files/{id}", "/settings"],
                               alt, benign_p, prefixes=(("", 0.5), ("app.", 0.3), ("api.", 0.2)))
            for _ in range(ord_counts[i]):
                add(src, "other", draw_row(rng, sp_ord), work_hours.draw(rng), os_.draw(rng))

        # --- benign look-alikes ---
        counts = [n for _, n in LOOKALIKES] if not is_dns else allocate(DNS_N["lookalike"], [n for _, n in LOOKALIKES])
        for dom, n in zip(lookalike_domains, counts):
            sp = make_spec(dom, (2000, 0.9), (45000, 1.0), CL_GENERAL,
                           ["/home", "/list", "/form/{id}", "/track/{id}", "/api/v1/items"])
            ps = uniform_sampler(cands)
            for _ in range(n):
                add(src, "benign_lookalike", draw_row(rng, sp), work_hours.draw(rng), ps.draw(rng))

        # --- other traffic: general web, internal portals, reports pages, file shares ---
        g_counts = allocate(GENERAL_N if not is_dns else DNS_N["general"], [1.0 / (i + 1) ** 0.8 for i in range(len(general_domains))])
        for dom, n in zip(general_domains, g_counts):
            sp = make_spec(dom, (900, 0.7), (120000, 1.0), CL_GENERAL, ["/", "/page/{id}", "/search", "/article/{id}"])
            ps = uniform_sampler(cands)
            for _ in range(n):
                add(src, "other", draw_row(rng, sp), work_hours.draw(rng), ps.draw(rng))
        i_counts = allocate(INTERNAL_N if not is_dns else DNS_N["internal"], [1.0 / (i + 1) ** 0.6 for i in range(len(internal_domains))])
        for dom, n in zip(internal_domains, i_counts):
            sp = make_spec(dom, (3000, 0.9), (60000, 0.9), CL_GENERAL, ["/home", "/forms/{id}", "/directory", "/tickets/{id}"])
            ps = uniform_sampler(cands)
            for _ in range(n):
                add(src, "other", draw_row(rng, sp), work_hours.draw(rng), ps.draw(rng))
        r_counts = allocate(DNS_N["reports"], [n for _, n, _ in REPORTS]) if is_dns else [n for _, n, _ in REPORTS]
        for dom, (_nm, _n, p_gen), n in zip(report_domains, REPORTS, r_counts):
            sp = make_spec(dom, (2000, 0.9), (150000, 0.9), CL_GENERAL, ["/reports/view/{id}", "/home", "/list"],
                           ["/reports/generate", "/statements/generate-pdf", "/invoice/generate"], p_gen,
                           alt_bytes=((1500, 0.7), (350000, 0.8)))
            ps = uniform_sampler(cands)
            for _ in range(n):
                add(src, "other", draw_row(rng, sp), work_hours.draw(rng), ps.draw(rng))
        f_counts = allocate(DNS_N["fileshare"], [n for _, n, _ in FILESHARE]) if is_dns else [n for _, n, _ in FILESHARE]
        for dom, (_nm, _n, p_big), n in zip(file_domains, FILESHARE, f_counts):
            sp = make_spec(dom, (6000, 1.0), (30000, 0.9), CL_GENERAL, ["/files", "/share/{id}", "/sync/status"],
                           ["/upload"], p_big, alt_bytes=((400000, 0.8), (5000, 0.7)))
            ps = uniform_sampler(cands)
            for _ in range(n):
                add(src, "other", draw_row(rng, sp), work_hours.draw(rng), ps.draw(rng))

    n_proxy = sum(1 for s in sessions if s["src"] == "proxy")
    n_dns = sum(1 for s in sessions if s["src"] == "dns")
    assert n_proxy == N_PROXY, n_proxy
    assert n_dns == N_DNS, n_dns

    # =====================================================================================
    # Off-network and personal-device sessions: in truth only, no log row exists
    # =====================================================================================
    all_adopters = [u for u in users if u["adopter"]]
    off_w = [u[5] * ARCH[u[2]]["off"] for u in UNSANCTIONED]
    off_dom = Sampler(range(len(UNSANCTIONED)), off_w)
    for _ in range(N_OFFNET):
        idx = off_dom.draw(rng)
        code, name, arch, _bl, _feed, _n, p_api = UNSANCTIONED[idx]
        a = ARCH[arch]
        ov = UNSANCTIONED_OVERRIDE.get(code, {})
        aff = dict(a["aff"])
        aff.update(ov.get("aff", {}))
        us = Sampler(all_adopters, [u["prop"] * aff.get(u["dept"], 1.0) for u in all_adopters])
        u = us.draw(rng)
        sp = make_spec(unsanc_domains[code], ov.get("out", a["out"]), a["inn"], a["clients"], a["main"], a["alt"], p_api)
        row = draw_row(rng, sp)
        row["hour"] = home_hours.draw(rng)
        sessions.append({"src": "off", "label": "off_network", "user": u["user_id"], **row})

    # =====================================================================================
    # Sort, assign ids, write
    # =====================================================================================
    proxy = sorted((s for s in sessions if s["src"] == "proxy"),
                   key=lambda s: (s["hour"], s["user"], s["host"], s["path"], s["out"], s["inn"]))
    dns = sorted((s for s in sessions if s["src"] == "dns"),
                 key=lambda s: (s["hour"], s["user"], s["host"], s["out"]))
    off = sorted((s for s in sessions if s["src"] == "off"),
                 key=lambda s: (s["user"], s["host"], s["out"], s["path"]))

    write_csv(OUT / "dept_sensitivity.csv", ["dept", "dept_name", "sensitivity_weight"],
              [(c, n, w) for c, n, w, _u, _b in DEPTS])
    write_csv(OUT / "users.csv", ["user_id", "dept", "site"], [(u["user_id"], u["dept"], u["site"]) for u in users])
    write_csv(OUT / "sanctioned_catalog.csv", ["tool", "domains", "approved_data_class", "ai_in_scope", "use_case"], cat_rows)

    feed = []
    for t, d, _cls, _ai, uc in CATALOG:
        if _ai == "yes":
            for x in d:
                feed.append((x, uc))
    for code, name, arch, _bl, in_feed, _n, _p in UNSANCTIONED:
        if in_feed:
            feed.append((unsanc_domains[code], ARCH[arch]["category"]))
    cats = ["chat", "document", "code", "image", "transcribe"]
    for i, d in enumerate(dead_feed):
        feed.append((d, cats[i % len(cats)]))
    feed.sort()
    write_csv(OUT / "known_ai_domains.csv", ["domain", "category"], feed)

    block = [(unsanc_domains[c], "domain") for c, _n, _a, bl, *_ in UNSANCTIONED if bl]
    block += [(d, "domain") for d in dead_block]
    block += [("ai", "keyword"), ("llm", "keyword")]
    write_csv(OUT / "blocklist.csv", ["entry", "match_type"], block)

    write_csv(OUT / "proxy_log.csv", ["hour", "user_id", "dept", "domain", "path", "bytes_out", "bytes_in", "client_class"],
              [(s["hour"], s["user"], dept_of[s["user"]], s["host"], s["path"], s["out"], s["inn"], s["client"]) for s in proxy])
    write_csv(OUT / "dns_log.csv", ["hour", "user_id", "domain"], [(s["hour"], s["user"], s["host"]) for s in dns])

    truth = []
    for i, s in enumerate(proxy, 1):
        truth.append((f"P{i}", s["label"], "", "", ""))
    for i, s in enumerate(dns, 1):
        truth.append((f"D{i}", s["label"], s["out"], "", ""))
    for i, s in enumerate(off, 1):
        truth.append((f"X{i}", s["label"], s["out"], s["user"], s["host"]))
    write_csv(OUT / "truth_sessions.csv", ["session_id", "true_label", "true_bytes_out", "user_id", "domain"], truth)

    print(f"proxy_log.csv {len(proxy)} rows; dns_log.csv {len(dns)} rows; truth_sessions.csv {len(truth)} rows "
          f"({len(off)} off-network); users {len(users)}")


if __name__ == "__main__":
    main()
