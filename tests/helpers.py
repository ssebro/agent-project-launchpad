"""Small synthetic histories: tests never need a developer's actual sessions."""

import json
import sqlite3
from pathlib import Path

from agent_projects.config import Paths


def paths(root: Path) -> Paths:
    return Paths(root / "data", root / "codex", root / "claude")


def codex(home: Path, rows: list[tuple] | None = None) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    file = home / "state_5.sqlite"
    with sqlite3.connect(file) as db:
        db.execute("CREATE TABLE IF NOT EXISTS threads (id TEXT, title TEXT, cwd TEXT, "
                   "updated_at INTEGER, rollout_path TEXT, archived INTEGER, agent_role TEXT)")
        db.executemany("INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?)", rows or [])
    return file


def claude(home: Path, native_id: str, directory: Path, *, sidechain: bool = False,
           partial: bool = False) -> Path:
    root = home / "projects" / "synthetic-project"
    root.mkdir(parents=True, exist_ok=True)
    file = root / f"{native_id}.jsonl"
    event = dict(type="user", cwd=str(directory), sessionId=native_id,
                 isSidechain=sidechain, message={"content": "Build a small example"})
    file.write_text(json.dumps(event) + '\n' + ("{partial" if partial else ""))
    return file
