# Architecture · Production Model DriftSentinel

## System architecture

```mermaid
flowchart LR
    subgraph SRC[Production Model Fleet]
        A1[Credit ML v3]
        A2[Fraud ML v7]
        A3[GenAI Support Q&A]
    end

    subgraph TEL[Telemetry plane]
        B1[Inference logs]
        B2[Feature store snapshots]
        B3[Vendor-version pin]
    end

    subgraph SENT[DriftSentinel]
        C1[Detect: PSI/KS/proxy]
        C2[Diagnose: bisect + segment]
        C3[Decide: action engine]
    end

    subgraph OUT[Downstream]
        D1[MRM evidence bundle]
        D2[Ops Slack/Teams alert]
        D3[Audit trail Project 08]
    end

    SRC --> TEL --> SENT
    C1 --> C2 --> C3
    C3 --> D1
    C3 --> D2
    C3 --> D3
```

## Data flow — single drift event

```mermaid
sequenceDiagram
    participant Model as Deployed Model
    participant Tel as Telemetry
    participant Det as Detect
    participant Diag as Diagnose
    participant Dec as Decide
    participant MRM as MRM Validator

    Model->>Tel: Inference + feature snapshot
    Tel->>Det: Reference vs current windows
    Det->>Det: PSI/KS sweep
    Det-->>Diag: PSI > 0.25 on dti
    Diag->>Diag: Segment slicer + upstream lineage
    Diag-->>Dec: Driver = dti shift; segment = subprime
    Dec->>Dec: Risk envelope check
    Dec->>MRM: Recommendation = SHADOW + bundle
    MRM-->>Dec: Validator attestation in 1 day
```

## Key trade-offs

- **Single-pane vs federated UX.** Single pane wins for CRO/Validator; federated wins for Ops Lead per business line. Resolution: single backbone, federated views.
- **Auto-rollback authority.** Tier-1 always requires human attestation; Tier-2/3 auto-rollback with audit trail (Project 08).
- **Vendor-version pinning vs. latest.** GenAI must pin or it isn't governable. Cost: 4–8 week lag on quality improvements. Worth it.

## Interlocks

- **Project 02 (Eval-First Console)** — shares eval-set storage and version pinning.
- **Project 06 (Inference Economics)** — drift events log $/inference deltas.
- **Project 08 (Audit Trail)** — every Decide-loop output is a lineage event.
