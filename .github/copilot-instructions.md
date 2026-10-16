# Review priorities

Focus on correctness and user-visible regressions, with concrete examples and
file/line references. Distinguish confirmed bugs from assumptions about native
agent formats. Read CONTRIBUTING.md and docs/architecture.md for context.

- Discovery reads native histories without modifying them. A shared directory
  alone must never merge separate projects.
- Resume must preserve exact native identities and ordinary agent permissions.
  Pass arguments as lists, never interpolate project content into a shell.
- Separate launcher setup messages from actual work. An empty visit must not
  silently rename a project or invent activity. Conversations without file edits
  still count as work.
- Explicit project names override automatic titles. Genuine work can provide a
  better native title; generic bootstrap titles are not meaningful names.
- Preserve lifecycle, summary freshness, and archive/undo semantics across exits,
  failures, restarts, and partial transcripts.
- Use fictional fixtures. Never request or publish real histories or credentials.
- Check behavioral test coverage and CI results. A passing suite is evidence,
  not a substitute for inspecting the logic.
