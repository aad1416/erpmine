"""Shared attachment capture and per-message accounting for email adapters."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence

from app.support.adapter.attachment_candidates import AttachmentCandidate
from app.support.adapter.attachment_capture_port import AttachmentCapturePort, AttachmentMetadata
from app.support.adapter.schemas import NormalizedMessage


async def capture_attachments(
    service: AttachmentCapturePort,
    message: NormalizedMessage,
    candidates: Sequence[AttachmentCandidate],
    load: Callable[[AttachmentCandidate, int], Awaitable[bytes | None]],
    *,
    provider: str,
    logger: logging.Logger,
    failure_detail: str,
) -> None:
    """Capture candidates in order, leaving provider-specific byte retrieval to ``load``."""
    accepted_bytes = 0
    for position, candidate in enumerate(candidates):
        metadata = AttachmentMetadata.from_candidate(candidate)
        existing = await service.existing_summary(
            message.mailbox_key, message.external_message_id,
            metadata.external_attachment_id,
        )
        if existing is not None:
            message.attachments.append(existing)
            if existing.capture_status == "ready":
                accepted_bytes += existing.size
            continue

        data = None
        download_error = None
        if not await service.preflight_rejection(
            metadata, position=position, message_bytes_already_accepted=accepted_bytes
        ):
            try:
                data = await load(candidate, position)
            except Exception:
                logger.warning(
                    "%s attachment retrieval failed for message %s, part %s",
                    provider, message.external_message_id, position, exc_info=True,
                )
                download_error = failure_detail

        summary = await service.capture(
            mailbox_key=message.mailbox_key,
            conversation_id=message.conversation_id,
            external_message_id=message.external_message_id,
            candidate=metadata,
            data=data,
            position=position,
            message_bytes_already_accepted=accepted_bytes,
            download_error=download_error,
        )
        message.attachments.append(summary)
        if summary.capture_status == "ready":
            accepted_bytes += summary.size
    message.has_attachments = bool(candidates)
