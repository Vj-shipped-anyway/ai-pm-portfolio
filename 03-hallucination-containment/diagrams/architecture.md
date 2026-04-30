# Architecture · Hallucination Containment for Bank Chatbots

## System architecture

```mermaid
flowchart LR
    subgraph CUST[Customer]
        U[Customer turn]
    end

    subgraph BOT[Deployed chatbot]
        M[Vendor or in-house LLM]
    end

    subgraph CONT[Containment layer]
        G1[Guard 1 - Ground: claim extract + KG check]
        G2[Guard 2 - Abstain: confidence + handoff]
        G3[Guard 3 - Probe: continuous red-team + quarantine]
    end

    subgraph KG[Authoritative KG]
        K1[Product catalog]
        K2[Rate sheet]
        K3[Fee schedule]
        K4[Reg references]
    end

    subgraph DOWN[Downstream]
        H[Live agent handoff]
        A[Audit trail - Project 08]
        E[Eval rubrics - Project 02]
    end

    U --> M --> G1
    KG --> G1
    G1 --> G2
    G2 --> G3
    G2 -->|low conf| H
    G1 -->|ungroundable| H
    G3 -->|regression| H
    G3 --> A
    G1 --> A
    G2 --> A
    E --> G3
```

## Data flow — single grounded turn

```mermaid
sequenceDiagram
    participant C as Customer
    participant Bot as LLM
    participant G as Ground guard
    participant KG as Knowledge graph
    participant A as Abstain guard
    participant H as Handoff

    C->>Bot: "What is the savings APY?"
    Bot->>G: Candidate: "Our APY is 4.85%."
    G->>G: Extract claim: APY = 4.85%
    G->>KG: Lookup savings_apy
    KG-->>G: 4.10% as-of 2026-04-15
    G->>G: Mismatch
    G-->>A: Ungroundable claim
    A->>H: Handoff with context
    H-->>C: Live agent answers with verified rate
```

## Data flow — auto-quarantine on probe regression

```mermaid
sequenceDiagram
    participant P as Probe scheduler
    participant Bot as LLM (use case)
    participant G as Containment
    participant Q as Quarantine controller
    participant E as Exec notification

    P->>Bot: Probe set (50 prompts)
    Bot->>G: Responses
    G->>P: Scored
    P->>P: Compare vs. baseline
    P-->>Q: Regression > 8% on Reg DD claims
    Q->>Q: Pull use case from customer flow
    Q-->>E: Exec notification within 4h
    Q->>E: Audit event logged
```

## Key trade-offs

- **Containment vs. model selection.** The instinct is "switch models." Switching introduces a new unknown-unknown set. Containment is model-agnostic and survives vendor swaps.
- **Refuse-rewrite vs. refuse-hard.** Rewriting an ungroundable claim with the KG value is better customer experience but introduces a small risk of paraphrase distortion. We start refuse-hard for v1; rewrite-with-citation is v2.
- **Abstention threshold per intent.** Single threshold is the trap (rate intents need higher confidence than directional questions). Per-intent thresholds are mandatory.
- **Auto-quarantine authority.** The system pulls a use case without human approval, with a 4-hour exec notification SLO. The reverse posture (human-required) loses the speed advantage.
- **KG as source of truth.** The LLM is never the source of truth on a rate, fee, or regulation. The KG is. The LLM is the natural-language interface to the KG.
- **Deflection give-back budget.** A 3-point give-back on deflection is the right trade for a 70-point hallucination cut. This must be defended explicitly, in writing, with the Head of CX.

## Interlocks

- **Project 01 (DriftSentinel)** — calibration drift on the abstention guard is a Tier-1 drift signal.
- **Project 02 (Eval-First Console)** — factuality rubrics and probe sets are co-authored here; results feed back to the console.
- **Project 07 (LLM Red Team)** — adversarial probes feed Guard 3 schedule; new jailbreaks discovered there land here.
- **Project 08 (Audit Trail)** — every guard fire (ground refuse, abstain, quarantine) is a lineage event with full evidence.
