import contextlib
import io
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_projects.projects import Catalog
from agent_projects.review import (
    generate,
    interactive_review,
    parse_suggestion,
    review_prompt,
    save,
    transcript_excerpt,
)
from helpers import codex, paths

PAYLOAD = dict(names=['Session picker', 'Shared agent launcher'],
               summary='The picker works; publishing remains unverified.',
               next_steps=['Verify the package and publish it.'])


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = paths(self.root)
        self.transcript = self.root / 'synthetic.jsonl'
        self.transcript.write_text(json.dumps(dict(type='response_item', payload=dict(
            type='message', role='user', content=[dict(type='input_text', text='Build a picker')]
        ))) + '\n')
        codex(self.paths.codex, [('one', 'Example', str(self.root), 100,
                                  str(self.transcript), 0, None)])
        self.catalog = Catalog(self.paths)
        self.project = self.catalog.find('codex:one')
        self.suggestion = parse_suggestion(json.dumps(PAYLOAD))

    def test_parses_native_json_and_claude_envelope(self):
        envelope = json.dumps(dict(result='```json\n' + json.dumps(PAYLOAD) + '\n```'))
        self.assertEqual(parse_suggestion(envelope), self.suggestion)
        self.assertEqual(parse_suggestion('```json\n' + json.dumps(PAYLOAD) + '\n```'),
                         self.suggestion)

    def test_invalid_suggestions_are_rejected(self):
        for value in [[], dict(PAYLOAD, names=[]), dict(PAYLOAD, names=['bad\x1bname']),
                      dict(PAYLOAD, summary=''), dict(PAYLOAD, next_steps='not a list')]:
            with self.assertRaises(ValueError):
                parse_suggestion(json.dumps(value))

    def test_extracts_dialogue_without_tools_or_reasoning(self):
        events = [
            dict(type='assistant', message=dict(content=[dict(type='thinking', thinking='secret'),
                                                        dict(type='text', text='Visible reply')])),
            dict(type='tool_result', message=dict(content='Private tool output')),
            dict(type='user', isSidechain=True, message=dict(content='Child agent')),
        ]
        self.transcript.write_text('\n'.join(json.dumps(e) for e in events))
        text = transcript_excerpt(self.transcript, 'claude')
        self.assertIn('Visible reply', text)
        for excluded in ['secret', 'Private tool output', 'Child agent']:
            self.assertNotIn(excluded, text)

    def test_excerpt_is_bounded_and_truncation_is_explicit(self):
        self.transcript.write_text('\n'.join(json.dumps(dict(type='user.message',
            data=dict(content='x' * 100))) for _ in range(30)))
        text = transcript_excerpt(self.transcript, 'copilot', limit=200)
        self.assertIn('omitted', text)
        self.assertLess(len(text), 400)

    def test_prompt_uses_supplied_evidence_only(self):
        text = review_prompt(self.catalog, self.project)
        self.assertIn('Build a picker', text)
        self.assertIn('untrusted conversation data', text)
        self.assertIn('Never invent success', text)

    def test_save_summary_and_optional_name_without_changing_lifecycle(self):
        self.catalog.toggle_completed(self.project)
        save(self.catalog, self.project, self.suggestion, None)
        project = self.catalog.find(self.project.id)
        self.assertEqual(project.title, 'Example')
        self.assertEqual(project.status, 'Completed')
        self.assertEqual(project.summary, self.suggestion.summary)
        self.assertFalse(project.summary_stale)
        save(self.catalog, project, self.suggestion, self.suggestion.names[1])
        self.assertEqual(self.catalog.find(project.id).title, self.suggestion.names[1])
        text = self.catalog.store.handoff(project.id).read_text()
        self.assertEqual(text.count('## Latest agent review'), 1)
        self.assertIn(self.suggestion.summary, text)

    def test_new_activity_marks_summary_stale(self):
        save(self.catalog, self.project, self.suggestion, None)
        with sqlite3.connect(self.paths.codex / 'state_5.sqlite') as db:
            db.execute("UPDATE threads SET updated_at = 500 WHERE id = 'one'")
        self.assertTrue(self.catalog.find(self.project.id).summary_stale)

    def test_interactive_cancel_never_renames_or_saves_summary(self):
        with patch('agent_projects.review.generate', return_value=self.suggestion), \
             patch('builtins.input', return_value='q'), contextlib.redirect_stdout(io.StringIO()):
            interactive_review(self.catalog, self.project, 'codex')
        self.assertFalse(self.catalog.find(self.project.id).summary)
        self.assertEqual(self.catalog.find(self.project.id).title, 'Example')

    @patch('agent_projects.review.executable', return_value=['/fake/codex'])
    def test_codex_review_is_ephemeral_and_read_only(self, _executable):
        def complete(args, **kwargs):
            file = Path(args[args.index('--output-last-message') + 1])
            file.write_text(json.dumps(PAYLOAD))
            self.assertIn('Build a picker', kwargs['input'])
            self.assertIn('--ephemeral', args)
            self.assertEqual(args[args.index('--sandbox') + 1], 'read-only')
            return subprocess.CompletedProcess(args, 0, '', '')
        with patch('agent_projects.review.subprocess.run', side_effect=complete):
            self.assertEqual(generate(self.catalog, self.project, 'codex'), self.suggestion)

    @patch('agent_projects.review.executable', return_value=['/fake/claude'])
    def test_claude_review_disables_tools_and_session_persistence(self, _executable):
        output = json.dumps(dict(result=json.dumps(PAYLOAD)))
        with patch('agent_projects.review.subprocess.run', return_value=
                   subprocess.CompletedProcess([], 0, output, '')) as call:
            self.assertEqual(generate(self.catalog, self.project, 'claude'), self.suggestion)
        args = call.call_args.args[0]
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertIn('--no-session-persistence', args)

    @patch('agent_projects.review.executable', return_value=['gh', 'copilot', '--'])
    def test_copilot_review_is_tracked_separately_and_denies_tools(self, _executable):
        with patch('agent_projects.review.subprocess.run', return_value=
                   subprocess.CompletedProcess([], 0, json.dumps(PAYLOAD), '')) as call:
            self.assertEqual(generate(self.catalog, self.project, 'copilot'), self.suggestion)
        args = call.call_args.args[0]
        self.assertIn('--available-tools', args)
        self.assertEqual(args[args.index('--deny-tool') + 1], '*')
        self.assertEqual(len(self.catalog.store.read()['review_sessions']), 1)

    @patch('agent_projects.review.executable', return_value=['/fake/claude'])
    def test_failed_review_does_not_modify_project(self, _executable):
        with patch('agent_projects.review.subprocess.run', return_value=
                   subprocess.CompletedProcess([], 1, '', 'Authentication failed')), \
             self.assertRaisesRegex(ValueError, 'nothing was saved'):
            generate(self.catalog, self.project, 'claude')
        self.assertFalse(self.catalog.find(self.project.id).summary)
