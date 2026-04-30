# Architecture · CRE Lease Abstraction Error Detector

## System architecture

```mermaid
flowchart LR
    subgraph SRC[Inputs]
        A1[Lease PDFs / docs]
        A2[Deployed lease-NLP vendor]
    end

    subgraph QA[QA layer — three checkers]
        B1[Primary extractor output]
        B2[Re-extractor: alt LLM/prompt]
        B3[Rule extractor: regex/templates]
        B4[Missing-but-likely classifier]
    end

    subgraph SCORE[Disagreement scoring]
        C1[Hard disagreement]
        C2[Soft disagreement]
        C3[Missing-but-likely flag]
        C4[Confidence floor]
    end

    subgraph UX[Reviewer surface]
        D1[Triage queue $-ranked]
        D2[Source-clause highlight on PDF]
        D3[Accept / Override / Counsel]
    end

    subgraph DOWN[Downstream]
        E1[Asset Management ledger]
        E2[Project 08 Audit Trail]
        E3[Project 10 Underwriting Truth]
    end

    A1 --> A2 --> B1
    A1 --> B2
    A1 --> B3
    A1 --> B4
    B1 --> SCORE
    B2 --> SCORE
    B3 --> SCORE
    B4 --> SCORE
    SCORE --> UX
    UX --> DOWN
```

## Data flow — single lease through QA

```mermaid
sequenceDiagram
    participant Op as Lease Admin
    participant V as Vendor NLP
    participant QA as QA Layer
    participant Rev as Reviewer
    participant Aud as Audit Trail (P08)
    participant UW as Underwriting Truth (P10)

    Op->>V: Submit lease for abstraction
    V-->>QA: Primary fields + confidence
    QA->>QA: Re-extract + rule extract + missing-but-likely
    QA->>QA: Score disagreements
    alt Any flag fires
        QA-->>Rev: Triage queue entry, $-ranked
        Rev->>Rev: Inspect source clause highlight
        Rev-->>Aud: Override + reason (audit event)
        Rev-->>UW: Confirmed abstraction → underwriting feed
    else Clean
        QA-->>UW: Auto-confirm → underwriting feed
        QA-->>Aud: Auto-confirm event
    end
```

## Key trade-offs

- **Run ensemble on every lease vs. only when primary low-confidence.** Tier the ensemble: full ensemble on leases scoring below confidence threshold or flagged by missing-but-likely; primary-only on high-confidence standard leases. Saves 60%+ on ensemble cost.
- **Source-clause highlight on PDF.** Char-offset primary, embedding-search fallback when offsets misalign (older OCR'd docs). Two-tier highlight prevents reviewer trust collapse on misaligned highlights.
- **Override authority.** Reviewer always overrides; the QA layer never auto-corrects. Trade: slower throughput, but litigation defensibility intact.
- **Vintage and asset-class fairness.** Missing-but-likely classifier risks systematic bias against older vintages or non-standard assets. Quarterly fairness audit is a mandatory gate.

## Interlocks

- **Project 08 (Audit Trail)** — every reviewer override is a lineage event with reviewer_id, source-clause hash, original primary value, corrected value.
- **Project 10 (CRE Underwriting Reliability Sentinel)** — confirmed abstractions feed the comp/T-12/rent-roll arithmetic validation. Bad abstractions in = bad underwriting out; this project closes that loop upstream.
- **Asset Management ledger** — corrected abstractions update the operational rent roll, escalation schedule, and CAM cap registry. Recovered rent is realized here.
