# Prompt Diff Risk (staged, not published)

This folder is the staging copy of a GitHub Action. It has not been published to the Marketplace and has not been run on GitHub. What is verified is the command it wraps: `python3 prompt_diff_risk.py check OLD NEW --format github`, covered by `tests/test_cli.py`. `tests/test_action.py` checks that no input reaches the shell as text.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `prompt-diff-risk-action`. Check that the name `Prompt Diff Risk` is not already taken on the Marketplace (the metadata `name` must be unique).
2. Copy `action.yml` from this folder and `../src/prompt_diff_risk.py` into the root of that repo.
3. Add a README with the usage below, a test workflow, and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`. The usage below pins `@v1`, so also create a `v1` tag on the same commit.
5. Run it once on a throwaway pull request before telling anyone.

## Usage

The Action compares two files, so the workflow first saves the prompt as it stands on the base branch. A prompt file that is new in the pull request has no base version; skip the job for that case.

```yaml
on:
  pull_request:
    paths: ['prompts/**']
jobs:
  prompt-diff-risk:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Save the prompt as it stands on the base branch
        env:
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
        run: git show "$BASE_SHA:prompts/support.txt" > "$RUNNER_TEMP/old.txt"
      - uses: Vj-shipped-anyway/prompt-diff-risk-action@v1
        with:
          old: ${{ runner.temp }}/old.txt
          new: prompts/support.txt
          tools: prompts/tools.json        # optional
          probes: evals/probes.csv         # optional
          fail-on: block                   # block, review or never
```

A BLOCK fails the check. A REVIEW prints a warning that names the probe slices to run, and fails only with `fail-on: review`. Exit status 2 means the input was malformed (empty file, bad JSON, a probe file without a slice column), and the step fails with a one-line message.

Inputs go through environment variables, not straight into the shell command, so a path with odd characters cannot inject commands. Text from the prompt is escaped before it is printed as an annotation, so a sentence cannot start a new workflow command.
