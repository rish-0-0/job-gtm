"""Create mv_root_data materialized view

Revision ID: 001
Revises:
Create Date: 2024-12-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW mv_root_data AS
        SELECT
            id,
            company_title,
            job_role,
            job_location_normalized,
            employment_type_normalized,
            min_salary_usd,
            max_salary_usd,
            seniority_level_normalized,
            is_remote,
            location_city,
            location_country,
            company_industry,
            company_size,
            primary_role,
            role_category,
            scraper_source,
            enrichment_status,
            created_at
        FROM job_listings_golden
        WHERE enrichment_status = 'completed'
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_mv_root_data_id ON mv_root_data(id)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_root_data")
