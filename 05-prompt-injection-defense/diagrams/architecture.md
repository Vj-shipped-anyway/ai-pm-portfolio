# Architecture · Prompt-Injection & Egress Defense

## System architecture

```mermaid
flowchart LR
    subgraph CLIENT[Client surfaces]
        U1[Internal copilot UI]
        U2[Customer chat]
        U3[Agent workflows]
    end

    subgraph GW[Defense Gateway]
        L1[Layer 1: Input classifier<br/>direct + indirect]
        L2[Layer 2: Egress filter<br/>PII / secrets / tenant]
        L3[Layer 3: Tool-call gate<br/>blast radius + provenance]
        POL[Policy store<br/>per-app tier]
    end

    subgraph LLM[LLM + tools]
        M1[Vendor model<br/>pinned version]
        T1[Tool registry]
        R1[Retrieval / RAG]
    end

    subgraph OUT[Downstream]
        A1[Audit Trail Project 08]
        A2[HITL Review Project 07]
        A3[CISO dashboard]
    end

    CLIENT --> L1
    L1 --> M1
    M1 --> L2
    L2 --> CLIENT
    M1 --> L3
    L3 --> T1
    R1 --> L1
    POL -. governs .- L1
    POL -. governs .- L2
    POL -. governs .- L3
    L1 --> A1
    L2 --> A1
    L3 --> A1
    L1 --> A2
    A1 --> A3
```

## Data flow — single attempted indirect injection

```mermaid
sequenceDiagram
    participant U as User
    participant GW as Gateway L1
    participant R as Retrieval
    participant M as LLM
    participant L2 as Gateway L2
    participant L3 as Gateway L3
    participant T as Tool
    participant Aud as Audit (P08)

    U->>GW: "Summarize this customer email"
    GW->>R: fetch email
    R-->>GW: email body + hidden instruction
    GW->>GW: Layer 1 classify (provenance=untrusted)
    GW-->>M: forward with provenance tag
    M-->>L2: response + proposed tool call
    L2->>L2: PII / secret / tenant scan
    L2-->>L3: clean output + tool intent
    L3->>L3: tool=transfer_funds, untrusted=true
    L3-->>U: BLOCKED — untrusted provenance
    L1-->>Aud: event(verdict, score, signature)
    L3-->>Aud: event(deny, tool, reason)
```

## Key trade-offs

- **Latency vs depth.** Each added detector costs p95 ms. Resolution: cheap rules synchronously, LLM-judge async on REVIEW-tier only, cache benign verdicts on identical-prefix hits.
- **Strict vs permissive defaults.** Customer-facing defaults strict, internal-research permissive, with App Owner co-sign required to relax. Default is enforce, never shadow, after Phase 0.
- **Build vs buy on classifier.** Buy commercial detector for known-attack coverage; build the indirect-injection + tenant-tag layer in-house because no vendor sees our data taxonomy.
- **Vendor-version pinning.** Required. Without it, egress patterns drift silently and Layer 2 calibration goes stale (see Project 01).

## Interlocks

- **Project 01 (DriftSentinel)** — pins the vendor model version; flags egress-pattern drift on upgrade.
- **Project 07 (HITL Designer)** — high-blast-radius tool calls always route through HITL; REVIEW-tier verdicts go to a reviewer pool.
- **Project 08 (Audit Trail)** — every gateway decision is a signed lineage event; the audit chain is the regulator-facing artifact.
- **Project 06 (Inference Economics)** — gateway adds metered $/inference for the classifier and LLM-judge layer; cost surface includes the security tax.
