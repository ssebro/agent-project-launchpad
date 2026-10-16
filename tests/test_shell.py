import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from agent_launchpad.cli import shell_init


class ShellTests(unittest.TestCase):
    def test_bash_and_zsh_forward_arguments_without_reparsing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('codex', 'claude', 'copilot', 'gh'):
                file = root / name
                file.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
                file.chmod(0o700)
            script = shell_init() + '\n' + 'gh api user --jq .login\ncodex "two words" "$(not-executed)"\n'
            # The last literal is escaped in the script, so argument forwarding
            # must not re-evaluate its contents through eval or another shell.
            script = script.replace('"$(not-executed)"', "'$(not-executed)'")
            for shell in ('bash', 'zsh'):
                binary = shutil.which(shell)
                if not binary:
                    continue
                result = subprocess.run([binary, '-c', script], text=True, capture_output=True,
                                        env={**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH']},
                                        timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(),
                                 ['api', 'user', '--jq', '.login', 'two words', '$(not-executed)'])
