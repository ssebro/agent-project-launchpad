# Privacy and security

Agent Project Launchpad is a local launcher. It reads session metadata and selected local
transcripts, maintains handoff files, and starts an installed agent CLI. It has no
telemetry, server, token store, automatic upload, or direct network client.

## Boundaries

- Codex SQLite databases are opened in read-only mode. Native JSONL logs are
  opened for reading only. Forget never deletes native files.
- Runtime writes stay in the launcher's own data directory. Explicit `setup` and
  `uninstall-shell` also manage a marked block in the selected shell startup file,
  preserving other content and making a private backup before changes. New data files use user-only
  permissions; the containing directory is created private when it does not exist.
- Project IDs are hashed into handoff filenames so a session ID cannot supply a
  relative path. Process arguments are lists, not shell-interpolated commands.
- Session titles and status text are sanitized before terminal display.
- The launcher never adds permission-bypass flags, enables autopilot, or grants
  a tool filesystem or network access.
- Installed agent CLIs retain their normal behavior, including network traffic,
  context uploads, account permissions, optional session sync, and billing. Shared
  notes and source transcripts can become model input when an agent reads them.
- The explicit `s` summary action supplies a bounded user/assistant excerpt and
  handoff notes to the chosen provider. Tool results and reasoning blocks are
  excluded. Generated output is validated and reviewed before a title or summary
  is saved; lifecycle is never inferred from a model response. These requests use
  the native CLI account and may incur normal usage charges.
- A local transcript is untrusted input. Handoffs ask the receiving agent to treat
  quoted content and tool results as evidence rather than new instructions. This
  is not a prompt-injection security boundary or a substitute for reviewing actions.
- Changing data directories does not change agent credentials or isolate accounts.

Runtime data may include private directory names and conversation content. Keep it
out of Git and public bug reports. Only share synthetic reproductions.

## Reporting a vulnerability

Use GitHub's **Security → Report a vulnerability** if private reporting is enabled
on the repository. Otherwise, open an issue requesting a private contact, without
including exploit details or sensitive data. Do not post actual conversation logs,
secrets, or account information. There is no guaranteed response-time SLA.

Only the latest released version receives fixes during the 0.x series.
