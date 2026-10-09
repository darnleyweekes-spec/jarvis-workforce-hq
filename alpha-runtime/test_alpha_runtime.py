import tempfile
import unittest
from pathlib import Path

from alpha_runtime import (
    AlphaRuntime, ApprovalRequired, ClaimEvidenceContract, ContextPermissionDenied,
    ContractVerifier, Evidence, MissionRequest, MissionState, ProposedAction,
    SpecialistResult, SQLiteMissionStore, ToolTrajectoryPolicy, TrajectoryBlocked,
    VerificationFailed,
)


class DemoSpecialist:
    def __init__(self, action=None, omit_criteria=False, omit_contract=False):
        self.action = action
        self.omit_criteria = omit_criteria
        self.omit_contract = omit_contract
        self.received = None

    def run(self, task):
        self.received = task
        done = () if self.omit_criteria else task.success_criteria
        contracts = () if self.omit_contract else tuple(
            ClaimEvidenceContract(
                criterion=criterion,
                status="verified",
                verification_method="artifact:specialist_result",
            )
            for criterion in done
        )
        return SpecialistResult(
            "Prepared a verified draft.",
            completed_criteria=done,
            proposed_actions=(self.action,) if self.action else (),
            claim_evidence=contracts,
        )


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "missions.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def request(self):
        return MissionRequest(
            "Prepare a customer update",
            ["draft prepared"],
            constraints=["Use approved incident evidence"],
            allowed_tools=["draft_builder"],
            prohibited_actions=["send without approval"],
            mission_id="mission-1",
        )

    def test_restart_event_chain_scoped_handoff_and_approval(self):
        action = ProposedAction(
            "send-update", "email.send",
            {"to": "customer@example.test", "body": "Draft"},
        )
        specialist = DemoSpecialist(action)
        runtime = AlphaRuntime(SQLiteMissionStore(self.db), {"SCRIBE": specialist})
        evidence = Evidence(
            "ev-1", "Incident affected login", "incident-24",
            "2026-09-23T10:00:00Z", "fact", 300,
        )
        state = runtime.submit(self.request(), "SCRIBE", [evidence])
        self.assertEqual(state["status"], "AWAITING_APPROVAL")
        self.assertEqual(specialist.received.evidence, (evidence,))
        self.assertEqual(specialist.received.allowed_tools, ("draft_builder",))
        self.assertEqual(
            specialist.received.mission_state.unresolved_requirements,
            ("draft prepared",),
        )
        self.assertEqual(state["mission_state"]["completed_requirements"], ["draft prepared"])
        self.assertNotIn("full_history", specialist.received.__dict__)

        restarted = SQLiteMissionStore(self.db)
        self.assertEqual(restarted.get("mission-1")["status"], "AWAITING_APPROVAL")
        self.assertTrue(restarted.verify_event_chain("mission-1"))
        calls = []
        result = runtime.approve_and_execute(
            "mission-1", action, "Darnley",
            lambda a, key: calls.append(key) or {"accepted": True},
        )
        self.assertEqual(result, {"accepted": True})
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            SQLiteMissionStore(self.db).get("mission-1")["status"],
            "ACTION_COMPLETED",
        )

    def test_unapproved_or_modified_action_does_not_run(self):
        action = ProposedAction("send-update", "email.send", {"to": "a@example.test"})
        runtime = AlphaRuntime(SQLiteMissionStore(self.db), {"SCRIBE": DemoSpecialist(action)})
        runtime.submit(self.request(), "SCRIBE")
        calls = []
        changed = ProposedAction("send-update", "email.send", {"to": "b@example.test"})
        with self.assertRaises(ApprovalRequired):
            runtime.approve_and_execute(
                "mission-1", changed, "Darnley", lambda a, k: calls.append(k)
            )
        self.assertEqual(calls, [])

    def test_verification_failure_blocks_actions(self):
        action = ProposedAction("send-update", "email.send", {"body": "draft"})
        runtime = AlphaRuntime(
            SQLiteMissionStore(self.db),
            {"SCRIBE": DemoSpecialist(action, True)},
            ContractVerifier(),
        )
        with self.assertRaises(VerificationFailed):
            runtime.submit(self.request(), "SCRIBE")
        self.assertEqual(
            SQLiteMissionStore(self.db).get("mission-1")["status"],
            "VERIFICATION_FAILED",
        )

    def test_false_success_claim_without_evidence_contract_is_blocked(self):
        runtime = AlphaRuntime(
            SQLiteMissionStore(self.db),
            {"SCRIBE": DemoSpecialist(omit_contract=True)},
        )
        with self.assertRaises(VerificationFailed):
            runtime.submit(self.request(), "SCRIBE")
        verification = SQLiteMissionStore(self.db).get("mission-1")["verification"]
        evidence_check = next(
            check for check in verification["checks"]
            if check["name"] == "claim_evidence_contract"
        )
        self.assertFalse(evidence_check["passed"])
        self.assertEqual(evidence_check["missing_contracts"], ["draft prepared"])

    def test_approval_required_and_action_is_idempotent(self):
        action = ProposedAction("send-update", "email.send", {"body": "draft"})
        store = SQLiteMissionStore(self.db)
        runtime = AlphaRuntime(store, {"SCRIBE": DemoSpecialist(action)})
        runtime.submit(self.request(), "SCRIBE")
        calls = []
        executor = lambda a, key: calls.append(key) or {"sent": True}
        runtime.approve_and_execute("mission-1", action, "Darnley", executor)
        repeated = store.execute_once("mission-1", action, executor)
        self.assertEqual(repeated, {"sent": True})
        self.assertEqual(len(calls), 1)

    def test_request_cannot_waive_approval_for_consequential_action(self):
        action = ProposedAction("publish", "status.publish", {"body": "Incident update"})
        request = MissionRequest(
            "Draft update", ["draft prepared"], approval_required=False,
            mission_id="mission-1",
        )
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
        store.transition(
            "mission-1", "PLANNED", "AWAITING_APPROVAL", "APPROVAL_REQUIRED"
        )
        store.approve("mission-1", action, "Darnley")
        with self.assertRaisesRegex(RuntimeError, "executor crashed"):
            store.execute_once(
                "mission-1", action,
                lambda a, key: (_ for _ in ()).throw(RuntimeError("executor crashed")),
            )
        with self.assertRaisesRegex(Exception, "outcome is unknown"):
            store.execute_once(
                "mission-1", action, lambda a, key: {"unexpected": True}
            )

    def test_mission_state_detects_repeated_no_progress(self):
        store = SQLiteMissionStore(self.db)
        store.create(self.request())
        state = MissionState(
            unresolved_requirements=("draft prepared",),
            revision=1,
        )
        progressed, count = store.set_mission_state("mission-1", state)
        self.assertFalse(progressed)
        self.assertEqual(count, 1)
        progressed, count = store.set_mission_state(
            "mission-1",
            MissionState(unresolved_requirements=("draft prepared",), revision=2),
        )
        self.assertFalse(progressed)
        self.assertEqual(count, 2)
        self.assertTrue(store.is_stalled("mission-1", threshold=2))


    def test_context_permission_blocks_cross_project_evidence(self):
        request = MissionRequest(
            "Prepare a customer update",
            ["draft prepared"],
            owner_scope="prime24ai",
            project_scope="agents",
            access_tags=["customer_ops"],
            mission_id="mission-1",
        )
        foreign = Evidence(
            "foreign-1",
            "Secret from another project",
            "project-db",
            "2026-10-09T10:00:00Z",
            "fact",
            owner_scope="prime24ai",
            project_scope="mediamatch",
            access_tags=("customer_ops",),
        )
        store = SQLiteMissionStore(self.db)
        runtime = AlphaRuntime(store, {"SCRIBE": DemoSpecialist()})
        with self.assertRaises(ContextPermissionDenied):
            runtime.submit(request, "SCRIBE", [foreign])
        state = store.get("mission-1")
        self.assertEqual(state["status"], "FAILED")
        self.assertEqual(state["evidence"], [])
        decisions = [
            event for event in store.events("mission-1")
            if event["event_type"] == "CONTEXT_PERMISSION_DECISION"
        ]
        self.assertEqual(decisions[-1]["payload"]["decision"], "DENY")

    def test_context_permission_fails_closed_when_scope_is_unresolved(self):
        request = MissionRequest(
            "Prepare a customer update",
            ["draft prepared"],
            mission_id="mission-1",
        )
        scoped = Evidence(
            "scoped-1",
            "Scoped fact",
            "project-db",
            "2026-10-09T10:00:00Z",
            "fact",
            project_scope="agents",
        )
        runtime = AlphaRuntime(SQLiteMissionStore(self.db), {"SCRIBE": DemoSpecialist()})
        with self.assertRaises(ContextPermissionDenied):
            runtime.submit(request, "SCRIBE", [scoped])

    def test_provenance_invalidation_cascades_to_dependents_and_state(self):
        request = MissionRequest(
            "Prepare a customer update",
            ["draft prepared"],
            owner_scope="prime24ai",
            project_scope="agents",
            access_tags=["ops"],
            mission_id="mission-1",
        )
        base = Evidence(
            "ev-base",
            "Login is degraded",
            "monitor",
            "2026-10-09T10:00:00Z",
            "fact",
            owner_scope="prime24ai",
            project_scope="agents",
            access_tags=("ops",),
        )
        derived = Evidence(
            "ev-derived",
            "Customer impact is elevated",
            "analysis",
            "2026-10-09T10:01:00Z",
            "fact",
            owner_scope="prime24ai",
            project_scope="agents",
            access_tags=("ops",),
            depends_on=("ev-base",),
        )
        store = SQLiteMissionStore(self.db)
        runtime = AlphaRuntime(store, {"SCRIBE": DemoSpecialist()})
        runtime.submit(request, "SCRIBE", [base, derived])
        invalidated = store.invalidate_evidence(
            "mission-1", "ev-base", "monitoring source corrected"
        )
        self.assertEqual(invalidated, ("ev-base", "ev-derived"))
        state = store.get("mission-1")
        self.assertNotIn("Login is degraded", state["mission_state"]["known_facts"])
        self.assertNotIn(
            "Customer impact is elevated", state["mission_state"]["known_facts"]
        )
        self.assertIn(
            "evidence_invalidated", state["mission_state"]["blocking_conditions"]
        )
        invalidation_events = [
            event for event in store.events("mission-1")
            if event["event_type"] == "EVIDENCE_INVALIDATED"
        ]
        self.assertEqual(len(invalidation_events), 2)


    def test_instrumented_tool_calls_are_audited_without_leaking_arguments(self):
        class Reader(DemoSpecialist):
            def run(self, task):
                self.received = task.invoke_tool(
                    "draft_builder", "sensitive customer input", lambda: "ok"
                )
                return super().run(task)

        store = SQLiteMissionStore(self.db)
        specialist = Reader()
        runtime = AlphaRuntime(store, {"SCRIBE": specialist})
        state = runtime.submit(self.request(), "SCRIBE")
        self.assertEqual(state["status"], "VERIFIED")
        self.assertEqual(specialist.received.allowed_tools, ("draft_builder",))
        tool_events = [
            event for event in store.events("mission-1")
            if event["event_type"].startswith("TOOL_CALL_")
        ]
        self.assertEqual(
            [e["event_type"] for e in tool_events],
            ["TOOL_CALL_STARTED", "TOOL_CALL_FINISHED"],
        )
        self.assertNotIn("sensitive customer input", str(tool_events))
        self.assertTrue(store.verify_event_chain("mission-1"))

    def test_repeated_operation_is_blocked_before_dispatch(self):
        calls = []
        class Looper(DemoSpecialist):
            def run(self, task):
                for _ in range(4):
                    task.invoke_tool(
                        "draft_builder", "same-request", lambda: calls.append(1)
                    )
                return super().run(task)

        store = SQLiteMissionStore(self.db)
        runtime = AlphaRuntime(
            store, {"SCRIBE": Looper()},
            trajectory_policy=ToolTrajectoryPolicy(max_repeats_per_operation=2),
        )
        with self.assertRaises(TrajectoryBlocked):
            runtime.submit(self.request(), "SCRIBE")
        self.assertEqual(len(calls), 2)
        self.assertEqual(store.get("mission-1")["status"], "FAILED")
        self.assertTrue(store.verify_event_chain("mission-1"))
        self.assertIn(
            "TRAJECTORY_BLOCKED",
            [e["event_type"] for e in store.events("mission-1")],
        )

    def test_disallowed_and_consequential_calls_never_dispatch(self):
        for kind in ("disallowed", "consequential"):
            with self.subTest(kind=kind):
                path = Path(self.temp.name) / (kind + ".sqlite")
                calls = []
                class Unsafe(DemoSpecialist):
                    def run(self, task):
                        task.invoke_tool(
                            "unknown" if kind == "disallowed" else "draft_builder",
                            "operation", lambda: calls.append(1),
                            consequential=(kind == "consequential"),
                        )
                        return super().run(task)
                runtime = AlphaRuntime(
                    SQLiteMissionStore(path), {"SCRIBE": Unsafe()}
                )
                with self.assertRaises(TrajectoryBlocked):
                    runtime.submit(self.request(), "SCRIBE")
                self.assertEqual(calls, [])

    def test_swallowed_trajectory_block_still_fails_mission(self):
        class Swallow(DemoSpecialist):
            def run(self, task):
                try:
                    task.invoke_tool("unknown", "operation", lambda: None)
                except TrajectoryBlocked:
                    pass
                return super().run(task)
        store = SQLiteMissionStore(self.db)
        with self.assertRaises(TrajectoryBlocked):
            AlphaRuntime(store, {"SCRIBE": Swallow()}).submit(
                self.request(), "SCRIBE"
            )
        self.assertEqual(store.get("mission-1")["status"], "FAILED")
        self.assertIsNone(store.get("mission-1")["verification"])

    def test_failure_streak_and_budget_limits(self):
        class CatchingReader(DemoSpecialist):
            def run(self, task):
                for i in range(3):
                    try:
                        task.invoke_tool(
                            "draft_builder", f"failed-{i}",
                            lambda: (_ for _ in ()).throw(ValueError("secret")),
                        )
                    except ValueError:
                        pass
                task.invoke_tool("draft_builder", "fourth", lambda: "should not run")
                return super().run(task)
        store = SQLiteMissionStore(self.db)
        runtime = AlphaRuntime(
            store, {"SCRIBE": CatchingReader()},
            trajectory_policy=ToolTrajectoryPolicy(
                max_failures_per_tool=2, max_total_calls=10,
            ),
        )
        with self.assertRaises(TrajectoryBlocked):
            runtime.submit(self.request(), "SCRIBE")
        reasons = [
            e["payload"].get("reason")
            for e in store.events("mission-1")
            if e["event_type"] == "TOOL_CALL_BLOCKED"
        ]
        self.assertIn("repeated_tool_failures", reasons)
        self.assertNotIn("secret", str(store.events("mission-1")))


    def test_invalidation_revokes_pending_action_eligibility(self):
        action = ProposedAction("send", "email.send", {"body": "draft"})
        evidence = Evidence(
            "ev-1", "Customer is impacted", "monitor",
            "2026-10-09T10:00:00Z", "fact",
        )
        store = SQLiteMissionStore(self.db)
        runtime = AlphaRuntime(store, {"SCRIBE": DemoSpecialist(action)})
        runtime.submit(self.request(), "SCRIBE", [evidence])
        self.assertEqual(store.get("mission-1")["status"], "AWAITING_APPROVAL")
        store.approve("mission-1", action, "reviewer")
        store.invalidate_evidence("mission-1", "ev-1", "source retracted")
        self.assertEqual(store.get("mission-1")["status"], "VERIFICATION_FAILED")
        called = []
        with self.assertRaises(ApprovalRequired):
            store.execute_once(
                "mission-1", action, lambda a, key: called.append(key)
            )
        with self.assertRaises(ApprovalRequired):
            runtime.approve_and_execute(
                "mission-1", action, "reviewer", lambda a, key: called.append(key)
            )
        self.assertEqual(called, [])
        self.assertTrue(store.verify_event_chain("mission-1"))

    def test_invalidation_of_completed_action_requires_reconciliation(self):
        action = ProposedAction("send", "email.send", {"body": "draft"})
        evidence = Evidence(
            "ev-1", "Customer is impacted", "monitor",
            "2026-10-09T10:00:00Z", "fact",
        )
        store = SQLiteMissionStore(self.db)
        runtime = AlphaRuntime(store, {"SCRIBE": DemoSpecialist(action)})
        runtime.submit(self.request(), "SCRIBE", [evidence])
        runtime.approve_and_execute(
            "mission-1", action, "reviewer",
            lambda a, key: {"status": "sent"},
        )
        store.invalidate_evidence("mission-1", "ev-1", "source retracted")
        self.assertEqual(store.get("mission-1")["status"], "ACTION_COMPLETED")
        self.assertIn(
            "POST_ACTION_EVIDENCE_INVALIDATED",
            [e["event_type"] for e in store.events("mission-1")],
        )


if __name__ == "__main__":
    unittest.main()
