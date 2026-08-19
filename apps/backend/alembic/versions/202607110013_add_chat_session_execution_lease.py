"""add chat session execution lease

Revision ID: 202607110013
Revises: 202607110012
"""

import sqlalchemy as sa
from alembic import op

revision = "202607110013"
down_revision = "202607110012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("execution_lease_token", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("execution_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_chat_sessions_execution_lease_expires_at",
        "chat_sessions",
        ["execution_lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_execution_lease_expires_at", table_name="chat_sessions")
    op.drop_column("chat_sessions", "execution_lease_expires_at")
    op.drop_column("chat_sessions", "execution_lease_token")
