"""Command-line entry point. No shell files are changed automatically."""

import argparse
import json
import shutil
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
    shell = commands.add_parser("shell-init", help="Print optional bash/zsh wrapper functions")
    shell.add_argument("--shell", choices=("bash", "zsh"), default="zsh")
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
    return root


def shell_init() -> str:
    blocks = []
    for agent in AGENTS:
        blocks.append(f'''{agent}() {{
  if [ "$#" -eq 0 ] && [ -t 0 ] && [ -t 1 ]; then
    command agent-projects --agent {agent}
  else
    command {agent} "$@"
  fi
}}''')
    blocks.append('''gh() {
  if [ "$#" -eq 1 ] && [ "$1" = "copilot" ] && [ -t 0 ] && [ -t 1 ]; then
    command agent-projects --agent copilot
  else
    command gh "$@"
  fi
}''')
    return "\n\n".join(blocks)


def run(args: argparse.Namespace) -> int:
    if args.command == "shell-init":
        print(shell_init())
        return 0
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
    elif args.command in ("set", "forget", "handoff", "resume"):
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
        else:
            return launch(catalog, project, args.agent)
    else:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError("The picker needs a terminal. Use 'agent-projects list --json' in scripts.")
        import curses

        from .ui import choose

        selection = curses.wrapper(choose, catalog, args.agent)
        if selection:
            return launch(catalog, selection.project, selection.agent)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError) as exc:
        print(f"agent-projects: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
