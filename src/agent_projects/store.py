"""Versioned local metadata with atomic replacement and process locking.

Only our own files are written. Native agent databases are never mutated.
"""

import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def atomic_write(path: Path, content: str) -> None:
    """Replace a file atomically, with user-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".agent-projects-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    def __init__(self, root: Path):
        self.root = root

    def read(self) -> dict[str, Any]:
        path = self.root / "state.json"
        if not path.exists():
            return {"version": 1, "projects": {}, "forgotten": []}
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"Cannot read {path}; preserve it and repair its JSON: {exc}") from exc
        if not isinstance(state, dict) or state.get("version") != 1:
            raise ValueError(f"Unsupported state format in {path}; no changes made")
        if not isinstance(state.get("projects"), dict) or not isinstance(state.get("forgotten"), list):
            raise ValueError(f"Invalid state structure in {path}; no changes made")
        for key, project in state["projects"].items():
            if not isinstance(key, str) or not isinstance(project, dict):
                raise ValueError(f"Invalid project metadata in {path}")
            sessions = project.get("sessions", {})
            if not isinstance(sessions, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in sessions.items()
            ):
                raise ValueError(f"Invalid session links in {path}")
            lifecycle = project.get('lifecycle', 'active')
            if lifecycle not in ('active', 'completed', 'archived'):
                raise ValueError(f"Invalid project lifecycle in {path}")
            updates = project.get('completed_updates', {})
            if not isinstance(updates, dict) or any(
                not isinstance(k, str) or not isinstance(v, (int, float))
                for k, v in updates.items()
            ):
                raise ValueError(f"Invalid completion baseline in {path}")
        return state

    @contextmanager
    def edit(self) -> Iterator[dict[str, Any]]:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.root / "state.lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = self.read()
            yield state
            atomic_write(self.root / "state.json", json.dumps(state, indent=2) + "\n")

    def handoff(self, project_id: str) -> Path:
        # Never turn an external session ID into an unchecked path component.
        digest = hashlib.sha256(project_id.encode()).hexdigest()
        return self.root / "handoffs" / f"{digest}.md"

    def forget(self, project_id: str, sessions: dict[str, str]) -> None:
        with self.edit() as state:
            record = state["projects"].setdefault(project_id, {})
            record.setdefault("sessions", {}).update(sessions)
            if record.get("lifecycle") != "archived":
                record["previous_lifecycle"] = record.get("lifecycle", "active")
            record["lifecycle"] = "archived"
            record["hidden"] = True
            state["forgotten"] = [i for i in state["forgotten"] if i != project_id] + [project_id]

    def restore(self, project_id: str | None = None) -> str | None:
        with self.edit() as state:
            if project_id is None:
                project_id = next(iter(reversed(state["forgotten"])), None)
            if project_id is None:
                return None
            if project_id not in state["projects"]:
                raise ValueError(f"Unknown project: {project_id}")
            record = state["projects"][project_id]
            if not record.get('hidden') and record.get('lifecycle') != 'archived':
                return project_id
            record["hidden"] = False
            record["lifecycle"] = record.pop("previous_lifecycle", "active")
            state["forgotten"] = [i for i in state["forgotten"] if i != project_id]
            return project_id
