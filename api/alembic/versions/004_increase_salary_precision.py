"""Increase salary column precision

Revision ID: 004
Revises: 003
Create Date: 2025-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop materialized view first (it depends on these columns)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_root_data")

    # Increase precision from NUMERIC(10,2) to NUMERIC(12,2)
    # This allows values up to 9,999,999,999.99 (nearly 10 billion)
    op.execute("""
        ALTER TABLE job_listings_golden
        ALTER COLUMN min_salary_raw TYPE NUMERIC(12,2),
        ALTER COLUMN max_salary_raw TYPE NUMERIC(12,2),
        ALTER COLUMN min_salary_usd TYPE NUMERIC(12,2),
        ALTER COLUMN max_salary_usd TYPE NUMERIC(12,2)
    """)

    # Recreate materialized view with updated column types
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

    # Recreate index
    op.execute("CREATE UNIQUE INDEX idx_mv_root_data_id ON mv_root_data(id)")


def downgrade() -> None:
    # Drop materialized view first
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_root_data")

    # Revert back to NUMERIC(10,2)
    op.execute("""
        ALTER TABLE job_listings_golden
        ALTER COLUMN min_salary_raw TYPE NUMERIC(10,2),
        ALTER COLUMN max_salary_raw TYPE NUMERIC(10,2),
        ALTER COLUMN min_salary_usd TYPE NUMERIC(10,2),
        ALTER COLUMN max_salary_usd TYPE NUMERIC(10,2)
    """)

    # Recreate materialized view
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

    # Recreate index
    op.execute("CREATE UNIQUE INDEX idx_mv_root_data_id ON mv_root_data(id)")
