"""Generates the synthetic data for project 59. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes the csv files next to this file)

What it builds
  agents.csv           14 AI agents of a modeled bank: owner, purpose, service account. Seven agents
                       share three service accounts.
  scope_catalog.csv    33 scopes in 8 namespaces. Six of them are group scopes such as accounts:*;
                       the `reaches` column lists the specific scopes a group stands for.
  grants.csv           Which agent holds which scope, when it was granted, and the ticket that asked
                       for it (blank for a few).
  calls.csv            About 5,000 calls over 90 days. On a shared service account the agent tag is
                       logged on half the calls only; the rest cannot be attributed.
  periodic_truth.csv   Grants that are legitimate but used once a quarter. The last use is before the
                       90-day window and the next use is after it, so a 90-day log sees them as unused.
  needed_truth.csv     For every grant: does the agent really need it, and why. This is the truth.
  example_*.csv        A small worked example (3 agents, 9 grants) for `scopekeeper.py --demo`.

The truth is known because the data is synthetic: this script decides which grants an agent needs
and writes the calls from that decision. The rules in src/scopekeeper.py never see the truth files.
Nothing here comes from a real bank, agent, platform or model. No model wrote any call; the calls
are drawn by this script from fixed rates.

Design choices were fixed before the first run; see data/README.md.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 5920261024
OUT = Path(__file__).parent

AS_OF = date(2026, 10, 23)                                   # last day of the window
WINDOW_DAYS = 90
WINDOW_START = AS_OF - timedelta(days=WINDOW_DAYS - 1)       # day 1

TARGET_CALLS = 5200              # core call rates are scaled so the expected total is this
SHARED_TAG_RATE = 0.5            # on a shared service account, the agent tag is logged on half the calls
MISSING_TICKET_P_LAUNCH = 0.03   # share of launch grants with no ticket reference
MISSING_TICKET_P_POST = 0.08     # share of after-launch grants with no ticket reference
SATSUN_WEIGHT = 0.3              # Saturday and Sunday traffic relative to a weekday

# namespace, specific scopes, whether a group scope `namespace:*` exists
NAMESPACES = [
    ("customers", ["read_profile", "read_kyc", "update_address", "update_contact"], True),
    ("accounts", ["read_balance", "read_history", "place_hold", "release_hold", "close_account"], True),
    ("ledger", ["read_entry", "post_entry", "reverse_entry"], True),
    ("payments", ["read_status", "initiate_payment", "release_wire", "cancel_payment"], True),
    ("notices", ["draft_notice", "send_email", "send_sms"], True),
    ("cases", ["read_case", "open_case", "close_case", "escalate_case"], True),
    ("reports", ["read_extract", "publish_report"], False),
    ("sanctions", ["read_alert", "clear_alert"], False),
]


def build_catalog() -> list:
    """(scope, reaches) rows: specific scopes have an empty reaches, a group lists its members."""
    rows = []
    for ns, members, has_group in NAMESPACES:
        specifics = sorted(f"{ns}:{m}" for m in members)
        rows.extend((s, "") for s in specifics)
        if has_group:
            rows.append((f"{ns}:*", ";".join(specifics)))
    return rows


# ---------------------------------------------------------------------------
# The fourteen agents. Each line is a decision the generator makes about the truth.
#   G   group grant, with the specific scopes the agent really calls and their rate per weekday
#   GX  group grant the agent never calls (a launch template)
#   D   needed, called every working day (scope, calls per weekday before scaling)
#   O   needed, called now and then (scope, expected calls in the 90 days; at least one is drawn)
#   Q   needed, called once a quarter, outside the window (scope, why)
#   U   added after launch and really needed (scope, calls per weekday)
#   L   granted at launch from a template and never needed
#   X   added after launch for a one-off task and never needed
#   S   never needed, but a smoke test called it a few times (scope, number of calls)
# ---------------------------------------------------------------------------
def agent(aid, owner, purpose, sa, launched, G=(), GX=(), D=(), O=(), Q=(), U=(), L=(), X=(), S=()):
    return dict(id=aid, owner=owner, purpose=purpose, sa=sa, launched=launched,
                G=list(G), GX=list(GX), D=list(D), O=list(O), Q=list(Q), U=list(U), L=list(L), X=list(X), S=list(S))


AGENTS = [
    agent("AG-01", "T-11 Retail Servicing", "Answers balance and transaction questions", "SVC-01", "2025-02-10",
          G=[("accounts:*", {"accounts:read_balance": 2.0, "accounts:read_history": 1.3})],
          D=[("customers:read_profile", 0.9), ("cases:read_case", 0.8), ("cases:open_case", 0.4)],
          O=[("notices:draft_notice", 12), ("reports:read_extract", 1.5)],
          U=[("notices:send_email", 0.3)],
          L=["ledger:read_entry", "payments:read_status", "customers:update_contact"],
          X=["cases:close_case"]),
    agent("AG-02", "T-14 Cards", "Triages card dispute intake", "SVC-02", "2025-03-24",
          D=[("cases:read_case", 1.0), ("cases:open_case", 0.7), ("accounts:read_history", 1.6),
             ("customers:read_profile", 0.8), ("accounts:read_balance", 0.6)],
          O=[("customers:read_kyc", 9), ("cases:escalate_case", 3)],
          Q=[("ledger:read_entry", "quarterly chargeback true-up")],
          U=[("notices:send_email", 0.4)],
          L=["notices:draft_notice", "reports:read_extract"],
          X=["payments:read_status"],
          S=[("accounts:place_hold", 2)]),
    agent("AG-03", "T-16 Payments", "Tells customers where a payment is", "SVC-03", "2025-04-14",
          D=[("payments:read_status", 3.0), ("notices:send_sms", 1.2), ("accounts:read_balance", 0.8),
             ("customers:read_profile", 0.5), ("cases:read_case", 0.4)],
          O=[("notices:send_email", 10), ("notices:draft_notice", 1.2)],
          L=["payments:cancel_payment", "customers:read_kyc", "reports:read_extract"],
          X=["payments:release_wire", "ledger:read_entry"]),
    agent("AG-04", "T-16 Payments", "Prepares routine payments for operator release", "SVC-04", "2025-05-05",
          G=[("payments:*", {"payments:read_status": 1.3, "payments:initiate_payment": 0.9})],
          D=[("ledger:read_entry", 0.8), ("accounts:read_balance", 1.0), ("accounts:read_history", 0.7)],
          O=[("ledger:post_entry", 18), ("customers:read_kyc", 1.5)],
          Q=[("ledger:reverse_entry", "quarter-end correction run")],
          U=[("accounts:place_hold", 0.12)],
          L=["notices:send_email", "cases:read_case", "customers:read_profile"],
          X=["accounts:close_account"]),
    agent("AG-05", "T-16 Payments", "Drafts wires for human release", "SVC-04", "2025-06-02",
          D=[("payments:release_wire", 0.6), ("accounts:read_balance", 0.7), ("payments:read_status", 0.9),
             ("sanctions:read_alert", 0.5)],
          O=[("payments:cancel_payment", 8), ("customers:update_address", 1.5)],
          Q=[("ledger:post_entry", "quarterly fee posting")],
          U=[("ledger:read_entry", 0.4)],
          L=["payments:initiate_payment", "notices:send_email", "cases:read_case"],
          X=["accounts:close_account", "accounts:release_hold"]),
    agent("AG-06", "T-16 Payments", "Schedules recurring transfers", "SVC-04", "2025-07-21",
          D=[("payments:read_status", 0.5), ("accounts:read_balance", 0.6), ("customers:read_profile", 0.4)],
          O=[("payments:cancel_payment", 12), ("cases:open_case", 6), ("reports:read_extract", 1.5)],
          Q=[("payments:initiate_payment", "quarterly fee sweep")],
          L=["payments:release_wire", "ledger:read_entry", "notices:draft_notice", "sanctions:read_alert"],
          X=["ledger:post_entry"]),
    agent("AG-07", "T-18 Finance Operations", "Matches ledger entries to payment confirmations", "SVC-05", "2025-03-03",
          G=[("ledger:*", {"ledger:read_entry": 3.0, "ledger:post_entry": 1.1})],
          D=[("payments:read_status", 1.2), ("accounts:read_history", 1.5), ("reports:read_extract", 0.5)],
          O=[("cases:open_case", 15), ("cases:read_case", 14)],
          Q=[("reports:publish_report", "quarter-end reconciliation pack")],
          L=["payments:initiate_payment", "notices:send_email", "sanctions:read_alert"],
          X=["payments:cancel_payment", "customers:read_profile"],
          S=[("sanctions:clear_alert", 1)]),
    agent("AG-08", "T-18 Finance Operations", "Posts month-end accrual adjustments", "SVC-06", "2025-08-11",
          D=[("ledger:read_entry", 1.1), ("ledger:post_entry", 0.5), ("reports:read_extract", 0.4),
             ("payments:read_status", 0.5)],
          O=[("ledger:reverse_entry", 4)],
          Q=[("accounts:read_history", "quarter-end tie-out"), ("reports:publish_report", "quarter-end close pack")],
          U=[("accounts:read_balance", 0.5), ("notices:send_email", 0.15)],
          L=["cases:read_case", "customers:read_kyc"],
          X=["payments:initiate_payment", "customers:update_address"]),
    agent("AG-09", "T-12 Contact Centre", "Drafts and sends customer email replies", "SVC-07", "2025-04-28",
          G=[("notices:*", {"notices:draft_notice": 1.6, "notices:send_email": 0.9})],
          D=[("cases:read_case", 1.3), ("cases:open_case", 0.4), ("customers:read_profile", 0.8),
             ("accounts:read_balance", 0.4)],
          O=[("cases:close_case", 12), ("reports:read_extract", 9), ("sanctions:read_alert", 1.5)],
          L=["payments:read_status", "customers:read_kyc", "ledger:read_entry"],
          X=["customers:update_contact"]),
    agent("AG-10", "T-13 Collections", "Sends payment reminders to late accounts", "SVC-07", "2025-09-15",
          D=[("notices:send_email", 0.8), ("notices:send_sms", 0.9), ("accounts:read_balance", 1.1),
             ("payments:read_status", 0.7)],
          O=[("cases:open_case", 12), ("reports:read_extract", 1.2), ("accounts:place_hold", 1.5)],
          U=[("cases:read_case", 0.5)],
          L=["notices:draft_notice", "payments:cancel_payment", "customers:update_contact"],
          X=["payments:initiate_payment"]),
    agent("AG-11", "T-15 Compliance Operations", "Collects periodic KYC refresh documents", "SVC-08", "2025-10-06",
          D=[("customers:read_kyc", 1.0), ("customers:update_contact", 0.5), ("cases:read_case", 0.6),
             ("sanctions:read_alert", 0.5)],
          O=[("notices:send_email", 10), ("cases:open_case", 7)],
          Q=[("cases:close_case", "quarterly stale-case sweep")],
          U=[("payments:read_status", 0.2)],
          L=["accounts:read_balance", "accounts:read_history", "ledger:read_entry"],
          X=["notices:draft_notice"]),
    agent("AG-12", "T-19 Treasury", "Builds the daily liquidity summary", "SVC-09", "2025-12-01",
          G=[("ledger:*", {"ledger:read_entry": 1.8}), ("accounts:*", {"accounts:read_balance": 1.4})],
          D=[("reports:read_extract", 0.9), ("payments:read_status", 0.7)],
          O=[("cases:read_case", 8), ("sanctions:read_alert", 1.5)],
          Q=[("reports:publish_report", "quarterly regulatory extract")],
          L=["payments:release_wire", "notices:send_email", "cases:open_case", "customers:read_kyc"],
          X=["payments:cancel_payment"]),
    agent("AG-13", "T-12 Contact Centre", "Logs and routes customer complaints", "SVC-09", "2026-01-12",
          G=[("cases:*", {"cases:read_case": 1.0, "cases:open_case": 0.8, "cases:close_case": 0.2})],
          GX=["payments:*"],
          D=[("customers:read_profile", 0.7), ("accounts:read_history", 0.5)],
          O=[("notices:send_email", 9), ("customers:read_kyc", 8), ("notices:send_sms", 1.5)],
          U=[("ledger:read_entry", 0.1)],
          L=["reports:read_extract", "accounts:read_balance"],
          X=["notices:draft_notice"]),
    agent("AG-14", "T-15 Compliance Operations", "Triages sanctions screening alerts", "SVC-10", "2026-03-09",
          D=[("sanctions:read_alert", 1.5), ("customers:read_profile", 0.6), ("cases:open_case", 0.5)],
          O=[("cases:escalate_case", 6)],
          Q=[("sanctions:clear_alert", "quarterly list re-screen")],
          L=["accounts:place_hold", "customers:read_kyc", "accounts:read_history"],
          X=["notices:send_email"]),
]


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


def write_example(catalog_rows: list) -> None:
    """A hand-built worked example, no randomness: 3 agents, 9 grants, 94 calls."""
    cat = dict(catalog_rows)
    write_csv("example_catalog.csv", ["scope", "reaches"], [("accounts:*", cat["accounts:*"])])
    write_csv("example_agents.csv", ["agent_id", "service_account"],
              [("EX-01", "EX-SVC-1"), ("EX-02", "EX-SVC-2"), ("EX-03", "EX-SVC-2")])
    grants = [("EX-01", "accounts:*"), ("EX-01", "customers:read_profile"), ("EX-01", "notices:send_sms"),
              ("EX-02", "ledger:read_entry"), ("EX-02", "payments:initiate_payment"),
              ("EX-03", "cases:close_case"), ("EX-03", "ledger:post_entry"), ("EX-03", "payments:initiate_payment"),
              ("EX-03", "payments:release_wire")]
    write_csv("example_grants.csv", ["agent_id", "scope", "granted_on", "ticket_id"],
              [(a, s, "2026-01-12", f"TKT-{9000 + i}") for i, (a, s) in enumerate(grants)])
    # (agent tag in the log, service account, scope, number of calls, first day, step in days)
    plan = [("EX-01", "EX-SVC-1", "accounts:read_balance", 30, 1, 3),
            ("EX-01", "EX-SVC-1", "accounts:read_history", 12, 2, 7),
            ("EX-01", "EX-SVC-1", "customers:read_profile", 20, 4, 4),
            ("EX-02", "EX-SVC-2", "payments:initiate_payment", 6, 3, 13),
            ("", "EX-SVC-2", "payments:initiate_payment", 8, 5, 11),
            ("EX-02", "EX-SVC-2", "ledger:read_entry", 10, 6, 9),
            ("EX-03", "EX-SVC-2", "payments:release_wire", 5, 8, 17),
            ("", "EX-SVC-2", "payments:release_wire", 3, 10, 29)]
    calls = []
    for agent_tag, sa, scope, n, first, step in plan:
        for i in range(n):
            calls.append(((first + i * step - 1) % WINDOW_DAYS + 1, len(calls), agent_tag, sa, scope))
    calls.sort()
    write_csv("example_calls.csv", ["call_id", "agent_id", "day", "scope_used", "service_account"],
              [(f"X{i:04d}", a, d, s, sa) for i, (d, _, a, sa, s) in enumerate(calls, 1)])


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
        assert post_lo <= post_hi, a["id"]

        def post_date() -> date:
            return post_lo + timedelta(days=rng_g.randrange((post_hi - post_lo).days + 1))

        for w, members in a["G"]:
            reach = cat[w][1].split(";")
            assert set(members) <= set(reach), (a["id"], w)
            basis = "group_all_members_used" if set(members) == set(reach) else "group_partly_used"
            grants.append(dict(agent=a["id"], scope=w, granted_on=launched, basis=basis, needed="yes",
                               needed_scopes=sorted(members), line=("G", members)))
        for w in a["GX"]:
            grants.append(dict(agent=a["id"], scope=w, granted_on=launched, basis="group_unused",
                               needed="no", needed_scopes=[], line=("GX", None)))
        for s, r in a["D"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="daily_use", needed="yes",
                               needed_scopes=[s], line=("D", r)))
        for s, e in a["O"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="occasional_use", needed="yes",
                               needed_scopes=[s], line=("O", e)))
        for s, why in a["Q"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="quarterly_cycle", needed="yes",
                               needed_scopes=[s], line=("Q", why)))
        for s, r in a["U"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=post_date(), basis="added_after_launch_used",
                               needed="yes", needed_scopes=[s], line=("U", r)))
        for s in a["L"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="launch_leftover", needed="no",
                               needed_scopes=[], line=("L", None)))
        for s in a["X"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=post_date(), basis="added_after_launch_unused",
                               needed="no", needed_scopes=[], line=("X", None)))
        for s, n in a["S"]:
            grants.append(dict(agent=a["id"], scope=s, granted_on=launched, basis="stray_use", needed="no",
                               needed_scopes=[], line=("S", n)))

    # ---- sanity: no duplicate grant, no specific grant under the agent's own group ------------
    seen = set()
    for g in grants:
        key = (g["agent"], g["scope"])
        assert key not in seen, key
        seen.add(key)
        assert g["scope"] in cat, g["scope"]
    for a in AGENTS:
        reached = {m for g in grants if g["agent"] == a["id"] and cat[g["scope"]][1]
                   for m in cat[g["scope"]][1].split(";")}
        for g in grants:
            if g["agent"] == a["id"] and not cat[g["scope"]][1]:
                assert g["scope"] not in reached, (a["id"], g["scope"])

    # ---- tickets: increasing with date, blank for a few ---------------------------------------
    order = sorted(grants, key=lambda g: (g["granted_on"], g["agent"], g["scope"]))
    n = 52000
    launch_of = {a["id"]: date.fromisoformat(a["launched"]) for a in AGENTS}
    for g in order:
        n += rng_g.randint(1, 40)
        p = MISSING_TICKET_P_POST if g["granted_on"] > launch_of[g["agent"]] else MISSING_TICKET_P_LAUNCH
        g["ticket"] = "" if rng_g.random() < p else f"TKT-{n:05d}"

    # ---- calls ---------------------------------------------------------------------------------
    rng_c = random.Random(f"{SEED}-calls")
    wsum = sum(day_weight(d) for d in range(1, WINDOW_DAYS + 1))
    core_expected, fixed_expected = 0.0, 0.0
    for g in grants:
        kind, val = g["line"]
        if kind in ("D", "U"):
            core_expected += val * wsum
        elif kind == "G":
            core_expected += sum(val.values()) * wsum
        elif kind in ("O", "S"):
            fixed_expected += val
    scale = (TARGET_CALLS - fixed_expected) / core_expected

    base_calls = []     # (day, agent_id, scope)
    for g in grants:
        kind, val = g["line"]
        lines = []
        if kind in ("D", "U"):
            lines = [(g["scope"], val)]
        elif kind == "G":
            lines = list(val.items())
        for scope, rate in lines:
            assert scope in cat and not cat[scope][1]
            for d in range(1, WINDOW_DAYS + 1):
                for _ in range(poisson(rng_c, rate * scale * day_weight(d))):
                    base_calls.append((d, g["agent"], scope))
        if kind == "O":
            for _ in range(max(1, poisson(rng_c, val))):
                base_calls.append((rng_c.randrange(1, WINDOW_DAYS + 1), g["agent"], g["scope"]))
        if kind == "S":
            for _ in range(val):
                base_calls.append((rng_c.randrange(1, WINDOW_DAYS + 1), g["agent"], g["scope"]))

    keyed = sorted(((c[0], rng_c.random(), c) for c in base_calls), key=lambda t: (t[0], t[1]))
    sa_of = {a["id"]: a["sa"] for a in AGENTS}
    calls = []
    for i, (d, _, (_, aid, scope)) in enumerate(keyed, 1):
        shared = len(sa_agents[sa_of[aid]]) > 1
        tagged = (not shared) or rng_c.random() < SHARED_TAG_RATE
        calls.append((f"C{i:05d}", aid if tagged else "", d, scope, sa_of[aid]))

    # ---- periodic truth ------------------------------------------------------------------------
    rng_r = random.Random(f"{SEED}-periodic")
    periodic = []
    for a in AGENTS:
        for scope, why in a["Q"]:
            d = rng_r.randint(2, 25)                                   # next use: 2 to 25 days after the window
            cycle = d + 90 + rng_r.randint(0, 10)                      # a bit over a quarter
            nxt = AS_OF + timedelta(days=d)
            last = nxt - timedelta(days=cycle)
            assert last < WINDOW_START and nxt > AS_OF
            periodic.append((a["id"], scope, last.isoformat(), cycle, nxt.isoformat(), rng_r.randint(2, 9), why))

    # ---- write ---------------------------------------------------------------------------------
    write_csv("agents.csv", ["agent_id", "owner", "purpose", "service_account", "launched_on"],
              [(a["id"], a["owner"], a["purpose"], a["sa"], a["launched"]) for a in AGENTS])
    write_csv("scope_catalog.csv", ["scope", "reaches"], catalog_rows)
    gsorted = sorted(grants, key=lambda g: (g["agent"], g["granted_on"], g["scope"]))
    write_csv("grants.csv", ["agent_id", "scope", "granted_on", "ticket_id"],
              [(g["agent"], g["scope"], g["granted_on"].isoformat(), g["ticket"]) for g in gsorted])
    write_csv("calls.csv", ["call_id", "agent_id", "day", "scope_used", "service_account"], calls)
    write_csv("periodic_truth.csv", ["agent_id", "scope", "last_use_date", "cycle_days", "next_use_date",
                                     "calls_next_quarter", "why"], periodic)
    write_csv("needed_truth.csv", ["agent_id", "scope", "needed", "basis", "needed_scopes"],
              [(g["agent"], g["scope"], g["needed"], g["basis"], ";".join(g["needed_scopes"])) for g in gsorted])
    write_example(catalog_rows)

    # ---- the generator's own checks ------------------------------------------------------------
    held = {}
    for g in grants:
        held.setdefault(g["agent"], set()).add(g["scope"])
    for _, aid, scope in base_calls:
        group = scope.split(":")[0] + ":*"
        assert scope in held[aid] or group in held[aid], (aid, scope)
    used_pairs = {(b[1], b[2]) for b in base_calls}
    for g in grants:
        if g["basis"] in ("launch_leftover", "added_after_launch_unused", "group_unused", "quarterly_cycle"):
            assert (g["agent"], g["scope"]) not in used_pairs
        if g["needed"] == "yes" and g["basis"] != "quarterly_cycle":
            for sc in g["needed_scopes"]:
                assert (g["agent"], sc) in used_pairs, (g["agent"], sc)       # every needed scope is called at least once
    assert {(r[0], r[1]) for r in periodic} == {(g["agent"], g["scope"]) for g in grants if g["basis"] == "quarterly_cycle"}

    n_unattr = sum(1 for c in calls if not c[1])
    print(f"seed {SEED}; window day 1 = {WINDOW_START}, day {WINDOW_DAYS} = {AS_OF}")
    print(f"rate scale {scale:.4f} (target {TARGET_CALLS} calls)")
    print(f"agents {len(AGENTS)}; service accounts {len(sa_agents)}; scopes {len(catalog_rows)}; grants {len(grants)}; "
          f"calls {len(calls)}; calls with no agent tag {n_unattr}; periodic grants {len(periodic)}")


if __name__ == "__main__":
    main()
