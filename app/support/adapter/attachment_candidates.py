"""Provider-neutral metadata used only while capturing inbound attachment bytes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttachmentCandidate:
    external_attachment_id: str
    file_name: str
    content_type: str
    declared_size: int = 0
    inline_data: str | None = None
    download_id: str | None = None
    download_url: str | None = None
