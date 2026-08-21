"""add chat session compaction error tracking

Revision ID: 202608210001
Revises: 202607110014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202608210001"
down_revision: str | None = "202607110014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("last_compaction_error", sa.String(200), nullable=True),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("last_compaction_failed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "last_compaction_failed_at")
    op.drop_column("chat_sessions", "last_compaction_error")
