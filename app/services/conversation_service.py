"""Derived state per conversation (02-architecture-decisions.md §6, §10.1); receives the
batch from app.support.ingestion.port.notify_ai_core(...) — does NOT pull anything
itself; writes ConversationMessage rows (§8) for the batch before invoking
decision_agent.py.

A create_ticket tool call is not actioned inline: _handle_create_ticket only enqueues a
create_ticket IngestionTask. The ticket API call and all of its outcome handling happen
later in handle_create_ticket_task, invoked by the ingestion worker via
app.support.ingestion.port.process_create_ticket once it claims that task — which is
also what gives ticket creation its own retry/dead-letter lifecycle instead of
piggybacking on a retry of the whole message turn.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import List

from sqlalchemy.orm import Session

from app.config.setting import settings
from app.db.database import SessionLocal
from app.db.models.Conversation import Conversation
from app.repositories.conversation_messages import ConversationMessageRepository
from app.repositories.conversations import ConversationRepository
from app.services.communication_log_client import enqueue_backfill
from app.services.decision_agent import DecisionAgent, SupportToolContext
from app.services.email_attachment_service import EmailAttachmentService
from app.services.linked_email_files import missing_linked_file_names
from app.services.ticket_client import TicketAttachmentOutcome, TicketClient, TicketOutcome
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage
from app.support.ingestion.models import TaskType
from app.support.ingestion.task_repository import TaskRepository

logger = logging.getLogger(__name__)

_decision_agent = DecisionAgent()


def _receiving_inbox_address(conversation: Conversation) -> str:
    """The Conversation's Mailbox, i.e. the address the customer wrote to — never a
    model argument (§10.2)."""
    address = conversation.mailbox
    if (
        settings.SUPPORT_TEST_RECEIVING_INBOX_OVERRIDE_FROM
        and address == settings.SUPPORT_TEST_RECEIVING_INBOX_OVERRIDE_FROM
        and settings.SUPPORT_TEST_RECEIVING_INBOX_OVERRIDE_TO
    ):
        return settings.SUPPORT_TEST_RECEIVING_INBOX_OVERRIDE_TO
    return address


def _build_run_input(
    conversation: Conversation,
    history: list,
    messages: List[NormalizedMessage],
    attachment_manifest: str = "",
) -> str:
    lines = []
    if history:
        lines.append("Conversation so far:")
        for msg in history:
            speaker = "Customer" if msg.direction == "inbound" else "You"
            lines.append(f"[{speaker}] {msg.body_text}")
        lines.append("")
    lines += [
        f"Baseline question rounds used: {conversation.question_round_count} of {settings.SUPPORT_QUESTION_ROUND_CAP}",
        f"Serial-correction attempts used: {conversation.serial_correction_attempt_count} of {settings.SUPPORT_SERIAL_CORRECTION_CAP}",
        "",
        "New message(s) from the customer:",
    ]
    for message in messages:
        lines.append(f"[Customer] {message.body_text}")
    if attachment_manifest:
        lines.extend(["", attachment_manifest])
    return "\n".join(lines)


def _compose_capture_failure_message(messages: List[NormalizedMessage]) -> str | None:
    failures = [
        attachment
        for message in messages
        for attachment in message.attachments
        if attachment.capture_status != "ready"
    ]
    if not failures:
        return None
    details = "; ".join(
        f"{attachment.file_name!r} ({attachment.capture_error or 'unavailable'})"
        for attachment in failures
    )
    return (
        "We received your follow-up, but the following file(s) could not be added "
        f"to the existing ticket: {details}. Please resend them."
    )


_LINKED_FILE_REQUEST = (
    "I can see a link to a file in your email, but I can't read or add the file "
    "from that link. Please send it as an email attachment so we can add it to your ticket."
)


def _missing_linked_files(messages: list, attachments: list) -> set[str]:
    ready_by_message: dict[str, list[str]] = {}
    for attachment in attachments:
        if attachment.capture_status == "ready":
            ready_by_message.setdefault(attachment.external_message_id, []).append(
                attachment.file_name
            )
    missing: set[str] = set()
    for message in messages:
        missing.update(
            missing_linked_file_names(
                [message.body_text],
                ready_by_message.get(message.external_message_id, []),
            )
        )
    return missing


def _with_linked_file_request(text: str, missing_files: set[str]) -> str:
    return f"{text.rstrip()}\n\n{_LINKED_FILE_REQUEST}" if missing_files else text


def _compose_duplicate_message(existing_ticket: dict) -> str:
    number = existing_ticket.get("number", "unknown")
    status = existing_ticket.get("status", "unknown")
    return (
        f"It looks like there's already an open ticket (#{number}, status: {status}) "
        "for this unit, so we haven't opened a new one. Someone will follow up with you "
        "on the existing ticket shortly."
    )


_UNIT_NOT_FOUND_MESSAGE = (
    "We couldn't find a unit matching that serial number — could you double-check it "
    "and send it again?"
)

_ESCALATION_MESSAGE = (
    "Thanks for the details — we've got what you've sent so far, and someone will "
    "follow up with you shortly."
)


async def handle_message_batch(
    conversation_id: str, messages: List[NormalizedMessage]
) -> None:
    """One turn = one batch of new messages for a thread (§10.3). The agent calls
    exactly one tool; that tool's side effects plus the derived-state update conclude
    the turn."""
    if not messages:
        return
    mailbox_key = messages[0].mailbox_key

    db = SessionLocal()
    try:
        conversation_repo = ConversationRepository(db)
        message_repo = ConversationMessageRepository(db)

        conversation = conversation_repo.get_or_create(mailbox_key, conversation_id)
        attachment_service = EmailAttachmentService(db)
        attachments = attachment_service.list_for_conversation(mailbox_key, conversation_id)

        if conversation.ticket_id is not None:
            new_rows = message_repo.add_inbound(conversation, messages)
            _enqueue_ticket_attachments(
                db, mailbox_key, conversation_id, conversation.ticket_id, attachments
            )
            failure_message = _compose_capture_failure_message(messages)
            missing_files = _missing_linked_files(new_rows, attachments)
            if missing_files:
                failure_message = _with_linked_file_request(failure_message or "", missing_files).strip()
            if failure_message:
                _enqueue_reply(
                    message_repo, conversation, mailbox_key, conversation_id,
                    failure_message, commit=False,
                )
            enqueue_backfill(db, conversation, conversation.ticket_id, commit=False)
            db.commit()
            return

        history = message_repo.get_all(conversation.id)
        message_repo.add_inbound(conversation, messages)

        baseline_capped = (
            conversation.question_round_count >= settings.SUPPORT_QUESTION_ROUND_CAP
            and not conversation.unit_serial
        )
        serial_capped = (
            conversation.serial_correction_attempt_count
            >= settings.SUPPORT_SERIAL_CORRECTION_CAP
            and not conversation.unit_serial
        )
        capped = baseline_capped or serial_capped

        run_input = _build_run_input(
            conversation, history, messages, attachment_service.manifest(attachments)
        )
        missing_files = _missing_linked_files(messages, attachments)
        if missing_files:
            run_input += (
                "\n\nThe customer linked a file in the email body, but the file itself was not "
                "attached. Its contents are unavailable. Do not claim to have read or "
                "attached it; the system will ask the customer to send it as an email attachment."
            )
        ctx = SupportToolContext(
            attachment_service=attachment_service,
            attachments={a.id: a for a in attachments},
        )
        await _decision_agent.run(
            run_input=run_input, ctx=ctx, allow_gathering_tools=not capped
        )

        if capped and ctx.tool_called in ("ask_question", "create_ticket"):
            # Defense in depth: allow_gathering_tools=False already withholds these
            # tools from the model, so this should be unreachable. If it ever isn't,
            # don't trust the call — force the escalation path instead.
            logger.warning(
                "Decision agent called %s for conversation %s despite exhausted caps; "
                "forcing escalation",
                ctx.tool_called,
                conversation_id,
            )
            ctx.tool_called = None

        if ctx.tool_called == "ask_question":
            await _handle_ask_question(
                conversation, conversation_repo, message_repo, mailbox_key, conversation_id, ctx,
                missing_files,
            )
        elif ctx.tool_called == "create_ticket":
            _handle_create_ticket(db, mailbox_key, conversation_id, ctx)
        elif ctx.tool_called == "reply":
            _enqueue_reply(
                message_repo, conversation, mailbox_key, conversation_id,
                _with_linked_file_request(ctx.reply_text, missing_files),
            )
        else:
            _escalate(db, conversation, message_repo, mailbox_key, conversation_id, missing_files)
    finally:
        db.close()


def _enqueue_reply(
    message_repo: ConversationMessageRepository,
    conversation: Conversation,
    mailbox_key: MailboxKey,
    conversation_id: str,
    text: str,
    commit: bool = True,
) -> None:
    """Logs the outbound message and queues its delivery as a send_message task; the
    worker performs the actual send. Nothing here touches the network, so callers can
    fold this into a larger transaction with `commit=False`."""
    message_repo.add_outbound(conversation, text, commit=False)
    TaskRepository(message_repo.db).enqueue(
        task_type=TaskType.send_message.value,
        mailbox_key=mailbox_key,
        conversation_id=conversation_id,
        payload={"text": text},
        commit=commit,
    )


async def _handle_ask_question(
    conversation: Conversation,
    conversation_repo: ConversationRepository,
    message_repo: ConversationMessageRepository,
    mailbox_key: MailboxKey,
    conversation_id: str,
    ctx: SupportToolContext,
    missing_files: set[str],
) -> None:
    if ctx.ask_question_reason == "serial_correction":
        conversation.serial_correction_attempt_count += 1
    else:
        conversation.question_round_count += 1
    conversation_repo.save(conversation)
    _enqueue_reply(
        message_repo, conversation, mailbox_key, conversation_id,
        _with_linked_file_request(ctx.ask_question_text, missing_files),
    )


def _handle_create_ticket(
    db: Session,
    mailbox_key: MailboxKey,
    conversation_id: str,
    ctx: SupportToolContext,
) -> None:
    """Enqueues the work; handle_create_ticket_task below does it. Nothing
    customer-facing happens this turn — the confirmation text the model composed is
    carried on the payload and only sent once the outcome is actually known."""
    task_repo = TaskRepository(db)
    if task_repo.has_open_or_running(
        TaskType.create_ticket.value, mailbox_key, conversation_id
    ):
        logger.info(
            "create_ticket task already open/running for conversation %s; skipping enqueue",
            conversation_id,
        )
        return
    task_repo.enqueue(
        task_type=TaskType.create_ticket.value,
        mailbox_key=mailbox_key,
        conversation_id=conversation_id,
        payload=ctx.create_ticket_args,
    )


async def handle_create_ticket_task(
    task_id: str, adapter: str, mailbox: str, conversation_id: str, payload: dict
) -> None:
    """Worker entry point for a claimed create_ticket task, called via
    app.support.ingestion.port.process_create_ticket. Owns the task's terminal status in
    every branch except "error", which raises so the worker's record_failure applies the
    normal attempt-count-gated retry instead."""
    db = SessionLocal()
    try:
        task_repo = TaskRepository(db)
        conversation_repo = ConversationRepository(db)
        message_repo = ConversationMessageRepository(db)
        mailbox_key = MailboxKey(adapter, mailbox)
        conversation = conversation_repo.get_or_create(mailbox_key, conversation_id)

        if conversation.ticket_id is not None:
            # Defense in depth against ever calling the ticket API twice for one
            # conversation; the enqueue-time guard plus same-pass ordering should make
            # this unreachable.
            logger.warning(
                "handle_create_ticket_task for conversation %s but ticket_id=%s already "
                "set; no-op",
                conversation_id,
                conversation.ticket_id,
            )
            task_repo.mark_done(task_id)
            return

        args = payload
        outcome: TicketOutcome = await TicketClient().create_ticket(
            unit_serial=args["unit_serial"],
            issue_description=args["issue_description"],
            title=args["title"],
            receiving_inbox_address=_receiving_inbox_address(conversation),
            conversation_id=conversation_id,
        )

        # Each branch commits once, at the end: a ticket_id must never reach the database
        # without the reply that tells the customer about it, since the guard above would
        # then make the retry a no-op and the message would be lost for good.
        if outcome.kind == "created":
            attachments = EmailAttachmentService(db).list_for_conversation(mailbox_key, conversation_id)
            inbound = [
                message for message in message_repo.get_all(conversation.id)
                if message.direction == "inbound"
            ]
            missing_files = _missing_linked_files(inbound, attachments)
            conversation.ticket_id = outcome.ticket_id
            conversation.unit_serial = args["unit_serial"]
            conversation.issue_description = args["issue_description"]
            conversation_repo.save(conversation, commit=False)
            _enqueue_reply(
                message_repo, conversation, mailbox_key, conversation_id,
                _with_linked_file_request(args["customer_message"], missing_files), commit=False,
            )
            enqueue_backfill(db, conversation, outcome.ticket_id, commit=False)
            _enqueue_ticket_attachments(
                db, mailbox_key, conversation_id, outcome.ticket_id,
                attachments,
            )
            task_repo.mark_done(task_id, commit=False)
            db.commit()

        elif outcome.kind == "duplicate":
            attachments = EmailAttachmentService(db).list_for_conversation(mailbox_key, conversation_id)
            inbound = [
                message for message in message_repo.get_all(conversation.id)
                if message.direction == "inbound"
            ]
            missing_files = _missing_linked_files(inbound, attachments)
            existing = outcome.existing_ticket or {}
            existing_id = existing.get("id")
            if existing_id:
                conversation.ticket_id = existing_id
                conversation_repo.save(conversation, commit=False)
                enqueue_backfill(db, conversation, existing_id, commit=False)
                _enqueue_ticket_attachments(
                    db, mailbox_key, conversation_id, existing_id,
                    attachments,
                )
                task_repo.mark_done(task_id, commit=False)
            else:
                # API returned 409 but omitted the ticket id — cannot close the
                # conversation safely, and retrying can't change the answer.
                logger.error(
                    "409 duplicate for conversation %s but existing ticket has no id — "
                    "dead-lettering",
                    conversation_id,
                )
                task_repo.mark_dead_letter(
                    task_id,
                    payload_patch={
                        "reason": "409_without_ticket_id",
                        "existing": existing,
                    },
                    commit=False,
                )
            text = _with_linked_file_request(_compose_duplicate_message(existing), missing_files)
            _enqueue_reply(
                message_repo, conversation, mailbox_key, conversation_id, text, commit=False
            )
            db.commit()

        elif outcome.kind == "unit_not_found":
            # Definitive for this serial, so the task is done — the customer sending a
            # corrected serial starts a new turn and a new task.
            conversation.serial_correction_attempt_count += 1
            conversation_repo.save(conversation, commit=False)
            _enqueue_reply(
                message_repo, conversation, mailbox_key, conversation_id,
                _UNIT_NOT_FOUND_MESSAGE, commit=False,
            )
            task_repo.mark_done(task_id, commit=False)
            db.commit()

        elif outcome.kind == "store_not_found":
            # Not customer-fixable — an internal receivingInboxAddress/store routing
            # problem. System alert/dead-letter, never surfaced as a re-ask (§7.2, §10.2).
            logger.error(
                "STORE_NOT_FOUND for conversation %s (adapter=%s, mailbox=%s) — "
                "routing/config issue, dead-lettering",
                conversation_id,
                mailbox_key.adapter,
                mailbox_key.mailbox,
            )
            task_repo.mark_dead_letter(
                task_id,
                payload_patch={
                    "reason": "STORE_NOT_FOUND",
                    "unit_serial": args["unit_serial"],
                },
            )

        else:  # "error" — transient/API failure. Deliberately not dead-lettered here:
               # unlike the two branches above, a retry might succeed.
            raise RuntimeError(
                f"create_ticket API error for conversation {conversation_id}: {outcome.error_detail}"
            )
    finally:
        db.close()


def _enqueue_ticket_attachments(
    db: Session,
    mailbox_key: MailboxKey,
    conversation_id: str,
    ticket_id: str,
    attachments: list,
) -> None:
    task_repo = TaskRepository(db)
    for attachment in attachments:
        if (
            attachment.capture_status != "ready"
            or attachment.ticket_status in {"uploaded", "rejected", "error"}
        ):
            continue
        attachment.ticket_id = ticket_id
        attachment.ticket_status = "pending"
        task_repo.enqueue_unique_task_if_absent(
            task_type=TaskType.attach_ticket_file.value,
            mailbox_key=mailbox_key,
            conversation_id=conversation_id,
            external_message_id=attachment.id,
            payload={"attachment_id": attachment.id, "ticket_id": ticket_id},
            commit=False,
        )


def _notify_attachment_failure(
    db: Session,
    mailbox_key: MailboxKey,
    conversation_id: str,
    ticket_id: str,
    file_name: str,
    reason: str,
) -> None:
    conversation = ConversationRepository(db).get_or_create(mailbox_key, conversation_id)
    _enqueue_reply(
        ConversationMessageRepository(db), conversation, mailbox_key, conversation_id,
        f"Your ticket was created, but the attached file {file_name!r} could not be "
        f"added ({reason}). Please resend it.",
        commit=False,
    )
    enqueue_backfill(db, conversation, ticket_id, commit=False)


async def handle_ticket_attachment_task(
    task_id: str, adapter: str, mailbox: str, conversation_id: str, payload: dict
) -> None:
    """Upload one canonical original after a new or duplicate ticket ID is known."""
    db = SessionLocal()
    try:
        task_repo = TaskRepository(db)
        mailbox_key = MailboxKey(adapter, mailbox)
        attachment_service = EmailAttachmentService(db)
        attachment = attachment_service.repository.get_by_id(payload["attachment_id"])
        if attachment is None or (
            attachment.adapter, attachment.mailbox, attachment.conversation_id
        ) != (adapter, mailbox, conversation_id):
            task_repo.mark_dead_letter(
                task_id, payload_patch={"reason": "attachment_record_missing_or_mismatched"}
            )
            return
        if attachment.ticket_status == "uploaded":
            task_repo.mark_done(task_id)
            return
        if attachment.capture_status != "ready" or not attachment.storage_path:
            attachment.ticket_status = "rejected"
            attachment.ticket_error = attachment.capture_error or "Attachment unavailable."
            _notify_attachment_failure(
                db, mailbox_key, conversation_id, payload["ticket_id"],
                attachment.file_name, attachment.ticket_error,
            )
            task_repo.mark_dead_letter(
                task_id, payload_patch={"reason": "canonical_attachment_unavailable"},
                commit=False,
            )
            db.commit()
            return

        if rejection := attachment_service.stored_file_rejection(attachment):
            attachment.ticket_status = "rejected"
            attachment.ticket_error = rejection
            _notify_attachment_failure(
                db, mailbox_key, conversation_id, payload["ticket_id"],
                attachment.file_name, rejection,
            )
            task_repo.mark_done(task_id, commit=False)
            db.commit()
            return

        outcome: TicketAttachmentOutcome = await TicketClient().attach_file(
            ticket_id=payload["ticket_id"],
            attachment_id=attachment.id,
            file_name=attachment.file_name,
            content_type=attachment.content_type,
            file_path=attachment.storage_path,
        )
        if outcome.kind == "uploaded":
            attachment.ticket_id = payload["ticket_id"]
            attachment.ticket_status = "uploaded"
            attachment.ticket_file_id = outcome.ticket_file_id
            attachment.ticket_error = None
            attachment.ticket_uploaded_at = datetime.now(UTC)
            task_repo.mark_done(task_id, commit=False)
            db.commit()
            attachment_service.delete_uploaded_local_file(attachment)
            return
        if outcome.kind == "rejected":
            attachment.ticket_status = "rejected"
            attachment.ticket_error = outcome.error_detail
            _notify_attachment_failure(
                db, mailbox_key, conversation_id, payload["ticket_id"],
                attachment.file_name, outcome.error_detail or "upload rejected",
            )
            task_repo.mark_done(task_id, commit=False)
            db.commit()
            return
        raise RuntimeError(
            f"ticket attachment API error for {attachment.id}: {outcome.error_detail}"
        )
    finally:
        db.close()


def finalize_ticket_attachment_failure(
    task_id: str,
    adapter: str,
    mailbox: str,
    conversation_id: str,
    attachment_id: str,
    reason: str,
) -> None:
    """Record exhausted retries and queue one customer notice atomically."""
    db = SessionLocal()
    try:
        task_repo = TaskRepository(db)
        attachment = EmailAttachmentService(db).repository.get_by_id(attachment_id)
        if attachment is None:
            task_repo.mark_dead_letter(
                task_id, payload_patch={"last_error": reason, "reason": "attachment_record_missing"}
            )
            return
        if attachment.ticket_status in {"uploaded", "rejected"}:
            task_repo.mark_done(task_id)
            return
        if attachment.ticket_status == "error":
            task_repo.mark_dead_letter(task_id, payload_patch={"last_error": reason})
            return
        attachment.ticket_status = "error"
        attachment.ticket_error = reason
        mailbox_key = MailboxKey(adapter, mailbox)
        conversation = ConversationRepository(db).get_or_create(mailbox_key, conversation_id)
        ticket_id = attachment.ticket_id or conversation.ticket_id
        if ticket_id:
            _notify_attachment_failure(
                db, mailbox_key, conversation_id, ticket_id, attachment.file_name,
                "upload failed after several attempts",
            )
        task_repo.mark_dead_letter(
            task_id, payload_patch={"last_error": reason}, commit=False
        )
        db.commit()
    finally:
        db.close()


def _escalate(
    db: Session,
    conversation: Conversation,
    message_repo: ConversationMessageRepository,
    mailbox_key: MailboxKey,
    conversation_id: str,
    missing_files: set[str] | None = None,
) -> None:
    """§10.1: round cap hit with no serial, or serial-correction budget exhausted.
    Queues a holding message, then dead-letters a synthesized create_ticket task so the
    escalation is a queryable row under the same 7-day retention as any other
    dead-letter — it is never picked up or executed by the worker. (synthesize_dead_letter
    rather than mark_dead_letter: escalation never got as far as a claimed task.)"""
    _enqueue_reply(
        message_repo, conversation, mailbox_key, conversation_id,
        _with_linked_file_request(_ESCALATION_MESSAGE, missing_files or set()),
    )
    TaskRepository(db).synthesize_dead_letter(
        task_type=TaskType.create_ticket.value,
        mailbox_key=mailbox_key,
        conversation_id=conversation_id,
        payload={"reason": "escalation_cap_exhausted"},
    )
