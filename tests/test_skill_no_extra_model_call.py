from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from actions.self_development import self_development
from selfdev.skills import list_skills


class SkillCreationNoExtraModelCallTests(unittest.TestCase):
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

    def test_create_skill_stores_supplied_instructions_without_generation_call(self):
        result = json.loads(self_development({
            "operation": "create_skill",
            "skill_name": "PowerShell Diagnostics",
            "description": "Diagnose Windows Python project issues.",
            "instructions": "Check the current directory, inspect the traceback, and reproduce the error before proposing changes.",
        }))
        self.assertTrue(result["success"])
        self.assertEqual(len(list_skills(active_only=True)), 1)
        self.assertIn("reproduce the error", list_skills(active_only=True)[0]["instructions"])

    def test_create_skill_requires_instructions_instead_of_calling_gemini(self):
        result = json.loads(self_development({
            "operation": "create_skill",
            "goal": "Build a debugging skill",
        }))
        self.assertFalse(result["success"])
        self.assertIn("no additional Gemini", result["message"])


if __name__ == "__main__":
    unittest.main()
