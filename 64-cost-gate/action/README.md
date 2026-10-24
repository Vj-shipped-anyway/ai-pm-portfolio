# Cost Gate (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 cost_gate.py check --fail-on fail --format github -- RESULTS BUDGET`, covered by `tests/test_cli.py`.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `cost-gate-action`. Check that the name `Cost Gate` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/cost_gate.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

```yaml
- uses: Vj-shipped-anyway/cost-gate-action@v1
  with:
    results: eval/results.csv
    budget: eval/budget.json
    fail-on: fail            # fail, warn or never
```

Inputs go through environment variables, not straight into the shell command, and the paths follow a `--` so a path that starts with a dash is not read as an option. The step prints one annotation per scope that is over budget, with text from the CSV escaped so a slice name cannot start a new workflow command.
