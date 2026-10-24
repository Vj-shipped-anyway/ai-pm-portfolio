# Feature Contract Gate (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 feature_contract.py check --format github -- CONTRACT BATCH`, covered by the tests in `../tests/` (`test_cli.py` for exit codes, malformed input and hostile strings).

## What it needs from the workflow

A contract file and a batch of data in the checked-out repository, for example a sample export that a pipeline test writes, or a fixture committed next to the contract. The Action does not fetch data and does not call a model.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `feature-contract-action`. Check that the name `Feature Contract Gate` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/feature_contract.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`. The usage below pins `@v1`, so also create a `v1` tag on the same commit.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

```yaml
- uses: Vj-shipped-anyway/feature-contract-action@v1
  with:
    contract: contracts/credit_triage.json
    batch: tests/sample_batch.csv
    fail-on: fail                     # fail, warn or never
```

Inputs go through environment variables, not straight into the shell command, and the paths follow `--`, so a path with odd characters cannot inject commands or be read as an option. Values from the batch that appear in the annotations are escaped (`%`, carriage return, newline), so a cell cannot start a new workflow command.
