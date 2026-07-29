"""Initial schema: documents, review_sessions, issues

Revision ID: 001
Revises:
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Documents ────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False, server_default=""),
        sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("storage_path", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── Review Sessions ──────────────────────────────────────────────────
    op.create_table(
        "review_sessions",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("document_id", sa.String(255), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("profile_id", sa.Text(), nullable=False),
        sa.Column("pack_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("categories", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.Text(), nullable=False, server_default="completed"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category_scores", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("report_markdown", sa.Text(), nullable=False, server_default=""),
    )

    # ── Issues ───────────────────────────────────────────────────────────
    op.create_table(
        "issues",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(255),
            sa.ForeignKey("review_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("issue_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_line_start", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("evidence_line_end", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("evidence_location", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.Text(), nullable=False, server_default="rule"),
        sa.Column("autofix_allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── Indexes ──────────────────────────────────────────────────────────
    op.create_index("idx_issues_session", "issues", ["session_id"])
    op.create_index("idx_issues_status", "issues", ["status"])
    op.create_index("idx_sessions_document", "review_sessions", ["document_id"])
    op.create_index("idx_sessions_created", "review_sessions", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("idx_sessions_created", table_name="review_sessions")
    op.drop_index("idx_sessions_document", table_name="review_sessions")
    op.drop_index("idx_issues_status", table_name="issues")
    op.drop_index("idx_issues_session", table_name="issues")
    op.drop_table("issues")
    op.drop_table("review_sessions")
    op.drop_table("documents")
