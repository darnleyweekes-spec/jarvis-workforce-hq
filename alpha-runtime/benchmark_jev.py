"""Run a small, synthetic Jev intake benchmark through ALPHA's shadow adapter.

Requires TYPESAFE_API_KEY. No email, CRM, Sites, or routing action is called.
Output is aggregate metrics only; raw prompts and credentials are never logged.
"""

from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from alpha_runtime import AlphaRuntime, MissionRequest, SQLiteMissionStore
from shadow_decisions import Decision, ShadowIntakeSpecialist


CASES = (
    ("Could you quote a new heat pump installation for my home in Portland?", "new_quote", False),
    ("The furnace stopped working and the house is freezing. Can someone come today?", "scheduling", True),
    ("Please move my cleaning appointment from Tuesday to Thursday.", "scheduling", False),
    ("What is the status of the plumbing repair you started yesterday?", "existing_job", False),
    ("The invoice shows a second charge for the same visit. Please review it.", "billing", False),
    ("The pipe burst and water is entering the electrical panel. Need help now.", "scheduling", True),
    ("We need a recurring quote for commercial cleaning at our office.", "new_quote", False),
    ("Where is the technician? They were due an hour ago.", "existing_job", True),
    ("I need a copy of the receipt for last month's service.", "billing", False),
    ("We sell website SEO packages. Would you like a free consultation?", "other", False),
)


class JevProvider:
    def __init__(self, key: str):
        self.key = key
        self.latencies_ms = []
        self.input_tokens = 0
        self.model_versions = set()

    def decide(self, message: str, labels: tuple[str, ...]) -> Decision:
        criteria = {
            "new_quote": "Asks for a price or quote for new work",
            "scheduling": "Requests a visit, appointment, dispatch, or rescheduling",
            "existing_job": "Asks about work already started or a technician's arrival",
            "billing": "Asks about an invoice, charge, receipt, or payment",
            "other": "Not a customer service request in these categories",
        }
        if set(criteria) != set(labels):
            raise ValueError("unexpected labels")
        payload = json.dumps({
            "state": message, "model": "jev-latest",
            "questions": {
                "category": {"type": "choice", "instructions": "Which single category best describes the customer's main request?",
                             "criteria": criteria},
                "urgent": {"type": "noul", "instructions": "This customer request needs prompt human attention due to immediate harm, active disruption, or a time-critical missed appointment."},
            },
        }).encode()
        request = urllib.request.Request(
            "https://api.typesafe.ai/v1/systemone", data=payload,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Jev HTTP {exc.code}; benchmark stopped") from None
        elapsed = (time.perf_counter() - start) * 1000
        answers = data["answers"]
        category = answers["category"]
        scores = category["probabilities"]
        if category["type"] != "choice" or answers["urgent"]["type"] != "noul":
            raise ValueError("unexpected Jev response types")
        if category["choice"] not in labels:
            raise ValueError("unexpected category")
        result = Decision(scores, answers["urgent"]["noul"])
        self.latencies_ms.append(elapsed)
        self.input_tokens += data.get("usage", {}).get("input_tokens", 0)
        self.model_versions.add(data.get("model", "unknown"))
        return result


def run() -> dict:
    key = os.getenv("TYPESAFE_API_KEY")
    if not key:
        raise SystemExit("TYPESAFE_API_KEY is required; no Jev calls were made")
    provider = JevProvider(key)
    correct_category = urgent_misses = false_urgent = review_count = 0
    total_start = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        store = SQLiteMissionStore(Path(directory) / "shadow.sqlite3")
        for index, (message, category, urgent) in enumerate(CASES):
            runtime = AlphaRuntime(store, {"INTAKE": ShadowIntakeSpecialist(provider, message)})
            request = MissionRequest("Classify synthetic intake in shadow", ["route proposed"],
                                     prohibited_actions=["send", "route"], mission_id=f"jev-shadow-{index}")
            state = runtime.submit(request, "INTAKE")
            assert state["status"] == "AWAITING_APPROVAL"
            assert store.verify_event_chain(request.mission_id)
            prediction = state["result"]["proposed_actions"][0]["payload"]
            correct_category += prediction["category"] == category
            predicts_urgent = prediction["urgent_probability"] >= 0.70
            urgent_misses += urgent and not predicts_urgent
            false_urgent += not urgent and predicts_urgent
            review_count += prediction["review_required"]
    times = sorted(provider.latencies_ms)
    return {
        "scope": "10 synthetic examples, sequential calls; no production traffic",
        "model_versions": sorted(provider.model_versions), "calls": len(times),
        "category_correct": correct_category, "urgent_cases": sum(c[2] for c in CASES),
        "urgent_misses": urgent_misses, "false_urgent": false_urgent,
        "review_count": review_count, "p50_api_ms": statistics.median(times),
        "p95_api_ms": times[min(len(times)-1, int(0.95 * len(times) + 0.999999)-1)],
        "end_to_end_total_ms": (time.perf_counter() - total_start) * 1000,
        "input_tokens": provider.input_tokens,
        "estimated_input_cost_usd": provider.input_tokens * 0.042 / 1_000_000,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
