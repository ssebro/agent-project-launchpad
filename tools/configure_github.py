"""Apply versioned repository settings using the maintainer's authenticated gh CLI."""

import argparse
import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = {'allow_squash_merge': True, 'allow_merge_commit': False,
            'allow_rebase_merge': False, 'delete_branch_on_merge': True}


def api(endpoint, method='GET', payload=None):
    args = ['gh', 'api', '--method', method, endpoint,
            '-H', 'Accept: application/vnd.github+json',
            '-H', 'X-GitHub-Api-Version: 2026-03-10']
    if payload is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def matches(actual, expected):
    """GitHub can add default fields and reorder rules in readback responses."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(matches(actual.get(k), v) for k, v in expected.items())
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(any(matches(item, wanted) for item in actual) for wanted in expected))
    return actual == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='ssebro/agent-project-launchpad')
    parser.add_argument('--dry-run', action='store_true', help='Print settings without network requests')
    args = parser.parse_args()
    rulesets = [json.loads(path.read_text()) for path in sorted((ROOT / '.github/rulesets').glob('*.json'))]
    # Required CI must exist on the default branch before enforcement, otherwise
    # its first PR could be blocked by a check the default branch cannot run.
    if args.dry_run:
        print(json.dumps(dict(repository=args.repo, settings=SETTINGS, rulesets=rulesets), indent=2))
        return
    endpoint = 'repos/' + args.repo
    repo = api(endpoint)
    if not repo.get('permissions', {}).get('admin'):
        raise ValueError('Repository admin permission is required; no settings changed')
    workflow = api(endpoint + '/contents/.github/workflows/ci.yml')
    if 'name: CI required' not in base64.b64decode(workflow['content']).decode():
        raise ValueError('Merge the workflow setup PR first so CI required exists on the default branch')
    api(endpoint, 'PATCH', SETTINGS)
    # Retire only the previously managed Copilot rule; preserve unrelated rules.
    for existing_rule in api(endpoint + '/rulesets?per_page=100'):
        if (existing_rule.get('source_type') == 'Repository'
                and existing_rule['name'] == 'Copilot reviews pull requests and new pushes'):
            api(endpoint + '/rulesets/' + str(existing_rule['id']), 'DELETE')
            print('Removed: ' + existing_rule['name'])
    for proposed in rulesets:
        existing = []
        page = 1
        while True:
            batch = api(endpoint + f'/rulesets?per_page=100&page={page}')
            existing.extend(item for item in batch if item.get('source_type') == 'Repository')
            if len(batch) < 100:
                break
            page += 1
        existing_matches = [item for item in existing if item['name'] == proposed['name']]
        if len(existing_matches) > 1:
            raise ValueError('Duplicate managed rulesets; inspect repository settings before retrying')
        suffix = '/' + str(existing_matches[0]['id']) if existing_matches else ''
        saved = api(endpoint + '/rulesets' + suffix, 'PUT' if existing_matches else 'POST', proposed)
        verified = api(endpoint + '/rulesets/' + str(saved['id']))
        for key in ('name', 'enforcement', 'conditions', 'rules'):
            if not matches(verified.get(key), proposed[key]):
                raise ValueError(f'Unexpected saved ruleset value for {key}; inspect repository settings')
        print('Verified: ' + proposed['name'])
    verified = api(endpoint)
    if any(verified.get(key) != value for key, value in SETTINGS.items()):
        raise ValueError('Repository merge settings did not match requested settings')
    print('Verified merge settings. Local hooks: python3 tools/install_git_hooks.py')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr.strip() or 'GitHub request failed; earlier settings may have applied') from error
    except ValueError as error:
        raise SystemExit(str(error)) from error
