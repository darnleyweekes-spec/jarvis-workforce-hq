import tempfile
import unittest
from pathlib import Path

from alpha_runtime import (
    AlphaRuntime, ApprovalRequired, ContractVerifier, Evidence, MissionRequest,
    ProposedAction, SpecialistResult, SQLiteMissionStore, VerificationFailed,
)


class DemoSpecialist:
    def __init__(self, action=None, omit_criteria=False):
        self.action = action
        self.omit_criteria = omit_criteria
        self.received = None

    def run(self, task):
        self.received = task
        done = () if self.omit_criteria else task.success_criteria
        return SpecialistResult("Prepared a verified draft.", completed_criteria=done,
                               proposed_actions=(self.action,) if self.action else ())


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "missions.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def request(self):
        return MissionRequest("Prepare a customer update", ["draft prepared"],
                              constraints=["Use approved incident evidence"],
                              allowed_tools=["draft_builder"],
                              prohibited_actions=["send without approval"],
                              mission_id="mission-1")

    def test_restart_event_chain_scoped_handoff_and_approval(self):
        action = ProposedAction("send-update", "email.send", {"to": "customer@example.test", "body": "Draft"})
        specialist = DemoSpecialist(action)
        runtime = AlphaRuntime(SQLiteMissionStore(self.db), {"SCRIBE": specialist})
        evidence = Evidence("ev-1", "Incident affected login", "incident-24", "2026-09-23T10:00:00Z", "fact", 300)
        state = runtime.submit(self.request(), "SCRIBE", [evidence])
        self.assertEqual(state["status"], "AWAITING_APPROVAL")
        self.assertEqual(specialist.received.evidence, (evidence,))
        self.assertEqual(specialist.received.allowed_tools, ("draft_builder",))
        self.assertNotIn("full_history", specialist.received.__dict__)

        restarted = SQLiteMissionStore(self.db)
        self.assertEqual(restarted.get("mission-1")["status"], "AWAITING_APPROVAL")
        self.assertTrue(restarted.verify_event_chain("mission-1"))
        calls = []
        result = runtime.approve_and_execute("mission-1", action, "Darnley",
                                               lambda a, key: calls.append(key) or {"accepted": True})
        self.assertEqual(result, {"accepted": True})
        self.assertEqual(len(calls), 1)
        self.assertEqual(SQLiteMissionStore(self.db).get("mission-1")["status"], "ACTION_COMPLETED")

    def test_unapproved_or_modified_action_does_not_run(self):
        action = ProposedAction("send-update", "email.send", {"to": "a@example.test"})
        runtime = AlphaRuntime(SQLiteMissionStore(self.db), {"SCRIBE": DemoSpecialist(action)})
        runtime.submit(self.request(), "SCRIBE")
        calls = []
        changed = ProposedAction("send-update", "email.send", {"to": "b@example.test"})
        with self.assertRaises(ApprovalRequired):
            runtime.approve_and_execute("mission-1", changed, "Darnley", lambda a, k: calls.append(k))
        self.assertEqual(calls, [])

    def test_verification_failure_blocks_actions(self):
        action = ProposedAction("send-update", "email.send", {"body": "draft"})
        runtime = AlphaRuntime(SQLiteMissionStore(self.db), {"SCRIBE": DemoSpecialist(action, True)}, ContractVerifier())
        with self.assertRaises(VerificationFailed):
            runtime.submit(self.request(), "SCRIBE")
        self.assertEqual(SQLiteMissionStore(self.db).get("mission-1")["status"], "VERIFICATION_FAILED")

    def test_approval_required_and_action_is_idempotent(self):
        action = ProposedAction("send-update", "email.send", {"body": "draft"})
        store = SQLiteMissionStore(self.db)
        runtime = AlphaRuntime(store, {"SCRIBE": DemoSpecialist(action)})
        runtime.submit(self.request(), "SCRIBE")
        calls = []
        executor = lambda a, key: calls.append(key) or {"sent": True}
        runtime.approve_and_execute("mission-1", action, "Darnley", executor)
        # Store-level duplicate requests return the prior result; executor not invoked again.
        repeated = store.execute_once("mission-1", action, executor)
        self.assertEqual(repeated, {"sent": True})
        self.assertEqual(len(calls), 1)

    def test_request_cannot_waive_approval_for_consequential_action(self):
        action = ProposedAction("publish", "status.publish", {"body": "Incident update"})
        request = MissionRequest("Draft update", ["draft prepared"], approval_required=False,
                                 mission_id="mission-1")
        runtime = AlphaRuntime(SQLiteMissionStore(self.db), {"SCRIBE": DemoSpecialist(action)})
        state = runtime.submit(request, "SCRIBE")
        self.assertEqual(state["status"], "AWAITING_APPROVAL")
        self.assertTrue(SQLiteMissionStore(self.db).verify_event_chain("mission-1"))

    def test_interrupted_action_fails_closed_for_manual_reconciliation(self):
        action = ProposedAction("write-config", "config.update", {"setting": "safe"})
        store = SQLiteMissionStore(self.db)
        request = self.request()
        store.create(request)
        store.transition("mission-1", "INTAKE", "PLANNED", "MISSION_PLANNED")
        store.transition("mission-1", "PLANNED", "AWAITING_APPROVAL", "APPROVAL_REQUIRED")
        store.approve("mission-1", action, "Darnley")
        with self.assertRaisesRegex(RuntimeError, "executor crashed"):
            store.execute_once("mission-1", action,
                               lambda a, key: (_ for _ in ()).throw(RuntimeError("executor crashed")))
        with self.assertRaisesRegex(Exception, "outcome is unknown"):
            store.execute_once("mission-1", action, lambda a, key: {"unexpected": True})


if __name__ == "__main__":
    unittest.main()
