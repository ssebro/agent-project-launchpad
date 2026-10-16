"""Keyboard-first curses UI. Discovery and mutation stay in the catalog."""

import curses
import os
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from .models import AGENTS, Project
from .projects import Catalog


def text_width(text: str) -> int:
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def clean(text: str) -> str:
    return "".join(c if c.isprintable() else " " for c in str(text))


def fit(text: str, width: int, pad: bool = False) -> str:
    """Truncate by terminal cells rather than bytes, preserving wide characters."""
    if width <= 0:
        return ""
    text = clean(text)
    if text_width(text) > width:
        output, used = "", 0
        for char in text:
            size = text_width(char)
            if used + size > width - 1:
                break
            output += char
            used += size
        text = output + "…"
    return text + " " * max(0, width - text_width(text)) if pad else text


@dataclass
class Selection:
    agent: str
    project: Project | None = None
    action: str = 'resume'


@dataclass(frozen=True)
class Theme:
    accent: int = curses.A_BOLD
    muted: int = curses.A_DIM
    selected: int = curses.A_REVERSE
    key: int = curses.A_REVERSE | curses.A_BOLD
    success: int = curses.A_BOLD
    warning: int = curses.A_BOLD
    danger: int = curses.A_BOLD
    ready: int = curses.A_BOLD

    @classmethod
    def initialize(cls) -> "Theme":
        if "NO_COLOR" in os.environ:
            return cls()
        try:
            if not curses.has_colors():
                return cls()
            curses.start_color()
            background = -1
            try:
                curses.use_default_colors()
            except curses.error:
                background = curses.COLOR_BLACK
            pairs = [
                (curses.COLOR_CYAN, background),
                (curses.COLOR_WHITE, curses.COLOR_BLUE),
                (curses.COLOR_BLACK, curses.COLOR_CYAN),
                (curses.COLOR_GREEN, background),
                (curses.COLOR_YELLOW, background),
                (curses.COLOR_RED, background),
                (curses.COLOR_MAGENTA, background),
            ]
            for number, (foreground, back) in enumerate(pairs, 1):
                curses.init_pair(number, foreground, back)
            return cls(
                accent=curses.color_pair(1) | curses.A_BOLD,
                selected=curses.color_pair(2),
                key=curses.color_pair(3) | curses.A_BOLD,
                success=curses.color_pair(4),
                warning=curses.color_pair(5),
                danger=curses.color_pair(6) | curses.A_BOLD,
                ready=curses.color_pair(7),
            )
        except curses.error:
            return cls()

    def status(self, value: str) -> int:
        value = value.strip().casefold()
        if value.startswith(("blocked", "failed", "error")):
            return self.danger
        if value.startswith(("done", "complete", "shipped")):
            return self.success
        if value.startswith(("ready", "review")):
            return self.ready
        if value.startswith(("active", "in progress", "working", "discovery", "waiting", "paused")):
            return self.warning
        return self.muted


class Painter:
    def __init__(self, screen):
        self.screen = screen
        self.height, self.width = screen.getmaxyx()

    def write(self, y: int, x: int, text: str, style: int = 0, width: int | None = None) -> None:
        available = min(self.width - x - 1, width if width is not None else self.width)
        if not 0 <= y < self.height - 1 or available < 1:
            return
        try:
            self.screen.addstr(y, x, fit(text, available), style)
        except curses.error:
            pass  # A terminal resize may race an individual draw call.

    def keys(self, y: int, items: list[tuple[str, str]], theme: Theme) -> None:
        x = 1
        for key, label in items:
            if x + len(key) + len(label) + 5 >= self.width:
                break
            self.write(y, x, f" {key} ", theme.key)
            x += len(key) + 3
            self.write(y, x, label)
            x += len(label) + 2


def render(screen, visible: list[Project], selected: int, total: int, agent: str,
           query: str, searching: bool, message: str, theme: Theme) -> None:
    """Dense list, stable columns, a separate preview, and a semantic command bar."""
    screen.erase()
    paint = Painter(screen)
    height, width = paint.height, paint.width
    paint.write(0, 1, "agent projects", theme.accent)
    paint.write(0, max(18, width - 29), f"{agent.upper()}  ·  Tab switch tool", theme.accent)
    paint.write(2, 1, " / ", theme.key if searching else theme.accent)
    paint.write(2, 5, query + ("▏" if searching else "") if query or searching
                else "Search projects…", 0 if query or searching else theme.muted)
    paint.write(3, 1, f"{len(visible)}/{total} projects", theme.muted)
    paint.write(3, max(17, width - 26), "most recently updated", theme.muted)
    date_width = 16 if width >= 100 else 10
    status_width = 20 if width >= 100 else 16 if width >= 65 else 12
    date_x = width - date_width - 2
    status_x = date_x - status_width - 2
    title_width = max(1, status_x - 5)
    for x, label in ((3, "PROJECT"), (status_x, "STATUS"), (date_x, "UPDATED")):
        paint.write(4, x, label, theme.muted)
    paint.write(5, 1, "─" * (width - 3), theme.muted)
    preview_y = height - 8
    capacity = max(1, preview_y - 6)
    start = max(0, selected - capacity + 1)
    for index in range(start, min(len(visible), start + capacity)):
        item = visible[index]
        y = 6 + index - start
        active = index == selected
        style = theme.selected if active else 0
        if active:
            paint.write(y, 1, " " * (width - 2), style)
        paint.write(y, 1, "›" if active else " ", style | curses.A_BOLD)
        paint.write(y, 3, fit(item.title, title_width), style | (curses.A_BOLD if active else 0))
        paint.write(y, status_x, fit(item.status, status_width),
                    style | curses.A_BOLD if active else theme.status(item.status))
        stamp = datetime.fromtimestamp(item.updated).astimezone()
        date = stamp.strftime("%Y-%m-%d %H:%M" if date_width == 16 else "%Y-%m-%d")
        paint.write(y, date_x, date, style if active else theme.muted)
    if not visible:
        paint.write(7, 3, "No matches. Clear search, start new, or undo forget.", theme.warning)
    paint.write(preview_y, 1, "─" * (width - 3), theme.muted)
    if visible:
        item = visible[selected]
        paint.write(preview_y + 1, 1, item.title, curses.A_BOLD)
        paint.write(preview_y + 2, 1, str(item.directory or "Directory not recorded"), theme.muted)
        native = " · ".join(item.sessions) or "No native session"
        if item.summary:
            prefix = 'Review may be stale: ' if item.summary_stale else 'Summary: '
            paint.write(preview_y + 3, 1, prefix + item.summary, theme.muted)
        else:
            paint.write(preview_y + 3, 1, "History: " + native + "  |  " + (item.detail or item.status),
                        theme.status(item.status))
    paint.keys(height - 4, [("n", "new"), ("Enter", "resume"), ("↑↓", "move"),
                            ("/", "search"), ("q", "quit")], theme)
    paint.keys(height - 3, [("s", "summary"), ("c", "done/open"), ("a", "archive"), ("r", "rename"),
                            ("u", "undo"), ("?", "help")], theme)
    message_style = theme.warning if message.startswith("Forget this project?") else theme.muted
    paint.write(height - 2, 1, message or "Active automatically · c completes/reopens · a archives", message_style)
    if height < 16 or width < 42:
        screen.erase()
        paint.write(0, 0, "Resize terminal to at least 42 × 16.")
        paint.keys(2, [("n", "new"), ("q", "quit")], theme)
    screen.refresh()


def choose(screen, catalog: Catalog, agent: str) -> Selection | None:
    curses.curs_set(0)
    screen.keypad(True)
    theme = Theme.initialize()
    projects = catalog.load()
    selected, query = 0, ""
    searching, confirming = False, False
    editing: str | None = None
    edit_value, notice = "", ""
    while True:
        visible = [p for p in projects if query.casefold() in
                   f"{p.title} {p.status} {p.directory or ''}".casefold()]
        selected = max(0, min(selected, len(visible) - 1))
        project = visible[selected] if visible else None
        footer = notice or (catalog.warnings[0] if catalog.warnings else "")
        if confirming:
            footer = "Forget this project? y confirms; any other key cancels. History is kept."
        elif editing:
            footer = f"{editing}: {edit_value}▏  (Enter saves; Esc cancels)"
        elif searching:
            footer = f"Search: {query}▏  (Enter applies; Esc clears)"
        elif query:
            footer = f"Filter: {query}  ·  / to edit; Esc clears"
        render(screen, visible, selected, len(projects), agent, query, searching, footer, theme)
        try:
            key = screen.get_wch()
        except curses.error:
            continue
        if key == curses.KEY_RESIZE:
            continue
        if confirming:
            if key in ("y", "Y") and project:
                catalog.forget(project)
                projects = catalog.load()
                notice = "Forgotten. Press u to restore. Native history is unchanged."
            confirming = False
            continue
        if editing:
            if key == "\x1b":
                editing = None
            elif key in ("\n", "\r", curses.KEY_ENTER):
                if project and edit_value.strip():
                    catalog.set_metadata(project, edit_value, None)
                    projects = catalog.load()
                    notice = f"{editing} saved."
                editing = None
            elif key in ("\x7f", "\b", curses.KEY_BACKSPACE):
                edit_value = edit_value[:-1]
            elif isinstance(key, str) and key.isprintable():
                edit_value += key
            continue
        if searching:
            if key == "\x1b":
                searching, query = False, ""
            elif key in ("\n", "\r", curses.KEY_ENTER):
                searching = False
            elif key in ("\x7f", "\b", curses.KEY_BACKSPACE):
                query = query[:-1]
            elif isinstance(key, str) and key.isprintable():
                query += key
            selected = 0
            continue
        if key == "\x1b" and query:
            query = ""
        elif key in ("q", "\x1b"):
            return None
        elif key == "n":
            return Selection(agent)
        elif key == "\t":
            agent = AGENTS[(AGENTS.index(agent) + 1) % len(AGENTS)]
        elif key == "/":
            searching = True
        elif key == "?":
            notice = "s summary + names · c done/open · a archive · u undo · Tab switches tool"
        elif key == 's' and project:
            return Selection(agent, project, 'review')
        elif key == "u":
            restored = catalog.store.restore()
            projects = catalog.load()
            notice = "Restored the last forgotten project." if restored else "Nothing to restore."
        elif key == "d" and project:
            confirming = True
        elif key == "a" and project:
            catalog.forget(project)
            projects = catalog.load()
            notice = "Archived. Press u to restore. Native history is unchanged."
        elif key == 'c' and project:
            catalog.toggle_completed(project)
            projects = catalog.load()
            notice = "Marked active." if project.status == "Completed" else "Marked completed."
        elif key == "r" and project:
            editing, edit_value = "Name", ""
        elif key in (curses.KEY_UP, "k") and visible:
            selected = (selected - 1) % len(visible)
        elif key in (curses.KEY_DOWN, "j") and visible:
            selected = (selected + 1) % len(visible)
        elif key in ("\n", "\r", curses.KEY_ENTER) and project:
            return Selection(agent, project)
