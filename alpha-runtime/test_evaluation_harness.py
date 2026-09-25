import json
import tempfile
import unittest
from pathlib import Path

from alpha_runtime import (
    AlphaRuntime, Evidence, MissionRequest, ProposedAction, SpecialistResult,
    SQLiteMissionStore, VerificationFailed,
)
from evaluation_harness import AlphaEvaluationHarness, ReliabilityGate


class SuccessSpecialist:
    def __init__(self, action=None):
        self.action = action

    def run(self, task):
        return SpecialistResult(
            "done",
            completed_criteria=task.success_criteria,
            proposed_actions=(self.action,) if self.action else (),
        )


class FailingVerificationSpecialist:
    def run(self, task):
        return SpecialistResult("incomplete", completed_criteria=())


class EvaluationHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "missions.sqlite3")
        self.store = SQLiteMissionStore(self.db)
        self.harness = AlphaEvaluationHarness(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def request(self, mission_id):
        return MissionRequest(
            "Prepare update",
            ["draft prepared"],
            allowed_tools=["draft_builder"],
            mission_id=mission_id,
        )

    def test_snapshot_is_exportable_and_chain_verified(self):
        evidence = Evidence(
            "ev-1", "Login affected", "incident-24", "2026-09-25T10:00:00Z", "fact"
        )
        runtime = AlphaRuntime(self.store, {"SCRIBE": SuccessSpecialist()})
        runtime.submit(self.request("m1"), "SCRIBE", [evidence])

        snap = self.harness.snapshot("m1")
        self.assertTrue(snap.event_chain_valid)
        self.assertEqual(snap.status, "VERIFIED")
        self.assertEqual(len(snap.trajectory_digest), 64)
        exported = json.loads(self.harness.export_snapshot("m1"))
        self.assertEqual(exported["mission_id"], "m1")
        self.assertTrue(exported["event_chain_valid"])

    def test_evaluation_and_gate_for_verified_mission(self):
        runtime = AlphaRuntime(self.store, {"SCRIBE": SuccessSpecialist()})
        runtime.submit(self.request("m1"), "SCRIBE")
        evaluation = self.harness.evaluate("m1")

        self.assertTrue(evaluation.mission_success)
        self.assertTrue(evaluation.terminal_success)
        self.assertTrue(evaluation.event_chain_valid)
        self.assertEqual(evaluation.score, 1.0)
        allowed, reasons = ReliabilityGate().decide(evaluation)
        self.assertTrue(allowed)
        self.assertEqual(reasons, ())
        self.assertIn("tool_selection_accuracy", evaluation.unsupported_metrics)

    def test_awaiting_approval_is_not_terminal_success(self):
        action = ProposedAction("send", "email.send", {"body": "draft"})
        runtime = AlphaRuntime(self.store, {"SCRIBE": SuccessSpecialist(action)})
        runtime.submit(self.request("m1"), "SCRIBE")
        evaluation = self.harness.evaluate("m1")

        self.assertTrue(evaluation.mission_success)
        self.assertFalse(evaluation.terminal_success)
        self.assertTrue(evaluation.approval_required)
        self.assertFalse(evaluation.action_completed)
        self.assertIn("awaiting_human_action", evaluation.failure_labels)

    def test_verification_failure_is_retained_by_regression_selection(self):
        good = AlphaRuntime(self.store, {"GOOD": SuccessSpecialist()})
        good.submit(self.request("good-1"), "GOOD")
        good.submit(self.request("good-2"), "GOOD")

        bad = AlphaRuntime(self.store, {"BAD": FailingVerificationSpecialist()})
        with self.assertRaises(VerificationFailed):
            bad.submit(self.request("bad-1"), "BAD")

        selected = self.harness.regression_subset(["good-1", "bad-1", "good-2"], 2)
        self.assertIn("bad-1", selected)

    def test_compare_reports_supported_metric_deltas(self):
        runtime = AlphaRuntime(self.store, {"SCRIBE": SuccessSpecialist()})
        runtime.submit(self.request("baseline"), "SCRIBE")
        runtime.submit(self.request("candidate"), "SCRIBE")

        comparison = self.harness.compare(["baseline"], ["candidate"])
        self.assertEqual(comparison["baseline"]["mission_success_rate"], 1.0)
        self.assertEqual(comparison["candidate"]["mission_success_rate"], 1.0)
        self.assertEqual(comparison["delta"]["mission_success_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
