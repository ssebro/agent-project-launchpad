"""Install local branch guards outside the working tree so they survive checkout."""

import shutil
import subprocess
from pathlib import Path


def main():
    source = Path(__file__).resolve().parents[1] / '.githooks'
    git_directory = Path(subprocess.check_output(
        ['git', 'rev-parse', '--absolute-git-dir'], text=True).strip())
    destination = git_directory / 'launchpad-hooks'
    current = subprocess.run(['git', 'config', '--get', 'core.hooksPath'],
                             text=True, capture_output=True)
    if current.returncode not in (0, 1):
        raise SystemExit('Cannot inspect existing hooks configuration')
    if current.stdout.strip() not in ('', '.githooks', str(destination)):
        raise SystemExit('Custom Git hooks are already configured; integrate the guards manually')
    destination.mkdir(exist_ok=True)
    for name in ('pre-commit', 'pre-push'):
        shutil.copyfile(source / name, destination / name)
        (destination / name).chmod(0o755)
    subprocess.run(['git', 'config', '--local', 'core.hooksPath', str(destination)], check=True)
    print('Installed branch guards in ' + str(destination))


if __name__ == '__main__':
    main()
