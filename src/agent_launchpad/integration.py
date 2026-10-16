"""Install the product's core shell integration, without changing agent binaries."""

import fcntl
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .store import atomic_write

START = '# >>> agent-launchpad >>>'
END = '# <<< agent-launchpad <<<'


@dataclass(frozen=True)
class SetupResult:
    path: Path
    changed: bool
    backup: Path | None = None
    preview: str = ''


def shell_name(value: str | None = None) -> str:
    shell = Path(value or os.environ.get('SHELL') or
                 ('zsh' if sys.platform == 'darwin' else 'bash')).name
    if shell not in ('bash', 'zsh'):
        raise ValueError('Shell integration supports bash and zsh; specify --shell bash or --shell zsh')
    return shell


def startup_file(shell: str, home: Path | None = None) -> Path:
    home = home or Path.home()
    if shell == 'zsh':
        return Path(os.environ.get('ZDOTDIR', str(home))).expanduser() / '.zshrc'
    if sys.platform == 'darwin':
        # Bash login shells read only the first existing profile. Do not create
        # .bash_profile ahead of an existing .profile and silently suppress it.
        return next((home / name for name in ('.bash_profile', '.bash_login', '.profile')
                     if (home / name).exists()), home / '.bash_profile')
    return home / '.bashrc'


def installed_launcher() -> Path:
    candidate = Path(sys.argv[0]).expanduser()
    if candidate.name in ('agent-launchpad', 'agent-projects') and candidate.is_file():
        return candidate.absolute()
    found = shutil.which('agent-launchpad') or shutil.which('agent-projects')
    if not found:
        raise ValueError('Install the package first, then run its agent-launchpad setup command')
    return Path(found).absolute()


def managed_block(launcher: Path) -> str:
    executable = shlex.quote(str(launcher))
    return '\n'.join([
        START,
        '# Start the project picker when an interactive agent command has no arguments.',
        f'if [ -x {executable} ]; then',
        f'  eval "$(command {executable} shell-init --launcher {executable})"',
        'fi',
        END,
    ]) + '\n'


def block_span(text: str) -> tuple[int, int] | None:
    starts = list(re.finditer(r'^' + re.escape(START) + r'\r?$', text, re.MULTILINE))
    ends = list(re.finditer(r'^' + re.escape(END) + r'\r?\n?', text, re.MULTILINE))
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or ends[0].start() < starts[0].end():
        raise ValueError('Shell integration markers are duplicated or incomplete; no changes made')
    return starts[0].start(), ends[0].end()


def configured(path: Path) -> bool:
    return path.exists() and block_span(path.read_text(encoding='utf-8')) is not None


def configure(shell: str, path: Path, launcher: Path | None, *, remove: bool = False,
              dry_run: bool = False) -> SetupResult:
    """Replace only our managed block; back up every actual startup-file change.

    Symlinks are followed so dotfile-manager symlinks remain intact. All reads and
    writes use the resolved target; the original file mode is preserved.
    """
    shell = shell_name(shell)
    target = path.expanduser().resolve()
    if remove and not target.exists():
        return SetupResult(target, False)
    if not remove and (launcher is None or not launcher.is_file() or not os.access(launcher, os.X_OK)):
        raise ValueError('The installed agent-launchpad executable is missing or not executable')
    # Dry runs neither create a lock nor change files or directories.
    if dry_run:
        return _configure(shell, target, launcher, remove=remove, dry_run=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_file = target.with_name(target.name + '.agent-launchpad.lock')
    fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _configure(shell, target, launcher, remove=remove, dry_run=False)


def _configure(shell: str, target: Path, launcher: Path | None, *, remove: bool,
               dry_run: bool) -> SetupResult:
    original = target.read_bytes().decode('utf-8') if target.exists() else ''
    span = block_span(original)
    block = '' if remove else managed_block(launcher)
    if not remove and '\r\n' in original:
        raise ValueError('Startup file uses CRLF line endings. Convert it to LF before setup; no changes made')
    if span:
        updated = original[:span[0]] + block + original[span[1]:]
    else:
        updated = original if remove else original + (
            '\n' if original and not original.endswith('\n') else ''
        ) + block
    if updated == original or dry_run:
        return SetupResult(target, updated != original, preview=block)
    shell_binary = shutil.which(shell)
    if not shell_binary:
        raise ValueError(f'{shell} is not installed; no startup file changes made')
    # Validate generated shell code in isolation. Existing startup content is
    # preserved, not executed as part of setup.
    probe = subprocess.run([shell_binary, '-n'], input=block, capture_output=True, text=True)
    if probe.returncode:
        raise ValueError(f'Could not validate shell integration: {probe.stderr.strip()}')
    if not remove:
        wrappers = subprocess.run([str(launcher), 'shell-init', '--launcher', str(launcher)],
                                  capture_output=True, text=True, timeout=10)
        if wrappers.returncode or not wrappers.stdout.strip():
            raise ValueError('Could not generate installed launcher functions; no changes made')
        verified = subprocess.run([shell_binary, '-n'], input=wrappers.stdout,
                                  capture_output=True, text=True)
        if verified.returncode:
            raise ValueError('Generated launcher functions have invalid syntax; no changes made')
    backup = None
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = target.with_name(target.name + '.agent-launchpad-backup-' + stamp)
        atomic_write(backup, original)
    atomic_write(target, updated)
    os.chmod(target, mode)
    return SetupResult(target, True, backup)


def check_shell(shell: str) -> dict[str, bool]:
    """Probe fresh startup behavior without invoking an agent or a model."""
    binary = shutil.which(shell_name(shell))
    if not binary:
        raise ValueError(f'{shell} is not installed')
    checks = []
    for command, agent in [('codex', 'codex'), ('claude', 'claude'),
                           ('copilot', 'copilot'), ('gh', 'copilot')]:
        checks.append(
            f'case "$(typeset -f {command} 2>/dev/null)" in '
            f'*"--agent {agent}"*) printf "AGENT_LAUNCHPAD_CHECK:{command}:ok\\n";; '
            f'*) printf "AGENT_LAUNCHPAD_CHECK:{command}:missing\\n";; esac'
        )
    args = [binary, '-lic' if shell == 'bash' and sys.platform == 'darwin' else '-ic',
            '\n'.join(checks)]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Shell startup did not finish within 15 seconds; check your shell startup files') from exc
    output = {}
    for line in result.stdout.splitlines():
        if line.startswith('AGENT_LAUNCHPAD_CHECK:'):
            _, command, status = line.split(':', 2)
            output[command] = status == 'ok'
    return {command: output.get(command, False) for command in ('codex', 'claude', 'copilot', 'gh')}
