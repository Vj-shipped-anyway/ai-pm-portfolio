# Evidence Gate (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 evidence_gate.py check --event EVENT.json --tiers TIERS.csv --format github`, covered by `tests/test_cli.py`. The workflow syntax in `action.yml` is untested: read it before you rely on it.

## What it does on a pull request

It reads the pull request description from the event file GitHub provides, parses the change record (a `Use case:` line, a `Declared tier:` line and one `- [x] E03 ... | ref: path | date: YYYY-MM-DD` line per evidence item), and compares it with the tier-to-evidence table. It fails the step when required evidence is missing, stale, unticked, or points at a file that is not in the repository. A mismatch between the declared tier and the registry, or a link to a page outside the repository, is a warning for a reviewer. A pull request with no change record at all fails: the run is meant for pull requests that touch AI code, so limit it with a `paths:` filter on the workflow trigger.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `evidence-gate-action`. Check that the name `Evidence Gate` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/evidence_gate.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`. Also create the moving tag `v1` on the same commit, because the usage below points at `@v1`.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

```yaml
on:
  pull_request:
    types: [opened, edited, synchronize, reopened]
    paths: ['src/ai/**', 'evidence/**']
jobs:
  evidence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Vj-shipped-anyway/evidence-gate-action@v1
        with:
          tiers: governance/tier_evidence.csv
          registry: governance/registry.csv   # optional
          fail-on: block                      # block, review or never
```

The checkout step is needed: the file listing comes from `git ls-files` in the workspace. Inputs and the event path go through environment variables, not straight into the shell command, so a path with odd characters cannot inject commands. The description text is read from the event file by the script and never passes through the shell. Evidence age is measured from the date the job runs. The `edited` type matters: by default GitHub does not re-run a workflow when only the description changes, and the description is where the evidence lives.
