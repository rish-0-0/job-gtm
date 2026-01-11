"""
Pytest configuration and shared fixtures for text-to-SQL tests
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any

# Test fixtures for common test data


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_nl_queries() -> Dict[str, str]:
    """Sample natural language queries for testing"""
    return {
        "simple_count": "How many job listings are there?",
        "filter_by_role": "Show me all Senior Engineer positions",
        "salary_filter": "What jobs pay between 100k and 150k?",
        "location_filter": "Find jobs in New York",
        "remote_jobs": "Show me remote job opportunities",
        "company_filter": "Jobs at Google or Microsoft",
        "complex_query": "How many remote Senior Engineer positions are there that pay more than 150k?",
        "aggregation": "Average salary by role",
        "multiple_conditions": "Remote jobs in San Francisco with salary above 120k",
        "null_handling": "Jobs where remote status is unknown",
    }


@pytest.fixture
def expected_sql_queries() -> Dict[str, str]:
    """Expected SQL queries for validation"""
    return {
        "simple_count": "SELECT COUNT(*) FROM mv_root_data",
        "filter_by_role": "SELECT * FROM mv_root_data WHERE primary_role = 'Senior Engineer'",
        "salary_filter": "SELECT * FROM mv_root_data WHERE min_salary_usd >= 100000 AND max_salary_usd <= 150000",
        "location_filter": "SELECT * FROM mv_root_data WHERE location_city = 'New York'",
        "remote_jobs": "SELECT * FROM mv_root_data WHERE is_remote = true",
    }


@pytest.fixture
def mock_database_results() -> Dict[str, Any]:
    """Mock database results for testing"""
    return {
        "columns": ["id", "company_title", "job_role", "min_salary_usd", "max_salary_usd"],
        "rows": [
            (1, "Google", "Senior Engineer", 150000, 200000),
            (2, "Microsoft", "Senior Engineer", 160000, 210000),
            (3, "Amazon", "Software Engineer", 120000, 160000),
        ],
        "row_count": 3,
    }


@pytest.fixture
def schema_context() -> Dict[str, Any]:
    """Database schema context for LLM prompts"""
    return {
        "table": "mv_root_data",
        "columns": [
            {"name": "id", "type": "INTEGER", "description": "Unique job listing ID"},
            {"name": "company_title", "type": "TEXT", "description": "Company name"},
            {"name": "job_role", "type": "TEXT", "description": "Job title/role"},
            {"name": "job_location_normalized", "type": "TEXT", "description": "Normalized location"},
            {"name": "employment_type_normalized", "type": "TEXT", "description": "Employment type (full-time, part-time, contract)"},
            {"name": "min_salary_usd", "type": "NUMERIC", "description": "Minimum salary in USD"},
            {"name": "max_salary_usd", "type": "NUMERIC", "description": "Maximum salary in USD"},
            {"name": "seniority_level_normalized", "type": "TEXT", "description": "Seniority level"},
            {"name": "is_remote", "type": "BOOLEAN", "description": "Whether job is remote"},
            {"name": "location_city", "type": "TEXT", "description": "City"},
            {"name": "location_country", "type": "TEXT", "description": "Country"},
            {"name": "company_industry", "type": "TEXT", "description": "Industry"},
            {"name": "company_size", "type": "TEXT", "description": "Company size"},
            {"name": "primary_role", "type": "TEXT", "description": "Primary role category"},
            {"name": "role_category", "type": "TEXT", "description": "Role category"},
            {"name": "scraper_source", "type": "TEXT", "description": "Data source"},
            {"name": "enrichment_status", "type": "TEXT", "description": "Enrichment status"},
            {"name": "created_at", "type": "TIMESTAMP", "description": "Creation timestamp"},
        ],
        "examples": [
            {
                "query": "How many jobs are there?",
                "sql": "SELECT COUNT(*) FROM mv_root_data",
            },
            {
                "query": "Show me senior engineer positions",
                "sql": "SELECT * FROM mv_root_data WHERE primary_role = 'Senior Engineer' LIMIT 100",
            },
        ],
    }


@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """Mock LLM response for testing"""
    return {
        "sql": "SELECT * FROM mv_root_data WHERE primary_role = 'Senior Engineer' LIMIT 100",
        "confidence": 0.95,
        "model": "test-model",
        "metadata": {
            "prompt_tokens": 1200,
            "response_tokens": 150,
            "duration_ms": 2500,
        },
    }


@pytest.fixture
def mock_llm_provider() -> AsyncMock:
    """Create a mock LLM provider"""
    provider = AsyncMock()
    provider.provider_name = "test-provider"
    provider.model_name = "test-model"
    provider.generate_sql = AsyncMock(
        return_value={
            "sql": "SELECT * FROM mv_root_data LIMIT 100",
            "confidence": 0.95,
            "model": "test-model",
            "metadata": {"prompt_tokens": 100, "response_tokens": 50, "duration_ms": 1000},
        }
    )
    provider.health_check = AsyncMock(return_value=True)
    return provider


@pytest.fixture
def mock_embedding_service() -> Mock:
    """Create a mock embedding service"""
    service = Mock()
    service.embed = Mock(
        return_value=[0.1] * 384  # 384-dimensional vector
    )
    return service


@pytest.fixture
def mock_redis_client() -> Mock:
    """Create a mock Redis client"""
    client = Mock()
    client.get = Mock(return_value=None)  # Cache miss by default
    client.set = Mock(return_value=True)
    client.delete = Mock(return_value=1)
    return client


@pytest.fixture
def mock_database_session() -> MagicMock:
    """Create a mock database session"""
    session = MagicMock()
    session.query = Mock()
    session.execute = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    return session


@pytest.fixture
def invalid_sql_queries() -> Dict[str, str]:
    """Invalid SQL queries for testing validation"""
    return {
        "drop_table": "DROP TABLE mv_root_data; SELECT * FROM mv_root_data",
        "update_query": "UPDATE mv_root_data SET salary = 100000",
        "comment_injection": "SELECT * FROM mv_root_data; -- comment",
        "union_injection": "SELECT * FROM mv_root_data UNION SELECT * FROM other_table",
        "no_select": "INSERT INTO mv_root_data VALUES (1, 'test')",
        "invalid_column": "SELECT invalid_col FROM mv_root_data",
        "multiple_statements": "SELECT * FROM mv_root_data; DELETE FROM mv_root_data",
        "unbalanced_parens": "SELECT * FROM mv_root_data WHERE (id = 1",
        "missing_table": "SELECT * FROM different_table",
        "xp_command": "SELECT xp_cmdshell('whoami')",
    }


@pytest.fixture
def valid_sql_queries() -> Dict[str, str]:
    """Valid SQL queries for testing validation"""
    return {
        "simple_select": "SELECT * FROM mv_root_data",
        "with_where": "SELECT * FROM mv_root_data WHERE is_remote = true",
        "with_order": "SELECT * FROM mv_root_data ORDER BY created_at DESC",
        "with_limit": "SELECT * FROM mv_root_data LIMIT 50",
        "with_aggregation": "SELECT primary_role, COUNT(*) FROM mv_root_data GROUP BY primary_role",
        "with_join": "SELECT * FROM mv_root_data WHERE min_salary_usd BETWEEN 100000 AND 150000",
        "with_like": "SELECT * FROM mv_root_data WHERE company_title LIKE '%Engineer%'",
        "with_case": "SELECT CASE WHEN is_remote THEN 'Remote' ELSE 'On-site' END FROM mv_root_data",
        "with_functions": "SELECT UPPER(primary_role), COUNT(*) FROM mv_root_data GROUP BY primary_role",
    }


@pytest.fixture
def test_metrics() -> Dict[str, Any]:
    """Initialize metrics tracking"""
    return {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "execution_times": [],
        "accuracy": 0.0,
    }
