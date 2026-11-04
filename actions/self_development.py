"""User-controlled source-based skill learning and guarded code repair."""
from __future__ import annotations

import json

from selfdev.learning import add_rule, list_rules, set_rule_active
from selfdev.skills import (
    approve_skill,
    list_pending_skills,
    list_skills,
    propose_skill,
    reject_skill,
    set_skill_active,
    view_skill,
)
from selfdev.repair import list_proposals, propose_repair
from selfdev.state import kill_switch_active


def self_development(parameters: dict, **_context) -> str:
    """Dispatch one supported self-development operation and return JSON."""
    if kill_switch_active():
        return json.dumps({"success": False, "message": "Self-development is disabled by LUMEN_SELFDEV_DISABLED."})
    params = parameters if isinstance(parameters, dict) else {}
    operation = str(params.get("operation", "status")).strip().lower()
    try:
        if operation == "learn_rule":
            result = add_rule(params.get("rule", ""), params.get("category", "general"))
        elif operation == "disable_rule":
            result = set_rule_active(str(params.get("rule_id", "")), False)
        elif operation in {"create_skill", "propose_skill"}:
            name = str(params.get("skill_name", "") or params.get("goal", "")).strip()
            description = str(params.get("description", "") or params.get("goal", "")).strip()
            instructions = str(params.get("instructions", "")).strip()
            sources = params.get("source_refs", params.get("sources", ["Current conversation"]))
            if isinstance(sources, str):
                sources = [line.strip() for line in sources.splitlines() if line.strip()]
            if not instructions:
                result = {
                    "success": False,
                    "message": (
                        "Provide the completed skill instructions, source references, and honest practice status. "
                        "Research and practice first; this operation stages a proposal only and makes no extra model/API call."
                    ),
                }
            else:
                result = propose_skill(
                    name or "learned-workflow",
                    description or "User-approved reusable workflow",
                    instructions,
                    sources=sources,
                    practice_status=str(params.get("practice_status", "not_run")),
                    practice_notes=str(params.get("practice_notes", "")),
                )
        elif operation == "approve_skill":
            result = approve_skill(str(params.get("pending_id", "")))
        elif operation == "reject_skill":
            result = reject_skill(str(params.get("pending_id", "")))
        elif operation == "pending_skills":
            result = {"success": True, "pending_skills": list_pending_skills(include_instructions=True)}
        elif operation == "list_skills":
            result = {
                "success": True,
                "skills": [{k: v for k, v in item.items() if k not in {"instructions", "history"}}
                           for item in list_skills(active_only=bool(params.get("active_only", True)))],
            }
        elif operation == "view_skill":
            result = view_skill(str(params.get("skill_id", "")))
        elif operation == "disable_skill":
            result = set_skill_active(str(params.get("skill_id", "")), False)
        elif operation == "enable_skill":
            result = set_skill_active(str(params.get("skill_id", "")), True)
        elif operation == "propose_repair":
            result = propose_repair(str(params.get("file_path", "")), str(params.get("error_report", "")))
            result["message"] = "Repair proposal saved for review. No source file was changed. Use the local selfdev CLI to inspect and explicitly apply it."
        elif operation == "status":
            result = {
                "success": True,
                "learned_rules": list_rules(active_only=True),
                "skills": [{k: v for k, v in item.items() if k not in {"instructions", "history"}}
                           for item in list_skills(active_only=True)],
                "pending_skills": list_pending_skills(),
                "repair_proposals": list_proposals(),
                "apply_instructions": "Review code repairs with: python -m selfdev.cli show <id>; apply with: python -m selfdev.cli apply <id>.",
                "skill_learning": (
                    "Research sources, practice a small example, then stage a skill proposal. "
                    "It becomes active only after approve_skill. Full instructions load on demand with view_skill. "
                    "No separate Gemini/API generation call is made."
                ),
            }
        else:
            result = {"success": False, "message": f"Unsupported operation: {operation}"}
    except Exception as exc:
        result = {"success": False, "message": f"Self-development operation failed: {type(exc).__name__}: {exc}"}
    return json.dumps(result, ensure_ascii=False, default=str)


TOOL = {
    "name": "lumen_self_development",
    "description": (
        "User-controlled learning and guarded self-improvement. Operations: status, learn_rule, disable_rule, "
        "create_skill/propose_skill, pending_skills, approve_skill, reject_skill, list_skills, view_skill, "
        "enable_skill, disable_skill, propose_repair. For skill learning, research sources and practice a small "
        "example first, then create_skill stages a proposal with source references and honest verification notes. "
        "A staged skill is NOT active until the user explicitly approves it. Existing skills are updated in place "
        "with version history after approval; inspect them before proposing duplicates. Full instructions are "
        "loaded on demand through view_skill. Skills contain instructions only and do not grant new tool permissions. "
        "No extra Gemini/API call is made to create or store a skill. Code repair only saves a reviewed proposal."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "operation": {"type": "STRING", "enum": [
                "status", "learn_rule", "disable_rule", "create_skill", "propose_skill",
                "pending_skills", "approve_skill", "reject_skill", "list_skills",
                "view_skill", "enable_skill", "disable_skill", "propose_repair"
            ]},
            "rule": {"type": "STRING", "description": "A concise user preference or behavioral rule."},
            "category": {"type": "STRING", "description": "Optional grouping for a learned rule."},
            "rule_id": {"type": "STRING", "description": "ID of a learned rule to disable."},
            "goal": {"type": "STRING", "description": "Task or skill goal; used as a name/description fallback only."},
            "skill_name": {"type": "STRING", "description": "Short skill name."},
            "description": {"type": "STRING", "description": "When and for what task this skill should be used."},
            "instructions": {"type": "STRING", "description": "Complete focused skill procedure. Research and practice it before proposal."},
            "source_refs": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "URLs, local source paths, repository revision/licence, or 'Current conversation'."},
            "sources": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Alias for source_refs."},
            "practice_status": {"type": "STRING", "enum": ["verified", "partial", "not_run", "failed", "not_applicable"], "description": "Honest result of a small practical check."},
            "practice_notes": {"type": "STRING", "description": "Concrete test performed and its observed result; required for verified."},
            "pending_id": {"type": "STRING", "description": "Pending skill proposal ID to approve or reject."},
            "skill_id": {"type": "STRING", "description": "Active skill ID or slug to view, enable, or disable."},
            "active_only": {"type": "BOOLEAN", "description": "For list_skills, list only enabled skills (default true)."},
            "file_path": {"type": "STRING", "description": "Optional repository-relative Python file under actions/ or plugins/."},
            "error_report": {"type": "STRING", "description": "Error message, traceback, or repair description."},
        },
        "required": ["operation"],
    },
    "handler": self_development,
}
