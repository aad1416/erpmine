"""add imap_thread_messages

IMAP-only threading record (ticket 03 of the IMAP/SMTP adapter): every inbound
message's Message-ID, References, sender and Conversation, and every Message-ID we send,
per Mailbox. Never purged, unlike adapter_outbox_messages.

Revision ID: c3d4e5f6a7b8
Revises: 0d07fda149a7
Create Date: 2026-09-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = '0d07fda149a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'imap_thread_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('direction', sa.String(), nullable=False),
        sa.Column('message_id', sa.String(), nullable=True),
        sa.Column('reference_ids', sa.Text(), nullable=True),
        sa.Column('sender_address', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('message_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', 'message_id', name='uq_imap_thread_source_message_id'),
    )
    op.create_index(
        'ix_imap_thread_source_conversation',
        'imap_thread_messages',
        ['source_id', 'conversation_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_imap_thread_source_conversation', table_name='imap_thread_messages')
    op.drop_table('imap_thread_messages')
