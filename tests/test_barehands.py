import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions import barehands


class BarehandsBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "server.py").write_text("# test", encoding="utf-8")
        (self.root / "stage.html").write_text("<html></html>", encoding="utf-8")
        (self.root / "media" / "misc").mkdir(parents=True)
        (self.root / "media" / "misc" / "logo.png").write_bytes(b"test")
        (self.root / "media" / "misc" / ".hidden.png").write_bytes(b"test")
        (self.root / "barehands.json").write_text(
            json.dumps({"port": 8794, "orbs": [{"kind": "media", "path": "media"}]}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_root_requires_barehands_files(self):
        with patch.object(barehands, "DEFAULT_ROOT", self.root):
            self.assertEqual(barehands._barehands_root(), self.root.resolve())

    def test_media_path_accepts_existing_file_inside_media_jail(self):
        self.assertEqual(barehands._safe_media_src(self.root, "misc/logo.png"), "misc/logo.png")

    def test_media_path_rejects_parent_traversal(self):
        with self.assertRaises(ValueError):
            barehands._safe_media_src(self.root, "../secret.png")

    def test_media_path_rejects_absolute_path(self):
        with self.assertRaises(ValueError):
            barehands._safe_media_src(self.root, str(self.root / "media" / "misc" / "logo.png"))

    def test_media_path_rejects_hidden_path(self):
        with self.assertRaises(ValueError):
            barehands._safe_media_src(self.root, "misc/.hidden.png")

    def test_fraction_rejects_nan_and_out_of_range_values(self):
        for value in (float("nan"), -0.1, 1.1, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    barehands._fraction(value, "x")

    def test_present_command_limits_text_length(self):
        with self.assertRaises(ValueError):
            barehands._build_command(self.root, "present", {"title": "x" * 121, "body": ""})


if __name__ == "__main__":
    unittest.main()
