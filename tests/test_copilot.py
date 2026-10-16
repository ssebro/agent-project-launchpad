import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agent_launchpad.discovery import discover_copilot
from agent_launchpad.launch import build_command, executable, launch
from agent_launchpad.projects import Catalog
from helpers import codex, paths


def copilot(home: Path, session_id: str, directory: Path) -> Path:
    folder = home / "session-state" / session_id
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / "events.jsonl"
    events = [dict(type="session.start", data=dict(sessionId=session_id,
                                                   context=dict(cwd=str(directory)))),
              dict(type="user.message", data=dict(content="Improve the example"))]
    file.write_text('\n'.join(json.dumps(event) for event in events) + '\n{partial')
    return file


class CopilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = replace(paths(self.root), copilot=self.root / "copilot")

    def test_event_discovery_handles_partial_writes(self):
        file = copilot(self.paths.copilot, "one", self.root)
        before = file.read_bytes()
        session = discover_copilot(self.paths.copilot).sessions[0]
        self.assertEqual(session.title, "Improve the example")
        self.assertEqual(session.directory, self.root)
        self.assertEqual(file.read_bytes(), before)

    def test_missing_or_mismatched_identity(self):
        self.assertEqual(discover_copilot(None).sessions, [])
        file = copilot(self.paths.copilot, "one", self.root)
        file.write_text(file.read_text().replace('"sessionId": "one"', '"sessionId": "other"'))
        self.assertFalse(discover_copilot(self.paths.copilot).sessions)

    def test_command_uses_interactive_prompt_and_exact_session_id(self):
        args = build_command(["gh", "copilot", "--"], "copilot", "one", Path("/notes"))
        self.assertEqual(args[:6], ["gh", "copilot", "--", "--session-id", "one", "--interactive"])
        self.assertNotIn("--prompt", args)

    def test_gh_fallback(self):
        with patch("agent_launchpad.launch.shutil.which", side_effect=[None, "/bin/gh"]):
            self.assertEqual(executable("copilot"), ["/bin/gh", "copilot", "--"])

    def test_switch_to_copilot_then_resume(self):
        codex(self.paths.codex, [("one", "Example", str(self.root), 100, None, 0, None)])
        catalog = Catalog(self.paths)
        project = catalog.find("codex:one")
        def create(args, **_kwargs):
            copilot(self.paths.copilot, args[2], self.root)
            return 0
        with patch("agent_launchpad.launch.shutil.which", return_value="/fake/copilot"), \
             patch("agent_launchpad.launch.subprocess.call", side_effect=create) as call:
            launch(catalog, project, "copilot")
            native_id = call.call_args.args[0][2]
        project = catalog.find(project.id)
        self.assertEqual(project.sessions["copilot"].native_id, native_id)
        self.assertEqual(len(catalog.load()), 1)
