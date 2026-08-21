"""add chat session audit failure counter

Revision ID: 202608210002
Revises: 202608210001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202608210002"
down_revision: str | None = "202608210001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column(
            "audit_failure_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "audit_failure_count")
