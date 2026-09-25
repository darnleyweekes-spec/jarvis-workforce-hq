"""Evaluation and regression harness for the ALPHA mission runtime.

The harness intentionally evaluates only facts recorded by SQLiteMissionStore.
Unsupported metrics (for example generic tool-call accuracy) are not inferred.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

from alpha_runtime import SQLiteMissionStore


PASSING_STATUSES = {"VERIFIED", "AWAITING_APPROVAL", "ACTION_COMPLETED"}
TERMINAL_SUCCESS_STATUSES = {"VERIFIED", "ACTION_COMPLETED"}
FAILURE_STATUSES = {"FAILED", "VERIFICATION_FAILED"}


@dataclass(frozen=True)
class TrajectorySnapshot:
    mission_id: str
    status: str
    request: dict[str, Any]
    evidence: tuple[dict[str, Any], ...]
    verification: dict[str, Any] | None
    result: dict[str, Any] | None
    events: tuple[dict[str, Any], ...]
    event_chain_valid: bool
    trajectory_digest: str


@dataclass(frozen=True)
class MissionEvaluation:
    mission_id: str
    status: str
    mission_success: bool
    terminal_success: bool
    verification_passed: bool | None
    event_chain_valid: bool
    context_provenance_passed: bool
    approval_required: bool
    action_completed: bool
    failed: bool
    score: float
    failure_labels: tuple[str, ...]
    unsupported_metrics: tuple[str, ...] = (
        "tool_selection_accuracy",
        "human_override_rate",
        "cost_per_verified_mission",
    )


@dataclass(frozen=True)
class ReliabilityGate:
    min_score: float = 0.80
    require_valid_event_chain: bool = True
    require_context_provenance: bool = True
    require_verification_if_present: bool = True

    def decide(self, evaluation: MissionEvaluation) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if evaluation.score < self.min_score:
            reasons.append(f"score {evaluation.score:.2f} below {self.min_score:.2f}")
        if self.require_valid_event_chain and not evaluation.event_chain_valid:
            reasons.append("event chain invalid")
        if self.require_context_provenance and not evaluation.context_provenance_passed:
            reasons.append("context provenance incomplete")
        if (self.require_verification_if_present and
                evaluation.verification_passed is False):
            reasons.append("verification failed")
        return not reasons, tuple(reasons)


class AlphaEvaluationHarness:
    """Builds replayable snapshots, scores missions, and selects regression cases."""

    def __init__(self, store: SQLiteMissionStore):
        self.store = store

    def snapshot(self, mission_id: str) -> TrajectorySnapshot:
        state = self.store.get(mission_id)
        raw_events = self.store.events(mission_id)
        events = tuple(self._stable_event(event) for event in raw_events)
        body = {
            "mission_id": mission_id,
            "status": state["status"],
            "request": state["request"],
            "evidence": state["evidence"],
            "verification": state["verification"],
            "result": state["result"],
            "events": events,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return TrajectorySnapshot(
            mission_id=mission_id,
            status=state["status"],
            request=state["request"],
            evidence=tuple(state["evidence"]),
            verification=state["verification"],
            result=state["result"],
            events=events,
            event_chain_valid=self.store.verify_event_chain(mission_id),
            trajectory_digest=digest,
        )

    def export_snapshot(self, mission_id: str) -> str:
        """Return a deterministic JSON artifact suitable for a regression corpus."""
        return json.dumps(asdict(self.snapshot(mission_id)), sort_keys=True, indent=2)

    def evaluate(self, mission_id: str) -> MissionEvaluation:
        snap = self.snapshot(mission_id)
        verification_passed = (
            bool(snap.verification.get("passed")) if snap.verification is not None else None
        )
        evidence_ok = all(
            bool(item.get("source"))
            and bool(item.get("retrieved_at"))
            and item.get("classification") in {"fact", "inference", "hypothesis", "user_input"}
            for item in snap.evidence
        )
        # Empty evidence is valid: not every mission requires external evidence.
        context_provenance_passed = evidence_ok
        approval_required = any(e["event_type"] == "APPROVAL_REQUIRED" for e in snap.events)
        action_completed = any(
            e["event_type"] == "MISSION_ACTION_COMPLETED" for e in snap.events
        )
        failed = snap.status in FAILURE_STATUSES
        mission_success = snap.status in PASSING_STATUSES and verification_passed is not False
        terminal_success = snap.status in TERMINAL_SUCCESS_STATUSES and verification_passed is not False

        checks = [
            snap.event_chain_valid,
            context_provenance_passed,
            verification_passed is not False,
            not failed,
            mission_success,
        ]
        score = sum(1.0 for check in checks if check) / len(checks)

        labels: list[str] = []
        if not snap.event_chain_valid:
            labels.append("event_chain")
        if not context_provenance_passed:
            labels.append("context_provenance")
        if verification_passed is False:
            labels.append("verification")
        if snap.status == "FAILED":
            labels.append("specialist_failure")
        if snap.status == "VERIFICATION_FAILED":
            labels.append("verification_block")
        if approval_required and not action_completed:
            labels.append("awaiting_human_action")

        return MissionEvaluation(
            mission_id=mission_id,
            status=snap.status,
            mission_success=mission_success,
            terminal_success=terminal_success,
            verification_passed=verification_passed,
            event_chain_valid=snap.event_chain_valid,
            context_provenance_passed=context_provenance_passed,
            approval_required=approval_required,
            action_completed=action_completed,
            failed=failed,
            score=score,
            failure_labels=tuple(labels),
        )

    def regression_subset(self, mission_ids: Sequence[str], limit: int) -> list[str]:
        """Select a deterministic, behavior-diverse regression subset.

        Severe/failed cases are retained first. Remaining slots use greedy
        farthest-point selection over recorded trajectory features. This gives
        ALPHA a dependency-free baseline until embedding-backed selection is
        justified by enough mission volume.
        """
        if limit <= 0:
            return []
        unique_ids = list(dict.fromkeys(mission_ids))
        if len(unique_ids) <= limit:
            return unique_ids

        evaluations = {mid: self.evaluate(mid) for mid in unique_ids}
        signatures = {mid: self._signature(self.snapshot(mid)) for mid in unique_ids}
        failures = sorted(
            (mid for mid in unique_ids if evaluations[mid].failed or evaluations[mid].score < 0.8),
            key=lambda mid: (evaluations[mid].score, mid),
        )
        chosen = failures[:limit]
        if len(chosen) >= limit:
            return chosen

        candidates = [mid for mid in unique_ids if mid not in chosen]
        if not chosen and candidates:
            # Seed deterministically with the richest trajectory.
            seed = max(candidates, key=lambda mid: (len(signatures[mid]), mid))
            chosen.append(seed)
            candidates.remove(seed)

        while candidates and len(chosen) < limit:
            next_id = max(
                candidates,
                key=lambda mid: (
                    min(self._jaccard_distance(signatures[mid], signatures[c]) for c in chosen),
                    len(signatures[mid]),
                    mid,
                ),
            )
            chosen.append(next_id)
            candidates.remove(next_id)
        return chosen

    def compare(self, baseline_ids: Iterable[str], candidate_ids: Iterable[str]) -> dict[str, Any]:
        """Compare two mission sets using only supported recorded metrics."""
        baseline = [self.evaluate(mid) for mid in baseline_ids]
        candidate = [self.evaluate(mid) for mid in candidate_ids]
        return {
            "baseline": self._aggregate(baseline),
            "candidate": self._aggregate(candidate),
            "delta": self._delta(self._aggregate(baseline), self._aggregate(candidate)),
        }

    @staticmethod
    def _stable_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "seq": event["seq"],
            "event_type": event["event_type"],
            "payload": event["payload"],
            "created_at": event["created_at"],
            "prev_hash": event["prev_hash"],
            "event_hash": event["event_hash"],
        }

    @staticmethod
    def _signature(snapshot: TrajectorySnapshot) -> frozenset[str]:
        features = {f"status:{snapshot.status}"}
        features.update(f"event:{event['event_type']}" for event in snapshot.events)
        if snapshot.verification:
            for check in snapshot.verification.get("checks", []):
                features.add(f"check:{check.get('name')}:{bool(check.get('passed'))}")
        features.update(
            f"evidence:{item.get('classification')}" for item in snapshot.evidence
        )
        return frozenset(features)

    @staticmethod
    def _jaccard_distance(left: frozenset[str], right: frozenset[str]) -> float:
        union = left | right
        if not union:
            return 0.0
        return 1.0 - (len(left & right) / len(union))

    @staticmethod
    def _aggregate(items: Sequence[MissionEvaluation]) -> dict[str, Any]:
        count = len(items)
        if not count:
            return {"count": 0, "mean_score": None, "mission_success_rate": None,
                    "terminal_success_rate": None, "chain_integrity_rate": None,
                    "context_provenance_rate": None, "verification_pass_rate": None}
        verified = [i for i in items if i.verification_passed is not None]
        return {
            "count": count,
            "mean_score": sum(i.score for i in items) / count,
            "mission_success_rate": sum(i.mission_success for i in items) / count,
            "terminal_success_rate": sum(i.terminal_success for i in items) / count,
            "chain_integrity_rate": sum(i.event_chain_valid for i in items) / count,
            "context_provenance_rate": sum(i.context_provenance_passed for i in items) / count,
            "verification_pass_rate": (
                sum(bool(i.verification_passed) for i in verified) / len(verified)
                if verified else None
            ),
        }

    @staticmethod
    def _delta(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, float | None]:
        result: dict[str, float | None] = {}
        for key in ("mean_score", "mission_success_rate", "terminal_success_rate",
                    "chain_integrity_rate", "context_provenance_rate", "verification_pass_rate"):
            left, right = baseline.get(key), candidate.get(key)
            result[key] = None if left is None or right is None else right - left
        return result
