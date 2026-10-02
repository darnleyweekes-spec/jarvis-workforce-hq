"""Small, provider-neutral ALPHA mission runtime.

This is a local execution core, not a hosted multi-tenant service. It persists
mission state and an append-only hash-chained event log in SQLite. No external
action runs unless a matching action is explicitly approved and an executor is
injected by the host application.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence


class MissionError(RuntimeError):
    pass


class ApprovalRequired(MissionError):
    pass


class VerificationFailed(MissionError):
    pass


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    claim: str
    source: str
    retrieved_at: str
    classification: str  # fact | inference | hypothesis | user_input
    freshness_seconds: int | None = None
    expires_at: str | None = None


@dataclass(frozen=True)
class ClaimEvidenceContract:
    """Binds a claimed completed criterion to verifiable support."""

    criterion: str
    status: str  # verified | not_verified | unknown
    evidence_ids: tuple[str, ...] = ()
    verification_method: str = ""


@dataclass(frozen=True)
class MissionState:
    """Compact explicit state for long-horizon execution."""

    known_facts: tuple[str, ...] = ()
    unresolved_requirements: tuple[str, ...] = ()
    completed_requirements: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    blocking_conditions: tuple[str, ...] = ()
    last_verified_progress: str | None = None
    revision: int = 0


@dataclass(frozen=True)
class MissionRequest:
    objective: str
    success_criteria: list[str]
    constraints: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    prohibited_actions: list[str] = field(default_factory=list)
    approval_required: bool = True
    mission_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class SpecialistTask:
    task_id: str
    role: str
    objective: str
    success_criteria: tuple[str, ...]
    constraints: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    mission_state: MissionState
    attempt: int = 1
    max_attempts: int = 2


@dataclass(frozen=True)
class SpecialistResult:
    summary: str
    evidence: tuple[Evidence, ...] = ()
    proposed_actions: tuple["ProposedAction", ...] = ()
    completed_criteria: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    claim_evidence: tuple[ClaimEvidenceContract, ...] = ()
    mission_state: MissionState | None = None


@dataclass(frozen=True)
class ProposedAction:
    action_id: str
    kind: str
    payload: dict[str, Any]
    consequential: bool = True

    @property
    def payload_hash(self) -> str:
        encoded = json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True)
class Verification:
    passed: bool
    checks: tuple[dict[str, Any], ...]
    rationale: str


class Specialist(Protocol):
    def run(self, task: SpecialistTask) -> SpecialistResult: ...


class Verifier(Protocol):
    def verify(self, task: SpecialistTask, result: SpecialistResult) -> Verification: ...


ActionExecutor = Callable[[ProposedAction, str], dict[str, Any]]


class SQLiteMissionStore:
    """SQLite persistence with append-only, hash-chained mission events."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    verification_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    mission_id TEXT NOT NULL REFERENCES missions(mission_id),
                    evidence_id TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY(mission_id, evidence_id)
                );
                CREATE TABLE IF NOT EXISTS mission_states (
                    mission_id TEXT PRIMARY KEY REFERENCES missions(mission_id),
                    state_json TEXT NOT NULL,
                    state_hash TEXT NOT NULL,
                    no_progress_count INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL REFERENCES missions(mission_id),
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TRIGGER IF NOT EXISTS events_no_update
                    BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete
                    BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
                CREATE TABLE IF NOT EXISTS approvals (
                    mission_id TEXT NOT NULL REFERENCES missions(mission_id),
                    action_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    approved_at REAL NOT NULL,
                    PRIMARY KEY(mission_id, action_id)
                );
                CREATE TABLE IF NOT EXISTS action_runs (
                    mission_id TEXT NOT NULL REFERENCES missions(mission_id),
                    action_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    executed_at REAL NOT NULL,
                    PRIMARY KEY(mission_id, action_id)
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _event(self, db: sqlite3.Connection, mission_id: str, event_type: str,
               payload: dict[str, Any]) -> None:
        prev = db.execute(
            "SELECT event_hash FROM events WHERE mission_id=? ORDER BY seq DESC LIMIT 1",
            (mission_id,),
        ).fetchone()
        prev_hash = prev["event_hash"] if prev else "0" * 64
        now = time.time()
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        body = json.dumps({"mission_id": mission_id, "event_type": event_type,
                           "payload": json.loads(payload_json), "created_at": now,
                           "prev_hash": prev_hash}, sort_keys=True, separators=(",", ":"))
        event_hash = hashlib.sha256(body.encode()).hexdigest()
        db.execute(
            "INSERT INTO events(mission_id,event_type,payload_json,created_at,prev_hash,event_hash) VALUES(?,?,?,?,?,?)",
            (mission_id, event_type, payload_json, now, prev_hash, event_hash),
        )

    @staticmethod
    def _state_fingerprint(state: MissionState) -> str:
        semantic = {
            "known_facts": state.known_facts,
            "unresolved_requirements": state.unresolved_requirements,
            "completed_requirements": state.completed_requirements,
            "assumptions": state.assumptions,
            "blocking_conditions": state.blocking_conditions,
        }
        return hashlib.sha256(
            json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _set_state_in_db(
        self,
        db: sqlite3.Connection,
        mission_id: str,
        state: MissionState,
        *,
        event_type: str = "MISSION_STATE_UPDATED",
    ) -> tuple[bool, int]:
        overlap = set(state.completed_requirements) & set(state.unresolved_requirements)
        if overlap:
            raise ValueError(
                f"requirements cannot be both complete and unresolved: {sorted(overlap)}"
            )
        row = db.execute(
            "SELECT state_hash,no_progress_count FROM mission_states WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        fingerprint = self._state_fingerprint(state)
        progressed = row is None or row["state_hash"] != fingerprint
        no_progress_count = 0 if progressed else int(row["no_progress_count"]) + 1
        now = time.time()
        db.execute(
            "INSERT INTO mission_states(mission_id,state_json,state_hash,no_progress_count,updated_at) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(mission_id) DO UPDATE SET state_json=excluded.state_json,"
            "state_hash=excluded.state_hash,no_progress_count=excluded.no_progress_count,"
            "updated_at=excluded.updated_at",
            (
                mission_id,
                json.dumps(asdict(state), sort_keys=True),
                fingerprint,
                no_progress_count,
                now,
            ),
        )
        self._event(db, mission_id, event_type, {
            "revision": state.revision,
            "progressed": progressed,
            "no_progress_count": no_progress_count,
            "completed_count": len(state.completed_requirements),
            "unresolved_count": len(state.unresolved_requirements),
            "blocking_count": len(state.blocking_conditions),
        })
        return progressed, no_progress_count

    def create(self, request: MissionRequest) -> None:
        now = time.time()
        initial_state = MissionState(
            unresolved_requirements=tuple(request.success_criteria),
            revision=0,
        )
        with self._connect() as db:
            db.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?)", (
                request.mission_id, "INTAKE", json.dumps(asdict(request), sort_keys=True),
                None, None, now, now))
            self._event(db, request.mission_id, "MISSION_CREATED", {
                "objective": request.objective,
                "criteria_count": len(request.success_criteria),
                "approval_required": request.approval_required,
            })
            self._set_state_in_db(
                db,
                request.mission_id,
                initial_state,
                event_type="MISSION_STATE_INITIALIZED",
            )

    def add_evidence(self, mission_id: str, item: Evidence) -> None:
        if item.classification not in {"fact", "inference", "hypothesis", "user_input"}:
            raise ValueError("unsupported evidence classification")
        with self._connect() as db:
            self._require(db, mission_id)
            db.execute("INSERT INTO evidence VALUES(?,?,?,?)", (
                mission_id, item.evidence_id, json.dumps(asdict(item), sort_keys=True), time.time()))
            self._event(db, mission_id, "EVIDENCE_ADDED", {
                "evidence_id": item.evidence_id, "source": item.source,
                "retrieved_at": item.retrieved_at, "classification": item.classification,
            })

    def get_mission_state(self, mission_id: str) -> MissionState:
        with self._connect() as db:
            self._require(db, mission_id)
            row = db.execute(
                "SELECT state_json FROM mission_states WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if row is None:
                raise MissionError("mission state not found")
            raw = json.loads(row["state_json"])
            return MissionState(
                known_facts=tuple(raw.get("known_facts", [])),
                unresolved_requirements=tuple(raw.get("unresolved_requirements", [])),
                completed_requirements=tuple(raw.get("completed_requirements", [])),
                assumptions=tuple(raw.get("assumptions", [])),
                blocking_conditions=tuple(raw.get("blocking_conditions", [])),
                last_verified_progress=raw.get("last_verified_progress"),
                revision=int(raw.get("revision", 0)),
            )

    def set_mission_state(self, mission_id: str, state: MissionState) -> tuple[bool, int]:
        with self._connect() as db:
            self._require(db, mission_id)
            return self._set_state_in_db(db, mission_id, state)

    def is_stalled(self, mission_id: str, threshold: int = 2) -> bool:
        if threshold < 1:
            raise ValueError("stall threshold must be >= 1")
        with self._connect() as db:
            self._require(db, mission_id)
            row = db.execute(
                "SELECT no_progress_count FROM mission_states WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if row is None:
                raise MissionError("mission state not found")
            return int(row["no_progress_count"]) >= threshold

    def transition(self, mission_id: str, expected: str, status: str,
                   event_type: str, payload: dict[str, Any] | None = None) -> None:
        with self._connect() as db:
            row = self._require(db, mission_id)
            if row["status"] != expected:
                raise MissionError(
                    f"invalid state transition: expected {expected}, got {row['status']}"
                )
            db.execute("UPDATE missions SET status=?, updated_at=? WHERE mission_id=?",
                       (status, time.time(), mission_id))
            self._event(db, mission_id, event_type, payload or {"from": expected, "to": status})

    def set_result(self, mission_id: str, result: SpecialistResult) -> None:
        with self._connect() as db:
            self._require(db, mission_id)
            db.execute("UPDATE missions SET result_json=?, updated_at=? WHERE mission_id=?",
                       (json.dumps(asdict(result), sort_keys=True), time.time(), mission_id))
            for item in result.evidence:
                if item.classification not in {"fact", "inference", "hypothesis", "user_input"}:
                    raise ValueError("unsupported evidence classification")
                db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)", (
                    mission_id, item.evidence_id, json.dumps(asdict(item), sort_keys=True), time.time()))
            if result.mission_state is not None:
                self._set_state_in_db(db, mission_id, result.mission_state)
            self._event(db, mission_id, "SPECIALIST_RESULT", {
                "summary": result.summary,
                "completed_criteria": list(result.completed_criteria),
                "proposed_actions": [a.action_id for a in result.proposed_actions],
                "errors": list(result.errors),
                "evidence_ids": [e.evidence_id for e in result.evidence],
                "claim_contracts": [c.criterion for c in result.claim_evidence],
            })

    def set_verification(self, mission_id: str, verification: Verification) -> None:
        with self._connect() as db:
            self._require(db, mission_id)
            db.execute("UPDATE missions SET verification_json=?, updated_at=? WHERE mission_id=?",
                       (json.dumps(asdict(verification), sort_keys=True), time.time(), mission_id))
            self._event(db, mission_id, "VERIFICATION", asdict(verification))

    def approve(self, mission_id: str, action: ProposedAction, approver: str) -> None:
        if not approver.strip():
            raise ValueError("approver identity is required")
        with self._connect() as db:
            row = self._require(db, mission_id)
            if row["status"] != "AWAITING_APPROVAL":
                raise ApprovalRequired("mission is not awaiting approval")
            db.execute("INSERT INTO approvals VALUES(?,?,?,?,?)", (
                mission_id, action.action_id, action.payload_hash, approver, time.time()))
            self._event(db, mission_id, "ACTION_APPROVED", {
                "action_id": action.action_id,
                "payload_hash": action.payload_hash,
                "approver": approver,
            })

    def approval_matches(self, mission_id: str, action: ProposedAction) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload_hash FROM approvals WHERE mission_id=? AND action_id=?",
                (mission_id, action.action_id),
            ).fetchone()
            return bool(row and row["payload_hash"] == action.payload_hash)

    def execute_once(self, mission_id: str, action: ProposedAction,
                     executor: ActionExecutor) -> dict[str, Any]:
        if action.consequential and not self.approval_matches(mission_id, action):
            raise ApprovalRequired("matching human approval is required")
        with self._connect() as db:
            previous = db.execute(
                "SELECT payload_hash,result_json FROM action_runs WHERE mission_id=? AND action_id=?",
                (mission_id, action.action_id),
            ).fetchone()
            if previous:
                if previous["payload_hash"] != action.payload_hash:
                    raise MissionError("idempotency key reused with different action payload")
                prior_result = json.loads(previous["result_json"])
                if prior_result.get("status") == "RESERVED":
                    raise MissionError(
                        "action outcome is unknown after an interrupted execution; "
                        "reconcile manually before retrying"
                    )
                return prior_result
            now = time.time()
            db.execute("INSERT INTO action_runs VALUES(?,?,?,?,?)", (
                mission_id,
                action.action_id,
                action.payload_hash,
                json.dumps({"status": "RESERVED"}),
                now,
            ))
            self._event(db, mission_id, "ACTION_RESERVED", {
                "action_id": action.action_id,
                "payload_hash": action.payload_hash,
            })
        result = executor(action, f"{mission_id}:{action.action_id}")
        with self._connect() as db:
            db.execute(
                "UPDATE action_runs SET result_json=?, executed_at=? WHERE mission_id=? AND action_id=?",
                (json.dumps(result, sort_keys=True), time.time(), mission_id, action.action_id),
            )
            self._event(db, mission_id, "ACTION_EXECUTED", {
                "action_id": action.action_id,
                "payload_hash": action.payload_hash,
                "result_digest": hashlib.sha256(
                    json.dumps(result, sort_keys=True).encode()
                ).hexdigest(),
            })
        return result

    def get(self, mission_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = self._require(db, mission_id)
            state_row = db.execute(
                "SELECT state_json,no_progress_count FROM mission_states WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            return {
                **dict(row),
                "request": json.loads(row["request_json"]),
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "verification": (
                    json.loads(row["verification_json"]) if row["verification_json"] else None
                ),
                "evidence": [
                    json.loads(r[0])
                    for r in db.execute(
                        "SELECT evidence_json FROM evidence WHERE mission_id=? ORDER BY created_at",
                        (mission_id,),
                    )
                ],
                "mission_state": json.loads(state_row["state_json"]) if state_row else None,
                "no_progress_count": int(state_row["no_progress_count"]) if state_row else None,
            }

    def events(self, mission_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            self._require(db, mission_id)
            return [
                dict(r) | {"payload": json.loads(r["payload_json"])}
                for r in db.execute(
                    "SELECT * FROM events WHERE mission_id=? ORDER BY seq",
                    (mission_id,),
                )
            ]

    def verify_event_chain(self, mission_id: str) -> bool:
        previous = "0" * 64
        for event in self.events(mission_id):
            if event["prev_hash"] != previous:
                return False
            body = json.dumps({
                "mission_id": mission_id,
                "event_type": event["event_type"],
                "payload": event["payload"],
                "created_at": event["created_at"],
                "prev_hash": previous,
            }, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(body.encode()).hexdigest()
            if digest != event["event_hash"]:
                return False
            previous = digest
        return True

    @staticmethod
    def _require(db: sqlite3.Connection, mission_id: str) -> sqlite3.Row:
        row = db.execute(
            "SELECT * FROM missions WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            raise MissionError("mission not found")
        return row


class ContractVerifier:
    """Independent minimum verifier with criterion-level evidence contracts."""

    _allowed_claim_statuses = {"verified", "not_verified", "unknown"}
    _non_evidence_methods = ("artifact:", "state:", "observation:")

    def verify(self, task: SpecialistTask, result: SpecialistResult) -> Verification:
        returned = set(result.completed_criteria)
        required = set(task.success_criteria)
        criteria_ok = required.issubset(returned)
        errors_ok = not result.errors

        available_evidence = {
            item.evidence_id for item in (*task.evidence, *result.evidence)
        }
        contracts = {contract.criterion: contract for contract in result.claim_evidence}
        invalid_contracts: list[dict[str, Any]] = []
        missing_contracts: list[str] = []
        for criterion in sorted(returned):
            contract = contracts.get(criterion)
            if contract is None:
                missing_contracts.append(criterion)
                continue
            ids_valid = all(
                item_id in available_evidence for item_id in contract.evidence_ids
            )
            method = contract.verification_method.strip()
            has_support = bool(contract.evidence_ids) or method.startswith(
                self._non_evidence_methods
            )
            valid = (
                contract.status in self._allowed_claim_statuses
                and contract.status == "verified"
                and bool(method)
                and ids_valid
                and has_support
            )
            if not valid:
                invalid_contracts.append({
                    "criterion": criterion,
                    "status": contract.status,
                    "verification_method": contract.verification_method,
                    "unknown_evidence_ids": sorted(
                        item_id
                        for item_id in contract.evidence_ids
                        if item_id not in available_evidence
                    ),
                })
        claim_contract_ok = not missing_contracts and not invalid_contracts

        state = result.mission_state
        state_ok = bool(
            state
            and returned.issubset(set(state.completed_requirements))
            and not (
                set(state.completed_requirements)
                & set(state.unresolved_requirements)
            )
        )

        checks = (
            {
                "name": "success_criteria",
                "passed": criteria_ok,
                "missing": sorted(required - returned),
            },
            {
                "name": "no_reported_errors",
                "passed": errors_ok,
                "errors": list(result.errors),
            },
            {
                "name": "evidence_metadata",
                "passed": all(
                    e.source and e.retrieved_at and e.classification
                    for e in result.evidence
                ),
            },
            {
                "name": "claim_evidence_contract",
                "passed": claim_contract_ok,
                "missing_contracts": missing_contracts,
                "invalid_contracts": invalid_contracts,
            },
            {
                "name": "mission_state_consistency",
                "passed": state_ok,
                "has_state": state is not None,
            },
        )
        passed = all(check["passed"] for check in checks)
        return Verification(
            passed,
            checks,
            "Contract checks passed."
            if passed
            else "One or more independent checks failed.",
        )


class AlphaRuntime:
    """Orchestrates an explicit lifecycle using injected, narrow specialists."""

    def __init__(self, store: SQLiteMissionStore, specialists: dict[str, Specialist],
                 verifier: Verifier | None = None):
        self.store = store
        self.specialists = specialists
        self.verifier = verifier or ContractVerifier()

    @staticmethod
    def _derive_state(
        prior: MissionState,
        request: MissionRequest,
        task_evidence: Sequence[Evidence],
        result: SpecialistResult,
    ) -> MissionState:
        combined = (*task_evidence, *result.evidence)
        facts = tuple(dict.fromkeys([
            *prior.known_facts,
            *(
                e.claim
                for e in combined
                if e.classification in {"fact", "user_input"}
            ),
        ]))
        assumptions = tuple(dict.fromkeys([
            *prior.assumptions,
            *(
                e.claim
                for e in combined
                if e.classification in {"inference", "hypothesis"}
            ),
        ]))
        completed = tuple(dict.fromkeys(result.completed_criteria))
        completed_set = set(completed)
        unresolved = tuple(
            criterion
            for criterion in request.success_criteria
            if criterion not in completed_set
        )
        blockers = tuple(dict.fromkeys(result.errors))
        return MissionState(
            known_facts=facts,
            unresolved_requirements=unresolved,
            completed_requirements=completed,
            assumptions=assumptions,
            blocking_conditions=blockers,
            last_verified_progress=prior.last_verified_progress,
            revision=prior.revision + 1,
        )

    def submit(self, request: MissionRequest, role: str,
               evidence: Sequence[Evidence] = ()) -> dict[str, Any]:
        if not request.objective.strip() or not request.success_criteria:
            raise ValueError("objective and at least one success criterion are required")
        if role not in self.specialists:
            raise ValueError(f"no specialist registered for role {role}")
        self.store.create(request)
        for item in evidence:
            self.store.add_evidence(request.mission_id, item)
        self.store.transition(
            request.mission_id,
            "INTAKE",
            "PLANNED",
            "MISSION_PLANNED",
            {"role": role, "criteria_count": len(request.success_criteria)},
        )
        self.store.transition(
            request.mission_id,
            "PLANNED",
            "EXECUTING",
            "SPECIALIST_STARTED",
            {"role": role},
        )
        prior_state = self.store.get_mission_state(request.mission_id)
        scoped = SpecialistTask(
            task_id=str(uuid.uuid4()),
            role=role,
            objective=request.objective,
            success_criteria=tuple(request.success_criteria),
            constraints=tuple(request.constraints),
            allowed_tools=tuple(request.allowed_tools),
            prohibited_actions=tuple(request.prohibited_actions),
            evidence=tuple(evidence),
            mission_state=prior_state,
            max_attempts=2,
        )
        try:
            result = self.specialists[role].run(scoped)
        except Exception as exc:  # Never silently retry side effects.
            self.store.transition(
                request.mission_id,
                "EXECUTING",
                "FAILED",
                "SPECIALIST_FAILED",
                {"role": role, "error_type": type(exc).__name__},
            )
            raise MissionError(
                "specialist failed; mission recorded without automatic retry"
            ) from exc

        if result.mission_state is None:
            result = replace(
                result,
                mission_state=self._derive_state(
                    prior_state,
                    request,
                    evidence,
                    result,
                ),
            )
        self.store.set_result(request.mission_id, result)

        verification = self.verifier.verify(scoped, result)
        self.store.set_verification(request.mission_id, verification)
        if not verification.passed:
            failed_state = result.mission_state
            if failed_state is not None:
                failed_state = replace(
                    failed_state,
                    blocking_conditions=tuple(dict.fromkeys([
                        *failed_state.blocking_conditions,
                        "verification_failed",
                    ])),
                    revision=failed_state.revision + 1,
                )
                self.store.set_mission_state(request.mission_id, failed_state)
            self.store.transition(
                request.mission_id,
                "EXECUTING",
                "VERIFICATION_FAILED",
                "MISSION_BLOCKED",
                {"reason": verification.rationale},
            )
            raise VerificationFailed(verification.rationale)

        verified_state = result.mission_state
        if verified_state is not None:
            progress_label = (
                "verified:" + ",".join(sorted(result.completed_criteria))
                if result.completed_criteria
                else "verified:no_completed_criteria"
            )
            verified_state = replace(
                verified_state,
                last_verified_progress=progress_label,
                revision=verified_state.revision + 1,
            )
            self.store.set_mission_state(request.mission_id, verified_state)

        pending_actions = [
            action
            for action in result.proposed_actions
            if action.consequential
        ]
        if pending_actions:
            self.store.transition(
                request.mission_id,
                "EXECUTING",
                "AWAITING_APPROVAL",
                "APPROVAL_REQUIRED",
                {"action_ids": [a.action_id for a in pending_actions]},
            )
        else:
            self.store.transition(
                request.mission_id,
                "EXECUTING",
                "VERIFIED",
                "MISSION_VERIFIED",
                {"action_count": len(result.proposed_actions)},
            )
        return self.store.get(request.mission_id)

    def approve_and_execute(self, mission_id: str, action: ProposedAction, approver: str,
                            executor: ActionExecutor) -> dict[str, Any]:
        state = self.store.get(mission_id)
        if state["status"] != "AWAITING_APPROVAL":
            raise ApprovalRequired("mission is not awaiting approval")
        declared = state["result"] or {}
        match = next(
            (
                item
                for item in declared.get("proposed_actions", [])
                if item["action_id"] == action.action_id
            ),
            None,
        )
        if not match:
            raise ApprovalRequired("action was not proposed by the verified mission")
        expected_hash = ProposedAction(**match).payload_hash
        if expected_hash != action.payload_hash:
            raise ApprovalRequired(
                "approved action payload differs from verified proposal"
            )
        self.store.approve(mission_id, action, approver)
        result = self.store.execute_once(mission_id, action, executor)
        self.store.transition(
            mission_id,
            "AWAITING_APPROVAL",
            "ACTION_COMPLETED",
            "MISSION_ACTION_COMPLETED",
            {"action_id": action.action_id},
        )
        return result
