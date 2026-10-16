# Compatibility and troubleshooting

## Supported scope

macOS and Linux, Python 3.10+, bash/zsh wrappers, UTF-8 terminals. `curses` and POSIX
file locks are required. The picker requires at least 42 columns × 16 rows. Use
`list --json` when a terminal is unavailable. WSL is the Windows option.

| Agent | Local discovery | Native launch/resume |
| --- | --- | --- |
| Codex | Latest `state_N.sqlite` threads, fallback `session_index.jsonl` | `codex resume ID PROMPT` |
| Claude Code | `projects/*/*.jsonl`, excluding sidechains | `claude --resume ID PROMPT`; new UUID with `--session-id` |
| Copilot CLI | `session-state/*/events.jsonl` session start and user messages | `copilot --session-id ID --interactive PROMPT`; or `gh copilot -- …` |

Local checks during development verified Codex CLI 0.163.0, Claude Code 2.1.301,
and Copilot CLI 1.0.98 command options. Tests use
synthetic histories for all adapters. Real authenticated model execution is not
part of automated tests, and broad version compatibility is not guaranteed.

Native history schemas are implementation details. Partial JSONL lines are skipped
to tolerate a concurrent writer. Unsupported Codex schemas produce warnings and
attempt index fallback. Some index entries lack directories; those can be listed
but cannot safely be launched by this picker. Claude sessions without a main
conversation and Copilot logs without a session-start record are skipped. Current
Copilot titles use the first user prompt; rename them here for clearer summaries.

## Known limits

- This is a terminal launcher, not a replacement for desktop app startup screens.
- No direct cloud, remote-host, or IDE-only history import; no cross-Mac syncing.
- The original conversation history remains native to each tool. Shared notes
  provide context, not an equivalent model state or automatic transcript conversion.
- Handoff maintenance depends on the agent following the launch prompt. Review
  notes when switching; do not assume another tool sees the latest turn.
- New (`n`) starts a plain native conversation. Handoff setup happens when that
  conversation is subsequently resumed through the picker. Lifecycle still works
  automatically: discoveries are Active, completion is a `c` toggle, and new native
  activity reopens completed projects on the next discovery. There is no background
  model service inferring whether work is semantically complete.
- Avoid editing the same handoff from two tools simultaneously. Agent-written
  Markdown is not a mergeable database transaction.
- If a first cross-tool Codex process crashes, or unrelated new Codex sessions
  appear in the same directory during launch, linking may remain unresolved.
- Missing or archived native sessions are not reconstructed from launcher metadata.
- Forget does not reduce the disk space used by the native agent's histories.
- The original personal prototype is not automatically imported. Point to the
  original native histories and transfer desired handoff content explicitly.

## Diagnosis

Run `agent-projects doctor`. Confirm native binaries and configuration directories.
If `copilot` is not on PATH but current `gh` is available, the launcher uses
`gh copilot`; that command may offer a first-time installation. Check `gh copilot
-- --help` for forwarded options. The retired `gh-copilot` extension is unsupported.

If Terminal still opens the agent directly, ensure `agent-projects` is on PATH,
remove the old prototype's shell-source line, add the README's `shell-init` line,
and open a fresh shell. Wrappers only intercept bare interactive invocations.

For a damaged `state.json`, back up the whole data directory before editing it.
The launcher reports malformed or unknown-version state and refuses to overwrite
it. Do not delete handoffs as a first troubleshooting step. Backups can contain
private work; keep them local.

## CLI references

- [Codex CLI reference](https://learn.chatgpt.com/docs/cli/reference)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Copilot CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
- [Copilot local session storage](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices)
