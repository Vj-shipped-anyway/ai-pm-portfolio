# Eval Gate (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 eval_gate.py check PROBES RESULTS --pin SNAPSHOT --format github`, covered by `tests/test_cli.py`, including a check that no `${{ }}` expression sits inside the shell script.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `eval-gate-action`. Check that the name `Eval Gate` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/eval_gate.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

```yaml
- uses: Vj-shipped-anyway/eval-gate-action@v1
  with:
    probes: evals/probes.csv
    results: evals/results.csv     # written by your harness; one row per probe
    pin: vendor-balanced-4-20260214
    fail-on: block                 # block, review or never
```

Your harness has to write `served_model` from the response itself (the model field the vendor's API returns), not from the name you asked for. If it copies the request, the gate compares the pin with the pin.

Inputs go through environment variables and an argument array, not straight into the shell command, so a value with odd characters cannot inject commands. The thresholds (3 and 5 points, 50 points for a collapsed probe) keep their defaults here; `--review-drop`, `--block-drop` and `--collapse-drop` change them on the command line.
