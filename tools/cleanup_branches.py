"""Delete branches whose exact heads are already merged into main."""

import json
import subprocess

REPO = 'ssebro/agent-project-launchpad'


def git(*args, check=True):
    return subprocess.run(['git', *args], text=True, capture_output=True, check=check)


def cleanup():
    remote_url = git('remote', 'get-url', 'origin').stdout.strip()
    allowed = {f'https://github.com/{REPO}', f'https://github.com/{REPO}.git',
               f'git@github.com:{REPO}.git', f'ssh://git@github.com/{REPO}.git'}
    if remote_url not in allowed:
        raise ValueError('Run cleanup in the Agent Project Launchpad maintainer checkout')
    current = git('branch', '--show-current').stdout.strip()
    worktrees = git('worktree', 'list', '--porcelain').stdout.splitlines()
    checked_out = {line.removeprefix('branch refs/heads/') for line in worktrees
                   if line.startswith('branch refs/heads/')}
    protected = {'main', 'HEAD', current} | checked_out
    proofs = {}
    def merged(branch, sha):
        key = (branch, sha)
        if key not in proofs:
            if git('merge-base', '--is-ancestor', sha, 'origin/main', check=False).returncode == 0:
                proofs[key] = 'ancestor'
            else:
                result = subprocess.run(['gh', 'pr', 'list', '--repo', REPO, '--head', branch,
                                         '--state', 'merged', '--limit', '20',
                                         '--json', 'headRefOid,baseRefName'],
                                        text=True, capture_output=True, check=True)
                proofs[key] = 'pr' if any(
                    p['headRefOid'] == sha and p['baseRefName'] == 'main'
                    for p in json.loads(result.stdout)) else None
        return proofs[key]
    remote = git('for-each-ref', 'refs/remotes/origin/',
                 '--format=%(refname:strip=3) %(objectname)').stdout.splitlines()
    for line in remote:
        branch, sha = line.split()
        if branch not in protected and merged(branch, sha):
            ref = 'refs/heads/' + branch
            # A branch that receives a newer commit during cleanup is preserved.
            git('push', f'--force-with-lease={ref}:{sha}', 'origin', ':' + ref)
            print('Deleted merged remote branch: ' + branch)
    local = git('for-each-ref', 'refs/heads/',
                '--format=%(refname:strip=2) %(objectname)').stdout.splitlines()
    for line in local:
        branch, sha = line.split()
        if branch not in protected:
            proof = merged(branch, sha)
            if proof:
                git('branch', '-d' if proof == 'ancestor' else '-D', branch)
                print('Deleted merged local branch: ' + branch)
    git('fetch', 'origin', '--prune')


if __name__ == '__main__':
    git('fetch', 'origin', '--prune')
    cleanup()
