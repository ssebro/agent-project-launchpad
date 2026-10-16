# Architecture

The core data flow is:

```text
Native histories ──read-only──> Discovery adapters ──> Sessions
                                                      │
Local metadata + Markdown handoffs ─────────────────> Catalog
                                                      │
                                               CLI / curses UI
                                                      │
                                           Native CLI + handoff prompt
```

## Modules

| Module | Responsibility |
| --- | --- |
| `config.py` | Resolve user-controlled data and history locations |
| `models.py` | Session, project, and discovery result types |
| `discovery.py` | Read-only format adapters; return sessions and warnings |
| `store.py` | Versioned metadata transactions, private files, handoff paths |
| `projects.py` | Join explicit native links and handoffs into the project list |
| `launch.py` | Build native argument lists, start tools, associate new sessions |
| `ui.py` | Keyboard interactions and terminal layout |
| `cli.py` | Parse commands, print shell integration, report errors |

## Identity

A newly discovered project's identity is `agent:native-session-id`. A project can
later own one native session per tool through `state.json`. Sessions are joined
only by those explicit associations. Tasks sharing a working directory do not
automatically merge. Duplicate ownership is treated as an error rather than an
invitation to guess.

Renames and lifecycle are launcher metadata. New discoveries default to Active.
Completion records the last native update for each associated session. If native
activity advances past that baseline, the project is displayed as Active again.
Resuming explicitly sets Active. Archive hides the project and records the prior
lifecycle for undo. Native activity never silently unarchives a project.

The handoff's `Status:` line is an optional progress note in the preview, separate
from lifecycle. Handoff edits do not reopen completed work. Native session
timestamps and handoff modification times determine visible last-update time.

## Persistence

```text
agent-projects/
├── state.json                  # version, projects, forgotten stack
├── state.lock                  # short-lived metadata transaction lock
└── handoffs/
    ├── <sha256-project-id>.md   # source context and ongoing notes
    └── <sha256>.<agent>.lock    # prevent duplicate launcher starts
```

`Store.edit()` takes an exclusive POSIX file lock, reloads current state, and
atomically replaces JSON on success. Failed transactions leave old JSON untouched.
No global lock is held while a model session runs. A per-project/tool process lock
prevents two launcher invocations from competing to create that same native link.
These are local-filesystem guarantees, not a distributed lock or sync protocol.

## Cross-tool launch

1. Validate the selected binary and working directory.
2. Create a handoff if needed, including relevant local transcript paths.
3. Read existing native links or allocate a pending UUID for Claude/Copilot.
4. Start the tool with a handoff-reading prompt and its native resume arguments.
5. After exit, record a new link only if its native transcript exists. For Codex,
   associate only a unique newly discovered session in the working directory.

A failed model start preserves notes and never becomes a successful session link.
An interrupted first Codex launch may need a manual association in a future
version; existing history remains independently discoverable.

## Adding a tool

Add a read-only adapter returning `Discovery`, define launch arguments, extend
environment path resolution and tool selection, and add synthetic fixture tests.
Verify both a fresh launch and native resume against current official CLI help.
Document the format and tested versions. Do not add a new runtime dependency just
to parse an incidental metadata file if the event log already contains the data.
