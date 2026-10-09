# ALPHA Runtime Core (first executable slice)

This is a provider-neutral Python runtime core for supervised ALPHA missions with a deployable, narrow single-host operator API. It is not the deployed Sites backend or a connected model/agent workforce.

## Deploy the ALPHA single-host API

The repository includes a runnable, authenticated HTTP service in `api_server.py`, a non-root Docker image, and a Docker Compose deployment. This deploys the **mission ledger, evidence metadata validation, audit events, and evaluation API**. It does **not** deploy the full ALPHA agent workforce or enable email sending, browsing, payment operations, or arbitrary tools. The exposed specialist verifies only **evidence metadata presence**, not factual truth.

### Requirements and launch

Install Docker Engine with the Compose plugin on a Linux host (or Docker Desktop locally). From the repository root:

```bash
cd alpha-runtime
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
# Replace ALPHA_API_TOKEN in .env with the generated value; never commit .env
chmod 600 .env
docker compose up --build -d
curl -fsS http://127.0.0.1:8080/healthz
```

Use the real token to check readiness and submit a mission:

```bash
export ALPHA_API_TOKEN="$(sed -n 's/^ALPHA_API_TOKEN=//p' .env)"
curl -fsS -H "Authorization: Bearer $ALPHA_API_TOKEN" http://127.0.0.1:8080/readyz

curl -fsS -X POST http://127.0.0.1:8080/v1/missions \
  -H "Authorization: Bearer $ALPHA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mission_id":"intake-001","objective":"Check incident intake metadata","owner_scope":"prime24ai","project_scope":"agents","access_tags":["ops"],"evidence":[{"evidence_id":"e-001","claim":"Operator reports an incident","source":"operator","retrieved_at":"2026-10-09T10:00:00Z","classification":"user_input"}]}'

curl -fsS -H "Authorization: Bearer $ALPHA_API_TOKEN" \
  http://127.0.0.1:8080/v1/missions/intake-001/evaluation
```

Endpoints: unauthenticated `GET /healthz`; authenticated `GET /readyz`, `POST /v1/missions`, `GET /v1/missions/{id}`, `GET /v1/missions/{id}/events`, `GET /v1/missions/{id}/evaluation`, and `POST /v1/missions/{id}/invalidate` with `{"evidence_id":"e-001","reason":"source corrected"}`.

The API rejects user-supplied tool permissions, proposed actions, and arbitrary role selection. It accepts a single, fixed metadata-audit criterion and never performs external actions. The body limit is 64 KiB; raw payloads and credentials are not logged by the HTTP handler.

### Render deployment (persistent single-host alternative)

The repository root contains `render.yaml`. Render can deploy the existing Docker image with a paid single-instance web service and a 1 GB persistent disk in Oregon. The blueprint disables automatic releases until an operator approves them. It does not deploy the public Prime24AI site or enable side-effectful agent tools.

1. Connect the Render workspace and GitHub repository `darnleyweekes-spec/jarvis-workforce-hq`.
2. Create a Blueprint from `render.yaml`. **Review the recurring compute and disk charges before approving service creation.**
3. Set `ALPHA_API_TOKEN` to a newly generated secret of at least 32 characters using Render's protected environment variable prompt. Do not paste it into issues, logs, or chat.
4. Deploy the Blueprint and verify `https://<assigned-service>.onrender.com/healthz` returns `{"status":"ok"}`. Then use an authorized client to call `/readyz` and create/read an example metadata-only mission.
5. Confirm the persistent disk is writable by the unprivileged container user and that the mission survives a service restart. If disk permission prevents startup, fix the mount ownership in the deployment environment; do not run the container as root merely to bypass the failure.
6. Configure restricted operator access, rate limiting, token rotation, monitoring, and tested backup/restore before storing real customer data. Render disk snapshots are not a substitute for a validated application-level backup.
7. Do not attach a custom public-facing Prime24AI domain until access controls and live smoke tests pass.

The `render.yaml` file is deployment configuration, not evidence that a Render service already exists.

### Operations and security boundary

- Docker Compose binds **127.0.0.1:8080 only**. For remote access, place a properly configured **TLS reverse proxy with authentication, rate limits, and access controls** in front of it; do not expose plain HTTP or the container port directly to the internet.
- `ALPHA_API_TOKEN` is mandatory and must contain at least 32 characters. Store it in a secrets manager for a managed deployment. Rotate by updating the secret and restarting the service.
- SQLite data persists in the Docker named volume `alpha_data`. Back it up using SQLite's backup API or a quiesced snapshot of the volume, verify restores, and secure the backups. Never store database files in the public site repository.
- The image runs as an unprivileged user with a read-only root filesystem and dropped Linux capabilities. This is a **single-process, single-host** service; do not scale replicas against the same SQLite volume.
- This API uses a **single shared operator token**, not per-user authentication or tenant authorization. Treat it as a private operator service only. Production multi-tenant deployment requires a separate identity layer, scope authorization, encrypted storage, observability, abuse controls, migration strategy, and a sandboxed tool runner.
- GitHub CI runs unit tests, builds the Docker image, and tests live container startup plus unauthorized/authorized readiness.
- To stop: `docker compose down` (keeps the volume). Do **not** use `down -v` unless intentional permanent data deletion is authorized.

## What is implemented

- SQLite persistence for mission state and evidence across process restarts.
- Append-only, hash-chained lifecycle events; database triggers reject event edits and deletion.
- Typed request, evidence, scoped specialist-task, action, and verification contracts.
- Criterion-level `ClaimEvidenceContract` records that prevent a specialist from declaring success without verifiable support.
- Explicit `MissionState` persistence for known facts, unresolved requirements, completed requirements, assumptions, blockers, and last verified progress.
- Mission-state progress detection with a no-progress counter and configurable stall threshold.
- Injected specialist and verifier interfaces; no provider SDK is required by the core.
- Independent contract verification blocks failed missions.
- Consequential actions require an approval bound to the exact action payload hash.
- Idempotency key passed to the action adapter; successful repeat requests return stored results.
- Interrupted action reservations fail closed for manual reconciliation instead of retrying blindly.
- Replayable evaluation snapshots with stable trajectory digests.
- Mission scoring for verification, evidence-contract compliance, event-chain integrity, evidence provenance, stalled state, failure state, and mission success.
- Deterministic behavior-diverse regression subset selection that retains failed/severe cases first.
- Baseline-vs-candidate reliability comparison and configurable reliability gates.
- Fail-closed context permission decisions (`ALLOW / DENY / UNRESOLVED`) using owner, project, and access-tag scope before evidence reaches a specialist.
- Provenance-aware evidence dependencies with transitive invalidation and mission-state cleanup when a source becomes invalid.
- Trust-layer repeatability evaluation across repeated mission runs: valid grading, traceable work, honest completion, and stable results.
- Real-time instrumented tool trajectory guard with allowlist/prohibited-action checks, bounded calls, repeated-operation detection, consecutive-tool loop detection, failure-streak cutoff, and hash-chained audit events.

## Verify

Requires Python 3.10+ and only the standard library.

```bash
python3 -m unittest discover -s alpha-runtime -p 'test_*.py' -v
```

The runtime and evaluation tests cover the durable request-to-verified-result path, process restart, evidence handoff, approval mismatch, duplicate execution, interrupted action handling, verifier rejection, false-success blocking, explicit mission-state persistence, stall detection, replayable trajectory export, reliability gating, approval-state evaluation, regression-case retention, and baseline/candidate comparison.

## Evidence-backed completion

A specialist may only mark a success criterion complete when it returns a matching `ClaimEvidenceContract` with `status="verified"` and an explicit verification method.

```python
from alpha_runtime import ClaimEvidenceContract, SpecialistResult

result = SpecialistResult(
    summary="Prepared draft",
    completed_criteria=("draft prepared",),
    claim_evidence=(
        ClaimEvidenceContract(
            criterion="draft prepared",
            status="verified",
            verification_method="artifact:draft_output",
        ),
    ),
)
```

Evidence IDs referenced by a claim contract must exist in the mission's task or specialist evidence. For completion that is verified from an artifact, state, or direct observation instead of an evidence record, use an explicit `artifact:`, `state:`, or `observation:` verification method. Missing, unknown, or unsupported completion claims fail independent verification and move the mission to `VERIFICATION_FAILED`.

This establishes the rule:

`CLAIM -> REQUIRED SUPPORT -> OBSERVED SUPPORT -> VERIFIED | NOT VERIFIED | UNKNOWN`

`UNKNOWN` and `NOT VERIFIED` never count as success.

## Explicit mission state

Every mission is initialized with a durable state object rather than relying on accumulated conversation history:

- `known_facts`
- `unresolved_requirements`
- `completed_requirements`
- `assumptions`
- `blocking_conditions`
- `last_verified_progress`
- `revision`

The runtime derives a state update after specialist execution, persists it to SQLite, and records a hash-chained `MISSION_STATE_UPDATED` event. Repeating the same semantic state increments `no_progress_count`; `store.is_stalled(mission_id, threshold=2)` allows the host or evaluator to stop or recover a mission that is looping without verified progress.

The intended context pattern is:

`REQUEST -> RETRIEVED EVIDENCE -> EXPLICIT MISSION STATE -> SPECIALIST -> CLAIM EVIDENCE -> STATE UPDATE -> VERIFICATION`

## Evaluation harness

`evaluation_harness.py` converts persisted ALPHA mission state into deterministic trajectory artifacts that can be replayed or retained as a regression corpus.

```python
from alpha_runtime import SQLiteMissionStore
from evaluation_harness import AlphaEvaluationHarness, ReliabilityGate

store = SQLiteMissionStore("missions.sqlite3")
evals = AlphaEvaluationHarness(store)

snapshot_json = evals.export_snapshot("mission-123")
result = evals.evaluate("mission-123")
allowed, reasons = ReliabilityGate(min_score=0.80).decide(result)
```

For a candidate runtime or orchestration change, compare representative baseline and candidate missions:

```python
comparison = evals.compare(
    baseline_ids=["baseline-1", "baseline-2"],
    candidate_ids=["candidate-1", "candidate-2"],
)

regression_ids = evals.regression_subset(all_mission_ids, limit=20)
```

The intended engineering loop is:

`MISSION -> TRAJECTORY -> EVALUATE -> CLASSIFY FAILURE -> REGRESSION CORPUS -> CHANGE -> REPLAY -> COMPARE -> DEPLOY`

The first regression selector is deliberately dependency-free. It retains failures, blocked false-success attempts, and stalled missions first, then chooses behavior-diverse trajectories using recorded mission/event/check/evidence/state features. Replace or augment it with embedding-backed trajectory selection only when mission volume justifies the added dependency and the embedding method is itself evaluated.

## Context authorization and provenance

Evidence can declare `owner_scope`, `project_scope`, required `access_tags`, `validity_status`, and `depends_on` evidence IDs. A mission can declare its own owner/project scope and access tags.

Before execution, every supplied evidence item receives an auditable permission decision:

- `ALLOW`: scope and access policy match; evidence may enter specialist context.
- `DENY`: known scope mismatch, missing access tag, or invalid evidence; the mission fails closed.
- `UNRESOLVED`: scoped evidence was supplied but the mission lacks enough scope information; the mission also fails closed.

Calling `invalidate_evidence()` marks the source invalid, recursively invalidates dependent evidence, records append-only invalidation events, removes unsupported known facts from explicit mission state, and adds an `evidence_invalidated` blocker for re-verification. If the mission is executing, verified, or awaiting approval, its status becomes `VERIFICATION_FAILED`, preventing new external actions even when an approval was previously recorded. If the action was already completed, the mission records a post-action invalidation event requiring manual reconciliation instead of pretending the external effect was undone.

## Trust-layer repeatability

Use repeated equivalent missions to test whether a passing result is actually trustworthy:

```python
report = evals.trust_layer(
    ["mission-repeat-1", "mission-repeat-2", "mission-repeat-3"],
    min_runs=2,
)
```

The report requires four independent conditions: verification/grading exists and the event chain is valid; work remains traceable through provenance and claim-evidence contracts; no false-success condition is present; and normalized result/verification/mission-state digests are identical across runs.

### Metrics currently supported

- Mission success and terminal success.
- Verification pass/fail when a verification record exists.
- Claim-evidence contract pass rate.
- False-success rate and false-success attempts blocked by verification.
- Mission-state stall rate.
- Trajectory horizon/event count.
- Instrumented tool call count, tool-error count, and whether a trajectory guard blocked execution.
- Hash-chain integrity.
- Evidence/context provenance completeness.
- Approval-required and action-completed state.
- Failure classification.
- Aggregate reliability score and baseline/candidate deltas.

### Metrics intentionally not inferred yet

The mission ledger now records instrumented tool-call traces, but not generic tool selection correctness, human overrides, or per-mission token/cost data. Therefore the harness marks these as unsupported rather than fabricating estimates:

- `tool_selection_accuracy`
- `human_override_rate`
- `cost_per_verified_mission`

Add those metrics only after the runtime records the underlying facts explicitly.

## Real-time abnormal trajectory monitoring

Specialists must call tools through the `SpecialistTask.invoke_tool` gateway. The gateway checks **before dispatch**, not after a mission has already completed. Example:

```python
from alpha_runtime import AlphaRuntime, ToolTrajectoryPolicy

runtime = AlphaRuntime(
    store, {"RESEARCHER": specialist},
    trajectory_policy=ToolTrajectoryPolicy(
        max_total_calls=30,
        max_repeats_per_operation=3,
        max_consecutive_same_tool=6,
        max_failures_per_tool=3,
    ),
)

# Inside specialist.run(task), for a read-only tool:
result = task.invoke_tool(
    "web_search", "query:incident-history:2026-10",
    lambda: read_only_search(),
)
```

The mission request must explicitly allow `web_search`. A stable operation key distinguishes repeated identical requests; only its SHA-256 digest is logged, not raw arguments, credentials, results, or exception messages. `TOOL_CALL_STARTED`, `TOOL_CALL_FINISHED`, and `TOOL_CALL_BLOCKED` events are hash-chained. Abnormal calls raise `TrajectoryBlocked` before dispatch and fail the mission even if a specialist swallows the exception. There are **no automatic retries**. Consequential tool calls are rejected by this gateway; they must be proposed and executed through the existing verified human-approval path.

**Enforcement boundary:** This is a local library and only protects calls made through the instrumented gateway. A production host must sandbox or constrain specialists so they cannot invoke arbitrary external SDKs/tools directly. The gateway does not provide process isolation, hard timeouts, semantic loop detection, or tenant authentication. Thresholds are deterministic operational heuristics, not proof that an agent's reasoning is correct.

## Host integration contract

1. Create a persistent SQLite file outside any public/static asset directory and initialize `SQLiteMissionStore`.
2. Implement one narrow `Specialist.run(task)` adapter per role. Give each only its task fields, explicit mission state, and explicitly allowed tools; never pass the full conversation history or credentials.
3. Require every completed success criterion to include a valid `ClaimEvidenceContract`. Do not convert unsupported claims into success.
4. Supply a domain verifier when generic completion checks are insufficient. Keep verification independent from the specialist that produced the result.
5. Call `AlphaRuntime.submit(request, role, evidence)` to plan, run, update state, verify, and persist the proposal.
6. If repeated state updates do not change facts, requirements, assumptions, or blockers, treat the mission as stalled and recover or escalate instead of blindly continuing.
7. Show `AWAITING_APPROVAL` proposals to an authenticated human. Call `approve_and_execute` only after authorization, with an action adapter that honors the provided idempotency key.
8. Record the external system's idempotency behavior and reconciliation method. If an adapter cannot guarantee idempotency, do not automatically retry it.
9. After missions complete, evaluate them with `AlphaEvaluationHarness`; preserve failed/severe trajectories in the regression corpus and gate consequential runtime changes on baseline-vs-candidate results.

## Current limitations (do not describe as production-ready)

- A minimal HTTP API, shared-token authentication, and single-host Docker packaging are included. There is no per-user identity, tenant isolation, hosted database, UI connection, provider/model adapter, or queue.
- SQLite is suitable for a single-host pilot, not concurrent multi-instance production without a deliberate storage migration and concurrency design.
- The host must authenticate approvers, enforce authorization, isolate tenants, protect the database file, redact logs, rate-limit requests, and manage backups/encryption.
- The core doesn't execute arbitrary tools; the host injects any executor. Approval records are not a substitute for user authentication or authorization.
- A crash after an external side effect but before result persistence is marked ambiguous and intentionally requires manual reconciliation.
- Instrumented tool calls are traced, but uninstrumented calls are not observable. Human-override telemetry, token accounting, provider latency, quality, and cost measurement are not yet recorded by this core.

## Lifecycle

`INTAKE -> PLANNED -> EXECUTING -> VERIFICATION_FAILED | VERIFIED | AWAITING_APPROVAL -> ACTION_COMPLETED`

Specialist exceptions transition to `FAILED` and are not retried automatically because the runtime cannot know whether an adapter already caused a side effect.

## Semantica context integration

The optional `semantica_context.py` adapter projects one mission from the ALPHA
SQLite ledger into a Semantica `ContextGraph`. It retains evidence source,
classification, retrieval time, expiry, claim references, verification records,
and the ordered event chain. An invalid ledger or unknown evidence reference
blocks graph construction. Each call builds a fresh graph for one mission.
SQLite stays authoritative; rebuilding the graph does not change approval or
mission state. Keep the graph on the trusted host, outside public assets.

Install the pinned Prime24AI fork in the host environment (Python 3.10–3.13):

```bash
python3 -m venv .venv-semantica
.venv-semantica/bin/python -m pip install -r alpha-runtime/requirements-semantica.txt
.venv-semantica/bin/python -m unittest discover -s alpha-runtime -p 'test_*.py' -v
```

Use from a host that has `alpha-runtime` on its Python path:

```python
from alpha_runtime import SQLiteMissionStore
from semantica_context import SemanticaContext

store = SQLiteMissionStore('/private/alpha/missions.sqlite3')
graph = SemanticaContext(store).build_graph('mission-123')
# An existing AlphaRuntime also exposes runtime.context_graph('mission-123').
```

This adds graph context to the executable core. It does not deploy a service or
connect the public Sites UI. No LLM credentials, external graph database, or
model provider is required. Hypotheses remain labeled hypotheses; graph links
are recorded relationships, not proof of causation. Graph output does not grant
permission to act and must not replace ALPHA's independent verification gates.
