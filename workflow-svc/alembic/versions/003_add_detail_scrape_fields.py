"""add detail scrape fields

Revision ID: 003
Revises: 002
Create Date: 2025-12-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add detail scraping metadata fields
    op.add_column('job_listings_golden',
        sa.Column('detail_scraped_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('job_listings_golden',
        sa.Column('detail_scrape_status', sa.String(length=50), nullable=True)
    )
    op.add_column('job_listings_golden',
        sa.Column('detail_scrape_duration_ms', sa.Integer(), nullable=True)
    )
    op.add_column('job_listings_golden',
        sa.Column('detail_scrape_errors', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    # Add full_page_text column for storing raw page content for AI processing
    op.add_column('job_listings_golden',
        sa.Column('full_page_text', sa.Text(), nullable=True)
    )

    # Create index on detail_scrape_status for efficient querying
    op.create_index(
        op.f('ix_job_listings_golden_detail_scrape_status'),
        'job_listings_golden',
        ['detail_scrape_status'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_job_listings_golden_detail_scrape_status'), table_name='job_listings_golden')
    op.drop_column('job_listings_golden', 'full_page_text')
    op.drop_column('job_listings_golden', 'detail_scrape_errors')
    op.drop_column('job_listings_golden', 'detail_scrape_duration_ms')
    op.drop_column('job_listings_golden', 'detail_scrape_status')
    op.drop_column('job_listings_golden', 'detail_scraped_at')
