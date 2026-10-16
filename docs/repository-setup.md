# Maintainer setup

All work goes through a focused branch and pull request. Install local guards:

```sh
python3 tools/install_git_hooks.py
```

The hooks prevent commits and pushes to `main` in this checkout. AGENTS.md carries
this rule to coding agents; CONTRIBUTING.md documents it for contributors.

## Enable server-side enforcement

After merging the workflow setup PR, run this once from an authenticated Terminal:

```sh
python3 tools/configure_github.py --dry-run
python3 tools/configure_github.py
```

The script verifies admin access and that `CI required` exists on the default
branch. It applies its named main-protection ruleset and removes the previously managed
Copilot review rule, leaving other rulesets intact. Rerunning updates the same ruleset. Every write is read back for verification;
errors stop the script, so a partial failure is not reported as full success.

The settings require a PR into the default branch, passing `CI required`, an
up-to-date branch, and resolved review conversations. Force pushes and deletion
of the default branch are blocked, including for admins. Merges use squash and
GitHub deletes merged branches automatically.

The JSON rule is in `.github/rulesets/`. You can inspect or configure it under
GitHub **Settings → Rules → Rulesets**.
