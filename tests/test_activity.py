"""Unreadable or incomplete evidence cannot establish a no-op or new work."""

import json
import tempfile
import unittest
from pathlib import Path

from agent_launchpad.activity import EMPTY_ACTIVITY, user_activity
from agent_launchpad.launch import handoff_prompt
from agent_launchpad.models import Session


class ActivityTests(unittest.TestCase):
    def test_missing_empty_malformed_and_partial_transcripts_are_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'events.jsonl'
            session = Session('copilot', 'id', 'Task', None, 100, file)
            self.assertIsNone(user_activity(session))
            for content in ('', '{broken', '{}\n', '{"type":"user.message"'):
                file.write_text(content)
                self.assertIsNone(user_activity(session))
            prompt = handoff_prompt(Path(folder) / 'notes.md')
            file.write_text(json.dumps(dict(type='user.message', data=dict(content=prompt))) + '\n')
            self.assertEqual(user_activity(session), EMPTY_ACTIVITY)
            with file.open('a') as stream:
                stream.write('{partial')
            self.assertIsNone(user_activity(session))
