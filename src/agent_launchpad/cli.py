"""Command-line entry point. Explicit setup manages shell integration."""

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from . import __version__
from .config import Paths
from .launch import launch
from .models import AGENTS
from .projects import Catalog


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Resume projects with Codex, Claude Code, or Copilot CLI.")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--agent", choices=AGENTS, default="codex")
    root.add_argument("--data-dir", type=Path, help="Override local metadata and handoff directory")
    commands = root.add_subparsers(dest="command")
    commands.add_parser("pick", help="Open the keyboard picker (default)")
    listing = commands.add_parser("list", help="List discovered projects without starting an agent")
    listing.add_argument("--json", action="store_true")
    listing.add_argument("--all", action="store_true", help="Include forgotten projects")
    commands.add_parser("doctor", help="Show tool paths, data locations, and discovery warnings")
    commands.add_parser('demo', help='Try the real picker with fictional projects and no model calls')
    for name, help_text in [('setup', 'Enable the picker for your normal agent commands'),
                            ('uninstall-shell', 'Remove managed shell integration; keep session data'),
                            ('check-shell', 'Verify the picker loads in a fresh interactive shell')]:
        setup = commands.add_parser(name, help=help_text)
        setup.add_argument('--shell', choices=('bash', 'zsh'))
        if name != 'check-shell':
            setup.add_argument('--rc-file', type=Path, help='Use a custom shell startup file')
            setup.add_argument('--dry-run', action='store_true', help='Preview without writing files')
    shell = commands.add_parser("shell-init", help="Print managed bash/zsh launcher functions")
    shell.add_argument("--shell", choices=("bash", "zsh"), default="zsh")
    shell.add_argument('--launcher', type=Path, help=argparse.SUPPRESS)
    setting = commands.add_parser("set", help="Update a project's display name or status")
    setting.add_argument("id")
    setting.add_argument("--name")
    setting.add_argument("--status", choices=("active", "completed", "archived"))
    forget = commands.add_parser("forget", help="Hide a project; keep its native history and notes")
    forget.add_argument("id")
    restore = commands.add_parser("restore", help="Restore a project, or undo the last forget")
    restore.add_argument("id", nargs="?")
    handoff = commands.add_parser("handoff", help="Create or locate a project's shared Markdown notes")
    handoff.add_argument("id")
    resume = commands.add_parser("resume", help="Resume a project by its ID or unique ID prefix")
    resume.add_argument("id")
    review = commands.add_parser('review', help='Ask the selected agent for a summary and suggested names')
    review.add_argument('id')
    review.add_argument('--json', action='store_true', help='Print suggestions without applying them')
    return root


def shell_init(launcher: Path | None = None) -> str:
    command = shlex.quote(str(launcher)) if launcher else 'agent-launchpad'
    blocks = []
    for agent in AGENTS:
        blocks.append(f'''{agent}() {{
  if [ "$#" -eq 0 ] && [ -t 0 ] && [ -t 1 ]; then
    command {command} --agent {agent}
  else
    command {agent} "$@"
  fi
}}''')
    blocks.append('''gh() {
  if [ "$#" -eq 1 ] && [ "$1" = "copilot" ] && [ -t 0 ] && [ -t 1 ]; then
    command LAUNCHER --agent copilot
  else
    command gh "$@"
  fi
}'''.replace('LAUNCHER', command))
    return "\n\n".join(blocks)


def run(args: argparse.Namespace) -> int:
    if args.command == "shell-init":
        print(shell_init(args.launcher))
        return 0
    if args.command in ('setup', 'uninstall-shell', 'check-shell'):
        from .integration import (
            check_shell,
            configure,
            installed_launcher,
            shell_name,
            startup_file,
        )

        shell = shell_name(args.shell)
        if args.command == 'check-shell':
            statuses = check_shell(shell)
            for tool, good in statuses.items():
                print(f'{"OK" if good else "MISSING"}  {"gh copilot" if tool == "gh" else tool}')
            if not all(statuses.values()):
                print('Run agent-launchpad setup, then open a new Terminal. '
                      'If you have later aliases/functions, move the managed block after them.')
                return 1
        else:
            path = args.rc_file or startup_file(shell)
            removing = args.command == 'uninstall-shell'
            result = configure(shell, path, None if removing else installed_launcher(),
                               remove=removing, dry_run=args.dry_run)
            if args.dry_run:
                print(f'Would {"remove" if removing else "enable"} integration in {result.path}')
                print(result.preview)
            else:
                print(f'{"Removed" if removing else "Enabled"} shell integration: {result.path}'
                      if result.changed else f'Already {"removed" if removing else "enabled"}: {result.path}')
                if result.backup:
                    print(f'Backup: {result.backup}')
                print('Open a new Terminal.' if removing else
                      'Open a new Terminal, then type codex, claude, copilot, or gh copilot.\n'
                      'Verify startup with: agent-launchpad check-shell')
        return 0
    if args.command == 'demo':
        from .demo import run_demo

        return run_demo(args.agent)
    paths = Paths.from_env()
    if args.data_dir:
        paths = replace(paths, data=args.data_dir.expanduser().resolve())
    catalog = Catalog(paths)
    if args.command == "list":
        projects = catalog.load(include_hidden=args.all)
        if args.json:
            print(json.dumps([asdict(p) for p in projects], default=str, indent=2))
        else:
            for project in projects:
                date = datetime.fromtimestamp(project.updated).astimezone().strftime("%Y-%m-%d %H:%M")
                print(f"{project.title}\t{project.status}\t{date}\t{project.id}"
                      + ("\t[forgotten]" if project.hidden else ""))
        for warning in catalog.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
    elif args.command == "doctor":
        from .integration import configured, shell_name, startup_file

        try:
            rc = startup_file(shell_name())
            print(f'Managed shell setup: {"configured" if configured(rc) else "not configured — run agent-launchpad setup"} ({rc})')
        except (ValueError, OSError) as exc:
            print(f'Shell integration: {exc}')
        for agent in AGENTS:
            print(f"{agent}: {shutil.which(agent) or 'not on PATH'}")
        print(f"Data: {paths.data}\nCodex history: {paths.codex}\nClaude history: {paths.claude}"
              f"\nCopilot history: {paths.copilot}")
        if not shutil.which("copilot") and shutil.which("gh"):
            print("Copilot launch: gh copilot -- (may prompt to install Copilot CLI)")
        print(f"Projects discovered: {len(catalog.load())}")
        for warning in catalog.warnings:
            print(f"Warning: {warning}")
    elif args.command == "restore":
        project_id = catalog.find(args.id).id if args.id else None
        print(catalog.store.restore(project_id) or "Nothing to restore.")
    elif args.command in ("set", "forget", "handoff", "resume", 'review'):
        project = catalog.find(args.id)
        if args.command == "set":
            if args.name is None and args.status is None:
                raise ValueError("Specify --name or --status")
            catalog.set_metadata(project, args.name, args.status)
        elif args.command == "forget":
            catalog.forget(project)
            print("Forgotten. Native history is unchanged; use restore to undo.")
        elif args.command == "handoff":
            print(catalog.prepare(project))
        elif args.command == 'review':
            from .review import generate, interactive_review

            if args.json:
                print(json.dumps(asdict(generate(catalog, project, args.agent)), indent=2))
            else:
                print(interactive_review(catalog, project, args.agent))
        else:
            return launch(catalog, project, args.agent)
    else:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError("The picker needs a terminal. Use 'agent-launchpad list --json' in scripts.")
        import curses

        from .ui import choose

        notice = ''
        while True:
            available = {agent: bool(shutil.which(agent) or
                                     (agent == 'copilot' and shutil.which('gh'))) for agent in AGENTS}
            selection = curses.wrapper(choose, catalog, args.agent, notice, available)
            if not selection:
                break
            if selection.action == 'review':
                from .review import interactive_review

                try:
                    notice = interactive_review(catalog, selection.project, selection.agent)
                except KeyboardInterrupt:
                    notice = 'Summary cancelled. No changes saved.'
                except (OSError, ValueError, subprocess.SubprocessError, EOFError) as exc:
                    notice = f'Summary failed: {exc}'
                args.agent = selection.agent
            else:
                return launch(catalog, selection.project, selection.agent)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, subprocess.SubprocessError, EOFError) as exc:
        print(f"agent-launchpad: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
