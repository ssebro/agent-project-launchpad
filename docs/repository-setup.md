# Maintainer setup

All work goes through a focused branch and pull request. Install local guards:

```sh
git config core.hooksPath .githooks
```

The hooks prevent commits and pushes to `main` in this checkout. AGENTS.md carries
this rule to coding agents; CONTRIBUTING.md documents it for contributors.

## Enable server-side enforcement and Copilot

After merging the workflow setup PR, run this once from an authenticated Terminal:

```sh
python3 tools/configure_github.py --dry-run
python3 tools/configure_github.py
```

The script verifies admin access and that `CI required` exists on the default
branch. It applies only its two named rulesets, leaving other rulesets intact.
Rerunning updates those same rulesets. Every write is read back for verification;
errors stop the script, so a partial failure is not reported as full success.

The settings require a PR into the default branch, passing `CI required`, an
up-to-date branch, and resolved review conversations. Force pushes and deletion
of the default branch are blocked, including for admins. Merges use squash and
GitHub deletes merged branches automatically.

A second ruleset requests Copilot review on open PRs and new pushes. Drafts wait
until marked ready. This needs an eligible Copilot account and available usage;
the script reports an API error if GitHub rejects the rule. Copilot feedback is
advisory; review it before making the final merge decision. There is no automatic
merge and no requirement for a second human approval in this solo-maintainer repo.

The JSON rules are in `.github/rulesets/`. You can also inspect or configure them
under GitHub **Settings → Rules → Rulesets**. The Copilot rule is **Automatically
request Copilot code review**, with **Review new pushes** enabled.

See GitHub's [Copilot review configuration](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-code-review).
