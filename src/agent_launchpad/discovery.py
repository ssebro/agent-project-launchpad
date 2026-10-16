"""Best-effort, read-only adapters for native local session formats.

These formats are not stable public APIs. Keep compatibility handling here and
report problems instead of silently treating inaccessible history as empty.
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from .activity import is_handoff_title
from .models import Discovery, Session


def timestamp(value: object, default: float = 0) -> float:
    try:
        if isinstance(value, (float, int)):
            return float(value)
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, OverflowError):
        pass
    return default


def optional_path(value: object) -> Path | None:
    return Path(value) if isinstance(value, str) and value else None


def discover_codex(home: Path) -> Discovery:
    result = Discovery()
    databases = sorted(
        (p for p in home.glob("state_*.sqlite") if re.fullmatch(r"state_\d+", p.stem)),
        key=lambda p: int(p.stem.split("_")[1]),
        reverse=True,
    )
    if databases:
        try:
            uri = databases[0].resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=2) as db:
                db.row_factory = sqlite3.Row
                columns = {r[1] for r in db.execute("PRAGMA table_info(threads)")}
                if not {"id", "cwd", "updated_at"}.issubset(columns):
                    raise ValueError("unrecognized threads schema")
                filters = []
                if "archived" in columns:
                    filters.append("archived = 0")
                if "agent_role" in columns:
                    filters.append("agent_role IS NULL")
                where = " WHERE " + " AND ".join(filters) if filters else ""
                for row in db.execute("SELECT * FROM threads" + where):
                    data = dict(row)
                    native_id = data.get("id")
                    if not isinstance(native_id, str) or not native_id:
                        continue
                    result.sessions.append(Session(
                        "codex", native_id,
                        str(data.get("name") or data.get("title") or "Untitled Codex conversation"),
                        optional_path(data.get("cwd")), timestamp(data.get("updated_at")),
                        optional_path(data.get("rollout_path")),
                    ))
            return result
        except (OSError, sqlite3.Error, ValueError) as exc:
            result.sessions.clear()
            result.warnings.append(f"Codex database: {exc}; trying session index")
    index = home / "session_index.jsonl"
    if index.exists():
        latest = {}
        try:
            with index.open(encoding="utf-8") as stream:
                for line in stream:
                    try:
                        item = json.loads(line)
                        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                            continue
                        latest[item["id"]] = Session(
                            "codex", item["id"], str(item.get("thread_name") or "Untitled"),
                            optional_path(item.get("cwd")), timestamp(item.get("updated_at")),
                        )
                    except ValueError:
                        continue  # A writer may be midway through the last line.
            result.sessions.extend(latest.values())
        except (OSError, UnicodeError) as exc:
            result.warnings.append(f"Codex index: {exc}")
    return result


def discover_claude(home: Path) -> Discovery:
    result = Discovery()
    for file in sorted((home / "projects").glob("*/*.jsonl")):
        if file.stem.startswith("agent-"):
            continue
        try:
            title, directory, native_id = "", None, ""
            updated = file.stat().st_mtime
            has_main = False
            with file.open(encoding="utf-8") as stream:
                for line in stream:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(event, dict) or event.get("isSidechain"):
                        continue
                    if event.get("type") in ("user", "assistant"):
                        has_main = True
                        directory = optional_path(event.get("cwd")) or directory
                        native_id = event.get("sessionId") or native_id
                    if event.get("type") == "summary" and event.get("summary"):
                        if not is_handoff_title(str(event['summary'])):
                            title = str(event["summary"])
                    elif not title and event.get("type") == "user":
                        message = event.get("message", {})
                        content = message.get("content") if isinstance(message, dict) else None
                        if (isinstance(content, str) and not content.startswith("<")
                                and not is_handoff_title(content)):
                            title = content[:200]
            if has_main:
                # The UUID filename is the native session identifier. Do not link
                # a transcript whose events claim a different identity.
                if native_id and native_id != file.stem:
                    result.warnings.append(f"Claude identity mismatch: {file.name}; skipped")
                    continue
                result.sessions.append(Session(
                    "claude", file.stem, title or "Untitled Claude conversation",
                    directory, updated, file,
                ))
        except (OSError, UnicodeError) as exc:
            result.warnings.append(f"Claude transcript {file.name}: {exc}")
    return result


def discover_copilot(home: Path | None) -> Discovery:
    """Read current Copilot CLI event logs; legacy gh-copilot has no such sessions."""
    result = Discovery()
    if home is None:
        return result
    for file in sorted((home / "session-state").glob("*/events.jsonl")):
        try:
            title, directory, native_id = "", None, ""
            updated = file.stat().st_mtime
            started = False
            with file.open(encoding="utf-8") as stream:
                for line in stream:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(event, dict) or event.get("agentId"):
                        continue
                    data = event.get("data", {})
                    if not isinstance(data, dict):
                        continue
                    if event.get("type") == "session.start":
                        started = True
                        native_id = data.get("sessionId") or native_id
                        context = data.get("context", {})
                        if isinstance(context, dict):
                            directory = optional_path(context.get("cwd")) or directory
                    elif event.get("type") == "user.message" and not title:
                        content = data.get("content")
                        if isinstance(content, str) and not is_handoff_title(content):
                            title = content[:200]
            if not started:
                continue
            if native_id and native_id != file.parent.name:
                result.warnings.append(f"Copilot identity mismatch: {file.parent.name}; skipped")
                continue
            result.sessions.append(Session(
                "copilot", file.parent.name, title or "Untitled Copilot conversation",
                directory, updated, file,
            ))
        except (OSError, UnicodeError) as exc:
            result.warnings.append(f"Copilot transcript {file.parent.name}: {exc}")
    return result
