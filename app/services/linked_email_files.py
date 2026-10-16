"""Recognize file links in email text without fetching untrusted URLs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import unquote, urlsplit

from app.config.email_attachments import ALLOWED_EMAIL_EXTENSIONS


_EXTENSIONS = "|".join(
    re.escape(ext) for ext in sorted(ALLOWED_EMAIL_EXTENSIONS, key=len, reverse=True)
)
_FILE_NAME = rf"[\w][\w .()\-]{{0,200}}\.(?:{_EXTENSIONS})"
_PLAIN_FILE_NAME = rf"[\w][\w()\-]{{0,200}}\.(?:{_EXTENSIONS})"
_LINKED_FILE = re.compile(
    rf"\[(?P<markdown>{_FILE_NAME})\]\(https?://[^\s)]+(?:\s+\"[^\"]*\")?\)"
    rf"|(?P<angle>{_PLAIN_FILE_NAME})\s*<https?://[^\s>]+>"
    rf"|\"(?P<quoted_colon>{_FILE_NAME})\"\s*:\s*https?://[^\s<>]+"
    rf"|(?P<colon>{_PLAIN_FILE_NAME})\s*:\s*https?://[^\s<>]+",
    re.IGNORECASE,
)

_DIRECT_URL = re.compile(r"https?://[^\s<>\"'()\[\]]+", re.IGNORECASE)


def file_name_from_url(url: str) -> str | None:
    """Return a supported basename from a direct file URL, without fetching it."""
    try:
        name = unquote(urlsplit(url.rstrip(".,;:!?")).path.rsplit("/", 1)[-1])
    except ValueError:
        return None
    return name if re.fullmatch(_FILE_NAME, name, re.IGNORECASE) else None


def missing_linked_file_names(
    body_texts: Iterable[str], captured_file_names: Iterable[str]
) -> set[str]:
    """Return named cloud files that were never captured as email attachments.

    This only identifies links. The attachment pipeline must not fetch their URLs.
    """
    captured = {name.casefold() for name in captured_file_names}
    missing: set[str] = set()
    for body in body_texts:
        named = list(_LINKED_FILE.finditer(body))
        for match in named:
            name = next(group for group in match.groups() if group is not None).strip()
            if name.casefold() not in captured:
                missing.add(name)
        named_index = 0
        for match in _DIRECT_URL.finditer(body):
            while named_index < len(named) and named[named_index].end() <= match.start():
                named_index += 1
            if (
                named_index < len(named)
                and named[named_index].start() <= match.start() < named[named_index].end()
            ):
                continue
            name = file_name_from_url(match.group())
            if name and name.casefold() not in captured:
                missing.add(name)
    return missing
