"""Generates the AgentKit synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes the CSVs next to this file)

The world is a modeled bank operations queue: payment exception handling (wire repair). A returned
or exception payment lands in a work queue; a worker reads the reason, looks up the original payment,
fixes a field, gets a second person to approve and resubmits. Nothing here comes from a real bank,
process, system, vendor or person. No model is used anywhere in this repo.

What it builds
  cases.csv            600 exception deliveries, the input an agent would see.
  human_outcomes.csv   the recorded human outcome per case (what the worker did), the minutes they
                       spent, and a pseudonymous worker id. A historical record, so the shadow
                       replay may use it.
  case_truth.csv       the generator's ANSWER KEY: which scenario each case was built from. The kit
                       never reads it; step scripts use it only to explain a result.
  payments.csv         the synthetic payments table (the original payments, one per case plus filler).
  parties_watchlist.csv  a synthetic party watch list (60 invented parties).
  reason_codes.csv     the rule table for the four synthetic return reason codes.
  fault_schedule.csv   the fault-injection schedule used by the tests and by step 4.
  step_minutes.csv     the per-step touch minutes the human path uses. A generator assumption, not a
                       time study.

Design choices (made from reasoning about the workflow, before any agent result was computed):
  * Each case is built from a named scenario (a "scenario" is a recipe, e.g. a clean account fix, an
    affiliate-company name, a closed account that has a successor account). The human outcome
    follows the recipe, not any matcher's score.
  * Planted edge cases: affiliate names that look like a close match but are a different party,
    ambiguous names, closed accounts that have a successor account, watch-list hits (exact and
    variant) and watch-list look-alikes that a person cleared, malformed records, duplicate
    deliveries, leading-zero account numbers that a spreadsheet hop corrupts.
  * The recorded human outcome is the generator's idea of a careful worker. It is not a gold label
    from a real operation, and a real worker would disagree with it sometimes.
  * The abbreviation variants in company names use eight abbreviations; the kit knows five of them.
    That is deliberate: a real name list holds abbreviations no table knows.

Time. Hour 0 is a constant epoch; the clock is never read. Cases open over 720 hours (30 days).
"""

from __future__ import annotations

import csv
import math
import random
import sys
from pathlib import Path

SEED = 20261027
OUT = Path(__file__).parent
HOURS = 720

SYLLABLES = ["bren", "mar", "ko", "vel", "dra", "lin", "tor", "sa", "qui", "nox", "ver", "tal", "om", "ri", "ax",
             "pel", "dun", "for", "gal", "hes", "jun", "kel", "lor", "mon", "nev", "ost", "pra", "rav", "sil",
             "tav", "ulm", "vin", "wex", "yor", "zan"]
SECTORS = ["Freight", "Logistics", "Textiles", "Foods", "Marine", "Energy", "Trading", "Engineering", "Packaging",
           "Agro", "Metals", "Plastics", "Chemicals", "Paper", "Timber", "Electronics", "Machinery", "Fisheries",
           "Ceramics", "Beverages"]
SERVICES = ["Services", "Systems", "Solutions", "Industries", "Supplies", "Partners", "Enterprises", "Distribution"]
AMBIGUOUS_THIRD = ["Group", "Holdings", "Associates", "Ventures", "Capital"]
LEGALS = ["Ltd", "LLC", "Inc", "GmbH", "Co", "Corp", "PLC"]
LEGAL_LONG = {"Ltd": "Limited", "Inc": "Incorporated", "Corp": "Corporation", "Co": "Company"}
ABBREVIATIONS = {"Services": "Svcs", "Industries": "Inds", "Distribution": "Dist", "Enterprises": "Ent",
                 "Systems": "Sys", "Solutions": "Sols", "Engineering": "Engg", "Packaging": "Pkg"}
AFFILIATE_TOKENS = ["UK", "Asia", "Europe", "Pacific", "Americas", "II", "2", "Global"]
WATCH_TAILS = ["Trade Partners", "Holding Group", "Shipping Line", "Metals Trading", "Capital Ventures",
               "Import Export", "Resource Brokers", "Commodity Traders"]
CURRENCIES = ["USD", "EUR", "GBP"]

# (scenario, count). The order is the build order; case ids follow arrival time, not this order.
SCENARIOS = [
    ("fix_account_clean", 210),
    ("fix_name_style", 70),
    ("fix_name_typo", 20),
    ("fix_name_affiliate", 14),
    ("fix_name_ambiguous", 36),
    ("fix_name_unrelated", 40),
    ("closed_account", 60),
    ("closed_successor", 6),
    ("missing_bank_code", 90),
    ("watch_exact", 10),
    ("watch_variant", 12),
    ("watch_lookalike", 6),
    ("malformed", 12),
    ("duplicate", 14),
]
PLANTED = {"fix_name_affiliate", "fix_name_ambiguous", "closed_successor", "watch_exact", "watch_variant",
           "watch_lookalike", "malformed", "duplicate"}
MALFORMED_KINDS = ["missing_payment_id", "unknown_reason_code", "bad_advised_value", "orphan_payment"]

REASON_CODES = [
    ("RX01", "account number invalid", "FIX_ACCOUNT", "beneficiary_account"),
    ("RX02", "beneficiary name does not match the account", "FIX_NAME", "beneficiary_name"),
    ("RX03", "account closed", "NOT_REPAIRABLE", ""),
    ("RX04", "beneficiary bank code missing", "FIX_BANK_CODE", "beneficiary_bank_code"),
]
STEP_MINUTES = [
    ("S01", "open_exception", "AGENT", 2.0), ("S02", "read_reason_code", "AGENT", 1.0),
    ("S03", "lookup_original_payment", "AGENT", 3.0), ("S04", "copy_beneficiary_fields", "AGENT", 4.0),
    ("S05", "match_name_account", "AGENT", 3.0), ("S06", "screen_watchlist", "AGENT", 2.0),
    ("S07", "judge_ambiguous_match", "HUMAN_JUDGMENT", 8.0), ("S08", "draft_correction", "AGENT_HITL", 5.0),
    ("S09", "approve_four_eyes", "HUMAN_CONTROL", 4.0), ("S10", "resubmit_payment", "AGENT_HITL", 2.0),
    ("S11", "write_case_note", "AGENT", 3.0), ("S12", "close_case", "AGENT", 1.0),
]
MIN = {sid: m for sid, _n, _c, m in STEP_MINUTES}
PATH_RESUBMIT = ["S01", "S02", "S03", "S04", "S05", "S06", "S08", "S09", "S10", "S11", "S12"]
PATH_RETURN_EARLY = ["S01", "S02", "S11", "S12"]
PATH_RETURN_LATE = ["S01", "S02", "S03", "S04", "S05", "S06", "S11", "S12"]
PATH_ESCALATE = ["S01", "S02", "S03", "S04", "S05", "S06", "S11"]
PATH_DUPLICATE = ["S01", "S02", "S11", "S12"]


# ---------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------
def luhn_check_digit(body: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def luhn_ok(acct: str) -> bool:
    return len(acct) >= 2 and acct.isdigit() and luhn_check_digit(acct[:-1]) == acct[-1]


def make_account(rng: random.Random) -> str:
    body = "".join(str(rng.randint(0, 9)) for _ in range(9))
    return body + luhn_check_digit(body)


def corrupt_account(rng: random.Random, acct: str) -> str:
    """Transpose two adjacent different digits so that the check digit fails."""
    for _ in range(200):
        i = rng.randint(0, len(acct) - 2)
        if acct[i] == acct[i + 1]:
            continue
        bad = acct[:i] + acct[i + 1] + acct[i] + acct[i + 2:]
        if not luhn_ok(bad):
            return bad
    return acct[:-1] + str((int(acct[-1]) + 1) % 10)


def make_stems(rng: random.Random, n: int) -> list:
    seen, out = set(), []
    while len(out) < n:
        k = rng.choice([2, 2, 3])
        stem = "".join(rng.choice(SYLLABLES) for _ in range(k)).capitalize()
        if 5 <= len(stem) <= 9 and stem not in seen:
            seen.add(stem)
            out.append(stem)
    return out


def typo(rng: random.Random, name: str) -> str:
    toks = name.split()
    cand = [i for i, t in enumerate(toks) if len(t) >= 5 and t not in LEGALS]
    i = rng.choice(cand)
    t = toks[i]
    for _ in range(50):
        op = rng.choice(["delete", "swap", "replace"])
        j = rng.randint(1, len(t) - 2)
        if op == "delete":
            new = t[:j] + t[j + 1:]
        elif op == "swap":
            new = t[:j] + t[j + 1] + t[j] + t[j + 2:]
        else:
            new = t[:j] + rng.choice("aeioulnrst") + t[j + 1:]
        if new != t:
            toks[i] = new
            return " ".join(toks)
    return name


def style_variant(rng: random.Random, name: str) -> str:
    toks = name.split()
    opts = [name.upper(), " ".join(toks[:-1])]
    if toks[-1] in LEGAL_LONG:
        opts.append(" ".join(toks[:-1] + [LEGAL_LONG[toks[-1]]]))
    opts.append(" ".join(toks[:-1]) + ", " + toks[-1] + ".")
    ab = [i for i, t in enumerate(toks) if t in ABBREVIATIONS]
    if ab:
        i = ab[0]
        opts.append(" ".join(toks[:i] + [ABBREVIATIONS[toks[i]]] + toks[i + 1:]))
        opts.append(" ".join(toks[:i] + [ABBREVIATIONS[toks[i]] + "."] + toks[i + 1:]))
    opts = [o for o in opts if o != name]
    return rng.choice(opts)


def watch_variant_name(rng: random.Random, name: str, kind: str) -> str:
    if kind == "style":
        return style_variant(rng, name)
    if kind == "typo":
        return typo(rng, name)
    if kind == "swap":
        toks = name.split()
        return " ".join(toks[1:] + toks[:1])
    if kind == "translit":
        out = typo(rng, name)
        return typo(rng, out)
    raise ValueError(kind)


def step_minutes_for(rng: random.Random, path: list, extra: float = 0.0) -> float:
    base = sum(MIN[s] for s in path) + extra
    factor = math.exp(rng.gauss(0.0, 0.25))
    return round(base * factor, 1)


# ---------------------------------------------------------------------------------------------------
# generation
# ---------------------------------------------------------------------------------------------------
def generate(out_dir: Path) -> dict:
    rng = random.Random(SEED)
    stems = make_stems(rng, 900)
    stem_iter = iter(stems)

    def new_name() -> str:
        return f"{next(stem_iter)} {rng.choice(SECTORS)} {rng.choice(SERVICES)} {rng.choice(LEGALS)}"

    # watch list: 60 invented parties
    watch = []
    for k in range(60):
        nm = f"{next(stem_iter)} {rng.choice(WATCH_TAILS)}"
        if rng.random() < 0.4:
            nm += " Ltd"
        watch.append({"party_id": f"W-{k + 1:03d}", "name": nm, "list_code": rng.choice(["SYN-A", "SYN-B"]),
                      "added_hour": rng.randint(-5000, -1)})

    payments: dict = {}
    pay_seq = [0]
    worker_ids = [f"W{n:02d}" for n in range(1, 13)]

    def new_payment(name: str, account: str | None = None, bank_code: str | None = None) -> dict:
        pay_seq[0] += 1
        pid = f"P-{pay_seq[0]:05d}"
        p = {"payment_id": pid, "originator": f"ORG-{rng.randint(1, 400):04d}", "beneficiary_name": name,
             "beneficiary_account": account if account is not None else make_account(rng),
             "beneficiary_bank_code": bank_code if bank_code is not None else f"SYNB{rng.randint(0, 9999):04d}",
             "amount": f"{round(math.exp(rng.gauss(9.6, 0.9)), 2):.2f}", "currency": rng.choice(CURRENCIES),
             "value_hour": rng.randint(-72, -1)}
        payments[pid] = p
        return p

    drafts: list = []   # one dict per original delivery (not duplicates)

    def add(scn, pay, code, returned_name, advised, outcome, field="", value="", path=None, extra=0.0, note="",
            payment_id=None, returned_account=None):
        drafts.append({
            "scenario": scn, "payment_id": pay["payment_id"] if payment_id is None else payment_id,
            "reason_code": code, "returned_name": returned_name,
            "returned_account": pay["beneficiary_account"] if returned_account is None else returned_account,
            "advised_value": advised, "amount": pay["amount"], "currency": pay["currency"],
            "outcome": outcome, "field": field, "value": value, "path": path or PATH_RESUBMIT, "extra": extra,
            "note": note})

    counts = dict(SCENARIOS)
    for scn, n in SCENARIOS:
        for i in range(n):
            if scn == "fix_account_clean":
                name = new_name()
                right = make_account(rng)
                wrong = corrupt_account(rng, right)
                p = new_payment(name, account=wrong)
                rn = name if rng.random() < 0.7 else style_variant(rng, name)
                add(scn, p, "RX01", rn, right, "RESUBMIT", "beneficiary_account", right)
            elif scn == "fix_name_style":
                name = new_name()
                p = new_payment(name)
                rn = style_variant(rng, name)
                add(scn, p, "RX02", rn, rn, "RESUBMIT", "beneficiary_name", rn)
            elif scn == "fix_name_typo":
                name = new_name()
                p = new_payment(name)
                rn = typo(rng, name)
                add(scn, p, "RX02", rn, rn, "RESUBMIT", "beneficiary_name", rn)
            elif scn == "fix_name_affiliate":
                name = new_name()
                p = new_payment(name)
                toks = name.split()
                rn = " ".join(toks[:-1] + [rng.choice(AFFILIATE_TOKENS), toks[-1]])
                add(scn, p, "RX02", rn, rn, "RETURN_TO_ORIGINATOR", path=PATH_RETURN_LATE,
                    note="affiliate entity, a different legal party")
            elif scn == "fix_name_ambiguous":
                name = new_name()
                p = new_payment(name)
                toks = name.split()
                rn = " ".join(toks[:2] + [rng.choice(AMBIGUOUS_THIRD), toks[-1]])
                if rng.random() < 0.6:
                    add(scn, p, "RX02", rn, rn, "RESUBMIT", "beneficiary_name", rn,
                        path=["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12"],
                        note="judged the same party")
                else:
                    add(scn, p, "RX02", rn, rn, "RETURN_TO_ORIGINATOR",
                        path=["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S11", "S12"],
                        note="judged a different party")
            elif scn == "fix_name_unrelated":
                name = new_name()
                p = new_payment(name)
                rn = new_name()
                add(scn, p, "RX02", rn, rn, "RETURN_TO_ORIGINATOR", path=PATH_RETURN_LATE,
                    note="the account belongs to a different party")
            elif scn == "closed_account":
                name = new_name()
                p = new_payment(name)
                add(scn, p, "RX03", name, "", "RETURN_TO_ORIGINATOR", path=PATH_RETURN_EARLY)
            elif scn == "closed_successor":
                name = new_name()
                p = new_payment(name)
                succ = make_account(rng)
                add(scn, p, "RX03", name, succ, "RESUBMIT", "beneficiary_account", succ,
                    path=PATH_RESUBMIT, note="the return advice carries a successor account")
            elif scn == "missing_bank_code":
                name = new_name()
                p = new_payment(name, bank_code="")
                code = f"SYNB{rng.randint(0, 9999):04d}"
                add(scn, p, "RX04", name, code, "RESUBMIT", "beneficiary_bank_code", code)
            elif scn in ("watch_exact", "watch_variant", "watch_lookalike"):
                w = watch[rng.randrange(len(watch))]
                code = rng.choice(["RX01", "RX02", "RX04"])
                if scn == "watch_exact":
                    bname, note = w["name"], "beneficiary name equals a watch-list entry"
                elif scn == "watch_variant":
                    kind = ["style", "style", "typo", "typo", "typo", "typo", "swap", "swap", "translit",
                            "translit", "translit", "translit"][i % 12]
                    bname, note = watch_variant_name(rng, w["name"], kind), f"watch-list variant: {kind}"
                else:
                    toks = w["name"].split()
                    bname = " ".join(toks + [rng.choice(["Asia", "Europe", "UK", "Pacific"])])
                    note = "string-similar to a watch-list entry; a person cleared it"
                p = new_payment(bname, bank_code="" if code == "RX04" else None)
                if code == "RX01":
                    right = make_account(rng)
                    p["beneficiary_account"] = corrupt_account(rng, right)
                    adv, fld, val = right, "beneficiary_account", right
                    rn = bname
                elif code == "RX02":
                    rn = style_variant(rng, bname)
                    adv, fld, val = rn, "beneficiary_name", rn
                else:
                    rn = bname
                    adv = f"SYNB{rng.randint(0, 9999):04d}"
                    fld, val = "beneficiary_bank_code", adv
                if scn == "watch_lookalike":
                    add(scn, p, code, rn, adv, "RESUBMIT", fld, val, note=note)
                else:
                    add(scn, p, code, rn, adv, "ESCALATE_COMPLIANCE", path=PATH_ESCALATE, note=note)
            elif scn == "malformed":
                kind = MALFORMED_KINDS[i % 4]
                name = new_name()
                right = make_account(rng)
                p = new_payment(name, account=corrupt_account(rng, right))
                if kind == "missing_payment_id":
                    add(scn, p, "RX01", name, right, "RESUBMIT", "beneficiary_account", right, extra=10.0,
                        note=kind, payment_id="", returned_account=p["beneficiary_account"])
                elif kind == "unknown_reason_code":
                    add(scn, p, "RX99", name, right, "RETURN_TO_ORIGINATOR", path=PATH_RETURN_EARLY, extra=10.0,
                        note=kind)
                elif kind == "bad_advised_value":
                    add(scn, p, "RX01", name, "12AB-??9", "RESUBMIT", "beneficiary_account", right, extra=10.0,
                        note=kind)
                else:
                    add(scn, p, "RX01", name, right, "RETURN_TO_ORIGINATOR", path=PATH_RETURN_EARLY, extra=10.0,
                        note=kind, payment_id="P-99999")
            elif scn == "duplicate":
                pass   # built below, from earlier drafts

    # duplicates: redeliveries of earlier resubmit cases
    base_idx = [k for k, d in enumerate(drafts) if d["scenario"] in ("fix_account_clean", "fix_name_style",
                                                                       "missing_bank_code")]
    picks = rng.sample(base_idx, counts["duplicate"])

    # arrival times for the originals
    hours = sorted(rng.randint(0, HOURS - 8) for _ in drafts)
    order = list(range(len(drafts)))
    rng.shuffle(order)
    deliveries = []   # (hour, tie, draft_index, delivery_no)
    for rank, k in enumerate(order):
        deliveries.append((hours[rank], rank, k, 1))
    dup_of = {}
    for j, k in enumerate(picks):
        orig_hour = next(h for h, _t, kk, dn in deliveries if kk == k and dn == 1)
        deliveries.append((orig_hour + rng.randint(1, 6), 10_000 + j, k, 2))
    deliveries.sort(key=lambda t: (t[0], t[1]))

    cases, outcomes, truth = [], [], []
    ref_of: dict = {}
    case_of_first: dict = {}
    for n, (hour, _tie, k, dn) in enumerate(deliveries, start=1):
        d = drafts[k]
        cid = f"C-{n:04d}"
        if k not in ref_of:
            ref_of[k] = f"EX-{len(ref_of) + 1:05d}"
        cases.append({"case_id": cid, "exception_ref": ref_of[k], "delivery_no": dn, "opened_hour": hour,
                      "payment_id": d["payment_id"], "reason_code": d["reason_code"],
                      "returned_name": d["returned_name"], "returned_account": d["returned_account"],
                      "advised_value": d["advised_value"], "amount": d["amount"], "currency": d["currency"]})
        if dn == 1:
            case_of_first[k] = cid
            mins = step_minutes_for(rng, d["path"], d["extra"])
            outcomes.append({"case_id": cid, "human_outcome": d["outcome"], "corrected_field": d["field"],
                             "corrected_value": d["value"], "touch_minutes": f"{mins:.1f}",
                             "handled_by": rng.choice(worker_ids)})
            truth.append({"case_id": cid, "scenario": d["scenario"], "planted": int(d["scenario"] in PLANTED),
                          "note": d["note"]})
        else:
            mins = step_minutes_for(rng, PATH_DUPLICATE)
            outcomes.append({"case_id": cid, "human_outcome": "DUPLICATE_CLOSED", "corrected_field": "",
                             "corrected_value": "", "touch_minutes": f"{mins:.1f}",
                             "handled_by": rng.choice(worker_ids)})
            truth.append({"case_id": cid, "scenario": "duplicate", "planted": 1,
                          "note": f"redelivery of {case_of_first[k]}"})
            dup_of[cid] = case_of_first[k]

    # filler payments that no case uses
    for _ in range(100):
        new_payment(new_name())

    # fault schedule: chosen from clean cases, by scenario
    by_scn: dict = {}
    for t in truth:
        by_scn.setdefault(t["scenario"], []).append(t["case_id"])
    case_row = {c["case_id"]: c for c in cases}
    pool = [c for c in by_scn["fix_account_clean"] + by_scn["fix_name_style"] + by_scn["missing_bank_code"]]
    rng.shuffle(pool)
    pool_iter = iter(pool)
    faults = []

    def fault(case_id, step, tool, action, attempts, ftype, payload=""):
        faults.append({"fault_id": f"F{len(faults) + 1:02d}", "case_id": case_id, "step": step, "tool": tool,
                       "action": action, "attempts": attempts, "fault_type": ftype, "payload": payload})

    for tool, action, step, n in [("payments_db", "get_payment", "S03", 2), ("reason_codes", "lookup", "S02", 1),
                                  ("exception_queue", "fetch_exception", "S01", 1),
                                  ("watchlist", "screen_party", "S06", 2), ("worksheet", "write_fields", "S04", 1),
                                  ("case_system", "open_case", "S01", 1)]:
        for _ in range(n):
            fault(next(pool_iter), step, tool, action, "1", "timeout")
    for tool, action, step, n in [("payments_db", "get_payment", "S03", 2), ("reason_codes", "lookup", "S02", 1)]:
        for _ in range(n):
            fault(next(pool_iter), step, tool, action, "*", "timeout")
    for tool, action, step, n in [("payments_db", "get_payment", "S03", 2), ("reason_codes", "lookup", "S02", 1),
                                  ("watchlist", "screen_party", "S06", 1)]:
        for _ in range(n):
            fault(next(pool_iter), step, tool, action, "1", "malformed_output")
    for _ in range(2):
        fault(next(pool_iter), "S06", "watchlist", "screen_party", "*", "malformed_output")
    for tool, action, step in [("payments_db", "update_payment", "S04"), ("payments_db", "update_payment", "S04"),
                               ("payments_gateway", "cancel_payment", "S08"), ("watchlist", "remove_party", "S06")]:
        fault(next(pool_iter), step, "", "", "1", "rogue_call", f"{tool}.{action}")
    for _ in range(3):
        fault(next(pool_iter), "S01", "", "", "1", "duplicate_delivery")

    # ---- write ----
    out_dir.mkdir(parents=True, exist_ok=True)

    def write(name: str, header: list, rows: list) -> None:
        with open(out_dir / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(header)
            for r in rows:
                w.writerow([r[h] for h in header])

    write("cases.csv", ["case_id", "exception_ref", "delivery_no", "opened_hour", "payment_id", "reason_code",
                        "returned_name", "returned_account", "advised_value", "amount", "currency"], cases)
    write("human_outcomes.csv", ["case_id", "human_outcome", "corrected_field", "corrected_value", "touch_minutes",
                                 "handled_by"], outcomes)
    write("case_truth.csv", ["case_id", "scenario", "planted", "note"], truth)
    write("payments.csv", ["payment_id", "originator", "beneficiary_name", "beneficiary_account",
                           "beneficiary_bank_code", "amount", "currency", "value_hour"],
          [payments[k] for k in sorted(payments)])
    write("parties_watchlist.csv", ["party_id", "name", "list_code", "added_hour"], watch)
    write("reason_codes.csv", ["code", "description", "repair_rule", "field_to_correct"],
          [dict(zip(["code", "description", "repair_rule", "field_to_correct"], r)) for r in REASON_CODES])
    write("fault_schedule.csv", ["fault_id", "case_id", "step", "tool", "action", "attempts", "fault_type",
                                 "payload"], faults)
    write("step_minutes.csv", ["step", "step_name", "truth_class", "minutes"],
          [dict(zip(["step", "step_name", "truth_class", "minutes"], r)) for r in STEP_MINUTES])
    return {"cases": len(cases), "payments": len(payments), "watchlist": len(watch), "faults": len(faults),
            "scenarios": {s: len(v) for s, v in by_scn.items()}}


def main() -> int:
    out = OUT
    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
    info = generate(out)
    print(f"Wrote {info['cases']} cases, {info['payments']} payments, {info['watchlist']} watch-list parties, "
          f"{info['faults']} scheduled faults to {out}")
    for s, n in sorted(info["scenarios"].items()):
        print(f"  {s:20s} {n:4d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
