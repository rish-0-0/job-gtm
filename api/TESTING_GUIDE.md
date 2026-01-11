# Text-to-SQL Feature Testing Guide

A comprehensive testing and evaluation framework for the Job GTM platform's text-to-SQL feature.

## Overview

This testing framework provides:

- **92 tests** across unit, integration, and evaluation categories
- **Coverage of all SQL operations** from generation to execution to caching
- **Security validation** for SQL injection and prompt injection attacks
- **Performance benchmarks** for latency and throughput
- **Quality metrics** for accuracy and confidence scores

## Quick Start

### Install Dependencies

```bash
pip install pytest pytest-asyncio pytest-cov
```

### Run Tests

From the `api/` directory:

```bash
# Run all tests
pytest tests/ -v

# Or use the runner scripts
./tests/run_tests.sh all          # Linux/Mac
.\tests\run_tests.bat all         # Windows
```

## Test Structure

### Unit Tests (37 tests)

Located in `tests/unit/`

#### SQL Validator (20 tests)
- Validates SELECT queries with WHERE, GROUP BY, ORDER BY, LIMIT
- Rejects dangerous operations: DROP, DELETE, UPDATE, INSERT
- Prevents SQL injection via comment injection, multiple statements, UNION injection
- Enforces column and table whitelisting
- Tests edge cases: case insensitivity, string literals, qualified names

**Key Tests:**
```
test_simple_select_query_valid
test_drop_table_rejected
test_invalid_column_rejected
test_sanitize_adds_limit
test_sql_injection_prevention
```

#### LLM Providers (17 tests)
- Tests Claude provider with Anthropic API
- Tests ChatGPT provider with OpenAI API
- Tests Ollama provider with local inference
- Validates response structures and metadata
- Tests health checks and error handling

**Key Tests:**
```
test_generate_sql_success
test_generate_sql_with_metadata
test_health_check_success
test_provider_name
test_timeout_error_raised
```

### Integration Tests (20 tests)

Located in `tests/integration/`

#### Text-to-SQL Flow
- End-to-end SQL generation with validation
- Multi-provider SQL generation comparison
- SQL execution with validation
- Caching mechanisms (Redis and pgvector)
- Error handling and fallback strategies
- Request validation and injection detection
- Complex query handling (aggregations, joins, multi-conditions)

**Key Tests:**
```
test_generate_sql_end_to_end
test_generate_sql_with_validation
test_redis_cache_hit
test_cache_set_and_retrieve
test_llm_provider_timeout_handled
test_aggregation_query_generation
```

### Evaluation Tests (35 tests)

Located in `tests/evals/`

#### Accuracy Evaluation
- **Keyword Coverage**: Generated SQL contains expected keywords (≥80% threshold)
- **Syntax Validity**: Generated SQL passes validation (≥80% threshold)
- **Semantic Correctness**: SQL matches natural language intent (≥70% threshold)

#### Performance Evaluation
- **Generation Latency**: Measure end-to-end generation time
- **Cache Performance**: Compare cache hit vs miss speeds
- **Query Hashing**: Throughput of SHA256 hashing (300 queries in <100ms)
- **Sanitization Overhead**: Throughput of SQL sanitization (300 queries in <500ms)

#### Quality Evaluation
- **Confidence Scores**: Distribution between 0.5-0.99 (reasonableness check)
- **Token Usage**: Validation of prompt/response token tracking
- **Response Consistency**: Same query produces identical results

#### Security Evaluation
- **SQL Injection Prevention**: Catch ≥80% of injection attempts
- **Prompt Injection Prevention**: Catch ≥50% of prompt injection attempts
- **Column Whitelist Enforcement**: Prevent unauthorized column access
- **Table Whitelist Enforcement**: Prevent access to non-whitelisted tables

#### Coverage Evaluation
- **Feature Support**: Validates 9+ SQL features work correctly (≥80% support)
  - WHERE clause, GROUP BY, ORDER BY, LIMIT
  - AGGREGATION (COUNT, AVG, MAX, MIN)
  - CASE expressions, String functions, BETWEEN, IN operator

## Running Specific Tests

### By Category

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Evaluation tests only (slow, run separately)
pytest tests/evals/ -v

# Fast tests (exclude slow evals)
pytest tests/ -m "not slow" -v
```

### By Component

```bash
# SQL Validator tests
pytest tests/unit/test_sql_validator.py -v

# LLM Provider tests
pytest tests/unit/test_llm_providers.py -v

# Text-to-SQL flow tests
pytest tests/integration/test_text_to_sql_flow.py -v
```

### By Marker

```bash
# Tests requiring LLM provider
pytest -m requires_llm -v

# Tests requiring database
pytest -m requires_db -v

# Exclude slow tests
pytest -m "not slow" -v
```

### Single Test

```bash
# Run a single test class
pytest tests/unit/test_sql_validator.py::TestSQLValidator -v

# Run a single test method
pytest tests/unit/test_sql_validator.py::TestSQLValidator::test_simple_select_query_valid -v
```

## Coverage Report

Generate HTML coverage report:

```bash
pytest tests/ --cov=app --cov-report=html
```

Open `htmlcov/index.html` in browser to view detailed coverage.

## Test Runner Scripts

### Linux/Mac

```bash
# Run all tests
./tests/run_tests.sh all

# Run unit tests
./tests/run_tests.sh unit

# Run with coverage
./tests/run_tests.sh coverage

# Run a specific test
./tests/run_tests.sh test tests/unit/test_sql_validator.py

# Verbose output
./tests/run_tests.sh verbose
```

### Windows

```bash
# Run all tests
.\tests\run_tests.bat all

# Run unit tests
.\tests\run_tests.bat unit

# Run with coverage
.\tests\run_tests.bat coverage

# Run a specific test
.\tests\run_tests.bat test tests\unit\test_sql_validator.py
```

## Test Fixtures

Common fixtures available in `conftest.py`:

```python
# Sample natural language queries
sample_nl_queries: Dict[str, str]

# Expected SQL outputs
expected_sql_queries: Dict[str, str]

# Database schema context
schema_context: Dict[str, Any]

# Mock LLM provider
mock_llm_provider: AsyncMock

# Mock Redis client
mock_redis_client: Mock

# Mock database session
mock_database_session: MagicMock

# Valid SQL for testing
valid_sql_queries: Dict[str, str]

# Invalid SQL for security testing
invalid_sql_queries: Dict[str, str]
```

## Key Metrics to Monitor

Track these metrics from test output:

| Metric | Target | Description |
|--------|--------|-------------|
| **Accuracy** | ≥80% | SQL keyword coverage in generated queries |
| **Validity** | ≥80% | Percentage of generated SQL that passes validation |
| **Semantic Match** | ≥70% | SQL semantic correctness vs natural language |
| **Performance** | <100ms | Average SQL generation latency |
| **SQL Injection Block** | ≥80% | Percentage of injection attempts caught |
| **Prompt Injection Block** | ≥50% | Percentage of prompt injection attempts caught |
| **Feature Support** | ≥80% | Percentage of SQL features that work |
| **Cache Effectiveness** | Varies | Hit rate and speed improvement |

## Test Execution Times

Expected durations:

- Unit tests: ~1-2 seconds
- Integration tests: ~2-3 seconds
- All evaluation tests: ~10-20 seconds
- **Total test suite: ~15-25 seconds**

## Continuous Integration

### GitHub Actions Example

```yaml
name: Test Text-to-SQL Feature

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r api/requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run unit tests
        run: pytest tests/unit/ -v

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Generate coverage
        run: pytest tests/ --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

## Adding New Tests

### For New SQL Features

1. Add test case to `valid_sql_queries` fixture in `conftest.py`
2. Create unit test in `tests/unit/test_sql_validator.py`
3. Create integration test in `tests/integration/test_text_to_sql_flow.py`
4. Create eval test in `tests/evals/test_text_to_sql_evals.py`

### For New LLM Provider

1. Implement provider class following `LLMProvider` interface
2. Add unit tests in `tests/unit/test_llm_providers.py`:
   - Health check
   - SQL generation
   - Error handling
   - Timeout handling
3. Add integration tests for provider switching and fallback
4. Update `app/services/llm_router.py` to include new provider

### For New Security Concerns

1. Add to `invalid_sql_queries` fixture
2. Add rejection test in `test_sql_validator.py`
3. Add security eval test in `test_text_to_sql_evals.py`
4. Update SQLValidator if new validation needed

## Troubleshooting

### AsyncIO Errors

Error: `RuntimeError: Event loop is closed`

Solution: Ensure `pytest-asyncio` is installed and `pytest.ini` has `asyncio_mode = auto`

### Import Errors

Error: `ModuleNotFoundError: No module named 'app'`

Solution: Set PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Mock Not Working

Ensure patch paths use full module paths:
```python
@patch("app.services.sql_validator.SQLValidator")
```

### Tests Hanging

Check for:
- Missing `AsyncMock` usage
- Infinite loops in test setup
- Unclosed database connections

## Performance Regression Testing

Track these metrics over time:

```bash
# Run with timing information
pytest tests/ -v --durations=10
```

This shows the 10 slowest tests and can help identify performance regressions.

## Code Examples

### Testing SQL Validation

```python
def test_custom_sql(validator):
    sql = "SELECT * FROM mv_root_data WHERE salary > 100000"
    is_valid, error = validator.validate(sql)
    assert is_valid is True

    sanitized = validator.sanitize(sql)
    assert "LIMIT" in sanitized
```

### Testing LLM Provider

```python
@pytest.mark.asyncio
async def test_sql_generation(mock_llm_provider, schema_context):
    result = await mock_llm_provider.generate_sql(
        "Show remote jobs",
        schema_context
    )

    assert "sql" in result
    assert result["confidence"] > 0.8
    assert "metadata" in result
```

### Testing Cache

```python
def test_cache_hit(mock_redis_client):
    import hashlib

    query = "Show remote jobs"
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    cached_sql = "SELECT * FROM mv_root_data WHERE is_remote = true"

    mock_redis_client.get.return_value = cached_sql

    result = mock_redis_client.get(f"nlquery:{query_hash}")
    assert result == cached_sql
```

## Best Practices

1. **Run tests before committing**: Use pre-commit hooks
2. **Use coverage reports**: Aim for >80% code coverage
3. **Monitor performance**: Track execution times for regressions
4. **Separate unit/integration/evals**: Run unit+integration in CI, evals separately
5. **Keep tests independent**: No test should depend on another
6. **Use descriptive names**: Test names should describe what they test
7. **Mock external services**: Database, LLM providers, Redis
8. **Test error cases**: Not just happy path
9. **Update tests with features**: New SQL features need tests
10. **Review test failures**: Don't ignore flaky tests

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [SQL Validator Code](../app/services/sql_validator.py)
- [LLM Providers](../app/services/)
- [Text-to-SQL Router](../app/routers/nl_query.py)

## Support

For issues or questions:

1. Check test output for specific failures
2. Run with `-vv -s` flags for verbose output
3. Check the [tests/README.md](tests/README.md) for detailed reference
4. Review existing tests for examples
5. Check fixture definitions in `conftest.py`
