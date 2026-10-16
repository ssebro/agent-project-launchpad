"""Finish reviewed PRs in order, then tag and verify the 1.0.0 GitHub release."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = 'ssebro/agent-project-launchpad'
VERSION = '1.0.0'
TAG = 'v' + VERSION
CHANGES = [
    ('fix/empty-agent-resume', 'Keep empty agent resumes from changing project identity or activity',
     'Separate automatic handoff visits from actual user work; preserve native session links on exit.'),
    ('feat/picker-new-conversation', 'Make new conversations the default and clarify project resumes',
     'Start fresh with Enter by default, retain the n shortcut, highlight the previous agent, and '
     'include the project name and saved summary in resume prompts. Includes updated preview and tests.'),
    ('release/v1.0.0', 'Release Agent Project Launchpad 1.0.0',
     'Set version 1.0.0, document pinned installation, and add tag-triggered builds and GitHub release '
     'publication on GitHub. The release tag is created only after the preceding PRs and CI pass.'),
]


def run(*args, capture=False, check=True):
    return subprocess.run(args, cwd=ROOT, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None)


def output(*args):
    return run(*args, capture=True).stdout.strip()


def gh_json(*args):
    return json.loads(output('gh', *args))


def ensure_pr(branch, title, body):
    prs = gh_json('pr', 'list', '--repo', REPO, '--head', branch, '--state', 'all',
                  '--json', 'number,state,url', '--limit', '20')
    if prs and prs[0]['state'] == 'MERGED':
        return prs[0]
    if prs and prs[0]['state'] == 'CLOSED':
        raise ValueError(f'{branch} has a closed, unmerged PR; inspect it before shipping')
    run('git', 'switch', branch)
    run('git', 'merge', '--no-edit', 'origin/main')
    run('git', 'push', '-u', 'origin', branch)
    if not prs:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md') as file:
            file.write(body + '\n\nValidation: synthetic tests locally; CI must pass before merge.\n')
            file.flush()
            run('gh', 'pr', 'create', '--repo', REPO, '--base', 'main', '--head', branch,
                '--title', title, '--body-file', file.name)
    return gh_json('pr', 'view', branch, '--repo', REPO, '--json', 'number,state,url')


def wait_for_ci(commit, workflow, event, branch=None):
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        args = ['run', 'list', '--repo', REPO, '--workflow', workflow,
                '--commit', commit, '--event', event, '--limit', '10',
                '--json', 'databaseId,status,conclusion']
        if branch:
            args += ['--branch', branch]
        runs = gh_json(*args)
        if runs:
            newest = runs[0]
            if newest['status'] == 'completed':
                if newest['conclusion'] != 'success':
                    raise ValueError(f'{workflow} failed; inspect run {newest["databaseId"]}.')
                return
            run('gh', 'run', 'watch', str(newest['databaseId']), '--repo', REPO,
                '--exit-status', '--interval', '10')
            return
        print(f'Waiting for {workflow} on {commit[:8]}…', flush=True)
        time.sleep(5)
    raise ValueError(f'{workflow} did not start within 15 minutes; no release was published')


def finish_pr(branch, title, body):
    pr = ensure_pr(branch, title, body)
    print(pr['url'], flush=True)
    if pr['state'] == 'MERGED':
        return
    commit = output('git', 'rev-parse', 'HEAD')
    wait_for_ci(commit, 'ci.yml', 'pull_request', branch)
    run('gh', 'pr', 'checks', str(pr['number']), '--repo', REPO, '--required')
    # The caller explicitly attests review; server rules still enforce resolved
    # threads and any required approvals. A concurrent push invalidates this merge.
    run('gh', 'pr', 'merge', str(pr['number']), '--repo', REPO, '--squash',
        '--match-head-commit', commit,
        '--author-email', '372075+ssebro@users.noreply.github.com')
    run('git', 'fetch', 'origin')


def validate_version(initializer, metadata):
    if f'__version__ = "{VERSION}"' not in initializer or f'version = "{VERSION}"' not in metadata:
        raise ValueError('Merged main does not contain the expected version; refusing to tag')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed', action='store_true',
                        help='Confirm you reviewed the fix, UI, and release branch changes; allow merging')
    parser.add_argument('--prepare-only', action='store_true', help='Push branches and open PRs without merging')
    args = parser.parse_args()
    if not args.reviewed and not args.prepare_only:
        parser.error('Use --prepare-only to open PRs, or --reviewed after reviewing the branch changes')
    os.chdir(ROOT)
    if output('git', 'status', '--porcelain'):
        raise ValueError('Commit or save working-tree changes before shipping')
    run('gh', 'auth', 'status')
    run('git', 'fetch', 'origin', '--tags')
    run(sys.executable, str(ROOT / 'tools/configure_github.py'))
    if args.prepare_only:
        for change in CHANGES:
            print(ensure_pr(*change)['url'], flush=True)
        run('git', 'switch', 'release/v1.0.0')
        return
    for change in CHANGES:
        finish_pr(*change)
    run('git', 'fetch', 'origin', '--tags')
    commit = output('git', 'rev-parse', 'origin/main')
    validate_version(output('git', 'show', 'origin/main:src/agent_launchpad/__init__.py'),
                     output('git', 'show', 'origin/main:pyproject.toml'))
    wait_for_ci(commit, 'ci.yml', 'push', 'main')
    existing = run('git', 'rev-parse', '--quiet', '--verify', f'{TAG}^{{commit}}', capture=True, check=False)
    if existing.returncode == 0 and existing.stdout.strip() != commit:
        raise ValueError(f'{TAG} already points elsewhere; it will not be moved or overwritten')
    if existing.returncode:
        run('git', 'tag', '-a', TAG, '-m', f'Agent Project Launchpad {VERSION}', commit)
    run('git', 'push', 'origin', f'refs/tags/{TAG}')
    wait_for_ci(commit, 'release.yml', 'push', TAG)
    release = gh_json('release', 'view', TAG, '--repo', REPO, '--json', 'url,isDraft,assets')
    names = [asset['name'] for asset in release['assets']]
    if release['isDraft'] or not any(name.endswith('.whl') for name in names) or not any(name.endswith('.tar.gz') for name in names):
        raise ValueError('Release assets are incomplete; inspect the release before announcing it')
    run('git', 'switch', 'main')
    run('git', 'merge', '--ff-only', 'origin/main')
    run(sys.executable, str(ROOT / 'tools/cleanup_branches.py'))
    print('Shipped: ' + release['url'], flush=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
