"""Merged-branch cleanup preserves active work and concurrent remote updates."""

import json
import subprocess
import unittest
from unittest.mock import patch

from tools.cleanup_branches import cleanup


class CleanupTests(unittest.TestCase):
    def simulate(self, heads, ancestor_heads, prs, fail_push=False):
        calls = []
        def git(*args, **_kwargs):
            calls.append(args)
            value, code = '', 0
            if args[:3] == ('remote', 'get-url', 'origin'):
                value = 'https://github.com/ssebro/agent-project-launchpad.git'
            elif args == ('branch', '--show-current'):
                value = 'main'
            elif args == ('worktree', 'list', '--porcelain'):
                value = 'branch refs/heads/main\nbranch refs/heads/in-use\n'
            elif args[0] == 'for-each-ref':
                value = '\n'.join(f'{branch} {sha}' for branch, sha in heads.items())
            elif args[0] == 'merge-base':
                code = 0 if args[2] in ancestor_heads else 1
            elif args[0] == 'push' and fail_push:
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, code, value)
        def request(args, **_kwargs):
            branch = args[args.index('--head') + 1]
            return subprocess.CompletedProcess(args, 0, json.dumps(prs.get(branch, [])))
        return calls, patch('tools.cleanup_branches.git', side_effect=git), \
            patch('tools.cleanup_branches.subprocess.run', side_effect=request)

    def test_preserves_unmerged_and_checked_out_branches(self):
        calls, git, request = self.simulate(
            {'main': 'm', 'merged': 'b', 'unfinished': 'u', 'in-use': 'w'}, {'b', 'w'}, {})
        with git, request:
            cleanup()
        deleted = [args[-1] for args in calls if args[:2] == ('branch', '-d')]
        self.assertEqual(deleted, ['merged'])
        pushes = [args for args in calls if args[0] == 'push']
        self.assertEqual(pushes, [('push', '--force-with-lease=refs/heads/merged:b', 'origin', ':refs/heads/merged')])

    def test_squash_merge_requires_exact_head_match(self):
        calls, git, request = self.simulate({'squashed': 's', 'unpushed': 'new'}, set(), {
            'squashed': [{'headRefOid': 's', 'baseRefName': 'main'}],
            'unpushed': [{'headRefOid': 'old', 'baseRefName': 'main'}],
        })
        with git, request:
            cleanup()
        self.assertIn(('branch', '-D', 'squashed'), calls)
        self.assertFalse(any(args[0] == 'branch' and args[-1] == 'unpushed' for args in calls))

    def test_failed_remote_lease_stops_before_local_deletion(self):
        calls, git, request = self.simulate({'merged': 'b'}, {'b'}, {}, fail_push=True)
        with git, request, self.assertRaises(subprocess.CalledProcessError):
            cleanup()
        self.assertNotIn(('branch', '-d', 'merged'), calls)
