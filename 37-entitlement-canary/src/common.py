"""Shared loading for the four step scripts of project 37, and the toy retrieval system the pull
requests change. The system is a stand-in: a keyword index with an entitlement filter and a few
settings. Nothing here is the tool; entitlement_canary.py only ever sees what the system returned.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from entitlement_canary import build_pack, closed_pairs, evaluate, make_canaries  # noqa: E402,F401

BASE_CONFIG = {"filter": "pre", "acl_source": "live", "groups": "nested", "deny": "honored", "cache": "none", "top_k": 5,
               "no_acl_sources": [], "unindexed_sources": [], "delegations": [], "withhold_for_role": {}}
STOP = frozenset("the and for with when this that into from its out see also".split())


def tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9]+(?:-[0-9]+)?", text.lower()) if len(t) >= 3 and t not in STOP]


def _read(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_world() -> dict:
    """The baseline estate: the access export, document text, relevance queries and a keyword index."""
    with open(os.path.join(DATA, "access_base.json"), encoding="utf-8") as fh:
        access = json.load(fh)
    text = {r["doc_id"]: r["text"] for r in _read("doc_text.csv")}
    queries = [{"query_id": r["query_id"], "user_id": r["user_id"], "text": r["text"],
                "relevant": set(r["relevant_doc_ids"].split(";"))} for r in _read("queries.csv")]
    postings: dict = {}
    for d in access["documents"]:
        for t in sorted(set(tokens(d["title"] + " " + text[d["doc_id"]]))):
            postings.setdefault(t, []).append(d["doc_id"])
    n = len(access["documents"])
    idf = {t: math.log(1 + n / len(v)) for t, v in postings.items()}
    return {"access": access, "text": text, "queries": queries, "postings": postings, "idf": idf}


def load_prs() -> list:
    truth = {r["pr_id"]: r for r in _read("pr_truth.csv")}
    out = []
    for r in _read("pr_cases.csv"):
        t = truth[r["pr_id"]]
        out.append({"pr_id": r["pr_id"], "kind": t["change_kind"], "leaks": t["truth_leaks"] == "yes",
                    "config": json.loads(r["config_json"]), "patch": json.loads(r["access_patch_json"])})
    return out


def patched_access(world: dict, patch: list) -> dict:
    """The access export as it stands on the pull request's branch."""
    new_acl = {p["doc_id"]: p["acl"] for p in patch}
    access = world["access"]
    return dict(access, documents=[dict(d, acl=new_acl.get(d["doc_id"], d["acl"])) for d in access["documents"]])


def _split(acl: list) -> tuple:
    return [g for g in acl if not g.startswith("-")], [g[1:] for g in acl if g.startswith("-")]


class System:
    """A retrieval system under one configuration. The oracle (`entitled`) walks the group tree downward
    from each ACL group; the tool's resolver walks upward from the user."""

    def __init__(self, world: dict, config: dict, access: dict = None):
        self.world = world
        self.cfg = dict(BASE_CONFIG, **config)
        access = access or world["access"]
        self.docs = {d["doc_id"]: d for d in access["documents"]}
        self.direct = {u["user_id"]: set(u["direct_groups"]) for u in access["users"]}
        self.role = {u["user_id"]: u.get("role", "") for u in access["users"]}
        self.children: dict = {}
        for g in access["groups"]:
            self.children.setdefault(g["parent"], []).append(g["child"])
        self.cache: dict = {}
        self._below: dict = {}
        self._allowed: dict = {}
        self._entitled: dict = {}

    def _descendants(self, g: str) -> set:
        if g not in self._below:
            out, stack = set(), [g]
            while stack:
                x = stack.pop()
                if x not in out:
                    out.add(x)
                    stack.extend(self.children.get(x, []))
            self._below[g] = out
        return self._below[g]

    def _may(self, user: str, doc: dict, cfg: dict) -> bool:
        if doc["source"] in cfg["no_acl_sources"]:
            return True
        acl = doc["acl_at_index"] if cfg["acl_source"] == "index_copy" else doc["acl"]
        allow, deny = _split(acl)
        if cfg["groups"] == "flat":
            def member(g): return g in self.direct[user]
        else:
            def member(g): return bool(self._descendants(g) & self.direct[user])
        ok = any(member(g) for g in allow)
        if cfg["deny"] == "honored" and any(member(g) for g in deny):
            ok = False
        for d in cfg["delegations"]:
            if d["user"] == user and d["scope_group"] in allow and self._descendants(d["scope_group"]) & self.direct[d["inherits_from"]]:
                ok = True
        if doc["source"] in cfg["withhold_for_role"].get(self.role[user], []):
            ok = False
        return ok

    def entitled(self, user: str, doc_id: str) -> bool:
        key = (user, doc_id)
        if key not in self._entitled:
            self._entitled[key] = self._may(user, self.docs[doc_id], BASE_CONFIG)
        return self._entitled[key]

    def allowed(self, user: str) -> set:
        if user not in self._allowed:
            hidden = set(self.cfg["unindexed_sources"])
            self._allowed[user] = {i for i, d in self.docs.items() if d["source"] not in hidden and self._may(user, d, self.cfg)}
        return self._allowed[user]

    def retrieve(self, user: str, text: str) -> list:
        cfg = self.cfg
        toks = tuple(sorted(set(tokens(text))))
        key = toks if cfg["cache"] == "shared" else (user, toks)
        if cfg["cache"] != "none" and key in self.cache:
            return list(self.cache[key])
        scores: dict = {}
        hidden = set(cfg["unindexed_sources"])
        for t in toks:
            for d in self.world["postings"].get(t, ()):
                if self.docs[d]["source"] not in hidden:
                    scores[d] = scores.get(d, 0.0) + self.world["idf"][t]
        ranked = sorted(scores, key=lambda d: (-scores[d], d))
        allowed = self.allowed(user)
        out = [d for d in ranked if d in allowed][:cfg["top_k"]] if cfg["filter"] == "pre" else [d for d in ranked[:cfg["top_k"]] if d in allowed]
        if cfg["cache"] != "none":
            self.cache[key] = out
        return list(out)


def pr_system(world: dict, pr: dict) -> System:
    return System(world, pr["config"], patched_access(world, pr["patch"]))


def run_harness(system: System, pack: list, prime: bool = True) -> list:
    """Run a pack the way the tool's README asks a harness to: control query first, then the probe."""
    rows = []
    for c in pack:
        control, primed = [], "no"
        if prime and c["prime_user"]:
            control, primed = system.retrieve(c["prime_user"], c["query"]), "yes"
        rows.append({"canary_id": c["canary_id"], "returned_doc_ids": ";".join(system.retrieve(c["user_id"], c["query"])),
                     "primed": primed, "control_returned_doc_ids": ";".join(control)})
    return rows


def exhaustive_leaks(system: System) -> set:
    """Every (user, document) pair the system returns to a user who may not open it, found by asking each
    document's title as each user (after one entitled user has asked it, so a shared cache is warm)."""
    leaked = set()
    users = sorted(system.direct)
    for doc_id in sorted(system.docs):
        title = system.docs[doc_id]["title"]
        opener = next((u for u in users if system.entitled(u, doc_id)), None)
        if opener:
            system.retrieve(opener, title)
        for u in users:
            for r in system.retrieve(u, title):
                if not system.entitled(u, r):
                    leaked.add((u, r))
    return leaked


def relevance_eval(system: System, queries: list) -> dict:
    """The usual retrieval eval: share of returned documents that are relevant. Entitlement plays no part."""
    total = hits = leaked = leaked_correct = 0
    for q in queries:
        for d in system.retrieve(q["user_id"], q["text"]):
            total += 1
            hits += d in q["relevant"]
            if not system.entitled(q["user_id"], d):
                leaked += 1
                leaked_correct += d in q["relevant"]
    return {"precision": hits / total if total else 0.0, "results": total, "leaked": leaked, "leaked_correct": leaked_correct}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
