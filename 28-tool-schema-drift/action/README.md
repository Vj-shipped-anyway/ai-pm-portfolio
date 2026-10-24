# Tool Schema Drift Gate (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 tool_schema_drift.py check OLD NEW --format github`, covered by `tests/test_cli.py`.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `tool-schema-drift-action`. Check that the name `Tool Schema Drift Gate` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/tool_schema_drift.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`. Also create the moving tag `v1` on the same commit, because the usage below points at `@v1`.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

```yaml
- uses: Vj-shipped-anyway/tool-schema-drift-action@v1
  with:
    old: schemas/before.json
    new: schemas/after.json
    calls: tests/recorded_calls.csv   # optional
    fail-on: block                    # block, review or never
```

Inputs go through environment variables, not straight into the shell command, so a path with odd characters cannot inject commands.
