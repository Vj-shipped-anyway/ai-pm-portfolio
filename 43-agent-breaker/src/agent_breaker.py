"""agent_breaker: a circuit breaker for an agent. It trips on failure, holds the agent's calls for a person,
lets a few probe calls through to test recovery, and writes a hash-chained log that can be replayed to
prove what it did. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 agent_breaker.py --demo
    python3 agent_breaker.py run EVENTS.csv [--controls CONTROLS.csv] [--policy POLICY.csv] [--log OUT.jsonl]
                                            [--agent NAME] [--fail-on trip|never]
    python3 agent_breaker.py verify LOG.jsonl [--policy POLICY.csv] [--head HASH]

Exit status: 0 when nothing tripped (run) or the log checks out (verify); 1 when the breaker tripped (run) or
the log does not check out (verify); 2 for bad or malformed input.

States, one breaker per agent (the agent is a field in the data, never read from a name):
    CLOSED       calls go to the agent. It trips to OPEN on a critical failure, on N failures in a row, or on a
                 failure rate over a time window (the rate is only scored once the window holds enough calls).
    OPEN         calls go to the human queue for the hold time. A probe failure doubles the next hold, up to a cap.
    HALF_OPEN    the next calls go to the agent as probes. All must pass to close; one failure re-opens.
    FORCED_OPEN  an operator engaged the switch. Nothing closes it but a release, and a release goes to HALF_OPEN.
A warn is logged when the rate reaches a fraction of the trip level; it alerts a person and switches nothing.
OPEN becomes HALF_OPEN when the first call arrives after the hold, so a transition is stamped with that call's time.

Library, one call in flight per agent:
    fleet = Fleet(default_policy())
    rec = fleet.admit(t_min, "payment-repair", "case-1")       # rec["route"] is "agent" or "human_queue"
    if rec["route"] == "agent":
        fleet.record(rec, "ok")                                 # or "fail", with a failure kind as the third argument

Events CSV:   t_min,agent,case_id,outcome,failure_kind   (t_min whole minutes, rows in time order, outcome ok|fail)
Controls CSV: t_min,agent,action,by,reason              (action engage|release)
Policy CSV:   parameter,value                           (other columns allowed; unknown parameters are refused)

When the events file is a recorded history, a call the breaker holds still has its recorded outcome in the file;
the breaker never sees it, and the log records that call without an outcome. That is a back-test, not a live run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import deque

CLOSED, OPEN, HALF_OPEN, FORCED_OPEN = "CLOSED", "OPEN", "HALF_OPEN", "FORCED_OPEN"
GENESIS = "0" * 64
KINDS = ("policy", "call", "transition", "warn", "control")
EVENT_COLS = ("t_min", "agent", "case_id", "outcome", "failure_kind")
CONTROL_COLS = ("t_min", "agent", "action", "by", "reason")

# name: (cast, default). Every default is an assumption; data/policy.csv says where each came from.
PARAMS = {
    "window_min": (int, 30),
    "min_window_calls": (int, 10),
    "trip_failure_rate": (float, 0.50),
    "warn_fraction": (float, 0.75),
    "clear_fraction": (float, 0.50),
    "consecutive_trip": (int, 5),
    "critical_kinds": (str, "scope_violation"),
    "hold_min": (int, 30),
    "hold_backoff": (int, 2),
    "max_hold_min": (int, 240),
    "probe_calls": (int, 3),
}


def safe(text) -> str:
    """One printable line from untrusted text: control characters and line separators become escapes."""
    out = []
    for ch in str(text):
        o = ord(ch)
        if ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 32 or 127 <= o < 160 or o in (0x2028, 0x2029):
            out.append("\\x%02x" % o if o < 256 else "\\u%04x" % o)
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------- policy
def default_policy() -> dict:
    return {k: v[1] for k, v in PARAMS.items()}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_policy(p) -> dict:
    """Return a validated copy of a policy, or raise ValueError."""
    if not isinstance(p, dict) or set(p) != set(PARAMS):
        raise ValueError("policy: expected exactly these parameters: " + ", ".join(sorted(PARAMS)))
    for k, (cast, _) in PARAMS.items():
        v = p[k]
        ok = isinstance(v, str) if cast is str else (_is_num(v) if cast is float else (isinstance(v, int) and not isinstance(v, bool)))
        if not ok:
            raise ValueError(f"policy: {k} must be a {cast.__name__}")
    if not 0 < p["trip_failure_rate"] <= 1:
        raise ValueError("policy: trip_failure_rate must be above 0 and at most 1")
    if not 0 < p["warn_fraction"] <= 1 or not 0 < p["clear_fraction"] < p["warn_fraction"]:
        raise ValueError("policy: need 0 < clear_fraction < warn_fraction <= 1")
    for k in ("window_min", "min_window_calls", "consecutive_trip", "hold_min", "probe_calls"):
        if p[k] < 1:
            raise ValueError(f"policy: {k} must be at least 1")
    if p["hold_backoff"] < 1 or p["max_hold_min"] < p["hold_min"]:
        raise ValueError("policy: need hold_backoff >= 1 and max_hold_min >= hold_min")
    return dict(p)


def _read_rows(path: str, required, label: str) -> list:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fields = reader.fieldnames
            rows = list(reader)
    except csv.Error as e:
        raise ValueError(f"{label}: not readable as CSV: {e}")
    if not fields:
        raise ValueError(f"{label}: the file is empty")
    missing = [c for c in required if c not in fields]
    if missing:
        raise ValueError(f"{label}: missing column(s) {', '.join(missing)}")
    for n, row in enumerate(rows, 1):
        if None in row or any(row[c] is None for c in required):
            raise ValueError(f"{label} row {n}: wrong number of fields (a truncated or damaged row)")
    return rows


def _minutes(text: str, where: str) -> int:
    s = text.strip()
    if not (s.isascii() and s.isdigit()):
        raise ValueError(f"{where}: t_min must be a whole number of minutes, 0 or more")
    return int(s)


def load_policy(path: str) -> dict:
    p = default_policy()
    seen = set()
    for r in _read_rows(path, ("parameter", "value"), "policy"):
        name = r["parameter"].strip()
        if name not in PARAMS:
            raise ValueError(f"policy: unknown parameter {safe(name)!r}")
        if name in seen:
            raise ValueError(f"policy: {name} appears twice")
        seen.add(name)
        cast = PARAMS[name][0]
        try:
            p[name] = r["value"].strip() if cast is str else cast(r["value"].strip())
        except ValueError:
            raise ValueError(f"policy: {name} is not a valid {cast.__name__}")
    return check_policy(p)


def load_events(path: str) -> list:
    rows = _read_rows(path, EVENT_COLS, "events")
    if not rows:
        raise ValueError("events: the file has a header and no rows")
    out, last = [], 0
    for n, r in enumerate(rows, 1):
        t = _minutes(r["t_min"], f"events row {n}")
        if t < last:
            raise ValueError(f"events row {n}: rows must be in time order")
        last = t
        if not r["agent"].strip() or not r["case_id"].strip():
            raise ValueError(f"events row {n}: agent and case_id must not be blank")
        if r["outcome"] not in ("ok", "fail"):
            raise ValueError(f"events row {n}: outcome must be ok or fail")
        out.append({"t": t, "agent": r["agent"], "case": r["case_id"], "outcome": r["outcome"],
                    "kind": (r["failure_kind"] or None) if r["outcome"] == "fail" else None})
    return out


def load_controls(path: str) -> list:
    out, last = [], 0
    for n, r in enumerate(_read_rows(path, CONTROL_COLS, "controls"), 1):
        t = _minutes(r["t_min"], f"controls row {n}")
        if t < last:
            raise ValueError(f"controls row {n}: rows must be in time order")
        last = t
        if r["action"] not in ("engage", "release") or not r["agent"].strip():
            raise ValueError(f"controls row {n}: need an agent and an action of engage or release")
        out.append({"t": t, "agent": r["agent"], "action": r["action"], "by": r["by"], "reason": r["reason"]})
    return out


# ---------------------------------------------------------------- audit log
def _digest(prev: str, core: dict) -> str:
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256((prev + blob).encode("utf-8")).hexdigest()


class AuditLog:
    """Append-only. Each event carries the hash of the one before it. Time is the stream's minute, never the clock."""

    def __init__(self):
        self.events = []
        self.head = GENESIS

    def append(self, t, agent: str, kind: str, data: dict) -> dict:
        core = {"seq": len(self.events) + 1, "t": t, "agent": agent, "kind": kind, "data": data}
        ev = dict(core, prev=self.head, hash=_digest(self.head, core))
        self.head = ev["hash"]
        self.events.append(ev)
        return ev

    def lines(self) -> list:
        return [json.dumps(e, sort_keys=True, ensure_ascii=True) for e in self.events]


# ---------------------------------------------------------------- the breaker
class Breaker:
    def __init__(self, agent: str, policy: dict, log: AuditLog):
        self.agent, self.p, self.log = agent, policy, log
        self.critical = frozenset(k for k in policy["critical_kinds"].split(";") if k)
        self.state = CLOSED
        self.window = deque()
        self.consecutive = 0
        self.opened_at = 0
        self.hold = policy["hold_min"]
        self.probes_ok = 0
        self.warned = False

    def _move(self, t: int, to: str, rule: str, **evidence) -> None:
        self.log.append(t, self.agent, "transition", {"from": self.state, "to": to, "rule": rule, "evidence": evidence})
        self.state = to

    def _reset(self) -> None:
        self.window.clear()
        self.consecutive = 0
        self.warned = False
        self.hold = self.p["hold_min"]
        self.probes_ok = 0

    def admit(self, t: int) -> str:
        """Where the next call goes: 'agent' or 'human_queue'. May move OPEN to HALF_OPEN first."""
        if self.state == OPEN and t - self.opened_at >= self.hold:
            self.probes_ok = 0
            self._move(t, HALF_OPEN, "hold_elapsed", held_min=t - self.opened_at)
        return "agent" if self.state in (CLOSED, HALF_OPEN) else "human_queue"

    def report(self, t: int, outcome: str, kind) -> None:
        """The outcome of a call that went to the agent."""
        failed = outcome == "fail"
        if self.state == HALF_OPEN:
            if failed:
                self.hold = min(self.hold * self.p["hold_backoff"], self.p["max_hold_min"])
                self.opened_at = t
                self._move(t, OPEN, "probe_failed", probes_ok=self.probes_ok, next_hold_min=self.hold)
            else:
                self.probes_ok += 1
                if self.probes_ok >= self.p["probe_calls"]:
                    ok = self.probes_ok
                    self._reset()
                    self._move(t, CLOSED, "probes_passed", probes_ok=ok)
            return
        self.window.append((t, failed))
        while self.window and self.window[0][0] <= t - self.p["window_min"]:
            self.window.popleft()
        self.consecutive = self.consecutive + 1 if failed else 0
        n = len(self.window)
        f = sum(1 for _, x in self.window if x)
        rate = f / n
        ev = {"window_calls": n, "window_fails": f, "consecutive": self.consecutive, "rate": round(rate, 4)}
        scored = n >= self.p["min_window_calls"]
        rule = None
        if failed and kind in self.critical:
            rule, ev["failure_kind"] = "critical", kind
        elif self.consecutive >= self.p["consecutive_trip"]:
            rule = "consecutive"
        elif scored and rate >= self.p["trip_failure_rate"]:
            rule = "rate"
        if rule:
            self.opened_at = t
            self._move(t, OPEN, rule, **ev)
            return
        trip = self.p["trip_failure_rate"]
        if scored and rate >= trip * self.p["warn_fraction"] and not self.warned:
            self.warned = True
            self.log.append(t, self.agent, "warn", {"window_calls": n, "window_fails": f, "rate": round(rate, 4)})
        elif self.warned and (not scored or rate < trip * self.p["clear_fraction"]):
            self.warned = False

    def engage(self, t: int, by: str, reason: str) -> bool:
        changed = self.state != FORCED_OPEN
        self.log.append(t, self.agent, "control", {"action": "engage", "by": by, "reason": reason,
                                                   "effect": "engaged" if changed else "none"})
        if changed:
            self._move(t, FORCED_OPEN, "operator", by=by)
        return changed

    def release(self, t: int, by: str, reason: str) -> bool:
        changed = self.state == FORCED_OPEN
        self.log.append(t, self.agent, "control", {"action": "release", "by": by, "reason": reason,
                                                   "effect": "released" if changed else "none"})
        if changed:
            self._reset()
            self._move(t, HALF_OPEN, "operator_release", by=by)
        return changed


class Fleet:
    """One breaker per agent, one shared audit log."""

    def __init__(self, policy: dict):
        self.policy = check_policy(policy)
        self.log = AuditLog()
        self.log.append(None, "", "policy", dict(self.policy))
        self.breakers = {}
        self.in_flight = set()
        self.last_t = 0

    def _breaker(self, t: int, agent: str) -> Breaker:
        if t < self.last_t:
            raise ValueError("time went backwards: events and controls must be fed in time order")
        self.last_t = t
        if agent not in self.breakers:
            self.breakers[agent] = Breaker(agent, self.policy, self.log)
        return self.breakers[agent]

    def admit(self, t: int, agent: str, case: str) -> dict:
        """First half of a live call: decide where it goes. A held call is logged here. A call routed to the agent
        stays in flight, one per agent, until record() gives its outcome."""
        b = self._breaker(t, agent)
        if agent in self.in_flight:
            raise ValueError("a call for this agent is still in flight: record its outcome first")
        route = b.admit(t)
        rec = {"t": t, "agent": agent, "case": case, "route": route, "state": b.state}
        if route == "agent":
            self.in_flight.add(agent)
        else:
            self.log.append(t, agent, "call", {"case": case, "state": b.state, "route": route, "outcome": None,
                                               "failure_kind": None})
        return rec

    def record(self, rec: dict, outcome: str, kind=None) -> None:
        """Second half: the agent's outcome (ok|fail) for a call admit() sent to it."""
        if rec["agent"] not in self.in_flight or rec["route"] != "agent":
            raise ValueError("this call is not in flight to the agent")
        if outcome not in ("ok", "fail"):
            raise ValueError("outcome must be ok or fail")
        self.in_flight.discard(rec["agent"])
        self.log.append(rec["t"], rec["agent"], "call", {"case": rec["case"], "state": rec["state"], "route": "agent",
                                                         "outcome": outcome, "failure_kind": kind if outcome == "fail" else None})
        self.breakers[rec["agent"]].report(rec["t"], outcome, kind)

    def handle(self, t: int, agent: str, case: str, outcome, kind=None) -> dict:
        """admit() and record() in one step, for a recorded history. `outcome` is what the agent did (ok|fail); it is
        used, and logged, only when the call goes to the agent, so a held call may pass None. A Fleet that has
        raised is not reusable."""
        if outcome not in ("ok", "fail", None):
            raise ValueError("outcome must be ok or fail")
        rec = self.admit(t, agent, case)
        if rec["route"] == "agent":
            if outcome is None:
                raise ValueError("the call goes to the agent but no outcome was given")
            self.record(rec, outcome, kind)
        return rec

    def control(self, t: int, agent: str, action: str, by: str, reason: str) -> bool:
        b = self._breaker(t, agent)
        if action == "engage":
            return b.engage(t, by, reason)
        if action == "release":
            return b.release(t, by, reason)
        raise ValueError("action must be engage or release")


def run_stream(events: list, controls: list, policy: dict):
    """Feed events and controls in time order (a control goes first at a tied minute). Returns (fleet, records)."""
    fleet, records = Fleet(policy), []
    ci = 0
    for e in events:
        while ci < len(controls) and controls[ci]["t"] <= e["t"]:
            c = controls[ci]
            fleet.control(c["t"], c["agent"], c["action"], c["by"], c["reason"])
            ci += 1
        records.append(fleet.handle(e["t"], e["agent"], e["case"], e["outcome"], e["kind"]))
    for c in controls[ci:]:
        fleet.control(c["t"], c["agent"], c["action"], c["by"], c["reason"])
    return fleet, records


# ---------------------------------------------------------------- verification
def verify_log(lines: list, policy=None, head=None) -> list:
    """Check a log: the hash chain, then a replay of its calls and controls through a fresh breaker, which must
    reproduce every event, hash included. Returns a list of problems (empty means it checks out). Raises
    ValueError when the lines are not an audit log at all."""
    events = []
    for i, line in enumerate(lines, 1):
        try:
            ev = json.loads(line)
        except ValueError:
            raise ValueError(f"line {i}: not JSON")
        ok = (isinstance(ev, dict) and isinstance(ev.get("seq"), int) and isinstance(ev.get("agent"), str)
              and ev.get("kind") in KINDS and isinstance(ev.get("data"), dict) and "t" in ev
              and isinstance(ev.get("prev"), str) and isinstance(ev.get("hash"), str))
        if not ok:
            raise ValueError(f"line {i}: not an audit event")
        events.append(ev)
    if not events:
        raise ValueError("the log is empty")
    problems, prev = [], GENESIS
    for i, ev in enumerate(events, 1):
        core = {k: ev[k] for k in ("seq", "t", "agent", "kind", "data")}
        if ev["prev"] != prev or ev["seq"] != i:
            problems.append(f"line {i}: chain broken: a line before it was removed, added or reordered")
        elif _digest(ev["prev"], core) != ev["hash"]:
            problems.append(f"line {i}: content does not match its hash: the line was edited")
        prev = ev["hash"]
    if head is not None and events[-1]["hash"] != head:
        problems.append("head hash differs from the one supplied: the log was cut short, extended or rewritten")
    if problems:
        return problems
    for i, ev in enumerate(events, 1):
        d = ev["data"]
        if ev["kind"] == "call" and d.get("route") == "agent" and d.get("state") in (OPEN, FORCED_OPEN):
            problems.append(f"line {i}: a call reached the agent while the breaker was {d['state']}")
    logged = events[0]["data"] if events[0]["kind"] == "policy" else None
    if logged is None:
        return problems + ["line 1: the first event must be the policy"]
    if policy is not None and policy != logged:
        problems.append("the policy in the log differs from the policy supplied")
    try:
        fleet = Fleet(policy if policy is not None else logged)
    except ValueError as e:
        return problems + [f"line 1: {e}"]
    for i, ev in enumerate(events[1:], 2):
        d = ev["data"]
        try:
            if ev["kind"] == "call":
                fleet.handle(ev["t"], ev["agent"], d["case"], d["outcome"] if d["route"] == "agent" else None,
                             d["failure_kind"])
            elif ev["kind"] == "control":
                fleet.control(ev["t"], ev["agent"], d["action"], d["by"], d["reason"])
        except (KeyError, TypeError, ValueError) as e:
            return problems + [f"line {i}: the replay cannot take this event ({safe(e)})"]
    if len(fleet.log.events) != len(events):
        problems.append(f"replay produces {len(fleet.log.events)} events, the log has {len(events)}")
    for i, (mine, theirs) in enumerate(zip(fleet.log.events, events), 1):
        if mine != theirs:
            problems.append(f"line {i}: replay disagrees: the rules do not produce this event from the logged calls")
            break
    return problems


# ---------------------------------------------------------------- command line
def describe(ev: dict, policy: dict) -> str:
    d = ev["data"]
    if ev["kind"] == "warn":
        return f"WARN       {d['window_fails']} of {d['window_calls']} calls failed (rate {d['rate']}); a person is told, nothing switches"
    if ev["kind"] == "control":
        return f"control {d['action']} by {safe(d['by'])} had no effect: the breaker was {'already' if d['action'] == 'engage' else 'not'} held by an operator"
    e, rule = d["evidence"], d["rule"]
    text = {
        "consecutive": lambda: f"{e['consecutive']} failures in a row",
        "rate": lambda: f"{e['window_fails']} of {e['window_calls']} calls failed in the last {policy['window_min']} min",
        "critical": lambda: f"critical failure: {safe(e['failure_kind'])}",
        "hold_elapsed": lambda: f"hold of {e['held_min']} min is over, the next calls are probes",
        "probe_failed": lambda: f"probe failed after {e['probes_ok']} good, next hold {e['next_hold_min']} min",
        "probes_passed": lambda: f"{e['probes_ok']} probes passed",
        "operator": lambda: f"engaged by {safe(e['by'])}",
        "operator_release": lambda: f"released by {safe(e['by'])}, probes first",
    }[rule]()
    return f"{d['from']:<11} -> {d['to']:<11} {text}"


def report(fleet: Fleet, records: list, problems: list) -> int:
    """Print the run. Returns the number of trips (CLOSED to OPEN)."""
    by_agent = {agent: {"calls": 0, "held": 0} for agent in fleet.breakers}      # an agent only a control named still shows
    for r in records:
        c = by_agent[r["agent"]]
        c["calls"] += 1
        c["held"] += r["route"] != "agent"
    trips = 0
    for agent in sorted(by_agent):
        c = by_agent[agent]
        print(f"agent {safe(agent)}   {c['calls']} calls: {c['calls'] - c['held']} to the agent, {c['held']} held for a person")
        for ev in fleet.log.events:
            if ev["agent"] != agent or ev["kind"] == "call" or (ev["kind"] == "control" and ev["data"]["effect"] != "none"):
                continue
            if ev["kind"] == "transition" and ev["data"]["from"] == CLOSED and ev["data"]["to"] == OPEN:
                trips += 1
            print(f"  t={ev['t']:<5} {describe(ev, fleet.policy)}")
    leaks = sum(1 for ev in fleet.log.events if ev["kind"] == "call" and ev["data"]["route"] == "agent"
                and ev["data"]["state"] in (OPEN, FORCED_OPEN))
    verdict = "chain intact, replay agrees" if not problems else f"NOT VERIFIED ({problems[0]})"
    print(f"audit: {len(fleet.log.events)} events, {verdict}; {leaks} calls reached the agent while the breaker was open; head {fleet.log.head[:16]}")
    print(f"decision: {'TRIPPED ' + str(trips) + ' time' + ('s' if trips != 1 else '') if trips else 'CLEAR, the breaker never tripped'}")
    return trips


def cmd_run(events_path, controls_path, policy_path, log_path, agent, fail_on) -> int:
    try:
        policy = load_policy(policy_path) if policy_path else default_policy()
        events = load_events(events_path)
        controls = load_controls(controls_path) if controls_path else []
        if agent is not None:
            events = [e for e in events if e["agent"] == agent]
            controls = [c for c in controls if c["agent"] == agent]
            if not events:
                raise ValueError(f"events: no rows for agent {safe(agent)!r}; nothing was run")
        fleet, records = run_stream(events, controls, policy)
        problems = verify_log(fleet.log.lines(), policy)
        if log_path:
            with open(log_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(fleet.log.lines()) + "\n")
    except (OSError, ValueError) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    trips = report(fleet, records, problems)
    if log_path:
        print(f"log: wrote {log_path}; to check it later, keep this head hash somewhere else: {fleet.log.head}")
    return 1 if (trips and fail_on == "trip") or problems else 0


def cmd_verify(log_path, policy_path, head) -> int:
    try:
        policy = load_policy(policy_path) if policy_path else None
        with open(log_path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        problems = verify_log(lines, policy, head)
    except (OSError, ValueError) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    if problems:
        for p in problems[:5]:
            print(f"problem: {p}")
        print(f"log NOT verified: {len(problems)} problem(s)")
        return 1
    print(f"log verified: {len(lines)} events, chain intact, replay agrees, head {json.loads(lines[-1])['hash'][:16]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_breaker")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_events.csv)")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="replay an events file through the breaker")
    r.add_argument("events")
    r.add_argument("--controls", help="operator engage/release actions (CSV)")
    r.add_argument("--policy", help="policy parameters (CSV); the defaults are used when omitted")
    r.add_argument("--log", help="write the hash-chained audit log here (JSON lines)")
    r.add_argument("--agent", help="run only this agent")
    r.add_argument("--fail-on", choices=["trip", "never"], default="trip")
    v = sub.add_parser("verify", help="check an audit log: hash chain, then replay")
    v.add_argument("log")
    v.add_argument("--policy", help="require this policy instead of trusting the one inside the log")
    v.add_argument("--head", help="the head hash you stored when the log was written; catches a cut-short log")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return cmd_run(os.path.join(d, "example_events.csv"), None, os.path.join(d, "policy.csv"), None, None, "never")
    if a.cmd == "run":
        return cmd_run(a.events, a.controls, a.policy, a.log, a.agent, a.fail_on)
    if a.cmd == "verify":
        return cmd_verify(a.log, a.policy, a.head)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
