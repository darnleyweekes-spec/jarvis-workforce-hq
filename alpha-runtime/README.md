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

## Verify

Requires Python 3.10+ and only the standard library.

```bash
python3 -m unittest discover -s alpha-runtime -p 'test_*.py' -v
```

Five tests cover the durable request-to-verified-result path, process restart, evidence handoff, approval mismatch, duplicate execution, interrupted action handling, and verifier rejection.

The optional `shadow_decisions.py` adapter and its three tests exercise a typed intake decision
through the same mission lifecycle with a stub provider. It records a proposed route only;
it has no Jev API connection, message sender, or routing executor. Confidence thresholds in
that adapter are illustrative, not calibrated for customer data. Do not enable live routing
from these local tests; first evaluate a real provider on labeled requests and measure
urgent misses, review rate, end-to-end latency, and cost against the existing workflow.

For an actual Jev API measurement, set `TYPESAFE_API_KEY` outside the repository and run
`python3 alpha-runtime/benchmark_jev.py`. It uses ten labeled synthetic intake examples,
serial API calls, and a temporary SQLite mission store. It reports category matches,
urgent misses, review rate, observed API latency, total runtime, and estimated input cost.
It stops before making a call when the key is absent. A ten-example synthetic result is a
smoke test, not evidence that customer intake can be routed automatically.

## Host integration contract

1. Create a persistent SQLite file outside any public/static asset directory and initialize `SQLiteMissionStore`.
2. Implement one narrow `Specialist.run(task)` adapter per role. Give each only its task fields and explicitly allowed tools; never pass the full conversation history or credentials.
3. Supply a domain verifier when generic completion checks are insufficient. Keep verification independent from the specialist that produced the result.
4. Call `AlphaRuntime.submit(request, role, evidence)` to plan, run, verify, and persist the proposal.
5. Show `AWAITING_APPROVAL` proposals to an authenticated human. Call `approve_and_execute` only after authorization, with an action adapter that honors the provided idempotency key.
6. Record the external system's idempotency behavior and reconciliation method. If an adapter cannot guarantee idempotency, do not automatically retry it.

## Current limitations (do not describe as production-ready)

- No HTTP/API server, authentication, tenant isolation, hosted database, UI connection, provider/model adapter, queue, or deployment configuration is included.
- SQLite is suitable for a single-host pilot, not concurrent multi-instance production without a deliberate storage migration and concurrency design.
- The host must authenticate approvers, enforce authorization, isolate tenants, protect the database file, redact logs, rate-limit requests, and manage backups/encryption.
- The core doesn't execute arbitrary tools; the host injects any executor. Approval records are not a substitute for user authentication or authorization.
- A crash after an external side effect but before result persistence is marked ambiguous and intentionally requires manual reconciliation.
- No real provider latency, quality, or cost measurement has been claimed.

## Lifecycle

`INTAKE -> PLANNED -> EXECUTING -> VERIFICATION_FAILED | VERIFIED | AWAITING_APPROVAL -> ACTION_COMPLETED`

Specialist exceptions transition to `FAILED` and are not retried automatically because the runtime cannot know whether an adapter already caused a side effect.
