"""Release failures must stop merging/tagging rather than report success."""

import subprocess
import unittest
from unittest.mock import patch

from tools.ship_release import finish_pr, main, validate_version


class ShippingTests(unittest.TestCase):
    def test_ci_failure_prevents_merge(self):
        with patch('tools.ship_release.ensure_pr', return_value={'number': 5, 'state': 'OPEN', 'url': 'PR'}), \
             patch('tools.ship_release.output', return_value='checked-sha'), \
             patch('tools.ship_release.wait_for_ci', side_effect=ValueError('CI failed')), \
             patch('tools.ship_release.run') as run:
            with self.assertRaisesRegex(ValueError, 'CI failed'):
                finish_pr('feature', 'Title', 'Body')
        run.assert_not_called()

    def test_merge_is_pinned_to_checked_commit_and_private_email(self):
        with patch('tools.ship_release.ensure_pr', return_value={'number': 5, 'state': 'OPEN', 'url': 'PR'}), \
             patch('tools.ship_release.output', return_value='checked-sha'), \
             patch('tools.ship_release.wait_for_ci') as wait, \
             patch('tools.ship_release.run') as run:
            finish_pr('feature', 'Title', 'Body')
        wait.assert_called_once_with('checked-sha', 'ci.yml', 'pull_request', 'feature')
        merge = next(call.args for call in run.call_args_list if call.args[:3] == ('gh', 'pr', 'merge'))
        self.assertEqual(merge[merge.index('--match-head-commit') + 1], 'checked-sha')
        self.assertTrue(merge[merge.index('--author-email') + 1].endswith('@users.noreply.github.com'))
        self.assertNotIn('--admin', merge)

    def test_dirty_checkout_stops_before_any_remote_mutation(self):
        with patch('sys.argv', ['ship', '--reviewed']), patch('tools.ship_release.os.chdir'), \
             patch('tools.ship_release.output', return_value=' M file'), \
             patch('tools.ship_release.run') as run:
            with self.assertRaisesRegex(ValueError, 'working-tree changes'):
                main()
        run.assert_not_called()

    def test_version_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'expected version'):
            validate_version('__version__ = "0.1.0"', 'version = "1.0.0"')

    def test_existing_tag_is_never_moved(self):
        def output(*args):
            if args == ('git', 'status', '--porcelain'):
                return ''
            if args[:2] == ('git', 'show'):
                return '__version__ = "1.0.0"\nversion = "1.0.0"'
            return 'new-main-sha'
        with patch('sys.argv', ['ship', '--reviewed']), patch('tools.ship_release.os.chdir'), \
             patch('tools.ship_release.output', side_effect=output), \
             patch('tools.ship_release.finish_pr'), patch('tools.ship_release.wait_for_ci'), \
             patch('tools.ship_release.run', return_value=
                   subprocess.CompletedProcess([], 0, 'old-tag-sha\n')) as run:
            with self.assertRaisesRegex(ValueError, 'will not be moved'):
                main()
        self.assertFalse(any(call.args[:3] == ('git', 'push', 'origin') for call in run.call_args_list))


class PyPIVerificationTests(unittest.TestCase):
    def test_requires_wheel_and_source_for_the_exact_version(self):
        import io
        import json

        from tools.ship_release import verify_pypi
        response = io.BytesIO(json.dumps({'info': {'version': '1.0.0'}, 'urls': [
            {'packagetype': 'bdist_wheel'}, {'packagetype': 'sdist'},
        ]}).encode())
        with patch('tools.ship_release.urllib.request.urlopen', return_value=response):
            verify_pypi()

    def test_missing_source_archive_is_not_reported_as_shipped(self):
        import io
        import json

        from tools.ship_release import verify_pypi
        response = io.BytesIO(json.dumps({'info': {'version': '1.0.0'}, 'urls': [
            {'packagetype': 'bdist_wheel'},
        ]}).encode())
        with patch('tools.ship_release.urllib.request.urlopen', return_value=response), \
             patch('tools.ship_release.time.monotonic', side_effect=[0, 0, 200]), \
             patch('tools.ship_release.time.sleep'):
            with self.assertRaisesRegex(ValueError, 'not verified'):
                verify_pypi()
