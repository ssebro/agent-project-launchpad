import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from agent_launchpad.projects import Catalog
from agent_launchpad.store import Store
from helpers import claude, codex, paths


def increment(root: str):
    store = Store(Path(root))
    for _ in range(10):
        with store.edit() as state:
            state["counter"] = state.get("counter", 0) + 1


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = paths(self.root)
        codex(self.paths.codex, [("one", "First", str(self.root), 100, "/example/one", 0, None),
                                 ("two", "Second", str(self.root), 200, None, 0, None)])
        self.catalog = Catalog(self.paths)

    def test_tasks_in_same_directory_stay_separate(self):
        self.assertEqual(len(self.catalog.load()), 2)

    def test_explicit_link_merges_histories(self):
        claude(self.paths.claude, "three", self.root)
        with self.catalog.store.edit() as state:
            state["projects"]["codex:one"] = {
                "title": "Shared project", "sessions": {"codex": "one", "claude": "three"},
            }
        projects = self.catalog.load()
        self.assertEqual(len(projects), 2)
        project = self.catalog.find("codex:one")
        self.assertEqual(set(project.sessions), {"codex", "claude"})
        self.assertEqual(project.title, "Shared project")

    def test_forget_persists_and_restores_without_deleting_history(self):
        project = self.catalog.find("codex:one")
        file = self.paths.codex / "state_5.sqlite"
        original = file.read_bytes()
        self.catalog.forget(project)
        self.assertEqual(len(Catalog(self.paths).load()), 1)
        self.assertEqual(len(self.catalog.load(include_hidden=True)), 2)
        self.assertEqual(self.catalog.store.restore(), project.id)
        self.assertEqual(len(self.catalog.load()), 2)
        self.assertEqual(file.read_bytes(), original)

    def test_handoff_status_and_metadata(self):
        project = self.catalog.find("codex:one")
        file = self.catalog.prepare(project)
        self.assertIn("/example/one", file.read_text())
        self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        self.catalog.set_metadata(project, "Better name", "completed")
        loaded = self.catalog.find(project.id)
        self.assertEqual(loaded.title, "Better name")
        self.assertEqual(loaded.status, "Completed")
        self.assertIn("Status: Work underway", file.read_text())
        self.assertEqual(loaded.detail, "Work underway")

    def test_discovered_projects_are_active_automatically(self):
        self.assertTrue(all(p.status == 'Active' for p in self.catalog.load()))

    def test_completion_toggle_persists_across_catalog_instances(self):
        project = self.catalog.find('codex:one')
        self.catalog.toggle_completed(project)
        project = Catalog(self.paths).find(project.id)
        self.assertEqual(project.status, 'Completed')
        self.catalog.toggle_completed(project)
        self.assertEqual(self.catalog.find(project.id).status, 'Active')

    def test_native_activity_reopens_completed_work(self):
        import sqlite3

        project = self.catalog.find('codex:one')
        self.catalog.toggle_completed(project)
        with sqlite3.connect(self.paths.codex / 'state_5.sqlite') as db:
            db.execute("UPDATE threads SET updated_at = 500 WHERE id = 'one'")
        self.assertEqual(self.catalog.find(project.id).status, 'Active')

    def test_handoff_notes_do_not_override_lifecycle(self):
        project = self.catalog.find('codex:one')
        file = self.catalog.prepare(project)
        self.catalog.toggle_completed(project)
        file.write_text(file.read_text().replace('Status: Work underway', 'Status: Needs review'))
        reloaded = self.catalog.find(project.id)
        self.assertEqual(reloaded.status, 'Completed')
        self.assertEqual(reloaded.detail, 'Needs review')

    def test_archive_and_restore_preserve_completed_state(self):
        project = self.catalog.find('codex:one')
        self.catalog.toggle_completed(project)
        self.catalog.forget(self.catalog.find(project.id))
        self.assertEqual(self.catalog.find(project.id).status, 'Archived')
        self.catalog.store.restore()
        self.assertEqual(self.catalog.find(project.id).status, 'Completed')

    def test_native_activity_does_not_unarchive(self):
        import sqlite3

        project = self.catalog.find('codex:one')
        self.catalog.forget(project)
        with sqlite3.connect(self.paths.codex / 'state_5.sqlite') as db:
            db.execute("UPDATE threads SET updated_at = 500 WHERE id = 'one'")
        self.assertTrue(self.catalog.find(project.id).hidden)

    def test_restore_of_nonarchived_project_does_not_change_lifecycle(self):
        project = self.catalog.find('codex:one')
        self.catalog.toggle_completed(project)
        self.catalog.store.restore(project.id)
        self.assertEqual(self.catalog.find(project.id).status, 'Completed')

    def test_unknown_and_ambiguous_prefixes(self):
        self.assertEqual(self.catalog.find("codex:o").id, "codex:one")
        for value in ("codex:", "missing"):
            with self.assertRaises(ValueError):
                self.catalog.find(value)

    def test_duplicate_native_associations_fail_clearly(self):
        with self.catalog.store.edit() as state:
            for key in ("first", "second"):
                state["projects"][key] = {"sessions": {"codex": "one"}}
        with self.assertRaisesRegex(ValueError, "multiple projects"):
            self.catalog.load()

    def test_invalid_state_is_preserved(self):
        self.paths.data.mkdir()
        file = self.paths.data / "state.json"
        for content in ('{broken', json.dumps({"version": 99}),
                        json.dumps({"version": 1, "projects": [], "forgotten": []})):
            file.write_text(content)
            with self.assertRaises(ValueError), self.catalog.store.edit():
                pass
            self.assertEqual(file.read_text(), content)

    def test_failed_transaction_does_not_write(self):
        with self.assertRaises(RuntimeError), self.catalog.store.edit() as state:
            state["projects"]["bad"] = {}
            raise RuntimeError("stop")
        self.assertEqual(self.catalog.store.read()["projects"], {})

    def test_parallel_metadata_updates_are_serialized(self):
        context = multiprocessing.get_context("spawn")
        workers = [context.Process(target=increment, args=(str(self.paths.data),)) for _ in range(3)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(15)
            if worker.is_alive():
                worker.terminate()
                self.fail("Metadata lock deadlocked")
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(self.catalog.store.read()["counter"], 30)

    def test_untrusted_project_id_cannot_escape_handoff_directory(self):
        file = self.catalog.store.handoff("../../outside")
        self.assertEqual(file.parent, self.paths.data / "handoffs")
        self.assertNotIn("..", file.name)
