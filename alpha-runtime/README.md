# ALPHA Runtime Core (first executable slice)

This is a provider-neutral Python runtime core for supervised ALPHA missions. It is an engine/library, not yet the deployed Sites backend or a connected model/agent service.

## What is implemented

- SQLite persistence for mission state and evidence across process restarts.
- Append-only, hash-chained lifecycle events; database triggers reject event edits and deletion.
- Typed request, evidence, scoped specialist-task, action, and verification contracts.
- Injected specialist and verifier interfaces; no provider SDK is required by the core.
- Independent contract verification blocks failed missions.
- Consequential actions require an approval bound to the exact action payload hash.
- Idempotency key passed to the action adapter; successful repeat requests return stored results.
- Interrupted action reservations fail closed for manual reconciliation instead of retrying blindly.
- Replayable evaluation snapshots with stable trajectory digests.
- Mission scoring for verification, event-chain integrity, evidence provenance, failure state, and mission success.
- Deterministic behavior-diverse regression subset selection that retains failed/severe cases first.
- Baseline-vs-candidate reliability comparison and configurable reliability gates.

## Verify

Requires Python 3.10+ and only the standard library.

```bash
python3 -m unittest discover -s alpha-runtime -p 'test_*.py' -v
```

The runtime and evaluation tests cover the durable request-to-verified-result path, process restart, evidence handoff, approval mismatch, duplicate execution, interrupted action handling, verifier rejection, replayable trajectory export, reliability gating, approval-state evaluation, regression-case retention, and baseline/candidate comparison.

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

The first regression selector is deliberately dependency-free. It retains failures first and then chooses behavior-diverse trajectories using recorded mission/event/check/evidence features. Replace or augment it with embedding-backed trajectory selection only when mission volume justifies the added dependency and the embedding method is itself evaluated.

### Metrics currently supported

- Mission success and terminal success.
- Verification pass/fail when a verification record exists.
- Hash-chain integrity.
- Evidence/context provenance completeness.
- Approval-required and action-completed state.
- Failure classification.
- Aggregate reliability score and baseline/candidate deltas.

### Metrics intentionally not inferred yet

The current mission ledger does not generically record arbitrary tool-call traces, human overrides, or per-mission token/cost data. Therefore the harness marks these as unsupported rather than fabricating estimates:

- `tool_selection_accuracy`
- `human_override_rate`
- `cost_per_verified_mission`

Add those metrics only after the runtime records the underlying facts explicitly.

## Host integration contract

1. Create a persistent SQLite file outside any public/static asset directory and initialize `SQLiteMissionStore`.
2. Implement one narrow `Specialist.run(task)` adapter per role. Give each only its task fields and explicitly allowed tools; never pass the full conversation history or credentials.
3. Supply a domain verifier when generic completion checks are insufficient. Keep verification independent from the specialist that produced the result.
4. Call `AlphaRuntime.submit(request, role, evidence)` to plan, run, verify, and persist the proposal.
5. Show `AWAITING_APPROVAL` proposals to an authenticated human. Call `approve_and_execute` only after authorization, with an action adapter that honors the provided idempotency key.
6. Record the external system's idempotency behavior and reconciliation method. If an adapter cannot guarantee idempotency, do not automatically retry it.
7. After missions complete, evaluate them with `AlphaEvaluationHarness`; preserve failed/severe trajectories in the regression corpus and gate consequential runtime changes on baseline-vs-candidate results.

## Current limitations (do not describe as production-ready)

- No HTTP/API server, authentication, tenant isolation, hosted database, UI connection, provider/model adapter, queue, or deployment configuration is included.
- SQLite is suitable for a single-host pilot, not concurrent multi-instance production without a deliberate storage migration and concurrency design.
- The host must authenticate approvers, enforce authorization, isolate tenants, protect the database file, redact logs, rate-limit requests, and manage backups/encryption.
- The core doesn't execute arbitrary tools; the host injects any executor. Approval records are not a substitute for user authentication or authorization.
- A crash after an external side effect but before result persistence is marked ambiguous and intentionally requires manual reconciliation.
- Generic tool-call tracing, human-override telemetry, token accounting, provider latency, quality, and cost measurement are not yet recorded by this core.

## Lifecycle

`INTAKE -> PLANNED -> EXECUTING -> VERIFICATION_FAILED | VERIFIED | AWAITING_APPROVAL -> ACTION_COMPLETED`

Specialist exceptions transition to `FAILED` and are not retried automatically because the runtime cannot know whether an adapter already caused a side effect.
