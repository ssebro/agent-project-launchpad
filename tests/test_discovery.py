import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent_projects.discovery import discover_claude, discover_codex, timestamp
from helpers import claude, codex


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_missing_histories_are_empty(self):
        self.assertEqual(discover_codex(self.root).sessions, [])
        self.assertEqual(discover_claude(self.root).sessions, [])

    def test_codex_excludes_archived_and_subagents_without_user_event_flag(self):
        file = codex(self.root, [
            ("one", "A project", str(self.root), 100, "/example/transcript", 0, None),
            ("old", "Archived", str(self.root), 200, None, 1, None),
            ("child", "Worker", str(self.root), 300, None, 0, "worker"),
        ])
        original = file.read_bytes()
        result = discover_codex(self.root)
        self.assertEqual([s.native_id for s in result.sessions], ["one"])
        self.assertEqual(result.sessions[0].transcript, Path("/example/transcript"))
        self.assertEqual(file.read_bytes(), original)

    def test_codex_older_schema_and_named_session(self):
        with sqlite3.connect(self.root / "state_99.sqlite") as db:
            db.execute("CREATE TABLE threads (id TEXT, cwd TEXT, updated_at INTEGER, name TEXT)")
            db.execute("INSERT INTO threads VALUES ('one', NULL, 1, 'Named project')")
        result = discover_codex(self.root)
        self.assertEqual(result.sessions[0].title, "Named project")
        self.assertIsNone(result.sessions[0].directory)

    def test_bad_schema_falls_back_to_index_with_warning(self):
        with sqlite3.connect(self.root / "state_1.sqlite") as db:
            db.execute("CREATE TABLE unrelated (value TEXT)")
        index = self.root / "session_index.jsonl"
        index.write_text(json.dumps(dict(id="one", thread_name="Fallback",
                                         updated_at="2026-01-01T00:00:00Z")) + '\n{partial')
        result = discover_codex(self.root)
        self.assertEqual(result.sessions[0].title, "Fallback")
        self.assertTrue(result.warnings)

    def test_index_uses_latest_metadata_and_skips_nonobjects(self):
        (self.root / "session_index.jsonl").write_text(
            '\n'.join(json.dumps(r) for r in [[], {"id": "one", "thread_name": "Old"},
                                             {"id": "one", "thread_name": "New"}]))
        self.assertEqual(discover_codex(self.root).sessions[0].title, "New")

    def test_claude_partial_line_summary_and_sidechain(self):
        file = claude(self.root, "one", self.root, partial=True)
        with file.open("a") as stream:
            stream.write('\n' + json.dumps(dict(type="summary", summary="A clear summary")))
        claude(self.root, "child", self.root, sidechain=True)
        result = discover_claude(self.root)
        self.assertEqual(len(result.sessions), 1)
        self.assertEqual(result.sessions[0].title, "A clear summary")

    def test_claude_identity_mismatch_is_skipped(self):
        file = claude(self.root, "one", self.root)
        file.write_text(file.read_text().replace('"sessionId": "one"', '"sessionId": "other"'))
        result = discover_claude(self.root)
        self.assertFalse(result.sessions)
        self.assertIn("identity mismatch", result.warnings[0])

    def test_timestamp_accepts_iso_and_numeric(self):
        self.assertEqual(timestamp(100), 100)
        self.assertGreater(timestamp("2026-01-01T00:00:00Z"), 100)
        self.assertEqual(timestamp("not a date", 5), 5)
