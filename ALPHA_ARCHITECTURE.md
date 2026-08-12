# ALPHA Mission Control — Architecture

## Product goal

ALPHA Mission Control turns a broad user objective into a supervised, evidence-aware execution path. The product should demonstrate the capabilities of the ALPHA agent network while remaining useful even before paid implementation.

## Phase 1 — Public Mission Lab

**Status:** implemented on `alpha-mission-control`.

The public site is static and browser-only. It performs deterministic mission classification and returns:

1. mission mode
2. specialist team
3. candidate fork stack
4. desired outcome
5. five-step execution plan
6. human approval boundary
7. downloadable mission brief

No mission text leaves the browser in this phase.

## Phase 2 — Evidence-backed missions

Add a backend mission service behind explicit user initiation.

Suggested roles:

- **ALPHA:** context packet, routing, synthesis, completion check
- **ROSALIND:** current web research and source comparison
- **MR. HOLMES / SAM:** authorized public-source research when relevant
- **VISION / PAM:** goal decomposition and product framing
- **HAL / JAN / BOB:** ML, LLM, retrieval, and software strategy
- **BENICIO / BILLY:** security and governance review

Candidate fork components:

- Firecrawl for web extraction
- Onyx or open-notebook for searchable research workspaces
- MarkItDown for document normalization
- Dify / Langflow / Flowise / Ruflo for agent-workflow experimentation
- LiteLLM for model-provider routing

Every research result should preserve source provenance, retrieval time, uncertainty, and the difference between fact and inference.

## Phase 3 — Approved action layer

Connect plans to tools only after the user approves the proposed action scope.

Candidate capabilities:

- n8n / Activepieces for workflow execution
- Twenty for CRM and mission state
- listmonk / Postiz for approved campaign operations
- Supabase for authenticated mission records and user data

Required controls:

- least-privilege credentials
- per-action approval policy
- audit log
- idempotency and rollback where possible
- secrets never exposed to client-side JavaScript
- sensitive data minimization
- explicit destructive-action boundaries

## Phase 4 — Local/private model options

For workloads where privacy, cost, or latency justifies it, evaluate:

- llama.cpp
- vLLM
- AirLLM
- LiteLLM as the routing layer

HAL owns model selection and evaluation. Use proven hosted or foundation models by default unless evidence supports a local or custom path.

## Mission contract

Every backend mission should have a structured packet:

```text
objective
user/context
constraints
freshness requirement
allowed tools
prohibited actions
required evidence
success criteria
approval gates
output format
```

## Execution state

```text
INTAKE
  -> PLAN
  -> ROUTE
  -> RESEARCH / BUILD / ANALYZE
  -> VERIFY
  -> APPROVAL_REQUIRED (when consequential)
  -> EXECUTE
  -> VALIDATE
  -> COMPLETE
```

A mission can return to PLAN or ROUTE when validation fails or new evidence materially changes the recommendation.

## Security boundary

Security and OSINT capabilities are defensive and permission-scoped. Intrusive testing, credential use, exploitation, scanning outside owned scope, persistence, or destructive actions require separate explicit authorization and must never be inferred from a general mission request.

## Fork integration rule

A fork appearing in ALPHA's capability map does not mean its source code is automatically bundled into the product. Before integration, record:

- license and attribution requirements
- maintenance/activity level
- dependency and supply-chain risk
- data transmitted or stored
- secret requirements
- network permissions
- deployment footprint
- failure behavior
- user-facing value versus integration cost

Prefer APIs, isolated services, or narrowly reused patterns when that reduces coupling and security risk.

## Success criteria for public v1

- visitor understands ALPHA within 10 seconds
- visitor can submit a mission without signup
- output changes based on the goal
- output provides a useful plan, not just marketing copy
- user can copy/download the brief
- site clearly distinguishes public demo capability from connected production capability
- consequential actions remain human-approved
