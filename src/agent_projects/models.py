"""Types shared by discovery, persistence, launch, and presentation."""

from dataclasses import dataclass, field
from pathlib import Path

AGENTS = ("codex", "claude", "copilot")


@dataclass(frozen=True)
class Session:
    agent: str
    native_id: str
    title: str
    directory: Path | None
    updated: float
    transcript: Path | None = None

    @property
    def key(self) -> str:
        return f"{self.agent}:{self.native_id}"


@dataclass
class Project:
    id: str
    title: str
    status: str
    directory: Path | None
    updated: float
    sessions: dict[str, Session] = field(default_factory=dict)
    hidden: bool = False
    detail: str = ""


@dataclass
class Discovery:
    sessions: list[Session] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
