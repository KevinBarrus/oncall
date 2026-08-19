"""add compressed tool evidence

Revision ID: 202607110012
Revises: 202607110011
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision = "202607110012"
down_revision: str | None = "202607110011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table("compressed_tool_evidence", sa.Column("id", sa.String(80), primary_key=True), sa.Column("owner_user_id", sa.String(80), nullable=False), sa.Column("chat_session_id", sa.String(80), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False), sa.Column("tool_name", sa.String(160), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("source_hash", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_compressed_tool_evidence_owner_session", "compressed_tool_evidence", ["owner_user_id", "chat_session_id"])

def downgrade() -> None:
    op.drop_index("ix_compressed_tool_evidence_owner_session", table_name="compressed_tool_evidence")
    op.drop_table("compressed_tool_evidence")
