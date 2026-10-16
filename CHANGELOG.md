# Changelog

## 0.1.0 — Unreleased

- Preserve project names and activity metadata when a resumed agent only reads its automatic handoff.
- Discover local Codex, Claude Code, and GitHub Copilot CLI conversations.
- Resume native sessions with per-project shared Markdown handoffs.
- Search, rename, switch tools, complete/reopen, and archive/restore from the keyboard.
- Automatic Active lifecycle; new native activity reopens completed projects.
- On-demand agent summaries, next steps, and suggested names with explicit review
  before saving, plus stale-summary detection.
- Core bash/zsh startup integration for bare `codex`, `claude`, `copilot`, and `gh copilot`.
- Core `setup` command installs startup integration with backups, idempotent edits,
  and clean removal; `check-shell` verifies fresh-shell behavior.
- Safe live demo replaces the generated preview; shorter README leads with setup.
- Search resumes with one Enter; rename starts with the current name; summary
  cancellation and missing agents keep the picker open.
- Standard-library runtime, versioned private local metadata, atomic writes, and
  process locks. Native histories remain read-only.
- CLI commands, documentation, synthetic tests, and macOS/Linux CI.
