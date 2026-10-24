# 📋 runbook-dryrun: an incident runbook you can dry-run, with the approval gate held

**I wanted to know how much of an incident runbook can be checked before anyone is paged, and what a dry run has to hold to be worth reading. This is a command-line tool. It reads a runbook written in a small YAML subset, walks it against a snapshot of system state without running anything, and holds at every approval gate until a record is on file that was given by a different person, in the right role, for the exact command that is about to run, inside its time limit. It prints READY, WAITING or BLOCKED.** It builds on the approval-digest idea from [27 AgentKit](../27-agentkit-reference-agent-and-playbook/) and on the incident framing of [19 IncidentLedger](../19-incidentledger-ai-incident-response/): 19 starts the clock, this is about what the person does next.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 54-runbook-dryrun/src && python3 runbook_dryrun.py --demo
```

It prints:

```text
runbook: scorer-rollback   5 steps   requester: dana
  s1   read   low    ok          modelctl status --target scorer-v7
  s2   read   low    ok          modelctl health --target scorer-v6
  s3   write  high   REJECTED    modelctl rollback --target scorer-v7 --to scorer-v6
       gate incident-commander, 30 min, digest 524b06ec291e
  s4   notify low    ok          chatctl post --channel ai-incident --text 'rolled back scorer-v7'
  s5   read   low    ok          modelctl status --target scorer-v6
findings:
  error   approval_invalid      s3   marta: digest_mismatch (approved 38130d770ffd, this rendering is 524b06ec291e)
verdict: BLOCKED
```

Marta approved a rollback of scorer-v8. The run is for scorer-v7. The approval is bound to the rendered command, so it does not carry over.

Standard library only, Python 3.9 or newer. To check your own files:

```bash
python3 runbook_dryrun.py check RUNBOOK.yml
python3 runbook_dryrun.py dryrun RUNBOOK.yml --world WORLD.json --requester NAME [--approvals APPROVALS.json] [--param name=value]
```

`check` needs no snapshot. `dryrun` exits 1 on BLOCKED, 2 on input it cannot read, and 0 otherwise; `--fail-on waiting` also fails on a held gate, and `--format github` prints annotations. Nothing is ever executed. Without `--approvals` the demo runbook ends `verdict: WAITING at s3`.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 94 drill cases, each a runbook with a state snapshot, a requester and the approvals on file; the script is named in brackets):

- 🟢 With nothing checked first, 53 of 94 cases go wrong only while someone follows the runbook; in 25 of them a high-risk change goes ahead with no valid approval, and 12 of the 53 stop or send a bad command after a write step has already gone through (`step_01`)
- 🟢 A dry run that prints every command shows 5 of those 53 problems (an unfilled placeholder), calls 48 of 53 fine, and notices 0 of 16 invalid approvals (`step_02`)
- 🟢 Each part alone: lint catches 17 of 53, the state check catches 17 of 53 and blocks 3 of 41 clean or waiting cases wrongly, the approval gate catches 16 of 53 (`step_03`)
- 🟢 Together: 46 of 53 blocked cases caught, 8 of 8 waiting cases held at the gate, the missing rollback warned in 4 of 4, 14 of 17 hard negatives pass, and the verdict matches the planted truth in 84 of 94 (`step_04`)

**Modeled** (🟡 these are my policy values, not a rule from anywhere): a high-risk write needs an approval gate; a medium or high-risk write should name a rollback or say `rollback: none`; an approval lasts 30 minutes unless the gate sets another limit. Change them in `runbook_dryrun.py` and the numbers move.

**Hypothetical** (🔴 never tested): that a team which dry-runs its runbooks loses less time in a real incident. I measured defects found before the run, not minutes saved.

## What it still gets wrong

- 🟢 7 of the 53 blocked cases pass as READY (`step_04` prints each one). Four are a step that changes production but is declared `effect: read, risk: low`, so nothing gates it (mislabeled_effect). Three are a snapshot that went stale between the dry run and the real one (world_drift). The tool trusts what the runbook says about itself and what the snapshot says about the world. It does not read a command to see what it does.
- 🟢 3 of 41 clean or waiting cases are blocked. The snapshot holds a number as text ("12" against `>= 5`), and the tool refuses to guess and says so. That is a false alarm by design: a stricter tool, not a smarter one.
- **The test set and the rules share an author.** I planted the defects and wrote the checks, so 46 of 53 shows the checks cover what I planted. I added hard negatives that could trip a rule (a placeholder in a note, a low-risk write with no gate, a second valid approval beside the requester's own, an approval exactly at its time limit) and the two kinds a dry run cannot see. Treat the numbers as a ceiling for these rules, not a rate on real runbooks, which I have not tested.
- The `sets` a step declares are the author's claim, and the tool applies them as written.
- An approval is bound to the rendered text of one command. It does not prove the approver read it, and role names are taken as written, with no directory lookup.
- Runbooks are linear: no branches, loops or parallel steps. The YAML is a subset (`data/README.md` lists it); a value that contains `: ` must be quoted.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the on-call person meet when nothing is checked first? | `step_01_prose_runbook.py` |
| 2 | What does a dry run that prints every command show? | `step_02_echo_dry_run.py` |
| 3 | Where does each part of the tool fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do lint, state and the approval gate catch together? | `step_04_with_dryrun.py` |

Run any of them from `src/`. Data is produced by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. `demo.html` is built by `src/_build_demo.py` from the files step 4 writes to `src/out/`.

## Aligned to

Nothing. I am not claiming alignment with a standard or a regulation for this project, and I cite none. Approval gates and rollbacks are ordinary practice and the policy values above are mine. It is a prototype on synthetic data and makes no claim of conformity to anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. The command names (`routectl`, `modelctl` and the rest) belong to no real product, and nothing comes from any employer, customer or bank. A prototype on synthetic data, not a production case study. The approval digest, the role check and the distinct-person check are re-implemented here from the gates in project 27 (there the second person is the one who judged the case; here it is the requester); nothing is imported across folders.

## Fork it

Swap `data/cases.csv` for your own runbooks, snapshots and approvals and keep the columns, or skip the data and point `check` and `dryrun` at your own files. Read the [PRD](./PRD.md) for the scope I held to.
