"""drop chat session compacted_message_count dead column

Revision ID: 202608210003
Revises: 202608210002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202608210003"
down_revision: str | None = "202608210002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("chat_sessions", "compacted_message_count")


def downgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("compacted_message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
