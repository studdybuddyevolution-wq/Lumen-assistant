"""Instruction-only skills: no Python files or scripts are executed."""
from __future__ import annotations

import re
import time
import uuid
from typing import Any

from .state import kill_switch_active, read_json, state_dir, write_json_atomic

def _skills_file():
    return state_dir() / "skills.json"
MAX_SKILLS = 50
MAX_INSTRUCTIONS = 6000


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return slug[:48]


def _load() -> list[dict[str, Any]]:
    data = read_json(_skills_file(), [])
    return data if isinstance(data, list) else []


def save_skill(name: str, description: str, instructions: str) -> dict[str, Any]:
    if kill_switch_active():
        return {"success": False, "message": "Self-development is disabled by LUMEN_SELFDEV_DISABLED."}
    clean_name = " ".join(str(name or "").split())[:60]
    clean_description = " ".join(str(description or "").split())[:300]
    clean_instructions = str(instructions or "").strip()
    slug = slugify(clean_name)
    if not slug or not clean_description or not clean_instructions:
        return {"success": False, "message": "A skill needs a name, description, and instructions."}
    if len(clean_instructions) > MAX_INSTRUCTIONS:
        return {"success": False, "message": f"Skill instructions exceed the {MAX_INSTRUCTIONS}-character limit."}
    if "```" in clean_instructions:
        return {"success": False, "message": "Instruction-only skills cannot contain executable code fences."}

    skills = _load()
    existing = next((item for item in skills if item.get("slug") == slug), None)
    if existing:
        existing.update({
            "name": clean_name,
            "description": clean_description,
            "instructions": clean_instructions,
            "active": True,
            "updated_at": time.time(),
        })
        write_json_atomic(_skills_file(), skills)
        return {"success": True, "skill": {k: v for k, v in existing.items() if k != "instructions"}, "message": "Updated the existing instruction skill."}

    if len(skills) >= MAX_SKILLS:
        return {"success": False, "message": f"The skill limit ({MAX_SKILLS}) has been reached."}
    now = time.time()
    item = {
        "id": uuid.uuid4().hex[:10],
        "slug": slug,
        "name": clean_name,
        "description": clean_description,
        "instructions": clean_instructions,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }
    skills.append(item)
    write_json_atomic(_skills_file(), skills)
    return {"success": True, "skill": {k: v for k, v in item.items() if k != "instructions"}, "message": "Saved an active instruction-only skill."}


def list_skills(active_only: bool = False) -> list[dict[str, Any]]:
    values = _load()
    if active_only:
        values = [item for item in values if item.get("active", True)]
    return values


def set_skill_active(slug: str, active: bool) -> dict[str, Any]:
    skills = _load()
    for item in skills:
        if item.get("slug") == slug or item.get("id") == slug:
            item["active"] = bool(active)
            item["updated_at"] = time.time()
            write_json_atomic(_skills_file(), skills)
            return {"success": True, "message": f"Skill {item.get('name')} {'enabled' if active else 'disabled'}."}
    return {"success": False, "message": f"No skill with ID or slug {slug!r}."}
