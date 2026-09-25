import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("project_contract", ROOT / "project_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


class ProjectContractTests(unittest.TestCase):
    def test_active_project_profiles_are_valid_and_scoped(self):
        profiles = json.loads((ROOT / "projects.json").read_text())["projects"]
        self.assertEqual(len(profiles), 10)
        self.assertEqual(len({profile["id"] for profile in profiles}), len(profiles))
        brand = json.loads((ROOT.parent / "brand" / "project-brand-registry.json").read_text())
        active_ids = {item["id"] for item in brand["projects"]
                      if item["status"] != "CONSOLIDATE_OR_RETIRE"}
        self.assertEqual({profile["id"] for profile in profiles}, active_ids)
        for profile in profiles:
            with self.subTest(project=profile["id"]):
                self.assertEqual(contract.validate(profile), [])
                mission = contract.mission_from_profile(profile, "Plan a narrow improvement")
                self.assertEqual(mission.allowed_tools, [])
                self.assertTrue(mission.approval_required)
                self.assertTrue(any("send external messages" in action
                                    for action in mission.prohibited_actions))

    def test_new_idea_needs_customer_problem_and_measurement_before_mission(self):
        idea = contract.new_concept("new-idea", "New Idea")
        self.assertIn("customer is required", contract.validate(idea))
        with self.assertRaisesRegex(ValueError, "invalid project contract"):
            contract.mission_from_profile(idea, "Build it")

    def test_connected_tools_and_automatic_actions_are_rejected(self):
        profile = json.loads((ROOT / "projects.json").read_text())["projects"][0]
        altered = dict(profile, connected_tools=["gmail.send"], automatic_external_actions=True)
        self.assertIn("automatic_external_actions must be false", contract.validate(altered))
        self.assertIn("connected_tools must be [] until a reviewed integration is implemented",
                      contract.validate(altered))


if __name__ == "__main__":
    unittest.main()
