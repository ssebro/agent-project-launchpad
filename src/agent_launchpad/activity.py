"""Distinguish user work from the launcher's automatic handoff prompt."""

import hashlib
import json
from pathlib import Path

from .context import extract_text
from .models import Session

EMPTY_ACTIVITY = hashlib.sha256().hexdigest()


def is_handoff_title(title: str) -> bool:
    normalized = ' '.join(title.casefold().split()).strip(' .!')
    return normalized in ('resume this project', 'resume project') or normalized.startswith((
        '[agent project launchpad handoff]',
        'resume this project. first read the shared handoff at ',
    ))


def user_activity(session: Session) -> str | None:
    """Fingerprint user requests, excluding bootstrap prompts and tool results.

    Missing or unreadable transcripts are unknown, never proof of an empty visit.
    Assistant replies to the automatic handoff do not count as new user work.
    """
    file = session.transcript
    if file is None:
        return None
    digest = hashlib.sha256()
    saw_user_text = False
    try:
        with Path(file).open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except ValueError:
                    if line.strip():
                        return None  # Partial/corrupt evidence cannot prove an empty visit.
                    continue
                if not isinstance(event, dict) or event.get('isSidechain') or event.get('agentId'):
                    continue
                text = ''
                if session.agent == 'codex' and event.get('type') == 'response_item':
                    payload = event.get('payload', {})
                    if isinstance(payload, dict) and payload.get('type') == 'message' and payload.get('role') == 'user':
                        text = extract_text(payload.get('content'))
                elif session.agent == 'claude' and event.get('type') == 'user':
                    message = event.get('message', {})
                    if isinstance(message, dict):
                        text = extract_text(message.get('content'))
                elif session.agent == 'copilot' and event.get('type') == 'user.message':
                    data = event.get('data', {})
                    if isinstance(data, dict):
                        text = extract_text(data.get('content'))
                text = text.strip()
                if text:
                    saw_user_text = True
                if not text or text.startswith((
                    '[Agent Project Launchpad handoff]',
                    'Resume this project. First read the shared handoff at ',
                    '# AGENTS.md instructions for ', '<environment_context>',
                    '<permissions instructions>', '<user_instructions>',
                )):
                    continue
                value = text.encode('utf-8')
                digest.update(str(len(value)).encode('ascii') + b':' + value)
    except (OSError, UnicodeError):
        return None
    return digest.hexdigest() if saw_user_text else None
