"""add email attachments

Revision ID: d6f8a93e12b4
Revises: c4e5f6a7b8c9
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d6f8a93e12b4"
down_revision: Union[str, Sequence[str], None] = "c4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_attachments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("adapter", sa.String(), nullable=False),
        sa.Column("mailbox", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("external_message_id", sa.String(), nullable=False),
        sa.Column("external_attachment_id", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("capture_status", sa.String(length=24), nullable=False),
        sa.Column("capture_error", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("ai_status", sa.String(length=24), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.String(), nullable=True),
        sa.Column("ticket_status", sa.String(length=24), nullable=False),
        sa.Column("ticket_file_id", sa.String(), nullable=True),
        sa.Column("ticket_error", sa.Text(), nullable=True),
        sa.Column("ticket_uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("openai_file_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "adapter",
            "mailbox",
            "external_message_id",
            "external_attachment_id",
            name="uq_email_attachment_provider_identity",
        ),
    )
    op.create_index(
        op.f("ix_email_attachments_mailbox"), "email_attachments", ["mailbox"]
    )
    op.create_index(
        op.f("ix_email_attachments_conversation_id"),
        "email_attachments",
        ["conversation_id"],
    )
    op.create_index(
        op.f("ix_email_attachments_external_message_id"),
        "email_attachments",
        ["external_message_id"],
    )
    op.create_index(
        op.f("ix_email_attachments_ticket_id"), "email_attachments", ["ticket_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_attachments_ticket_id"), table_name="email_attachments")
    op.drop_index(
        op.f("ix_email_attachments_external_message_id"),
        table_name="email_attachments",
    )
    op.drop_index(
        op.f("ix_email_attachments_conversation_id"), table_name="email_attachments"
    )
    op.drop_index(op.f("ix_email_attachments_mailbox"), table_name="email_attachments")
    op.drop_table("email_attachments")
