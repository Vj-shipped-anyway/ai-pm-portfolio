# Staged issue draft. Not submitted.

Target: the MITRE ATLAS data repository (`mitre-atlas/atlas-data`), or the contribution page that its `CONTRIBUTING.md` points to. I have not read that page's submission steps (the fetch returned HTTP 404 on 2026-10-24), so the first job is to find the right channel.

**Title:** Question on scope: is a retry-loop failure in a tool-calling agent a fit for a case study?

**Body**

I have a small tool that drafts a case study from the trace of one agent run, using the study fields in `dist/schemas/atlas_contribution_schema.json` (version 1.1 of the case-study schema, collection 2026.09). Before I offer a real case study I would like to ask three things.

1. Scope. In the trace I work from, the agent calls one tool again and again after a bad response, and the run is cut off when its cost reaches a cap. The trace shows effects (a loop, a cost overrun) and does not show an adversary. In one variant an upstream scanner flags the bad response as instruction-like. Is a failure with no confirmed adversary in scope, or only incidents where an adversary is known?
2. Mapping. For the effects I used AML.T0029 (Denial of AI Service) and AML.T0034 (Cost Harvesting), and AML.T0051.001 (Indirect) for the flagged response. Would you map them differently?
3. Fields. The draft carries a `meta` block with call numbers that back each step. Is extra metadata at the top level welcome, or should the evidence sit in the step descriptions only?

Attached as a format example is `case_study_draft.yaml`. It is built from a synthetic trace, so it is not an incident and I am not proposing it for the catalogue. `actor`, `reporter` and `references` are left as TODO on purpose.

Placeholders to fill from a real case before anything is sent: TODO(real trace and owner's permission), TODO(reporter), TODO(references), TODO(sign-off under the contribution terms in `CONTRIBUTING.md`).
