# 📎 chargeback-packet (merchant dispute evidence): the packet checked against the list before the clock runs out

**I wanted to know how many dispute response packets go out with a fault that a person could have caught while the window was still open, and what it takes to catch them. This is a command-line tool that takes a dispute case and its packet, looks up the evidence list for the reason code, runs the response clock, checks that the documents agree with the case, and prints READY, FIX or LATE.** It is built for the person who assembles the packet, and it is a different party from the bank-side clocks in [49 dispute-clock](../49-dispute-clock/).

**▶ Static demo, no install:** [open demo.html](./demo.html)

The reason codes, evidence lists, response windows and the page limit are assumptions of a modeled network (🟡). I did not read any card network's rules for this project, so I claim no alignment with one. READY means the checker found nothing wrong that it can see. It does not predict whether a dispute is won.

## Run one now

```bash
cd 75-chargeback-packet/src && python3 chargeback_packet.py --demo
```

It prints:

```text
case CB-DEMO  RC-02 Goods or services not received  amount 129.00  due 2026-03-04, 4 days left as of 2026-02-28
  [missing_evidence      ] delivery proof: need one of delivery_tracking, digital_access_log
decision: FIX (1 problem, 4 days left)
```

The dispute was received on 2 February with a 30-day window in the modeled list, so the last day is 4 March. The packet has the order record and a customer message and no proof of delivery, which is the one required item for this code. With four days left, that is a fix, not a loss.

Standard library only, Python 3.9 or newer. To check your own file: `python3 chargeback_packet.py check cases.json --rules my_rules.json --as-of 2026-03-31`. The file holds one case or a list of cases. It exits 1 when any packet is FIX or LATE and 2 when the input cannot be read. Text from the input is escaped before it is printed.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 100 planted dispute cases; the script is named in brackets):

- 🟢 No check: 57 of 100 packets go out with a planted fault, carrying $58,502.91 of $103,404.68 in disputed value; 43 of those faults had time left to fix and 14 packets were already late (`step_01`)
- 🟢 Counting documents (the order record plus at least two others) holds back 22 of 100, sends 37 of 57 faulty packets anyway, holds back 2 of 43 ready ones and passes 8 of 14 late packets (`step_02`)
- 🟢 Each part alone: the evidence list flags 10 of 34 visible faults, the clock flags 14 of 14 late packets and no defective one, the consistency checks flag 24 of 34 visible faults; none of them flags a ready packet (0 of 43) (`step_03`)
- 🟢 All three together: 34 of 34 visible faults go to FIX, 14 of 14 late packets are marked LATE, 0 of 43 ready packets are flagged, and the decision matches the planted truth in 91 of 100 (`step_04`)
- 🟢 A person opens 48 of 100 packets instead of reading all 100, and 7 of the 34 drafts to fix have 3 or fewer days left (`step_04`)
- 🟢 Hard negatives that stayed READY: 8 of 8 using the second option of an either-or item, 5 of 5 partial disputes, 5 of 5 sent on the last day, 5 of 5 drafts with the window open (2 of 2 due today), 3 of 3 with an extra document on no list (`step_04`)

## What it still gets wrong

- 🟢 Nine of the 43 defective packets pass: 6 carry a document that belongs to another case and 3 carry an unreadable scan, and every one has the right label, reference, date and page count (`step_04` prints each one). The checker never opens a file.
- **The data and the rules share an author.** I wrote the recipe for a good packet and the rules, in separate tables so that a mistake in one shows up as a false alarm, but I wrote both. 0 of 43 ready packets flagged shows they agree with each other. It does not show that they match any real network, and the numbers are a ceiling for these rules, not a rate on real disputes.
- 🟡 The evidence lists, the windows (14 to 30 days), the last-day-counts rule and the page limit are invented. The window is counted in calendar days. There is no weekend, holiday, time-zone or extension rule. Real lists differ by network and change over time; load the one your acquirer publishes into `data/rules.json` before relying on any output.
- Document types are a fixed vocabulary. A misspelt type shows up as a missing item and a note that the type is on no list; the checker does not guess what was meant.
- One reason code per case. No second presentment, no pre-arbitration stage, no partial evidence value: a packet with one weak document and a packet with a strong one are both READY.
- It checks page counts, not file size or format.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What goes out when nobody checks the packet? | `step_01_no_check.py` |
| 2 | What does counting documents catch? | `step_02_count_the_documents.py` |
| 3 | Where does each part of the check fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do the list, the clock and the consistency checks catch together? | `step_04_with_check.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The tests in `tests/` cover bad input, hostile strings and the boundary days of the clock, and a golden test pins the numbers above.

## Aligned to

Nothing. I did not read any card network's rules, reason-code list or published deadlines for this build, so the codes RC-01 to RC-06 and everything attached to them are my own. This is a prototype, not compliant with or certified against any scheme.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, merchant, customer, bank or card network. A prototype on synthetic data, not a production case study.

## Fork it

Replace `data/rules.json` with your acquirer's published list (keep the shape: reason codes, windows, slots with either-or `accept` lists) and point `check` at an export of your open disputes with the columns in [`data/README.md`](./data/README.md). Read the [PRD](./PRD.md) for the scope I held to.
