"""Step 2 - The basic approach: an RPA-style script that follows the happy path with no controls.

I wrote this script to stand for the usual first scripted version of a rule-based queue: read the exception, look
up the reason, look up the payment, copy fields through a spreadsheet, compare names, screen the party,
apply the fix, resubmit, write a note, close. It has no scope checks, no gates, no audit trail, and it
keeps going when a case throws an error. It runs against the same simulated systems as the kit.

It is one script I wrote, not a survey of scripts. What it does wrong is a property of this script.
Run from src/:  python3 step_02_script_without_controls.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentkit.data_io import load_world  # noqa: E402
from agentkit.environment import SimEnvironment  # noqa: E402
from common import table, write_csv, write_json  # noqa: E402

SHEET_FIELDS = ("beneficiary_name", "beneficiary_account", "beneficiary_bank_code", "amount", "currency")

# What this script leaves behind for whoever owns it next. Step 3 checks this list against the brief.
ARTIFACTS = ["the script itself", "a nightly count of cases processed"]


class UncontrolledScript:
    def __init__(self, env: SimEnvironment):
        self.env = env
        self.log = []          # the script's only record: one line per resubmission
        self.decisions = []    # instrumentation added by this harness so step 3 can count decisions; the script
        self.actions = {}      # does not write these two. actions: what the script ended up doing per case

    def decide(self, cid: str, kind: str) -> None:
        self.decisions.append((cid, kind))

    def done(self, cid: str, action: str, field: str = "", value: str = "", payload: dict = None) -> None:
        self.actions[cid] = {"action": action, "field": field, "value": value, "payload": payload or {}}

    def run(self, case_ids) -> str:
        n = 0
        for cid in case_ids:
            try:
                self.handle(cid)
                n += 1
            except Exception:
                pass            # keep the nightly job running
        return f"Done. {n} cases processed."

    def handle(self, cid: str) -> None:
        env = self.env
        exc = env.fetch_exception(cid)
        env.open_case(cid, exc["exception_ref"])
        rule = env.lookup(exc["reason_code"])
        self.decide(cid, "route_by_reason_code")
        if rule["repair_rule"] == "NOT_REPAIRABLE":
            env.append_note(cid, "account closed, returned to originator")
            env.close_case(cid, "RETURN_TO_ORIGINATOR")
            self.decide(cid, "return_to_originator")
            self.done(cid, "RETURN_TO_ORIGINATOR")
            return
        pay = env.get_payment(exc["payment_id"])
        sheet = env.write_fields(cid, {k: pay[k] for k in SHEET_FIELDS}, as_text=False)["stored"]
        same = pay["beneficiary_name"] == exc["returned_name"]
        self.decide(cid, "compare_names")
        listed = {w["name"].upper() for w in env.export_list()}
        hit = exc["returned_name"].upper() in listed or pay["beneficiary_name"].upper() in listed
        self.decide(cid, "screen_watch_list")
        if hit:
            env.append_note(cid, "name is on the watch list")
            env.escalate_case(cid, "compliance", "watch-list hit")
            self.decide(cid, "escalate")
            self.done(cid, "ESCALATE_COMPLIANCE")
            return
        field, value = rule["field_to_correct"], exc["advised_value"]
        self.decide(cid, "draft_correction")
        env.update_payment(exc["payment_id"], field, value)          # fix it at the source
        payload = dict(sheet)
        payload[field] = value
        env.resubmit(exc["payment_id"], payload)
        self.decide(cid, "resubmit")
        self.log.append(f"RESUBMITTED {exc['payment_id']} {field}")
        env.append_note(cid, f"{field} corrected; names {'match' if same else 'differ'}")
        env.close_case(cid, "RESUBMIT")
        self.done(cid, "RESUBMIT", field, value, payload)


def run_script(world: dict, case_ids=None) -> dict:
    env = SimEnvironment.from_world(world)
    ids = list(case_ids) if case_ids is not None else [c["case_id"] for c in world["cases"]]
    s = UncontrolledScript(env)
    banner = s.run(ids)
    for cid in ids:
        s.actions.setdefault(cid, {"action": "SKIPPED_SILENTLY", "field": "", "value": "", "payload": {}})
    return {"env": env, "script": s, "banner": banner, "ids": ids}


def summarize(world: dict) -> dict:
    run = run_script(world)
    env, s = run["env"], run["script"]
    acts = Counter(a["action"] for a in s.actions.values())
    calls = Counter((sys_, act) for sys_, act, _acc, _c in env.call_log)
    return {"banner": run["banner"], "cases": len(run["ids"]), "actions": dict(sorted(acts.items())),
            "resubmissions": len(env.ledger), "log_lines": len(s.log), "decisions": len(s.decisions),
            "calls": {f"{a}.{b}": n for (a, b), n in sorted(calls.items())}}


def main() -> int:
    world = load_world()
    run = run_script(world)
    env, s = run["env"], run["script"]
    sm = summarize(world)
    print("=" * 100)
    print("Step 2 - The basic approach: a script on the happy path, no controls")
    print("=" * 100)
    print("\nThe script's own output when the job finishes:")
    print(f"  {run['banner']}")
    print("\nWhat it actually did (counted from the simulated systems, not from the script's output):")
    rows = [(k, v) for k, v in sm["actions"].items()]
    print(table(rows, ["ended as", "cases"]))
    print(f"\n  resubmissions sent to the payments gateway   {sm['resubmissions']}")
    print(f"  lines in the script's own log                {sm['log_lines']}")
    print("\nCalls the script made to each system action:")
    rows = [(k, v) for k, v in sm["calls"].items()]
    print(table(rows, ["system.action", "calls"]))
    print("\nIt finishes without an error and reports a count. Step 3 measures what the count does not say.")
    write_csv("step_02_script_results.csv", ["case_id", "action", "field", "value"],
              [(c, a["action"], a["field"], a["value"]) for c, a in sorted(s.actions.items())])
    write_json("step_02_summary.json", sm)
    print("\nWrote src/out/step_02_script_results.csv and step_02_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
