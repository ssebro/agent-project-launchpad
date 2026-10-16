# Contributing

Small, focused contributions are welcome. For a new adapter or a large behavior
change, start with an issue describing the user workflow and compatibility needs.

## Local setup

Install the development extras and run the commands in the README. Tests use
Python's standard `unittest` framework, temporary directories, synthetic SQLite
databases, and synthetic JSONL events. They do not need an agent subscription,
network access, real history, or API credentials. CI runs on macOS and Linux.

## Code guidelines

- Keep discovery adapters read-only, independent of UI and launch behavior.
- Keep native session associations explicit. A matching directory alone is not
  enough to merge two existing conversations.
- Call processes with argument lists and preserve normal permission prompts.
- Persist only necessary local metadata, outside the source package. Use the
  store's locked transactions and atomic replacement for metadata changes.
- Report unsupported formats and unreadable files with actionable messages.
- Add behavioral tests for changed keyboard flows, discovery formats, and
  cross-tool linking. Cover malformed/partial input and failed starts.
- Use clear names, type annotations at module boundaries, and small modules.
  Explain format assumptions and tradeoffs in comments rather than restating code.

Never attach actual session logs, paths, tokens, or private handoffs to an issue,
test fixture, screenshot, or pull request. Reproduce the format using invented data.

## Pull requests

Explain the problem and resulting behavior, then list relevant validation. Include
known compatibility limits. Update the README or compatibility notes for user-facing
changes. Keep unrelated cleanup separate. Maintainers may squash commits; no CLA
is required. Contributions are under the repository's MIT license.

## Releases

See [the release checklist](docs/releasing.md). Version 0.x reflects that native
history formats can change and adapters may need updates.
