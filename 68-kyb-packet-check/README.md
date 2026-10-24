# 🪪 KYB Packet Check: the beneficial owner a model misread (synthetic documents)

**I wanted to know what lands in an onboarding file when a model misreads one line of a business filing, and which misreads a cheap check can stop before a person signs off. This is a command-line check: it takes the text of a packet and the model's extraction of it, and prints PASS or REVIEW with the findings.** It never calls a model. The extraction is an input, so any extractor can sit in front of it; I ship 75 synthetic packets and a recorded extraction for each.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 68-kyb-packet-check/src && python3 kyb_packet_check.py --demo
```

It prints:

```text
packet KYB-EX01  Harbor Lane Supply LLC
  [grounding   ] pct_not_in_source      Mateo L. Petrov: read 20%, source line shows 30%
  [grounding   ] pct_not_in_source      Jonas R. Okafor: read 30%, source line shows 20%
checked: 3 holders, 0 look-through rows, 3 people against 12 source lines
owners at 25 percent or more as read: Imani Weller 50%, Jonas R. Okafor 30%; control person: Imani Weller
decision: REVIEW (2 findings)
```

The model swapped two percentages. The schedule still adds to 100, so a sum check is silent. Only the comparison with the filing line shows that the file would name Jonas Okafor, who holds 20 percent, as an owner and leave out Mateo Petrov, who holds 30.

Standard library only, Python 3.9 or newer. To check your own files: `python3 kyb_packet_check.py check packet.txt extraction.json`. Exit 0 is PASS, 1 is REVIEW, 2 means an input could not be read (empty, truncated or wrong-type files get a one-line message, not a traceback). The demo exits 0 so the command does not look like a failure. The extraction format is in [`data/README.md`](./data/README.md).

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 75 planted packets, 43 with a planted misread and 32 clean; the script is named in brackets):

- 🟢 No check: 0 of 75 packets stopped, and 20 of 75 files would list the wrong people, meaning the 25 percent owners plus the control person (`step_01`)
- 🟢 A shape check (fields present, certification signed) flags 12 of 43 misreads and 0 of 32 clean packets; it passes 31 of 43 misreads, 18 of which would list the wrong people (`step_02`)
- 🟢 Completeness and arithmetic without the filing text flag 30 of 43 misreads; grounding against the filing text alone flags 19 of 43; 21 are caught only by the first, 10 only by the second (`step_03`)
- 🟢 A sum check with zero tolerance flags 4 of 32 clean packets (thirds written as 33.33 add up to 99.99); with a tolerance of 0.1 it flags 0 of 32 (`step_03`)
- 🟢 All three together: 40 of 43 misreads flagged, 0 of 32 clean packets flagged, 17 of 20 wrong-people packets flagged, and 40 of 75 packets go to a person (`step_04`)
- 🟡 Modeled: the sum tolerance of 0.1 point and the rule that a schedule adds to 100 are my assumptions, not the order's. I chose the tolerance so that thirds written to two decimals pass.
- 🔴 Hypothetical: that a reviewer clears a three-line finding faster than a re-read of the filing. I did not time anyone. How often a real model misreads a filing like these is also unmeasured; the planted misreads say nothing about it.

## What it still gets wrong

- 🟢 Three of the 43 misreads pass (`step_04` prints each one): the nominee notes KYB-001, KYB-032 and KYB-057. The extraction matches the schedule line for line, and a note elsewhere in the filing says the holder acts for someone who is not listed. A check for the word "nominee" would catch these three. I left it out because it would be fit to my own wording of the note.
- **The packets and the checks share an author.** I planted the misreads and wrote the rules, so 40 of 43 shows the rules cover what I planted. I built hard cases into both sides: clean packets a careless rule would flag (thirds, names in another form, an entity at 20 percent, an owner exactly at 25 and one at 24), and swapped percents that keep the total at 100. Treat the result as a ceiling for these rules, not a rate on real filings, which I have not tried.
- **The filing text here is clean.** It is plain synthetic text in a few row formats. A real filing is a scan or a PDF, and grounding is only as good as the text layer you hand it: an OCR error can flag a correct read or let a wrong one through.
- A PASS shows only that the extraction agrees with the filing, not that the filing is true or that a person is who they say they are. The order's "verify" step is outside this tool.
- Names match on words, ignoring single-letter initials and word order, so two different people with the same first and last name count as one. Look-through goes one level. Trusts are not handled. Dates must be ISO. A schedule that legitimately adds to less than 100 (unallocated interests) would be flagged; none of my packets has one, so I have not measured that.
- The certification is checked for a signer and a date, not read against the filing. Findings print names and percentages but never a date of birth, address or ID number.

## The extraction is a stub

`data/extractions.csv` holds what an imaginary extractor returned for each packet, with the misreads planted by [`data/_generate.py`](./data/README.md) after the filing text was written. The steps replay it. To use a real extractor, write its output in the same JSON shape and pass the file to `check`.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What reaches the file when nothing checks the extraction? | `step_01_no_check.py` |
| 2 | What does a field-presence check catch? | `step_02_field_validation.py` |
| 3 | Where does each half fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do the three checks catch together? | `step_04_with_check.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The tests (`tests/`, 61 of them) pin those numbers, bad input and hostile strings.

## Aligned to

FinCEN order FIN-2026-R001, "Exceptive Relief from Requirement to Identify and Verify Beneficial Owners at Each Account Opening", issued February 13, 2026 ([PDF](https://www.fincen.gov/system/files/2026-02/FinCEN-Order-CCDExceptiveRelief.pdf)). I read the whole text on 2026-10-24 and did not check for later changes; the order says FinCEN may revoke an exception at its discretion.

What I took from it, all from its footnote 6, which recites 31 CFR 1010.230: a beneficial owner is each individual who directly or indirectly owns 25 percent or more of the equity interests, plus a single individual with significant responsibility to control, manage or direct the customer; the information is name, address, date of birth and an identification number; and the person providing it certifies that it is accurate. The order lets an institution limit identification and verification to a customer's first account, to any time it knows facts that reasonably call earlier information into question, and to what its risk-based procedures call for. This tool sits upstream of that: it asks whether what a model wrote down agrees with the filing it read.

Everything else is my design and not from the order: the sum rule and its tolerance, the grounding rule, one level of look-through, and sending any finding to a person. It is a prototype, aligned to that text and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer, real filing or bank, and the names are invented. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/packets.csv` and `data/extractions.csv` for your own exports and keep the columns, or skip the data and point `check` at one packet text and one extraction file. The scoring steps also need `truth.csv`. Read the [PRD](./PRD.md) for the scope I held to.
