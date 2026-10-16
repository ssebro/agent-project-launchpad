"""Exercise the installed-style CLI and a real child process, with no model calls."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import codex, paths


class IntegrationTests(unittest.TestCase):
    def test_fresh_cross_tool_launch_and_resume_via_real_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = paths(root)
            codex(config.codex, [("one", "Synthetic task", directory, 100, None, 0, None)])
            bin_dir = root / "bin"
            bin_dir.mkdir()
            stub = bin_dir / "claude"
            stub.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
session_id = args[1]
home = pathlib.Path(os.environ['CLAUDE_CONFIG_DIR'])
folder = home / 'projects' / 'example'
folder.mkdir(parents=True, exist_ok=True)
event = dict(type='user', cwd=os.getcwd(), sessionId=session_id,
             message=dict(content='Synthetic agent handoff'))
(folder / (session_id + '.jsonl')).write_text(json.dumps(event) + '\\n')
with (home.parent / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps(dict(args=args, cwd=os.getcwd())) + '\\n')
''')
            stub.chmod(0o700)
            environment = {
                **os.environ,
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                "AGENT_PROJECTS_HOME": str(config.data),
                "CODEX_HOME": str(config.codex),
                "CLAUDE_CONFIG_DIR": str(config.claude),
                "COPILOT_HOME": str(root / "copilot"),
            }
            command = [sys.executable, "-m", "agent_launchpad", "--agent", "claude",
                       "resume", "codex:one"]
            for _ in range(2):
                result = subprocess.run(command, env=environment, cwd=root, text=True,
                                        capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
            calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
            self.assertEqual(calls[0]["args"][0], "--session-id")
            self.assertEqual(calls[1]["args"][0], "--resume")
            self.assertEqual(calls[0]["args"][1], calls[1]["args"][1])
            self.assertEqual(Path(calls[0]["cwd"]).resolve(), root.resolve())
            self.assertIn("shared handoff", calls[0]["args"][-1])
            state = json.loads((config.data / "state.json").read_text())
            self.assertIn("claude", state["projects"]["codex:one"]["sessions"])
