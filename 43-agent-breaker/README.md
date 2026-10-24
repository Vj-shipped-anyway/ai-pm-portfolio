# 🔌 agent-breaker: a circuit breaker for an agent

**I wanted to know what it takes for an agent to stop itself: trip when it fails, hold its cases for a person, test the way back, and leave a log that proves what happened. This is a standard-library module and command line that does that. It routes an agent's calls to a human queue on a critical failure, a run of failures or a failure rate, probes before it lets the agent back, and writes a hash-chained log that a second run can reproduce line for line.** It takes the warn and clear fractions from [25 KillSwitch](../25-killswitch-ai-fallback-drills/) (the trip rules and every other number here are mine) and the operator switch and audit chain from [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), and puts them in one breaker you can wrap around any tool-calling loop.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 43-agent-breaker/src && python3 agent_breaker.py --demo
```

It prints:

```text
agent payment-repair   90 calls: 47 to the agent, 43 held for a person
  t=68    CLOSED      -> OPEN        5 failures in a row
  t=98    OPEN        -> HALF_OPEN   hold of 30 min is over, the next calls are probes
  t=98    HALF_OPEN   -> OPEN        probe failed after 0 good, next hold 60 min
  t=158   OPEN        -> HALF_OPEN   hold of 60 min is over, the next calls are probes
  t=162   HALF_OPEN   -> CLOSED      3 probes passed
audit: 96 events, chain intact, replay agrees; 0 calls reached the agent while the breaker was open; head 99b9289be1c3a889
decision: TRIPPED 1 time
```

Standard library only, Python 3.9 or newer. To back-test your own history: `python3 agent_breaker.py run events.csv --log audit.jsonl`, then `python3 agent_breaker.py verify audit.jsonl --head <hash>`. It exits 1 when the breaker tripped (run) or the log does not check out (verify), and 2 for input it cannot read. Inside a loop:

```python
fleet = Fleet(default_policy())
rec = fleet.admit(minute, "payment-repair", "case-1")   # rec["route"] is "agent" or "human_queue"
if rec["route"] == "agent":
    fleet.record(rec, "ok")                              # or "fail", with a failure kind
```

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 5 agents, 7523 calls over three days, 25 planted faults; 🟡 modeled, with the assumption named; the script is named in brackets):

- 🟢 With no stop, 312 of the 7523 calls are harmful and every one is served (`step_01`)
- 🟡 A person who reads each agent's failure rate every 60 minutes engages the switch for 6 of 14 must-trip faults, and 247 of the 312 harmful calls are still served (`step_01`; the review interval, the 0.50 line and a 120 minute hold are my assumptions in `data/model_assumptions.csv`)
- 🟢 The common breaker (5 failures in a row, a fixed 30 minute hold, one probe) trips 9 of 14 must-trip faults and 2 of 7 must-not-trip faults, and 168 of 312 harmful calls are served (`step_02`)
- 🟢 Where it fails: 0 of 3 scope violations tripped, 3 of its 15 closes are followed by a new trip within 15 minutes, and raising the count to 8 trips only 3 of 14 must-trip faults (`step_03`)
- 🟢 agent_breaker trips 12 of 14 must-trip faults (scope violations 3 of 3, flapping 2 of 2), a median of 13 minutes after the fault starts against 18 for the common breaker, and serves 142 of 312 harmful calls (`step_04`)
- 🟢 The price: 267 harmless calls go to the human queue against 140 for the common breaker, which is 1.57 held per harmful call avoided against 0.97 (`step_04`)
- 🟢 The log: 7599 events, chain intact, replay agrees, 0 calls reached the agent while the breaker was open. Of 4 tamper tests, 3 are detected from the log alone and 4 with the stored head hash (`step_04`)

## What it still gets wrong

- 🟢 **Silent errors.** 33 of the 312 harmful calls were reported ok by the agent, and the breaker tripped on 0 of the 2 silent-error faults. It reads outcomes; it cannot read whether an outcome was right (`step_04`).
- 🟢 **A slow burn.** A 0.28 failure rate sits under the trip rate: 0 of 2 tripped and 30 of 30 harmful calls were served. One of the two raised a warn, which tells a person and switches nothing (`step_04`).
- 🟢 **A quiet agent.** `limit-review` never had more than 8 calls in a 30 minute window and the rate is scored from 10, so its 2 must-trip faults were not tripped (`step_04`).
- 🟢 **Long blips look like outages.** 2 of 7 must-not-trip faults tripped, the two that fail 5 or 6 times in a row. A count of failures cannot tell them from an outage (`step_04`).
- 🟢 **The way back is strict and costly.** One failed probe re-opens the breaker with a doubled hold. 2 probe failures were not harm, one close was premature (a new trip within 15 minutes), one fault was still held when the data ended, and the breaker held 267 harmless calls (`step_04`).
- 🟢 **I did not fit the trip rate.** I set 0.5 before looking at the stream. At 0.3 the same run serves 123 harmful calls and holds 202 harmless ones, better on both counts, but moving it now would be tuning to my own data (`step_04` prints the sweep). Most trips came from the count of failures in a row (10), then critical failures (3), and only 2 from the rate.
- **The chain is not a signature.** Anyone who can rewrite the whole file can build a consistent chain. A cut at an event boundary passes unless you kept the head hash somewhere else, which `step_04` shows (detected with the head, not without it). The replay catches a forged story with valid hashes; it does not catch a forged policy unless you pass `--policy`.
- **It is a back-test as shipped.** On a recorded history, a held call still has its recorded outcome in the file; the breaker never sees it and the log says so. `admit` and `record` allow one call in flight per agent. Wiring it into a live loop, timing out a call that never returns, and running it across processes are not built.
- **The test set and the rules share an author.** I planted the faults and wrote the rules, so the numbers are a ceiling for these rules on this stream, not a rate on real traffic. The set includes cases the rules should miss and cases that could raise a false alarm, and both are printed.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the agent meet with an operator switch and a person on a schedule? | `step_01_no_breaker.py` |
| 2 | What does the common failures-in-a-row breaker stop? | `step_02_consecutive_count.py` |
| 3 | Where does it fail, and what stays unfixed? | `step_03_deficiencies_exposed.py` |
| 4 | What do critical path, rate window, backoff, probes and a replayable log add? | `step_04_with_breaker.py` |

Run any of them from `src/`. Data is produced by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The planted truth (which calls did harm, which faults must trip) comes from the generator; the rules in `agent_breaker.py` never read it.

## Aligned to

The [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative) (page read 2026-10-24). It sets out three pillars: industry-led standards, community-led open protocols, and research into agent authentication, identity and security evaluation. It names no stop, hold or logging requirement and no threshold, so this prototype is aligned in direction only: a runtime control for an agent and an evidence trail that can be checked. Every number in `data/policy.csv` is my assumption except the warn and clear fractions, which come from [25](../25-killswitch-ai-fallback-drills/data/policy.csv). It is a prototype, aligned to that direction and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real agent. The agents, the faults and the harm are made up by `data/_generate.py`. Credibility tags: 🟢 measured by a script in this folder, 🟡 modeled with the assumption named, 🔴 hypothetical. A prototype on synthetic data, not a production case study.

## Fork it

Keep the five columns of `events.csv` (`t_min`, `agent`, `case_id`, `outcome`, `failure_kind`) and point `run` at an export of your own agent's tool calls, with `--policy` for your thresholds. Group by the `agent` field, not by naming. Read the [PRD](./PRD.md) for the scope I held to.
