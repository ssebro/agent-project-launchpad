import json
import tempfile
import unittest
from pathlib import Path

from agent_launchpad.context import create_packet
from agent_launchpad.demo import demo_catalog


class ContextTests(unittest.TestCase):
    def test_packet_refreshes_recent_dialogue_and_preserves_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = demo_catalog(Path(directory))
            project = catalog.load()[0]
            note = catalog.prepare(project)
            original = note.read_text()
            packet_file = create_packet(catalog, project)
            packet = json.loads(packet_file.read_text())
            self.assertIn('Work on session picker', packet['sources'][0]['recent_dialogue'])
            self.assertEqual(note.read_text(), original)
            transcript = project.sessions['codex'].transcript
            event = dict(type='response_item', payload=dict(type='message', role='assistant',
                         content=[dict(type='output_text', text='A new decision was made.')]))
            with transcript.open('a') as stream:
                stream.write(json.dumps(event) + '\n')
            fresh = json.loads(create_packet(catalog, project).read_text())
            self.assertIn('A new decision', fresh['sources'][0]['recent_dialogue'])
            self.assertEqual(packet_file.stat().st_mode & 0o777, 0o600)

    def test_missing_transcript_is_an_explicit_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = demo_catalog(Path(directory))
            project = catalog.load()[0]
            project.sessions['codex'].transcript.unlink()
            packet = json.loads(create_packet(catalog, project).read_text())
            self.assertIn('unavailable', packet['sources'][0]['gap'])
