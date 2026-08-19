"""add SOP belief attribution fields

Revision ID: 202607110010
Revises: 202607110009
Create Date: 2026-07-12 00:02:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202607110010"
down_revision: str | None = "202607110009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sop_belief_evidence",
        sa.Column("attribution_stage", sa.String(length=40), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "sop_belief_evidence",
        sa.Column("evidence_strength", sa.String(length=40), nullable=False, server_default="unknown"),
    )


def downgrade() -> None:
    op.drop_column("sop_belief_evidence", "evidence_strength")
    op.drop_column("sop_belief_evidence", "attribution_stage")
