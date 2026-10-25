# Sample Data — CorpusGate walkthrough

Seven CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261020` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, employee, system, vendor or incident. The documents are sentences built from topic vocabulary by the generator, not by a model, and no real person's data exists in these files.**

**The truth is known because the data is synthetic.** The generator decides every access list, label and injected value, so it can say exactly who may read what. A real estate does not hand you that; the first job in a real deployment is exporting the real access lists and the group directory.

**Seed and design choices, stated.** I chose the seed once and did not try another. I changed the query design once after the first run: a quarter of the base queries now mention two aspects, because the first run gave a precision of 1.000 and that is not a believable eval. The test set is dense on purpose, so that every effect appears often enough to count. It is a test set, not an estimate of real-world frequency: the leak rate, the number of stale ACLs and the share of documents with personal data are all properties of this data.

**Personal-data values are obviously invalid.** SSN-like values start with 9 and have group 00 (for example, the pattern `9dd-00-dddd`); account-like values look like `ACCT-0000-1234`; e-mail-like values end in `.example`. A few documents also carry look-alikes that are not personal data (a form number shaped like an SSN, a shared mailbox, a sample account on a form), so that a pattern scan has false positives to score.

The headline scenario the walkthrough resolves: **an internal assistant retrieves from 500 documents for 40 users. Without an entitlement check, 291 of 1,000 results go to a user who may not read them. With CorpusGate, 11 do, all from ACL changes made after the last sync.**

---

## Shape of the data

This is printed by `step_01_no_access_control.py`:

```
DATA SHAPE
  Documents: 500 (true label: public 90, internal 239, confidential 121, restricted 50); 12 carry a wrong label
  Users: 40 (5 contractors); groups: 29, nested up to 4 levels deep; documents with an explicit deny entry: 215
  Queries: 200 asked by 39 different users
  Personal data injected into 60 documents (account_like 20, email_like 18, ssn_like 22)
  ACL changes after indexing: 39 (revokes 25, grants 14); 3 of them after the last sync
  Canary pack: 120 user and document pairs (mislabeled 14, nested_deny 20, ordinary 60, revoked_after_index 20, revoked_after_sync 6)
```

---

## `documents.csv` — 500 documents

| Column | Type | What it is |
| --- | --- | --- |
| `doc_id` | string | `D0001` onward. |
| `title` | string | Built from the topic and ends in `[DOC-nnnn]`, a token only this document has (canaries use it). |
| `text` | string | Three or four short sentences from topic vocabulary, plus one sentence of personal data in the injected documents and in the look-alikes. |
| `dept` | string | Owner team: retail, commercial, risk, compliance, legal, hr or tech. |
| `sensitivity` | string | The label in use: public, internal, confidential or restricted. 12 documents carry a label lower than the truth. |
| `acl_groups` | string | The source ACL today: groups that may read, separated by `;`. An entry starting with `-` is an explicit deny. |
| `acl_groups_at_index` | string | The copy stored when the index was built. It differs from `acl_groups` for the documents in `acl_changes.csv`. |
| `pii_truth` | string | `none`, `ssn_like`, `account_like` or `email_like`: what the generator injected. Used only to score the scan. |
| `sensitivity_label_truth` | string | The label the document should have. Used only to score the label-only filter. |

Rows, as printed (the text column is left out here):

| doc_id | dept | sensitivity | acl_groups | acl_groups_at_index | pii_truth | sensitivity_label_truth |
| --- | --- | --- | --- | --- | --- | --- |
| `D0001` | `risk` | `public` | `grp-all-staff` | `grp-all-staff` | `none` | `public` |
| `D0002` | `risk` | `internal` | `grp-all-staff` | `grp-all-staff` | `none` | `internal` |
| `D0003` | `retail` | `confidential` | `grp-retail` | `grp-retail` | `none` | `confidential` |
| `D0004` | `tech` | `public` | `grp-all-staff` | `grp-all-staff` | `none` | `public` |

True labels: public 90, internal 239, confidential 121, restricted 50. 215 documents have at least one explicit deny entry (for example `-grp-contractors`).

## `groups.csv` and `users.csv` — the directory

`groups.csv` has 29 `(parent, child)` rows over 29 groups, nested up to four levels deep. **Members of the child group are also members of the parent group**, so a user in `grp-retail-cards-fraud` is in `grp-retail-cards`, `grp-retail` and `grp-all-staff`. Some groups have two parents.

`users.csv` has 40 users (5 contractors) and their **direct** memberships only. A contractor is directly in a contractor group and in a department group; the deny entry on a document names the contractor group, which the contractor reaches only through nesting. That is what a flat group check misses.

| user_id | dept | role | direct_groups |
| --- | --- | --- | --- |
| `U001` | `tech` | `contractor` | `grp-contractors-tech;grp-tech` |
| `U002` | `compliance` | `analyst` | `grp-compliance-aml-investigations` |
| `U003` | `risk` | `manager` | `grp-risk` |
| `U004` | `hr` | `analyst` | `grp-hr-comp` |

## `queries.csv` — 200 test questions

| Column | Type | What it is |
| --- | --- | --- |
| `query_id` | string | `Q001` onward. |
| `user_id` | string | The asker. 39 different users ask. |
| `text` | string | Built from the topic's head words and the sub-topic's core words. |
| `relevant_doc_ids` | string | The documents relevant to the question's topic and sub-topic, separated by `;`. Relevance truth, independent of who may read. |

Every cluster of related documents has at least one question. Some questions are planted for each effect (a question from a user whose access was revoked, from a contractor, from a user who can read a document the label filter would hide, and so on), so that each effect appears. A quarter of the base questions mention two aspects.

| query_id | user_id | text | relevant_doc_ids |
| --- | --- | --- | --- |
| `Q001` | `U007` | `how do we handle checkout and session for privileged recording` | `D0115;D0137;D0163;D0192;D0303;D0424` |
| `Q002` | `U004` | `what is the rule for identity on account opening verification` | `D0028;D0033;D0126;D0214;D0335;D0427;D0448` |
| `Q003` | `U031` | `loan covenant extension amortization collateral` | `D0023;D0087;D0091;D0153;D0169;D0307;D0353;D0425` |

## `canary_queries.csv` — 120 canaries

| Column | Type | What it is |
| --- | --- | --- |
| `canary_id` | string | `CAN-001` onward. |
| `user_id`, `doc_id` | string | A user and a document that user may not read (the generator checks this). |
| `query_text` | string | Built to retrieve exactly that document: its `DOC-nnnn` token and its topic words. |
| `stratum` | string | Why the pair was picked: `ordinary`, `revoked_after_index`, `revoked_after_sync`, `nested_deny` or `mislabeled`. |

The pack is stratified toward known failure cases, so counts over it describe this pack, not a rate.

| canary_id | user_id | doc_id | query_text | stratum |
| --- | --- | --- | --- | --- |
| `CAN-001` | `U001` | `D0107` | `DOC-0107 regulator correspondence matters` | `mislabeled` |
| `CAN-002` | `U004` | `D0453` | `DOC-0453 market exposure stress` | `ordinary` |
| `CAN-003` | `U003` | `D0346` | `DOC-0346 records archive destruction` | `revoked_after_sync` |

## `acl_changes.csv` — the ACL change log

One row per document whose ACL changed after the index was built: 39 changes, 3 of them after the last sync (`2026-09-30T00:00`). `from_acl` is the index copy and `to_acl` is today's ACL. Dates are constants in the generator.

| change_id | doc_id | changed_at | change_kind | from_acl | to_acl |
| --- | --- | --- | --- | --- | --- |
| `AC-001` | `D0157` | `2026-06-05T08:30` | `add_contractor_deny` | `grp-all-staff` | `grp-all-staff;-grp-contractors` |
| `AC-002` | `D0315` | `2026-06-10T07:30` | `add_group` | `grp-risk;grp-incident-response;-grp-contractors` | `grp-risk;grp-incident-response;-grp-contractors;grp-compliance` |
| `AC-003` | `D0246` | `2026-06-13T15:15` | `add_group` | `grp-risk-credit;grp-exec;-grp-contractors` | `grp-risk-credit;grp-exec;-grp-contractors;grp-compliance` |
| `AC-004` | `D0292` | `2026-06-14T14:15` | `add_group` | `grp-risk;-grp-contractors` | `grp-risk;-grp-contractors;grp-compliance` |

## `entitlement_truth.csv` — who may read what, today

For each user, the documents the user may read under today's ACL. **The generator computes it by walking the group tree downward from each ACL group; the resolver in `src/step_04` walks upward from the user.** Same rule, two implementations. Their agreement on all 20,000 user and document pairs is therefore **by construction**; it shows the resolver is not buggy, and says nothing about a directory that is wrong.

---

## Headline scenario — a restricted document in the top 5

| Source | What it gives you |
| --- | --- |
| `queries.csv` | Q003, asked by U031 (retail analyst): "loan covenant extension amortization collateral". |
| `documents.csv` | D0153, labeled restricted, with an ACL that does not include any of the user's groups. |
| `users.csv` and `groups.csv` | The user's direct group and the 2 groups above it in the tree (3 groups in all). |
| `entitlement_truth.csv` | The user may read 338 of 500 documents; D0153 is not one of them. |

Run the walkthrough and you see the same thing three ways: a relevance-only assistant (it returns the document and the eval scores it as correct), the cheap guards (each fixes one failure and leaves another), and CorpusGate (3 better matches withheld, the user sees only what the ACL allows).
