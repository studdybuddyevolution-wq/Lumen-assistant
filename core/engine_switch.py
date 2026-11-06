"""Explicit engine-switch command parsing.

This module is intentionally small and side-effect free. It recognises only
complete switch commands, not casual mentions of words like "local" or "Gemini".
"""
from __future__ import annotations

import re

_SWITCH = re.compile(
    r"^(?:(?:hey\s+)?(?:lumen|jarvis)\s+)?"
    r"(?:please\s+)?(?:switch|change|move|go|use)\s+"
    r"(?:back\s+)?(?:to\s+)?(?:the\s+)?"
    r"(?:(?:conversation\s+)?engine\s+)?"
    r"(local|offline|gemini|cloud|online)"
    r"(?:\s+(?:engine|mode|live))?$"
)


def parse_engine_switch(text: str) -> str | None:
    """Return local or gemini for an explicit, whole-utterance command."""
    value = re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower())
    value = " ".join(value.split())
    match = _SWITCH.fullmatch(value)
    if not match:
        return None
    target = match.group(1)
    return "local" if target in ("local", "offline") else "gemini"
