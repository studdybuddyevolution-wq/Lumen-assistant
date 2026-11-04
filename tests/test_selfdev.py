from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from selfdev.learning import add_rule, build_prompt_context, list_rules, set_rule_active
from selfdev.skills import list_skills, save_skill, set_skill_active, view_skill
from selfdev import repair


class SelfDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"XDG_DATA_HOME": self.temp.name, "LOCALAPPDATA": self.temp.name})
        self.env.start()
        self.project = Path(self.temp.name) / "project"
        (self.project / "actions").mkdir(parents=True)
        (self.project / "plugins").mkdir(parents=True)
        (self.project / "actions" / "sample.py").write_text("def run():\n    return 'old'\n", encoding="utf-8")
        self.root_patch = patch.object(repair, "PROJECT_ROOT", self.project)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_rule_is_persisted_and_can_be_disabled(self):
        result = add_rule("Prefer short answers", category="style")
        self.assertTrue(result["success"])
        self.assertEqual(len(list_rules(active_only=True)), 1)
        self.assertIn("Prefer short answers", build_prompt_context())
        self.assertTrue(set_rule_active(result["rule"]["id"], False)["success"])
        self.assertEqual(list_rules(active_only=True), [])

    def test_skill_learning_protocol_prioritizes_research_practice_and_approval(self):
        context = build_prompt_context()
        self.assertIn("SKILL LEARNING PROTOCOL", context)
        self.assertIn("free_research", context)
        self.assertIn("practise a small", context.lower())
        self.assertIn("Wait for explicit approval", context)

    def test_skill_is_instruction_only_and_can_be_disabled(self):
        result = save_skill("Release checklist", "Prepare a release", "Check tests, notes, and rollback steps.")
        self.assertTrue(result["success"])
        context = build_prompt_context()
        self.assertIn("Release checklist", context)
        self.assertNotIn("Check tests, notes, and rollback steps.", context)
        slug = list_skills(active_only=True)[0]["slug"]
        self.assertIn("Check tests, notes, and rollback steps.", view_skill(slug)["skill"]["instructions"])
        self.assertTrue(set_skill_active(slug, False)["success"])
        self.assertEqual(list_skills(active_only=True), [])

    def test_repair_proposal_does_not_modify_source(self):
        original = (self.project / "actions" / "sample.py").read_text(encoding="utf-8")
        proposal = repair.create_proposal("actions/sample.py", "def run():\n    return 'fixed'\n", "Fix sample output")
        self.assertEqual(proposal["status"], "pending_review")
        self.assertEqual((self.project / "actions" / "sample.py").read_text(encoding="utf-8"), original)
        self.assertIn("return 'fixed'", proposal["diff"])

    def test_apply_and_rollback_require_current_hash_to_match(self):
        proposal = repair.create_proposal("actions/sample.py", "def run():\n    return 'fixed'\n", "Fix sample")
        applied = repair.apply_proposal(proposal["id"])
        self.assertTrue(applied["success"])
        self.assertIn("fixed", (self.project / "actions" / "sample.py").read_text(encoding="utf-8"))
        rolled = repair.rollback_proposal(proposal["id"])
        self.assertTrue(rolled["success"])
        self.assertIn("old", (self.project / "actions" / "sample.py").read_text(encoding="utf-8"))

    def test_traceback_parser_selects_an_eligible_project_frame(self):
        trace = f'Traceback (most recent call last):\n  File "{self.project / "actions" / "sample.py"}", line 2, in run\nValueError: bad value'
        relative, line = repair.parse_traceback_target(trace)
        self.assertEqual(relative, "actions/sample.py")
        self.assertEqual(line, 2)

    def test_core_and_config_paths_are_not_repair_targets(self):
        with self.assertRaises(ValueError):
            repair.resolve_target("../project/config/api_keys.json", self.project)
        (self.project / "core").mkdir()
        (self.project / "core" / "gemini.py").write_text("# protected\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            repair.resolve_target("core/gemini.py", self.project)


if __name__ == "__main__":
    unittest.main()
