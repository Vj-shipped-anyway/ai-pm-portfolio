# Architecture · Eval-First Console for Regulated AI

## System architecture

```mermaid
flowchart LR
    subgraph SME[SME authoring plane]
        A1[Credit officer]
        A2[Fraud analyst]
        A3[Compliance specialist]
    end

    subgraph CONS[Eval-First Console]
        B1[Author: rubric + slice editor]
        B2[Run: scheduler + vendor pin]
        B3[Detect: regression flagger]
        B4[Coverage map]
    end

    subgraph PLAT[AI Platform]
        C1[Prompt registry]
        C2[Model registry]
        C3[Vendor adapters]
    end

    subgraph EVAL[Eval execution]
        D1[LLM-as-judge pool]
        D2[SME gold calibration set]
    end

    subgraph OUT[Downstream]
        E1[Use-case owner dashboard]
        E2[MRM evidence bundle]
        E3[DriftSentinel - Project 01]
        E4[Audit Trail - Project 08]
    end

    SME --> B1
    B1 --> B2
    B2 --> EVAL
    PLAT --> B2
    EVAL --> B3
    B3 --> OUT
    B4 --> E1
```

## Data flow — single eval run on vendor silent update

```mermaid
sequenceDiagram
    participant Vendor as Vendor model
    participant Pin as Vendor pinning
    participant Sched as Eval scheduler
    participant Judge as LLM-judge pool
    participant Det as Regression detector
    participant Owner as Use-case owner
    participant MRM as MRM Validator

    Vendor->>Pin: Snapshot hash changed
    Pin-->>Sched: Trigger re-eval
    Sched->>Judge: Run rubric x slice matrix
    Judge-->>Det: Score table by version
    Det->>Det: Diff vs. pinned baseline
    Det-->>Owner: Regression alert + slice cuts
    Det-->>MRM: Evidence bundle (rubric/version/score)
    Owner->>MRM: Recommendation = ROLLBACK
    MRM-->>Owner: Attestation in 1 day
```

## Key trade-offs

- **LLM-as-judge vs. SME gold panel.** Judge for cost and frequency; SME panel weekly to calibrate. Judge alone is unsafe in regulated workflows; SME alone is unscalable.
- **Per-prompt-change cadence vs. nightly.** Per-change is correct for promotion gating; nightly catches pinned-vendor drift. Run both.
- **Aggregate vs. slice-first reporting.** Aggregate is the trap (commercial-vs-retail gap of 18 points hides at the aggregate). Slice-first is non-negotiable for regulated workflows.
- **Eval cost vs. coverage.** Tiered cadence: hot use cases nightly, warm weekly, cold monthly. Per-use-case eval budget caps with line-1 owner sign-off.
- **SME authorship vs. engineer authorship.** SME-authored rubrics are 4–8x slower to produce, but they are the only ones that survive a regulator question. Engineer-authored rubrics are an anti-pattern in regulated workflows.

## Interlocks

- **Project 01 (DriftSentinel)** — consumes eval-set artifacts as the GenAI proxy-metric source; shares vendor-version pinning.
- **Project 03 (Hallucination Containment)** — eval rubrics include factuality; calibration data flows in.
- **Project 05 (Synthetic Eval Data)** — seeds rubric coverage for under-represented slices.
- **Project 06 (Inference Economics)** — eval budget caps; cost-per-eval visibility.
- **Project 08 (Audit Trail)** — every rubric edit, vendor pin change, and regression flag is a lineage event.
