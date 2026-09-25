import tempfile
import unittest
from pathlib import Path

from alpha_runtime import AlphaRuntime, MissionRequest, ProposedAction, SQLiteMissionStore
from shadow_decisions import Decision, ShadowIntakeSpecialist


class StubProvider:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def decide(self, message, labels):
        self.calls += 1
        return self.answer


def answer(category="new_quote", confidence=0.94, urgent=0.08):
    others = (1 - confidence) / 4
    return Decision({label: confidence if label == category else others for label in
                     ("new_quote", "scheduling", "existing_job", "billing", "other")}, urgent)


class ShadowDecisionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SQLiteMissionStore(Path(self.temp.name) / "missions.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def submit(self, response):
        provider = StubProvider(response)
        runtime = AlphaRuntime(self.store, {"INTAKE": ShadowIntakeSpecialist(provider, "Need a quote")})
        request = MissionRequest("Route intake in shadow", ["route proposed"],
                                 allowed_tools=[], prohibited_actions=["send", "route"],
                                 mission_id="shadow-1")
        return runtime, runtime.submit(request, "INTAKE"), provider

    def test_high_confidence_still_waits_for_approval_without_execution(self):
        runtime, state, provider = self.submit(answer())
        self.assertEqual(provider.calls, 1)
        self.assertEqual(state["status"], "AWAITING_APPROVAL")
        proposal = state["result"]["proposed_actions"][0]
        self.assertEqual(proposal["payload"]["category"], "new_quote")
        self.assertFalse(proposal["payload"]["review_required"])
        self.assertTrue(self.store.verify_event_chain("shadow-1"))
        self.assertFalse(any(e["event_type"] == "ACTION_EXECUTED" for e in self.store.events("shadow-1")))
        calls = []
        with self.assertRaisesRegex(ValueError, "approver identity is required"):
            runtime.approve_and_execute("shadow-1", ProposedAction(**proposal),
                                        "", lambda *_: calls.append(True))
        self.assertEqual(calls, [])

    def test_uncertainty_and_urgency_force_review(self):
        for response in (answer(confidence=0.55), answer(urgent=0.91)):
            with self.subTest(response=response):
                with tempfile.TemporaryDirectory() as directory:
                    self.store = SQLiteMissionStore(Path(directory) / "missions.sqlite3")
                    _, state, _ = self.submit(response)
                    self.assertTrue(state["result"]["proposed_actions"][0]["payload"]["review_required"])

    def test_malformed_output_fails_closed(self):
        with self.assertRaisesRegex(Exception, "specialist failed"):
            self.submit(Decision({"new_quote": 1.0}, 0.0))
        self.assertEqual(self.store.get("shadow-1")["status"], "FAILED")
        self.assertTrue(self.store.verify_event_chain("shadow-1"))


if __name__ == "__main__":
    unittest.main()
