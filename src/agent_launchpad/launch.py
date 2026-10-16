"""Use documented CLI arguments; never shell-interpolate project content."""

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from .context import create_packet
from .discovery import discover_claude, discover_codex, discover_copilot
from .models import AGENTS, Project
from .projects import Catalog


def handoff_prompt(file: Path, packet: Path | None = None) -> str:
    return (
        f"Resume this project. First read the shared handoff at {file}. "
        + (f"Also read the freshly generated context packet at {packet}; it records recent dialogue, "
           "source timestamps, and context gaps. Reconcile the latest evidence with the handoff. "
           if packet else '') +
        "Read the source files it identifies where needed. Your native conversation may be "
        "older than the handoff; reconcile differences before acting. Keep this handoff updated "
        "with Status, findings, decisions, changed files, validation, and next steps before "
        "finishing each turn. Do not claim to know the other tool's history unless you read it."
    )


def executable(agent: str) -> list[str]:
    if agent not in AGENTS:
        raise ValueError(f"Unsupported agent: {agent}")
    binary = shutil.which(agent)
    if not binary and agent == "copilot":
        gh = shutil.which("gh")
        if gh:
            return [gh, "copilot", "--"]
    if not binary:
        raise ValueError(f"{agent} is not on PATH. Install it or select the other tool with Tab.")
    return [binary]


def build_command(binary: str | list[str], agent: str, native_id: str | None, file: Path,
                  new_id: str | None = None, packet: Path | None = None) -> list[str]:
    if agent not in AGENTS:
        raise ValueError(f"Unsupported agent: {agent}")
    if native_id is not None and (not native_id or native_id.startswith("-")):
        raise ValueError("Invalid native session identity; refusing to treat it as a CLI flag")
    args = [binary] if isinstance(binary, str) else list(binary)
    if agent == "copilot":
        args += ["--session-id", native_id or new_id] if native_id or new_id else []
        return args + ["--interactive", handoff_prompt(file, packet)]
    if native_id:
        args += ["resume", native_id] if agent == "codex" else ["--resume", native_id]
    elif agent == "claude" and new_id:
        args += ["--session-id", new_id]
    args += [handoff_prompt(file, packet)]
    return args


def launch(catalog: Catalog, project: Project | None, agent: str) -> int:
    binary = executable(agent)
    if project is None:
        return subprocess.call(binary)
    directory = project.directory
    if directory is None or not directory.is_dir():
        raise ValueError(
            f"Project directory is unavailable: {directory or 'not recorded'}. "
            "Use the agent's own resume command, or restore that directory first."
        )
    file = catalog.prepare(project)
    # Native identities are pinned under the metadata lock. No lock is held
    # while an interactive agent runs, which could take hours.
    with catalog.store.edit() as state:
        record = state["projects"].setdefault(project.id, {})
        record["lifecycle"] = "active"
        record["hidden"] = False
        record.pop("completed_updates", None)
        state["forgotten"] = [i for i in state["forgotten"] if i != project.id]
        links = record.setdefault("sessions", {})
        links.update({a: s.native_id for a, s in project.sessions.items()})
        native_id = links.get(agent)
        pending_key = f"pending_{agent}_id"
        discover = {"claude": lambda: discover_claude(catalog.paths.claude),
                    "copilot": lambda: discover_copilot(catalog.paths.copilot)}
        pending = record.get(pending_key) if agent in discover else None
        if pending and any(s.native_id == pending for s in discover[agent]().sessions):
            native_id = links[agent] = record.pop(pending_key)
        new_id = None
        if agent in discover and not native_id:
            new_id = pending or str(uuid.uuid4())
            record[pending_key] = new_id
    before = {s.native_id for s in discover_codex(catalog.paths.codex).sessions}
    # Own-process launches for this project/tool must not race to associate a
    # new native session. OS locks also recover automatically after a crash.
    import fcntl

    lock_path = file.with_suffix(f".{agent}.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(f"This project is already open through this launcher in {agent}.") from exc
        packet = create_packet(catalog, catalog.find(project.id))
        returncode = subprocess.call(
            build_command(binary, agent, native_id, file, new_id, packet), cwd=directory,
        )
        with catalog.store.edit() as state:
            record = state["projects"].setdefault(project.id, {})
            links = record.setdefault("sessions", {})
            if agent in discover and new_id:
                if any(s.native_id == new_id for s in discover[agent]().sessions):
                    links[agent] = new_id
                    record.pop(pending_key, None)
            elif agent == "codex" and not native_id:
                candidates = [
                    s for s in discover_codex(catalog.paths.codex).sessions
                    if s.native_id not in before and s.directory is not None
                    and s.directory.resolve() == directory.resolve()
                ]
                if len(candidates) == 1:
                    candidate = candidates[0].native_id
                    claimed = any(
                        r.get("sessions", {}).get("codex") == candidate
                        for key, r in state["projects"].items() if key != project.id
                    )
                    if not claimed:
                        links["codex"] = candidate
                else:
                    print("Could not uniquely link the new Codex conversation. "
                          "The handoff is preserved; native history remains available.")
    return returncode
