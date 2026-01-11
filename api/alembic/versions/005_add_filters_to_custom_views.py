"""Add filters column to custom_materialized_views table

Revision ID: 005
Revises: 004
Create Date: 2024-01-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add filters column to store filter conditions for the view
    op.add_column(
        "custom_materialized_views",
        sa.Column("filters", JSONB, nullable=True)
    )


def downgrade() -> None:
    op.drop_column("custom_materialized_views", "filters")
