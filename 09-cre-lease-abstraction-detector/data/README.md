# Sample Data — LeaseGuard Walkthrough

Six synthetic lease abstracts plus two ground-truth CSVs. The leases are written to mirror what shows up in a real CRE portfolio: a couple of clean ICSC/BOMA forms, then four progressively non-standard cases that break a deployed lease-NLP pipeline in specific, named ways.

These are synthetic. Names, addresses, and dollar figures are invented. The clause structure and lease language is calibrated against the public ICSC retail-lease template, BOMA office form, and the kinds of redlined leases I have read out of actual CRE portfolios over the past five years.

## Files

| File | What it is |
| --- | --- |
| `leases/lease_01_standard_retail.txt` | Clean ICSC retail lease, all 12 fields findable. Easy. |
| `leases/lease_02_standard_office.txt` | Clean BOMA office lease, stepped escalation table. Easy. |
| `leases/lease_03_non_standard_industrial.txt` | Triple-net industrial with embedded amendments, CPI-floor-cap escalation, ROFO. |
| `leases/lease_04_redlined_retail.txt` | Mall in-line retail with `[STRIKE]`/`[INSERT]` redline markup, CPI-floor-cap, co-tenancy kick-out, exclusivity. The hardest one. |
| `leases/lease_05_with_side_letter.txt` | Office lease + side letter granting ROFO on Floor 13. The ROFO does not appear in the lease body. |
| `leases/lease_06_complex_anchor_tenant.txt` | Anchor tenant power-center lease: stepped escalation, co-tenancy kick-out, sales-based kick-out, four-category exclusivity. |
| `expected_extractions.csv` | The 12 ground-truth fields per lease. The number `step_02` is graded against. |
| `deficiency_classes.csv` | For each lease, which of the six deficiencies trip on it, plus a short note. The number `step_03` is graded against. |

## The 12 fields

Every commercial lease has more than 12 abstractable fields — a typical Argus-style abstract pulls 80-150. We use 12 here because they are the ones an asset-management team actually argues about during a recovery dispute:

```
tenant_name, premises_sf, base_rent_psf, lease_term_months, commencement_date,
escalation_type, escalation_value, cam_cap_psf, cam_base_year,
kickout_clause, exclusivity_clause, ROFO_present
```

If lease-NLP gets these 12 right, the asset manager has a fighting chance during reconciliation. If it gets the escalation type wrong or omits the CAM cap, the landlord has already lost the argument before the dispute starts.

## Redline markup convention

In `lease_04`, redlines are simulated with `[STRIKE]old text[/STRIKE]` and `[INSERT]new text[/INSERT]` markers. In a production OCR pipeline these would be strikethroughs and inserted-text formatting in the source PDF. The point is the same: a vanilla LLM-over-OCR pipeline reads through the markers as if they're regular text, and ends up extracting the *struck* values rather than the *negotiated* ones.

## How this maps to the walkthrough

- `step_01_manual_abstraction.py` ignores the deficiency_classes file. A paralegal reading the lease cover-to-cover gets the right answers regardless of how messy the document is — the bottleneck is time, not accuracy.
- `step_02_deployed_lease_nlp.py` produces a per-lease per-field extraction calibrated to what real Claude-over-OCR pipelines actually produce on these patterns. Graded against `expected_extractions.csv`.
- `step_03_deficiencies_exposed.py` explains every wrong field by mapping it to a class in `deficiency_classes.csv`.
- `step_04_with_leaseguard.py` runs the verification ensemble and produces a triage queue.
