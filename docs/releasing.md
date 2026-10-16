# Releasing 1.0.0

The prepared branches separate the no-op fix, picker UI, and release packaging.
To publish their PRs without merging:

```sh
python3 tools/ship_release.py --prepare-only
```

Review those branch changes and their PRs. Then the single completion command is:

```sh
python3 tools/ship_release.py --reviewed
```

Run it from an authenticated Terminal with a clean checkout. It enables and
verifies repository rules, pushes/opens missing PRs, and merges the fix, UI, and
release PRs in order. Each branch is brought up to date with main, and its exact
commit must pass CI and required checks. GitHub still enforces unresolved review
threads and any required approvals. The `--reviewed` flag is your confirmation
that you reviewed these changes; the script does not invent a human approval.

After main passes CI, it checks both version fields, creates the annotated
`v1.0.0` tag, and pushes it. The Release workflow rechecks tests and lint, builds
wheel and sdist, smoke-tests the wheel, and publishes both on GitHub. The command
waits for that workflow and verifies the published assets before reporting shipped.
It then cleans up merged local and remote branches. Cleanup checks exact commit
ancestry or a merged PR with a matching head, and preserves branches in use.
Failures stop the process; rerun after resolving them. Merged PRs are skipped.

GitHub Actions uses its repository token, with release-write permission scoped
to the release job.
Native history formats and cross-agent context limits remain documented in the
user guide and compatibility notes.
