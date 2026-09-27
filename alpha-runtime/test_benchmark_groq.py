import tempfile
import unittest
from pathlib import Path

from alpha_runtime import AlphaRuntime, MissionRequest, SQLiteMissionStore
from benchmark_groq import ShadowGroqSpecialist


class FakeGroq:
    def decide(self, message):
        return {"category": "scheduling", "urgent": True}


class GroqShadowTests(unittest.TestCase):
    def test_groq_decision_is_only_a_pending_review_action(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteMissionStore(Path(directory) / "shadow.sqlite3")
            runtime = AlphaRuntime(store, {"INTAKE": ShadowGroqSpecialist(FakeGroq(), "Pipe burst")})
            state = runtime.submit(MissionRequest("Shadow triage", ["route proposed"],
                                                  mission_id="groq-shadow"), "INTAKE")
            self.assertEqual(state["status"], "AWAITING_APPROVAL")
            self.assertEqual(state["result"]["proposed_actions"][0]["payload"],
                             {"category": "scheduling", "urgent": True, "review_required": True})
            self.assertTrue(store.verify_event_chain("groq-shadow"))
            self.assertFalse(any(event["event_type"] == "ACTION_EXECUTED"
                                 for event in store.events("groq-shadow")))


if __name__ == "__main__":
    unittest.main()
