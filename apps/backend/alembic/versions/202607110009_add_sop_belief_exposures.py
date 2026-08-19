"""add SOP belief exposures

Revision ID: 202607110009
Revises: 202607110008
Create Date: 2026-07-12 00:01:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202607110009"
down_revision: str | None = "202607110008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sop_belief_exposures",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=80), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("task_id", sa.String(length=80), nullable=False),
        sa.Column("document_id", sa.String(length=80), nullable=False),
        sa.Column("document_version", sa.String(length=96), nullable=False),
        sa.Column("attribution_stage", sa.String(length=40), nullable=False),
        sa.Column("evidence_strength", sa.String(length=40), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sop_belief_exposures_owner_user_id", "sop_belief_exposures", ["owner_user_id"])
    op.create_index("ix_sop_belief_exposures_tenant_id", "sop_belief_exposures", ["tenant_id"])
    op.create_index("ix_sop_belief_exposures_task_id", "sop_belief_exposures", ["task_id"])
    op.create_index("ix_sop_belief_exposures_document_id", "sop_belief_exposures", ["document_id"])
    op.create_index(
        "ix_sop_belief_exposures_scope_task",
        "sop_belief_exposures",
        ["owner_user_id", "tenant_id", "task_id"],
    )


def downgrade() -> None:
    op.drop_table("sop_belief_exposures")
