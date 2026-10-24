# Intake Tier Action (staged, not published)

This folder is the staging copy of a GitHub Action and the issue form it reads. It has not been published to the Marketplace and **it has not run on GitHub**. What is verified is the command it wraps, `python3 intake_tier_action.py check - --format github`, covered by `tests/test_cli.py`. The `gh` commands in `action.yml` and the YAML in `ai-intake.yml` have not been run or validated by GitHub.

## What it does on an opened or edited issue

1. Reads the issue body by the form's own headings (`### Data class` and so on).
2. Recomputes the tier from the rubric, checking the data class against a catalog file and the vendor model against a registry file when you supply them.
3. Adds one `ai-tier:N` label, adds `tier-mismatch` when the declared tier differs, or adds `needs-info` when the body cannot be read. It removes only its own stale labels and leaves every other label alone.
4. Posts one comment that starts with `<!-- intake-tier-action -->` and edits that same comment on later runs.

## One assumption to check first

The tool expects the body an issue form produces: a `### label` heading, a blank line, then the answer, with `_No response_` for an empty optional field. I wrote that from memory of how GitHub renders issue forms and did not verify it in this project. If GitHub renders a field differently, the tool fails loudly: the issue gets `needs-info` and the comment names the heading it could not find. Open one real issue from the form and compare before relying on it.

## Publish steps (a Marketplace listing needs its own repository)

1. Create a public repo named `intake-tier-action`. Check that the name `Intake Tier Action` is free on the Marketplace.
2. Copy `action.yml` from this folder and `../src/intake_tier_action.py` into the root of that repo.
3. Add a README with the set-up steps below, a test workflow and a licence.
4. Draft a release, tick "Publish this Action to the GitHub Marketplace" (two-factor authentication is required), and tag `v1.0.0`.
5. Run it once on a throwaway issue before telling anyone.

## Set up in the repository that takes the intake

1. Copy `ai-intake.yml` to `.github/ISSUE_TEMPLATE/ai-intake.yml`. Keep the field labels as they are.
2. Create the labels once: `ai-intake`, `ai-tier:1`, `ai-tier:2`, `ai-tier:3`, `ai-tier:4`, `needs-info`, `tier-mismatch`. For example, `gh label create ai-tier:3`.
3. Put a catalog CSV (`dataset_name,catalog_class`) and, if you have one, a registry CSV (`issue_number,vendor_model`) in the repository. Both are optional. The example workflow reads them from `.github/ai-intake/catalog.csv` and `.github/ai-intake/registry.csv`.
4. Save `example-workflow.yml` as `.github/workflows/ai-intake-tier.yml`. It needs `issues: write`.

## Safety notes

- The issue body, the label names and the issue number reach the shell as environment variables, never as part of the command text, so a body with shell syntax in it is data.
- The body is read from standard input. Text from the issue that appears in a comment or a log line is cut down to letters, digits, space and a few marks, so it cannot carry a mention, a link, markup or a workflow command. Annotations are escaped as well.
- The workflow listens to `opened` and `edited` only. I expect its own label and comment changes not to fire those events, so it should not loop, but I have not seen that on GitHub.
- A repeated heading, a missing heading or an unreadable value sends the issue to `needs-info`; the tool does not guess an input. A complete form with a pasted block that repeats a heading is sent there too, which costs a person one look.
- The tier never approves anything. A reviewer confirms it.
