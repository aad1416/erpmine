"""Convert HTML email bodies to text while retaining named file links."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.config.email_attachments import ALLOWED_EMAIL_EXTENSIONS
from app.services.linked_email_files import file_name_from_url


def html_to_text(html: str) -> str:
    if not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        name = anchor.get_text(" ", strip=True)
        href = anchor.get("href", "")
        if (
            1 <= len(name) <= 255
            and name.rsplit(".", 1)[-1].lower() in ALLOWED_EMAIL_EXTENSIONS
            and href.startswith(("https://", "http://"))
            and len(href) <= 2048
            and not any(character.isspace() for character in href)
        ):
            anchor.replace_with(f"[{name}]({href})")
        elif (
            href.startswith(("https://", "http://"))
            and len(href) <= 2048
            and not any(character.isspace() for character in href)
            and file_name_from_url(href)
        ):
            anchor.replace_with(f"{name} {href}" if name else href)
    return soup.get_text(separator="\n").strip()
