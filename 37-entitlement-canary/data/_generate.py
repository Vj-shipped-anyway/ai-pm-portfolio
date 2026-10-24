"""Generate the synthetic data for project 37: a small document estate with nested groups, an access
spec for it, 96 relevance-eval queries, 50 pull requests that each change a retrieval system, and a
tiny worked example for the demo command.

Everything is seeded, so a rerun reproduces every file byte for byte. Nothing comes from any
employer, customer, bank or real system.

The truth is known because this script decides every access list. It also decides, for each pull
request, whether the planted change leaks: the label comes from the kind of change that was planted,
not from the canary rules in src/. Entitlement here is computed by walking the group tree DOWNWARD
from each ACL group; the resolver in src/entitlement_canary.py walks UPWARD from the user. Same rule,
two implementations.

Hard on purpose: delegation_inherit leaks for one user over one to four documents, so a pack of
sixty canaries will usually miss it; acl_grant, stricter_filter, per_user_cache and rerank_change
change what comes back without leaking; source_unindexed removes a source from the index, which
makes its canaries untestable.

Run (from data/):  python3 _generate.py
Writes:  access_base.json, doc_text.csv, queries.csv, entitlement_truth.csv, pr_cases.csv,
         pr_truth.csv, example_access.json, example_pack.csv, example_results.csv
"""
from __future__ import annotations

import csv
import json
import os
import random

SEED = 37
HERE = os.path.dirname(os.path.abspath(__file__))
rng = random.Random(SEED)

EDGES = [
    ("grp-all-staff", "grp-retail"), ("grp-all-staff", "grp-commercial"), ("grp-all-staff", "grp-risk"),
    ("grp-all-staff", "grp-compliance"), ("grp-all-staff", "grp-tech"), ("grp-all-staff", "grp-hr"),
    ("grp-all-staff", "grp-legal"), ("grp-retail", "grp-retail-cards"), ("grp-retail", "grp-retail-branch"),
    ("grp-retail-cards", "grp-retail-cards-fraud"), ("grp-commercial", "grp-commercial-credit"),
    ("grp-risk", "grp-risk-model"), ("grp-compliance", "grp-compliance-aml"), ("grp-legal", "grp-compliance-aml"),
    ("grp-tech", "grp-tech-platform"), ("grp-contractors", "grp-contractors-tech"), ("grp-contractors", "grp-contractors-ops"),
]
GROUPS = sorted({g for e in EDGES for g in e})
CHILDREN: dict = {}
for _p, _c in EDGES:
    CHILDREN.setdefault(_p, []).append(_c)


def _descendants(g: str) -> set:
    out, stack = set(), [g]
    while stack:
        x = stack.pop()
        if x not in out:
            out.add(x)
            stack.extend(CHILDREN.get(x, []))
    return out


DESC = {g: _descendants(g) for g in GROUPS}


def in_group(direct: list, g: str) -> bool:
    return bool(DESC.get(g, {g}) & set(direct))


def split_acl(acl: list) -> tuple:
    return [g for g in acl if not g.startswith("-")], [g[1:] for g in acl if g.startswith("-")]


def may_open(direct: list, acl: list) -> bool:
    allow, deny = split_acl(acl)
    return any(in_group(direct, g) for g in allow) and not any(in_group(direct, g) for g in deny)


# topic head, five aspects, home group, restricted sub-group
TOPICS = [
    ("Operational loss", ["rating heatmap", "escalation owner", "reporting cadence", "root cause", "recovery tracking"], "grp-risk", "grp-risk-model"),
    ("Card disputes", ["chargeback timeline", "merchant evidence", "provisional credit", "network rules", "customer notice"], "grp-retail", "grp-retail-cards"),
    ("Fraud alerts", ["rule tuning", "case triage", "false positive", "device signal", "analyst queue"], "grp-retail-cards", "grp-retail-cards-fraud"),
    ("Credit limits", ["annual review", "covenant check", "collateral value", "exception approval", "rating override"], "grp-commercial", "grp-commercial-credit"),
    ("Transaction monitoring", ["alert threshold", "scenario backtest", "case narrative", "filing decision", "source feed"], "grp-compliance", "grp-compliance-aml"),
    ("Access reviews", ["quarterly recertification", "privileged accounts", "leaver removal", "owner attestation", "exception log"], "grp-tech", "grp-tech-platform"),
    ("Change management", ["release window", "rollback plan", "emergency change", "approval record", "freeze period"], "grp-tech", "grp-tech-platform"),
    ("Complaint handling", ["intake form", "response deadline", "redress payment", "trend report", "escalation path"], "grp-retail", "grp-retail-branch"),
    ("Vendor onboarding", ["due diligence", "contract terms", "exit plan", "data sharing", "risk tiering"], "grp-commercial", "grp-commercial-credit"),
    ("Model validation", ["input data", "benchmark test", "limitation notice", "monitoring plan", "approval memo"], "grp-risk", "grp-risk-model"),
    ("Records retention", ["archive schedule", "legal hold", "destruction log", "storage location", "review cycle"], "grp-legal", "grp-legal"),
    ("Compensation review", ["band mapping", "exception request", "bonus pool", "calibration notes", "pay equity"], "grp-hr", "grp-hr"),
]
KINDS = ["FAQ", "Procedure", "Guidance", "Checklist", "Standard"]
ADJ = ["agreed", "revised", "current", "approved"]
STEPS = ["owner", "template", "approval", "evidence", "cadence", "escalation"]
RECORDS = ["process", "audit", "review", "status"]
VERBS = ["signed off", "confirmed", "reviewed"]
LEADS = ["how do we handle", "what is the rule for", "guidance on", "where is the procedure for"]
DENY_CHOICES = [("-grp-contractors", 0.55), ("-grp-contractors-tech", 0.65), ("-grp-contractors-ops", 0.75),
                ("-grp-retail-cards", 0.85), ("-grp-hr", 1.0)]
SOURCES = ["minutes"] * 3 + ["policy"] * 10 + ["tickets"] * 25 + ["wiki"] * 35 + ["dms"] * 47
EMPLOYEE_POOL = ["grp-retail-cards-fraud", "grp-retail-cards", "grp-retail-branch", "grp-commercial-credit", "grp-commercial",
                 "grp-risk-model", "grp-risk", "grp-compliance-aml", "grp-compliance", "grp-tech-platform", "grp-tech",
                 "grp-hr", "grp-legal"]


def write_csv(name: str, header: list, rows: list) -> None:
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_json(name: str, obj) -> None:
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")


# ------------------------------------------------------------------ users
users = [
    {"user_id": "U001", "role": "contractor", "direct_groups": ["grp-contractors-tech", "grp-tech"]},
    {"user_id": "U002", "role": "contractor", "direct_groups": ["grp-contractors-tech", "grp-tech"]},
    {"user_id": "U003", "role": "contractor", "direct_groups": ["grp-contractors-ops", "grp-retail"]},
    {"user_id": "U004", "role": "contractor", "direct_groups": ["grp-contractors-ops", "grp-commercial"]},
    {"user_id": "U005", "role": "contractor", "direct_groups": ["grp-contractors-ops", "grp-commercial"]},
    {"user_id": "U006", "role": "contractor", "direct_groups": ["grp-contractors-tech", "grp-retail"]},
]
pool = EMPLOYEE_POOL[:]
rng.shuffle(pool)
for i in range(7, 21):
    primary = pool[(i - 7) % len(pool)]
    groups = [primary]
    if rng.random() < 0.25:
        groups.append(rng.choice([g for g in EMPLOYEE_POOL if g != primary]))
    users.append({"user_id": "U%03d" % i, "role": "employee", "direct_groups": sorted(groups)})
direct = {u["user_id"]: u["direct_groups"] for u in users}

# ------------------------------------------------------------------ documents
raw = []
for head, aspects, home, leaf in TOPICS:
    for aspect in aspects:
        for kind in rng.sample(KINDS, 2):
            raw.append({"topic": head, "aspect": aspect, "kind": kind, "home": home, "leaf": leaf})
rng.shuffle(raw)
sources = SOURCES[:]
rng.shuffle(sources)
docs = []
for i, r in enumerate(raw):
    n = i + 1
    title = "%s: %s (%s) [DOC-%04d]" % (r["topic"], r["aspect"], r["kind"], n)
    x = rng.random()
    if x < 0.3:
        allow = ["grp-all-staff"]
    elif x < 0.6:
        allow = [r["home"]]
    elif x < 0.85:
        allow = [r["leaf"]]
    else:
        allow = [r["leaf"], "grp-compliance"]
    acl = sorted(set(allow))
    if rng.random() < 0.45:
        y = rng.random()
        acl.append(next(d for d, cut in DENY_CHOICES if y < cut))
    docs.append({"doc_id": "D%04d" % n, "title": title, "source": sources[i], "topic": r["topic"], "aspect": r["aspect"],
                 "kind": r["kind"], "acl": acl})

# ACL changes after the index was built: 12 documents gained a deny entry and 8 were drawn to lose an extra group
# (one of the 8 already had that group, so 19 documents end up with an index copy that differs)
has_deny = [d for d in docs if any(g.startswith("-") for g in d["acl"])]
no_deny = [d for d in docs if not any(g.startswith("-") for g in d["acl"])]
stale_deny = {d["doc_id"] for d in rng.sample(has_deny, 12)}
stale_group = {d["doc_id"]: rng.choice(["grp-hr", "grp-legal", "grp-compliance"]) for d in rng.sample(no_deny, 8)}
for d in docs:
    if d["doc_id"] in stale_deny:
        d["acl_at_index"] = [g for g in d["acl"] if not g.startswith("-")]
    elif d["doc_id"] in stale_group:
        d["acl_at_index"] = sorted(set(d["acl"]) | {stale_group[d["doc_id"]]})
    else:
        d["acl_at_index"] = list(d["acl"])

# texts, with a few cross-references that quote another document's title
by_topic: dict = {}
for d in docs:
    by_topic.setdefault(d["topic"], []).append(d)
xref = {d["doc_id"] for d in rng.sample(docs, 8)}
for d in docs:
    first = d["aspect"].split()[0]
    text = ("This %s sets out the %s guidance for %s cases. It covers %s, including the %s step and the %s record. "
            "Teams apply the %s procedure when %s is %s."
            % (d["kind"].lower(), rng.choice(ADJ), d["topic"].lower(), d["aspect"], rng.choice(STEPS), rng.choice(RECORDS),
               rng.choice(ADJ), first, rng.choice(VERBS)))
    if d["doc_id"] in xref:
        other = rng.choice([o for o in by_topic[d["topic"]] if o["doc_id"] != d["doc_id"]])
        text += " See also %s." % other["title"]
    d["text"] = text

access = {
    "groups": [{"parent": p, "child": c} for p, c in EDGES],
    "users": users,
    "documents": [{k: d[k] for k in ("doc_id", "title", "source", "topic", "acl", "acl_at_index")} for d in docs],
}
write_json("access_base.json", access)
write_csv("doc_text.csv", ["doc_id", "text"], [[d["doc_id"], d["text"]] for d in docs])

# ------------------------------------------------------------------ truth for the baseline
truth_rows = []
for u in users:
    ids = [d["doc_id"] for d in docs if may_open(direct[u["user_id"]], d["acl"])]
    truth_rows.append([u["user_id"], len(ids), ";".join(ids)])
write_csv("entitlement_truth.csv", ["user_id", "n_entitled", "entitled_doc_ids"], truth_rows)

# ------------------------------------------------------------------ relevance-eval queries
queries = []
for head, aspects, _home, _leaf in TOPICS:
    rel = ";".join(d["doc_id"] for d in docs if d["topic"] == head)
    for _ in range(8):
        queries.append([rng.choice(users)["user_id"], "%s %s %s" % (rng.choice(LEADS), head.lower(), rng.choice(aspects)), rel])
rng.shuffle(queries)
write_csv("queries.csv", ["query_id", "user_id", "text", "relevant_doc_ids"],
          [["Q%03d" % (i + 1), q[0], q[1], q[2]] for i, q in enumerate(queries)])

# ------------------------------------------------------------------ pull requests
stale_pairs = sum(1 for u in users for d in docs
                  if may_open(direct[u["user_id"]], d["acl_at_index"]) and not may_open(direct[u["user_id"]], d["acl"]))
flat_pairs = sum(1 for u in users for d in docs
                 if not may_open(direct[u["user_id"]], d["acl"])
                 and any(g in direct[u["user_id"]] for g in split_acl(d["acl"])[0])
                 and not any(g in direct[u["user_id"]] for g in split_acl(d["acl"])[1]))
assert stale_pairs >= 20 and flat_pairs >= 5, (stale_pairs, flat_pairs)


def delegation_triples(count: int) -> list:
    cands = []
    for g in GROUPS:
        scoped = [d for d in docs if g in split_acl(d["acl"])[0]]
        bosses = sorted(u["user_id"] for u in users if in_group(direct[u["user_id"]], g))
        if not scoped or not bosses:
            continue
        for u in users:
            uid = u["user_id"]
            if uid == bosses[0]:
                continue
            leak = [d for d in scoped if not may_open(direct[uid], d["acl"])]
            if 1 <= len(leak) <= 4:
                cands.append((len(leak), g, uid, bosses[0]))
    cands.sort()
    picked, used = [], set()
    for n, g, uid, boss in cands:
        if g not in used and uid not in {p["user"] for p in picked}:
            picked.append({"user": uid, "inherits_from": boss, "scope_group": g})
            used.add(g)
        if len(picked) == count:
            break
    assert len(picked) == count, "not enough narrow delegation cases"
    return picked


def grant_patch(k: int) -> list:
    pool_docs = [d for d in docs if d["acl"] != ["grp-all-staff"]]
    chosen = sorted(rng.sample(pool_docs, k), key=lambda d: d["doc_id"])
    return [{"doc_id": d["doc_id"], "acl": ["grp-all-staff"]} for d in chosen]


def jitter(i: int) -> dict:
    return [{}, {"top_k": 6}, {}, {"top_k": 4}, {}][i % 5]


plan = []   # (kind, truth_leaks, config, patch)
for i in range(5):
    plan.append(("deny_ignored", "yes", dict(jitter(i), deny="ignored"), []))
for i in range(5):
    plan.append(("flat_groups", "yes", dict(jitter(i + 1), groups="flat"), []))
for i in range(4):
    plan.append(("index_acl_copy", "yes", dict(jitter(i), acl_source="index_copy"), []))
for i in range(5):
    plan.append(("shared_cache", "yes", dict(jitter(i + 2), cache="shared"), []))
for srcs in (["wiki"], ["tickets"], ["policy"], ["minutes"], ["minutes", "tickets"]):
    plan.append(("new_source_no_acl", "yes", {"no_acl_sources": srcs}, []))
for t in delegation_triples(4):
    plan.append(("delegation_inherit", "yes", {"delegations": [t]}, []))
for srcs in (["minutes"], ["policy"], ["minutes", "policy"]):
    plan.append(("source_unindexed", "no", {"unindexed_sources": srcs}, []))
for cfg in ({"top_k": 8}, {"top_k": 3}, {"filter": "post"}, {"filter": "post", "top_k": 8}, {"top_k": 10}, {"top_k": 4}):
    plan.append(("rerank_change", "no", cfg, []))
for roles in (["tickets"], ["wiki"], ["dms"], ["tickets", "wiki"]):
    plan.append(("stricter_filter", "no", {"withhold_for_role": {"contractor": roles}}, []))
for i in range(4):
    plan.append(("per_user_cache", "no", dict(jitter(i + 3), cache="per_user"), []))
for _ in range(5):
    plan.append(("acl_grant", "no", {}, grant_patch(12)))
rng.shuffle(plan)

write_csv("pr_cases.csv", ["pr_id", "config_json", "access_patch_json"],
          [["PR-%03d" % (i + 1), json.dumps(p[2], sort_keys=True), json.dumps(p[3], sort_keys=True)] for i, p in enumerate(plan)])
write_csv("pr_truth.csv", ["pr_id", "change_kind", "truth_leaks"],
          [["PR-%03d" % (i + 1), p[0], p[1]] for i, p in enumerate(plan)])

# ------------------------------------------------------------------ the worked example behind --demo
ex_access = {
    "groups": [{"parent": "grp-all-staff", "child": "grp-eng"}, {"parent": "grp-all-staff", "child": "grp-hr"},
               {"parent": "grp-contractors", "child": "grp-contractors-eng"}],
    "users": [{"user_id": "U1", "direct_groups": ["grp-eng"]},
              {"user_id": "U2", "direct_groups": ["grp-contractors-eng", "grp-eng"]},
              {"user_id": "U3", "direct_groups": ["grp-hr"]}],
    "documents": [
        {"doc_id": "D1", "title": "Payments runbook [DOC-0001]", "source": "dms", "acl": ["grp-all-staff", "-grp-contractors"]},
        {"doc_id": "D2", "title": "Pay band guide [DOC-0002]", "source": "dms", "acl": ["grp-hr"]},
        {"doc_id": "D3", "title": "Onboarding guide [DOC-0003]", "source": "dms", "acl": ["grp-all-staff"]},
        {"doc_id": "D4", "title": "Vendor shortlist [DOC-0004]", "source": "dms", "acl": ["grp-eng", "-grp-contractors-eng"]},
        {"doc_id": "D5", "title": "Board minutes [DOC-0005]", "source": "minutes", "acl": ["grp-hr"]},
    ],
}
write_json("example_access.json", ex_access)
titles = {d["doc_id"]: d["title"] for d in ex_access["documents"]}
ex_pack = [("CAN-001", "U2", "D1", "nested_deny", "dms", "U3"), ("CAN-002", "U2", "D4", "direct_deny", "dms", "U1"),
           ("CAN-003", "U1", "D2", "ordinary", "dms", "U3"), ("CAN-004", "U1", "D5", "ordinary", "minutes", "U3"),
           ("CAN-005", "U2", "D2", "ordinary", "dms", "U3"), ("CAN-006", "U2", "D5", "ordinary", "minutes", "U3")]
write_csv("example_pack.csv", ["canary_id", "user_id", "doc_id", "query", "stratum", "source", "prime_user"],
          [[c, u, d, titles[d], s, src, p] for c, u, d, s, src, p in ex_pack])
write_csv("example_results.csv", ["canary_id", "returned_doc_ids", "primed", "control_returned_doc_ids"],
          [["CAN-001", "D1;D3", "yes", "D1;D3"], ["CAN-002", "D3", "yes", "D4;D3"], ["CAN-003", "D3", "yes", "D2;D3"],
           ["CAN-004", "D3", "yes", "D5;D3"], ["CAN-005", "D3", "yes", "D2;D3"], ["CAN-006", "D3", "yes", "D5;D3"]])
print("wrote %d documents, %d users, %d pull requests; stale pairs %d, flat-group pairs %d"
      % (len(docs), len(users), len(plan), stale_pairs, flat_pairs))
