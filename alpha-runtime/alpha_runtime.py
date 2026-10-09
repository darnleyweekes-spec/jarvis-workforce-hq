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


class ContextPermissionDenied(MissionError):
    pass


class TrajectoryBlocked(MissionError):
    """An unsafe or abnormal instrumented tool call was stopped before dispatch."""


@dataclass(frozen=True)
class ToolTrajectoryPolicy:
    max_total_calls: int = 30
    max_repeats_per_operation: int = 3
    max_consecutive_same_tool: int = 6
    max_failures_per_tool: int = 3

    def __post_init__(self):
        if min(
            self.max_total_calls,
            self.max_repeats_per_operation,
            self.max_consecutive_same_tool,
            self.max_failures_per_tool,
        ) < 1:
            raise ValueError("trajectory limits must be positive")


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    claim: str
    source: str
    retrieved_at: str
    classification: str  # fact | inference | hypothesis | user_input
    freshness_seconds: int | None = None
    expires_at: str | None = None
    owner_scope: str | None = None
    project_scope: str | None = None
    access_tags: tuple[str, ...] = ()
    validity_status: str = "active"  # active | invalid
    depends_on: tuple[str, ...] = ()


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
    owner_scope: str | None = None
    project_scope: str | None = None
    access_tags: list[str] = field(default_factory=list)
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
    tool_guard: ToolTrajectoryGuard | None = field(default=None, repr=False, compare=False)

    def invoke_tool(
        self,
        tool_name: str,
        operation_key: str,
        executor: Callable[[], Any],
        *,
        consequential: bool = False,
    ) -> Any:
        """Instrumented read-only tool gateway; all adapters must use this path."""
        if self.tool_guard is None:
            raise TrajectoryBlocked("no instrumented tool gateway is configured")
        return self.tool_guard.invoke(
            tool_name, operation_key, executor, consequential=consequential
        )


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
        if item.validity_status not in {"active", "invalid"}:
            raise ValueError("unsupported evidence validity status")
        with self._connect() as db:
            self._require(db, mission_id)
            db.execute("INSERT INTO evidence VALUES(?,?,?,?)", (
                mission_id, item.evidence_id, json.dumps(asdict(item), sort_keys=True), time.time()))
            self._event(db, mission_id, "EVIDENCE_ADDED", {
                "evidence_id": item.evidence_id, "source": item.source,
                "retrieved_at": item.retrieved_at, "classification": item.classification,
                "owner_scope": item.owner_scope, "project_scope": item.project_scope,
                "access_tags": list(item.access_tags), "validity_status": item.validity_status,
                "depends_on": list(item.depends_on),
            })

    def record_context_decision(
        self,
        mission_id: str,
        evidence_id: str,
        decision: str,
        reason: str,
    ) -> None:
        if decision not in {"ALLOW", "DENY", "UNRESOLVED"}:
            raise ValueError("unsupported context permission decision")
        with self._connect() as db:
            self._require(db, mission_id)
            self._event(db, mission_id, "CONTEXT_PERMISSION_DECISION", {
                "evidence_id": evidence_id,
                "decision": decision,
                "reason": reason,
            })

    def invalidate_evidence(
        self,
        mission_id: str,
        evidence_id: str,
        reason: str,
    ) -> tuple[str, ...]:
        """Invalidate evidence and transitively invalidate dependent evidence."""
        if not reason.strip():
            raise ValueError("invalidation reason is required")
        with self._connect() as db:
            mission_row = self._require(db, mission_id)
            rows = list(db.execute(
                "SELECT evidence_id,evidence_json FROM evidence WHERE mission_id=?",
                (mission_id,),
            ))
            by_id = {row["evidence_id"]: json.loads(row["evidence_json"]) for row in rows}
            if evidence_id not in by_id:
                raise MissionError("evidence not found")
            invalidated: list[str] = []
            queue = [evidence_id]
            while queue:
                current = queue.pop(0)
                if current in invalidated:
                    continue
                invalidated.append(current)
                for candidate_id, payload in by_id.items():
                    if current in payload.get("depends_on", []) and candidate_id not in invalidated:
                        queue.append(candidate_id)
            for current in invalidated:
                payload = dict(by_id[current])
                payload["validity_status"] = "invalid"
                db.execute(
                    "UPDATE evidence SET evidence_json=? WHERE mission_id=? AND evidence_id=?",
                    (json.dumps(payload, sort_keys=True), mission_id, current),
                )
                self._event(db, mission_id, "EVIDENCE_INVALIDATED", {
                    "evidence_id": current,
                    "root_evidence_id": evidence_id,
                    "reason": reason,
                })

            state_row = db.execute(
                "SELECT state_json FROM mission_states WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if state_row:
                raw_state = json.loads(state_row["state_json"])
                active_claims = {
                    payload.get("claim")
                    for item_id, payload in by_id.items()
                    if item_id not in invalidated
                    and payload.get("validity_status", "active") == "active"
                    and payload.get("classification") in {"fact", "user_input"}
                }
                invalid_claims = {
                    by_id[item_id].get("claim")
                    for item_id in invalidated
                    if by_id[item_id].get("classification") in {"fact", "user_input"}
                }
                known_facts = tuple(
                    fact for fact in raw_state.get("known_facts", [])
                    if fact not in invalid_claims or fact in active_claims
                )
                state = MissionState(
                    known_facts=known_facts,
                    unresolved_requirements=tuple(raw_state.get("unresolved_requirements", [])),
                    completed_requirements=tuple(raw_state.get("completed_requirements", [])),
                    assumptions=tuple(raw_state.get("assumptions", [])),
                    blocking_conditions=tuple(dict.fromkeys([
                        *raw_state.get("blocking_conditions", []),
                        "evidence_invalidated",
                    ])),
                    last_verified_progress=raw_state.get("last_verified_progress"),
                    revision=int(raw_state.get("revision", 0)) + 1,
                )
                self._set_state_in_db(db, mission_id, state)
            if mission_row["status"] in {
                "VERIFIED", "AWAITING_APPROVAL", "EXECUTING"
            }:
                db.execute(
                    "UPDATE missions SET status=?, updated_at=? WHERE mission_id=?",
                    ("VERIFICATION_FAILED", time.time(), mission_id),
                )
                self._event(db, mission_id, "MISSION_REVERIFICATION_REQUIRED", {
                    "prior_status": mission_row["status"],
                    "invalidated_evidence_ids": invalidated,
                })
            elif mission_row["status"] == "ACTION_COMPLETED":
                self._event(db, mission_id, "POST_ACTION_EVIDENCE_INVALIDATED", {
                    "invalidated_evidence_ids": invalidated,
                    "requires_manual_reconciliation": True,
                })
            return tuple(invalidated)

    def record_tool_event(
        self, mission_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        if event_type not in {
            "TOOL_CALL_STARTED", "TOOL_CALL_FINISHED", "TOOL_CALL_BLOCKED"
        }:
            raise ValueError("unsupported tool event")
        with self._connect() as db:
            row = self._require(db, mission_id)
            if row["status"] != "EXECUTING":
                raise TrajectoryBlocked("tool gateway only operates during execution")
            self._event(db, mission_id, event_type, payload)

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
                if item.validity_status not in {"active", "invalid"}:
                    raise ValueError("unsupported evidence validity status")
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
            mission_row = self._require(db, mission_id)
            if mission_row["status"] != "AWAITING_APPROVAL":
                raise ApprovalRequired(
                    "mission is not in a verified approval state"
                )
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


class ToolTrajectoryGuard:
    """Synchronous pre-dispatch safety gate for instrumented read-only tools.

    This protects only tool calls made through SpecialistTask.invoke_tool.
    A host must prevent specialists from bypassing this gateway.
    """

    def __init__(
        self,
        store: SQLiteMissionStore,
        mission_id: str,
        allowed_tools: Sequence[str],
        prohibited_actions: Sequence[str],
        policy: ToolTrajectoryPolicy,
    ):
        self.store = store
        self.mission_id = mission_id
        self.allowed_tools = set(allowed_tools)
        self.prohibited_actions = set(prohibited_actions)
        self.policy = policy
        self.total_calls = 0
        self.repeats: dict[tuple[str, str], int] = {}
        self.failures: dict[str, int] = {}
        self.last_tool: str | None = None
        self.consecutive = 0
        self.blocked_reason: str | None = None

    def invoke(
        self,
        tool_name: str,
        operation_key: str,
        executor: Callable[[], Any],
        *,
        consequential: bool = False,
    ) -> Any:
        if self.blocked_reason is not None:
            raise TrajectoryBlocked(f"tool trajectory blocked: {self.blocked_reason}")
        if not tool_name or not operation_key:
            self.blocked_reason = "invalid_tool_invocation"
            self.store.record_tool_event(
                self.mission_id, "TOOL_CALL_BLOCKED",
                {"reason": self.blocked_reason},
            )
            raise TrajectoryBlocked("tool trajectory blocked: invalid_tool_invocation")
        # Store a digest, never raw tool inputs, credentials, outputs, or exceptions.
        operation_digest = hashlib.sha256(operation_key.encode()).hexdigest()
        key = (tool_name, operation_digest)
        repeats = self.repeats.get(key, 0)
        consecutive = self.consecutive + 1 if self.last_tool == tool_name else 1
        reason = None
        if consequential:
            reason = "consequential_tool_requires_human_approval"
        elif tool_name not in self.allowed_tools:
            reason = "tool_not_allowlisted"
        elif tool_name in self.prohibited_actions:
            reason = "tool_explicitly_prohibited"
        elif self.total_calls >= self.policy.max_total_calls:
            reason = "tool_call_budget_exceeded"
        elif repeats >= self.policy.max_repeats_per_operation:
            reason = "repeated_operation_loop"
        elif consecutive > self.policy.max_consecutive_same_tool:
            reason = "consecutive_tool_loop"
        elif self.failures.get(tool_name, 0) >= self.policy.max_failures_per_tool:
            reason = "repeated_tool_failures"
        payload = {"tool": tool_name, "operation_digest": operation_digest}
        if reason:
            self.blocked_reason = reason
            self.store.record_tool_event(
                self.mission_id, "TOOL_CALL_BLOCKED", {**payload, "reason": reason}
            )
            raise TrajectoryBlocked(f"tool trajectory blocked: {reason}")

        self.total_calls += 1
        self.repeats[key] = repeats + 1
        self.last_tool = tool_name
        self.consecutive = consecutive
        self.store.record_tool_event(
            self.mission_id, "TOOL_CALL_STARTED", {**payload, "attempt": repeats + 1}
        )
        try:
            result = executor()
        except Exception as exc:
            self.failures[tool_name] = self.failures.get(tool_name, 0) + 1
            self.store.record_tool_event(
                self.mission_id, "TOOL_CALL_FINISHED",
                {**payload, "outcome": "error", "error_type": type(exc).__name__},
            )
            raise
        self.store.record_tool_event(
            self.mission_id, "TOOL_CALL_FINISHED", {**payload, "outcome": "success"}
        )
        return result


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
            item.evidence_id
            for item in (*task.evidence, *result.evidence)
            if item.validity_status == "active"
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
                 verifier: Verifier | None = None,
                 trajectory_policy: ToolTrajectoryPolicy | None = None):
        self.store = store
        self.specialists = specialists
        self.verifier = verifier or ContractVerifier()
        self.trajectory_policy = trajectory_policy or ToolTrajectoryPolicy()

    @staticmethod
    def context_permission(
        request: MissionRequest,
        item: Evidence,
    ) -> tuple[str, str]:
        if item.validity_status != "active":
            return "DENY", "evidence is not active"
        if item.owner_scope is not None:
            if request.owner_scope is None:
                return "UNRESOLVED", "mission owner scope is missing"
            if item.owner_scope != request.owner_scope:
                return "DENY", "owner scope mismatch"
        if item.project_scope is not None:
            if request.project_scope is None:
                return "UNRESOLVED", "mission project scope is missing"
            if item.project_scope != request.project_scope:
                return "DENY", "project scope mismatch"
        required_tags = set(item.access_tags)
        supplied_tags = set(request.access_tags)
        if required_tags and not required_tags.issubset(supplied_tags):
            return "DENY", "required access tags are missing"
        return "ALLOW", "scope and access policy satisfied"

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
                if e.classification in {"fact", "user_input"} and e.validity_status == "active"
            ),
        ]))
        assumptions = tuple(dict.fromkeys([
            *prior.assumptions,
            *(
                e.claim
                for e in combined
                if e.classification in {"inference", "hypothesis"} and e.validity_status == "active"
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
        allowed_evidence: list[Evidence] = []
        blocked_context: list[dict[str, str]] = []
        for item in evidence:
            decision, reason = self.context_permission(request, item)
            self.store.record_context_decision(
                request.mission_id, item.evidence_id, decision, reason
            )
            if decision == "ALLOW":
                self.store.add_evidence(request.mission_id, item)
                allowed_evidence.append(item)
            else:
                blocked_context.append({
                    "evidence_id": item.evidence_id,
                    "decision": decision,
                    "reason": reason,
                })
        if blocked_context:
            self.store.transition(
                request.mission_id,
                "INTAKE",
                "FAILED",
                "CONTEXT_PERMISSION_BLOCKED",
                {"blocked": blocked_context},
            )
            raise ContextPermissionDenied(
                "mission context contains denied or unresolved evidence"
            )
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
            evidence=tuple(allowed_evidence),
            mission_state=prior_state,
            max_attempts=2,
            tool_guard=ToolTrajectoryGuard(
                self.store,
                request.mission_id,
                request.allowed_tools,
                request.prohibited_actions,
                self.trajectory_policy,
            ),
        )
        try:
            result = self.specialists[role].run(scoped)
            if scoped.tool_guard and scoped.tool_guard.blocked_reason:
                raise TrajectoryBlocked(
                    f"tool trajectory blocked: {scoped.tool_guard.blocked_reason}"
                )
        except Exception as exc:  # Never silently retry side effects.
            self.store.transition(
                request.mission_id,
                "EXECUTING",
                "FAILED",
                "TRAJECTORY_BLOCKED" if isinstance(exc, TrajectoryBlocked)
                else "SPECIALIST_FAILED",
                {"role": role, "error_type": type(exc).__name__},
            )
            if isinstance(exc, TrajectoryBlocked):
                raise
            raise MissionError(
                "specialist failed; mission recorded without automatic retry"
            ) from exc

        if result.mission_state is None:
            result = replace(
                result,
                mission_state=self._derive_state(
                    prior_state,
                    request,
                    allowed_evidence,
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

    def context_graph(self, mission_id: str):
        """Build optional Semantica context without changing mission state."""
        from semantica_context import SemanticaContext
        return SemanticaContext(self.store).build_graph(mission_id)

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
