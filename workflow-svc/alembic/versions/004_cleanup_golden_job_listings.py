"""Cleanup golden job listings data - fix malformed values and inconsistencies

Revision ID: 004
Revises: 003
Create Date: 2026-01-10 10:00:00.000000

Fixes:
1. Normalize location data (None, empty strings, pipe-separated values)
2. Handle pipe-separated values by selecting the first non-empty value
3. Clean up seniority level data
4. Clean up work arrangement data
5. Clean up company data
6. Clean up role classification data
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """
    Run all cleanup operations on job_listings_golden table
    """
    connection = op.get_bind()

    # Step 1: Clean up location_city
    # Handle: None, empty strings, pipe-separated values (pick first)
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET location_city = NULL
        WHERE location_city IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    # Replace pipe-separated values with first value
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET location_city = TRIM(SPLIT_PART(location_city, '|', 1))
        WHERE location_city LIKE '%|%'
          AND location_city IS NOT NULL
          AND location_city NOT IN ('', 'None', 'NULL');
    """))

    # Step 2: Clean up location_state
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET location_state = NULL
        WHERE location_state IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET location_state = TRIM(SPLIT_PART(location_state, '|', 1))
        WHERE location_state LIKE '%|%'
          AND location_state IS NOT NULL
          AND location_state NOT IN ('', 'None', 'NULL');
    """))

    # Step 3: Clean up location_country
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET location_country = NULL
        WHERE location_country IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET location_country = TRIM(SPLIT_PART(location_country, '|', 1))
        WHERE location_country LIKE '%|%'
          AND location_country IS NOT NULL
          AND location_country NOT IN ('', 'None', 'NULL');
    """))

    # Step 4: Clean up job_location_normalized
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET job_location_normalized = NULL
        WHERE job_location_normalized IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET job_location_normalized = TRIM(SPLIT_PART(job_location_normalized, '|', 1))
        WHERE job_location_normalized LIKE '%|%'
          AND job_location_normalized IS NOT NULL
          AND job_location_normalized NOT IN ('', 'None', 'NULL');
    """))

    # Step 5: Clean up seniority_level_normalized
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET seniority_level_normalized = NULL
        WHERE seniority_level_normalized IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET seniority_level_normalized = TRIM(SPLIT_PART(seniority_level_normalized, '|', 1))
        WHERE seniority_level_normalized LIKE '%|%'
          AND seniority_level_normalized IS NOT NULL
          AND seniority_level_normalized NOT IN ('', 'None', 'NULL');
    """))

    # Step 6: Clean up work_arrangement_normalized
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET work_arrangement_normalized = NULL
        WHERE work_arrangement_normalized IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET work_arrangement_normalized = TRIM(SPLIT_PART(work_arrangement_normalized, '|', 1))
        WHERE work_arrangement_normalized LIKE '%|%'
          AND work_arrangement_normalized IS NOT NULL
          AND work_arrangement_normalized NOT IN ('', 'None', 'NULL');
    """))

    # Step 7: Clean up company_industry
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET company_industry = NULL
        WHERE company_industry IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET company_industry = TRIM(SPLIT_PART(company_industry, '|', 1))
        WHERE company_industry LIKE '%|%'
          AND company_industry IS NOT NULL
          AND company_industry NOT IN ('', 'None', 'NULL');
    """))

    # Step 8: Clean up company_size
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET company_size = NULL
        WHERE company_size IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET company_size = TRIM(SPLIT_PART(company_size, '|', 1))
        WHERE company_size LIKE '%|%'
          AND company_size IS NOT NULL
          AND company_size NOT IN ('', 'None', 'NULL');
    """))

    # Step 9: Clean up primary_role
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET primary_role = NULL
        WHERE primary_role IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET primary_role = TRIM(SPLIT_PART(primary_role, '|', 1))
        WHERE primary_role LIKE '%|%'
          AND primary_role IS NOT NULL
          AND primary_role NOT IN ('', 'None', 'NULL');
    """))

    # Step 10: Clean up role_category
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET role_category = NULL
        WHERE role_category IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET role_category = TRIM(SPLIT_PART(role_category, '|', 1))
        WHERE role_category LIKE '%|%'
          AND role_category IS NOT NULL
          AND role_category NOT IN ('', 'None', 'NULL');
    """))

    # Step 11: Clean up employment_type_normalized
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET employment_type_normalized = NULL
        WHERE employment_type_normalized IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET employment_type_normalized = TRIM(SPLIT_PART(employment_type_normalized, '|', 1))
        WHERE employment_type_normalized LIKE '%|%'
          AND employment_type_normalized IS NOT NULL
          AND employment_type_normalized NOT IN ('', 'None', 'NULL');
    """))

    # Step 12: Clean up job_role
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET job_role = NULL
        WHERE job_role IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET job_role = TRIM(SPLIT_PART(job_role, '|', 1))
        WHERE job_role LIKE '%|%'
          AND job_role IS NOT NULL
          AND job_role NOT IN ('', 'None', 'NULL');
    """))

    # Step 13: Clean up company_title
    # Handle: None, empty strings, pipe-separated values
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET company_title = NULL
        WHERE company_title IN ('None', 'NONE', 'none', '', 'NULL', 'null', 'N/A', 'n/a');
    """))

    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET company_title = TRIM(SPLIT_PART(company_title, '|', 1))
        WHERE company_title LIKE '%|%'
          AND company_title IS NOT NULL
          AND company_title NOT IN ('', 'None', 'NULL');
    """))

    # Step 14: Trim excess whitespace from all string fields
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET
            location_city = NULLIF(TRIM(location_city), ''),
            location_state = NULLIF(TRIM(location_state), ''),
            location_country = NULLIF(TRIM(location_country), ''),
            job_location_normalized = NULLIF(TRIM(job_location_normalized), ''),
            seniority_level_normalized = NULLIF(TRIM(seniority_level_normalized), ''),
            work_arrangement_normalized = NULLIF(TRIM(work_arrangement_normalized), ''),
            company_industry = NULLIF(TRIM(company_industry), ''),
            company_size = NULLIF(TRIM(company_size), ''),
            primary_role = NULLIF(TRIM(primary_role), ''),
            role_category = NULLIF(TRIM(role_category), ''),
            employment_type_normalized = NULLIF(TRIM(employment_type_normalized), ''),
            job_role = NULLIF(TRIM(job_role), ''),
            company_title = NULLIF(TRIM(company_title), '');
    """))

    # Step 15: Update timestamp to track when cleanup was performed
    connection.execute(sa.text("""
        UPDATE job_listings_golden
        SET updated_at = NOW()
        WHERE enrichment_status = 'completed';
    """))


def downgrade():
    """
    Downgrade is not supported for data cleanup migrations.
    This migration makes permanent changes to the data.
    """
    pass
