import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_launchpad.launch import build_command, launch
from agent_launchpad.projects import Catalog
from helpers import claude, codex, paths


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = paths(self.root)
        codex(self.paths.codex, [("one", "Example", str(self.root), 100, None, 0, None)])
        self.catalog = Catalog(self.paths)
        self.project = self.catalog.find("codex:one")

    def test_commands_are_argument_lists_without_shell_interpolation(self):
        file = Path('/tmp/notes with spaces/$(unsafe).md')
        args = build_command("/bin/codex", "codex", "one", file)
        self.assertEqual(args[:3], ["/bin/codex", "resume", "one"])
        self.assertIn(str(file), args[-1])
        args = build_command("/bin/claude", "claude", None, file, "new-id")
        self.assertEqual(args[:3], ["/bin/claude", "--session-id", "new-id"])

    def test_session_identity_cannot_inject_flags(self):
        with self.assertRaisesRegex(ValueError, "CLI flag"):
            build_command("codex", "codex", "--dangerously-skip-permissions", Path("/notes"))

    @patch("agent_launchpad.launch.shutil.which", return_value="/fake/codex")
    @patch("agent_launchpad.launch.subprocess.call", return_value=0)
    def test_resume_original_codex_without_activity_preserves_completion(self, call, _which):
        self.catalog.toggle_completed(self.project)
        self.assertEqual(launch(self.catalog, self.project, "codex"), 0)
        self.assertEqual(call.call_args.args[0][:3], ["/fake/codex", "resume", "one"])
        self.assertEqual(call.call_args.kwargs["cwd"], self.root)
        self.assertEqual(self.catalog.find(self.project.id).status, 'Completed')

    @patch("agent_launchpad.launch.shutil.which", return_value="/fake/claude")
    def test_switch_to_claude_records_only_created_transcript_then_resumes(self, _which):
        def create(args, **_kwargs):
            claude(self.paths.claude, args[2], self.root)
            return 0
        with patch("agent_launchpad.launch.subprocess.call", side_effect=create) as call:
            launch(self.catalog, self.project, "claude")
            native_id = call.call_args.args[0][2]
        project = self.catalog.find(self.project.id)
        self.assertEqual(project.sessions["claude"].native_id, native_id)
        with patch("agent_launchpad.launch.subprocess.call", return_value=0) as call:
            launch(self.catalog, project, "claude")
            self.assertEqual(call.call_args.args[0][1:3], ["--resume", native_id])

    @patch("agent_launchpad.launch.shutil.which", return_value="/fake/claude")
    @patch("agent_launchpad.launch.subprocess.call", return_value=1)
    def test_failed_start_does_not_create_phantom_session_link(self, _call, _which):
        self.assertEqual(launch(self.catalog, self.project, "claude"), 1)
        record = self.catalog.store.read()["projects"][self.project.id]
        self.assertNotIn("claude", record["sessions"])
        self.assertIn("pending_claude_id", record)

    @patch("agent_launchpad.launch.shutil.which", return_value="/fake/codex")
    def test_switch_to_codex_links_new_session(self, _which):
        claude(self.paths.claude, "three", self.root)
        project = self.catalog.find("claude:three")
        def create(_args, **_kwargs):
            codex(self.paths.codex, [("new", "New", str(self.root), 400, None, 0, None)])
            return 0
        with patch("agent_launchpad.launch.subprocess.call", side_effect=create):
            launch(self.catalog, project, "codex")
        self.assertEqual(self.catalog.find(project.id).sessions["codex"].native_id, "new")

    @patch("agent_launchpad.launch.shutil.which", return_value=None)
    def test_missing_binary_is_actionable(self, _which):
        with self.assertRaisesRegex(ValueError, "not on PATH"):
            launch(self.catalog, self.project, "claude")

    @patch("agent_launchpad.launch.shutil.which", return_value="/fake/codex")
    def test_missing_directory_is_not_silently_replaced(self, _which):
        self.project.directory = self.root / "not-here"
        with self.assertRaisesRegex(ValueError, "directory is unavailable"):
            launch(self.catalog, self.project, "codex")

    @patch("agent_launchpad.launch.shutil.which", return_value="/fake/codex")
    @patch("agent_launchpad.launch.subprocess.call", side_effect=subprocess.SubprocessError("bad"))
    def test_subprocess_failure_keeps_handoff(self, _call, _which):
        with self.assertRaises(subprocess.SubprocessError):
            launch(self.catalog, self.project, "codex")
        self.assertTrue(self.catalog.store.handoff(self.project.id).exists())
