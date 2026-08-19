"""add SOP belief feedback submissions

Revision ID: 202607110011
Revises: 202607110010
Create Date: 2026-08-19 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202607110011"
down_revision: str | None = "202607110010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sop_belief_feedback_submissions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("owner_user_id", sa.String(length=80), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("task_id", sa.String(length=80), nullable=False),
        sa.Column("rating", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "tenant_id",
            "task_id",
            "rating",
            name="uq_sop_belief_feedback_submission_scope_task_rating",
        ),
    )
    op.create_index(
        "ix_sop_belief_feedback_submissions_scope_task",
        "sop_belief_feedback_submissions",
        ["owner_user_id", "tenant_id", "task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sop_belief_feedback_submissions_scope_task",
        table_name="sop_belief_feedback_submissions",
    )
    op.drop_table("sop_belief_feedback_submissions")
