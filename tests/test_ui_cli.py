import contextlib
import curses
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_launchpad.cli import main, shell_init
from agent_launchpad.models import Session
from agent_launchpad.projects import Catalog
from agent_launchpad.ui import Theme, choose, fit, render, text_width
from helpers import codex, paths


class Screen:
    def __init__(self, keys, size=(30, 120)):
        self.keys = iter(keys)
        self.size = size
        self.lines = []

    def keypad(self, _value):
        pass

    def erase(self):
        pass

    def refresh(self):
        pass

    def getmaxyx(self):
        return self.size

    def get_wch(self):
        return next(self.keys)

    def addstr(self, y, x, text, style):
        self.lines.append((y, x, text, style))


class UITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = paths(Path(self.temp.name))
        codex(self.paths.codex, [("one", "First", self.temp.name, 200, None, 0, None),
                                 ("two", "Second", self.temp.name, 100, None, 0, None)])
        self.catalog = Catalog(self.paths)
        cursor = patch("agent_launchpad.ui.curses.curs_set")
        cursor.start()
        self.addCleanup(cursor.stop)

    def choose(self, keys, size=(30, 120)):
        return choose(Screen(keys, size), self.catalog, "codex")

    def test_arrow_navigation_and_column_order(self):
        import curses

        screen = Screen([curses.KEY_DOWN, curses.KEY_DOWN, "\n"])
        result = choose(screen, self.catalog, "codex")
        self.assertEqual(result.project.id, "codex:two")
        header = {text: x for y, x, text, _style in screen.lines if y == 4}
        self.assertLess(header['PROJECT'], header['STATUS'])
        self.assertLess(header['STATUS'], header['UPDATED'])

    def test_new_and_tool_switch(self):
        self.assertIsNone(self.choose(["n"]).project)
        self.assertEqual(self.choose(["\t", "\t", "n"]).agent, "copilot")

    def test_new_is_first_and_default_without_project_actions(self):
        for agent in ("codex", "claude", "copilot"):
            screen = Screen(["\n"])
            result = choose(screen, self.catalog, agent)
            self.assertIsNone(result.project)
            self.assertEqual(result.agent, agent)
            self.assertTrue(any(y == 6 and text == 'New conversation'
                                for y, _x, text, _style in screen.lines))
        before = [(p.id, p.title, p.status) for p in self.catalog.load()]
        result = self.choose(['d', 'a', 'c', 'r', 's', '\n'])
        self.assertIsNone(result.project)
        self.assertEqual(before, [(p.id, p.title, p.status) for p in self.catalog.load()])
        self.assertEqual(self.choose([curses.KEY_UP, '\n']).project.id, 'codex:two')

    def test_search_does_not_trigger_new_shortcut(self):
        result = self.choose(["/", "S", "e", "c", "o", "n", "d", "\n", "\n"])
        self.assertEqual(result.project.title, "Second")

    def test_forget_confirmation_and_undo(self):
        result = self.choose([curses.KEY_DOWN, "d", "y", "\n"])
        self.assertEqual(result.project.id, "codex:two")
        result = self.choose([curses.KEY_DOWN, "u", "\n"])
        self.assertEqual(result.project.id, "codex:one")
        self.assertEqual(self.choose([curses.KEY_DOWN, "d", "n", "\n"]).project.id, "codex:one")

    def test_rename_and_status(self):
        result = self.choose([curses.KEY_DOWN, "r", '\x15', *"Readable name", "\n", "c", "\n"])
        self.assertEqual(result.project.title, "Readable name")
        self.assertEqual(result.project.status, "Completed")

    def test_archive_shortcut_and_undo(self):
        result = self.choose([curses.KEY_DOWN, 'a', '\n'])
        self.assertEqual(result.project.id, 'codex:two')
        result = self.choose([curses.KEY_DOWN, 'u', '\n'])
        self.assertEqual(result.project.id, 'codex:one')

    def test_summary_shortcut_does_not_change_lifecycle(self):
        result = self.choose([curses.KEY_DOWN, 's'])
        self.assertEqual(result.action, 'review')
        self.assertEqual(result.project.status, 'Active')
        self.assertEqual(self.catalog.find(result.project.id).status, 'Active')

    def test_rename_starts_with_existing_name(self):
        result = self.choose([curses.KEY_DOWN, 'r', *' draft', '\n', '\n'])
        self.assertEqual(result.project.title, 'First draft')

    def test_search_opens_with_one_enter_and_supports_arrows(self):
        import curses

        self.assertEqual(self.choose(['/', *'Second', '\n']).project.id, 'codex:two')
        result = self.choose(['/', curses.KEY_DOWN, '\n'])
        self.assertEqual(result.project.id, 'codex:two')

    def test_unavailable_agent_keeps_picker_open(self):
        result = choose(Screen(['\n', 'n', 's', '\t', '\n']), self.catalog, 'codex',
                        available_agents={'codex': False, 'claude': True})
        self.assertEqual(result.agent, 'claude')

    def test_help_returns_to_same_selection(self):
        result = self.choose([curses.KEY_DOWN, '?', 'x', '\n'])
        self.assertEqual(result.project.id, 'codex:one')

    def test_empty_small_and_narrow_screens(self):
        for project in self.catalog.load():
            self.catalog.forget(project)
        self.assertIsNone(self.choose(["\n"]).project)
        self.assertIsNone(self.choose(["n"], (8, 30)).project)
        self.catalog.store.restore()
        self.assertIsNotNone(self.choose([curses.KEY_DOWN, "\n"], (24, 60)).project)

    def test_wide_unicode_and_escape_characters(self):
        self.assertLessEqual(text_width(fit("日本語のプロジェクト", 10)), 10)
        self.assertEqual(fit("abc", 5, pad=True), "abc  ")
        self.assertNotIn("\x1b", fit("bad\x1b[31m", 30))

    def test_dense_rows_and_semantic_command_styles(self):
        screen = Screen([], (24, 80))
        theme = Theme(accent=101, selected=102, key=103, warning=104)
        projects = self.catalog.load()
        render(screen, projects, 0, 2, 'codex', '', False, '', theme)
        titles = [(y, style) for y, x, text, style in screen.lines
                  if x == 3 and text in ('First', 'Second')]
        self.assertEqual([y for y, _style in titles], [6, 7])
        keys = [style for _y, _x, text, style in screen.lines if text == ' n ']
        self.assertEqual(keys, [theme.key])

    def test_last_agent_is_latest_native_activity_not_chosen_destination(self):
        project = self.catalog.load()[0]
        project.sessions['claude'] = Session('claude', 'newer', 'First', None, 300)
        project.sessions['copilot'] = Session('copilot', 'older', 'First', None, 150)
        for width in (80, 100, 120):
            screen = Screen([], (24, width))
            theme = Theme(previous_agent=123)
            render(screen, [project], 0, 1, 'codex', '', False, '', theme)
            texts = [text for _y, _x, text, _style in screen.lines]
            self.assertIn('Continue with Codex', texts)
            self.assertIn('Last used: ', texts)
            self.assertTrue(any(text == 'Claude Code' and style == theme.previous_agent
                                for _y, _x, text, style in screen.lines))
            self.assertNotIn('LAST AGENT', texts)

    def test_status_palette_and_no_color(self):
        theme = Theme(success=1, warning=2, danger=3, ready=4, muted=5)
        for status, expected in [('Done', 1), ('In progress', 2), ('Blocked', 3),
                                 ('Ready for review', 4), ('Not done', 5)]:
            self.assertEqual(theme.status(status), expected)
        with patch.dict('os.environ', {'NO_COLOR': '1'}), \
             patch('agent_launchpad.ui.curses.start_color') as start:
            self.assertEqual(Theme.initialize(), Theme())
            start.assert_not_called()


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = paths(Path(self.temp.name))
        codex(self.paths.codex, [("one", "Example", self.temp.name, 100, None, 0, None)])
        config = patch("agent_launchpad.cli.Paths.from_env", return_value=self.paths)
        config.start()
        self.addCleanup(config.stop)

    def invoke(self, args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = main(args)
        return code, output.getvalue(), error.getvalue()

    def test_list_json_and_set(self):
        code, output, _error = self.invoke(["list", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)[0]["id"], "codex:one")
        self.assertEqual(self.invoke(["set", "codex:one", "--name", "Readable"])[0], 0)
        self.assertIn("Readable", self.invoke(["list"])[1])

    def test_forget_restore(self):
        self.assertEqual(self.invoke(["forget", "codex:one"])[0], 0)
        self.assertEqual(json.loads(self.invoke(["list", "--json"])[1]), [])
        self.assertEqual(self.invoke(["restore"])[0], 0)
        self.assertEqual(len(json.loads(self.invoke(["list", "--json"])[1])), 1)

    def test_invalid_project_and_missing_set_fields(self):
        self.assertEqual(self.invoke(["handoff", "unknown"])[0], 1)
        self.assertEqual(self.invoke(["set", "codex:one"])[0], 1)

    def test_noninteractive_picker_is_actionable(self):
        with patch("sys.stdin.isatty", return_value=False):
            code, _output, error = self.invoke([])
        self.assertEqual(code, 1)
        self.assertIn("list --json", error)

    def test_shell_init_preserves_argument_forwarding(self):
        text = shell_init()
        for agent in ("codex", "claude", "copilot"):
            self.assertIn(f"command {agent} \"$@\"", text)
        self.assertIn('[ "$#" -eq 1 ] && [ "$1" = "copilot" ]', text)
        self.assertIn('command gh "$@"', text)
