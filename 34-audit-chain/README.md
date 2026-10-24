# 🔗 audit-chain (hash-chained log): an append-only trail for agent actions, checked with one command

**I wanted to know how much of an agent's audit trail a reviewer can trust once someone with write access to the file wants it to say something else, and which edits a single command can find. This is a command-line tool: an append-only JSON-lines log where each event carries the hash of the one before it, a `verify` command, and an anchor you keep outside the log. I took the log from the [AgentKit audit module](../27-agentkit-reference-agent-and-playbook/) and attacked it with 101 planted edits.** The chain finds a changed, removed, reordered or inserted event anywhere in the file, except that the last event can be rewritten with its own hash recomputed. It cannot see a cut from the end or a rewrite that recomputes every hash; an anchor can, but only up to the event it was taken at.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 34-audit-chain/src && python3 audit_chain.py --demo
```

It prints:

```text
[a log nobody touched]
verify: example_log.jsonl   30 events   head 9b651ae4f0ecdf13
  anchor at event 24: hash matches
verdict: OK
[one approval changed after the fact]
verify: example_log_edited.jsonl   30 events   head 9b651ae4f0ecdf13
  line 8 (seq 8): hash does not match the event content
verdict: ALTERED (1 problem)
[the last 10 events removed]
verify: example_log_cut.jsonl   20 events   head 04bcf6997c76c5ba
  log: only 20 readable events, but the anchor was taken at event 24; events were removed or cannot be read
verdict: ALTERED (1 problem)
```

Standard library only, Python 3.9 or newer. To use it on your own agent:

```bash
python3 audit_chain.py append agent.jsonl --case C0001 --kind case_start --detail '{"source": "queue_a"}'
python3 audit_chain.py anchor agent.jsonl --out anchor.json      # keep this file where the log's editor cannot reach
python3 audit_chain.py verify agent.jsonl --anchor anchor.json
```

`verify` exits 0 when nothing in the log shows a sign of alteration, 1 when something does (including a line that is cut off or is not an event), and 2 when it could not run: a missing or empty file, a bad anchor, bad arguments. Without `--anchor` it says in its output that events removed from the end would not be noticed.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: one log of 280 events and 101 planted edits, each applied to its own copy; the script is named in brackets):

- 🟢 No integrity check: 0 of 91 tampered logs flagged, and the edited file still holds well-formed events (`step_01`)
- 🟢 A checksum on each event plus a gap-free sequence check flags 18 of 91: all 12 changed values and all 6 deleted lines. It flags 0 of 13 value edits where the hash was recomputed, and 0 of 6 renumbered deletes, 0 of 6 swaps and 0 of 6 inserts (`step_02`)
- 🟢 The bare chain, as the AgentKit module shipped it, flags 48 of 91. It closes the renumbered delete, the swap and the insert, and 12 of 13 value edits with the hash recomputed; the one that passes is the edit of event 280, the last, because nothing after it holds its hash (`step_03`)
- 🟢 The bare chain still passes all 7 duplicate-key lines, all 7 lines with a field outside the hash, all 12 full rewrites, all 10 cuts and all 6 forged appends (`step_03`)
- 🟢 The strict chain check plus an anchor at event 200 flags 76 of 91: 64 of 64 edits that touch event 200 or earlier and 12 of 27 that only touch the open tail after it. It flags 0 of 10 harmless changes (`step_04`)

## What it still gets wrong

- 🟢 15 of 91 planted edits pass step 4, all in the open tail: 6 forged appends, 4 full rewrites, 4 cuts that keep every anchored event, and the edit of the last event with its own hash recomputed (`step_04` prints each group). Whatever is written after the last anchor is protected by the chain alone, so the interval between anchors is the window an attacker has.
- 🟢 A forged append and a real one are the same bytes: 0 of 6 forged appends flagged, 6 of 6 legitimate appends accepted (`step_03`). Telling them apart needs a key held by the writer, so a forged event fails to verify. I have not built that.
- **The anchor is only as good as where you keep it.** If the person who can edit the log can also edit the anchor, nothing is detected. The tool writes and reads an anchor file; it does not store it anywhere safe.
- **An action that was never logged leaves no trace.** AgentKit checks the log against the orchestrator's own counts; I did not copy that check here.
- **The sequence number is not a clock.** The chain shows order, not time. A timestamp in `detail` is only as true as the writer.
- **Single writer.** There is no file locking. Two writers fork the chain, and `verify` reports it. `append` reads the whole file each time.
- **The hash is defined over Python's JSON encoding** (sorted keys, compact separators, ASCII). The generator in `data/` is a second writer, but it is also Python. I have not tested a log written by another language.
- **The planted edits and the checks share an author.** I chose which edits to plant and wrote the rules, so 76 of 91 shows the checks cover what I thought of, not what an attacker would try. The set includes the cases I expected to miss and the harmless rewrites I expected to pass, but it is a ceiling, not a rate on real logs.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a reader get from a log with no integrity check? | `step_01_no_integrity_check.py` |
| 2 | What does a checksum on each event, plus a sequence check, catch? | `step_02_record_checksums.py` |
| 3 | Where does that fail, and where does the bare chain still fail? | `step_03_deficiencies_exposed.py` |
| 4 | What does the strict chain check plus an anchor catch? | `step_04_chain_and_anchor.py` |

Run any of them from `src/`. The tool is `src/audit_chain.py`; `src/common.py` holds the planted edits and the weaker checks the steps compare against. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. There are 80 unit tests, including a golden test that pins the step 4 numbers, tests for empty, wrong-type and cut-off input, and tests with hostile strings in the log.

What I took from the earlier projects: the event layout, the event kinds and the hash from [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), and the problem from [09 LineageLog](../09-lineagelog-ai-decision-audit/). The 09 exam pack describes its record as immutable and hash-anchored, but its code sets `immutable: True` as a literal and carries a placeholder policy hash; nothing in it computes a digest. This project is a check that could back a claim like that. The code in `src/audit_chain.py` is changed from AgentKit's in three ways, listed at the top of the file: `detail` is a dict argument, the log is read strictly, and an anchor can be taken and checked.

## Aligned to

The [NIST AI Risk Management Framework 1.0](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) (2023), the MANAGE function. I read the Core page on NIST's AI Resource Center on 2026-10-23. Subcategory MANAGE 4.3 asks that incidents and errors are communicated to relevant AI actors and that the processes for tracking, responding to and recovering from them are followed and documented. The framework does not prescribe a log format or a hash chain. My reading is narrower: an incident record is only useful in review if the reviewer can tell it was not changed afterwards, and this tool is one way to give them that check. It is a prototype, aligned to that function and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real agent. 🟡 The anchor at event 200 is an assumption I chose for the example; no rule sets that interval. A prototype on synthetic data, not a production case study.

## Fork it

Point `verify` at any JSON-lines log written with the event layout in `src/audit_chain.py`, or start one with `append`. To rerun the comparison on your own actions, replace `data/actions.csv` (columns `case_id`, `step`, `kind`, `actor`, `detail_json`), change `ANCHOR_SEQ` and the plan sizes in `data/_generate.py` to fit the length of your log, and run it. Read the [PRD](./PRD.md) for the scope I held to.
