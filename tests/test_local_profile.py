import unittest

from providers.local_profile import (
    MODEL,
    OLLAMA_URL,
    PIPER_VOICE,
    get_llm_config,
    get_profile,
)


class LocalProfileTests(unittest.TestCase):
    def test_profile_wires_whisper_qwen_and_piper(self):
        pipeline, configs = get_profile()
        self.assertEqual(pipeline, {
            "stt": "whisper",
            "llm": "openai_compat",
            "tts": "piper",
        })
        self.assertEqual(configs["whisper"]["backend"], "local")
        self.assertEqual(configs["whisper"]["device"], "cpu")
        self.assertEqual(configs["openai_compat"]["model"], MODEL)
        self.assertEqual(configs["openai_compat"]["base_url"], OLLAMA_URL)
        self.assertEqual(configs["openai_compat"]["api_key"], "")
        self.assertEqual(configs["piper"]["voice"], PIPER_VOICE)

    def test_profile_returns_independent_settings(self):
        pipeline, configs = get_profile()
        pipeline["llm"] = "changed"
        configs["openai_compat"]["model"] = "changed"
        self.assertEqual(get_llm_config()["model"], MODEL)
        self.assertEqual(get_profile()[0]["llm"], "openai_compat")


if __name__ == "__main__":
    unittest.main()
