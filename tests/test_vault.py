from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory import vault_manager as vault
from selfdev.skills import save_skill


class VaultManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "Lumen-Vault"
        self.env = patch.dict(os.environ, {
            "LUMEN_VAULT_PATH": str(self.root),
            "LUMEN_VAULT_DISABLED": "0",
            "LUMEN_VAULT_AUTO_CONTEXT": "1",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_initialize_creates_scaffold_and_is_idempotent(self):
        first = vault.initialize_vault()
        index_path = self.root / "VAULT-INDEX.md"
        self.assertTrue(first["success"])
        self.assertTrue(index_path.is_file())
        original = index_path.read_text(encoding="utf-8")
        second = vault.initialize_vault()
        self.assertIn("VAULT-INDEX.md", second["preserved"])
        self.assertEqual(index_path.read_text(encoding="utf-8"), original)

    def test_initialize_refuses_nonempty_unknown_folder_without_merge_flag(self):
        self.root.mkdir(parents=True)
        (self.root / "My Notes.md").write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            vault.initialize_vault()
        self.assertFalse((self.root / "VAULT-INDEX.md").exists())
        merged = vault.initialize_vault(merge_existing=True)
        self.assertTrue(merged["success"])
        self.assertEqual((self.root / "My Notes.md").read_text(encoding="utf-8"), "keep")

    def test_create_read_search_and_append_note(self):
        vault.initialize_vault()
        created = vault.create_note("02 - Lumen Assistant/Development/Test.md", "# Test note\n\nBarehands bridge")
        self.assertTrue(created["success"])
        read = vault.read_note("02 - Lumen Assistant/Development/Test.md")
        self.assertIn("UNTRUSTED VAULT NOTE DATA", read["content"])
        search = vault.search_notes("Barehands")
        self.assertGreaterEqual(len(search["matches"]), 1)
        appended = vault.append_note("02 - Lumen Assistant/Development/Test.md", "Second update")
        self.assertTrue(appended["success"])
        self.assertIn("Second update", vault.read_note("02 - Lumen Assistant/Development/Test.md")["content"])

    def test_paths_cannot_escape_or_read_non_markdown(self):
        vault.initialize_vault()
        for value in ("../secret.md", "C:\\secret.md", ".obsidian/app.md", "folder/file.txt"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    vault._note_path(value)

    def test_existing_notes_are_not_overwritten(self):
        vault.initialize_vault()
        result = vault.create_note("Active Priorities.md", "replacement")
        self.assertFalse(result["success"])
        self.assertIn("Open Tasks", (self.root / "Active Priorities.md").read_text(encoding="utf-8"))

    def test_jobs_can_be_created_listed_and_loaded(self):
        vault.initialize_vault()
        result = vault.save_job("Build Feature", "Implement a Lumen feature", "1. Inspect code\n2. Add tests")
        self.assertTrue(result["success"])
        jobs = vault.list_jobs()
        self.assertEqual(jobs["count"], 1)
        loaded = vault.load_job("build-feature")
        self.assertTrue(loaded["success"])
        self.assertIn("Implement a Lumen feature", loaded["content"])

    def test_priority_add_and_complete(self):
        vault.initialize_vault()
        self.assertTrue(vault.add_priority("Connect the Obsidian vault")["success"])
        self.assertTrue(vault.complete_priority("Connect the Obsidian vault")["success"])
        priorities = (self.root / "Active Priorities.md").read_text(encoding="utf-8")
        self.assertIn("- [x] Connect the Obsidian vault", priorities)
        self.assertNotIn("- [ ] Connect the Obsidian vault", priorities)

    def test_daily_log_appends_a_new_session_to_same_day(self):
        vault.initialize_vault()
        one = vault.log_daily_note("Vault build", "Created the local vault", what_got_done="Added scaffold")
        two = vault.log_daily_note("Skill design", "Mapped skills to Jobs", decisions="Keep skill JSON registry")
        self.assertEqual(one["session"], 1)
        self.assertEqual(two["session"], 2)
        daily = (self.root / one["path"]).read_text(encoding="utf-8")
        self.assertIn("## Session 1", daily)
        self.assertIn("## Session 2", daily)
        self.assertIn("Mapped skills to Jobs", daily)

    def test_prompt_context_is_bounded_and_optional(self):
        vault.initialize_vault()
        context = vault.build_prompt_context(max_chars=500)
        self.assertLessEqual(len(context), 502)
        with patch.dict(os.environ, {"LUMEN_VAULT_AUTO_CONTEXT": "0"}):
            self.assertEqual(vault.build_prompt_context(), "")

    def test_export_skill_creates_agent_skills_package_and_sources(self):
        vault.initialize_vault()
        data_dir = self.root.parent / "lumen-data"
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(data_dir), "LOCALAPPDATA": str(data_dir)}):
            saved = save_skill(
                "Canvas Animation",
                "Build small Canvas animations using documented APIs.",
                "Create a canvas, animate with requestAnimationFrame, and inspect the result.",
                sources=["https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API"],
                practice_status="partial",
                practice_notes="Static review only; browser runtime check not run.",
            )
            exported = vault.export_instruction_skill(saved["skill"]["id"])
        self.assertTrue(exported["success"])
        skill_path = self.root / "Resources" / "Skills" / "canvas-animation" / "SKILL.md"
        sources_path = self.root / "Resources" / "Skills" / "canvas-animation" / "references" / "SOURCES.md"
        self.assertTrue(skill_path.is_file())
        self.assertTrue(sources_path.is_file())
        self.assertIn("name: canvas-animation", skill_path.read_text(encoding="utf-8"))
        self.assertIn("developer.mozilla.org", sources_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
