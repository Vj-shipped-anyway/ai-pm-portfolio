"""Generates the CorpusGate synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes the CSVs next to this file)

What it builds
  documents.csv          500 short synthetic documents with a label, an access list (ACL), the ACL
                         copy stored when the index was built, and hidden truth (PII, true label).
  groups.csv             the group tree: (parent, child) rows. Members of the child group are
                         also members of the parent group. Nested up to four levels deep.
  users.csv              40 users and their DIRECT group memberships only.
  queries.csv            200 queries, each asked by one user, with the documents that are relevant
                         to the query's topic (relevance truth, independent of who may read).
  canary_queries.csv     120 canaries: a (user, not-entitled document) pair plus a query built to
                         retrieve exactly that document.
  acl_changes.csv        the ACL change log: every change to a document's ACL after indexing.
  entitlement_truth.csv  for each user, the documents the user may read today. Computed here by
                         walking the group tree DOWNWARD from each ACL group. The CorpusGate
                         resolver in src/step_04 walks UPWARD from the user. Same rule, two
                         implementations; comparing them is one of the measurements.

The truth is known because the data is synthetic: this script decides every ACL, label and
injected personal-data value, so it can say exactly who may read what. Nothing here comes from a
real bank, customer, employee, system or model. No real person's data exists in these files:
personal-data values are obviously invalid formats (SSN-like numbers start with 9 and have
group 00; account numbers look like ACCT-0000-1234; e-mail addresses end in .example).

Design choices that make every effect appear often enough to count (stated, not hidden):
  * ACL changes, mislabeled documents, nested-group denies and personal-data documents are planted
    in known numbers, and for each kind there are queries from a user who is affected. So the
    leakage rates are properties of this test set, not estimates of real-world frequency.
  * Document text is built from topic vocabulary (24 topics x 3 sub-topics) so that a plain
    TF-IDF scorer retrieves the right cluster most of the time. It is not natural language.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED = 20261020          # chosen once; no other seed was tried
OUT = Path(__file__).parent

N_DOCS = 500
N_QUERIES = 200
N_CANARIES = 120

# Dates are constants, not the clock.
INDEXED_AT = "2026-06-01T02:00"      # the index copy of every ACL was taken here
SYNC_AT = "2026-09-30T00:00"         # the last time CorpusGate pulled the source ACLs
AS_OF = "2026-10-01T00:00"           # "today" for the truth files

# ---------------------------------------------------------------------------
# Group tree: (parent, child). Members of the child are also members of the parent.
# ---------------------------------------------------------------------------
GROUP_EDGES = [
    ("grp-all-staff", "grp-retail"), ("grp-all-staff", "grp-commercial"), ("grp-all-staff", "grp-risk"),
    ("grp-all-staff", "grp-compliance"), ("grp-all-staff", "grp-legal"), ("grp-all-staff", "grp-hr"),
    ("grp-all-staff", "grp-tech"), ("grp-all-staff", "grp-exec"), ("grp-all-staff", "grp-contractors"),
    ("grp-retail", "grp-retail-cards"), ("grp-retail", "grp-retail-branches"),
    ("grp-retail-cards", "grp-retail-cards-fraud"),
    ("grp-commercial", "grp-commercial-payments"), ("grp-commercial", "grp-commercial-lending"),
    ("grp-commercial-payments", "grp-commercial-payments-ops"),
    ("grp-risk", "grp-risk-credit"), ("grp-risk", "grp-risk-model"),
    ("grp-risk-model", "grp-risk-model-validation"),
    ("grp-compliance", "grp-compliance-aml"), ("grp-compliance", "grp-compliance-privacy"),
    ("grp-compliance-aml", "grp-compliance-aml-investigations"),
    ("grp-legal", "grp-legal-litigation"), ("grp-hr", "grp-hr-comp"), ("grp-tech", "grp-tech-platform"),
    ("grp-contractors", "grp-contractors-risk"), ("grp-contractors", "grp-contractors-tech"),
    ("grp-incident-response", "grp-tech-platform"),
    ("grp-model-governance", "grp-risk-model"), ("grp-model-governance", "grp-compliance-privacy"),
]

DEPTS = ["retail", "commercial", "risk", "compliance", "legal", "hr", "tech"]
SUBTEAMS = {
    "retail": ["grp-retail-cards", "grp-retail-branches"],
    "commercial": ["grp-commercial-payments", "grp-commercial-lending"],
    "risk": ["grp-risk-credit", "grp-risk-model"],
    "compliance": ["grp-compliance-aml", "grp-compliance-privacy"],
    "legal": ["grp-legal-litigation"],
    "hr": ["grp-hr-comp"],
    "tech": ["grp-tech-platform"],
}
DEEP_GROUPS = {
    "retail": ["grp-retail-cards-fraud"],
    "commercial": ["grp-commercial-payments-ops"],
    "risk": ["grp-risk-model-validation", "grp-risk-credit"],
    "compliance": ["grp-compliance-aml-investigations", "grp-compliance-privacy"],
    "legal": ["grp-legal-litigation"],
    "hr": ["grp-hr-comp"],
    "tech": ["grp-tech-platform"],
}
SHARE_GROUPS = ["grp-risk", "grp-compliance", "grp-model-governance", "grp-incident-response", "grp-legal"]

# (dept, role, direct groups) counts per dept; leaf choices are drawn with the seeded RNG.
USER_PLAN = [
    ("retail", 7, [["grp-retail-branches"], ["grp-retail-cards"], ["grp-retail-cards-fraud"], ["grp-retail"]]),
    ("commercial", 6, [["grp-commercial-payments"], ["grp-commercial-payments-ops"], ["grp-commercial-lending"], ["grp-commercial"]]),
    ("risk", 5, [["grp-risk-credit"], ["grp-risk-model"], ["grp-risk-model-validation"], ["grp-risk"]]),
    ("compliance", 5, [["grp-compliance-aml"], ["grp-compliance-aml-investigations"], ["grp-compliance-privacy"], ["grp-compliance"]]),
    ("legal", 3, [["grp-legal-litigation"], ["grp-legal"]]),
    ("hr", 3, [["grp-hr-comp"], ["grp-hr"]]),
    ("tech", 4, [["grp-tech-platform"], ["grp-tech"]]),
]

# ---------------------------------------------------------------------------
# Topics: (dept, name, head words, three sub-topics of (core, core, extra, extra))
# ---------------------------------------------------------------------------
TOPICS = [
    ("retail", "card disputes", ("card", "dispute"),
     (("chargeback", "window", "merchant", "evidence"), ("provisional", "credit", "timing", "letter"),
      ("affidavit", "fraud", "claim", "liability"))),
    ("retail", "branch cash", ("branch", "cash"),
     (("vault", "count", "custody", "sealed"), ("courier", "pickup", "seal", "manifest"),
      ("shortage", "variance", "teller", "report"))),
    ("retail", "account opening", ("account", "opening"),
     (("identity", "document", "verification", "residency"), ("joint", "signer", "mandate", "form"),
      ("dormant", "reactivation", "closure", "balance"))),
    ("retail", "overdraft fees", ("overdraft", "fee"),
     (("waiver", "goodwill", "authority", "cap"), ("daily", "assessment", "posting", "order"),
      ("limit", "notice", "opt", "consent"))),
    ("commercial", "wire transfers", ("wire", "transfer"),
     (("cutoff", "beneficiary", "correspondent", "charges"), ("dual", "approval", "limit", "callback"),
      ("recall", "amendment", "tracer", "reversal"))),
    ("commercial", "trade finance", ("trade", "finance"),
     (("guarantee", "tenor", "discrepancy", "presentation"), ("collection", "documentary", "acceptance", "maturity"),
      ("invoice", "receivable", "advance", "recourse"))),
    ("commercial", "commercial lending", ("loan", "covenant"),
     (("ratio", "breach", "waiver", "cure"), ("collateral", "appraisal", "lien", "perfection"),
      ("renewal", "extension", "maturity", "amortization"))),
    ("commercial", "merchant services", ("merchant", "settlement"),
     (("acquiring", "interchange", "scheme", "rebate"), ("reserve", "holdback", "onboarding", "underwriting"),
      ("terminal", "outage", "replacement", "firmware"))),
    ("risk", "credit scoring", ("scorecard", "applicant"),
     (("cutpoint", "band", "override", "exception"), ("bureau", "refresh", "thin", "file"),
      ("stability", "backtest", "benchmark", "vintage"))),
    ("risk", "model validation", ("model", "validation"),
     (("inventory", "tier", "owner", "attestation"), ("challenger", "sensitivity", "outcome", "analysis"),
      ("finding", "remediation", "issue", "closure"))),
    ("risk", "market risk", ("market", "exposure"),
     (("desk", "position", "limit", "breach"), ("stress", "scenario", "shock", "horizon"),
      ("valuation", "curve", "input", "override"))),
    ("risk", "operational risk", ("operational", "loss"),
     (("event", "taxonomy", "near", "miss"), ("control", "testing", "sample", "deficiency"),
      ("rating", "heatmap", "assessment", "owner"))),
    ("compliance", "AML monitoring", ("monitoring", "alert"),
     (("threshold", "typology", "structuring", "velocity"), ("investigation", "narrative", "escalation", "disposition"),
      ("filing", "deadline", "extension", "confidentiality"))),
    ("compliance", "sanctions screening", ("sanctions", "screening"),
     (("watchlist", "match", "fuzzy", "name"), ("tuning", "calibration", "sample", "positive"),
      ("blocking", "delisting", "license", "hold"))),
    ("compliance", "privacy requests", ("privacy", "request"),
     (("erasure", "portability", "access", "verification"), ("retention", "schedule", "legal", "hold"),
      ("consent", "withdrawal", "marketing", "preference"))),
    ("compliance", "records retention", ("records", "archive"),
     (("destruction", "certificate", "vendor", "schedule"), ("mailbox", "journaling", "surveillance", "email"),
      ("voice", "recording", "storage", "playback"))),
    ("legal", "contracts", ("contract", "clause"),
     (("indemnity", "carve", "cap", "liability"), ("termination", "convenience", "notice", "cure"),
      ("assignment", "succession", "change", "consent"))),
    ("legal", "litigation holds", ("litigation", "preservation"),
     (("custodian", "acknowledgement", "release", "notice"), ("snapshot", "device", "backup", "imaging"),
      ("discovery", "privilege", "review", "log"))),
    ("legal", "regulator correspondence", ("regulator", "correspondence"),
     (("examination", "submission", "response", "tracker"), ("matters", "attention", "requiring", "closure"),
      ("inquiry", "intake", "routing", "acknowledgement"))),
    ("hr", "compensation", ("compensation", "band"),
     (("merit", "cycle", "budget", "guideline"), ("bonus", "accrual", "deferral", "clawback"),
      ("signing", "award", "grant", "vesting"))),
    ("hr", "employee relations", ("employee", "relations"),
     (("grievance", "mediation", "intake", "outcome"), ("leave", "accommodation", "request", "documentation"),
      ("separation", "severance", "release", "agreement"))),
    ("tech", "incident management", ("incident", "severity"),
     (("page", "rota", "handover", "escalation"), ("postmortem", "action", "owner", "review"),
      ("status", "communication", "template", "cadence"))),
    ("tech", "access management", ("privileged", "entitlement"),
     (("joiner", "mover", "leaver", "recertification"), ("checkout", "session", "recording", "break"),
      ("service", "rotation", "credential", "secret"))),
    ("tech", "change management", ("change", "release"),
     (("freeze", "calendar", "exception", "approval"), ("rollback", "plan", "test", "evidence"),
      ("emergency", "retroactive", "ticket", "closure"))),
]

KINDS = ["procedure", "guidance note", "checklist", "memo", "FAQ", "meeting summary"]
ADJ = ["current", "standard", "approved", "internal", "revised", "agreed"]
NOUN = ["procedure", "policy", "guidance", "process", "checklist", "practice"]
STATE = ["confirmed", "recorded", "approved", "reviewed", "logged", "signed off"]
PERIOD = ["day", "week", "month", "quarter"]

LABELS = ["public", "internal", "confidential", "restricted"]
LABEL_RANK = {l: i for i, l in enumerate(LABELS)}


# ---------------------------------------------------------------------------
# Group helpers (the DOWNWARD implementation used for the truth file)
# ---------------------------------------------------------------------------
def build_children():
    ch = defaultdict(set)
    for p, c in GROUP_EDGES:
        ch[p].add(c)
    return ch


CHILDREN = build_children()


def descendants(g):
    seen, stack = set(), [g]
    while stack:
        x = stack.pop()
        for c in CHILDREN.get(x, ()):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    return seen


def parse_acl(acl):
    allow = {g for g in acl if not g.startswith("-")}
    deny = {g[1:] for g in acl if g.startswith("-")}
    return allow, deny


def acl_text(acl):
    return ";".join(acl)


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def make_users(rng):
    rows = []
    for dept, n, leaves in USER_PLAN:
        for i in range(n):
            leaf = leaves[i % len(leaves)] if i < len(leaves) else rng.choice(leaves)
            role = "manager" if leaf == [f"grp-{dept}"] else "analyst"
            rows.append([dept, role, list(leaf)])
    rows.append(["exec", "exec", ["grp-exec"]])
    rows.append(["exec", "exec", ["grp-exec"]])
    for i in range(3):
        rows.append(["risk", "contractor", ["grp-contractors-risk", "grp-risk"]])
    for i in range(2):
        rows.append(["tech", "contractor", ["grp-contractors-tech", "grp-tech"]])
    rng.shuffle(rows)
    users = []
    for i, (dept, role, groups) in enumerate(rows, 1):
        users.append({"user_id": f"U{i:03d}", "dept": dept, "role": role, "direct": groups})
    return users


# ---------------------------------------------------------------------------
# ACLs
# ---------------------------------------------------------------------------
def make_acl(dept, label, rng):
    dg = f"grp-{dept}"
    if label == "public":
        return ["grp-all-staff"]
    if label == "internal":
        acl = ["grp-all-staff"]
        if rng.random() < 0.30:
            acl.append("-grp-contractors")
        return acl
    if label == "confidential":
        r = rng.random()
        if r < 0.45:
            acl = [dg]
        elif r < 0.75:
            acl = [rng.choice(SUBTEAMS[dept]), "grp-exec"]
        else:
            other = rng.choice([g for g in SHARE_GROUPS if g != dg])
            acl = [dg, other]
        if rng.random() < 0.5:
            acl.append("-grp-contractors")
        return acl
    acl = [rng.choice(DEEP_GROUPS[dept])]
    if rng.random() < 0.6:
        acl.append("grp-exec")
    acl.append("-grp-contractors")
    return acl


def pick_label(dept, rng):
    r = rng.random()
    if dept in ("hr", "legal", "compliance"):
        cuts = (0.10, 0.50, 0.85)
    else:
        cuts = (0.20, 0.70, 0.92)
    if r < cuts[0]:
        return "public"
    if r < cuts[1]:
        return "internal"
    if r < cuts[2]:
        return "confidential"
    return "restricted"


def main() -> None:
    rng = random.Random(SEED)

    # -- groups, users, membership closure (downward) -------------------------------------
    groups = sorted({g for e in GROUP_EDGES for g in e})
    users = make_users(rng)
    members_of = {}
    for g in groups:
        sub = {g} | descendants(g)
        members_of[g] = {u["user_id"] for u in users if set(u["direct"]) & sub}
    all_users = {u["user_id"] for u in users}

    def entitled_users(acl):
        allow, deny = parse_acl(acl)
        yes = set()
        for g in allow:
            yes |= members_of.get(g, set())
        for g in deny:
            yes -= members_of.get(g, set())
        return yes

    def flat_users(acl):
        allow, deny = parse_acl(acl)
        return {u["user_id"] for u in users
                if set(u["direct"]) & allow and not set(u["direct"]) & deny}

    # -- clusters and documents ------------------------------------------------------------
    n_clusters = len(TOPICS) * 3
    sizes = [6] * n_clusters
    extra = N_DOCS - sum(sizes)
    while extra > 0:
        i = rng.randrange(n_clusters)
        if sizes[i] < 8:
            sizes[i] += 1
            extra -= 1
    slots = []
    for ci, sz in enumerate(sizes):
        slots += [ci] * sz
    rng.shuffle(slots)

    docs = []
    for n, ci in enumerate(slots, 1):
        ti, si = divmod(ci, 3)
        owner, tname, head, subs = TOPICS[ti]
        core = subs[si][:2]
        extras = list(subs[si][2:])
        dept = owner if rng.random() < 0.85 else rng.choice([d for d in DEPTS if d != owner])
        label = pick_label(dept, rng)
        kind = rng.choice(KINDS)
        x = rng.choice(extras)
        y = extras[0] if x == extras[1] else extras[1]
        if rng.random() < 0.4:
            y = rng.choice(NOUN)
        noise = []
        if rng.random() < 0.25:
            other = [s for s in range(3) if s != si]
            noise.append(subs[rng.choice(other)][rng.randrange(2)])
        if rng.random() < 0.15:
            other_t = rng.choice([t for t in range(len(TOPICS)) if t != ti])
            noise.append(TOPICS[other_t][2][0])
        docs.append({
            "n": n, "doc_id": f"D{n:04d}", "cluster": ci, "topic": ti, "sub": si, "head": head, "core": core,
            "x": x, "y": y, "noise": noise, "kind": kind, "dept": dept, "true_label": label,
            "label": label, "acl_index": make_acl(dept, label, rng), "acl_now": None,
            "pii": "none", "pii_variant": "", "decoy": "", "adj": rng.sample(ADJ, 2),
            "noun": rng.sample(NOUN, 2), "state": rng.choice(STATE), "period": rng.choice(PERIOD),
            "extra_sentence": rng.random() < 0.5,
        })
    by_id = {d["doc_id"]: d for d in docs}

    # -- mislabeled documents (label says lower than the truth) ------------------------------
    hi = [d for d in docs if d["true_label"] in ("confidential", "restricted")]
    rng.shuffle(hi)
    mislabeled = hi[:12]
    for i, d in enumerate(mislabeled):
        d["label"] = "internal" if i < 10 else "public"

    # -- ACL changes after indexing -------------------------------------------------------------
    def change_options(d):
        """(kind, new_acl, direction) options for a document at its index-time ACL."""
        acl = d["acl_index"]
        label, dept = d["true_label"], d["dept"]
        deny = [g for g in acl if g.startswith("-")]
        opts = []
        if label in ("public", "internal") and acl[0] == "grp-all-staff":
            opts.append(("narrow_to_dept", [f"grp-{dept}"] + deny, "revoke"))
            if not deny:
                opts.append(("add_contractor_deny", acl + ["-grp-contractors"], "revoke"))
        if label == "confidential":
            if acl[0] == f"grp-{dept}":
                opts.append(("narrow_to_subteam", [SUBTEAMS[dept][0]] + acl[1:], "revoke"))
            share = [g for g in SHARE_GROUPS if g not in acl and g != f"grp-{dept}"]
            if share:
                opts.append(("add_group", acl + [share[0]], "grant"))
        if label == "restricted":
            if "grp-exec" not in acl:
                opts.append(("add_exec", acl[:-1] + ["grp-exec", acl[-1]], "grant"))
            else:
                opts.append(("add_dept_group", [acl[0], f"grp-{dept}", "grp-exec", "-grp-contractors"], "grant"))
        return opts

    pool = [d for d in docs if d not in mislabeled]
    rng.shuffle(pool)
    changes = []
    n_rev, n_grant = 0, 0
    used = set()
    for d in pool:
        if n_rev >= 22 and n_grant >= 14:
            break
        opts = change_options(d)
        rng.shuffle(opts)
        for kind, new_acl, direction in opts:
            if direction == "revoke" and n_rev >= 22:
                continue
            if direction == "grant" and n_grant >= 14:
                continue
            before, after = entitled_users(d["acl_index"]), entitled_users(new_acl)
            diff = (before - after) if direction == "revoke" else (after - before)
            if not diff:
                continue
            when = date(2026, 6, 1) + timedelta(days=rng.randint(2, 119))      # 2026-06-03 .. 2026-09-28
            ts = f"{when.isoformat()}T{rng.randint(7, 19):02d}:{rng.choice(['00', '15', '30', '45'])}"
            changes.append({"doc_id": d["doc_id"], "changed_at": ts, "kind": kind, "from": d["acl_index"],
                            "to": new_acl, "direction": direction})
            used.add(d["doc_id"])
            if direction == "revoke":
                n_rev += 1
            else:
                n_grant += 1
            break
    # three revocations after the last sync (the ACL-sync window)
    win_pool = [d for d in docs if d["doc_id"] not in used and d not in mislabeled
                and d["true_label"] in ("public", "internal") and d["acl_index"][0] == "grp-all-staff"
                and not any(g.startswith("-") for g in d["acl_index"])]
    rng.shuffle(win_pool)
    for i, d in enumerate(win_pool[:3]):
        ts = f"2026-09-30T{(8, 11, 15)[i]:02d}:{rng.choice(['00', '30'])}"
        changes.append({"doc_id": d["doc_id"], "changed_at": ts, "kind": "narrow_to_dept",
                        "from": d["acl_index"], "to": [f"grp-{d['dept']}"], "direction": "revoke"})
        used.add(d["doc_id"])
    changes.sort(key=lambda c: (c["changed_at"], c["doc_id"]))
    for i, c in enumerate(changes, 1):
        c["change_id"] = f"AC-{i:03d}"
    chg_by_doc = {c["doc_id"]: c for c in changes}
    for d in docs:
        d["acl_now"] = chg_by_doc[d["doc_id"]]["to"] if d["doc_id"] in chg_by_doc else d["acl_index"]

    # -- personal data -----------------------------------------------------------------------
    def pii_value(kind, unusual):
        if kind == "ssn_like":
            a, b = rng.randint(10, 99), rng.randint(1000, 9999)
            if not unusual:
                return f"9{a}-00-{b}", "dashed"
            return (f"9{a} 00 {b}", "spaces") if rng.random() < 0.5 else (f"9{a}00{b}", "no_separator")
        if kind == "account_like":
            b = rng.randint(1000, 9999)
            if not unusual:
                return f"ACCT-0000-{b}", "acct_hyphen"
            return (f"ACCT 0000 {b}", "acct_spaces") if rng.random() < 0.5 else (f"account no. 0000{b}", "account_no")
        b = rng.randint(1000, 9999)
        if not unusual:
            return f"user{b}@corp.example", "email"
        return (f"user{b} at corp dot example", "email_spelled") if rng.random() < 0.5 else (f"user{b} [at] corp.example", "email_bracket")

    # 60 PII documents: 10 public, 28 internal, 14 confidential, 8 restricted
    want = {"public": 10, "internal": 28, "confidential": 14, "restricted": 8}
    kinds = (["ssn_like"] * 22 + ["account_like"] * 20 + ["email_like"] * 18)
    rng.shuffle(kinds)
    unusual_flags = ([True] * 4 + [False] * 18, [True] * 3 + [False] * 17, [True] * 3 + [False] * 15)
    unusual = {"ssn_like": list(unusual_flags[0]), "account_like": list(unusual_flags[1]), "email_like": list(unusual_flags[2])}
    for k in unusual:
        rng.shuffle(unusual[k])
    pii_docs = []
    cand = [d for d in docs if d["doc_id"] not in used and d not in mislabeled]
    rng.shuffle(cand)
    for d in cand:
        if want.get(d["true_label"], 0) > 0 and len(pii_docs) < 60:
            want[d["true_label"]] -= 1
            pii_docs.append(d)
    for d, k in zip(pii_docs, kinds):
        u = unusual[k].pop()
        d["pii"] = k
        d["pii_value"], d["pii_variant"] = pii_value(k, u)
    # decoys: text that looks like personal data but is not
    decoy_pool = [d for d in docs if d["pii"] == "none"]
    rng.shuffle(decoy_pool)
    decoy_plan = ["form_number"] * 4 + ["shared_mailbox"] * 3 + ["sample_account"] * 2
    for d, k in zip(decoy_pool, decoy_plan):
        d["decoy"] = k

    # -- text ------------------------------------------------------------------------------------
    def doc_text(d):
        h1, h2 = d["head"]
        a, b = d["core"]
        s = [f"This {d['kind']} sets out the {d['adj'][0]} {d['noun'][0]} for {h1} {h2} cases.",
             f"It covers {a} and {b}, including the {d['x']} step and the {d['y']} record."]
        if d["noise"]:
            s[-1] = s[-1][:-1] + f". See also {' and '.join(d['noise'])}."
        s.append(f"Teams apply the {d['adj'][1]} {d['noun'][1]} when {a} is {d['state']}.")
        if d["extra_sentence"]:
            s.append(f"The {h1} {h2} owner checks {b} each {d['period']}.")
        if d["pii"] == "ssn_like":
            s.append(f"Case note: applicant identifier {d['pii_value']} was pasted from the intake form.")
        elif d["pii"] == "account_like":
            s.append(f"Refund is credited to settlement account {d['pii_value']}.")
        elif d["pii"] == "email_like":
            s.append(f"Escalate to {d['pii_value']} for sign-off.")
        if d["decoy"] == "form_number":
            s.append(f"Use form {rng.randint(100, 199)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)} for this request.")
        elif d["decoy"] == "shared_mailbox":
            s.append("Questions go to the shared mailbox servicedesk@corp.example.")
        elif d["decoy"] == "sample_account":
            s.append("The example format shown on the form is ACCT-0000-1234.")
        return " ".join(s)

    for d in docs:
        h1, h2 = d["head"]
        a, b = d["core"]
        d["title"] = f"{h1.capitalize()} {h2}: {a} and {b} ({d['kind']}) [DOC-{d['n']:04d}]"
        d["text"] = doc_text(d)

    # -- entitlement truth (current ACL, downward closure) --------------------------------------
    ent_now = {d["doc_id"]: entitled_users(d["acl_now"]) for d in docs}
    ent_index = {d["doc_id"]: entitled_users(d["acl_index"]) for d in docs}
    ent_sync = {}
    for d in docs:
        acl = d["acl_index"]
        c = chg_by_doc.get(d["doc_id"])
        if c and c["changed_at"] <= SYNC_AT:
            acl = c["to"]
        ent_sync[d["doc_id"]] = entitled_users(acl)
    flat_now = {d["doc_id"]: flat_users(d["acl_now"]) for d in docs}
    user_by_id = {u["user_id"]: u for u in users}

    # -- queries -------------------------------------------------------------------------------
    clusters = defaultdict(list)
    for d in docs:
        clusters[d["cluster"]].append(d)

    def query_text(d, with_extra, variant):
        h1, h2 = d["head"]
        a, b = d["core"]
        t = [f"{h1} {a} {b}", f"what is the rule for {a} on {h1} {h2}", f"how do we handle {a} and {b} for {h1}",
             f"{h1} {h2} {b}", f"{a} {h2} guidance"][variant % 5]
        return t + (f" {d['x']}" if with_extra else "")

    plan = []   # (category, doc_id, user_id)
    taken_docs = set()

    def add_plan(cat, doc, uids, n_users=1):
        pick = sorted(uids)
        rng.shuffle(pick)
        for u in pick[:n_users]:
            plan.append((cat, doc["doc_id"], u))
        taken_docs.add(doc["doc_id"])

    def pick_docs(cands, k):
        cands = [d for d in cands if d["doc_id"] not in taken_docs]
        rng.shuffle(cands)
        return cands[:k]

    revoked = [by_id[c["doc_id"]] for c in changes if c["direction"] == "revoke" and c["changed_at"] <= SYNC_AT]
    for d in pick_docs(revoked, 6):
        add_plan("stale_revoked", d, ent_index[d["doc_id"]] - ent_now[d["doc_id"]], 2)
    granted = [by_id[c["doc_id"]] for c in changes if c["direction"] == "grant"]
    for d in pick_docs(granted, 4):
        add_plan("stale_granted", d, ent_now[d["doc_id"]] - ent_index[d["doc_id"]])
    for c in [c for c in changes if c["changed_at"] > SYNC_AT]:
        d = by_id[c["doc_id"]]
        add_plan("sync_window", d, ent_sync[d["doc_id"]] - ent_now[d["doc_id"]], 2)
    nested = [d for d in docs if flat_now[d["doc_id"]] - ent_now[d["doc_id"]]]
    for d in pick_docs(nested, 5):
        add_plan("nested_deny", d, flat_now[d["doc_id"]] - ent_now[d["doc_id"]])
    flat_den = [d for d in docs if (ent_now[d["doc_id"]] - flat_now[d["doc_id"]]) and d["doc_id"] not in chg_by_doc]
    for d in pick_docs(flat_den, 5):
        add_plan("flat_denied", d, ent_now[d["doc_id"]] - flat_now[d["doc_id"]])
    over = [d for d in docs if d["label"] in ("confidential", "restricted") and d["doc_id"] not in chg_by_doc]
    for d in pick_docs(over, 4):
        add_plan("label_over", d, ent_now[d["doc_id"]])
    mis = [d for d in mislabeled if d["doc_id"] not in chg_by_doc]
    for d in pick_docs(mis, 8):
        add_plan("mislabeled", d, all_users - ent_now[d["doc_id"]])
    rest = [d for d in docs if d["true_label"] == "restricted" and d not in mislabeled and d["doc_id"] not in chg_by_doc]
    for d in pick_docs(rest, 4):
        add_plan("leak_restricted", d, all_users - ent_now[d["doc_id"]])
    conf = [d for d in docs if d["true_label"] == "confidential" and d not in mislabeled and d["doc_id"] not in chg_by_doc]
    for d in pick_docs(conf, 4):
        add_plan("leak_confidential", d, all_users - ent_now[d["doc_id"]])
    for k, cat in (("ssn_like", "pii_ssn"), ("account_like", "pii_account"), ("email_like", "pii_email")):
        c = [d for d in docs if d["pii"] == k and d["pii_variant"] in ("dashed", "acct_hyphen", "email")
             and d["doc_id"] not in chg_by_doc and len(ent_now[d["doc_id"]]) >= 30]
        for d in pick_docs(c, 3):
            add_plan(cat, d, ent_now[d["doc_id"]])
    c = [d for d in docs if d["pii"] != "none" and d["pii_variant"] not in ("dashed", "acct_hyphen", "email")
         and d["doc_id"] not in chg_by_doc and len(ent_now[d["doc_id"]]) >= 30]
    for d in pick_docs(c, 4):
        add_plan("pii_unusual", d, ent_now[d["doc_id"]])

    # base queries: every cluster once, then random clusters; half asked by a user in the topic's dept
    base_n = N_QUERIES - len(plan)
    assert base_n >= n_clusters, "too many planted queries"
    base_clusters = list(range(n_clusters)) + [rng.randrange(n_clusters) for _ in range(base_n - n_clusters)]
    queries = []
    for cat, doc_id, uid in plan:
        d = by_id[doc_id]
        queries.append({"cat": cat, "cluster": d["cluster"], "user": uid, "doc": d, "extra": True, "mixed": ""})
    for ci in base_clusters:
        owner = TOPICS[ci // 3][0]
        same = rng.random() < 0.5
        pool_u = [u["user_id"] for u in users if (u["dept"] == owner) == same and u["role"] != "exec"]
        if not pool_u:
            pool_u = [u["user_id"] for u in users]
        # a quarter of the base queries mention two aspects (a core word of a sibling sub-topic),
        # so a plain scorer cannot be perfect; the relevant set stays the primary cluster only
        sib = [s for s in range(3) if s != ci % 3]
        mixed = TOPICS[ci // 3][3][rng.choice(sib)][rng.randrange(2)] if rng.random() < 0.25 else ""
        queries.append({"cat": "base", "cluster": ci, "user": rng.choice(pool_u),
                        "doc": rng.choice(clusters[ci]), "extra": rng.random() < 0.3, "mixed": mixed})
    rng.shuffle(queries)
    q_rows = []
    for i, q in enumerate(queries, 1):
        d = q["doc"]
        rel = sorted(x["doc_id"] for x in clusters[q["cluster"]])
        text = query_text(d, q["extra"], rng.randrange(5)) + (f" {q['mixed']}" if q["mixed"] else "")
        q_rows.append([f"Q{i:03d}", q["user"], text, ";".join(rel)])

    # -- canaries -------------------------------------------------------------------------------
    not_ent = {d["doc_id"]: sorted(all_users - ent_now[d["doc_id"]]) for d in docs}
    canary_pairs = []
    seen_pairs = set()

    def add_canary(stratum, doc, uid):
        if (uid, doc["doc_id"]) in seen_pairs or uid in ent_now[doc["doc_id"]]:
            return False
        seen_pairs.add((uid, doc["doc_id"]))
        canary_pairs.append((stratum, uid, doc))
        return True

    plan_n = {"revoked_after_index": 20, "revoked_after_sync": 6, "nested_deny": 20, "mislabeled": 14}
    win_docs = [by_id[c["doc_id"]] for c in changes if c["changed_at"] > SYNC_AT]
    for d in win_docs:
        for u in sorted(ent_sync[d["doc_id"]] - ent_now[d["doc_id"]])[:2]:
            add_canary("revoked_after_sync", d, u)
    k = 0
    for d in revoked:
        for u in sorted(ent_index[d["doc_id"]] - ent_now[d["doc_id"]]):
            if k < plan_n["revoked_after_index"] and add_canary("revoked_after_index", d, u):
                k += 1
                break
    k = 0
    for d in [d for d in docs if flat_now[d["doc_id"]] - ent_now[d["doc_id"]]]:
        for u in sorted(flat_now[d["doc_id"]] - ent_now[d["doc_id"]]):
            if k < plan_n["nested_deny"] and add_canary("nested_deny", d, u):
                k += 1
                break
    k = 0
    for d in mislabeled:
        for u in not_ent[d["doc_id"]][:2]:
            if k < plan_n["mislabeled"] and add_canary("mislabeled", d, u):
                k += 1
    guard = 0
    while len(canary_pairs) < N_CANARIES and guard < 100000:
        guard += 1
        d = rng.choice(docs)
        u = rng.choice(not_ent[d["doc_id"]]) if not_ent[d["doc_id"]] else None
        if u:
            add_canary("ordinary", d, u)
    canary_pairs.sort(key=lambda t: (t[0], t[1], t[2]["doc_id"]))
    rng.shuffle(canary_pairs)
    c_rows = []
    for i, (stratum, uid, d) in enumerate(canary_pairs, 1):
        h1, h2 = d["head"]
        c_rows.append([f"CAN-{i:03d}", uid, d["doc_id"], f"DOC-{d['n']:04d} {h1} {h2} {d['core'][0]}", stratum])

    # -- write -----------------------------------------------------------------------------------
    write_csv(OUT / "groups.csv", ["parent", "child"], [[p, c] for p, c in GROUP_EDGES])
    write_csv(OUT / "users.csv", ["user_id", "dept", "role", "direct_groups"],
              [[u["user_id"], u["dept"], u["role"], ";".join(u["direct"])] for u in users])
    write_csv(OUT / "documents.csv",
              ["doc_id", "title", "text", "dept", "sensitivity", "acl_groups", "acl_groups_at_index",
               "pii_truth", "sensitivity_label_truth"],
              [[d["doc_id"], d["title"], d["text"], d["dept"], d["label"], acl_text(d["acl_now"]),
                acl_text(d["acl_index"]), d["pii"], d["true_label"]] for d in docs])
    write_csv(OUT / "queries.csv", ["query_id", "user_id", "text", "relevant_doc_ids"], q_rows)
    write_csv(OUT / "canary_queries.csv", ["canary_id", "user_id", "doc_id", "query_text", "stratum"], c_rows)
    write_csv(OUT / "acl_changes.csv", ["change_id", "doc_id", "changed_at", "change_kind", "from_acl", "to_acl"],
              [[c["change_id"], c["doc_id"], c["changed_at"], c["kind"], acl_text(c["from"]), acl_text(c["to"])]
               for c in changes])
    truth_rows = []
    for u in sorted(user_by_id):
        ids = sorted(d for d, s in ent_now.items() if u in s)
        truth_rows.append([u, len(ids), ";".join(ids)])
    write_csv(OUT / "entitlement_truth.csv", ["user_id", "n_entitled", "entitled_doc_ids"], truth_rows)

    # -- invariants --------------------------------------------------------------------------------
    assert len(docs) == N_DOCS and len(q_rows) == N_QUERIES and len(c_rows) == N_CANARIES, (len(docs), len(q_rows), len(c_rows))
    assert sum(1 for d in docs if d["pii"] != "none") == 60
    assert len(changes) == 22 + 14 + 3, len(changes)
    assert len({c["doc_id"] for c in changes}) == len(changes)
    print(f"wrote {len(docs)} documents, {len(users)} users, {len(groups)} groups, {len(q_rows)} queries, "
          f"{len(c_rows)} canaries, {len(changes)} ACL changes")


if __name__ == "__main__":
    main()
