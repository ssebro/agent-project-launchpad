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
| `integration.py` | Set up, check, and remove the core shell startup integration |
| `activity.py` | Fingerprint user requests to distinguish work from automatic handoff visits |
| `context.py` | Extract bounded dialogue and refresh cross-agent context before resume |
| `models.py` | Session, project, and discovery result types |
| `discovery.py` | Read-only format adapters; return sessions and warnings |
| `store.py` | Versioned metadata transactions, private files, handoff paths |
| `projects.py` | Join explicit native links and handoffs into the project list |
| `launch.py` | Build native argument lists, start tools, associate new sessions |
| `review.py` | Extract bounded dialogue, request agent suggestions, save accepted reviews |
| `ui.py` | Keyboard interactions and terminal layout |
| `cli.py` | Parse commands, print shell integration, report errors |
| `demo.py` | Exercise the real UI with fictional disposable histories |

## Identity

A newly discovered project's identity is `agent:native-session-id`. A project can
later own one native session per tool through `state.json`. Sessions are joined
only by those explicit associations. Tasks sharing a working directory do not
automatically merge. Duplicate ownership is treated as an error rather than an
invitation to guess.

Renames and lifecycle are launcher metadata. New discoveries default to Active.
Completion records the last native update for each associated session. If native
activity advances past that baseline, the project is displayed as Active again.
A resume with a new user request sets Active. Bootstrap-only visits preserve
the prior lifecycle, activity timestamps, last agent, and summary freshness. Archive hides the project and records the prior
lifecycle for undo. Native activity never silently unarchives a project.

The handoff's `Status:` line is an optional progress note in the preview, separate
from lifecycle. Handoff edits do not reopen completed work. Native session
timestamps and handoff modification times determine visible last-update time.

## Persistence

```text
agent-launchpad/
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
   Refresh a separate context packet with current source references, timestamps,
   recent dialogue, and explicit evidence gaps. Preserve the shared Markdown notes.
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

## On-demand review

The summary action exits curses temporarily, invokes the selected agent in a new
review context, and presents the result before saving. It never resumes the source
session to generate a review. Evidence includes up to 8,000 handoff characters and
up to two recent native transcripts, each limited to 10,000 characters of extracted
user/assistant text. Tool results and reasoning blocks are excluded. No local
program can guarantee a model will ignore malicious instructions in evidence;
tool restrictions and isolation reduce the available actions.

Validated suggestions are displayed first. On acceptance, the summary and optional
selected name are stored, and a marked review block is added to the shared handoff
without replacing other notes. Native update baselines and handoff mtime track
whether a saved summary may be stale. Summaries do not control lifecycle. Copilot's
separate review-session IDs are kept in metadata so its generated review history
does not clutter the project list; native files are not deleted.

## Empty visits and display titles

An automatic handoff prompt and its assistant replies are setup, not new user
work. Native session links are retained for resume, but an unchanged user-request
fingerprint keeps the previous activity timestamp (zero for an unused new link).
Later user requests, including ones made outside the launcher, invalidate that
baseline. Missing, unreadable, empty, or partially written transcripts remain
unknown rather than proving an empty visit or new work. Unknown evidence preserves
last-known activity and completion metadata with a discovery warning. Exit
reconciliation runs in `finally`, so Ctrl-C still associates an unambiguous new
Codex session and records any real requests made before interruption.
Only launcher metadata changes; native conversations are never rewritten.

An explicit display name takes precedence. Otherwise the most recent descriptive
native title from work is used, excluding known generic handoff titles. This is
a conservative selection rule, not model-based comparison of competing names;
the on-demand summary review can propose a more meaningful name for the user to
accept. A no-op does not freeze future title updates from genuine work.
