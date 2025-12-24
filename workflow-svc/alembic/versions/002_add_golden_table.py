"""add golden table

Revision ID: 002
Revises: 001
Create Date: 2025-12-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create job_listings_golden table
    op.create_table('job_listings_golden',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_job_id', sa.Integer(), nullable=True),
    sa.Column('posting_url', sa.Text(), nullable=False),

    # Core fields
    sa.Column('company_title', sa.String(length=255), nullable=True),
    sa.Column('job_role', sa.String(length=255), nullable=True),
    sa.Column('job_location_raw', sa.String(length=255), nullable=True),
    sa.Column('job_location_normalized', sa.String(length=255), nullable=True),
    sa.Column('employment_type_raw', sa.String(length=100), nullable=True),
    sa.Column('employment_type_normalized', sa.String(length=100), nullable=True),

    # Salary normalization
    sa.Column('salary_range_raw', sa.String(length=255), nullable=True),
    sa.Column('min_salary_raw', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('max_salary_raw', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('currency_raw', sa.String(length=10), nullable=True),
    sa.Column('min_salary_usd', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('max_salary_usd', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('currency_conversion_rate', sa.Numeric(precision=10, scale=6), nullable=True),
    sa.Column('currency_conversion_date', sa.DateTime(timezone=True), nullable=True),

    # Experience and seniority fields
    sa.Column('required_experience', sa.String(length=255), nullable=True),
    sa.Column('seniority_level_raw', sa.String(length=100), nullable=True),
    sa.Column('seniority_level_normalized', sa.String(length=50), nullable=True),
    sa.Column('seniority_confidence_score', sa.Numeric(precision=3, scale=2), nullable=True),

    # Work arrangement
    sa.Column('work_arrangement_raw', sa.String(length=100), nullable=True),
    sa.Column('work_arrangement_normalized', sa.String(length=50), nullable=True),

    # Fraud detection
    sa.Column('scam_score', sa.Integer(), nullable=True),
    sa.Column('scam_indicators', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

    # Skills and tech stack
    sa.Column('skills_extracted', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('tech_stack_normalized', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

    # Location normalization
    sa.Column('location_city', sa.String(length=100), nullable=True),
    sa.Column('location_state', sa.String(length=100), nullable=True),
    sa.Column('location_country', sa.String(length=100), nullable=True),
    sa.Column('location_timezone', sa.String(length=50), nullable=True),
    sa.Column('is_remote', sa.Boolean(), nullable=True),

    # Company enrichment
    sa.Column('about_company_raw', sa.Text(), nullable=True),
    sa.Column('company_research', sa.Text(), nullable=True),
    sa.Column('company_industry', sa.String(length=100), nullable=True),
    sa.Column('company_size', sa.String(length=100), nullable=True),

    # Hiring team
    sa.Column('hiring_team_raw', sa.Text(), nullable=True),
    sa.Column('hiring_team_analysis', sa.Text(), nullable=True),

    # Benefits
    sa.Column('has_stock_options', sa.Boolean(), nullable=True),
    sa.Column('stock_options_details', sa.Text(), nullable=True),
    sa.Column('other_benefits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

    # Full job details (from deep scrape)
    sa.Column('job_description_full', sa.Text(), nullable=True),
    sa.Column('job_requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('job_benefits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

    # Role classification
    sa.Column('primary_role', sa.String(length=100), nullable=True),
    sa.Column('role_category', sa.String(length=100), nullable=True),
    sa.Column('is_management', sa.Boolean(), nullable=True),

    # Additional metadata from raw job_listing
    sa.Column('date_posted', sa.String(length=100), nullable=True),
    sa.Column('scraper_source', sa.String(length=100), nullable=True),
    sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True),

    # Processing metadata
    sa.Column('enriched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ollama_model_version', sa.String(length=50), nullable=True),
    sa.Column('processing_duration_ms', sa.Integer(), nullable=True),
    sa.Column('ai_prompt_tokens', sa.Integer(), nullable=True),
    sa.Column('ai_response_tokens', sa.Integer(), nullable=True),
    sa.Column('enrichment_status', sa.String(length=50), nullable=True),
    sa.Column('enrichment_errors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('enrichment_version', sa.Integer(), server_default='1', nullable=False),

    # Timestamps
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),

    sa.PrimaryKeyConstraint('id'),
    sa.ForeignKeyConstraint(['source_job_id'], ['job_listings.id'], ),
    )

    # Create indexes
    op.create_index(op.f('ix_job_listings_golden_id'), 'job_listings_golden', ['id'], unique=False)
    op.create_index(op.f('ix_job_listings_golden_posting_url'), 'job_listings_golden', ['posting_url'], unique=True)
    op.create_index(op.f('ix_job_listings_golden_source_job_id'), 'job_listings_golden', ['source_job_id'], unique=False)
    op.create_index(op.f('ix_job_listings_golden_company_title'), 'job_listings_golden', ['company_title'], unique=False)
    op.create_index(op.f('ix_job_listings_golden_enrichment_status'), 'job_listings_golden', ['enrichment_status'], unique=False)
    op.create_index(op.f('ix_job_listings_golden_seniority_level_normalized'), 'job_listings_golden', ['seniority_level_normalized'], unique=False)
    op.create_index(op.f('ix_job_listings_golden_scraper_source'), 'job_listings_golden', ['scraper_source'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_job_listings_golden_scraper_source'), table_name='job_listings_golden')
    op.drop_index(op.f('ix_job_listings_golden_seniority_level_normalized'), table_name='job_listings_golden')
    op.drop_index(op.f('ix_job_listings_golden_enrichment_status'), table_name='job_listings_golden')
    op.drop_index(op.f('ix_job_listings_golden_company_title'), table_name='job_listings_golden')
    op.drop_index(op.f('ix_job_listings_golden_source_job_id'), table_name='job_listings_golden')
    op.drop_index(op.f('ix_job_listings_golden_posting_url'), table_name='job_listings_golden')
    op.drop_index(op.f('ix_job_listings_golden_id'), table_name='job_listings_golden')
    op.drop_table('job_listings_golden')
