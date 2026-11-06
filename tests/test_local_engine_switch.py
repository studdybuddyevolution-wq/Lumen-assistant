from __future__ import annotations

import unittest

from core.engine_switch import validate_local_pipeline


class FakeProvider:
    def __init__(self, result=(True, "ready")):
        self.result = result

    def probe(self, **_kwargs):
        return self.result


class FakeRegistry:
    def __init__(self, declarations):
        self.declarations = declarations

    def get_declaration(self, provider_id):
        return self.declarations.get(provider_id)

    def missing_fields(self, provider_id, config):
        return [] if config.get("configured", True) else ["Model"]

    def build(self, provider_id, config):
        return self.declarations[provider_id]["instance"]


class LocalEngineValidationTests(unittest.TestCase):
    def setUp(self):
        self.declarations = {
            "ollama": {
                "id": "ollama", "label": "Ollama", "_available": True,
                "catalog": ({"id": "ollama", "label": "Ollama", "local": True},),
                "instance": FakeProvider(),
            },
            "whisper": {
                "id": "whisper", "label": "Whisper", "_available": True,
                "catalog": ({"id": "local", "label": "Whisper local", "local": True},),
                "instance": FakeProvider(),
            },
            "piper": {
                "id": "piper", "label": "Piper", "_available": True,
                "catalog": ({"id": "piper", "label": "Piper local", "local": True},),
                "instance": FakeProvider(),
            },
            "cloud_tts": {
                "id": "cloud_tts", "label": "Cloud TTS", "_available": True,
                "catalog": ({"id": "hosted", "label": "Hosted TTS", "local": False},),
                "instance": FakeProvider(),
            },
        }
        self.configs = {
            "ollama": {"catalog": "ollama", "configured": True},
            "whisper": {"catalog": "local", "configured": True},
            "piper": {"catalog": "piper", "configured": True},
            "cloud_tts": {"catalog": "hosted", "configured": True},
        }
        self.registry = FakeRegistry(self.declarations)

    def validate(self, pipeline):
        validate_local_pipeline(
            self.registry, pipeline, lambda provider_id: self.configs.get(provider_id, {})
        )

    def test_accepts_three_configured_local_providers(self):
        self.validate({"llm": "ollama", "stt": "whisper", "tts": "piper"})

    def test_rejects_missing_pipeline_slot(self):
        with self.assertRaisesRegex(ValueError, "No STT provider"):
            self.validate({"llm": "ollama", "tts": "piper"})

    def test_rejects_cloud_provider_in_any_slot(self):
        with self.assertRaisesRegex(ValueError, "not confirmed as local"):
            self.validate({"llm": "ollama", "stt": "whisper", "tts": "cloud_tts"})

    def test_rejects_unconfigured_provider(self):
        self.configs["ollama"]["configured"] = False
        with self.assertRaisesRegex(ValueError, "needs: Model"):
            self.validate({"llm": "ollama", "stt": "whisper", "tts": "piper"})

    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.validate({"llm": "missing", "stt": "whisper", "tts": "piper"})

    def test_rejects_local_provider_that_fails_its_readiness_probe(self):
        self.declarations["whisper"]["instance"] = FakeProvider((False, "package missing"))
        with self.assertRaisesRegex(ValueError, "not ready: package missing"):
            self.validate({"llm": "ollama", "stt": "whisper", "tts": "piper"})


if __name__ == "__main__":
    unittest.main()
