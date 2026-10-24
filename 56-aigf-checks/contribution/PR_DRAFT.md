# Pull request draft (not opened, and not to be opened before a maintainer answers the issue)

Target: https://github.com/finos/ai-governance-framework. Rules from its contribution guide (read 2026-10-24): the pull request merges cleanly; one contribution per commit; the commit and pull request messages reference the issue, use the present tense and the imperative mood, and keep the first line to 72 characters or fewer; avoid whitespace-only edits; every commit carries a `Signed-off-by` line.

## Title

Add runnable-check pointers to five risk entries

## Description

Adds, under the Links section of five risk entries, one row that names a runnable check: the command, what it covers and what it does not. Refs the enhancement issue (add its number here once it exists).

Entries: ri-4, ri-5, ri-10, ri-24, ri-26. Placement follows the maintainers' answer to the issue. If they ask for a different place, this description and the diff change with it.

## Commits

One commit per risk entry, so each can be reviewed or dropped alone. Subject lines, in the imperative and under 72 characters:

```text
Add a runnable check to the prompt injection risk
Add a runnable check to the hallucination risk
```

Each commit is made with `git commit -s`, so the message ends with a line of this form (the name and address are the author's own):

```text
Signed-off-by: Your Name <you@example.com>
```

Before pushing, save a commit message to a file and run `python3 aigf_checks.py signoff message.txt` from `56-aigf-checks/src` in a clone of the portfolio. It checks the form of the sign-off line and the length of the subject. It does not check the mood of the subject or that the address is yours.

## Checklist

- [ ] The issue was answered and the placement follows the answer
- [ ] Each of the five commands was run on the day of the pull request and its output read
- [ ] Every commit has a `Signed-off-by` line
- [ ] The text says what each check covers and what it does not, in the maintainers' tone
- [ ] No claim of compliance or certification anywhere
