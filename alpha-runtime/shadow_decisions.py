"""Local-only ALPHA decision shadow adapter; no network or action executor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from alpha_runtime import ProposedAction, SpecialistResult, SpecialistTask


LABELS = ("new_quote", "scheduling", "existing_job", "billing", "other")


@dataclass(frozen=True)
class Decision:
    probabilities: Mapping[str, float]
    urgent_probability: float


class DecisionProvider(Protocol):
    def decide(self, message: str, labels: tuple[str, ...]) -> Decision: ...


class ShadowIntakeSpecialist:
    """Record a proposed internal route for review, never execute a route."""

    def __init__(self, provider: DecisionProvider, message: str,
                 min_confidence: float = 0.85, urgent_threshold: float = 0.70):
        self.provider = provider
        self.message = message
        self.min_confidence = min_confidence
        self.urgent_threshold = urgent_threshold

    def run(self, task: SpecialistTask) -> SpecialistResult:
        if not self.message.strip():
            raise ValueError("empty intake")
        decision = self.provider.decide(self.message, LABELS)
        scores = decision.probabilities
        if (set(scores) != set(LABELS)
                or any(not isinstance(p, (float, int)) or not 0 <= p <= 1 for p in scores.values())
                or abs(sum(scores.values()) - 1) > 0.01
                or not isinstance(decision.urgent_probability, (float, int))
                or not 0 <= decision.urgent_probability <= 1):
            raise ValueError("invalid decision probabilities")
        category = max(LABELS, key=lambda label: scores[label])
        confidence = scores[category]
        review = confidence < self.min_confidence or decision.urgent_probability >= self.urgent_threshold
        proposed = ProposedAction(
            action_id="review-intake", kind="intake.route.proposed",
            payload={"category": category, "confidence": round(confidence, 4),
                     "urgent_probability": round(decision.urgent_probability, 4),
                     "review_required": review}, consequential=True,
        )
        return SpecialistResult(
            summary="Shadow route recorded for review; no message sent or route changed.",
            proposed_actions=(proposed,), completed_criteria=task.success_criteria,
        )
