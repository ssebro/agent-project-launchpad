"""Render the actual picker with demo data to a crisp PNG (macOS, Swift required).

Run from the checkout: PYTHONPATH=src python3 docs/tools/capture_preview.py
No agent sessions, model requests, or personal state are used.
"""

import curses
import json
import subprocess
import tempfile
from pathlib import Path

from agent_launchpad.demo import demo_catalog
from agent_launchpad.ui import Theme, render


class Frame:
    """Record the same cell writes curses receives, including overwritten cells."""

    def getmaxyx(self):
        return 23, 100

    def erase(self):
        self.cells = {}

    def addstr(self, y, x, text, style):
        for offset, char in enumerate(text):
            self.cells[y, x + offset] = [y, x + offset, char, style]

    def refresh(self):
        pass


def main():
    # Small style IDs stand in for terminal-specific curses color-pair values.
    theme = Theme(accent=1, muted=2, selected=3, key=4, success=5,
                  warning=6, danger=7, ready=8)
    with tempfile.TemporaryDirectory(prefix='launchpad-preview-') as folder:
        root = Path(folder)
        catalog = demo_catalog(root)
        projects = catalog.load()
        projects[0].summary = 'Picker implemented; review changes and publish the release.'
        frame = Frame()
        render(frame, projects, 0, len(projects), 'claude', '', False,
               'DEMO · Fictional projects · No agents or model requests', theme)
        data = root / 'frame.json'
        data.write_text(json.dumps(list(frame.cells.values())))
        output = Path(__file__).resolve().parents[1] / 'preview.png'
        subprocess.run(['swift', '-module-cache-path', str(root / 'swift-cache'),
                        str(Path(__file__).with_name('render_frame.swift')),
                        str(data), str(output), str(curses.A_BOLD)], check=True)
        print(output)


if __name__ == '__main__':
    main()
