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

## Branches and pull requests

Install the local guards once per checkout:

```sh
python3 tools/install_git_hooks.py
```

The guards are copied into Git’s local metadata directory so they remain active
when you switch branches. They reject commits on `main` and pushes to `main`.
Server-side rules are the
shared enforcement; local hooks are an extra guard and are not installed by pip.

Start a focused branch from the latest default branch:

```sh
git switch main
git pull --ff-only
git switch -c fix/describe-the-change
# Make and validate your changes, then commit them on this branch.
git push -u origin HEAD
gh pr create
```

Explain the problem and resulting behavior, then list relevant validation and
known compatibility limits. Keep unrelated changes in separate PRs. Update docs
for user-facing changes. The PR template provides a short checklist.

CI runs tests on macOS/Linux and checks lint and packaging. `CI required` combines
those results into one required check. Copilot reviews open PRs and new pushes
when the maintainer has enabled the repository ruleset and the author is eligible
for Copilot review. Read the findings and resolve applicable comments; automated
review does not merge PRs. The maintainer makes the final merge decision.

For this single-maintainer repository, the proposed rules require PRs, passing
CI, and resolved review conversations, but do not require an approval from a
second human who may not be available. Copilot is an additional reviewer, not
a claim that every change has human approval. Contributors cannot approve their
own PRs. Maintainers may squash commits; no CLA is required.

Maintainers can apply the versioned settings with
`python3 tools/configure_github.py`. See [repository setup](docs/repository-setup.md).
Contributions are under the repository's MIT license.

## Releases

See [the release checklist](docs/releasing.md). Version 0.x reflects that native
history formats can change and adapters may need updates.
