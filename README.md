# Agent Project Launchpad

**Pick up your work with Codex, Claude Code, or GitHub Copilot CLI.**

A keyboard-first terminal picker for your agent projects. See what you were
working on, when you last touched it, and where you left off. Switch agents
with shared project notes and recent conversation context carried along.

Type `claude`, `codex`, or `gh copilot` as usual. Pick a project and press Enter
to continue. Your existing conversations appear automatically, including projects
you worked on with another agent. The preview shows who you last used;
“Continue with” shows who will pick up the work.

![Agent Project Launchpad picker showing projects, lifecycle status, agent switching, and keyboard controls](https://raw.githubusercontent.com/ssebro/agent-project-launchpad/v1.0.0/docs/preview.png)

*The actual picker renderer with fictional demo projects.*

## Install and enable

Requires macOS or Linux, Python 3.10+, and an installed agent.

```sh
pipx install agent-project-launchpad
agent-launchpad setup
```

Open a new Terminal and start your agent as usual:

```sh
claude       # Open the picker with Claude Code selected
codex        # Open it with Codex selected
gh copilot   # Open it with GitHub Copilot selected
```

“New conversation” is selected first: press Enter for a fresh session in your
current directory. Use ↑/↓ and Enter to resume a saved project. Press `n` to
start fresh from anywhere in the list. Resume prompts include the project's
name and saved summary when available.

`setup` enables the picker for your normal commands in bash/zsh and backs up
the startup file it changes. You only need to run it once.
Check the installation with `agent-launchpad check-shell`.

Need [pipx](https://pipx.pypa.io/) or prefer a virtual environment?
See the [installation guide](https://github.com/ssebro/agent-project-launchpad/blob/v1.0.0/docs/guide.md#install).

## Try the demo

```sh
agent-launchpad demo
```

This runs the real picker with fictional projects. It launches no agents, makes
no model requests, and leaves your existing sessions alone.

## Everyday controls

| Key | Action |
| --- | --- |
| `↑` / `↓`, `Enter` | Start a new conversation or resume a saved project |
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
background. [Details and privacy](https://github.com/ssebro/agent-project-launchpad/blob/v1.0.0/SECURITY.md).

To remove startup integration, run `agent-launchpad uninstall-shell`.

[User guide](https://github.com/ssebro/agent-project-launchpad/blob/v1.0.0/docs/guide.md) · [Troubleshooting](https://github.com/ssebro/agent-project-launchpad/blob/v1.0.0/docs/compatibility.md) ·
[Contributing](https://github.com/ssebro/agent-project-launchpad/blob/v1.0.0/CONTRIBUTING.md) · [Architecture](https://github.com/ssebro/agent-project-launchpad/blob/v1.0.0/docs/architecture.md) · [MIT license](https://github.com/ssebro/agent-project-launchpad/blob/v1.0.0/LICENSE)
