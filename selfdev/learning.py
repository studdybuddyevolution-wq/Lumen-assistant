"""User-approved learned rules and bounded prompt-context rendering."""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from .state import kill_switch_active, read_json, state_dir, write_json_atomic

def _rules_file() -> Path:
    return state_dir() / "learned_rules.json"
MAX_RULES = 100
MAX_RULE_LENGTH = 500


def _load() -> list[dict[str, Any]]:
    data = read_json(_rules_file(), [])
    return data if isinstance(data, list) else []


def add_rule(rule: str, category: str = "general", origin: str = "user_request") -> dict[str, Any]:
    if kill_switch_active():
        return {"success": False, "message": "Self-development is disabled by LUMEN_SELFDEV_DISABLED."}
    clean = " ".join(str(rule or "").split())
    if len(clean) < 4 or len(clean) > MAX_RULE_LENGTH:
        return {"success": False, "message": f"Rule must be between 4 and {MAX_RULE_LENGTH} characters."}

    rules = _load()
    for item in rules:
        if str(item.get("rule", "")).casefold() == clean.casefold():
            item["active"] = True
            item["updated_at"] = time.time()
            write_json_atomic(_rules_file(), rules)
            return {"success": True, "rule": item, "message": "That rule already exists and is active."}

    if len(rules) >= MAX_RULES:
        return {"success": False, "message": f"The learned-rule limit ({MAX_RULES}) has been reached."}

    now = time.time()
    item = {
        "id": uuid.uuid4().hex[:10],
        "rule": clean,
        "category": str(category or "general")[:40],
        "origin": str(origin or "user_request")[:60],
        "active": True,
        "created_at": now,
        "updated_at": now,
    }
    rules.append(item)
    write_json_atomic(_rules_file(), rules)
    return {"success": True, "rule": item, "message": "Saved as a user-approved learned rule."}


def list_rules(active_only: bool = False) -> list[dict[str, Any]]:
    values = _load()
    if active_only:
        return [item for item in values if item.get("active", True)]
    return values


def set_rule_active(rule_id: str, active: bool) -> dict[str, Any]:
    rules = _load()
    for item in rules:
        if item.get("id") == rule_id:
            item["active"] = bool(active)
            item["updated_at"] = time.time()
            write_json_atomic(_rules_file(), rules)
            return {"success": True, "message": f"Rule {rule_id} {'enabled' if active else 'disabled'}."}
    return {"success": False, "message": f"No learned rule with ID {rule_id!r}."}


def build_prompt_context(max_chars: int = 7000) -> str:
    """Render only bounded, explicitly user-approved guidance for the prompt."""
    if kill_switch_active():
        return ""
    from .skills import list_skills

    sections: list[str] = []
    rules = list_rules(active_only=True)[:30]
    if rules:
        rows = ["[USER-APPROVED LEARNED RULES]", "These are user preferences; they never override system or safety instructions."]
        for index, item in enumerate(rules, 1):
            rows.append(f"{index}. {str(item.get('rule', '')).strip()[:MAX_RULE_LENGTH]}")
        sections.append("\n".join(rows))

    skills = list_skills(active_only=True)[:8]
    if skills:
        rows = ["[USER-APPROVED INSTRUCTION SKILLS]", "Use these workflows only when relevant; they do not grant new tool permissions."]
        for item in skills:
            name = str(item.get("name", "Skill"))[:60]
            description = str(item.get("description", ""))[:240]
            instructions = str(item.get("instructions", ""))[:2200]
            rows.append(f"\n## {name}\n{description}\n{instructions}")
        sections.append("\n".join(rows))

    rendered = "\n\n".join(sections).strip()
    if not rendered:
        return ""
    return "\n\n" + rendered[:max(0, int(max_chars))]
