"""Lumen's ready-made, fully local conversation profile.

The profile is separate from editable provider settings. Choosing it never
overwrites a user's custom Whisper, Ollama, Piper, sidecar, or Gemini settings.
"""
from __future__ import annotations

from copy import deepcopy
from importlib.util import find_spec

MODEL = "qwen3.5:4b"
OLLAMA_URL = "http://127.0.0.1:11434/v1"
PIPER_VOICE = "en_US-lessac-medium"

_PIPELINE = {
    "stt": "whisper",
    "llm": "openai_compat",
    "tts": "piper",
}
_CONFIGS = {
    "whisper": {
        "backend": "local",
        "model": "base",
        "device": "cpu",
        "language": "",
        "base_url": "",
        "api_key": "",
        "download_root": "",
    },
    "openai_compat": {
        "base_url": OLLAMA_URL,
        "model": MODEL,
        "api_key": "",
        "vision": "1",
        "vision_model": MODEL,
        "max_tools": "14",
        "max_tool_chars": "12000",
    },
    "piper": {
        "voice": PIPER_VOICE,
        "follow_language": "1",
        "speed": "1.0",
    },
}


def get_profile() -> tuple[dict, dict]:
    """Fresh copies of the three local pipeline slots and their settings."""
    return deepcopy(_PIPELINE), deepcopy(_CONFIGS)


def get_llm_config() -> dict:
    """The local Qwen endpoint, also used by model-assisted local side calls."""
    return deepcopy(_CONFIGS["openai_compat"])


def validate_local_profile() -> tuple[bool, str]:
    """Check dependencies, Ollama reachability and the exact Qwen model tag."""
    if find_spec("faster_whisper") is None:
        return False, (
            "Local speech recognition is not installed. Run: "
            "python -m pip install faster-whisper"
        )
    if find_spec("piper") is None:
        return False, (
            "Local Piper speech output is not installed. Run: "
            "python -m pip install piper-tts"
        )

    try:
        from providers import registry
        llm = registry.build("openai_compat", get_llm_config())
        models = llm.models(timeout=6.0)
    except Exception as exc:
        return False, (
            "Ollama did not answer at " + OLLAMA_URL + ". Start Ollama and "
            "check that it is running. Details: " + str(exc)[:180]
        )

    if MODEL not in models:
        return False, (
            "Ollama is running, but it does not have " + MODEL +
            " installed. Run: ollama pull " + MODEL
        )
    return True, "Local requirements are ready: Whisper, Ollama/Qwen 3.5 4B and Piper."
