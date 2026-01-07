"""Create nl_query_cache table with pgvector support for text-to-SQL feature

Revision ID: 003
Revises: 002
Create Date: 2025-12-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create natural language query cache table
    op.create_table(
        "nl_query_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # Original query
        sa.Column("query_text", sa.Text(), nullable=False),
        # SHA256 hash for exact matching
        sa.Column("query_hash", sa.String(64), nullable=False, unique=True, index=True),
        # Vector embedding for semantic similarity (384 dimensions for all-MiniLM-L6-v2)
        sa.Column("query_embedding", sa.Text(), nullable=False),  # Will be cast to vector(384)
        # Generated SQL
        sa.Column("generated_sql", sa.Text(), nullable=False),
        # LLM metadata
        sa.Column("llm_provider", sa.String(50), nullable=False),  # ollama, chatgpt, claude
        sa.Column("llm_model", sa.String(100), nullable=False),  # e.g., qwen2.5:7b
        # Validation status
        sa.Column("validated", sa.Boolean(), nullable=False, default=False),
        # Usage tracking
        sa.Column("execution_count", sa.Integer(), nullable=False, default=0),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # LLM response metadata (tokens, duration, etc.)
        sa.Column("metadata", JSONB, nullable=True),
    )

    # Cast query_embedding column to vector type
    op.execute("ALTER TABLE nl_query_cache ALTER COLUMN query_embedding TYPE vector(384) USING query_embedding::vector")

    # Create pgvector index for similarity search (IVFFlat with 100 lists)
    # Note: Build index after data is loaded for better performance
    op.execute("""
        CREATE INDEX ix_nl_query_cache_embedding_ivfflat
        ON nl_query_cache
        USING ivfflat (query_embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Index for cache eviction queries
    op.create_index("ix_nl_query_cache_last_used", "nl_query_cache", ["last_used_at"])

    # Index for provider analytics
    op.create_index("ix_nl_query_cache_provider", "nl_query_cache", ["llm_provider"])


def downgrade() -> None:
    op.drop_index("ix_nl_query_cache_provider")
    op.drop_index("ix_nl_query_cache_last_used")
    op.drop_index("ix_nl_query_cache_embedding_ivfflat")
    op.drop_table("nl_query_cache")
    # Note: We don't drop the vector extension as other tables might use it
