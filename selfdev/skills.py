"""Persistent, instruction-only skills with an explicit approval queue.

Runtime skills are stored outside the source repository. Each approved skill is
a reusable procedure; this module never executes code from a skill.
"""
from __future__ import annotations

import re
import time
import uuid
from typing import Any

from .state import kill_switch_active, read_json, state_dir, write_json_atomic

MAX_SKILLS = 50
MAX_PENDING_SKILLS = 20
MAX_SKILL_NAME = 64
MAX_DESCRIPTION = 1024
MAX_INSTRUCTIONS = 14_000
MAX_SOURCES = 12
MAX_SOURCE_LENGTH = 700
MAX_PRACTICE_NOTES = 2400
VALID_PRACTICE = {"verified", "partial", "not_run", "failed", "not_applicable"}


def _skills_file():
    return state_dir() / "skills.json"


def _pending_file():
    return state_dir() / "pending_skills.json"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return slug[:48]


def standard_name(value: str) -> str:
    """Return a directory-safe name compatible with the Agent Skills format."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:64].strip("-")


def _load() -> list[dict[str, Any]]:
    data = read_json(_skills_file(), [])
    return data if isinstance(data, list) else []


def _load_pending() -> list[dict[str, Any]]:
    data = read_json(_pending_file(), [])
    return data if isinstance(data, list) else []


def _clean_sources(sources: Any) -> list[str]:
    if isinstance(sources, str):
        raw = sources.splitlines()
    elif isinstance(sources, (tuple, list)):
        raw = list(sources)
    else:
        raw = []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = " ".join(str(item or "").split()).strip()[:MAX_SOURCE_LENGTH]
        if not value or value.casefold() in seen:
            continue
        if value.casefold().startswith(("javascript:", "data:", "file://")):
            continue
        seen.add(value.casefold())
        result.append(value)
        if len(result) >= MAX_SOURCES:
            break
    return result


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items()
            if key not in {"instructions", "history"}}


def _validate(name: str, description: str, instructions: str,
              sources: Any, practice_status: str,
              practice_notes: str) -> tuple[dict[str, Any] | None, str]:
    clean_name = " ".join(str(name or "").split())[:MAX_SKILL_NAME]
    clean_description = " ".join(str(description or "").split())[:MAX_DESCRIPTION]
    clean_instructions = str(instructions or "").strip()
    slug = slugify(clean_name)
    clean_sources = _clean_sources(sources)
    status = str(practice_status or "not_run").strip().lower()
    clean_practice = str(practice_notes or "").strip()[:MAX_PRACTICE_NOTES]

    if not slug or not clean_description or not clean_instructions:
        return None, "A skill needs a name, description, and instructions."
    if len(clean_instructions) > MAX_INSTRUCTIONS:
        return None, f"Skill instructions exceed the {MAX_INSTRUCTIONS}-character limit."
    if chr(96) * 3 in clean_instructions:
        return None, "Instruction-only skills cannot contain executable code fences."
    if not clean_sources:
        return None, "Record at least one source (for example, an official documentation URL or 'Current conversation')."
    if status not in VALID_PRACTICE:
        return None, f"practice_status must be one of: {', '.join(sorted(VALID_PRACTICE))}."
    if status == "verified" and len(clean_practice) < 12:
        return None, "A verified skill needs concrete practice evidence. Otherwise mark it partial or not_run."
    return {
        "name": clean_name,
        "slug": slug,
        "description": clean_description,
        "instructions": clean_instructions,
        "source_refs": clean_sources,
        "practice_status": status,
        "practice_notes": clean_practice,
    }, ""


def propose_skill(name: str, description: str, instructions: str,
                  sources: Any = None, practice_status: str = "not_run",
                  practice_notes: str = "") -> dict[str, Any]:
    """Stage a new or updated skill for explicit human approval."""
    if kill_switch_active():
        return {"success": False, "message": "Self-development is disabled by LUMEN_SELFDEV_DISABLED."}
    clean, error = _validate(name, description, instructions, sources,
                             practice_status, practice_notes)
    if error:
        return {"success": False, "message": error}

    skills = _load()
    pending = _load_pending()
    existing = next((item for item in skills if item.get("slug") == clean["slug"]), None)
    queued = next((item for item in pending if item.get("slug") == clean["slug"]), None)

    if queued:
        queued.update(clean)
        queued["updated_at"] = time.time()
        queued["target_skill_id"] = existing.get("id") if existing else queued.get("target_skill_id")
        write_json_atomic(_pending_file(), pending)
        return {
            "success": True,
            "pending_id": queued["id"],
            "skill": _metadata(queued),
            "proposal": {**_metadata(queued), "instructions": queued["instructions"]},
            "message": "Updated the pending skill proposal. It is still inactive until you approve it.",
        }

    if len(pending) >= MAX_PENDING_SKILLS:
        return {"success": False, "message": f"The pending skill limit ({MAX_PENDING_SKILLS}) has been reached."}

    now = time.time()
    item = {
        "id": uuid.uuid4().hex[:10],
        **clean,
        "target_skill_id": existing.get("id") if existing else None,
        "status": "pending_approval",
        "created_at": now,
        "updated_at": now,
    }
    pending.append(item)
    write_json_atomic(_pending_file(), pending)
    return {
        "success": True,
        "pending_id": item["id"],
        "skill": _metadata(item),
        "proposal": {**_metadata(item), "instructions": item["instructions"]},
        "message": (
            "Skill update staged for approval; the current active version is unchanged."
            if existing else
            "New skill staged for approval; it is not active yet."
        ),
    }


def _commit_skill(item: dict[str, Any]) -> dict[str, Any]:
    skills = _load()
    existing = next((skill for skill in skills
                     if skill.get("id") == item.get("target_skill_id")
                     or skill.get("slug") == item.get("slug")), None)
    now = time.time()
    if existing:
        history = list(existing.get("history", []))
        snapshot = {key: existing.get(key) for key in (
            "version", "name", "description", "instructions", "source_refs",
            "practice_status", "practice_notes", "updated_at"
        )}
        history.append(snapshot)
        existing.update({
            "name": item["name"],
            "description": item["description"],
            "instructions": item["instructions"],
            "source_refs": list(item.get("source_refs", [])),
            "practice_status": item.get("practice_status", "not_run"),
            "practice_notes": item.get("practice_notes", ""),
            "active": True,
            "version": int(existing.get("version", 1)) + 1,
            "updated_at": now,
            "history": history[-3:],
        })
        saved = existing
        message = "Approved and updated the existing skill. Its previous versions are retained in history."
    else:
        if len(skills) >= MAX_SKILLS:
            return {"success": False, "message": f"The active skill limit ({MAX_SKILLS}) has been reached."}
        saved = {
            "id": uuid.uuid4().hex[:10],
            "slug": item["slug"],
            "name": item["name"],
            "description": item["description"],
            "instructions": item["instructions"],
            "source_refs": list(item.get("source_refs", [])),
            "practice_status": item.get("practice_status", "not_run"),
            "practice_notes": item.get("practice_notes", ""),
            "active": True,
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "history": [],
        }
        skills.append(saved)
        message = "Approved and activated the new instruction-only skill."

    write_json_atomic(_skills_file(), skills)
    return {"success": True, "skill": _metadata(saved), "message": message}


def approve_skill(pending_id: str) -> dict[str, Any]:
    if kill_switch_active():
        return {"success": False, "message": "Self-development is disabled by LUMEN_SELFDEV_DISABLED."}
    pending = _load_pending()
    item = next((value for value in pending if value.get("id") == pending_id), None)
    if item is None:
        return {"success": False, "message": f"No pending skill proposal with ID {pending_id!r}."}
    result = _commit_skill(item)
    if not result.get("success"):
        return result
    pending = [value for value in pending if value.get("id") != pending_id]
    write_json_atomic(_pending_file(), pending)
    return result


def reject_skill(pending_id: str) -> dict[str, Any]:
    if kill_switch_active():
        return {"success": False, "message": "Self-development is disabled by LUMEN_SELFDEV_DISABLED."}
    pending = _load_pending()
    remaining = [item for item in pending if item.get("id") != pending_id]
    if len(remaining) == len(pending):
        return {"success": False, "message": f"No pending skill proposal with ID {pending_id!r}."}
    write_json_atomic(_pending_file(), remaining)
    return {"success": True, "message": f"Rejected and removed pending skill proposal {pending_id}."}


def list_pending_skills(include_instructions: bool = False) -> list[dict[str, Any]]:
    values = _load_pending()
    if include_instructions:
        return [{**_metadata(item), "instructions": item.get("instructions", "")}
                for item in values]
    return [_metadata(item) for item in values]


def save_skill(name: str, description: str, instructions: str,
               sources: Any = None, practice_status: str = "not_run",
               practice_notes: str = "") -> dict[str, Any]:
    """Backward-compatible direct save helper for trusted local callers/tests.

    The conversation action uses propose_skill instead, so agent-created skills
    always pass through approval before they become active.
    """
    if kill_switch_active():
        return {"success": False, "message": "Self-development is disabled by LUMEN_SELFDEV_DISABLED."}
    clean, error = _validate(name, description, instructions, sources or ["Current conversation"],
                             practice_status, practice_notes)
    if error:
        return {"success": False, "message": error}
    item = {**clean, "target_skill_id": None}
    result = _commit_skill(item)
    if result.get("success"):
        result["message"] = "Saved a trusted local instruction-only skill."
    return result


def list_skills(active_only: bool = False) -> list[dict[str, Any]]:
    values = _load()
    if active_only:
        values = [item for item in values if item.get("active", True)]
    return values


def view_skill(slug_or_id: str) -> dict[str, Any]:
    key = str(slug_or_id or "").strip()
    item = next((value for value in _load()
                 if value.get("id") == key or value.get("slug") == key
                 or standard_name(value.get("name", "")) == key.lower()), None)
    if item is None:
        return {"success": False, "message": f"No active skill found for {key!r}."}
    if not item.get("active", True):
        return {"success": False, "message": f"Skill {item.get('name')} is disabled."}
    return {"success": True, "skill": item, "message": "Loaded the full skill instructions."}


def set_skill_active(slug: str, active: bool) -> dict[str, Any]:
    skills = _load()
    for item in skills:
        if item.get("slug") == slug or item.get("id") == slug:
            item["active"] = bool(active)
            item["updated_at"] = time.time()
            write_json_atomic(_skills_file(), skills)
            return {"success": True, "message": f"Skill {item.get('name')} {'enabled' if active else 'disabled'}."}
    return {"success": False, "message": f"No skill with ID or slug {slug!r}."}


def to_skill_markdown(skill: dict[str, Any]) -> tuple[str, str]:
    """Return a standards-compatible SKILL.md filename and document."""
    name = standard_name(skill.get("slug") or skill.get("name") or "lumen-skill")
    description = " ".join(str(skill.get("description", "")).split())
    description = description.replace("\\", "\\\\").replace('"', '\\"')
    version = str(skill.get("version", 1))
    practice_status = str(skill.get("practice_status", "not_run"))
    body = (
        "---\n"
        f"name: {name}\n"
        f'description: "{description}"\n'
        "metadata:\n"
        "  author: lumen\n"
        f'  version: "{version}"\n'
        f'  practice_status: "{practice_status}"\n'
        "---\n\n"
        f"# {skill.get('name', 'Lumen Skill')}\n\n"
        f"{skill.get('description', '')}\n\n"
        "## Instructions\n\n"
        f"{str(skill.get('instructions', '')).strip()}\n"
    )
    return name, body
