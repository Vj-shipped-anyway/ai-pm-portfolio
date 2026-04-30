# Architecture · CRE AI Underwriting Reliability Sentinel

## System architecture

```mermaid
flowchart LR
    subgraph IN[Inputs]
        A1[AI-drafted underwriting memo]
        A2[OM packet / rent roll / T-12]
    end

    subgraph PARSE[Claim extraction]
        P1[Comp citations]
        P2[Submarket stats]
        P3[Arithmetic claims]
    end

    subgraph SOT[Source-of-truth feeds]
        S1[CoStar API]
        S2[Reonomy API]
        S3[Cherre API]
        S4[Proprietary deals DB]
    end

    subgraph CHECK[Three-check sentinel]
        C1[Comp citation verification]
        C2[Symbolic arithmetic re-val]
        C3[Submarket stat cross-check]
    end

    subgraph OUT[Outputs]
        O1[Confidence dashboard]
        O2[Sectional pass/fail]
        O3[Verification stamp on memo]
        O4[Audit trail event - Project 08]
    end

    IN --> PARSE
    PARSE --> CHECK
    SOT --> C1
    SOT --> C3
    CHECK --> OUT
```

## Data flow — single memo through sentinel

```mermaid
sequenceDiagram
    participant An as Analyst
    participant Co as Copilot (AI memo)
    participant Sen as Sentinel
    participant SoT as Source-of-truth feeds
    participant IC as Investment Committee
    participant Aud as Audit Trail (P08)

    An->>Co: Draft underwriting memo
    Co-->>An: Memo with comps + stats + math
    An->>Sen: Run sentinel before IC
    Sen->>Sen: Parse comps, stats, arithmetic
    Sen->>SoT: Verify each comp + each stat
    SoT-->>Sen: Truth records or null
    Sen->>Sen: Re-run T-12 / rent-roll math symbolically
    Sen-->>An: Sectional pass/fail + divergences
    alt Clean pass (≥ 95%)
        An->>IC: Memo + verification stamp
        Sen-->>Aud: PASS event with hashes
    else Flagged
        An->>An: Reconcile divergences or override w/ senior sign-off
        An-->>Aud: Override event + reason
    else Blocked
        An->>An: Re-draft with verified inputs
        An-->>Aud: BLOCK event
    end
```

## Key trade-offs

- **Symbolic re-validation vs. second LLM on math.** Symbolic wins, every time. Math is a deterministic problem; LLMs introduce non-determinism into a place that doesn't tolerate it.
- **Single source-of-truth vs. multi-feed.** Multi-feed always for stats (and surface disagreements rather than picking). Single feed acceptable for comp existence checks where ground truth is unambiguous.
- **Tolerance bands.** Tight bands → analyst friction; loose bands → hallucinations slip. Operating point is set quarterly against IC outcomes (override-and-was-right rate is the calibration signal).
- **Override authority.** Senior sign-off required for any override; every override is an audit event. Analysts cannot silently bypass the sentinel.
- **Cost discipline.** Cap sentinel cost at ~$3 per memo; cache aggressive on stat pulls; batch comp lookups.

## Interlocks

- **Project 08 (Audit Trail)** — every sentinel run, every override, every IC-forwarded memo writes a lineage event with verification record + reviewer ID.
- **Project 09 (Lease Abstraction Detector)** — corrected lease abstractions (post-QA) feed Check 2's rent-roll arithmetic. Bad lease abstractions in = bad NOI re-val out; this project's reliability depends on Project 09's truth.
- **IC packet workflow** — sentinel verification stamp becomes a required field on IC memos; gating rule lives in IC governance, not in the sentinel.
- **Asset Management handoff** — at close, the verified underwriting (not the raw AI draft) is what attaches to the property file for post-close benchmarking.
