# Agent Project Launchpad

**Pick up your work with Codex, Claude Code, or GitHub Copilot CLI.**

A keyboard-first terminal picker for your agent projects. See what you were
working on, when you last touched it, and where you left off. Switch agents
with shared project notes and recent conversation context carried along.

Type `claude`, `codex`, or `gh copilot` as usual. Pick a project and press Enter
to continue. Your existing conversations appear automatically, including projects
you worked on with another agent. The preview shows who you last used;
“Continue with” shows who will pick up the work.

![Agent Project Launchpad picker showing projects, lifecycle status, agent switching, and keyboard controls](docs/preview.png)

*The actual picker renderer with fictional demo projects.*

## Install and enable

Requires macOS or Linux, Python 3.10+, and at least one agent already installed.

```sh
pipx install git+https://github.com/ssebro/agent-project-launchpad.git
agent-launchpad setup
```

Open a new Terminal and start your agent as usual:

```sh
claude       # Open the picker with Claude Code selected
codex        # Open it with Codex selected
gh copilot   # Open it with GitHub Copilot selected
```

Choose a project with ↑/↓ and press Enter, or press `n` to start something new.

`setup` enables the picker for your normal commands in bash/zsh and backs up
the startup file it changes. You only need to run it once.
Check the installation with `agent-launchpad check-shell`.

Need [pipx](https://pipx.pypa.io/) or prefer a virtual environment?
See the [installation guide](docs/guide.md#install).

## Try the demo

```sh
agent-launchpad demo
```

This runs the real picker with fictional projects. It launches no agents, makes
no model requests, and leaves your existing sessions alone.

## Everyday controls

| Key | Action |
| --- | --- |
| `↑` / `↓`, `Enter` | Select and continue a project |
| `Tab` | Change the agent to continue with |
| `n` | Start something new |
| `/` | Search |
| `s` | Generate a summary and suggested names; review before saving |
| `r` | Rename manually |
| `c` | Complete / reopen |
| `a`, `u` | Archive / undo archive |
| `?`, `Esc` | Help / cancel |

Projects start Active automatically. New conversation activity reopens completed
work. Opening an agent and leaving without a new request keeps the project’s
name, last agent, date, and completion status. Archiving keeps the original history and can be undone.

## What carries over?

Each project has shared notes for decisions, progress, and next steps. Before
continuing, the launcher refreshes recent conversation excerpts and source
references for the selected agent to read. Full conversations stay in their
original agents. Context excerpts are bounded; important gaps still need review.

Data stays on your Mac or Linux machine until an agent reads it as model context.
Summaries use your existing agent account and normal usage. Nothing runs in the
background. [Details and privacy](SECURITY.md).

To remove startup integration, run `agent-launchpad uninstall-shell`.

[User guide](docs/guide.md) · [Troubleshooting](docs/compatibility.md) ·
[Contributing](CONTRIBUTING.md) · [Architecture](docs/architecture.md) · [MIT license](LICENSE)
