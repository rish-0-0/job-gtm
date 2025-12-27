"""Create custom_materialized_views table for tracking user-defined views

Revision ID: 002
Revises: 001
Create Date: 2024-12-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_materialized_views",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Columns in order as specified by user
        sa.Column("columns", JSONB, nullable=False),
        # The actual view name in postgres (e.g., mv_custom_my_view)
        sa.Column("view_name", sa.String(100), nullable=False, unique=True),
        # Migration file that created this view
        sa.Column("migration_revision", sa.String(50), nullable=True),
        # Status tracking
        sa.Column("status", sa.String(50), nullable=False, default="pending"),
        # pending, creating, completed, failed
        sa.Column("error_message", sa.Text(), nullable=True),
        # Workflow tracking
        sa.Column("workflow_id", sa.String(255), nullable=True),
        # Row count (updated on refresh)
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        # Created by (for future multi-user support)
        sa.Column("created_by", sa.String(100), nullable=True),
    )

    # Index for status queries
    op.create_index("ix_custom_materialized_views_status", "custom_materialized_views", ["status"])


def downgrade() -> None:
    op.drop_index("ix_custom_materialized_views_status")
    op.drop_table("custom_materialized_views")
