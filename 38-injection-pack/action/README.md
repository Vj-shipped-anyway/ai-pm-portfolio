# Injection Pack Gate (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 injection_pack.py compare OLD NEW --pack PACK --format github`, covered by `tests/test_cli.py`.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `injection-pack-action`. Check that the name `Injection Pack Gate` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/injection_pack.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a license.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`. Also create the moving tag `v1` on the same commit, because the usage below points at `@v1`.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

The check compares two revisions of the rules, so the job needs both. Check out the base branch into one folder and the pull request into another:

```yaml
- uses: actions/checkout@v4
  with:
    path: head
- uses: actions/checkout@v4
  with:
    ref: ${{ github.base_ref }}
    path: base
- uses: Vj-shipped-anyway/injection-pack-action@v1
  with:
    pack: head/gateway/injection_pack.csv
    old-rules: base/gateway/rules.json
    new-rules: head/gateway/rules.json
    min-catch: '70'      # optional floor, percent of attack cases blocked
    max-fp: '15'         # optional ceiling, percent of benign cases blocked
    fail-on: regression  # regression or never
```

Inputs go through environment variables and a bash argument array, not straight into the shell command, so a path with odd characters cannot inject commands. Text that comes from the pack or the rules (case ids, rule ids, names) is escaped before it is printed as a workflow annotation, so a hostile id cannot start a new annotation.

The step prints one `::error` annotation per regression and a `::warning` when a changed rule matches no case in the pack. It exits 1 on a regression or a missed floor and 2 when a file is missing or malformed.
