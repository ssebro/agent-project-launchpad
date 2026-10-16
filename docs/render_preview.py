"""Generate the README preview from the real renderer and invented project data.

Run from the checkout: PYTHONPATH=src python3 docs/render_preview.py
No real session history is read.
"""

from html import escape
from pathlib import Path

from agent_projects.models import Project, Session
from agent_projects.ui import Theme, render, text_width

THEME = Theme(accent=1, muted=2, selected=4, key=8,
              success=16, warning=32, danger=64, ready=128)


class Capture:
    def __init__(self, height: int, width: int):
        self.height, self.width = height, width
        self.cells = [[(" ", 0) for _ in range(width)] for _ in range(height)]

    def getmaxyx(self):
        return self.height, self.width

    def erase(self):
        pass

    def refresh(self):
        pass

    def addstr(self, y, x, text, style):
        for char in text:
            if x >= self.width:
                break
            self.cells[y][x] = char, style
            x += text_width(char)


def colors(style: int) -> tuple[str, str]:
    if style & THEME.key:
        return "#10232e", "#67e8f9"
    if style & THEME.selected:
        return "#ffffff", "#1e40af"
    for role, color in ((THEME.accent, "#67e8f9"), (THEME.success, "#86efac"),
                        (THEME.warning, "#fcd34d"), (THEME.danger, "#fca5a5"),
                        (THEME.ready, "#d8b4fe"), (THEME.muted, "#9ca3af")):
        if style & role:
            return color, "#111827"
    return "#e5e7eb", "#111827"


def main() -> None:
    projects = []
    for index, (title, status) in enumerate([
        ("Session picker", "Active"),
        ("Release checklist", "Active"),
        ("Documentation refresh", "Completed"),
        ("API migration", "Active"),
        ("Landing page", "Completed"),
    ]):
        folder = Path("/example/projects") / title.lower().replace(" ", "-")
        # Fixed UTC timestamp ensures the fixture has no personal history.
        stamp = 1792161720 - index * 86400
        session = Session("codex", f"example-{index}", title, folder, stamp)
        projects.append(Project(f"codex:example-{index}", title, status, folder, stamp,
                                {"codex": session}))
    capture = Capture(21, 108)
    render(capture, projects, 0, len(projects), "codex", "", False, "", THEME)
    cell, line, margin = 8, 21, 20
    width, height = capture.width * cell + 2 * margin, capture.height * line + 2 * margin
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           '<title id="title">Agent Projects terminal picker</title>',
           '<desc id="desc">Compact project list with a blue selection band, colored status '
           'labels, a selected-project preview, and cyan keyboard command chips.</desc>',
           f'<rect width="{width}" height="{height}" rx="12" fill="#111827"/>',
           '<g font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
           'font-size="13" xml:space="preserve">']
    for y, row in enumerate(capture.cells):
        start = 0
        while start < len(row):
            style = row[start][1]
            end = start + 1
            while end < len(row) and row[end][1] == style:
                end += 1
            text = ''.join(char for char, _style in row[start:end])
            foreground, background = colors(style)
            x, top = margin + start * cell, margin + y * line
            if background != "#111827":
                svg.append(f'<rect x="{x}" y="{top}" width="{(end-start)*cell}" '
                           f'height="{line}" rx="2" fill="{background}"/>')
            if text.strip():
                svg.append(f'<text x="{x}" y="{top+15}" fill="{foreground}" '
                           f'textLength="{len(text)*cell}" lengthAdjust="spacingAndGlyphs">'
                           f'{escape(text)}</text>')
            start = end
    svg += ['</g>', '</svg>']
    (Path(__file__).parent / 'preview.svg').write_text('\n'.join(svg) + '\n')


if __name__ == '__main__':
    main()
