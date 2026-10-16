"""A live preview of the real UI, using disposable fictional histories."""

import curses
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from .config import Paths
from .projects import Catalog
from .review import Suggestion, present_review
from .ui import choose


def demo_catalog(root: Path) -> Catalog:
    paths = Paths(root / 'data', root / 'codex', root / 'claude', root / 'copilot')
    paths.codex.mkdir()
    rows = []
    for index, title in enumerate(['Session picker', 'Release checklist', 'Documentation refresh',
                                    'API migration', 'Landing page']):
        transcript = root / f'example-{index}.jsonl'
        event = dict(type='response_item', payload=dict(type='message', role='user',
                     content=[dict(type='input_text', text=f'Work on {title.lower()}.')]))
        transcript.write_text(json.dumps(event) + '\n')
        rows.append((f'example-{index}', title,
                     '/example/projects/' + title.lower().replace(' ', '-'),
                     time.time() - index * 3600, str(transcript)))
    with sqlite3.connect(paths.codex / 'state_1.sqlite') as db:
        db.execute('CREATE TABLE threads (id TEXT, title TEXT, cwd TEXT, updated_at REAL, rollout_path TEXT)')
        db.executemany('INSERT INTO threads VALUES (?, ?, ?, ?, ?)', rows)
    catalog = Catalog(paths)
    catalog.toggle_completed(catalog.find('codex:example-2'))
    catalog.toggle_completed(catalog.find('codex:example-4'))
    return catalog


def run_demo(agent: str) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError('The live demo needs a terminal; run agent-launchpad demo in Terminal')
    with tempfile.TemporaryDirectory(prefix='agent-launchpad-demo-') as directory:
        catalog = demo_catalog(Path(directory))
        notice = 'DEMO · Fictional projects · No agents or model requests'
        while True:
            selection = curses.wrapper(choose, catalog, agent, notice)
            if selection is None:
                return 0
            agent = selection.agent
            if selection.action == 'review':
                project = selection.project
                suggestion = Suggestion(
                    [project.title, project.title + ' follow-up'],
                    'Example summary: the core work is implemented; review and publishing remain.',
                    ['Review the changes.', 'Validate the result before publishing.'],
                )
                try:
                    notice = 'DEMO · ' + present_review(catalog, project, suggestion)
                except (KeyboardInterrupt, EOFError):
                    notice = 'DEMO · Summary cancelled.'
            else:
                notice = f'DEMO · Would start {agent}' + (
                    f' on {selection.project.title}' if selection.project else ' in your current folder'
                ) + ' · No agent was launched'
