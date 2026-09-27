"""Groq structured-output intake smoke benchmark in ALPHA shadow mode.

Requires GROQ_API_KEY. No messages or routing actions are executed.
Groq outputs categories and booleans, not calibrated probabilities.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from alpha_runtime import AlphaRuntime, MissionRequest, ProposedAction, SpecialistResult, SQLiteMissionStore
from benchmark_jev import CASES
from shadow_decisions import LABELS


MODEL = "openai/gpt-oss-20b"
INPUT_PRICE_PER_M = 0.075
OUTPUT_PRICE_PER_M = 0.30


class GroqProvider:
    def __init__(self, key):
        self.key = key
        self.latencies_ms = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.models = set()

    def decide(self, message):
        schema = {
            "type": "object", "properties": {
                "category": {"type": "string", "enum": list(LABELS)},
                "urgent": {"type": "boolean"},
            }, "required": ["category", "urgent"], "additionalProperties": False,
        }
        payload = json.dumps({
            "model": MODEL, "temperature": 0, "max_completion_tokens": 120,
            "messages": [
                {"role": "system", "content":
                 "Classify the main customer request. new_quote asks for a price for new work; "
                 "scheduling asks for a visit or appointment; existing_job asks about work "
                 "already underway; billing asks about charges or receipts; other is unrelated. "
                 "Set urgent true for immediate harm, active disruption, or a time-critical "
                 "missed appointment. Output only the requested fields."},
                {"role": "user", "content": message},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "intake_route", "strict": True, "schema": schema}},
        }).encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions", data=payload,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Groq HTTP {exc.code}; benchmark stopped") from None
        elapsed = (time.perf_counter() - start) * 1000
        choice = data["choices"][0]["message"]
        if choice.get("refusal") or not choice.get("content"):
            raise ValueError("model refused or returned empty content")
        result = json.loads(choice["content"])
        if (set(result) != {"category", "urgent"} or result["category"] not in LABELS
                or type(result["urgent"]) is not bool):
            raise ValueError("unexpected structured decision")
        self.latencies_ms.append(elapsed)
        self.models.add(data.get("model", "unknown"))
        self.input_tokens += data.get("usage", {}).get("prompt_tokens", 0)
        self.output_tokens += data.get("usage", {}).get("completion_tokens", 0)
        return result


class ShadowGroqSpecialist:
    def __init__(self, provider, message):
        self.provider = provider
        self.message = message

    def run(self, task):
        decision = self.provider.decide(self.message)
        return SpecialistResult(
            "Proposed shadow classification; manual review required because probabilities are unavailable.",
            proposed_actions=(ProposedAction(
                "review-intake", "intake.route.proposed",
                {"category": decision["category"], "urgent": decision["urgent"],
                 "review_required": True}, consequential=True),),
            completed_criteria=task.success_criteria,
        )


def run():
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise SystemExit("GROQ_API_KEY is required; no Groq calls were made")
    provider = GroqProvider(key)
    correct = missed_urgent = false_urgent = 0
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        store = SQLiteMissionStore(Path(directory) / "missions.sqlite3")
        for i, (message, category, urgent) in enumerate(CASES):
            runtime = AlphaRuntime(store, {"INTAKE": ShadowGroqSpecialist(provider, message)})
            request = MissionRequest("Shadow intake decision", ["route proposed"],
                                     prohibited_actions=["send", "route"], mission_id=f"groq-{i}")
            state = runtime.submit(request, "INTAKE")
            assert state["status"] == "AWAITING_APPROVAL"
            assert store.verify_event_chain(request.mission_id)
            prediction = state["result"]["proposed_actions"][0]["payload"]
            assert prediction["review_required"] is True
            correct += prediction["category"] == category
            missed_urgent += urgent and not prediction["urgent"]
            false_urgent += not urgent and prediction["urgent"]
    timings = sorted(provider.latencies_ms)
    return {
        "scope": "10 synthetic examples, serial calls, all routes pending manual review",
        "models": sorted(provider.models), "calls": len(timings),
        "category_correct": correct, "urgent_cases": sum(case[2] for case in CASES),
        "urgent_misses": missed_urgent, "false_urgent": false_urgent,
        "p50_api_ms": statistics.median(timings),
        "p95_api_ms": timings[math.ceil(len(timings) * .95) - 1],
        "end_to_end_total_ms": (time.perf_counter() - start) * 1000,
        "input_tokens": provider.input_tokens, "output_tokens": provider.output_tokens,
        "estimated_cost_usd": (provider.input_tokens * INPUT_PRICE_PER_M +
                               provider.output_tokens * OUTPUT_PRICE_PER_M) / 1_000_000,
        "calibrated_confidence": None,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
