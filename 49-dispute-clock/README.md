# ⏳ dispute-clock (Reg E style clocks): the deadlines of a dispute, counted in business days

**I wanted to know how many dispute deadlines a bank misses when its case system holds one flat target date, and what it takes to count the right days from the right start. This is a command-line tool that puts each step of a dispute (acknowledge, decide on provisional credit, investigate, send the final notice) on its own clock, counts business days against a holiday file, and prints which clocks were missed and which are about to be.** It carries over the clock idea from [19 IncidentLedger](../19-incidentledger-ai-incident-response/) and adds business-day arithmetic, clocks that start at an event, and a window class per case.

**▶ Static demo, no install:** [open demo.html](./demo.html)

The windows are assumptions of a modeled bank (🟡). I did not read Regulation E or any other rule for this project, so I claim no alignment with one.

## Run one now

```bash
cd 49-dispute-clock/src && python3 dispute_clock.py --demo
```

It prints:

```text
as of 2026-09-30: 1 dispute, 4 clocks apply (5 clocks in policy, 11 holidays loaded)
missed 1 (late 1, breached 0); running 1, of which 1 due within 5 days; not started 1; on time 1
DSP-EX1  unauthorized_card
  DC1 Acknowledge to customer                due 2026-09-09  sent 2026-09-09  on time
  DC2 Provisional credit decision            due 2026-09-16  sent 2026-09-18  late by 2 business days
  DC3 Investigation concluded (standard)     due 2026-10-04  sent not done    running, 4 days left
  DC5 Final notice to customer               not started (waits for concluded_on)
```

The customer first reported on Friday 4 September. The Monday after is a holiday in the modeled calendar, so an acknowledgement sent on the 9th is on its last allowed day; a calendar-day count would have called it late. The final notice clock has not started because it begins at the conclusion, and the investigation is still open.

Standard library only, Python 3.9 or newer. To check your own file: `python3 dispute_clock.py check disputes.csv --as-of 2026-09-30`. It exits 1 when a clock was missed and 2 when the input cannot be read. `--format github` prints workflow annotations with the input text escaped; that format has been tested against the documented syntax and has not run in a real workflow.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 150 disputes and 524 clocks, read at one as-of date; the script is named in brackets):

- 🟢 One flat 30-day target flags 40 of 150 disputes and shows 32 of the 151 missed clocks. Of the 50 missed acknowledgements, 34 missed credit decisions and 30 missed final notices, it shows none (`step_01`)
- 🟢 A calendar-day countdown from the logged date matches the planted status on 454 of 524 clocks (86.6%), calls 45 clocks missed that were not, and calls 25 missed clocks fine or not due (`step_02`)
- 🟢 Business-day counting alone leaves 37 wrong of 524, a first-contact start alone leaves 76, and both together leave 5 (`step_03`)
- 🟢 The tool matches 519 of 524 (99.0%), finds 150 of the 151 missed clocks and raises 4 false alarms. On the planted hard cases it is right on 108 of 109 clocks that land on the due day, 57 of 57 across a holiday and 238 of 241 logged after first contact (`step_04`)
- 🟢 At the as-of date 14 running clocks are due within 5 days, on 14 disputes, and 107 of 150 disputes have at least one missed clock (`step_04`)

**Modeled** (🟡): the windows (2 business days to acknowledge, 7 to decide on a credit, 30 calendar days to investigate, 60 for the extended class, 3 business days to send the final notice), the holiday calendar, the rule that clocks start at first contact, and the rule that the credit clock is also met by finishing the investigation. They are in `data/policy.csv` and `data/holidays.csv`; change one and every number above moves.

**Hypothetical** (🔴): that a real queue misses clocks at anything like this rate, or that business-day counting would move a real queue's numbers by this much. I have not run it on a real dispute export.

## What it still gets wrong

- 🟢 Four clocks on paused investigations are called missed when the plan says they were not (DSP-0036, DSP-0051, DSP-0079 and DSP-0103, all on the investigation clock), and 18 of the 22 paused clocks are right. The bank asked the customer for information and waited; the tool does not read `info_requested_on` or `info_received_on`, so the clock keeps running (`step_03`, `step_04`). This is the known limit I left in on purpose.
- 🟢 One missed clock passes: DSP-0092 was recorded as extended, so the tool gave it 60 days, but the longer window never applied. The tool trusts the recorded window class. Of the 6 such disputes it is right on 5 (`step_04`)
- **The data and the tool share an author.** I planted the dates and wrote the rules. The truth file is labelled by counting elapsed days and the tool steps to a due date, which are two formulations, but both use my holiday list. A closure missing from `holidays.csv` would make both wrong in the same way, so the match rate is a ceiling, not a rate on real disputes. The first version of the data had no wrongly recorded window class; I added it after asking where the tool could pass a late clock.
- **Dates, not times.** A clock is counted in whole days. There is no cut-off hour, so a notice sent after close of business counts for that day.
- **No pauses, restarts or rollover.** A due date that lands on a weekend or a holiday stays there. A customer who adds facts mid-investigation does not restart anything.
- **Events are taken as recorded.** `acknowledged_on` is the date someone entered. The tool cannot tell whether the customer was told.
- **Not a statement of any rule.** "Reg E style" names the shape of the process: acknowledge, provisional credit, investigation window, final notice. The day counts are mine.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does one flat target per case show? | `step_01_flat_target.py` |
| 2 | What does a calendar-day countdown from the logged date get wrong? | `step_02_calendar_countdown.py` |
| 3 | Which fix removes which error, and what is left? | `step_03_deficiencies_exposed.py` |
| 4 | What do business days, first-contact starts and event-driven clocks catch? | `step_04_business_day_clocks.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` at the repo root confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. `python3 -m unittest discover -s tests` runs 41 tests, including a golden test that pins these numbers and tests for empty, wrong-type, truncated and hostile input.

**What came from IncidentLedger.** The vocabulary (an anchor, a window, on time, late, breached, running, not started) and the idea of keeping the windows in a policy file. I rewrote the engine in this folder and imported nothing from it. New here: business days against a holiday file, a clock that starts at an event (the final notice starts at the conclusion), a clock met by the earliest of several events, and a window class per case.

## Aligned to

Nothing. The title says Reg E style because the process has that shape; I did not read Regulation E for this project, and none of the windows is taken from it. I claim no alignment, compliance or certification. If you adapt this, take the windows from counsel's reading of the rule that governs your products.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, bank or real dispute. The calendar is a modeled one. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/disputes.csv`, `data/policy.csv` and `data/holidays.csv` for your own and keep the columns. The tool reads only the dispute columns the policy names, plus `dispute_id`, `dispute_type`, `window_class` and `credit_eligible`; to add a clock, add a policy row that names a new date column. Read the [PRD](./PRD.md) for the scope I held to.
