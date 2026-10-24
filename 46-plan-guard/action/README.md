# Plan Guard (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 plan_guard.py check --fail-on block --format github -- PLAN`, covered by `tests/test_cli.py`.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `plan-guard-action`. Check that the name `Plan Guard` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/plan_guard.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a license.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`. Also create the moving tag `v1` on the same commit, because the usage below points at `@v1`.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

```yaml
- run: terraform show -json tfplan > plan.json
- uses: Vj-shipped-anyway/plan-guard-action@v1
  with:
    plan: plan.json
    fail-on: block        # block, review or never
```

Inputs go through environment variables, not straight into the shell command, and the plan path follows `--`, so a path with odd characters or a leading dash cannot inject commands or options. Keep `plan.json` out of uploaded build artifacts: a plan can carry values you would not want to publish.
