# Real-data mode: the BPI Challenge 2012 loan-application log

Everything else in this project runs on synthetic data, where the generator knows the answer. That is the right way to test a method and the wrong way to show it works: a planted signal is easy to find. This folder is the one place the same questions are put to a real log that nobody planted anything in.

The log is not in this repo. `fetch_bpi2012.py` downloads it from the 4TU.ResearchData archive and checks it against the published MD5. `../../src/real_bpi2012.py` reads it.

## The log

| | |
| --- | --- |
| Title | BPI Challenge 2012 |
| Creator | Boudewijn van Dongen |
| Publisher | Eindhoven University of Technology, through 4TU.ResearchData |
| First published | 2012-04-23 |
| What it is | An event log of a loan-application process at a financial institution, in XES format |
| File | `BPI_Challenge_2012.xes.gz`, 3,342,406 bytes, MD5 `74c7ba9aba85bfcb181a22c9d565e5b5` |
| License on the record | 4TU General Terms of Use |

**Citation.** van Dongen, Boudewijn (2012): BPI Challenge 2012. Version 1. 4TU.ResearchData. dataset. https://doi.org/10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f

## The terms, read before using it

The record lists the 4TU General Terms of Use, not a Creative Commons license. The text I read is the August 2016 PDF (`General_terms_of_use.pdf`, MD5 `5a37f1aea024a6339971a69994e094d5`). This table is my summary of what it asks, not legal advice; the PDF governs.

| What the terms ask | What this folder does about it |
| --- | --- |
| Cite the dataset in the text and in a reference list (Articles 1 and 2). | The citation is above, in the project README, and in the first lines of the committed output. |
| Remix, transform or build on the data for non-commercial purposes only (Article 4b). | This is a portfolio and teaching artifact. Do not use this log in paid, client or product work. The script accepts any XES file with `--file`, so a log whose license allows that use can be swapped in. |
| When distributing the data, acknowledge the rights-holder, and say that later distribution must do the same (Article 4a). | The log is not redistributed. It is fetched from the archive on demand and is git-ignored. |
| Respect copyright on the data (Article 5) and, for personal data, use it only for research (Article 7). | The resource column holds numbers, not names. The script counts distinct resources and reads nothing else about them. |

The MIT license on this repo covers the code. It does not cover the log, and it does not widen the terms above for the numbers printed from it.

## Run it

From the repo root:

```bash
python3 26-stepscout-task-mining-agent-candidates/data/real/fetch_bpi2012.py
cd 26-stepscout-task-mining-agent-candidates/src
python3 real_bpi2012.py --write-output
```

The archive's file server returns 502 now and then. The fetch script retries, and if it still fails it prints where to place the file by hand. Standard library only, Python 3.9 or newer; reading the 3.3 MB file takes a few seconds.

`python3 real_bpi2012.py --selftest` needs no download. It runs the parser and the analysis on a three-case log whose answers are worked out by hand, and the repo check runs it on every push.

## What is committed

`bpi2012_output.txt` is the text the script prints for the file with the MD5 above. It is derived from the log and carries the citation and the terms line. The README of this project quotes only numbers that appear in it, and the repo check fails if a green-tagged number in the project README is missing from that file.

## What it answers and what it cannot

From a case-system log alone it can answer: how many real paths the cases take and how much the most common one covers, how much elapsed time is waiting and how much is hands-on work, how often a case schedules the same work item again, and how a list ranked by waiting plus hands-on time differs from one ranked by hands-on time.

It cannot answer, and the script prints this: anything off the system, because the log has no desktop layer; which steps an agent can take over, because there is no control register and no answer key; and anything about a bank other than this one process in 2011 and 2012.
