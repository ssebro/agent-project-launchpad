# User guide

**Pick up your work with Codex, Claude Code, or GitHub Copilot CLI.**

Type `claude`, `codex`, or `gh copilot` as usual. Agent Project Launchpad shows
your existing projects, when you last worked on them, and where you left off.
Choose one and press Enter to continue with the agent you launched. Shared
project notes and recent conversation context carry along, including when
the project was previously worked on with another agent.

## Install

Requires **Python 3.10+**, macOS or Linux, a UTF-8 terminal, and at least one
supported agent installed and authenticated separately. Windows is not supported
natively; use WSL. There are **no runtime Python dependencies**.

With [pipx](https://pipx.pypa.io/):

```sh
pipx install git+https://github.com/ssebro/agent-project-launchpad.git
agent-launchpad setup
```

Or install from a checkout in an isolated environment:

```sh
git clone https://github.com/ssebro/agent-project-launchpad.git
cd agent-project-launchpad
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/agent-launchpad setup
```

`setup` is part of installation: it enables the picker for your normal agent
commands in bash/zsh, backing up the startup file before changing it. Run it once,
then open a new Terminal. If you installed in a virtual environment, it does not
need to stay activated.

The package is installed from GitHub; it is not published on PyPI.

## Pick up your work

In a new Terminal, use whichever agent you want to work with:

```sh
claude       # Open the picker with Claude Code selected
codex        # Open it with Codex selected
gh copilot   # Open it with GitHub Copilot selected
```

Existing local conversations appear automatically. Use ↑/↓ to choose a project
and Enter to continue with the agent you launched. The header says “Continue
with Codex” (or your chosen agent); the project preview shows which agent most
recently worked on it. If that changes your choice, press Tab to change the
agent you will continue with.
Press `n` to start a new conversation in your current Terminal directory.
Standalone `copilot` also opens the picker when installed.

Commands with arguments, such as `claude --help` or `codex exec ...`, keep their
normal behavior. If the picker does not appear, run `agent-launchpad check-shell`;
see [shell setup details](#shell-setup-details) below.

| Key | Action |
| --- | --- |
| `n` | Start a new conversation immediately, in the current Terminal directory |
| `↑` / `↓` or `k` / `j` | Select a project |
| `Enter` | Resume the selected project with the selected tool |
| `Tab` | Change the agent to continue with: Codex → Claude Code → Copilot |
| `/` | Filter by project name, status, or directory |
| `r` | Rename the project in this picker |
| `s` | Ask the selected agent for a progress summary and suggested names |
| `c` | Toggle the project between Active and Completed |
| `a` | Archive the project from the shared list |
| `u` | Restore the last archived project, including after a restart |
| `q` | Quit |

Names follow the most recent descriptive native session title or first prompt
until you choose a name yourself. Generic handoff titles such as “Resume This
Project” are excluded. A real conversation can provide a better native title;
opening and leaving an agent cannot. Use `s` for an agent's naming suggestions
and review them before saving.
Status tracks the lifecycle: **Active, Completed, or Archived**, not live running/idle activity. Dates are
local time and reflect the latest native session or shared-handoff modification.
Distinct tasks in the same directory remain separate projects. Rows are compact:
project name, status, then date. The preview shows the full selected name,
directory, and which agent most recently worked on the project, based on native
conversation activity. That history is separate from the agent you choose to
continue with. Narrow terminals shorten the date and keep one line per project.
Color distinguishes the selection, command keycaps, and lifecycle; text
labels and a selection marker also work in monochrome. Set `NO_COLOR=1` to opt out.

Discovered projects are Active automatically; there is no status field to fill
out. Press `c` when work is complete, and `c` again to reopen it. Resuming a project
marks it Active when you make a new request. Opening an agent, reading the
automatic handoff, and leaving does not change the name, last agent, update date,
or completion status. A discussion or review counts as work even without file
edits. New native session activity after completion also makes it Active
at the next discovery. Handoff edits alone do not reopen completed work.

**Archive is reversible:** it hides the project from all three pickers. Native
conversation history and shared notes stay on disk. `u` restores the most recently
archived project to its prior lifecycle, including across restarts. Archived
projects stay hidden even if their native session changes. Native deletion is left
to each tool. `agent-launchpad list --all` includes archived projects. The `forget`
CLI command and legacy `d`-then-`y` shortcut are aliases for archive.

### Agent-generated summaries and names

Press `s` on a project. The selected agent receives a bounded sample of recent
user/assistant messages and existing handoff notes, then suggests a short progress
summary, next steps, and up to three names. Tool output and hidden reasoning are
excluded from the sample. The result may be incomplete if important context is
outside that excerpt; the prompt asks the agent to state uncertainty.

After seeing the result, press Enter to save only the summary, select a suggested
name by number to save both, or `q` to discard. Names and summaries never change
without that choice; reviews do not change lifecycle. Saved summaries appear in
the preview and shared handoff. New native activity or handoff edits mark the
summary as potentially stale.

This is an explicit model request using your selected CLI's account, permissions,
and billing. It runs only when requested. Codex reviews use ephemeral read-only
sessions; Claude reviews disable tools and native persistence; Copilot reviews deny
tools and use separate session IDs excluded from this picker. No background
summarizer runs. Review-generation flags are checked against the documented native
CLIs; authenticated model inference is not part of the automated tests.

For scripts, `agent-launchpad --agent claude review ID --json` prints suggestions
without applying them. `list --json` includes previously saved summaries without
calling a model.

### Shell setup details

If you skipped setup during installation, enable the picker with:

```sh
agent-launchpad setup
```

Setup detects bash/zsh, backs up the startup file before changing it, and adds one
managed block. Open a new Terminal, then verify:

```sh
agent-launchpad check-shell
```

Bare `codex`, `claude`, `copilot`, and `gh copilot` open the picker. Commands with
arguments, such as `codex --help` or `gh repo list`, pass through unchanged.
`command codex` bypasses the picker when you need the original CLI directly.
Setup uses the installed executable's absolute path, so a virtual environment
need not remain activated. Agent binaries are never replaced.

For a custom startup file or to preview the change:

```sh
agent-launchpad setup --shell zsh --rc-file ~/.zshrc --dry-run
```

For zsh, setup respects `ZDOTDIR`. For bash on macOS, it uses the first existing
login profile; on Linux it uses `.bashrc`. `--rc-file` handles custom arrangements.
Check-shell reads a fresh interactive shell's startup files without invoking an
agent. If you define conflicting aliases/functions later, move the managed block
below them. Shell startup timeouts are reported rather than treated as success.

`agent-launchpad shell-init` remains available for people maintaining their own
dotfiles, but ordinary installation uses `setup`.

For Copilot, a standalone `copilot` binary is preferred. Otherwise the launcher
uses `gh copilot -- …`; current GitHub CLI versions may offer to install Copilot
on first use. This supports the current agentic Copilot CLI, not the retired
`gh-copilot` suggestion extension. It does not manage cloud or IDE-only sessions.

### Shared handoffs

Type your normal agent command, select a project, and press Enter. The launcher
creates or refreshes its shared handoff automatically. To pick up a Claude
project with Codex, type `codex`, select that project, and press Enter. You can
also change the receiving agent with Tab while browsing the picker.

A handoff contains the goal, decisions, findings, changed files, validation, and
next steps. You can
edit it yourself. A `Status: ...` line provides an optional progress note in the
preview; it does not control Active/Completed/Archived. Every resume
asks the agent to read and maintain the handoff. This is an instruction, not a
guarantee: check the notes when switching agents. Agent Project Launchpad does not run a
background model to summarize your work. New (`n`) starts a normal native
conversation; shared handoff instructions are added on its first picker resume.

The first resume in another tool creates its native conversation. Subsequent
launches resume that conversation through a stored link. Claude and Copilot use
explicit session IDs. New Codex sessions are linked after the process exits only
when exactly one newly discovered session matches the working directory. An
ambiguous match is left unlinked and reported. See [limitations](compatibility.md).

### Direct commands and scripting

Everyday use starts with `claude`, `codex`, or `gh copilot`. The `agent-launchpad`
command also provides diagnostics, scripting, and direct access to the picker:

```sh
agent-launchpad --agent claude     # Open the picker directly
agent-launchpad list               # Tab-separated project listing
agent-launchpad list --json        # IDs, directories, native links, saved summaries
agent-launchpad doctor             # Tool paths and discovery warnings
agent-launchpad handoff ID         # Create or locate a project's shared notes
agent-launchpad --agent claude resume ID
```

Use an actual project ID from `list`; unique ID prefixes also work. These commands
are alternatives for scripts and troubleshooting; they are not needed to resume
projects through your usual agent commands.

## Local data and privacy

Native history is read in place. Agent Project Launchpad writes its own metadata and
handoffs under `${XDG_STATE_HOME:-~/.local/state}/agent-launchpad/`, outside the
source checkout. The launcher itself makes no network requests, reads no auth
tokens, and never changes native history or permission settings. Agent CLIs keep
their own normal authentication, network, permission, and billing behavior.

**When an agent reads a handoff or transcript, it may send that content to its
model provider under your existing settings.** Think about that boundary when
moving a project between work and personal accounts. Do not commit your runtime
data to this repository. See [privacy and security](../SECURITY.md).

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `AGENT_LAUNCHPAD_HOME` | `$XDG_STATE_HOME/agent-launchpad` | Launcher metadata and handoffs |
| `XDG_STATE_HOME` | `~/.local/state` | Base directory for launcher data |
| `CODEX_HOME` | `~/.codex` | Codex history discovery |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Claude Code history discovery |
| `COPILOT_HOME` | `~/.copilot` | Copilot CLI history discovery |

`--data-dir PATH` overrides `AGENT_LAUNCHPAD_HOME`. Agent-specific environment
variables are inherited by the launched tools. Separate work/personal histories
need separate agent configuration as well as separate launcher data directories.

## Uninstall

Run `agent-launchpad uninstall-shell` and open a new shell,
then run `pipx uninstall agent-project-launchpad` (or delete your dedicated virtual
environment). Your native sessions are unaffected. Launcher data is deliberately
retained; remove its data directory separately if you no longer want the notes.

## Development

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
.venv/bin/python -m build
```

Tests can also run with no installed dependencies:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](../CONTRIBUTING.md), the [architecture](architecture.md),
and [compatibility notes](compatibility.md). Contributions should use
synthetic session fixtures; never upload actual conversation history.

## License

[MIT](../LICENSE). Independent community software; not affiliated with OpenAI,
Anthropic, or GitHub. Product names belong to their respective owners.

The previous `agent-projects` command and `AGENT_PROJECTS_HOME` setting remain supported. Existing state in the former default directory is reused automatically.

## Refresh the README preview

On macOS, run `PYTHONPATH=src python3 docs/tools/capture_preview.py` from the
checkout. This uses the actual picker renderer and disposable demo data, then
rasterizes terminal cells with the system monospace font at 2× resolution.
The README embeds the PNG with its natural aspect ratio. Swift is needed only
to regenerate this documentation image.
