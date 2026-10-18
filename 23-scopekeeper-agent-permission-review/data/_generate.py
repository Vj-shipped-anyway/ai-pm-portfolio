"""Generates the ScopeKeeper synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes six CSVs next to this file)

What it builds
  agents.csv           15 AI agents of a modeled bank: owner, purpose, service account, risk tier.
                       Seven agents share three service accounts.
  scope_catalog.csv    30 scopes in 8 namespaces: 25 specific scopes and 5 wildcards such as
                       accounts:*. Each has an impact class and a flag for human approval.
  grants.csv           184 grants: which agent holds which scope, when it was granted, and the
                       ticket that asked for it (blank for a few).
  calls.csv            About 8,000 calls over 90 days. On a shared service account the agent tag
                       is logged on half the calls only; the rest cannot be attributed.
  rare_use_truth.csv   Ten grants that are legitimate but used on a quarterly cycle. The last use
                       is before the 90-day window and the next use is after it, so a 90-day
                       review sees them as unused.
  needed_truth.csv     For every grant: does the agent really need it, and why. This is the truth.

The truth is known because the data is synthetic: this script decides which grants an agent needs
and writes the calls from that decision. Nothing here comes from a real bank, agent, platform or
model. No model wrote any call; the calls are drawn by this script from fixed rates.

Design choices are fixed before any results are looked at; see data/README.md. Scale constants
(call volume, tag rate, ticket-gap rates, approval-skip rates) are listed below.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261023
OUT = Path(__file__).parent

AS_OF = date(2026, 10, 17)                       # the review date: last day of the window
WINDOW_DAYS = 90
WINDOW_START = AS_OF - timedelta(days=WINDOW_DAYS - 1)      # day 1 = 2026-07-20

TARGET_CALLS = 8000              # core call rates are scaled so the expected total is this
SHARED_TAG_RATE = 0.5            # on a shared service account, the agent tag is logged on half the calls
MISSING_TICKET_P_LAUNCH = 0.03   # share of launch grants with no ticket reference
MISSING_TICKET_P_POST = 0.08     # share of after-launch grants with no ticket reference
BASE_SKIP = 0.01                 # background rate of a high-impact call logged without approval
SATSUN_WEIGHT = 0.3              # Saturday and Sunday traffic relative to a weekday


# ---------------------------------------------------------------------------
# Scope catalog: (namespace, [(name, impact, needs_human_approval)])
# ---------------------------------------------------------------------------
NAMESPACES = [
    ("accounts", [("read_balance", "read", "no"), ("read_transactions", "read", "no"),
                  ("read_profile", "read", "no"), ("update_contact", "write", "no"),
                  ("close_account", "write", "yes")], True),
    ("ledger", [("read_entry", "read", "no"), ("write_entry", "write", "yes"),
                ("reverse_entry", "write", "yes"), ("post_adjustment", "write", "yes")], True),
    ("payments", [("read_status", "read", "no"), ("initiate_payment", "money_movement", "yes"),
                  ("initiate_wire", "money_movement", "yes"), ("cancel_payment", "money_movement", "yes"),
                  ("schedule_transfer", "money_movement", "yes")], True),
    ("messages", [("draft_email", "write", "no"), ("send_email", "external_message", "yes"),
                  ("send_sms", "external_message", "yes"), ("post_portal_notice", "external_message", "yes")], True),
    ("cases", [("read", "read", "no"), ("create", "write", "no"), ("close", "write", "yes")], True),
    ("documents", [("read", "read", "no"), ("upload", "write", "no")], False),
    ("kyc", [("read_case", "read", "no")], False),
    ("rates", [("read_quote", "read", "no")], False),
]
IMPACT_ORDER = ["read", "write", "external_message", "money_movement"]


def build_catalog() -> list:
    rows = []
    for ns, members, has_wild in NAMESPACES:
        for name, impact, appr in members:
            rows.append((f"{ns}:{name}", "specific", impact, appr))
        if has_wild:
            top = max(members, key=lambda m: IMPACT_ORDER.index(m[1]))[1]
            appr = "yes" if any(m[2] == "yes" for m in members) else "no"
            rows.append((f"{ns}:*", "wildcard", top, appr))
    return rows


# ---------------------------------------------------------------------------
# The fifteen agents. Each line is a decision the generator makes about the truth.
#   W   wildcard grant, with the specific scopes the agent really calls and their daily rate
#   WX  wildcard grant the agent never calls (a launch template)
#   C   needed, called every working day (scope, calls per weekday before scaling)
#   S   needed, called now and then (scope, expected calls in the 90 days)
#   Q   needed, called once a quarter, outside the window (scope, why)
#   CU  added after launch and really needed (scope, calls per weekday)
#   L   granted at launch from a template and never needed
#   CX  added after launch for a one-off task and never needed
# `skip` is the share of high-impact calls logged without the human approval the catalog requires.
# ---------------------------------------------------------------------------
def agent(aid, owner, purpose, sa, tier, launched, skip=BASE_SKIP, W=(), WX=(), C=(), S=(), Q=(), CU=(), L=(), CX=()):
    return dict(id=aid, owner=owner, purpose=purpose, sa=sa, tier=tier, launched=launched, skip=skip,
                W=list(W), WX=list(WX), C=list(C), S=list(S), Q=list(Q), CU=list(CU), L=list(L), CX=list(CX))


AGENTS = [
    agent("A-01", "T-11 Retail Servicing", "Answers customer balance and transaction questions", "SA-04", "medium", "2025-02-10",
          W=[("accounts:*", {"accounts:read_balance": 2.2, "accounts:read_transactions": 1.4})],
          C=[("cases:create", 0.5), ("documents:read", 0.6), ("cases:read", 0.9), ("kyc:read_case", 0.3)],
          S=[("rates:read_quote", 10), ("messages:draft_email", 12)],
          CU=[("messages:send_email", 0.3)],
          L=["ledger:read_entry", "payments:read_status", "documents:upload"],
          CX=["cases:close"]),
    agent("A-02", "T-14 Cards", "Triages card dispute intake", "SA-05", "medium", "2025-03-24",
          C=[("cases:read", 1.0), ("cases:create", 0.7), ("accounts:read_transactions", 1.6),
             ("documents:read", 0.8), ("accounts:read_balance", 0.6)],
          S=[("accounts:read_profile", 9), ("cases:close", 20)],
          Q=[("ledger:read_entry", "quarterly chargeback true-up")],
          CU=[("messages:send_email", 0.4), ("kyc:read_case", 0.3)],
          L=["messages:draft_email", "rates:read_quote"],
          CX=["payments:read_status"]),
    agent("A-03", "T-16 Payments", "Tells customers where a payment is", "SA-06", "medium", "2025-04-14",
          C=[("payments:read_status", 3.0), ("messages:send_sms", 1.2), ("accounts:read_balance", 0.8),
             ("accounts:read_profile", 0.5), ("cases:read", 0.4)],
          S=[("messages:post_portal_notice", 6), ("messages:send_email", 10)],
          L=["payments:cancel_payment", "documents:read", "rates:read_quote"],
          CX=["payments:schedule_transfer", "ledger:read_entry"]),
    agent("A-04", "T-16 Payments", "Prepares routine payments for operator release", "SA-01", "high", "2025-05-05",
          W=[("payments:*", {"payments:read_status": 1.3, "payments:initiate_payment": 0.9,
                             "payments:schedule_transfer": 0.5})],
          C=[("ledger:read_entry", 0.8), ("accounts:read_balance", 1.0), ("accounts:read_transactions", 0.7)],
          S=[("ledger:write_entry", 18)],
          Q=[("ledger:post_adjustment", "quarter-end adjustment")],
          CU=[("ledger:reverse_entry", 0.12)],
          L=["messages:send_email", "cases:read", "documents:read", "rates:read_quote"],
          CX=["accounts:update_contact"]),
    agent("A-05", "T-16 Payments", "Drafts wire transfers for human release", "SA-01", "high", "2025-06-02",
          C=[("payments:initiate_wire", 0.6), ("accounts:read_balance", 0.7), ("payments:read_status", 0.9),
             ("kyc:read_case", 0.5)],
          S=[("payments:cancel_payment", 8)],
          Q=[("ledger:write_entry", "quarterly true-up posting")],
          CU=[("ledger:read_entry", 0.4)],
          L=["payments:initiate_payment", "payments:schedule_transfer", "messages:send_email"],
          CX=["accounts:close_account", "accounts:update_contact"]),
    agent("A-06", "T-16 Payments", "Schedules recurring transfers", "SA-01", "high", "2025-07-21", skip=0.12,
          C=[("payments:schedule_transfer", 0.8), ("accounts:read_balance", 0.6), ("payments:read_status", 0.5),
             ("accounts:read_profile", 0.4)],
          S=[("payments:cancel_payment", 12), ("cases:create", 6)],
          Q=[("payments:initiate_payment", "quarterly fee sweep")],
          L=["payments:initiate_wire", "ledger:read_entry", "messages:draft_email", "kyc:read_case"],
          CX=["ledger:write_entry"]),
    agent("A-07", "T-18 Finance Operations", "Matches ledger entries to payment confirmations", "SA-07", "high", "2025-03-03",
          skip=0.25,
          W=[("ledger:*", {"ledger:read_entry": 3.0, "ledger:write_entry": 1.1})],
          C=[("payments:read_status", 1.2), ("accounts:read_transactions", 1.5), ("documents:read", 0.5)],
          S=[("cases:create", 15), ("cases:read", 14)],
          Q=[("documents:upload", "quarter-end reconciliation pack")],
          L=["payments:initiate_payment", "messages:send_email", "rates:read_quote"],
          CX=["payments:cancel_payment", "accounts:read_profile"]),
    agent("A-08", "T-18 Finance Operations", "Posts month-end accrual adjustments", "SA-08", "high", "2025-08-11",
          C=[("ledger:read_entry", 1.1), ("ledger:write_entry", 0.5), ("documents:read", 0.4),
             ("payments:read_status", 0.5)],
          S=[("ledger:post_adjustment", 10), ("ledger:reverse_entry", 4)],
          Q=[("accounts:read_transactions", "quarter-end tie-out"), ("documents:upload", "quarter-end close pack")],
          CU=[("accounts:read_balance", 0.5), ("messages:send_email", 0.15)],
          L=["cases:read", "rates:read_quote"],
          CX=["payments:initiate_payment", "accounts:update_contact"]),
    agent("A-09", "T-12 Contact Centre", "Drafts and sends customer e-mail replies", "SA-02", "medium", "2025-04-28",
          skip=0.10,
          W=[("messages:*", {"messages:draft_email": 1.6, "messages:send_email": 0.9})],
          C=[("cases:read", 1.3), ("cases:create", 0.4), ("accounts:read_profile", 0.8),
             ("accounts:read_balance", 0.4)],
          S=[("cases:close", 12), ("documents:read", 9)],
          L=["payments:read_status", "rates:read_quote", "kyc:read_case", "ledger:read_entry"],
          CX=["accounts:update_contact"]),
    agent("A-10", "T-13 Collections", "Sends payment reminders to late accounts", "SA-02", "high", "2025-09-15",
          skip=0.35,
          C=[("messages:send_email", 0.8), ("messages:send_sms", 0.9), ("accounts:read_balance", 1.1),
             ("payments:read_status", 0.7)],
          S=[("messages:post_portal_notice", 5), ("cases:create", 12)],
          CU=[("cases:read", 0.5)],
          L=["messages:draft_email", "payments:schedule_transfer", "accounts:update_contact", "documents:read"],
          CX=["payments:initiate_payment"]),
    agent("A-11", "T-15 Compliance Operations", "Collects periodic KYC refresh documents", "SA-09", "medium", "2025-10-06",
          C=[("kyc:read_case", 1.0), ("documents:read", 0.7), ("documents:upload", 0.5), ("cases:read", 0.6),
             ("accounts:read_profile", 0.5)],
          S=[("messages:send_email", 10), ("cases:create", 7)],
          Q=[("cases:close", "quarterly stale-case sweep")],
          CU=[("payments:read_status", 0.2)],
          L=["accounts:read_balance", "accounts:read_transactions", "ledger:read_entry"],
          CX=["messages:draft_email"]),
    agent("A-12", "T-19 Treasury", "Quotes indicative rates to relationship managers", "SA-03", "low", "2025-11-17",
          C=[("rates:read_quote", 2.0), ("accounts:read_balance", 0.6), ("documents:read", 0.4)],
          S=[("payments:read_status", 20), ("cases:read", 6)],
          Q=[("documents:upload", "quarterly rate-sheet publication")],
          CU=[("messages:draft_email", 0.2)],
          L=["ledger:read_entry", "kyc:read_case", "accounts:read_transactions"],
          CX=["accounts:read_profile", "cases:create"]),
    agent("A-13", "T-19 Treasury", "Builds the daily liquidity summary", "SA-03", "low", "2025-12-01",
          W=[("ledger:*", {"ledger:read_entry": 1.8}), ("accounts:*", {"accounts:read_balance": 1.4})],
          C=[("rates:read_quote", 0.9), ("documents:read", 0.5), ("payments:read_status", 0.7)],
          S=[("cases:read", 8)],
          Q=[("documents:upload", "quarterly regulatory extract")],
          L=["payments:initiate_wire", "messages:send_email", "cases:create", "kyc:read_case"],
          CX=["payments:schedule_transfer"]),
    agent("A-14", "T-12 Contact Centre", "Logs and routes customer complaints", "SA-10", "medium", "2026-01-12",
          W=[("cases:*", {"cases:read": 1.0, "cases:create": 0.8, "cases:close": 0.2})],
          WX=["payments:*"],
          C=[("documents:read", 0.5), ("accounts:read_profile", 0.7), ("accounts:read_transactions", 0.5)],
          S=[("messages:send_email", 9), ("kyc:read_case", 8)],
          CU=[("ledger:read_entry", 0.1)],
          L=["documents:upload", "rates:read_quote", "accounts:read_balance"],
          CX=["messages:draft_email"]),
    agent("A-15", "T-11 Retail Servicing", "Processes address and contact changes", "SA-11", "high", "2026-03-09",
          C=[("accounts:update_contact", 0.9), ("accounts:read_profile", 1.2), ("documents:read", 0.4),
             ("cases:create", 0.4)],
          S=[("accounts:close_account", 6), ("messages:send_email", 12)],
          L=["accounts:read_transactions", "payments:read_status", "ledger:read_entry", "documents:upload"],
          CX=["ledger:write_entry", "payments:cancel_payment"]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's method; fine for the small rates used here."""
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def day_weight(day: int) -> float:
    d = WINDOW_START + timedelta(days=day - 1)
    return SATSUN_WEIGHT if d.weekday() >= 5 else 1.0


def write_csv(name: str, header: list, rows: list) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    catalog_rows = build_catalog()
    cat = {r[0]: r for r in catalog_rows}
    sa_agents: dict = {}
    for a in AGENTS:
        sa_agents.setdefault(a["sa"], []).append(a["id"])

    # ---- grants: one row per (agent, scope) with its truth -----------------------------------
    rng_g = random.Random(f"{SEED}-grants")
    grants = []          # dict: agent, scope, granted_on, basis, needed, needed_scopes, line
    for a in AGENTS:
        launched = date.fromisoformat(a["launched"])
        post_lo, post_hi = launched + timedelta(days=45), WINDOW_START - timedelta(days=21)

        def post_date() -> date:
            return post_lo + timedelta(days=rng_g.randrange((post_hi - post_lo).days + 1))

        for w, members in a["W"]:
            assert all(m.split(":")[0] == w.split(":")[0] for m in members), (a["id"], w)
            full = len([r for r in catalog_rows if r[1] == "specific" and r[0].split(":")[0] == w.split(":")[0]])
            basis = "wildcard_all_members_used" if len(members) == full else "wildcard_partly_used"
            grants.append(dict(agent=a["id"], scope=w, granted_on=launched, basis=basis, needed="yes",
                               needed_scopes=sorted(members), line=("W", members)))
        for w in a["WX"]:
            grants.append(dict(agent=a["id"], scope=w, granted_on=launched, basis="wildcard_unused",
                               needed="no", needed_scopes=[], line=("WX", None)))
        for s, r in a["C"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="daily_use", needed="yes",
                               needed_scopes=[s], line=("C", r)))
        for s, e in a["S"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="occasional_use", needed="yes",
                               needed_scopes=[s], line=("S", e)))
        for s, why in a["Q"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="quarterly_cycle", needed="yes",
                               needed_scopes=[s], line=("Q", why)))
        for s, r in a["CU"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=post_date(), basis="added_after_launch_used",
                               needed="yes", needed_scopes=[s], line=("CU", r)))
        for s in a["L"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="launch_leftover", needed="no",
                               needed_scopes=[], line=("L", None)))
        for s in a["CX"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=post_date(), basis="added_after_launch_unused",
                               needed="no", needed_scopes=[], line=("CX", None)))

    # ---- sanity: no duplicate grant, no specific grant under the agent's own wildcard ---------
    seen = set()
    for g in grants:
        key = (g["agent"], g["scope"])
        assert key not in seen, key
        seen.add(key)
        assert g["scope"] in cat, g["scope"]
    for a in AGENTS:
        wild_ns = {g["scope"].split(":")[0] for g in grants if g["agent"] == a["id"] and g["scope"].endswith(":*")}
        for g in grants:
            if g["agent"] == a["id"] and not g["scope"].endswith(":*"):
                assert g["scope"].split(":")[0] not in wild_ns, (a["id"], g["scope"])

    # ---- tickets: increasing with date, blank for a few ---------------------------------------
    order = sorted(grants, key=lambda g: (g["granted_on"], g["agent"], g["scope"]))
    n = 41000
    launch_of = {a["id"]: date.fromisoformat(a["launched"]) for a in AGENTS}
    for g in order:
        n += rng_g.randint(1, 40)
        p = MISSING_TICKET_P_POST if g["granted_on"] > launch_of[g["agent"]] else MISSING_TICKET_P_LAUNCH
        g["ticket"] = "" if rng_g.random() < p else f"TKT-{n:05d}"

    # ---- calls ---------------------------------------------------------------------------------
    rng_c = random.Random(f"{SEED}-calls")
    wsum = sum(day_weight(d) for d in range(1, WINDOW_DAYS + 1))
    core_expected, spor_expected = 0.0, 0.0
    for g in grants:
        kind, val = g["line"]
        if kind in ("C", "CU"):
            core_expected += val * wsum
        elif kind == "W":
            core_expected += sum(val.values()) * wsum
        elif kind == "S":
            spor_expected += val
    scale = (TARGET_CALLS - spor_expected) / core_expected

    base_calls = []     # (day, agent_id, scope)
    for g in grants:
        kind, val = g["line"]
        lines = []
        if kind in ("C", "CU"):
            lines = [(g["scope"], val)]
        elif kind == "W":
            lines = list(val.items())
        for scope, rate in lines:
            assert scope in cat and cat[scope][1] == "specific"
            for d in range(1, WINDOW_DAYS + 1):
                for _ in range(poisson(rng_c, rate * scale * day_weight(d))):
                    base_calls.append((d, g["agent"], scope))
        if kind == "S":
            for _ in range(max(1, poisson(rng_c, val))):
                base_calls.append((rng_c.randrange(1, WINDOW_DAYS + 1), g["agent"], g["scope"]))

    keyed = sorted(((c[0], rng_c.random(), c) for c in base_calls), key=lambda t: (t[0], t[1]))
    skip = {a["id"]: a["skip"] for a in AGENTS}
    sa_of = {a["id"]: a["sa"] for a in AGENTS}
    calls = []
    for i, (d, _, (_, aid, scope)) in enumerate(keyed, 1):
        if cat[scope][3] == "yes":
            appr = "no" if rng_c.random() < skip[aid] else "yes"
        else:
            appr = "not_required"
        shared = len(sa_agents[sa_of[aid]]) > 1
        tagged = (not shared) or rng_c.random() < SHARED_TAG_RATE
        calls.append((f"C{i:05d}", aid if tagged else "", d, scope, appr, sa_of[aid]))

    # ---- rare-use truth ------------------------------------------------------------------------
    rng_r = random.Random(f"{SEED}-rare")
    rare = []
    for a in AGENTS:
        for scope, why in a["Q"]:
            d = rng_r.randint(2, 25)                                   # next use: 2 to 25 days after the review
            cycle = d + 90 + rng_r.randint(0, 10)                      # a bit over a quarter
            nxt = AS_OF + timedelta(days=d)
            last = nxt - timedelta(days=cycle)
            assert last < WINDOW_START and nxt > AS_OF
            rare.append((a["id"], scope, last.isoformat(), cycle, nxt.isoformat(), rng_r.randint(2, 9), why))

    # ---- write ---------------------------------------------------------------------------------
    write_csv("agents.csv", ["agent_id", "owner", "purpose", "service_account", "risk_tier", "launched_on"],
              [(a["id"], a["owner"], a["purpose"], a["sa"], a["tier"], a["launched"]) for a in AGENTS])
    write_csv("scope_catalog.csv", ["scope", "kind", "impact", "needs_human_approval"], catalog_rows)
    gsorted = sorted(grants, key=lambda g: (g["agent"], g["granted_on"], g["scope"]))
    write_csv("grants.csv", ["agent_id", "scope", "granted_on", "ticket_id"],
              [(g["agent"], g["scope"], g["granted_on"].isoformat(), g["ticket"]) for g in gsorted])
    write_csv("calls.csv", ["call_id", "agent_id", "day", "scope_used", "human_approved", "service_account"], calls)
    write_csv("rare_use_truth.csv", ["agent_id", "scope", "last_use_date", "cycle_days", "next_use_date",
                                     "calls_next_quarter", "why"], rare)
    write_csv("needed_truth.csv", ["agent_id", "scope", "needed", "basis", "needed_scopes"],
              [(g["agent"], g["scope"], g["needed"], g["basis"], ";".join(g["needed_scopes"])) for g in gsorted])

    # ---- the generator's own checks ------------------------------------------------------------
    held = {}
    for g in grants:
        held.setdefault(g["agent"], set()).add(g["scope"])
    for _, aid, scope in base_calls:
        ns = scope.split(":")[0]
        assert scope in held[aid] or f"{ns}:*" in held[aid], (aid, scope)
    quarterly = {(r[0], r[1]) for r in rare}
    used_pairs = {(b[1], b[2]) for b in base_calls}
    for g in grants:
        if g["basis"] in ("launch_leftover", "added_after_launch_unused", "wildcard_unused", "quarterly_cycle"):
            assert (g["agent"], g["scope"]) not in used_pairs
    assert quarterly == {(g["agent"], g["scope"]) for g in grants if g["basis"] == "quarterly_cycle"}
    for g in grants:
        if g["needed"] == "yes" and g["basis"] != "quarterly_cycle":
            for sc in g["needed_scopes"]:
                assert (g["agent"], sc) in used_pairs, (g["agent"], sc)       # every needed scope is called at least once

    n_unattr = sum(1 for c in calls if not c[1])
    print(f"seed {SEED}; as-of {AS_OF}; window day 1 = {WINDOW_START}")
    print(f"rate scale {scale:.4f} (target {TARGET_CALLS} calls)")
    print(f"agents {len(AGENTS)}; service accounts {len(sa_agents)}; scopes {len(catalog_rows)}; grants {len(grants)}; "
          f"calls {len(calls)}; calls with no agent tag {n_unattr}; rare-use grants {len(rare)}")


if __name__ == "__main__":
    main()
