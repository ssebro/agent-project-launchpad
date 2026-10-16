"""Paths are configurable; personal data lives outside the installed package."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    data: Path
    codex: Path
    claude: Path
    copilot: Path | None = None

    @classmethod
    def from_env(cls) -> "Paths":
        home = Path.home()
        state = Path(os.environ.get("XDG_STATE_HOME", str(home / ".local/state")))
        default_data = state / 'agent-launchpad'
        legacy_data = state / 'agent-projects'
        if not default_data.exists() and legacy_data.exists():
            default_data = legacy_data
        return cls(
            Path(os.environ.get('AGENT_LAUNCHPAD_HOME') or
                 os.environ.get("AGENT_PROJECTS_HOME", str(default_data))).expanduser(),
            Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser(),
            Path(os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))).expanduser(),
            Path(os.environ.get("COPILOT_HOME", str(home / ".copilot"))).expanduser(),
        )
