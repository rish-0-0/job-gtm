"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-12-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create job_listings table
    op.create_table('job_listings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_title', sa.String(length=255), nullable=False),
    sa.Column('job_role', sa.String(length=255), nullable=False),
    sa.Column('job_location', sa.String(length=255), nullable=True),
    sa.Column('employment_type', sa.String(length=100), nullable=True),
    sa.Column('salary_range', sa.String(length=255), nullable=True),
    sa.Column('min_salary', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('max_salary', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('required_experience', sa.String(length=255), nullable=True),
    sa.Column('seniority_level', sa.String(length=100), nullable=True),
    sa.Column('job_description', sa.Text(), nullable=True),
    sa.Column('date_posted', sa.String(length=100), nullable=True),
    sa.Column('posting_url', sa.Text(), nullable=True),
    sa.Column('hiring_team', sa.Text(), nullable=True),
    sa.Column('about_company', sa.Text(), nullable=True),
    sa.Column('scraper_source', sa.String(length=100), nullable=False),
    sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('company_title', 'job_role', 'job_location', 'employment_type', name='uq_job_listing_details')
    )
    op.create_index(op.f('ix_job_listings_company_title'), 'job_listings', ['company_title'], unique=False)
    op.create_index(op.f('ix_job_listings_id'), 'job_listings', ['id'], unique=False)
    op.create_index(op.f('ix_job_listings_job_location'), 'job_listings', ['job_location'], unique=False)
    op.create_index(op.f('ix_job_listings_job_role'), 'job_listings', ['job_role'], unique=False)
    op.create_index(op.f('ix_job_listings_posting_url'), 'job_listings', ['posting_url'], unique=True)
    op.create_index(op.f('ix_job_listings_scraper_source'), 'job_listings', ['scraper_source'], unique=False)

    # Create workflow_runs table
    op.create_table('workflow_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workflow_id', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('result', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workflow_runs_id'), 'workflow_runs', ['id'], unique=False)
    op.create_index(op.f('ix_workflow_runs_workflow_id'), 'workflow_runs', ['workflow_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_workflow_runs_workflow_id'), table_name='workflow_runs')
    op.drop_index(op.f('ix_workflow_runs_id'), table_name='workflow_runs')
    op.drop_table('workflow_runs')
    op.drop_index(op.f('ix_job_listings_scraper_source'), table_name='job_listings')
    op.drop_index(op.f('ix_job_listings_posting_url'), table_name='job_listings')
    op.drop_index(op.f('ix_job_listings_job_role'), table_name='job_listings')
    op.drop_index(op.f('ix_job_listings_job_location'), table_name='job_listings')
    op.drop_index(op.f('ix_job_listings_id'), table_name='job_listings')
    op.drop_index(op.f('ix_job_listings_company_title'), table_name='job_listings')
    op.drop_table('job_listings')
