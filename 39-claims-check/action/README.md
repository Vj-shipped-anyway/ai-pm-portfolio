# Claims Check (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is tested is the command it wraps: `python3 claims_check.py check README.md --evidence ... --format github`, covered by `tests/test_cli.py`.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `claims-check-action`. Check that the name `Claims Check` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/claims_check.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`.
5. Run it once on a throwaway pull request, with a README that has one wrong number, before telling anyone.

## Usage

The action reads text files. It does not run your scripts, so a step before it has to write what they print.

```yaml
- name: Print the numbers the README cites
  run: |
    mkdir -p evidence
    cd src
    for s in step_0*.py; do python3 "$s" > "../evidence/${s%.py}.txt"; done

- uses: Vj-shipped-anyway/claims-check-action@v1
  with:
    readme: README.md
    evidence: |
      evidence/*.txt
      data/README.md
    fail-on: unsupported      # unsupported or never
    min-digits: '2'
    pairs: 'true'             # false checks "a of b" as two separate numbers
```

Each input goes through an environment variable, not straight into the shell command, so a path with odd characters cannot inject commands. Text that came from the repository (the README path, an evidence pattern) is escaped before it is written into a workflow command.

The step fails when a number after a green circle is not printed, when an evidence pattern matches no file, or when a file cannot be read as text. It prints a warning, and passes, when the README has no green number to check.
