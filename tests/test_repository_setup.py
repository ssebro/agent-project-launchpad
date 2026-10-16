"""Verify settings writes against a simulated GitHub API, without credentials."""

import base64
import contextlib
import io
import unittest
from unittest.mock import patch

from tools.configure_github import SETTINGS, main


class RepositorySetupTests(unittest.TestCase):
    def test_missing_default_branch_check_prevents_all_settings_writes(self):
        responses = [{'permissions': {'admin': True}},
                     {'content': base64.b64encode(b'name: old CI').decode()}]
        with patch('sys.argv', ['setup']), \
             patch('tools.configure_github.api', side_effect=responses) as api:
            with self.assertRaisesRegex(ValueError, 'Merge the workflow setup PR first'):
                main()
        self.assertEqual([call.args[1:] for call in api.call_args_list], [(), ()])

    def test_apply_updates_only_named_rulesets_and_verifies_readback(self):
        saved = {}
        writes = []
        unrelated = {'id': 99, 'name': 'Unrelated rule', 'source_type': 'Repository'}
        existing = {'id': 1, 'name': 'Copilot reviews pull requests and new pushes',
                    'source_type': 'Repository'}
        def api(endpoint, method='GET', payload=None):
            if method != 'GET':
                writes.append((endpoint, method, payload))
                if endpoint.endswith('/rulesets/1') or endpoint.endswith('/rulesets'):
                    identity = 1 if method == 'PUT' else 2
                    saved[identity] = {**payload, 'id': identity}
                    return saved[identity]
                return SETTINGS
            if '/contents/' in endpoint:
                return {'content': base64.b64encode(b'name: CI required').decode()}
            if '/rulesets?' in endpoint:
                return [unrelated, existing]
            if '/rulesets/' in endpoint:
                value = saved[int(endpoint.rsplit('/', 1)[1])]
                # GitHub adds defaults and may return rules in a different order.
                return {**value, 'rules': list(reversed(value['rules']))}
            return {'permissions': {'admin': True}, **SETTINGS}
        with patch('sys.argv', ['setup']), patch('tools.configure_github.api', side_effect=api), \
             contextlib.redirect_stdout(io.StringIO()):
            main()
        self.assertEqual([method for _path, method, _payload in writes], ['PATCH', 'PUT', 'POST'])
        self.assertFalse(any('/rulesets/99' in path for path, _method, _payload in writes))

    def test_dry_run_makes_no_network_calls(self):
        with patch('sys.argv', ['setup', '--dry-run']), \
             patch('tools.configure_github.api') as api, contextlib.redirect_stdout(io.StringIO()):
            main()
        api.assert_not_called()
