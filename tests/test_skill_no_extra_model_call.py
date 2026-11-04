from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from actions.self_development import self_development
from selfdev.skills import list_pending_skills, list_skills, view_skill


class SkillLearningPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "XDG_DATA_HOME": self.temp.name,
            "LOCALAPPDATA": self.temp.name,
            "LUMEN_SELFDEV_DISABLED": "0",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_create_skill_stages_proposal_until_explicit_approval(self):
        result = json.loads(self_development({
            "operation": "create_skill",
            "skill_name": "Canvas Animation",
            "description": "Build small Canvas animations using documented browser APIs.",
            "instructions": "Check browser support, create a minimal canvas, animate with requestAnimationFrame, and verify the resulting motion.",
            "source_refs": ["https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API"],
            "practice_status": "partial",
            "practice_notes": "Reviewed the Canvas API documentation; no local runtime test has been performed yet.",
        }))
        self.assertTrue(result["success"])
        pending_id = result["pending_id"]
        self.assertIn("requestAnimationFrame", result["proposal"]["instructions"])
        self.assertEqual(len(list_pending_skills()), 1)
        pending_view = json.loads(self_development({"operation": "pending_skills"}))
        self.assertIn("requestAnimationFrame", pending_view["pending_skills"][0]["instructions"])
        self.assertEqual(list_skills(active_only=True), [])

        approved = json.loads(self_development({
            "operation": "approve_skill",
            "pending_id": pending_id,
        }))
        self.assertTrue(approved["success"])
        self.assertEqual(len(list_pending_skills()), 0)
        self.assertEqual(len(list_skills(active_only=True)), 1)
        skill = view_skill("canvas_animation")["skill"]
        self.assertEqual(skill["source_refs"], ["https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API"])
        self.assertEqual(skill["practice_status"], "partial")

    def test_reject_skill_discards_proposal_without_activating_it(self):
        proposal = json.loads(self_development({
            "operation": "create_skill",
            "skill_name": "Markdown Notes",
            "description": "Create structured Markdown notes.",
            "instructions": "Use clear headings and link related notes.",
            "source_refs": ["Current conversation"],
            "practice_status": "not_run",
        }))
        rejected = json.loads(self_development({
            "operation": "reject_skill",
            "pending_id": proposal["pending_id"],
        }))
        self.assertTrue(rejected["success"])
        self.assertEqual(list_pending_skills(), [])
        self.assertEqual(list_skills(active_only=True), [])

    def test_update_does_not_replace_active_skill_until_approved_and_keeps_history(self):
        first = json.loads(self_development({
            "operation": "create_skill",
            "skill_name": "Python Debugging",
            "description": "Debug a Python project.",
            "instructions": "Inspect the traceback and reproduce the failure.",
            "source_refs": ["Current conversation"],
            "practice_status": "not_run",
        }))
        self.assertTrue(json.loads(self_development({
            "operation": "approve_skill", "pending_id": first["pending_id"]
        }))["success"])
        skill_id = list_skills(active_only=True)[0]["id"]

        update = json.loads(self_development({
            "operation": "create_skill",
            "skill_name": "Python Debugging",
            "description": "Debug a Python project.",
            "instructions": "Inspect the traceback, reproduce the failure, add a focused regression test, and verify the fix.",
            "source_refs": ["Current conversation"],
            "practice_status": "partial",
            "practice_notes": "The procedure was drafted; it has not yet been exercised on a real issue.",
        }))
        self.assertTrue(update["success"])
        self.assertEqual(view_skill(skill_id)["skill"]["instructions"], "Inspect the traceback and reproduce the failure.")

        self.assertTrue(json.loads(self_development({
            "operation": "approve_skill", "pending_id": update["pending_id"]
        }))["success"])
        revised = view_skill(skill_id)["skill"]
        self.assertIn("regression test", revised["instructions"])
        self.assertEqual(revised["version"], 2)
        self.assertEqual(len(revised["history"]), 1)

    def test_verified_status_requires_concrete_practice_evidence(self):
        result = json.loads(self_development({
            "operation": "create_skill",
            "skill_name": "Tested Skill",
            "description": "A skill with a practice record.",
            "instructions": "Run a small check and record its outcome.",
            "source_refs": ["Current conversation"],
            "practice_status": "verified",
            "practice_notes": "Looks good.",
        }))
        self.assertFalse(result["success"])
        self.assertIn("concrete practice evidence", result["message"])

    def test_skill_creation_handler_does_not_make_a_second_model_call(self):
        result = json.loads(self_development({
            "operation": "create_skill",
            "skill_name": "Local Skill",
            "description": "A locally stored workflow.",
            "instructions": "Use the approved procedure.",
            "source_refs": ["Current conversation"],
            "practice_status": "not_run",
        }))
        self.assertTrue(result["success"])
        self.assertEqual(list_skills(active_only=True), [])
        self.assertEqual(len(list_pending_skills()), 1)

    def test_create_skill_without_instructions_does_not_call_a_generator(self):
        result = json.loads(self_development({
            "operation": "create_skill",
            "goal": "Build a debugging skill",
        }))
        self.assertFalse(result["success"])
        self.assertIn("stages a proposal only", result["message"])


if __name__ == "__main__":
    unittest.main()
