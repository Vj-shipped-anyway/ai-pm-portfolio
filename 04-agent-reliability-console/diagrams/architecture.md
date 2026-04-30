# Architecture · Agent Reliability & Tool-Use Observability

## System architecture

```mermaid
flowchart LR
    subgraph FLEET[Deployed agent fleet]
        A1[Recon agent]
        A2[Dispute agent]
        A3[KYC refresh agent]
    end

    subgraph TEL[Telemetry plane]
        T1[Trajectory capture - OTel]
        T2[Tool I/O snapshot]
        T3[Intent classifier]
    end

    subgraph CON[Reliability Console]
        C1[Loop detector]
        C2[Misuse classifier]
        C3[Runaway detector]
        C4[Schema-drift sentinel]
        C5[Four-dim budget enforcer]
        C6[Circuit breaker]
        C7[Replay UI]
    end

    subgraph DOWN[Downstream]
        D1[SRE incident queue]
        D2[Use-case owner dashboard]
        D3[Inference economics - Project 06]
        D4[Audit trail - Project 08]
    end

    FLEET --> TEL
    TEL --> C1
    TEL --> C2
    TEL --> C3
    TEL --> C4
    C1 --> C6
    C2 --> C6
    C3 --> C6
    C4 --> C6
    C5 --> C6
    C6 --> DOWN
    TEL --> C7
```

## Data flow — trajectory with circuit-breaker fire

```mermaid
sequenceDiagram
    participant Ag as Agent
    participant Tel as Trajectory capture
    participant Cls as Classifiers
    participant CB as Circuit breaker
    participant H as Human queue
    participant Aud as Audit trail

    Ag->>Tel: tool_call(fetch_ledger)
    Ag->>Tel: tool_call(fetch_ledger)  
    Ag->>Tel: tool_call(fetch_ledger)
    Tel->>Cls: stream
    Cls->>Cls: Loop classifier: max-repeat = 5
    Cls-->>CB: Loop fired
    CB->>Ag: HALT
    CB->>H: Route to human queue
    CB->>Aud: Lineage event with full trajectory
```

## Data flow — schema-drift sentinel

```mermaid
sequenceDiagram
    participant API as Upstream API
    participant Gw as API Gateway
    participant Sen as Schema sentinel
    participant Reg as Tool registry
    participant Q as Quarantine

    API->>Gw: Contract update (new field)
    Gw->>Sen: Schema diff job
    Sen->>Reg: Compare vs. tool description
    Sen-->>Q: Drift detected on fetch_customer
    Q->>Q: Quarantine agent until re-attested
    Q->>Reg: Tool-description currency = STALE
```

## Key trade-offs

- **Trajectory as unit of observation, not request.** A request-centric view misses loops, misuse, and runaway. Trajectory is the only useful unit for agents.
- **Four-dim budgets vs. single-dim cost cap.** Tokens alone is insufficient — wall-clock loops can blow up regardless. All four dimensions are required for blast-radius enforcement.
- **Inline classifiers vs. async.** Loop and misuse must be inline (they enforce the breaker). Schema-drift is async (it informs quarantine, not real-time halt).
- **SRE org vs. AI/ML org ownership.** SRE is the right home — reliability is an operational discipline, and the tools (OTel, SLO, error budget) are SRE-native.
- **Tool descriptions as a regulated artifact.** Every write-tool exposed to a regulated agent must have a Compliance-attested description. Read-tools require AI Risk attestation. This is the governance lever.
- **Replay PII handling.** Tokenize at capture; replay UI scoped by role. 90 days hot, 365 cold-tokenized.

## Interlocks

- **Project 02 (Eval-First Console)** — agent eval rubrics include trajectory shape; classifier calibration shares the SME panel.
- **Project 06 (Inference Economics)** — runaway detector reads $/trajectory from the inference-economics ledger.
- **Project 07 (LLM Red Team)** — adversarial prompt suites that induce tool misuse run here as drills.
- **Project 08 (Audit Trail)** — every classifier hit, breaker fire, and replay session is a lineage event with full evidence.
