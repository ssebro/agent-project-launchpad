# Releasing 1.0.0

## One-time PyPI setup

Sign in to [PyPI publishing settings](https://pypi.org/manage/account/publishing/)
and add a pending GitHub publisher with these values:

| Field | Value |
| --- | --- |
| PyPI project name | `agent-project-launchpad` |
| Owner | `ssebro` |
| Repository | `agent-project-launchpad` |
| Workflow filename | `release.yml` |
| Environment | `pypi` |

The first successful publish creates the PyPI project. PyPI checks project-name
availability at publication. [Trusted Publisher setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Ship the release

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
wheel and sdist, smoke-tests the wheel, and publishes the same artifacts to PyPI and GitHub. The command
waits for that workflow and verifies GitHub assets and PyPI metadata before
reporting shipped.
It then cleans up merged local and remote branches. Cleanup checks exact commit
ancestry or a merged PR with a matching head, and preserves branches in use.
Failures stop the process. For a failed release workflow, correct the issue and
retry its failed jobs with `gh run rerun RUN_ID --failed`, then repeat the
completion command. Merged PRs are skipped.

PyPI publishing uses short-lived GitHub OIDC credentials in the `pypi` job.
GitHub release-write permission is scoped to the separate GitHub release job.
Native history formats and cross-agent context limits remain documented in the
user guide and compatibility notes.
