"""add SOP belief persistence

Revision ID: 202607110008
Revises: 202607110007
Create Date: 2026-07-11 23:58:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202607110008"
down_revision: str | None = "202607110007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sop_belief_states",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=80), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("document_id", sa.String(length=80), nullable=False),
        sa.Column("document_version", sa.String(length=96), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("beta", sa.Float(), nullable=False),
        sa.Column("failure_modes", sa.JSON(), nullable=False),
        sa.Column("contexts", sa.JSON(), nullable=False),
        sa.Column("observations", sa.Integer(), nullable=False),
        sa.Column("mean_tokens", sa.Float(), nullable=False),
        sa.Column("mean_turns", sa.Float(), nullable=False),
        sa.Column("mean_elapsed_seconds", sa.Float(), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "owner_user_id",
            "tenant_id",
            "document_id",
            "document_version",
            name="uq_sop_belief_states_scope_document_version",
        ),
    )
    op.create_index("ix_sop_belief_states_owner_user_id", "sop_belief_states", ["owner_user_id"])
    op.create_index("ix_sop_belief_states_tenant_id", "sop_belief_states", ["tenant_id"])
    op.create_index("ix_sop_belief_states_document_id", "sop_belief_states", ["document_id"])
    op.create_index(
        "ix_sop_belief_states_scope_document",
        "sop_belief_states",
        ["owner_user_id", "tenant_id", "document_id"],
    )

    op.create_table(
        "sop_belief_evidence",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("state_id", sa.String(length=80), nullable=False),
        sa.Column("owner_user_id", sa.String(length=80), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("task_id", sa.String(length=80), nullable=False),
        sa.Column("document_id", sa.String(length=80), nullable=False),
        sa.Column("document_version", sa.String(length=96), nullable=False),
        sa.Column("context", sa.String(length=240), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("failure_mode", sa.String(length=160), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("turns", sa.Integer(), nullable=False),
        sa.Column("elapsed_seconds", sa.Float(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["state_id"], ["sop_belief_states.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sop_belief_evidence_state_id", "sop_belief_evidence", ["state_id"])
    op.create_index("ix_sop_belief_evidence_owner_user_id", "sop_belief_evidence", ["owner_user_id"])
    op.create_index("ix_sop_belief_evidence_tenant_id", "sop_belief_evidence", ["tenant_id"])
    op.create_index("ix_sop_belief_evidence_task_id", "sop_belief_evidence", ["task_id"])
    op.create_index("ix_sop_belief_evidence_document_id", "sop_belief_evidence", ["document_id"])
    op.create_index(
        "ix_sop_belief_evidence_scope_task",
        "sop_belief_evidence",
        ["owner_user_id", "tenant_id", "task_id"],
    )
    op.create_index(
        "ix_sop_belief_evidence_state_created",
        "sop_belief_evidence",
        ["state_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("sop_belief_evidence")
    op.drop_table("sop_belief_states")
