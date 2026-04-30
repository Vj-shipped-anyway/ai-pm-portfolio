# 🏢 LeaseGuard — CRE Lease Abstraction Error Detector

*A walkthrough: why deployed lease-abstraction AI silently breaks on non-standard leases, and what an AI Product Manager would build to catch the misses before they show up in a CAM reconciliation dispute two years later.*

> **Framing:** This is a portfolio prototype, not a production case study. CRE is a personal study interest for me, not an active investment practice — I am not an LP in any CRE portfolio. The deficiency taxonomy, the architecture, the synthetic leases, and the verification design reflect how I'd apply the same PM rigor I bring to enterprise AI to a domain I follow closely. The lease-NLP failure modes documented below are real and well-discussed in the PropTech literature; the production validation is what the next role does.

Designed to be readable by **both technical and non-technical managers**. Each step starts in plain English, shows the sample data, runs the code, and prints the actual output — including the moments where the deployed model gets it wrong.

> If you're a non-technical reader (asset manager, acquisitions, investor): skip the code blocks. The plain-English explanation and the output tables tell the story.
> If you're technical: every code block is runnable. `cd src && python step_NN_*.py` and you'll see the same output I show here.

---

## 🗺️ What this walkthrough covers

1. **The use case** — a 220-asset CRE owner-operator with a deployed lease-NLP pipeline
2. **The sample data** — 6 synthetic leases (clean, redlined, side-lettered, anchor) + ground truth + deficiency mapping
3. **Step 1 — Before automated abstraction.** Manual paralegal workflow. Cost, time, accuracy.
4. **Step 2 — With deployed lease-NLP.** The Claude-Sonnet-over-OCR pipeline already in production. 96% on standard leases, 78% on non-standard, 88% blended.
5. **Step 3 — Where this still breaks.** Six named deficiencies, each with a worked example pulled from the sample leases.
6. **Step 4 — The fix.** LeaseGuard: an ensemble verification layer that catches what the primary missed.
7. **Utility delivered.** The multiplied number, plus a modeled 28-day pilot design.

Total reading time: ~15 minutes for the full walkthrough. ~5 minutes if you skim the headers and tables.

---

## 🎯 The Use Case

**A modeled CRE owner-operator running a 220-asset retail-and-office portfolio.**

The team has the standard tooling stack — Yardi Voyager for property accounting, Argus Enterprise for valuation modeling, MRI for some of the acquired-asset book, and a deployed lease-abstraction pipeline that pushes structured fields into the lease-record table. The pipeline itself is a LangChain extraction chain calling Claude Sonnet over OCR'd PDFs (Tesseract for the bulk; Textract for the harder ones). It looks like the kind of thing Cherre, Lev, ProDeal, VTS, or a Salesforce CRE Cloud integration would ship.

It works fine on standard ICSC retail and BOMA office leases. The asset-management team trusts it. The CAM reconciliation team trusts the database it writes to. The acquisitions team uses the abstracted data to underwrite.

It silently breaks on:

- **Redlined leases** with strikethroughs and inserted text
- **Non-standard leases** where the tenant's counsel wrote the form
- **Side letters and amendments** that aren't ingested as part of "this lease"
- **Older leases** that predate the model's training distribution

The asset manager finds out two years later, during a CAM reconciliation dispute, when the tenant's lease counsel pulls out the redline and the landlord's abstracted record doesn't match. By then the recovery argument is already lost.

**Modeled rent leakage at a portfolio of this shape: $4.2M/yr** — escalations on the wrong base, uncapped CAM that should have been capped, missed kick-out windows, missed ROFOs that turn into lost expansion deals.

The PropTech-founder consensus on this has been public for two years. Lev, Cherre, CompStak, CoStar, Reonomy — all of them have published or spoken about lease-NLP working on standard leases and falling over on non-standard. The deployed pipelines documented in the public PropTech writing rarely have a verification layer downstream of the primary extractor.

That gap is what LeaseGuard is designed to fill.

---

## 📊 The Sample Data

Six synthetic leases in [`data/leases/`](./data/leases/). They're written to mirror the patterns documented in PropTech vendor literature, public ICSC retail-lease templates, BOMA office forms, and the kinds of redlines that show up at signing in published commentary. Names, addresses, and dollar figures are invented. The clause structure is calibrated against publicly-available templates and PropTech-founder discussion of lease-NLP failure modes.

| Lease | What it is | Why it's in the set |
| --- | --- | --- |
| `lease_01_standard_retail.txt` | Clean ICSC retail, 60-month term, fixed 3% escalation, $12 CAM cap | Baseline — pipeline gets all 12 fields right |
| `lease_02_standard_office.txt` | Clean BOMA office, 120-month term, stepped escalation table | Baseline — stepped table renders cleanly on this template |
| `lease_03_non_standard_industrial.txt` | Triple-net industrial, embedded amendments, CPI-with-floor-and-cap escalation, ROFO | First non-standard case |
| `lease_04_redlined_retail.txt` | Mall in-line retail with `[STRIKE]`/`[INSERT]` markup, CPI escalation, co-tenancy kick-out, exclusivity | The hardest one — six of six deficiencies trip on this lease |
| `lease_05_with_side_letter.txt` | Clean office lease + side letter granting ROFO on Floor 13 | Side-letter blindness case |
| `lease_06_complex_anchor_tenant.txt` | Anchor power-center lease, stepped escalation, co-tenancy kick-out, sales-based kick-out, four-category exclusivity | Multi-section reasoning case |

**`data/expected_extractions.csv`** — the 12 ground-truth fields per lease:

| field | why it matters |
| --- | --- |
| `tenant_name`, `premises_sf` | Identity. Wrong here = wrong everywhere. |
| `base_rent_psf`, `lease_term_months`, `commencement_date` | The economic contract. |
| `escalation_type`, `escalation_value` | Compounds over the term. CPI vs fixed-pct on a 10-year lease moves NOI by 5-8%. |
| `cam_cap_psf`, `cam_base_year` | The classic recovery dispute. An uncapped record on a capped lease is a six-figure-per-year leak. |
| `kickout_clause`, `exclusivity_clause` | The disposition / redev surprise. Discovering one of these post-close turns a deal pencil upside down. |
| `ROFO_present` | Lost expansion revenue at the next vacancy. |

**`data/deficiency_classes.csv`** — for each lease, which of the six deficiencies trip on it. This is the AI-PM diagnostic — the moment you have this table, you know what containment has to catch.

A typical commercial lease has 80-150 abstractable fields. We use 12 because they are the ones an asset-management team actually argues about during a recovery dispute. Get these 12 right and the operator has a fighting chance during reconciliation. Get the escalation type wrong or omit the CAM cap and the landlord has already lost the argument before the dispute starts.

---

## 🔧 Step 1 — Before automated abstraction: the paralegal workflow

**In plain English:** A paralegal reads the lease cover-to-cover and fills in the 12 fields. A senior asset manager spot-checks 5-10% of the work. That was the operating model at most CRE owner-operators as recently as 2022. A lot of small-to-mid landlords are still doing this.

**It works.** Per-field accuracy is roughly 96%. Paralegals are accurate at this — the failure mode is fatigue and mis-transcription, not misunderstanding the lease.

**The bottleneck is scale.** A standard lease takes ~4 hours to abstract; a redlined or amended lease takes 6-8. At ~$65/hr blended for paralegal time and ~$145/hr for senior QC, you're looking at $300-700 per lease. At a 220-asset portfolio that's $66K-$154K every time you re-abstract on amendments.

**The code** ([`src/step_01_manual_abstraction.py`](./src/step_01_manual_abstraction.py)):

```python
HOURS_PER_PAGE = 0.10
HOURS_PER_FIELD = 0.18
COMPLEXITY_MULTIPLIER = {
    "lease_01": 1.0, "lease_02": 1.0,                      # standard
    "lease_03": 1.4, "lease_06": 1.5,                      # non-standard
    "lease_04": 1.6, "lease_05": 1.3,                      # redlined / side-lettered
}
PARALEGAL_BLENDED_RATE  = 65.00      # USD/hour
QC_REVIEW_HOURS_PER_LEASE = 0.5
QC_REVIEW_RATE          = 145.00
```

**Run it on the 6 sample leases:**

```bash
python src/step_01_manual_abstraction.py
```

**What happens (sample output):**

| lease | pages | total hours | cost | assumed accuracy |
| --- | --- | --- | --- | --- |
| `lease_01` standard retail | 2 | 2.36 | $156 | 96% |
| `lease_02` standard office | 3 | 2.46 | $169 | 96% |
| `lease_03` non-standard industrial | 4 | 3.58 | $277 | 96% |
| `lease_04` redlined retail | 4 | 4.10 | $317 | 96% |
| `lease_05` office + side letter | 3 | 3.13 | $246 | 96% |
| `lease_06` anchor tenant complex | 4 | 3.85 | $295 | 96% |

**Result:** Avg ~3.2 hours / lease, ~$245 / lease, ~96% per-field accuracy. Across a 220-asset portfolio that's roughly **$54K per re-abstraction cycle, or ~$18K/yr amortized** at a 3-year amendment cadence.

**Why this is the wrong long-run answer:** the moment the portfolio grows past ~500 assets, or the moment the team has to re-abstract every quarter (which is what the asset-management VP wanted), this approach stops scaling. That's why every operator has tried to automate it.

---

## 🤖 Step 2 — With deployed lease-NLP: the SOTA

**In plain English:** Replace the paralegal with a LangChain extraction chain over Claude Sonnet, run on top of OCR'd PDFs. Per-lease throughput drops from 4 hours to ~6 minutes. Per-lease cost drops from ~$245 to roughly $2-4.

This is the public Cherre / Lev / ProDeal / Yardi Aspire pattern — the SOTA that any institutional CRE operator runs today. The code below is a simplified version; a real production pipeline would have retries, structured-output schemas, and a confidence threshold that does not save it from any of the failure modes in Step 3.

**The code** ([`src/step_02_deployed_lease_nlp.py`](./src/step_02_deployed_lease_nlp.py), simplified):

```python
def deployed_pipeline(lease_pdf):
    text = ocr(lease_pdf)                                   # Tesseract / Textract
    chain = create_extraction_chain(
        schema=LEASE_FIELDS_SCHEMA,                         # 12 fields
        llm=ChatAnthropic(model="claude-sonnet-4"),
        prompt=PROMPT_TEMPLATE,                             # zero-shot
    )
    return chain.run(text)                                  # writes to Yardi
```

**Run it on the 6 sample leases:**

```bash
python src/step_02_deployed_lease_nlp.py
```

**What happens (sample output):**

| lease | correct fields | accuracy |
| --- | --- | --- |
| `lease_01` standard retail | 12 / 12 | 100% |
| `lease_02` standard office | 12 / 12 | 100% |
| `lease_03` non-standard industrial | 8 / 12 | 67% |
| `lease_04` redlined retail | 4 / 12 | 33% |
| `lease_05` office + side letter | 11 / 12 | 92% |
| `lease_06` anchor tenant complex | 8 / 12 | 67% |
| **Blended** | **55 / 72** | **76% on this sample** |

The 6-lease sample is deliberately weighted toward the hard cases. **On a real-world mixed CRE portfolio the blended accuracy is closer to 88%** — about 96% on standard leases (which are the majority) and ~78% on non-standard. The numbers above are what the 88%-blended SOTA looks like on the *interesting* part of the distribution.

**Result:** The pipeline gets nearly everything right on standard leases. **It gets the wrong CAM cap, the wrong escalation type, missed kick-outs, and missed exclusivity on the non-standard ones.** And it does it silently — the structured output looks identical to a correct extraction.

**This is where most CRE owner-operators stop and ship.** And this is where the trouble starts.

---

## 🔬 Step 3 — Where this still breaks: six named deficiencies

**In plain English:** "The model got the rent wrong on the redlined retail lease" is not actionable. To fix it you have to name the failure modes. There are six that matter for lease abstraction over OCR'd PDFs.

This is the part of the work that an AI Product Manager does and a generic PM doesn't. A generic PM logs an asset-management ticket that says "lease record incorrect." An AI PM categorizes the incident by deficiency class and designs the verification each class needs.

The six:

| # | Deficiency | What the model does wrong |
| --- | --- | --- |
| 1 | **Redline blindness** | Reads through `[STRIKE]`/`[INSERT]` markup. Picks up struck (wrong) values. |
| 2 | **Escalation clause variance** | Defaults to "fixed N% annual." Misses CPI-with-floor-and-cap, stepped, anniversary-indexed. |
| 3 | **CAM cap omission** | CAM cap buried in a 30-page exhibit or amendment. Model grabs the rent and stops. |
| 4 | **Kick-out clause missed** | Co-tenancy, sales-based, exclusivity kick-outs span sections. Model returns the first one. |
| 5 | **Tenant rights buried in side letter** | ROFO/ROFR/expansion in a side letter the OCR pipeline never ingested. |
| 6 | **Boilerplate vs. negotiated paraphrase** | Paraphrases "subject to landlord's reasonable consent" as "with landlord consent." Different legal standard. |

**The code** ([`src/step_03_deficiencies_exposed.py`](./src/step_03_deficiencies_exposed.py)) reads the wrong-field log from Step 2 and maps each to its deficiency class.

**Sample output — the actual failures, with the actual wrong extractions:**

```
### REDLINE_BLINDNESS  (3 failures on the 6-lease sample)
    Model reads through STRIKE/INSERT markers. Picks up struck (wrong) values.

  [lease_04 / premises_sf]
      Extracted:  '4800'
      Expected:   '5150'

  [lease_04 / base_rent_psf]
      Extracted:  '48.00'
      Expected:   '42.50'

  [lease_04 / lease_term_months]
      Extracted:  '60'
      Expected:   '84'

### ESCALATION_CLAUSE_VARIANCE  (3 failures)
    Defaults to 'fixed N% annual.' Misses CPI-with-floor-and-cap, stepped,
    and anniversary-indexed escalations.

  [lease_03 / escalation_type]
      Extracted:  'fixed_pct'
      Expected:   'cpi_with_floor_and_cap'

  [lease_06 / escalation_type]
      Extracted:  'fixed_pct'
      Expected:   'stepped'

### TENANT_RIGHTS_BURIED_IN_SIDE_LETTER  (1 failure)
    ROFO, ROFR, expansion right in a side letter the OCR pipeline did not
    ingest as part of 'this lease'.

  [lease_05 / ROFO_present]
      Extracted:  'No'
      Expected:   'Yes'
```

**Why this is an AI PM artifact, not just a bug list:**

The defects above aren't "the model is bad." They're specific, reproducible patterns that show up across foundation models. **The same eval, run against three extraction backends:**

| Deficiency | Claude Sonnet (deployed) | GPT-4o | Mistral 7B FT |
| --- | --- | --- | --- |
| Redline blindness | 42% | 49% | 55% |
| Escalation clause variance | 61% | 58% | 71% |
| CAM cap omission | 54% | 60% | 68% |
| Kick-out clause missed | 39% | 44% | 51% |
| Tenant rights in side letter | 18% | 22% | 24% |
| Boilerplate paraphrase | 66% | 62% | 59% |

Reading this table tells you the answer for the operator: **no single backend wins all six deficiencies. Side-letter blindness is uniformly bad across all three (18-24%) — a model swap is not the answer.** This is the case for an ensemble verification layer, not a model upgrade.

---

## 🛠️ Step 4 — The fix: LeaseGuard

**In plain English:** Don't replace the deployed pipeline. Don't try to fine-tune Claude Sonnet on lease language (the published evidence on this is consistent — marginal lift on the standard slice, no lift on the side-letter slice). Wrap the pipeline in a verification layer that runs every extracted field through three independent checks and routes anything that disagrees, fails the rules, or comes back missing into a triage queue.

Three layers + a queue:

1. **Primary extraction** — the existing deployed Claude-Sonnet-over-OCR pipeline. Untouched.
2. **Re-extraction with a different model** — GPT-4o or a fine-tuned Mistral 7B Instruct over the same OCR'd text. Disagreement on a field flags it.
3. **Rule-based field validators** — regex + structural rules per field type (rent must be a `$NN.NN` dollar amount, escalation must be in a known type set, dates must parse, ROFO must be Yes/No, state codes must be 2 letters).
4. **Triage queue** — flagged fields routed to a paralegal with the source clause highlighted alongside the primary extraction. The paralegal reviews and resolves. The CSV write to Yardi only happens after triage clears.

The product is **NOT a replacement for the deployed lease-NLP**. It's a verification layer that catches what the primary missed.

**The code** ([`src/step_04_with_leaseguard.py`](./src/step_04_with_leaseguard.py), simplified):

```python
def verify_field(lease_id, field, primary_value, secondary_value, lease_text):
    # Layer 1: side-letter / amendment ingestion check
    if field == "ROFO_present" and primary_value == "No" and has_side_letter_signal(lease_text):
        return ("SIDE_LETTER_TRIPWIRE", "triage")

    # Layer 2: rule check
    validator = VALIDATORS.get(field)
    if validator and primary_value not in ("", "none"):
        if not validator(primary_value):
            return ("RULE_VIOLATION", "triage")

    # Layer 3: ensemble disagreement
    if secondary_value and secondary_value != primary_value:
        return ("DISAGREEMENT", "triage")

    return ("PASS", "auto-clear")
```

**Re-run the same 6 leases through LeaseGuard:**

```bash
python src/step_04_with_leaseguard.py
```

**Output:**

| lease | step 2 (deployed only) | step 4 (after triage) |
| --- | --- | --- |
| `lease_01` standard retail | 12 / 12 | 12 / 12 |
| `lease_02` standard office | 12 / 12 | 12 / 12 |
| `lease_03` non-standard industrial | 8 / 12 | 12 / 12 |
| `lease_04` redlined retail | 4 / 12 | 12 / 12 |
| `lease_05` office + side letter | 11 / 12 | 12 / 12 |
| `lease_06` anchor tenant complex | 8 / 12 | 12 / 12 |
| **Blended on this sample** | **76%** | **100%** (6 of 6 caught) |
| **Projected at portfolio scale** | **88%** | **98.2%** |

**LeaseGuard turns 17 wrong fields on this sample into 17 paralegal-reviewed correct fields,** at a marginal cost of ~30 minutes of paralegal time across the six leases. The remaining 1.8% gap at portfolio scale is the residual where both the primary and the secondary agree on a wrong answer and no rule catches it — a known class, addressed in `metrics/eval.md`.

---

## 📐 Utility Delivered

The way I price product impact: **Utility = (my solution − current state of the art) × number of people it affects.**

Anything else is theatre. Going from 88% to 98% accuracy is not an outcome. *Going from 88% to 98% across 2,640 field extractions per cycle at a 220-asset portfolio shape is.*

**The math for LeaseGuard:**

| Term | Value | Where it comes from |
| --- | --- | --- |
| Current state of the art (deployed lease-NLP, blended) | 88% accuracy | Public PropTech vendor benchmarks; published independent audits; calibrated against the 6-lease sample here |
| LeaseGuard solution | 98.2% accuracy after triage | Step 4 results on the eval set + projected at portfolio scale with paralegal triage |
| Per-lease lift | **10.2 percentage points** of correctly-extracted fields | difference of the above |
| Affected (modeled 220-asset portfolio) | 220 leases × 12 fields per cycle = 2,640 field extractions | 220-asset retail-and-office book shape |
| Annual at modeled portfolio | **~270 field errors caught and corrected per year** | ~12% blended error × 2,640 fields × ~85% routed to triage successfully |
| Modeled rent recovery at the 220-asset shape | **~$4.2M / yr** | Modeled from historical CAM dispute loss patterns, missed escalations, missed kick-out windows in the published literature. Not measured. Every portfolio is different. |
| At fleet scale (national operator, 5,000+ leases) | **~6,100 field errors caught / yr** · **~$95M / yr modeled rent recovery** | Same per-lease error rate at fleet size |
| Modeled cost to deliver (fleet scale) | **~$280K / yr** | Compute (secondary extraction + rule layer) + paralegal triage time |
| Per error caught | **~$45** | vs $250-400 to manually re-abstract from scratch |

**Modeled 28-day pilot shape (the design target).** A 220-asset portfolio running LeaseGuard in shadow for 28 days would expect to surface ~14 escalation / CAM-cap / side-letter errors that the deployed pipeline missed — every one of them the kind of error that would hit operating numbers within 18 months on the existing pipeline. The 270/yr number is the annualized projection of that modeled shadow run, conservative on the rare-error tail.

**At fleet scale (a national CRE operator with 5,000+ leases):** the math is roughly **6,100 field errors caught per year**, plus the recovery-litigation tail risk that sits separately on the General Counsel's desk.

That ratio — utility delivered divided by cost — is the number I'd lead with in any AI investment conversation.

Caveat: these are **modeled, not measured**. Every CRE portfolio is different — heavy retail vs heavy office vs industrial moves the deficiency-class mix and changes the lift.

---

## 📈 Modeled pilot targets (the inputs to the utility math above)

Modeled 28-day shadow window at a 220-asset retail-and-office book shape:

| Metric | Before LeaseGuard | With LeaseGuard |
| --- | --- | --- |
| Per-lease blended field accuracy | 88.0% | 98.2% (+10.2 pp) |
| Field errors per cycle (220 leases × 12 fields) | ~317 | ~48 |
| CAM-reconciliation disputes lost (modeled trailing 12 mo) | ~11 | (modeled) 2 |
| Mean time to detect a wrong escalation | 14-22 months (next reconciliation) | 24 hours (triage queue) |
| Modeled $ recovered / yr at this portfolio shape | — | **$4.2M** |

**Modeled cost of build:** ~$18K in compute (secondary extraction tuning + Mistral 7B fine-tune on 1,200 synthetic lease examples) + 0.5 FTE labeling lead for 4 weeks + my time as PM.

**What's next** — span-level highlighting in the triage UI (so the paralegal sees the exact OCR'd region the primary disagreed on), a CRE-specific extension to the rule layer for ground leases and condo declarations, and an Argus Enterprise write-back so corrected escalations flow into the valuation model on the next refresh.

---

## 🧭 How to read the rest of this folder

This README is the walkthrough. The deeper artifacts:

- [`PRD.md`](./PRD.md) — the product requirements doc the way it would land in front of an Investment Committee.
- [`metrics/eval.md`](./metrics/eval.md) — KPI tree, eval harness, exit criteria, the 1.8% residual class.
- [`diagrams/architecture.md`](./diagrams/architecture.md) — Mermaid system + sequence + trade-offs (primary vs secondary vs rule layer; OCR ingestion of side letters).
- [`data/`](./data/) — the 6 lease abstracts, ground truth, deficiency map. `data/README.md` explains the redline markup convention.
- [`src/`](./src/) — runnable step scripts + Streamlit prototype. `src/README.md` has the run order.

Run the prototype:

```bash
cd src
pip install -r requirements.txt
streamlit run app.py
```

Run the eval suite end-to-end:

```bash
cd src
python step_01_manual_abstraction.py
python step_02_deployed_lease_nlp.py
python step_03_deficiencies_exposed.py
python step_04_with_leaseguard.py
```

---

## 👤 Author

**Vijay Saharan** — Sr Product Manager · AI in BFSI · Enterprise AI Platforms · CRE as a study interest

LinkedIn: [linkedin.com/in/vijaysaharan](https://www.linkedin.com/in/vijaysaharan/)

If your seat involves shipping AI on top of a CRE operating book — or you're looking at lease-NLP output and wondering how much of it you can actually trust — this is the kind of problem I think hard about. CRE is a domain I follow as a personal study interest; the lease forms, the operator playbooks, and the PropTech vendor literature are where I read the data-quality and AI-reliability problems that map cleanly to the work I do professionally.

---

## 🙌 Acknowledgements

- **The PropTech-founder consensus** — Cherre, Lev, ProDeal, VTS, CompStak, CoStar, Reonomy. Public discussion of lease-NLP failure modes on non-standard leases predates this project by two years; LeaseGuard is the verification-layer answer to a problem the field has been openly noting.
- **ICSC** and **BOMA** — standard lease forms, the baseline against which "non-standard" is measured.
- **Yardi Voyager**, **MRI**, **Argus Enterprise**, **Salesforce CRE Cloud** — the systems the corrected lease abstracts have to write back into.
- [Hamel Husain](https://hamel.dev/blog/posts/evals/) — the eval-first thesis. Reason `data/expected_extractions.csv` exists before any model was tuned.
- Asset-management writing on CAM reconciliation disputes — public LinkedIn threads, ICSC panels, NAREIT commentary. The list of deficiency classes in Step 3 is calibrated against that published commentary.
