# Entitlement Canary (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 entitlement_canary.py check ACCESS PACK RESULTS --format github`, covered by `tests/test_check.py`.

The Action does not run your retrieval system. Your own test job does that and writes a results file; the Action reads the file, checks every returned document against the access export, and fails the step.

## What your test job has to do

For each canary in the pack, in the order of the pack:

1. If `prime_user` is not empty, ask the canary's `query` as `prime_user` first (the control). Keep the document ids it returns.
2. Ask the same `query` as `user_id` (the probe). Keep the document ids it returns. Map chunks to their document id first; the check reads document ids, not chunk ids.
3. Write one row to the results CSV: `canary_id`, `returned_doc_ids` (the probe, separated by `;`), `primed` (`yes` if step 1 ran, else `no`), `control_returned_doc_ids` (the control, separated by `;`).

Run the control and the probe against the same running instance, with the cache in the state production would have. A cache shared between users shows up only when the control runs first. The check cannot see whether you did this; it reads the `primed` column you wrote.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `entitlement-canary-action`. Check that the name `Entitlement Canary` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/entitlement_canary.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

```yaml
- uses: Vj-shipped-anyway/entitlement-canary-action@v1
  with:
    access: access/export.json          # as it stands on this branch
    pack: canaries/pack.csv             # built once with: entitlement_canary.py build-pack
    results: canaries/results.csv       # written by your test job in the step before
    fail-on: block                      # block, review or never
    min-per-source: '3'                 # optional
```

Inputs go through environment variables, not straight into the shell command, so a path with odd characters cannot inject commands. Text taken from the access export or the files (titles, user ids) is escaped before it is written into a workflow command.

Rebuild the pack when the access export changes in a way that matters (a new source, new groups). Keep the seed in the commit message so the pack can be rebuilt byte for byte.
