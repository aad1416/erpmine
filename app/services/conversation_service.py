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
from typing import List

from sqlalchemy.orm import Session

from app.config.setting import settings
from app.db.database import SessionLocal
from app.db.models.Conversation import Conversation
from app.repositories.conversation_messages import ConversationMessageRepository
from app.repositories.conversations import ConversationRepository
from app.services.communication_log_client import enqueue_backfill
from app.services.decision_agent import DecisionAgent, SupportToolContext
from app.services.ticket_client import TicketClient, TicketOutcome
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
    return "\n".join(lines)


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

        if conversation.ticket_id is not None:
            # §10.1: post-ticket message handling is explicitly out of scope for this
            # phase — a deliberate no-op, not an error.
            logger.info(
                "Conversation %s already has ticket_id=%s; ignoring new batch",
                conversation_id,
                conversation.ticket_id,
            )
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

        run_input = _build_run_input(conversation, history, messages)
        ctx = SupportToolContext()
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
                conversation, conversation_repo, message_repo, mailbox_key, conversation_id, ctx
            )
        elif ctx.tool_called == "create_ticket":
            _handle_create_ticket(db, mailbox_key, conversation_id, ctx)
        elif ctx.tool_called == "reply":
            _enqueue_reply(
                message_repo, conversation, mailbox_key, conversation_id, ctx.reply_text
            )
        else:
            _escalate(db, conversation, message_repo, mailbox_key, conversation_id)
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
) -> None:
    if ctx.ask_question_reason == "serial_correction":
        conversation.serial_correction_attempt_count += 1
    else:
        conversation.question_round_count += 1
    conversation_repo.save(conversation)
    _enqueue_reply(
        message_repo, conversation, mailbox_key, conversation_id, ctx.ask_question_text
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
            conversation.ticket_id = outcome.ticket_id
            conversation.unit_serial = args["unit_serial"]
            conversation.issue_description = args["issue_description"]
            conversation_repo.save(conversation, commit=False)
            _enqueue_reply(
                message_repo, conversation, mailbox_key, conversation_id,
                args["customer_message"], commit=False,
            )
            enqueue_backfill(db, conversation, outcome.ticket_id, commit=False)
            task_repo.mark_done(task_id, commit=False)
            db.commit()

        elif outcome.kind == "duplicate":
            existing = outcome.existing_ticket or {}
            existing_id = existing.get("id")
            if existing_id:
                conversation.ticket_id = existing_id
                conversation_repo.save(conversation, commit=False)
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
            text = _compose_duplicate_message(existing)
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


def _escalate(
    db: Session,
    conversation: Conversation,
    message_repo: ConversationMessageRepository,
    mailbox_key: MailboxKey,
    conversation_id: str,
) -> None:
    """§10.1: round cap hit with no serial, or serial-correction budget exhausted.
    Queues a holding message, then dead-letters a synthesized create_ticket task so the
    escalation is a queryable row under the same 7-day retention as any other
    dead-letter — it is never picked up or executed by the worker. (synthesize_dead_letter
    rather than mark_dead_letter: escalation never got as far as a claimed task.)"""
    _enqueue_reply(
        message_repo, conversation, mailbox_key, conversation_id, _ESCALATION_MESSAGE
    )
    TaskRepository(db).synthesize_dead_letter(
        task_type=TaskType.create_ticket.value,
        mailbox_key=mailbox_key,
        conversation_id=conversation_id,
        payload={"reason": "escalation_cap_exhausted"},
    )
