"""Validate that the complete conversation pipeline is configured locally.

The engine-switch command uses this before changing the active mode. A cloud
provider in even one slot is rejected, so "switch to local" cannot quietly
leave speech recognition or speech output on a hosted service.
"""

from __future__ import annotations


_REQUIRED_SLOTS = ("llm", "stt", "tts")


def validate_local_pipeline(registry, pipeline: dict, get_provider_config) -> None:
    """Raise ValueError unless LLM, STT and TTS are all explicitly local.

    The provider catalog's local flag is authoritative. A custom or unknown
    endpoint is not assumed local merely because its name sounds local.
    """
    pipeline = pipeline if isinstance(pipeline, dict) else {}

    for slot in _REQUIRED_SLOTS:
        provider_id = str(pipeline.get(slot) or "").strip()
        if not provider_id:
            raise ValueError(
                f"No {slot.upper()} provider is selected. Configure all three "
                "local providers in Engine & Providers first."
            )

        declaration = registry.get_declaration(provider_id)
        if declaration is None:
            raise ValueError(
                f"The selected {slot.upper()} provider {provider_id!r} is unavailable."
            )
        if not declaration.get("_available", True):
            required = ", ".join(declaration.get("requires", ())) or "its dependencies"
            raise ValueError(
                f"{declaration.get('label', provider_id)} needs {required} installed."
            )

        cfg = dict(get_provider_config(provider_id) or {})
        missing = registry.missing_fields(provider_id, cfg)
        if missing:
            raise ValueError(
                f"{declaration.get('label', provider_id)} needs: {', '.join(missing)}."
            )

        catalog_id = str(cfg.get("catalog") or "").strip()
        entries = declaration.get("catalog") or ()
        selected = next(
            (entry for entry in entries if str(entry.get("id") or "") == catalog_id),
            None,
        )
        if selected is None or selected.get("local") is not True:
            label = (selected or {}).get("label") or catalog_id or provider_id
            raise ValueError(
                f"{slot.upper()} provider {label!r} is not confirmed as local. "
                "Choose an entry marked 'on this computer'."
            )
