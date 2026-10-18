"""Step 4 - The fix: CorpusGate.

Five parts, all plain rules, no model:

  1. Effective ACL      resolve the user's groups through the whole group tree (nested groups) and honor
                        explicit deny entries, instead of comparing direct groups.
  2. ACL drift check    compare the ACL copy stored in the index with the source ACL as of the last sync,
                        and filter on the source ACL, not on the stale copy.
  3. Pre-filter         remove documents the asker may not read BEFORE ranking, so unreadable documents never
                        take one of the K slots. (A post-filter is scored for comparison.)
  4. Ingestion scan     regex scan for personal data when a document is indexed. Policy (an assumption of the
                        modeled bank): ssn_like and account_like -> quarantine (not indexed); email_like -> redact.
  5. Canary pack        a fixed set of user and not-entitled-document pairs, each with a query built to retrieve
                        exactly that document. Reported as leaked / total.

The retriever is a stub (TF-IDF, not a model). No model is used anywhere in this repo.

Known limit, left in on purpose and printed: personal data in a format the patterns do not match, and the
ACL-sync window (changes after the last sync are invisible to the gate).

Run (from src/):
    python3 step_04_with_corpusgate.py

Output: a readable summary, plus CSVs and out/step_04_summary.json.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from statistics import mean

from step_01_no_access_control import (
    K, OUT_DIR, SYNC_AT, build_index, effective_groups, leak_stats, load_all, pct, rank_all,
    split_list, status_quo, _is_revoke,
)
from step_02_relevance_only_eval import relevance_eval
from step_03_deficiencies_exposed import (
    allowed_by_acl, allowed_by_label, open_to_all_staff, readable_recall, run_canaries, run_system,
    scan_text, PII_PATTERNS,
)

ASSISTANT_USERS = 1200                       # modeled: assumption, not a statistic
QUARANTINE_KINDS = ("ssn_like", "account_like")
REDACT_KINDS = ("email_like",)
STORY_ORDER = ["leak_restricted", "leak_confidential", "stale_revoked", "stale_granted", "flat_denied",
               "flat_allowed", "label_mislabeled", "label_over", "pii_ssn", "pii_account", "pii_email",
               "pii_missed", "sync_window", "mostly_withheld", "clean"]
STORY_TITLES = {
    "leak_restricted": "a restricted document leaks into the top 5",
    "leak_confidential": "another team's confidential document leaks",
    "stale_revoked": "access was revoked after indexing, the index copy still allows it",
    "stale_granted": "access was granted after indexing, the index copy hides it",
    "flat_denied": "entitled through a parent group, the flat check blocks it",
    "flat_allowed": "a contractor passes the flat check, a parent-group deny blocks them",
    "label_mislabeled": "a mislabeled document slips past the label filter",
    "label_over": "an entitled confidential document is blocked by the label filter",
    "pii_ssn": "SSN-like number in a document open to all staff",
    "pii_account": "account number in a document open to all staff",
    "pii_email": "e-mail address redacted before indexing",
    "pii_missed": "personal data in an unusual format passes the scan (known limit)",
    "sync_window": "access revoked after the last sync (known limit)",
    "mostly_withheld": "most of the best matches are withheld",
    "clean": "nothing to catch, results unchanged",
}


# ---------------------------------------------------------------------------
# Part 2: source ACL as of the last sync, and drift against the index copy
# ---------------------------------------------------------------------------
def synced_acls(data: dict, at: str = SYNC_AT) -> dict:
    """doc_id -> ACL as the source stood at `at`: start from the index copy, replay the change log up to `at`."""
    acl = {d: list(r["acl_index"]) for d, r in data["docs"].items()}
    for c in sorted(data["changes"], key=lambda c: (c["changed_at"], c["change_id"])):
        if c["changed_at"] <= at:
            acl[c["doc_id"]] = split_list(c["to_acl"])
    return acl


def acl_drift(data: dict, synced: dict) -> list:
    out = []
    for d, r in data["docs"].items():
        if set(r["acl_index"]) != set(synced[d]):
            out.append({"doc_id": d, "index_acl": ";".join(r["acl_index"]), "source_acl": ";".join(synced[d])})
    return out


# ---------------------------------------------------------------------------
# Part 4: ingestion scan, quarantine, redaction
# ---------------------------------------------------------------------------
def redact(text: str, kinds=REDACT_KINDS) -> str:
    for kind, rx in PII_PATTERNS:
        if kind in kinds:
            text = rx.sub("[REDACTED]", text)
    return text


def ingest_scan(data: dict, policy: str = "quarantine") -> dict:
    """Scan every document once. Returns per-document action and the text that would be indexed.
    policy "quarantine": ssn_like and account_like documents are not indexed, email_like values are redacted.
    policy "redact_all": no document is held back; every matched value is redacted (a cheaper variant)."""
    rows, texts = {}, {}
    for d, r in data["docs"].items():
        hits = scan_text(r["text"])
        kinds = sorted({k for k, _ in hits})
        if policy == "quarantine" and any(k in QUARANTINE_KINDS for k in kinds):
            action = "quarantine"
        elif kinds:
            action = "redact"
        else:
            action = "index"
        rows[d] = {"doc_id": d, "kinds": kinds, "action": action, "pii_truth": r["pii_truth"],
                   "found": r["pii_truth"] in kinds}
        if action != "quarantine":
            body = redact(r["text"], tuple(k for k, _ in PII_PATTERNS) if policy == "redact_all" else REDACT_KINDS) if action == "redact" else r["text"]
            texts[d] = r["title"] + " " + body
    return {"rows": rows, "texts": texts}


# ---------------------------------------------------------------------------
# Explanations (used by the app and the demo)
# ---------------------------------------------------------------------------
def group_path(data: dict, user_id: str, target: str) -> list:
    """Shortest chain of groups from one of the user's direct groups up to `target`."""
    start = sorted(data["users"][user_id]["direct"])
    prev, queue, seen = {}, list(start), set(start)
    while queue:
        g = queue.pop(0)
        if g == target:
            path = [g]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return list(reversed(path))
        for p in sorted(data["parents"].get(g, ())):
            if p not in seen:
                seen.add(p)
                prev[p] = g
                queue.append(p)
    return []


def explain_access(data: dict, user_id: str, acl: list) -> dict:
    """Why the effective-ACL rule allows or denies this user. Returns {allowed, why}."""
    eff = effective_groups(data, user_id)
    allow = [g for g in acl if not g.startswith("-")]
    deny = [g[1:] for g in acl if g.startswith("-")]
    hit_deny = sorted(eff & set(deny))
    if hit_deny:
        return {"allowed": False, "why": f"denied: the user is in {hit_deny[0]} ({' > '.join(group_path(data, user_id, hit_deny[0]))}) and the ACL denies it"}
    hit = sorted(eff & set(allow))
    if hit:
        return {"allowed": True, "why": f"allowed: {' > '.join(group_path(data, user_id, hit[0]))}"}
    return {"allowed": False, "why": "denied: none of the user's groups is on the ACL (" + ", ".join(allow) + ")"}


# ---------------------------------------------------------------------------
# The analysis (everything the steps, the app and the demo read)
# ---------------------------------------------------------------------------
def analyze(data: dict = None) -> dict:
    data = data or load_all()
    sq = status_quo(data)
    docs, truth, queries = data["docs"], data["truth"], data["queries"]
    n_users, n_docs, n_q = len(data["users"]), len(docs), len(queries)
    n_pairs = n_users * n_docs
    rank0 = sq["rank"]

    synced = synced_acls(data)
    drift = acl_drift(data, synced)
    scan = ingest_scan(data)
    gate_index = build_index(scan["texts"])
    rank_gate = rank_all(data, gate_index)

    allowed_sync = allowed_by_acl(data, synced, nested=True)
    allowed_now = allowed_by_acl(data, {d: docs[d]["acl_now"] for d in docs}, nested=True)
    allowed_idx = allowed_by_acl(data, {d: docs[d]["acl_index"] for d in docs}, nested=True)
    allowed_flat = allowed_by_acl(data, {d: docs[d]["acl_now"] for d in docs}, nested=False)
    allowed_lab = allowed_by_label(data)

    res0 = sq["results_by_query"]
    res_post = run_system(data, rank0, allowed_sync, "post")
    res_pre = run_system(data, rank0, allowed_sync, "pre")
    res_cg = run_system(data, rank_gate, allowed_sync, "pre")
    res_truth = run_system(data, rank0, truth, "pre")
    scan_r = ingest_scan(data, "redact_all")
    res_redact = run_system(data, rank_all(data, build_index(scan_r["texts"])), allowed_sync, "pre")
    guards = {"index_acl": run_system(data, rank0, allowed_idx), "flat": run_system(data, rank0, allowed_flat),
              "label": run_system(data, rank0, allowed_lab)}

    def system(name, res):
        s = leak_stats(data, res)
        rec, n_rec = readable_recall(data, res)
        ev = relevance_eval(data, res)
        s.update({"name": name, "readable_recall": rec, "precision": ev["precision"], "recall_all": ev["recall"],
                  "per_query": mean(len(v) for v in res.values())})
        return s

    systems = [system("no access control (step 1)", res0), system("post-filter on the ACL", res_post),
               system("pre-filter on the ACL, no PII action", res_pre), system("CorpusGate (pre-filter + PII action)", res_cg),
               system("variant: redact all, quarantine none", res_redact)]
    truth_sys = system("true-entitlement filter (best case)", res_truth)

    # resolver agreement with the generator's truth file
    agree_now = n_pairs - sum(len(allowed_now[u] ^ truth[u]) for u in truth)
    agree_sync = n_pairs - sum(len(allowed_sync[u] ^ truth[u]) for u in truth)
    window_pairs = sum(len(allowed_sync[u] - truth[u]) for u in truth)

    # personal data
    rows = scan["rows"]
    inj = [d for d in docs if docs[d]["pii_truth"] != "none"]
    found = [d for d in inj if rows[d]["found"]]
    missed = [d for d in inj if not rows[d]["found"]]
    fp = [d for d in docs if docs[d]["pii_truth"] == "none" and rows[d]["kinds"]]
    quarantined = [d for d in docs if rows[d]["action"] == "quarantine"]
    redacted = [d for d in docs if rows[d]["action"] == "redact"]
    by_kind = {}
    for k in ("ssn_like", "account_like", "email_like"):
        t = [d for d in inj if docs[d]["pii_truth"] == k]
        by_kind[k] = {"injected": len(t), "found": sum(1 for d in t if rows[d]["found"])}
    missed_set = set(missed)

    # a result "serves personal data" when the indexed text still holds it: the unfiltered system serves every
    # injected value; CorpusGate serves only the ones the scan missed
    pii_before = sum(1 for q in queries for d in res0[q["query_id"]] if docs[d]["pii_truth"] != "none")
    pii_after = sum(1 for q in queries for d in res_cg[q["query_id"]] if d in missed_set)
    pii_before_open = sum(1 for q in queries for d in res0[q["query_id"]]
                          if docs[d]["pii_truth"] != "none" and open_to_all_staff(docs[d]))

    # canaries
    can_none = run_canaries(data, sq["index"])
    can_cg = run_canaries(data, gate_index, allowed_sync)
    strata = sorted({c["stratum"] for c in data["canaries"]})
    can_rows = []
    for st in strata:
        a = [c for c in can_none if c["stratum"] == st]
        b = [c for c in can_cg if c["stratum"] == st]
        can_rows.append({"stratum": st, "pairs": len(a), "leaked_none": sum(c["leaked"] for c in a),
                         "leaked_cg": sum(c["leaked"] for c in b)})

    # window changes
    window = []
    for c in sorted(data["changes"], key=lambda c: c["changed_at"]):
        if c["changed_at"] > SYNC_AT:
            lost = sorted(u for u in data["users"] if c["doc_id"] in allowed_sync[u] and c["doc_id"] not in truth[u])
            window.append({"change_id": c["change_id"], "doc_id": c["doc_id"], "changed_at": c["changed_at"],
                           "from_acl": c["from_acl"], "to_acl": c["to_acl"], "users_still_allowed": lost})

    # utility (per 100 queries)
    leak0, leak1 = sq["leaked"] * 100.0 / n_q, systems[3]["leaked"] * 100.0 / n_q
    utility = (leak0 - leak1) * ASSISTANT_USERS

    A = {
        "data": data, "sq": sq, "synced": synced, "drift": drift, "scan": scan, "gate_index": gate_index,
        "rank0": rank0, "rank_gate": rank_gate, "allowed_sync": allowed_sync, "allowed_idx": allowed_idx,
        "allowed_flat": allowed_flat, "allowed_lab": allowed_lab, "res0": res0, "res_cg": res_cg, "guards": guards,
        "systems": systems, "truth_sys": truth_sys, "res_post": res_post, "res_pre": res_pre,
        "canaries_none": can_none, "canaries_cg": can_cg, "canary_rows": can_rows, "window": window,
        "missed": missed, "false_pos": fp, "quarantined": quarantined, "redacted": redacted,
        "summary": {
            "recall_queries": readable_recall(data, res0)[1],
            "n_docs": n_docs, "n_users": n_users, "n_queries": n_q, "n_pairs": n_pairs,
            "resolver_agree_now": agree_now, "resolver_agree_sync": agree_sync, "window_pairs": window_pairs,
            "drift_docs": len(drift), "drift_revokes": sum(1 for x in drift if _drift_is_revoke(data, x)),
            "changes_total": len(data["changes"]), "changes_after_sync": len(window),
            "leaked_before": sq["leaked"], "leaked_after": systems[3]["leaked"], "results": sq["results"],
            "leaked_window": sum(1 for q in queries for d in res_cg[q["query_id"]]
                                 if d not in truth[q["user_id"]] and d in {w["doc_id"] for w in window}),
            "queries_leak_before": sq["queries_with_leak"], "queries_leak_after": systems[3]["queries_with_leak"],
            "leak_per_100_before": leak0, "leak_per_100_after": leak1,
            "readable_recall_before": systems[0]["readable_recall"], "readable_recall_post": systems[1]["readable_recall"],
            "readable_recall_pre": systems[2]["readable_recall"], "readable_recall_after": systems[3]["readable_recall"],
            "readable_recall_truth": truth_sys["readable_recall"], "readable_recall_redact": systems[4]["readable_recall"],
            "recall_all_before": systems[0]["recall_all"], "recall_all_after": systems[3]["recall_all"],
            "precision_before": systems[0]["precision"], "precision_after": systems[3]["precision"],
            "per_query_post": systems[1]["per_query"], "per_query_pre": systems[2]["per_query"],
            "pii_injected": len(inj), "pii_found": len(found), "pii_missed": len(missed), "pii_false_pos": len(fp),
            "pii_by_kind": by_kind, "quarantined": len(quarantined), "redacted": len(redacted),
            "quarantined_true": sum(1 for d in quarantined if docs[d]["pii_truth"] != "none"),
            "redacted_true": sum(1 for d in redacted if docs[d]["pii_truth"] != "none"),
            "pii_results_before": pii_before, "pii_results_before_open": pii_before_open, "pii_results_after": pii_after,
            "canaries": len(data["canaries"]), "canary_leaked_none": sum(c["leaked"] for c in can_none),
            "canary_leaked_cg": sum(c["leaked"] for c in can_cg),
            "assistant_users": ASSISTANT_USERS, "utility": utility,
        },
    }
    A["stories"] = pick_stories(A)
    return A


def _drift_is_revoke(data: dict, x: dict) -> bool:
    return _is_revoke(data, {"from_acl": x["index_acl"], "to_acl": x["source_acl"]})


# ---------------------------------------------------------------------------
# The picker: about 15 queries, one per story, chosen by rule (never by hand)
# ---------------------------------------------------------------------------
def pick_stories(A: dict) -> list:
    data, docs, truth = A["data"], A["data"]["docs"], A["data"]["truth"]
    changed = {c["doc_id"]: c for c in data["changes"]}
    mis = {d for d, r in docs.items() if r["sensitivity"] != r["sensitivity_label_truth"]}
    rows = A["scan"]["rows"]
    cands = defaultdict(list)           # tag -> [(score, query_id)]
    for q in data["queries"]:
        qid, u = q["query_id"], q["user_id"]
        user = data["users"][u]
        r0, rc = A["res0"][qid], A["res_cg"][qid]
        leaks0 = [d for d in r0 if d not in truth[u]]
        rr = set(q["relevant"]) & truth[u]
        idx_leak = [d for d in A["guards"]["index_acl"][qid] if d not in truth[u] and d in changed]
        idx_hide = [d for d in rr if d not in A["allowed_idx"][u] and d in changed]
        flat_hide = [d for d in rr if d not in A["allowed_flat"][u]]
        flat_leak = [d for d in A["guards"]["flat"][qid] if d not in truth[u]]
        lab_leak = [d for d in A["guards"]["label"][qid] if d not in truth[u] and d in mis]
        lab_hide = [d for d in rr if d not in A["allowed_lab"][u] and d not in mis]
        gate_leak = [d for d in rc if d not in truth[u]]
        r0_pii = [d for d in r0 if docs[d]["pii_truth"] != "none" and open_to_all_staff(docs[d]) and d in truth[u]]
        removed = len(set(r0) - set(rc))
        served = [d for d in rc if d in set(A["missed"])]
        pure = not gate_leak and not served          # no known-limit effect mixed into this story
        plain = [d for d in leaks0 if d not in changed and d not in mis and docs[d]["pii_truth"] == "none"]
        c = cands
        n_rest = sum(1 for d in plain if docs[d]["sensitivity_label_truth"] == "restricted")
        if pure and n_rest and user["role"] != "contractor":
            c["leak_restricted"].append((-n_rest, qid))
        n_conf = sum(1 for d in plain if docs[d]["sensitivity_label_truth"] == "confidential" and docs[d]["dept"] != user["dept"])
        if pure and n_conf and not n_rest and user["role"] != "contractor":
            c["leak_confidential"].append((-n_conf, qid))
        if pure and idx_leak:
            c["stale_revoked"].append((-len(idx_leak), qid))
        if pure and idx_hide:
            c["stale_granted"].append((-len(idx_hide), qid))
        if pure and flat_hide and not flat_leak:
            c["flat_denied"].append((-len(flat_hide), qid))
        if pure and flat_leak and user["role"] == "contractor":
            c["flat_allowed"].append((-len(flat_leak), qid))
        if pure and lab_leak:
            c["label_mislabeled"].append((-len(lab_leak), qid))
        if pure and lab_hide:
            c["label_over"].append((-len(lab_hide), qid))
        for tag, kind in (("pii_ssn", "ssn_like"), ("pii_account", "account_like"), ("pii_email", "email_like")):
            hit = [d for d in r0_pii if docs[d]["pii_truth"] == kind and rows[d]["found"]]
            if pure and hit:
                c[tag].append((-len(hit), qid))
        if served and not gate_leak:
            c["pii_missed"].append((-len(served), qid))
        if gate_leak and not served:
            c["sync_window"].append((-len(gate_leak), qid))
        if pure and removed >= 4:
            c["mostly_withheld"].append((-removed, qid))
        guards_quiet = all(not [d for d in A["guards"][g][qid] if d not in truth[u]] for g in A["guards"]) and not (
            (rr - A["allowed_idx"][u]) or (rr - A["allowed_flat"][u]) or (rr - A["allowed_lab"][u]))
        if pure and guards_quiet and not leaks0 and r0 == rc and all(docs[d]["pii_truth"] == "none" for d in r0):
            c["clean"].append((0, qid))
    chosen, used = [], set()
    for tag in STORY_ORDER:
        for _, qid in sorted(cands.get(tag, [])):
            if qid not in used:
                used.add(qid)
                q = next(x for x in data["queries"] if x["query_id"] == qid)
                u = data["users"][q["user_id"]]
                chosen.append({"tag": tag, "query_id": qid, "user_id": q["user_id"],
                               "label": f"{qid} - {u['user_id']} ({u['dept'] if u['dept'] == u['role'] else u['dept'] + ' ' + u['role']}) - {STORY_TITLES[tag]}"})
                break
    return chosen


def story_detail(A: dict, qid: str) -> dict:
    """Everything the picker shows for one query, as plain data."""
    data, docs, truth = A["data"], A["data"]["docs"], A["data"]["truth"]
    q = next(x for x in data["queries"] if x["query_id"] == qid)
    u = q["user_id"]
    user = data["users"][u]
    rel = set(q["relevant"])
    rr = rel & truth[u]
    r0, rc = A["res0"][qid], A["res_cg"][qid]
    scores = dict(A["rank0"][qid])
    rows = A["scan"]["rows"]

    def item(d, with_why=False):
        r = docs[d]
        out = {"doc_id": d, "title": r["title"], "dept": r["dept"], "shown_label": r["sensitivity"],
               "true_label": r["sensitivity_label_truth"], "readable": d in truth[u], "relevant": d in rel,
               "score": round(scores.get(d, 0.0), 3), "pii": r["pii_truth"], "acl": r["acl_groups"]}
        if with_why:
            out["why"] = explain_access(data, u, r["acl_now"])["why"]
        return out

    held = [d for d in r0 if rows[d]["action"] == "quarantine" and d in A["allowed_sync"][u]]
    redacted_in = [d for d in rc if rows[d]["action"] == "redact"]
    served_pii = [d for d in rc if d in set(A["missed"])]
    g = A["guards"]
    out = {
        "query_id": qid, "text": q["text"], "n_relevant": len(rel),
        "user": {"id": u, "dept": user["dept"], "role": user["role"], "direct": user["direct"],
                 "effective": sorted(effective_groups(data, u)), "readable": len(truth[u]), "docs": len(docs)},
        "unfiltered": [item(d, True) for d in r0],
        "precision": round(sum(1 for d in r0 if d in rel) / len(r0), 3), "recall": round(sum(1 for d in r0 if d in rel) / len(rel), 3),
        "guards": {name: {"leaked": sum(1 for d in g[name][qid] if d not in truth[u]),
                          "withheld": len(rr - ({"index_acl": A["allowed_idx"], "flat": A["allowed_flat"], "label": A["allowed_lab"]}[name][u]))}
                   for name in ("index_acl", "flat", "label")},
        "gate": {"results": [item(d) for d in rc], "removed_acl": sum(1 for d in r0 if d not in A["allowed_sync"][u]),
                 "held_pii": [{"doc_id": d, "kind": rows[d]["kinds"][0] if rows[d]["kinds"] else ""} for d in held],
                 "redacted": redacted_in, "pii_served": served_pii, "leaked": [d for d in rc if d not in truth[u]],
                 "readable_relevant": len(rr),
                 "recall_before": round(len(set(r0) & rr) / len(rr), 3) if rr else None,
                 "recall_after": round(len(set(rc) & rr) / len(rr), 3) if rr else None},
    }
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    A = analyze()
    data, docs, S = A["data"], A["data"]["docs"], A["summary"]
    n_q = S["n_queries"]

    print("STEP 4 - WITH CORPUSGATE")
    print("Five parts, plain rules, no model. The retriever is the same TF-IDF stub, not a model.")
    print()
    print("1. EFFECTIVE ACL (nested groups, explicit denies)")
    print(f"   Resolver vs the generator's truth file, today's ACL: {S['resolver_agree_now']:,} of {S['n_pairs']:,} user and document pairs agree ({pct(S['resolver_agree_now'], S['n_pairs'])}).")
    print("   That agreement is by construction: the generator and the resolver implement one rule in two ways (downward and upward).")
    print()
    print("2. ACL DRIFT (index copy vs source ACL as of the last sync)")
    print(f"   Index ACL differs from the source ACL as of {SYNC_AT}: {S['drift_docs']} of {S['n_docs']} documents ({pct(S['drift_docs'], S['n_docs'])}): {S['drift_revokes']} revokes, {S['drift_docs'] - S['drift_revokes']} grants.")
    print("   CorpusGate filters on the source ACL, so none of these is decided from the stale copy; each is listed for re-indexing.")
    print(f"   Resolver on the synced ACL vs the truth file: {S['resolver_agree_sync']:,} of {S['n_pairs']:,} pairs agree ({pct(S['resolver_agree_sync'], S['n_pairs'])}); the difference is the sync window below.")
    print()
    print("3. INGESTION SCAN (regex at ingestion; ssn_like and account_like -> quarantine, email_like -> redact)")
    print(f"   Injected personal data: {S['pii_injected']} documents. Found: {S['pii_found']} of {S['pii_injected']} ({pct(S['pii_found'], S['pii_injected'])}); missed {S['pii_missed']}; flagged with none: {S['pii_false_pos']} documents.")
    for k in ("ssn_like", "account_like", "email_like"):
        b = S["pii_by_kind"][k]
        print(f"     {k:<13} found {b['found']} of {b['injected']}")
    print(f"   Quarantined (not indexed): {S['quarantined']} documents ({S['quarantined_true']} with injected data, {S['quarantined'] - S['quarantined_true']} look-alikes). Redacted: {S['redacted']} documents ({S['redacted_true']} with injected data).")
    print(f"   Results in the {n_q} queries that carry personal data: {S['pii_results_before']} before ({S['pii_results_before_open']} from documents open to all staff), {S['pii_results_after']} after.")
    print()
    print(f"4. RESULTS ON THE {n_q} QUERIES (top {K}; leaked = a result the asker may not read today)")
    print(f"   {'system':<40}{'returned':>9}{'leaked':>8}{'queries':>9}{'readable recall@5':>19}{'per query':>11}")
    for s in A["systems"]:
        print(f"   {s['name']:<40}{s['results']:>9,}{s['leaked']:>8}{s['queries_with_leak']:>9}{s['readable_recall']:>19.3f}{s['per_query']:>11.2f}")
    ts = A["truth_sys"]
    print(f"   {ts['name']:<40}{ts['results']:>9,}{ts['leaked']:>8}{ts['queries_with_leak']:>9}{ts['readable_recall']:>19.3f}{ts['per_query']:>11.2f}")
    clause = (f"all {S['recall_queries']} queries have at least one" if S['recall_queries'] == n_q
              else f"over the {S['recall_queries']} queries that have at least one")
    print(f"   Readable recall@5 counts only relevant documents the asker may read ({clause}). 'queries' is queries with at least one leaked result.")
    print(f"   Change in readable recall from filtering: readable recall@{K} goes {S['readable_recall_before']:.3f} -> {S['readable_recall_after']:.3f} ({S['readable_recall_after'] - S['readable_recall_before']:+.3f}), because unreadable results no longer take slots.")
    print(f"   Cost of the PII action alone: {S['readable_recall_pre'] - S['readable_recall_after']:.3f} (pre-filter without it {S['readable_recall_pre']:.3f}). Gap to the true-entitlement filter: {S['readable_recall_truth'] - S['readable_recall_after']:.3f}.")
    print(f"   Policy choice: redacting every match instead of quarantining gives readable recall@{K} {S['readable_recall_redact']:.3f}, so quarantine costs {S['readable_recall_redact'] - S['readable_recall_after']:.3f} more.")
    print(f"   A post-filter returns {S['per_query_post']:.2f} results per query on average; the pre-filter returns {S['per_query_pre']:.2f}.")
    print(f"   The old eval, rerun on the CorpusGate results: precision@{K} {S['precision_before']:.3f} -> {S['precision_after']:.3f}, recall@{K} {S['recall_all_before']:.3f} -> {S['recall_all_after']:.3f}.")
    print("   Recall@5 against all relevant documents falls because unreadable relevant documents are no longer returned; that is the intended behavior, not a loss.")
    print()
    print(f"5. CANARY PACK ({S['canaries']} pairs; each asks for one document the user may not read)")
    print(f"   Leaked / total: no access control {S['canary_leaked_none']} of {S['canaries']}; CorpusGate {S['canary_leaked_cg']} of {S['canaries']}.")
    print(f"   {'stratum':<22}{'pairs':>6}{'no control':>12}{'CorpusGate':>12}")
    for r in A["canary_rows"]:
        print(f"   {r['stratum']:<22}{r['pairs']:>6}{r['leaked_none']:>12}{r['leaked_cg']:>12}")
    print()
    print("KNOWN LIMIT (left in on purpose)")
    print(f"  (a) Personal data in a format the patterns do not match: {S['pii_missed']} of {S['pii_injected']} injected documents were not found.")
    for d in sorted(A["missed"]):
        tail = re.search(r"(Case note:|Refund is|Escalate to).*$", docs[d]["text"])
        print(f"      {d} {docs[d]['pii_truth']:<13}{tail.group(0) if tail else ''}")
    print(f"      They are served as they are: {S['pii_results_after']} results in the {n_q} queries still carry personal data.")
    print(f"  (b) The ACL-sync window: {S['changes_after_sync']} ACL changes landed after the last sync ({SYNC_AT}). The gate reads source ACLs at sync time, so it cannot see them.")
    for w in A["window"]:
        print(f"      {w['change_id']} {w['doc_id']} {w['changed_at']}  {w['from_acl']} -> {w['to_acl']}  (still allowed for {len(w['users_still_allowed'])} users)")
    print(f"      Until the next sync it allows {S['window_pairs']} user and document pairs the source now denies.")
    print(f"      The canary pack caught it: {S['canary_leaked_cg']} of {S['canaries']} canaries leaked. The {n_q} queries leaked {S['leaked_after']} results, {S['leaked_window']} of them from these {S['changes_after_sync']} documents.")
    print("      This prototype does not close the window; the production design (ARCHITECTURE.md) sketches how.")
    print()
    print(f"UTILITY (the people term is modeled: {S['assistant_users']:,} assistant users is an assumption, not a statistic)")
    print(f"  Unreadable results returned per 100 queries: {S['leak_per_100_before']:.2f} without CorpusGate, {S['leak_per_100_after']:.2f} with it.")
    print(f"  Lift: {S['leak_per_100_before'] - S['leak_per_100_after']:.2f} unreadable results removed per 100 queries, at a readable recall@{K} change of {S['readable_recall_after'] - S['readable_recall_before']:+.3f}.")
    print(f"  Utility = ({S['leak_per_100_before']:.2f} - {S['leak_per_100_after']:.2f}) x {S['assistant_users']:,} = {S['utility']:,.0f} unreadable results kept from users if each user runs 100 queries.")
    print("  Sensitivity to the user count: " + "; ".join(f"{n:,} users gives {(S['leak_per_100_before'] - S['leak_per_100_after']) * n:,.0f}" for n in (600, 1200, 2400)) + ".")
    print()
    print(f"PICKER STORIES ({len(A['stories'])} of {len(STORY_ORDER)} found by rule)")
    for st in A["stories"]:
        print(f"  {st['label']}")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_04_acl_drift.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["doc_id", "index_acl", "source_acl_at_sync"])
        for x in A["drift"]:
            w.writerow([x["doc_id"], x["index_acl"], x["source_acl"]])
    with open(OUT_DIR / "step_04_pii_scan.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["doc_id", "pii_truth", "kinds_found", "action", "found"])
        for d in sorted(A["scan"]["rows"]):
            r = A["scan"]["rows"][d]
            if r["kinds"] or r["pii_truth"] != "none":
                w.writerow([d, r["pii_truth"], ";".join(r["kinds"]), r["action"], int(r["found"])])
    with open(OUT_DIR / "step_04_canaries.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["canary_id", "user_id", "doc_id", "stratum", "leaked_no_control", "leaked_corpusgate"])
        for a, b in zip(A["canaries_none"], A["canaries_cg"]):
            w.writerow([a["canary_id"], a["user_id"], a["doc_id"], a["stratum"], int(a["leaked"]), int(b["leaked"])])
    with open(OUT_DIR / "step_04_results.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["query_id", "user_id", "rank", "doc_id", "asker_may_read"])
        for q in data["queries"]:
            for i, d in enumerate(A["res_cg"][q["query_id"]], 1):
                w.writerow([q["query_id"], q["user_id"], i, d, int(d in data["truth"][q["user_id"]])])
    summary = dict(A["summary"])
    summary["systems"] = [{k: v for k, v in s.items() if k != "by_label"} for s in A["systems"]]
    summary["canary_rows"] = A["canary_rows"]
    summary["stories"] = A["stories"]
    (OUT_DIR / "step_04_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
