# Security policy

This repo holds prototypes that run on synthetic data. Nothing here takes real input, and there are no credentials, keys or customer data in the code or in the git history (I scanned both for secret-shaped strings before writing this). The three Streamlit apps (HalluGuard, DriftSentinel and LeaseGuard) are demos on synthetic data.

## What to report

- A secret committed by mistake: a key, token or password, anywhere in the repo.
- A script that writes outside its own folder, runs code it should not, or makes a network call that its README does not mention. The step scripts use the standard library and make no network calls. The one script that does is `26-stepscout-task-mining-agent-candidates/data/real/fetch_bpi2012.py`, which downloads a single public file and checks it against its published MD5.
- A known vulnerability in a package listed in a project's `requirements.txt`, such as the packages the Streamlit apps use.

A prototype that gets an answer wrong, such as a guardrail that misses an attack, is not a vulnerability. Each project prints what it still gets wrong, so that belongs in a normal issue.

## How to report

GitHub's private vulnerability reporting is not switched on for this repo. Until it is, open an issue titled "Security: please contact me" and leave the details out of it. I will reply on the issue and move the details somewhere private.

## Supported versions

The current `main` branch only.
