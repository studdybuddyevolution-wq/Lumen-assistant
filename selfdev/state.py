"""Persistent state for Lumen's self-development features (outside the repo)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def kill_switch_active() -> bool:
    """Emergency environment-variable switch that disables learning and edits."""
    return os.environ.get("LUMEN_SELFDEV_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def state_dir() -> Path:
    """Return a per-user data directory without writing into the source tree."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "Lumen" / "selfdev"


def read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path, value: Any) -> None:
    """Write JSON via a same-directory temporary file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
