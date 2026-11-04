"""Optional local bridge from Lumen to the Barehands hand-tracked board.

Barehands is installed as a separate upstream checkout under integrations/.
This action talks only to its documented loopback HTTP endpoints; it does not
call an AI service, use credentials, or execute the upstream shell scripts.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = BASE_DIR / "integrations" / "barehands"
_ALLOWED_ENDPOINTS = {"/config", "/state", "/cmd"}
_ALLOWED_MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".webm", ".glb", ".gltf"}
# Bypass system HTTP proxies so even a misconfigured proxy cannot route these
# local-control requests off the machine.
_LOCAL_HTTP = build_opener(ProxyHandler({}))


def _barehands_root() -> Path | None:
    configured = os.environ.get("LUMEN_BAREHANDS_DIR", "").strip()
    candidate = Path(configured).expanduser() if configured else DEFAULT_ROOT
    try:
        root = candidate.resolve(strict=True)
    except OSError:
        return None
    if not root.is_dir() or not (root / "server.py").is_file() or not (root / "stage.html").is_file():
        return None
    return root


def _config(root: Path) -> dict:
    path = root / "barehands.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("barehands.json must contain a JSON object.")
    return data


def _port(root: Path) -> int:
    value = _config(root).get("port", 8794)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError("The Barehands port must be an integer from 1 to 65535.")
    return value


def _media_root(root: Path) -> Path:
    cfg = _config(root)
    media_orb = next(
        (orb for orb in cfg.get("orbs", [])
         if isinstance(orb, dict) and orb.get("kind") == "media"),
        None,
    )
    raw = str(media_orb.get("path") or "media") if media_orb else "media"
    path = Path(raw).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _request(root: Path, method: str, endpoint: str, payload: dict | None = None,
             timeout: float = 2.5):
    if endpoint not in _ALLOWED_ENDPOINTS:
        raise ValueError("Unsupported Barehands endpoint.")
    port = _port(root)
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(
        f"http://127.0.0.1:{port}{endpoint}",
        data=body,
        headers=headers,
        method=method,
    )
    with _LOCAL_HTTP.open(request, timeout=timeout) as response:
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Barehands returned an unexpectedly large response.")
        return json.loads(raw.decode("utf-8")) if raw else None


def _is_online(root: Path) -> bool:
    try:
        return isinstance(_request(root, "GET", "/config"), dict)
    except Exception:
        return False


def _start_server(root: Path) -> None:
    if sys.platform == "win32":
        launcher = root / "run.bat"
        if not launcher.is_file():
            raise FileNotFoundError("Barehands run.bat is missing.")
        # Keep the server console visible so the user can see errors and stop it.
        os.startfile(str(launcher))  # type: ignore[attr-defined]
        return

    log_path = Path(tempfile.gettempdir()) / "lumen-barehands.log"
    with log_path.open("ab") as log:
        subprocess.Popen(
            [sys.executable, str(root / "server.py")],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )


def _safe_media_src(root: Path, value: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        raise ValueError("Use a path relative to Barehands' configured media folder.")
    if raw.startswith("media/"):
        raw = raw[6:]
    rel = PurePosixPath(raw)
    if not raw or any(part in ("", ".", "..") or part.startswith(".") for part in rel.parts):
        raise ValueError("The media path must be a normal relative path inside the media folder.")
    if rel.suffix.lower() not in _ALLOWED_MEDIA_EXTS:
        raise ValueError("Supported media: PNG, JPG, WEBP, GIF, WEBM, GLB and GLTF.")
    media = _media_root(root)
    target = media.joinpath(*rel.parts).resolve()
    if media not in target.parents or not target.is_file():
        raise ValueError("That file does not exist inside Barehands' configured media folder.")
    return rel.as_posix()


def _fraction(value, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number between 0 and 1.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number between 0 and 1.")
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be a number between 0 and 1.")
    return number


def _build_command(root: Path, operation: str, params: dict) -> dict:
    if operation in ("present", "add_card"):
        title = str(params.get("title", "")).strip()
        body = str(params.get("body", "")).strip()
        if not title:
            raise ValueError("Provide a title for the board card.")
        if len(title) > 120 or len(body) > 4000:
            raise ValueError("Board card text is too long (title max 120, body max 4000 characters).")
        command = {"a": operation, "title": title, "body": body}
        for key in ("x", "y"):
            if key in params:
                command[key] = _fraction(params[key], key)
        return command
    if operation == "add_image":
        return {"a": "add_img", "src": _safe_media_src(root, params.get("src", ""))}
    if operation in ("clear", "reset"):
        return {"a": operation}
    raise ValueError("Unsupported board operation.")


def _summarize_state(state) -> str:
    if not isinstance(state, dict) or "items" not in state:
        return "The server is running, but the tracker page has not sent a board snapshot yet."
    items = state.get("items")
    if not isinstance(items, list):
        return "The tracker returned an unreadable board snapshot."
    if not items:
        return "The Barehands board is currently empty."
    lines = [f"The board currently has {len(items)} item(s):"]
    for item in items[:25]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "item")
        title = str(item.get("title") or item.get("src") or "untitled").replace("\n", " ")[:100]
        body = str(item.get("body") or "").replace("\n", " ")[:140]
        line = f"- {kind}: {title}"
        if body:
            line += f" — {body}"
        lines.append(line)
    if len(items) > 25:
        lines.append(f"- …and {len(items) - 25} more")
    return "\n".join(lines)


def barehands_control(parameters: dict, **_context) -> str:
    """Control the optional Barehands board through its local HTTP API."""
    if os.environ.get("LUMEN_BAREHANDS_DISABLED", "").strip() == "1":
        return json.dumps({"success": False, "message": "Barehands integration is disabled by LUMEN_BAREHANDS_DISABLED=1."})

    params = parameters if isinstance(parameters, dict) else {}
    operation = str(params.get("operation", "status")).strip().lower()
    root = _barehands_root()
    if root is None:
        return json.dumps({
            "success": False,
            "message": "Barehands is not installed in the expected folder. Follow BAREHANDS_INTEGRATION.md, or set LUMEN_BAREHANDS_DIR to its folder.",
            "expected_folder": str(DEFAULT_ROOT),
        })

    try:
        port = _port(root)
        base_url = f"http://127.0.0.1:{port}"
        if operation == "status":
            online = _is_online(root)
            name = "Barehands"
            if online:
                config = _request(root, "GET", "/config")
                name = str(config.get("name") or name)
            return json.dumps({
                "success": True,
                "installed": True,
                "running": online,
                "url": f"{base_url}/stage.html",
                "name": name,
                "message": "Barehands is responding locally." if online else "Barehands is installed but not running.",
            })
        if operation == "start":
            if not _is_online(root):
                _start_server(root)
                deadline = time.monotonic() + 8.0
                while time.monotonic() < deadline and not _is_online(root):
                    time.sleep(0.25)
            online = _is_online(root)
            return json.dumps({
                "success": online,
                "running": online,
                "url": f"{base_url}/stage.html",
                "message": (
                    "Barehands is running. Open the stage in Chrome and allow camera access."
                    if online else
                    "Barehands was launched but did not respond yet. Check its visible server window or the lumen-barehands.log file."
                ),
            })
        if operation == "open":
            if not _is_online(root):
                return json.dumps({"success": False, "message": "Barehands is not running. Run the start operation first."})
            url = f"{base_url}/stage.html"
            opened = bool(webbrowser.open(url, new=2))
            return json.dumps({
                "success": opened,
                "url": url,
                "message": "Opened Barehands. Chrome is recommended; allow camera access." if opened else f"Open this URL manually in Chrome: {url}",
            })
        if operation == "board_state":
            if not _is_online(root):
                return json.dumps({"success": False, "message": "Barehands is not running."})
            state = _request(root, "GET", "/state")
            return json.dumps({"success": True, "board": _summarize_state(state)})
        if operation in ("present", "add_card", "add_image", "clear", "reset"):
            if not _is_online(root):
                return json.dumps({"success": False, "message": "Barehands is not running. Start it before sending board commands."})
            command = _build_command(root, operation, params)
            _request(root, "POST", "/cmd", command)
            return json.dumps({"success": True, "operation": operation, "message": "Barehands accepted the board command."})
        return json.dumps({
            "success": False,
            "message": "Supported operations: status, start, open, present, add_card, add_image, board_state, clear, reset.",
        })
    except HTTPError as exc:
        return json.dumps({"success": False, "message": f"Barehands rejected the request (HTTP {exc.code}). Check the media path or command."})
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return json.dumps({"success": False, "message": f"Barehands operation failed: {type(exc).__name__}: {exc}"})


TOOL = {
    "name": "barehands_control",
    "description": (
        "Control Lumen's optional Barehands local webcam/hand-gesture board. "
        "Use status/start/open to manage the board; when the user asks to SEE or present something, "
        "use present or add_card; use add_image only for a file already inside Barehands' configured "
        "media folder; use board_state before describing what is currently on the board. "
        "Operations: status, start, open, present, add_card, add_image, board_state, clear, reset. "
        "This action contacts only 127.0.0.1 and makes no AI/API calls."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "operation": {"type": "STRING", "enum": [
                "status", "start", "open", "present", "add_card",
                "add_image", "board_state", "clear", "reset"
            ]},
            "title": {"type": "STRING", "description": "Short title for present or add_card."},
            "body": {"type": "STRING", "description": "Text for a present or add_card."},
            "src": {"type": "STRING", "description": "Relative path of an existing image or model inside Barehands' configured media folder."},
            "x": {"type": "NUMBER", "description": "Optional horizontal position from 0 to 1."},
            "y": {"type": "NUMBER", "description": "Optional vertical position from 0 to 1."}
        },
        "required": ["operation"]
    },
    "handler": barehands_control,
}
