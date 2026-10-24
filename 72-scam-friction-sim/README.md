# ⏳ scam-friction-sim (real-time payments): what a 20-minute hold stops, and who waits

**I wanted to know what holding a suspicious real-time payment for 20 minutes would actually do: how much scam value it stops, and how many people who did nothing wrong have to wait for it. This is a small simulator with named assumptions. It replays 12,000 synthetic payments against a hold policy and prints both columns side by side. The stop side rests on what a held victim does, which I had to invent; the friction side is the part a bank controls, and it is where a blanket rule and a scored rule differ most.**

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 72-scam-friction-sim/src && python3 scam_friction_sim.py --demo
```

It prints:

```text
payments: 12000 (330 scam, 11670 legitimate); hold 20 minutes
  none (no hold)                             stopped   0.0% of scam value, legit held    0 (0.0%), legit lost 0
  blanket (new payee, amount >= 500)         stopped  21.6% of scam value, legit held  336 (2.9%), legit lost 10
  score (hold >= 8, warn >= 6)               stopped  20.1% of scam value, legit held   52 (0.4%), legit lost 2
```

Standard library only, Python 3.9 or newer. To score your own files: `python3 scam_friction_sim.py run --payments p.csv --truth t.csv --policy score --hold-score 8 --warn-score 6 --assumptions a.json`. It exits 1 when `--max-held-pct` or `--min-stopped-pct` is broken, and 2 for malformed input.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 12000 payments, 330 of them scams; the script is named in brackets):

- 🟢 With no hold, the 330 scam payments are worth $403,678 of the $3,202,027 moved (12.6%), none is stopped and nobody waits (`step_01`)
- 🟢 A blanket hold on every first payment to a new payee of 500 or more stops 21.6% of scam value ($87,222 of $403,678) and holds 336 of 11670 legitimate payments (2.9%); 10 of those customers give up and 6720 minutes are spent waiting, or 6.6 legitimate holds for every scam payment stopped (`step_02`)
- 🟢 The blanket rule holds 262 of the 330 large legitimate first payments, which is the hard negative that makes it noisy (`step_02`)
- 🟢 Holding every payment would stop 29.7% of scam value with no coaching and 24.0% with coaching at 0.2, so the ceiling comes from what held victims do and not from the rule (`step_03`)
- 🟢 Scale the assumed give-up probabilities by 0.5, 1 and 1.5 and the same blanket rule stops 15.5%, 21.6% and 31.3% of scam value; coaching at 0, 0.2, 0.5 and 0.8 gives 26.2%, 21.6%, 15.5% and 9.4% (`step_03`)
- 🟢 If scams are one-tenth as common the blanket rule holds 65.9 legitimate payments per scam payment stopped, and at one-hundredth, 658.8 (`step_03`)
- 🟢 A scored hold (hold at 8 or more, warn at 6 and 7, chosen by a 0.5% friction budget) stops 20.1% of scam value, holds 52 legitimate payments and loses 2, against 21.6%, 336 and 10 for the blanket rule; legitimate holds per scam payment stopped fall from 6.6 to 1.1 (`step_04`)
- 🟢 Holding only, at the blanket rule's friction (289 legitimate payments held, score 6 or more), the scored rule stops 22.9% of scam value, so at equal friction the gain is small and the gain is mostly in the friction cut (`step_04`)
- 🟢 The scored rule holds 51 of the 330 large legitimate first payments, against 262 (`step_04`)
- 🟢 Under coaching at 0.5 the scored rule stops 14.2% and the blanket rule 15.5%; at 0.8, 8.3% and 9.4%. With scams one-tenth as common, the scored rule holds 10.8 legitimate payments per scam payment stopped, against 65.9 (`step_04`)

**What I assumed** (🟡 modeled: the values are invented and named in [`data/assumptions.json`](./data/README.md); the print-out of step 1 lists them):

- 🟡 A held victim gives up with probability 0.4 for a coached live scam, 0.1 for a slow-burn one, 0.35 for an account takeover (the owner sees the hold) and 0.15 for a payment to an established payee
- 🟡 A scammer in touch with the victim has coached them through the hold in 0.2 of cases; a held legitimate payment is abandoned in 0.03; a warning has 0.3 of a hold's effect
- 🟡 The 20 minutes comes from the project idea; the stop probability does not depend on length

**What I could not know** (🔴 hypothetical):

- 🔴 That a real hold changes a real victim's mind at any of these probabilities. I have no data on it, and the whole stop side depends on it

## What it still gets wrong

- 🟢 144 of 330 scam payments get neither a hold nor a warning from the scored rule ($72,204). All 60 payments to a payee the customer has paid before pass untouched, and the best score among them is 3; to hold half of them the threshold would drop to 1, which would hold 3973 of 11670 legitimate payments (34.0%) (`step_03`, `step_04`). That is the known miss, left in on purpose.
- **The test set and the rules share an author.** I planted the scenarios and wrote the score, so the result shows the rules cover what I planted. I included three hard negatives (large legitimate first payments, night payments from a new device, payments during a call) and one hard case (the established payee); the first are held more than I would like and the second is missed entirely. Treat the numbers as a ceiling for these rules, not a rate on real payments.
- **The stop side is invented.** Every probability is an assumption, and the sweeps above show the answer moves from 15.5% to 31.3% as they move. I would not quote any stopped percentage from this project as a finding.
- **The share of scams is far above any real share** (330 in 12000). The ratio of legitimate holds to scams stopped scales with it, which is why step 3 and step 4 print it at one-tenth as well.
- **No hold-length curve.** Five, 20 and 60 minutes stop the same share, because the model says so. Whether a shorter hold works as well is the question a real trial has to answer.
- Not modeled: repeat attempts after a release, a payment moved to another rail, support calls, a scammer who adapts to the hold, recovery after money has left, and the cost of a scam to the customer beyond its dollar value.
- I did not read any rule that sets or limits a hold on a real-time payment and I cite none. This project does not say a 20-minute hold is permitted or advisable on any rail.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What passes when nothing is held, and what do the assumptions say? | `step_01_no_hold.py` |
| 2 | What does the rule most teams start with stop, and who does it hold? | `step_02_blanket_hold.py` |
| 3 | Where does that number stop being trustworthy? | `step_03_deficiencies_exposed.py` |
| 4 | What does a scored hold with a warning band change? | `step_04_scored_hold.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The scenario of each payment is drawn first and the rules never see it, so the labels do not come from the rules.

## Aligned to

Vice Chair for Supervision Michelle Bowman's speech on consumer fraud, ["A Coordinated Approach to Consumer Fraud Protection"](https://www.federalreserve.gov/newsevents/speech/bowman20260505a.htm), Federal Reserve Board, 2026-05-05 (read 2026-10-24). It treats fraud as a banking-system problem and describes a customer who goes ahead with a fraudulent transfer despite a bank employee's concern. I found no discussion of holding payments, hold lengths or customer friction in it, so this project does not borrow a parameter from it. It tests one mechanism a bank might use in that situation. It is a prototype, aligned to that framing and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer, payment rail or bank. A prototype on synthetic data with invented customer behaviour, not a production case study. See [`data/README.md`](./data/README.md) for every assumption and the planted scenarios.

## Fork it

Replace `data/assumptions.json` with your own beliefs and rerun any step, or swap `data/payments.csv` and `data/truth.csv` for your own labelled history and keep the columns. The truth file needs an explicit `scenario` column for scams, and the stored draws can be any uniform numbers from 0 up to 1. Read the [PRD](./PRD.md) for the scope I held to.
