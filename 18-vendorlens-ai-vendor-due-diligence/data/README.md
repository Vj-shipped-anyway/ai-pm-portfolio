# Sample Data — VendorLens walkthrough

Five CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261018` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, vendor, model provider, regulator dataset or incident. Vendor ids (V-01 to V-40) and model providers (MP-1 to MP-5) are invented codes. The answers and documents are written by the generator, not by a vendor or a model.**

**The truth is known because the data is synthetic.** The generator decides, for every vendor, the real quality of its controls, how much it over-claims, how exposed it is and which model provider it really runs on. It then writes the questionnaire answers, the documents and the contract terms the bank would see. A real estate does not hand you the first half; the first job in a real deployment is collecting the documents and contract terms that stand behind the answers.

The headline scenario the walkthrough resolves: **a modeled bank has 40 AI vendors and a 20-question questionnaire with an 85% pass line. 29 vendors pass, including 6 of the 10 that are truly high risk. MP-1 carries 42.9% of the 56 critical use cases and no question asks about it. 33 vendors have no tested exit. With VendorLens, each answer is weighed against a document or the contract, the provider is mapped, exit is scored, and 8 vendors are rated HIGH, 5 of them truly high risk.**

---

## What was designed, what was tried, and what changed

The brief for the generator is to make every effect appear often enough to count. It is a test set, not an estimate of how often real vendors over-claim, how often real documents are stale, or how concentrated a real bank is.

- **Seed.** `20261018` is the only seed used. I did not search for a seed.
- **Two parameters changed after the first run, before any scoring code existed.** (1) The first run passed only 15 of 40 vendors at the 85% line. A questionnaire that passes under 40% of vendors would not be the failure being modeled, so I raised the base yes rate and the share of over-claiming vendors. (2) The first run set the true HIGH line at a latent score of 0.30 and produced 19 of 40 HIGH. I moved the lines to 0.40 (HIGH) and 0.24 (MEDIUM) so that about a quarter of vendors are HIGH. Both were changes to the data design; neither was made after seeing a VendorLens score, which did not exist yet.
- **Provider assignment is redrawn until three conditions hold.** Exactly one provider is above 40% of critical use cases in the disclosed view and below 50%; that provider's true share is at least 6 points higher than its disclosed share; no other provider is above 40% in the true view. The generator needed 13 draws. This is a design condition, stated so a reader does not mistake the 42.9% for a random result.
- **The latent risk score has an unobserved part.** Every vendor carries a hidden factor that no field in the CSVs reveals, so no scoring method built from answers, documents and contracts can reproduce the truth exactly.
- **Where agreement is by construction.** The generator and VendorLens both treat critical vendors with customer data as more exposed and both read the same exit and contract fields. The weights differ, but agreement on those parts is partly by construction. The part that is not by construction is control quality: the truth uses the vendor's real controls, and VendorLens sees them only through answers and documents.

## `vendors.csv` — 40 vendors

| vendor_id | service_type | criticality | data_access | use_cases_supported | critical_use_cases | model_provider | exit_clause | portability_days | exit_tested | audit_right | model_change_notice_days | last_assessed_on | contract_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V-01 | translation | standard | none | 2 | 0 | MP-1 | yes | 21 | no | no | 0 | 2026-08-30 | 2028-03-08 |
| V-02 | collections outreach | standard | internal | 2 | 0 | MP-1 | no | - | no | yes | 0 | 2025-12-23 | 2026-12-24 |
| V-03 | HR screening support | important | internal | 5 | 1 | MP-4 | yes | 131 | no | no | 0 | 2024-12-14 | 2027-10-13 |
| V-04 | enterprise search | standard | internal | 1 | 1 | MP-1 | no | - | no | no | 90 | 2026-06-27 | 2028-05-09 |

| Column | Type | What it is |
| --- | --- | --- |
| `vendor_id` | string | `V-01` to `V-40`, invented. |
| `service_type` | string | A generic service description, such as "customer chat assistant" or "KYC document extraction". Not a product. |
| `criticality` | string | `critical`, `important` or `standard`. 10, 14 and 16 vendors. |
| `data_access` | string | `customer_pii`, `internal` or `none`. 15, 16 and 9 vendors. |
| `use_cases_supported` | int | How many of the bank's use cases the vendor supports. |
| `critical_use_cases` | int | How many of those are critical use cases. Concentration counts these: 56 across the estate. |
| `model_provider` | string | The upstream model provider, `MP-1` to `MP-5`, or blank when the vendor does not disclose it (5 vendors). |
| `exit_clause` | `yes`/`no` | Whether the contract has an exit clause. |
| `portability_days` | int | Days the vendor says it needs to port data and cut over. Blank when there is no exit clause. |
| `exit_tested` | `yes`/`no` | Whether an exit has ever been tested. Only possible with a clause. |
| `audit_right` | `yes`/`no` | Whether the contract gives the bank a right to audit. |
| `model_change_notice_days` | int | Contracted notice before a model version changes. 0 means no commitment. |
| `last_assessed_on` | date | Last full assessment. As-of date is `2026-10-15`, a constant in the generator and in `step_01`. |
| `contract_end` | date | Contract end date. |

## `questions.csv` — 20 questions

| question_id | group | text | verified_by |
| --- | --- | --- | --- |
| Q01 | security | Access to customer data is limited by role and reviewed | independent_control_report |
| Q02 | security | Data is encrypted at rest and in transit | independent_control_report |
| Q03 | security | Security events are logged and monitored | independent_control_report |
| Q04 | security | An incident response plan exists and is exercised | independent_control_report |

`verified_by` says what could back an answer: `independent_control_report` (Q01 to Q06), `penetration_test` (Q07 to Q10), `model_documentation` (Q11 to Q14), `contract` (Q15 and Q16, checked against `model_change_notice_days` and `audit_right`) or `none` (Q17 to Q20, which nothing in this repo can check). No question asks which upstream model provider a vendor runs on, and none asks about exit.

## `questionnaire.csv` — 40 vendors by 20 answers

One row per vendor, one column per question, values `yes`, `partial` or `no`. These are the vendor's own answers: 800 in total. A vendor passes at 85% yes, which is 17 of 20.

## `evidence.csv` — 92 documents

| vendor_id | doc_type | issued_on | covers_ai_service |
| --- | --- | --- | --- |
| V-01 | independent_control_report | 2026-01-05 | yes |
| V-01 | penetration_test | 2024-12-17 | yes |
| V-02 | independent_control_report | 2025-12-10 | yes |
| V-02 | model_documentation | 2026-03-15 | yes |

| Column | Type | What it is |
| --- | --- | --- |
| `vendor_id` | string | Join key. |
| `doc_type` | string | `independent_control_report`, `penetration_test` or `model_documentation`. |
| `issued_on` | date | Issue date. A document older than 365 days at the as-of date is stale. |
| `covers_ai_service` | `yes`/`no` | Whether the document covers the AI service or only another part of the vendor. `no` means out of scope. |

38 of 40 vendors supplied at least one document. Some vendors supplied an older second document of the same type. The generator makes a document more likely for a vendor with better real controls, but a document says nothing about whether the vendor's answers are true: a vendor can over-claim and still have a valid document.

## `truth.csv` — what the generator decided

| vendor_id | true_risk | latent_risk | overclaimed_answers | provider_disclosed | true_model_provider |
| --- | --- | --- | --- | --- | --- |
| V-01 | low | 0.190 | 0 | yes | MP-1 |
| V-02 | low | 0.218 | 1 | yes | MP-1 |
| V-03 | medium | 0.336 | 2 | yes | MP-4 |
| V-04 | low | 0.225 | 1 | yes | MP-1 |

| Column | Type | What it is |
| --- | --- | --- |
| `vendor_id` | string | Join key. |
| `true_risk` | string | `high`, `medium` or `low`, from the latent score. 10, 14 and 16 vendors. |
| `latent_risk` | float | The latent score behind the class. See below. |
| `overclaimed_answers` | int | How many of the vendor's 20 answers said better than the truth (yes for a partial, yes or partial for a no). 79 across the estate. |
| `provider_disclosed` | `yes`/`no` | Whether the vendor tells the bank its upstream provider. 5 vendors do not. |
| `true_model_provider` | string | The provider the vendor really runs on. This is how the truth about hidden fourth parties is known by construction. |

**The latent score.** `latent = weakness x (0.35 + 0.65 x exposure) + noise`, where weakness is 0.45 x (1 - real control quality) + 0.20 x exit gap + 0.08 x contract gap + 0.12 x concentration (1 when the vendor's real provider carries more than 40% of critical use cases) + 0.15 x a hidden factor; exposure is 0.55, 0.30 or 0.10 for critical, important or standard plus 0.45, 0.15 or 0 for customer PII, internal data or none; noise has a standard deviation of 0.02. HIGH is 0.40 or more, MEDIUM is 0.24 or more. These are the generator's rules for this exercise, not a statement about real vendors.

**Over-claiming.** A vendor whose real control quality is below 0.55 over-claims heavily with probability 0.55, and any other vendor with probability 0.30. A heavy over-claimer says yes to most things it should not; the rest are mostly honest. Q15 and Q16 are anchored to the contract: a vendor's true answer to "customers may audit" is yes only if the contract gives an audit right. Over-claiming is only partly linked to control quality, so some weak vendors answer honestly and some strong ones over-claim.

---

## Headline scenario — the shared provider

| Source | What it gives you |
| --- | --- |
| `vendors.csv` | 14 vendors name MP-1; 5 vendors name nothing. |
| `questionnaire.csv` | 10 of the 14 vendors on MP-1 pass the 85% line on their own. |
| `questions.csv` | No question asks which provider a vendor runs on. |
| `truth.csv` | 3 of the 5 vendors that hide their provider really run on MP-1, which lifts it from 42.9% to 53.6% of critical use cases. |

Run the walkthrough and you see the same thing three ways: the questionnaire (each vendor passes or fails alone), the concentration view (MP-1 flagged at 42.9%) and the truth (53.6%, a number a real bank would not have).
