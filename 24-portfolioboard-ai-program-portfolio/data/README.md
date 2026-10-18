# Sample Data — PortfolioBoard walkthrough

Ten files drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261018` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, program, team, vendor or incident. The owners and teams are invented codes, the program names are generic use-case labels, and no model wrote or scored anything.**

**The truth is known because the data is synthetic.** The generator decides which criteria are unmet, which evidence is stale, which programs are slipped and which attestations are false, and it writes the answer to `program_truth.csv`. A real estate does not hand you that; the first job in a real deployment is wiring a real gate-evidence feed and checking a sample of the "met" flags against the documents.

The headline scenario the walkthrough resolves: **a modeled bank runs 30 AI programs. Each owner reports a color; 19 report green. Against the gate evidence, 4 of those 19 fail a criterion, 6 sit behind a red or slipped upstream program, and model risk review is short in 4 of 4 quarters. With PortfolioBoard, every status is read from the evidence, and 23 of 30 change.**

**This is a test set, not an estimate of how often real programs are mis-reported.** The portfolio is dense in problems on purpose so that every effect appears often enough to count.

---

## Calendar and as-of date

Weeks are counted from the first week of 2023Q1 in 13-week quarters. `AS_OF_WEEK = 200` is a fixed constant in the generator (written to `policy.csv`), in 2026Q4. No script reads the clock. Quarters in `capacity.csv` and `demand.csv` run 2026Q4 to 2027Q3.

## `programs.csv` — 30 programs

| Column | Type | What it is |
| --- | --- | --- |
| `program_id` | string | `P-01` to `P-30`. |
| `name` | string | A generic use-case label. Invented. |
| `stage` | string | `idea`, `discovery`, `build`, `pilot` or `scale`. Counts: idea 5, discovery 6, build 8, pilot 6, scale 5. |
| `owner` | string | An invented owner code (business line and number). 25 distinct owners. |
| `self_reported_rag` | string | The color the owner reports: `green`, `amber` or `red`. |
| `est_benefit_usd` | integer | The owner's estimate of annual benefit in USD. Never measured. |
| `benefit_confidence` | number | The owner's stated confidence in that estimate, 0.3 to 0.9. |
| `target_quarter` | string | The quarter the owner committed to reach scale (or went live, for programs already at scale). |

```
program_id,name,stage,owner,self_reported_rag,est_benefit_usd,benefit_confidence,target_quarter
P-01,Complaint triage assistant,pilot,CX-01,green,2550000,0.9,2027Q3
P-02,Enterprise model gateway,scale,TC-01,green,1450000,0.9,2026Q3
P-03,Dispute case summarizer,build,OP-01,red,1650000,0.7,2027Q2
P-04,KYC document extraction,scale,OP-02,green,4550000,0.7,2026Q3
P-05,Evaluation harness service,pilot,DS-01,amber,2100000,0.9,2027Q3
```

Six programs are shared foundations other programs depend on: three platforms (a model gateway, an evaluation harness, a prompt and tool registry), two data feeds and one approval service.

## `gate_criteria.csv` — 17 criteria across five gates

Each gate admits a program to a stage (gate 1 to idea, gate 5 to scale). A program must hold evidence for every criterion of every gate up to its stage.

| Column | Type | What it is |
| --- | --- | --- |
| `criterion_id` | string | `K01` to `K17`. |
| `gate`, `gate_name` | int, string | The gate the criterion belongs to. |
| `criterion` | string | For example "Risk review complete". |
| `attested_by` | string | Who attests it: the owner or a review team. |
| `max_age_days` | integer | The freshness rule: evidence older than this is stale. An assumption of the modeled bank, not legal advice. |

```
criterion_id,gate,gate_name,criterion,attested_by,max_age_days
K01,1,Intake,Owner named,owner,365
K02,1,Intake,Risk tier assigned,model_risk_review,365
K03,1,Intake,Use case registered in intake,owner,365
K04,2,Discovery entry,Sponsor named,owner,365
```

## `program_evidence.csv` — 286 attestations

One row per program and criterion in force at its stage.

| Column | Type | What it is |
| --- | --- | --- |
| `program_id`, `criterion_id` | strings | Join keys. |
| `met` | yes/no | The attestation. Self-attested: nothing here is checked against a document. |
| `evidence_age_days` | integer | Age of the evidence in days. Blank when `met` is no. |

```
program_id,criterion_id,met,evidence_age_days
P-01,K01,yes,152
P-01,K02,yes,193
P-01,K03,yes,120
P-01,K04,yes,102
P-01,K05,yes,66
```

## `capacity.csv` and `demand.csv`

`capacity.csv` is supply in FTE for four teams (data science, engineering, model risk review, security review) over four quarters. `demand.csv` is the need the owners plan, per program, team and quarter: 464 rows. Planned need rises at the quarter a program passes its exit gate, because the review teams do the gate work. Supply is sized to what the budget can see: data science, engineering and security review close to average demand, model risk review for last year's portfolio.

```
team,quarter,supply_fte
data_science,2026Q4,27.0
data_science,2027Q1,27.0
data_science,2027Q2,27.0
data_science,2027Q3,27.0
```

```
program_id,team,quarter,need_fte
P-01,data_science,2026Q4,1.10
P-01,engineering,2026Q4,1.60
P-01,model_risk_review,2026Q4,0.41
P-01,security_review,2026Q4,0.51
P-01,data_science,2027Q1,0.89
```

## `dependencies.csv` — 25 edges

| Column | Type | What it is |
| --- | --- | --- |
| `program_id` | string | The program that depends on another. |
| `depends_on` | string | The upstream program. |
| `dep_type` | string | `platform`, `data_feed` or `approval`. |

```
program_id,depends_on,dep_type
P-03,P-17,approval
P-04,P-05,platform
P-04,P-17,approval
P-05,P-02,platform
P-06,P-01,data_feed
```

## `stage_history.csv` — 90 stage visits

| Column | Type | What it is |
| --- | --- | --- |
| `program_id`, `stage` | strings | One row per stage a program has entered. |
| `entered_week` | integer | The week it entered the stage. |
| `review_requested_week` | integer | The week it asked for the exit gate review. Blank if not yet requested. This column is what lets the wait at the gate be told apart from the work before it. |
| `exited_week` | integer | The week it left the stage. Blank while it is still there. |

```
program_id,stage,entered_week,review_requested_week,exited_week
P-01,idea,102,131,132
P-01,discovery,132,156,158
P-01,build,158,179,196
P-01,pilot,196,,
P-02,idea,72,87,89
```

The programs entered the portfolio between week 50 and week 190, about one every five weeks, and the stage mix is set so that stage counts follow Little's law for that flow. The generator builds each program's history backwards from its current stage; there is no simulated arrival process. Mean weeks of work before the review request are 22 (idea), 25 (discovery), 24 (build) and 17 (pilot); mean weeks waiting at the exit gate are 2.5, 4, 15 and 12, because model risk and security review sit at the gates after build and pilot. These are generator parameters, not findings. The measured waits are in the step 3 output.

## `wip_limits.csv` and `policy.csv`

`wip_limits.csv` holds one work-in-progress limit per stage: idea 8, discovery 6, build 6, pilot 5, scale 10. A policy assumption of the modeled bank. `policy.csv` holds the as-of week and the calendar convention.

## `program_truth.csv` — what each program's status truly is

Computed by the generator from the true state of each criterion (not from the attested `met`) and the rules in the module docstring. Used only to score: no step reads it to make a decision.

| Column | Type | What it is |
| --- | --- | --- |
| `true_evidence_status` | string | RED if a criterion is truly unmet; AMBER if all are truly met but some evidence is stale; else GREEN. |
| `true_blocked_by` | string | Upstream programs that are truly red or slipped, direct or through a chain. |
| `true_status` | string | RED if evidence is RED; AMBER if evidence is AMBER, the program is slipped, or something upstream blocks it; else GREEN. |
| `false_attestation` | string | The criterion that was attested met with fresh evidence while not truly met. Blank for all but 3 programs. |

```
program_id,true_evidence_status,true_blocked_by,true_status,false_attestation
P-01,AMBER,,AMBER,
P-02,GREEN,,GREEN,
P-03,RED,P-05,RED,
P-04,AMBER,P-05,AMBER,
P-05,RED,,RED,
```

True status totals: 6 green, 11 amber, 13 red. Planted false attestations: P-06 Evaluation plan attached; P-07 Evaluation plan attached; P-24 Data source approved.

---

## How the generator decides the truth

- **Health quota.** Before dependencies, 12 programs have clean evidence, 8 have stale evidence only and 10 have unmet criteria. The six shared foundations are set by hand (two red, one amber, three green; two slipped), because shared services are where dependency risk concentrates. The other 24 are shuffled into the remaining quota.
- **Owners are optimistic.** A program with clean evidence is reported green 85% of the time; stale evidence, 65%; unmet criteria, 55%. Reporting red is rare. These are design choices.
- **Slipped programs.** 5 programs are past their target quarter and not at scale: the two slipped foundations and three drawn at random from discovery, build and pilot.
- **Planted misses.** Exactly 3 non-foundation programs, with no dependents, in build, pilot or scale, get one false attestation: marked met, evidence fresh, not truly met. Nothing in the files reveals it. It is the miss left in on purpose.
- **Sizes and noise.** Each program has a size factor (0.7, 1.0 or 1.3) that scales its planned demand, plus a bounded random factor on each demand row.

## Seed note and the two changes after the first run

`SEED = 20261018` is the first and only seed tried. No seeds were compared. The generator parameters (quotas, probabilities, supply, durations, limits) were set from design reasoning before any output was inspected. Two changes were made after the first run, each for a structural reason rather than to move a number:

1. **A chain edge.** The first run showed that no program reached a bad upstream program only through a chain, so the transitive path of the propagation rule was never exercised. I added one fixed edge to the generator: P-17 (model inventory registration) depends on P-05 (evaluation harness). No random draw moved.
2. **A coherence fix.** A check of the first data found "met" evidence older than the program that attested it (29 of 268 attestations, in 13 programs) and scale-stage target quarters earlier than the quarter the program entered scale. I capped every evidence age at the age of the program, restricted amber (stale) health to programs old enough to hold stale evidence (the shuffle is repeated until that holds), and set a scale-stage program's target quarter to the quarter it entered scale. This moved the health shuffle, and with it the owners' colors, the evidence rows and every figure that depends on them. No supply, demand, probability, quota, duration or limit was touched, and the stage history is byte-for-byte what it was.

The first version printed 0 chain-only cases; the shipped data prints 2 of the 19 green reports reaching a bad upstream program only through a chain.

## What this data cannot tell you

It cannot tell you how often real owners over-report, how often real attestations are false, or how long real reviews take. Those are generator parameters here. The numbers in the walkthrough measure what the status rules do on this mix, not what a real portfolio would show.
