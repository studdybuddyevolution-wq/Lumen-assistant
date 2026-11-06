import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "core" / "engine_switch.py"
SPEC = importlib.util.spec_from_file_location("lumen_engine_switch_test", MODULE)
ENGINE_SWITCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE_SWITCH)


class EngineSwitchParsingTests(unittest.TestCase):
    def test_local_commands(self):
        phrases = (
            "switch to local",
            "Lumen, switch to local engine.",
            "please use the local engine",
            "go offline",
            "switch back to offline mode",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(ENGINE_SWITCH.parse_engine_switch(phrase), "local")

    def test_gemini_commands(self):
        phrases = (
            "switch to Gemini",
            "Jarvis, switch back to Gemini Live.",
            "use cloud mode",
            "go online",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(ENGINE_SWITCH.parse_engine_switch(phrase), "gemini")

    def test_casual_mentions_are_not_switch_commands(self):
        phrases = (
            "turn on the local lights",
            "tell me about Gemini",
            "I prefer local music",
            "hello Lumen",
            "switch to local lights",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIsNone(ENGINE_SWITCH.parse_engine_switch(phrase))


if __name__ == "__main__":
    unittest.main()
