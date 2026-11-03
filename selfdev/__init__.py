"""Guarded, user-controlled self-development features for Lumen.

The package deliberately has no import-time dependency on Gemini or optional
runtime packages. Code generation is lazy and code changes are never applied
from the conversation action; use ``python -m selfdev.cli apply <id>`` after
reviewing the generated diff.
"""

from .learning import build_prompt_context

__all__ = ["build_prompt_context"]
