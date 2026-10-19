import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_launchpad.cli import main
from agent_launchpad.integration import START, configure, shell_name, startup_file


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rc = self.root / '.bashrc'
        self.launcher = self.root / "bin with spaces" / "agent-launchpad"
        self.launcher.parent.mkdir()
        self.launcher.write_text('#!/bin/sh\nprintf "codex() { :; }\\n"\n')
        self.launcher.chmod(0o700)

    def test_setup_is_idempotent_backed_up_and_preserves_mode(self):
        original = '# Existing configuration\nexport EXAMPLE=value\n'
        self.rc.write_text(original)
        self.rc.chmod(0o640)
        result = configure('bash', self.rc, self.launcher)
        self.assertTrue(result.changed)
        self.assertEqual(result.backup.read_text(), original)
        self.assertEqual(result.backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.rc.stat().st_mode & 0o777, 0o640)
        installed = self.rc.read_text()
        self.assertTrue(installed.startswith(original))
        self.assertEqual(installed.count(START), 1)
        self.assertIn(str(self.launcher), installed)
        self.assertFalse(configure('bash', self.rc, self.launcher).changed)
        self.assertEqual(self.rc.read_text(), installed)

    def test_uninstall_removes_only_managed_block(self):
        original = 'export BEFORE=1\n'
        self.rc.write_text(original)
        configure('bash', self.rc, self.launcher)
        with self.rc.open('a') as stream:
            stream.write('export AFTER=2\n')
        result = configure('bash', self.rc, None, remove=True)
        self.assertTrue(result.changed)
        self.assertEqual(self.rc.read_text(), original + 'export AFTER=2\n')

    def invoke_uninstall(self, *options):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(['uninstall', '--shell', 'bash', '--rc-file', str(self.rc), *options])
        return code, output.getvalue()

    def test_uninstall_command_preserves_user_config_and_data_and_is_repeatable(self):
        self.rc.write_text('export USER_SETTING=1\n')
        configure('bash', self.rc, self.launcher)
        notes = self.root / 'notes.md'
        notes.write_text('Saved work')
        code, output = self.invoke_uninstall()
        self.assertEqual(code, 0)
        self.assertEqual(self.rc.read_text(), 'export USER_SETTING=1\n')
        self.assertEqual(notes.read_text(), 'Saved work')
        self.assertIn('Backup:', output)
        self.assertIn('pipx uninstall agent-project-launchpad', output)
        self.assertIn('package is still installed', output)
        self.assertIn('Already removed:', self.invoke_uninstall()[1])

    def test_uninstall_command_dry_run_leaves_managed_block_untouched(self):
        configure('bash', self.rc, self.launcher)
        before = self.rc.read_bytes()
        code, output = self.invoke_uninstall('--dry-run')
        self.assertEqual(code, 0)
        self.assertIn('Would remove integration', output)
        self.assertNotIn('To finish removing', output)
        self.assertEqual(self.rc.read_bytes(), before)

    def test_dry_run_does_not_create_files_or_parent_directories(self):
        rc = self.root / 'missing' / '.bashrc'
        result = configure('bash', rc, self.launcher, dry_run=True)
        self.assertTrue(result.changed)
        self.assertIn(START, result.preview)
        self.assertFalse(rc.parent.exists())

    def test_symlink_is_preserved(self):
        target = self.root / 'dotfiles' / 'bashrc'
        target.parent.mkdir()
        target.write_text('# managed by user\n')
        self.rc.symlink_to(target)
        configure('bash', self.rc, self.launcher)
        self.assertTrue(self.rc.is_symlink())
        self.assertIn(START, target.read_text())

    def test_incomplete_markers_are_not_overwritten(self):
        self.rc.write_text(START + '\n# unfinished\n')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            configure('bash', self.rc, self.launcher)
        self.assertEqual(self.rc.read_text(), START + '\n# unfinished\n')

    def test_crlf_startup_is_not_silently_rewritten_or_given_broken_shell_code(self):
        self.rc.write_bytes(b'# example\r\n')
        with self.assertRaisesRegex(ValueError, 'CRLF'):
            configure('bash', self.rc, self.launcher)
        self.assertEqual(self.rc.read_bytes(), b'# example\r\n')

    def test_reinstall_replaces_old_executable_path(self):
        configure('bash', self.rc, self.launcher)
        newer = self.root / 'new-bin' / 'agent-launchpad'
        newer.parent.mkdir()
        newer.write_bytes(self.launcher.read_bytes())
        newer.chmod(0o700)
        configure('bash', self.rc, newer)
        self.assertEqual(self.rc.read_text().count(START), 1)
        self.assertNotIn(str(self.launcher), self.rc.read_text())

    def test_broken_launcher_does_not_touch_startup(self):
        self.rc.write_text('# original\n')
        self.launcher.write_text('#!/bin/sh\nexit 1\n')
        with self.assertRaisesRegex(ValueError, 'generate'):
            configure('bash', self.rc, self.launcher)
        self.assertEqual(self.rc.read_text(), '# original\n')

    def test_shell_detection_and_profile_selection(self):
        self.assertEqual(shell_name('/bin/zsh'), 'zsh')
        with self.assertRaises(ValueError):
            shell_name('fish')
        with patch.dict(os.environ, {'ZDOTDIR': str(self.root / 'zsh')}):
            self.assertEqual(startup_file('zsh', self.root), self.root / 'zsh' / '.zshrc')
        (self.root / '.profile').write_text('# existing login configuration\n')
        with patch('sys.platform', 'darwin'):
            self.assertEqual(startup_file('bash', self.root), self.root / '.profile')
        with patch('sys.platform', 'linux'):
            self.assertEqual(startup_file('bash', self.root), self.rc)
