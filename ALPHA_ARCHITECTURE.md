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


## Current implementation truth

The public Mission Lab is a deterministic browser classifier. It is not yet a durable multi-agent runtime: it does not execute specialist agents, ingest evidence objects, persist mission state, perform cross-agent verification, or measure business outcomes. Public copy and demonstrations must preserve that distinction.

Do not increase the roster, add more fixed templates, or describe planned integrations as connected capability. The next production priorities are:

1. durable mission ledger with idempotent state transitions
2. structured evidence objects with provenance and freshness
3. real role handoffs using compact context packets
4. independent EVAL verification before consequential approval
5. outcome telemetry tied to the mission's baseline and target
6. only then, additional agents or integrations

## Brand identity gate

Brand, positioning, homepage, proposal, and outreach changes use the executable gate in `brand/`.

Workflow:

```text
EVIDENCE_REQUIRED
  -> GAP_CONFIRMED
  -> IDENTITY_SELECTED
  -> VALUE_SELECTED
  -> READY_FOR_HUMAN_REVIEW
  -> APPROVED_FOR_TEST
  -> KEEP / ITERATE / REVERT
```

The gate requires attributable current-perception evidence, one or two relevant identity perspectives, functional plus emotional or self-expressive value, one highest-visibility move, a stop-doing rule, and an owned 30-day measure. Desired identity is not treated as evidence of current market perception.


## Executable runtime core status

The initial provider-neutral execution core is implemented in `alpha-runtime/`. It persists mission state in SQLite, records append-only hash-chained events, carries evidence provenance, hands each specialist a bounded typed task, independently verifies returned criteria, and gates consequential actions on approval tied to the exact payload hash. Action keys are idempotent; interrupted actions fail closed for manual reconciliation.

This core is not yet a deployed production service. The following remain before live customer workloads: authenticated API and approver identity, tenant isolation, persistent hosted storage/concurrency strategy, real specialist/provider adapters, domain-specific independent verifiers, operational observability, backup/restore, security review, and UI integration. The public browser Mission Lab remains a separate local classifier and must not be described as connected to this runtime until an authenticated service is actually deployed and validated.

The runtime test suite covers persistence across store re-instantiation, event chain integrity, evidence scoping, failed verification, approval binding, duplicate requests, and ambiguous interrupted actions. Run it using the command in `alpha-runtime/README.md`.
