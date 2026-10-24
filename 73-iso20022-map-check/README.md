# 🔎 ISO 20022 Map Check: gaps and truncation in a legacy-to-ISO field mapping

**I wanted to know what a legacy-to-ISO 20022 conversion loses without anyone noticing, and how much of that a mapping review can catch before a payment goes out. This is a command-line check: it reads the field mapping, and optionally the pairs of legacy and ISO messages your converter produced, and reports fields with no home, values that cannot fit, and values that arrived cut short, dropped or changed.** Schema validation passes most of those cases, because a name cut to 33 characters is still a valid name.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 73-iso20022-map-check/src && python3 iso20022_map_check.py --demo
```

It prints:

```text
mapping: 19 rows | 20 legacy fields | 20 ISO elements | 1 dropped on purpose (INTNOTE)
  [error  ] legacy_unmapped          ORGAD3                   no mapping row, so a populated value is dropped
  [error  ] iso_mandatory_unsourced  GrpHdr/MsgId             mandatory element with no mapping row and no constant
  [error  ] code_not_covered         CHGS=O                   legacy code has no entry in table chgs
  [error  ] capacity_overflow        CdtrAcct/Id/Othr/Id      BENACC can hold 35 characters, the element takes 34
  [error  ] capacity_overflow        RmtInf/Ustrd             OBI1+OBI2+OBI3+OBI4 can hold 143 characters, the element takes 140
  [warning] reverse_exposure         10 rows                   the ISO element takes more than the legacy field holds, e.g. PmtId/InstrId: element takes 35 characters, SNDREF holds 16
pairs: 3 checked
  [error  ] altered                  IntrBkSttlmAmt           1 of 3 pairs (first B06-M01): the amount differs
  [error  ] truncated                CdtrAcct/Id/Othr/Id      1 of 3 pairs (first B03-P1): kept 34 of 35 characters
  [error  ] truncated                Dbtr/Nm                  1 of 3 pairs (first B03-P1): kept 33 of 35 characters
  [error  ] truncated                RmtInf/Ustrd             1 of 3 pairs (first B03-P1): kept 140 of 143 characters
  [error  ] unmapped_lost            ORGAD3                   3 of 3 pairs (first B03-P1): populated, but no mapping row carries it
  [error  ] untraced                 GrpHdr/MsgId             3 of 3 pairs (first B03-P1): a value is present but no mapping row writes this element
coverage: code values never seen: TYP=15, TYP=16, CHGS=B, CHGS=O
coverage: code combinations (TYP, CHGS) never seen: 8 of 9 (10/B, 10/O, 15/S, 15/B, 15/O, 16/S)
decision: FAIL (5 mapping errors, 10 pair findings)
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 iso20022_map_check.py check DIR --pairs pairs.json`, where `DIR` holds `legacy_fields.csv`, `iso_elements.csv`, `mapping.csv` and `code_tables.json` (the columns are in [data/README.md](./data/README.md)). It exits 1 when it finds an error, 2 when an input file is malformed, so a CI step fails on a real problem and not on a typo. `python3 iso20022_map_check.py probe DIR` prints legacy messages with every field filled to its limit; run those through your converter and feed the output back as pairs. The check never prints a payment value, only field names, counts and lengths.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: ten converter builds, 23 legacy messages each, 230 message pairs; the script is named in brackets):

- 🟢 Schema validation alone passes 214 of 230 pairs, and 113 of the 129 pairs that carry a planted defect still pass (`step_01`)
- 🟢 An exact field-by-field comparison catches 78 of those 129 defective pairs, flags 154 of 162 harmless variations (padding, trailing zeros), and cannot see 99 of 212 planted defects because they sit on rows that change the value on the way (`step_02`)
- 🟢 The mapping checks alone find 5 of 5 planted mapping defects and flag 0 of 3 harmless rows. On pairs, the ordinary messages alone find a defect in 5 of 8 builds that have one, and the boundary probes alone find 6 of 8 (`step_03`)
- 🟢 All together: 5 of 5 mapping defects, 212 of 212 planted converter defects in the pairs, 0 of 162 harmless variations flagged, and 7 of 8 defective builds found. 10 of 12 text rows could cut data on the way back to the legacy format, which the check reports as a warning (`step_04`)

**What I assumed** (🟡 modeled): the legacy format is invented; the ISO element names follow the pacs.008 naming in a flat path view, but the lengths and mandatory flags are my simplification, not read from any message specification; a constant `NOTPROVIDED` fills the end-to-end identifier; the generator's converters cut long values to the element limit, as a converter that must stay schema-valid would.

**What I could not test** (🔴 hypothetical): a real bank's mapping spreadsheet and converter. I would expect it to hold gap and capacity findings the first run, and defects I did not plant. I have not seen one.

## What it still gets wrong

- 🟢 Build B10 drops the beneficiary account only when TYP is 16 and CHGS is S, and it is not found (`step_04` prints it, with the defect firing 0 times). No message carries that pair of codes: 2 of 9 code combinations are absent (15/S, 16/S), and the probes cycle the code values together instead of crossing them. Crossing every coded field fixes this here and grows as the product of the code counts; the coverage line prints the gap so it is not silent.
- **Event-level results are complete by construction.** 212 of 212 with no false alarm looks better than it is: the generator and the check agree that padding is not a change and that amounts compare as numbers. I wrote both, so these numbers are a ceiling for these rules, not a rate on real converters. The build-level numbers (5 of 8 on ordinary messages, 7 of 8 with probes) carry the information: a defect is found only if some message reaches it.
- **The check proves a converter follows the mapping. It cannot prove the mapping is right.** If the spreadsheet sends the debtor name to the creditor element and the converter obeys it, every pair passes. The mapping checks look at lengths, coverage and codes, not meaning.
- The ISO side is a flat path-to-value view, not XML. Namespaces, repeated elements beyond indexed address lines, structured addresses and the real schemas are out of scope. The reverse direction (ISO to legacy) is checked by arithmetic only; no down-converted messages are tested.
- `join_lines` assumes one fixed separator. How a long ISO text is split back into legacy lines (word wrap or hard cut) is not modelled.
- Values are never printed, so a finding says "differs from character 12", not what the two values were. That is deliberate and slower to debug.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does ISO schema validation alone let through? | `step_01_schema_check_only.py` |
| 2 | What does a plain field-by-field comparison cost and miss? | `step_02_exact_compare.py` |
| 3 | Where does each half fail alone, and what stays hidden? | `step_03_deficiencies_exposed.py` |
| 4 | What do mapping checks, pair checks and probes catch together? | `step_04_with_check.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The folder layout follows [28 Tool Schema Drift](../28-tool-schema-drift/); the check itself shares no code with it.

## Aligned to

The Federal Reserve moved the Fedwire Funds Service to ISO 20022. Its press release of July 15, 2025, announces the completed migration ([Federal Reserve Financial Services, read 2026-10-24](https://www.frbservices.org/news/press-releases/071525-iso20022-migration-announcement/)). That release is the only Fed source I read. I did not read the Fedwire message specification or any FedNow format document, so nothing here states what either service requires, and the element lengths are mine. This is a prototype aligned to the migration problem, not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. The legacy format, the messages, the names and the builds are invented; nothing comes from any employer, institution or real message. A prototype on synthetic data, not a production case study.

## Fork it

Replace the four mapping files in `data/` with your own (keep the columns) and write your converter's output as a pairs file, or run `probe` and convert what it prints. Read the [PRD](./PRD.md) for the scope I held to.
