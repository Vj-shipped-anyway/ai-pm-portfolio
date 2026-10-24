# Issue draft (not opened)

Target: https://github.com/finos/ai-governance-framework, on the project's issue page, using the enhancement request template. The headings below are mine; move the text into the template's fields. Read the guide first: https://github.com/finos/ai-governance-framework/blob/main/CONTRIBUTING.md (read 2026-10-24). Search for an existing issue on the same idea before opening this one.

## Title

Enhancement: point each risk entry at a runnable check, five entries to start

## What I would like to propose

Each risk entry describes what can go wrong and what to do about it. A reader who wants to see the risk addressed in practice has no pointer to something they can run. I would like to add, for a small number of entries, one row that names a runnable check: the command, what it covers and what it does not.

I have a first set of five, each pointing at a check in a public portfolio of prototypes on synthetic data ( https://github.com/Vj-shipped-anyway/ai-pm-portfolio ):

| Risk entry | Check | What it does not cover |
|---|---|---|
| ri-4 Hallucination and Inaccurate Outputs | 41-narrative-trace | Sentences with no citation |
| ri-5 Foundation Model Versioning | 47-swapbrief | It does not detect that a provider changed a model |
| ri-10 Prompt Injection | 38-injection-pack | A real model; attack kinds outside the pack |
| ri-24 Agent Action Authorization Bypass | 23-scopekeeper-agent-permission-review | Not tested on call chaining or skipped approval steps |
| ri-26 MCP Server Supply Chain Compromise | 28-tool-schema-drift | Malicious instructions in a description; intercepted connections |

These are my reading of each entry and each project, and they are unreviewed.

## What I would like to ask

1. Is a pointer to a runnable check in scope for a risk entry, or does it belong somewhere else (a separate page, or the mitigations)?
2. If it is in scope, where should it sit? The entries I read have a Links section; a short table under it would fit the structure, but you may prefer a new heading.
3. Should the checks live in this repository or be linked from outside it? I would link outside and keep the framework free of code.

## Why a row has to stay true

A pointer that says "this check covers this risk" goes stale when the check changes. In my portfolio, `56-aigf-checks` compares each row's claim with the line the check prints and reports the rows that no longer hold. It is a prototype on synthetic data. I mention it so you know the rows would not be typed once and forgotten; I am not proposing that the framework adopt the tool.

## Limits

The mapping is not endorsed by anyone but me. The prototype does not run a check or read its code. Nothing in the portfolio is a certification of anything.

## Next

If the answer to question 1 is yes, I will open a pull request for the five entries, with a `Signed-off-by` line on every commit.
