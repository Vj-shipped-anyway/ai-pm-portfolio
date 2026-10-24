# PRD: MCP Scope Lint

## Problem
An MCP server is granted a set of scopes, and its tools each ask for some of them. Nobody compares the two. A scope that no tool asks for stays. A wildcard stays whole although the tools use one scope behind it. A tool marked read-only can still ask for write. The review approves a list of names.

## Who it is for
An engineer who owns an MCP server, and the security or platform reviewer who approves what the server may be granted.

## What it does
1. Parses a tool manifest into tools, a scope catalog and a grant, and rejects anything malformed with exit 2.
2. Applies five rules: an unused grant, a wildcard used in part, a tool that asks for more than its hints allow, a tool with no hint that asks for a wildcard, a tool that requires a scope that is not granted.
3. Scores breadth: the share of reachable scopes that no tool requires.
4. Proposes a smaller grant that never adds a scope, and lists the tools it changes.
5. Prints text or GitHub annotations and exits non-zero at a chosen level.

## Out of scope
Reading tool descriptions or input schemas; scope hierarchies other than a per-resource wildcard; run-time scope step-up; exporting a manifest from a live server; any model call; hosting.

## Success, as the scripts print it
Unneeded scopes cut (61 of 83 on the planted set, against 53 of 83 for a blocklist that also cuts 18 needed ones); no finding on the hard negatives built to look risky (0 on 15, 6 and 8 tools); the known limits named (22 of 83 unneeded scopes stay, 3 needed ones are cut).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. A hint is a claim by the tool's author, and a wrong read-only hint makes the proposal cut a needed scope. A manifest shows less slack than there is, because tools that over-ask look like need.

## Next
Run it on one real server manifest its owner is allowed to share; add an export from a server's configuration; compare it with a call log, as in [23](../23-scopekeeper-agent-permission-review/), to catch the tool nobody calls.
