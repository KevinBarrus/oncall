"""add archived chat messages

Revision ID: 202607110014
Revises: 202607110013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202607110014"
down_revision: str | None = "202607110013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "archived_chat_messages",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("owner_user_id", sa.String(80), nullable=False),
        sa.Column(
            "session_id",
            sa.String(80),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_archived_chat_messages_owner_session_created_at",
        "archived_chat_messages",
        ["owner_user_id", "session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_archived_chat_messages_owner_session_created_at",
        table_name="archived_chat_messages",
    )
    op.drop_table("archived_chat_messages")
