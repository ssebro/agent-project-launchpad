"""Opening and leaving an agent is not a new contribution to the project."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agent_launchpad.launch import handoff_prompt, launch
from agent_launchpad.projects import Catalog
from agent_launchpad.ui import last_agent
from helpers import claude, codex, paths


class IdleResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = replace(paths(self.root), copilot=self.root / 'copilot')
        original = claude(self.paths.claude, 'original', self.root)
        os.utime(original, (100, 100))
        self.catalog = Catalog(self.paths)
        self.project = self.catalog.find('claude:original')

    def write_session(self, agent, native_id, prompt, followup=None):
        texts = [prompt] + ([followup] if followup else [])
        if agent == 'codex':
            file = self.root / (native_id + '.jsonl')
            events = [dict(type='response_item', payload=dict(type='message', role='user',
                      content=[dict(type='input_text', text=text)])) for text in texts]
            # Metadata can change independently of actual user requests.
            codex(self.paths.codex, [(native_id, 'Resume This Project', str(self.root),
                                     500, str(file), 0, None)])
        elif agent == 'claude':
            file = claude(self.paths.claude, native_id, self.root)
            events = [dict(type='user', cwd=str(self.root), sessionId=native_id,
                           message=dict(content=text)) for text in texts]
        else:
            file = self.paths.copilot / 'session-state' / native_id / 'events.jsonl'
            file.parent.mkdir(parents=True, exist_ok=True)
            events = [dict(type='session.start', data=dict(sessionId=native_id,
                           context=dict(cwd=str(self.root))))]
            events += [dict(type='user.message', data=dict(content=text)) for text in texts]
        if agent == 'codex':
            events.append(dict(type='response_item', payload=dict(type='message', role='assistant',
                          content=[dict(type='output_text', text='Context read; waiting for your request.')])))
        file.write_text('\n'.join(json.dumps(event) for event in events) + '\n')
        os.utime(file, (500, 500))
        return file

    def run_visit(self, agent, followup=None):
        def run(args, **_kwargs):
            native_id = 'new-codex' if agent == 'codex' else args[2]
            self.write_session(agent, native_id, args[-1], followup)
            # Bootstrap-only assistant replies and automatic notes are not user work.
            handoff = self.catalog.store.handoff(self.project.id)
            handoff.write_text(handoff.read_text() + '\nContext read.\n')
            return 0
        with patch('agent_launchpad.launch.executable', return_value=['/fake/' + agent]), \
             patch('agent_launchpad.launch.subprocess.call', side_effect=run):
            launch(self.catalog, self.catalog.find(self.project.id), agent)

    def test_new_agent_bootstrap_preserves_title_agent_date_and_completion(self):
        for agent in ('codex', 'copilot'):
            with self.subTest(agent=agent):
                self.catalog.set_metadata(self.project, None, 'completed')
                before = self.catalog.find(self.project.id)
                self.run_visit(agent)
                after = Catalog(self.paths).find(self.project.id)
                self.assertEqual(after.title, before.title)
                self.assertNotEqual(after.title, 'Resume This Project')
                self.assertEqual(after.updated, before.updated)
                self.assertEqual(after.status, 'Completed')
                self.assertEqual(last_agent(after), 'Claude Code')
                self.assertIn(agent, after.sessions)  # Native session remains resumable.
                self.assertEqual(len(self.catalog.load()), 1)

    def test_first_switch_to_claude_does_not_count_bootstrap_as_work(self):
        with tempfile.TemporaryDirectory() as folder:
            config = paths(Path(folder))
            codex(config.codex, [('original', 'Real project', folder, 100, None, 0, None)])
            catalog = Catalog(config)
            project = catalog.find('codex:original')
            def run(args, **_kwargs):
                file = claude(config.claude, args[2], Path(folder))
                event = dict(type='user', cwd=folder, sessionId=args[2], message=dict(content=args[-1]))
                file.write_text(json.dumps(event) + '\n')
                return 0
            with patch('agent_launchpad.launch.executable', return_value=['/fake/claude']), \
                 patch('agent_launchpad.launch.subprocess.call', side_effect=run):
                launch(catalog, project, 'claude')
            after = catalog.find(project.id)
            self.assertEqual(after.updated, 100)
            self.assertEqual(last_agent(after), 'Codex')
            self.assertEqual(after.title, 'Real project')

    def test_actual_user_request_updates_agent_and_reopens_work(self):
        self.catalog.toggle_completed(self.project)
        self.run_visit('codex', 'Explain the failing test; no file edits needed.')
        after = self.catalog.find(self.project.id)
        self.assertEqual(after.title, self.project.title)
        self.assertEqual(last_agent(after), 'Codex')
        self.assertEqual(after.status, 'Active')
        self.assertGreater(after.updated, self.project.updated)

    def test_later_native_request_overrides_idle_baseline_without_launcher(self):
        self.run_visit('copilot')
        session = self.catalog.find(self.project.id).sessions['copilot']
        with session.transcript.open('a') as stream:
            stream.write(json.dumps(dict(type='user.message', data=dict(content='Review the design.'))) + '\n')
        after = Catalog(self.paths).find(self.project.id)
        self.assertEqual(last_agent(after), 'GitHub Copilot')
        self.assertGreater(after.updated, self.project.updated)

    def test_repeat_resume_same_agent_without_user_input_preserves_date(self):
        self.run_visit('codex', 'Review this change.')
        self.catalog.toggle_completed(self.catalog.find(self.project.id))
        before = self.catalog.find(self.project.id)
        def run(_args, **_kwargs):
            # The native CLI updates metadata even though the user immediately quits.
            import sqlite3
            with sqlite3.connect(self.paths.codex / 'state_5.sqlite') as db:
                db.execute("UPDATE threads SET updated_at = updated_at + 100 WHERE id = 'new-codex'")
            return 0
        with patch('agent_launchpad.launch.executable', return_value=['/fake/codex']), \
             patch('agent_launchpad.launch.subprocess.call', side_effect=run):
            launch(self.catalog, before, 'codex')
        after = self.catalog.find(self.project.id)
        self.assertEqual(after.sessions['codex'].updated, before.sessions['codex'].updated)
        self.assertEqual(after.updated, before.updated)
        self.assertEqual(after.status, 'Completed')

    def test_real_work_can_supply_a_better_native_title_but_explicit_names_win(self):
        self.run_visit('codex', 'Refactor payment retry handling.')
        import sqlite3
        with sqlite3.connect(self.paths.codex / 'state_5.sqlite') as db:
            db.execute("UPDATE threads SET title = 'Payment retry handling' WHERE id = 'new-codex'")
        project = self.catalog.find(self.project.id)
        self.assertEqual(project.title, 'Payment retry handling')
        self.catalog.set_metadata(project, 'Billing reliability', None)
        self.assertEqual(self.catalog.find(project.id).title, 'Billing reliability')

    def test_bootstrap_assistant_reply_does_not_stale_saved_summary(self):
        with self.catalog.store.edit() as state:
            state['projects'][self.project.id] = {
                'summary': 'Review next steps.', 'reviewed_at': 100,
                'review_source_updates': {self.project.id: 100},
            }
        self.run_visit('codex')
        after = self.catalog.find(self.project.id)
        self.assertFalse(after.summary_stale)
        self.assertEqual(after.summary, 'Review next steps.')

    def test_old_bootstrap_only_link_uses_origin_title_and_agent(self):
        self.write_session('codex', 'old', handoff_prompt(self.root / 'handoff.md'))
        with self.catalog.store.edit() as state:
            state['projects'][self.project.id] = {'sessions': {'claude': 'original', 'codex': 'old'}}
        after = self.catalog.find(self.project.id)
        self.assertEqual(after.title, self.project.title)
        self.assertEqual(last_agent(after), 'Claude Code')
        self.assertEqual(after.updated, 100)
