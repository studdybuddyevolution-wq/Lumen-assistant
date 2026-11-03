"""Human-gated repair proposals with path policy, hash checks, backups and rollback."""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from .state import kill_switch_active, read_json, state_dir, write_json_atomic

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_SOURCE_BYTES = 40_000
MAX_REPORT_CHARS = 6_000
ALLOWED_ROOTS = {"actions", "plugins"}
PROTECTED_PATHS = {
    "actions/self_development.py",
    "actions/dev_agent.py",
    "actions/code_helper.py",
    "core/gemini.py",
    "memory/config_manager.py",
    "main.py",
    "ui.py",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_target(relative_path: str, root: Path | None = None) -> Path:
    base = (root or PROJECT_ROOT).resolve()
    raw = str(relative_path or "").strip().replace("\\", "/")
    if not raw or "\x00" in raw:
        raise ValueError("Provide a repository-relative Python file path.")
    try:
        candidate = (base / raw).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError("Target file does not exist.") from exc
    try:
        relative = candidate.relative_to(base).as_posix()
    except ValueError as exc:
        raise ValueError("Target path is outside the Lumen project.") from exc
    parts = relative.split("/")
    if len(parts) < 2 or parts[0] not in ALLOWED_ROOTS:
        raise ValueError("Repairs are limited to Python files inside actions/ or plugins/.")
    if candidate.suffix.lower() != ".py" or not candidate.is_file():
        raise ValueError("Target must be an existing .py source file.")
    if any(part.startswith(".") or part in {"__pycache__", ".venv", "venv"} for part in parts):
        raise ValueError("Hidden folders, caches and virtual environments are not repair targets.")
    if relative in PROTECTED_PATHS:
        raise ValueError(f"{relative} is protected from self-editing.")
    if candidate.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError(f"Target file exceeds the {MAX_SOURCE_BYTES}-byte review limit.")
    return candidate


def _has_top_level_tool(source: str) -> bool:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "TOOL" for target in node.targets):
                return True
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "TOOL":
            return True
    return False


def _proposal_path(proposal_id: str) -> Path:
    clean = re.sub(r"[^a-f0-9]", "", str(proposal_id or "").lower())
    if len(clean) != 12:
        raise ValueError("Invalid proposal ID.")
    return state_dir() / "proposals" / f"{clean}.json"


def create_proposal(relative_path: str, candidate_source: str, summary: str = "") -> dict[str, Any]:
    """Store a candidate without changing the target file. Useful for tests too."""
    target = resolve_target(relative_path)
    original = target.read_text(encoding="utf-8")
    candidate = str(candidate_source or "")
    if not candidate.strip():
        raise ValueError("The generated replacement was empty.")
    if len(candidate.encode("utf-8")) > MAX_SOURCE_BYTES * 2:
        raise ValueError("The generated replacement exceeds the size limit.")
    ast.parse(candidate, filename=str(target))
    if _has_top_level_tool(original) and not _has_top_level_tool(candidate):
        raise ValueError("The candidate removed the action's module-level TOOL declaration.")
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True), candidate.splitlines(keepends=True),
        fromfile=f"a/{relative_path}", tofile=f"b/{relative_path}",
    ))
    if not diff:
        raise ValueError("The candidate is identical to the current file; no proposal was saved.")

    proposal_id = uuid.uuid4().hex[:12]
    item = {
        "id": proposal_id,
        "target": str(relative_path).replace("\\", "/"),
        "summary": " ".join(str(summary or "Suggested repair").split())[:300],
        "source_sha256": sha256_text(original),
        "candidate_sha256": sha256_text(candidate),
        "candidate_source": candidate,
        "diff": diff,
        "status": "pending_review",
        "created_at": time.time(),
        "backup_path": "",
        "applied_at": None,
    }
    write_json_atomic(_proposal_path(proposal_id), item)
    return {k: v for k, v in item.items() if k not in {"candidate_source"}}



def parse_traceback_target(problem_report: str) -> tuple[str | None, int | None]:
    """Find the innermost repair-eligible project frame in a Python traceback."""
    matches = re.findall(r"""File\s+["\']([^"\']+\.py)["\'],\s+line\s+(\d+)""", str(problem_report or ""), flags=re.IGNORECASE)
    for raw_path, raw_line in reversed(matches):
        candidate = Path(raw_path)
        try:
            if candidate.is_absolute():
                relative = candidate.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
            else:
                relative = candidate.as_posix()
            resolved = resolve_target(relative)
            return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix(), int(raw_line)
        except (ValueError, OSError):
            continue
    return None, None


def extract_ast_context(source: str, line_number: int, radius: int = 24) -> str:
    """Return the innermost enclosing function/class or a bounded line window."""
    lines = source.splitlines()
    try:
        tree = ast.parse(source)
        candidates = [node for node in ast.walk(tree)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and getattr(node, "lineno", 0) <= line_number <= getattr(node, "end_lineno", 0)]
        if candidates:
            node = min(candidates, key=lambda item: item.end_lineno - item.lineno)
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    except SyntaxError:
        pass
    start = max(0, line_number - radius - 1)
    end = min(len(lines), line_number + radius)
    return "\n".join(lines[start:end])


def propose_repair(relative_path: str, problem_report: str) -> dict[str, Any]:
    """Ask Lumen's existing Gemini ladder for a replacement; never apply it here."""
    if kill_switch_active():
        raise RuntimeError("Self-development is disabled by LUMEN_SELFDEV_DISABLED.")
    report = str(problem_report or "").strip()
    inferred_line = None
    if not str(relative_path or "").strip():
        relative_path, inferred_line = parse_traceback_target(report)
        if not relative_path:
            raise ValueError("No repair-eligible Lumen source file was found in the traceback. Provide file_path explicitly.")
    target = resolve_target(relative_path)
    original = target.read_text(encoding="utf-8")
    if not report:
        raise ValueError("Provide an error message, traceback, or clear description of the failure.")
    report = report[:MAX_REPORT_CHARS]

    context = extract_ast_context(original, inferred_line) if inferred_line else "(No source line was inferred.)"
    prompt = f"""You are proposing a narrowly scoped repair for the Lumen assistant.
Return exactly one complete replacement Python source file inside a single ```python fenced block.
Do not return a diff, explanation, or multiple alternatives.
Preserve existing public functions, imports that are still needed, and the module-level TOOL declaration when present.
Do not add third-party dependencies. Do not include secrets or credentials.
Do not add eval, exec, dynamic imports, shell commands, subprocess calls, network access, or filesystem deletion.
Make the smallest repair that addresses the report. If the report is insufficient, preserve behavior and add defensive validation rather than guessing.

TARGET: {relative_path}
PROBLEM REPORT:
{report}

FAILING FUNCTION / LOCAL AST CONTEXT:
```python
{context}
```

CURRENT SOURCE:
```python
{original}
```
"""
    from core import gemini

    generated = gemini.text(prompt, tier=gemini.SMART, timeout_ms=60_000, default="")
    if not generated:
        raise RuntimeError("Gemini did not return a repair candidate. The current file was not changed.")
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", generated, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Gemini's reply did not contain one complete Python code block. No file was changed.")
    return create_proposal(relative_path, match.group(1).strip() + "\n", report[:220])


def get_proposal(proposal_id: str) -> dict[str, Any]:
    path = _proposal_path(proposal_id)
    item = read_json(path, None)
    if not isinstance(item, dict):
        raise ValueError(f"Proposal {proposal_id!r} was not found or is unreadable.")
    return item


def list_proposals() -> list[dict[str, Any]]:
    folder = state_dir() / "proposals"
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = read_json(path, None)
        if isinstance(item, dict):
            items.append({k: v for k, v in item.items() if k not in {"candidate_source", "diff"}})
    return items


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def apply_proposal(proposal_id: str) -> dict[str, Any]:
    """Apply a reviewed proposal; caller (CLI) must obtain explicit confirmation."""
    if kill_switch_active():
        raise RuntimeError("Self-development is disabled by LUMEN_SELFDEV_DISABLED.")
    item = get_proposal(proposal_id)
    if item.get("status") != "pending_review":
        raise ValueError(f"Proposal status is {item.get('status')!r}, not pending_review.")
    target = resolve_target(item.get("target", ""))
    current = target.read_text(encoding="utf-8")
    if sha256_text(current) != item.get("source_sha256"):
        raise RuntimeError("The target file changed after this proposal was generated. Create a fresh proposal.")
    candidate = str(item.get("candidate_source", ""))
    ast.parse(candidate, filename=str(target))
    compile(candidate, str(target), "exec")
    if _has_top_level_tool(current) and not _has_top_level_tool(candidate):
        raise ValueError("Refusing to remove the action's TOOL declaration.")

    backup_dir = state_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{proposal_id}.bak"
    _atomic_write_text(backup, current)
    _atomic_write_text(target, candidate)

    item["status"] = "applied"
    item["backup_path"] = str(backup)
    item["applied_at"] = time.time()
    write_json_atomic(_proposal_path(proposal_id), item)
    return {"success": True, "message": f"Applied proposal {proposal_id} to {item['target']}; backup saved at {backup}."}


def rollback_proposal(proposal_id: str) -> dict[str, Any]:
    item = get_proposal(proposal_id)
    if item.get("status") != "applied":
        raise ValueError("Only an applied proposal can be rolled back.")
    target = resolve_target(item.get("target", ""))
    current = target.read_text(encoding="utf-8")
    if sha256_text(current) != item.get("candidate_sha256"):
        raise RuntimeError("The target has changed since the proposal was applied. Refusing to overwrite newer edits.")
    backup = Path(str(item.get("backup_path", ""))).resolve(strict=True)
    backup_root = (state_dir() / "backups").resolve()
    if not backup.is_relative_to(backup_root) or not backup.is_file():
        raise ValueError("The proposal backup is missing or outside the self-development backup folder.")
    original = backup.read_text(encoding="utf-8")
    ast.parse(original, filename=str(target))
    _atomic_write_text(target, original)
    item["status"] = "rolled_back"
    item["rolled_back_at"] = time.time()
    write_json_atomic(_proposal_path(proposal_id), item)
    return {"success": True, "message": f"Rolled back proposal {proposal_id} on {item['target']}."}
