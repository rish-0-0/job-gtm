# Text-to-SQL Feature Tests and Evaluations

This directory contains comprehensive tests and evaluations for the text-to-SQL feature in the Job GTM platform.

## Directory Structure

```
tests/
├── conftest.py                          # Shared fixtures and configuration
├── pytest.ini                          # Pytest configuration
├── unit/                               # Unit tests for individual components
│   ├── test_sql_validator.py          # SQL validation, sanitization, security
│   └── test_llm_providers.py          # LLM provider implementations
├── integration/                        # Integration tests
│   └── test_text_to_sql_flow.py      # End-to-end flows and interactions
└── evals/                             # Evaluation and benchmark tests
    └── test_text_to_sql_evals.py     # Accuracy, performance, quality metrics
```

## Test Coverage

### Unit Tests (37 tests)

#### SQL Validator (`test_sql_validator.py`)
- **Validation Tests**: SELECT queries with various WHERE, GROUP BY, ORDER BY clauses
- **Rejection Tests**: DROP, UPDATE, DELETE, INSERT statements, SQL injection, comment injection
- **Column Validation**: Whitelist enforcement, invalid column detection
- **Sanitization Tests**: LIMIT addition, trailing semicolon removal, whitespace handling
- **Edge Cases**: Case insensitivity, qualified column names, BETWEEN, IN, CASE expressions, aggregate functions

#### LLM Providers (`test_llm_providers.py`)
- **Provider Interface**: Abstract class requirements, method signatures
- **Claude Provider**: SQL generation, health checks, metadata collection
- **ChatGPT Provider**: SQL generation, response parsing, timeout handling
- **Ollama Provider**: Local inference, connection handling, fallback support
- **Error Handling**: Timeout errors, validation errors, provider errors

### Integration Tests (20 tests)

#### Text-to-SQL Flow (`test_text_to_sql_flow.py`)
- **SQL Generation**: End-to-end flow, validation pipeline, multi-provider support
- **SQL Execution**: Valid/invalid SQL execution, result formatting, Decimal conversion
- **Caching**: Redis exact match cache, similarity cache, cache hit/miss scenarios
- **Error Handling**: Provider timeouts, fallback mechanisms, database errors
- **Request Validation**: Query length validation, prompt injection detection, provider validation
- **Complex Queries**: Aggregations, joins, multi-condition filters

### Evaluation Tests (35 tests)

#### Accuracy (`test_text_to_sql_evals.py`)
- **Keyword Coverage**: Expected SQL keywords in generated queries
- **Syntax Validity**: All generated SQL passes validation (≥80% threshold)
- **Semantic Correctness**: SQL semantically matches natural language (≥70% threshold)
- **Coverage Metrics**: Support for 9+ SQL features (≥80% support rate)

#### Performance (`test_text_to_sql_evals.py`)
- **Generation Latency**: Measure end-to-end generation time
- **Cache Performance**: Cache hit vs miss speed comparison
- **Hashing Performance**: Query hashing throughput (300 queries in <100ms)
- **Sanitization Overhead**: SQL sanitization throughput (300 queries in <500ms)

#### Quality (`test_text_to_sql_evals.py`)
- **Confidence Scores**: Distribution and reasonableness (0.5-0.99 average)
- **Token Usage**: Prompt/response token tracking and validation
- **Response Consistency**: Same query produces consistent results

#### Security (`test_text_to_sql_evals.py`)
- **SQL Injection Prevention**: Catch ≥80% of SQL injection attempts
- **Prompt Injection Prevention**: Catch ≥50% of prompt injection attempts
- **Column Whitelist**: Enforce whitelisted column access
- **Table Whitelist**: Enforce single table (mv_root_data) access

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-asyncio pytest-cov
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test Categories

**Unit Tests Only:**
```bash
pytest tests/unit/ -v
```

**Integration Tests Only:**
```bash
pytest tests/integration/ -v
```

**Evaluation Tests Only:**
```bash
pytest tests/evals/ -v
```

**Unit + Integration (exclude slow evals):**
```bash
pytest tests/ -m "not evals" -v
```

### Run Tests by Marker

**All tests marked as requiring LLM:**
```bash
pytest -m requires_llm -v
```

**Tests requiring database:**
```bash
pytest -m requires_db -v
```

**Exclude slow tests:**
```bash
pytest -m "not slow" -v
```

### With Coverage Report

```bash
pytest tests/ --cov=app --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`

### Verbose Output

```bash
pytest tests/ -v -s
```

The `-s` flag shows print statements and logging output.

### Run Single Test File

```bash
pytest tests/unit/test_sql_validator.py -v
```

### Run Single Test Class

```bash
pytest tests/unit/test_sql_validator.py::TestSQLValidator -v
```

### Run Single Test

```bash
pytest tests/unit/test_sql_validator.py::TestSQLValidator::test_simple_select_query_valid -v
```

## Test Fixtures

Common fixtures available in `conftest.py`:

- **sample_nl_queries**: Natural language test queries
- **expected_sql_queries**: Expected SQL for validation
- **schema_context**: Database schema context for LLM prompts
- **mock_llm_provider**: Mock LLM provider
- **mock_database_session**: Mock database session
- **mock_redis_client**: Mock Redis client
- **valid_sql_queries**: Dictionary of valid SQL queries
- **invalid_sql_queries**: Dictionary of invalid SQL queries (for security testing)
- **test_metrics**: Metrics tracking structure

### Using Fixtures

```python
def test_example(valid_sql_queries):
    sql = valid_sql_queries["simple_select"]
    # Test with this SQL
```

## Test Configuration

### pytest.ini

Configuration options:
- `testpaths`: Specifies test directories
- `python_files`: File name pattern for tests
- `asyncio_mode`: Async test handling mode
- `markers`: Custom test markers (unit, integration, evals, slow, requires_db, requires_llm)

## Sample Output

```
tests/unit/test_sql_validator.py::TestSQLValidator::test_simple_select_query_valid PASSED
tests/unit/test_sql_validator.py::TestSQLValidator::test_drop_table_rejected PASSED
tests/unit/test_llm_providers.py::TestClaudeProvider::test_generate_sql_success PASSED
tests/integration/test_text_to_sql_flow.py::TestTextToSQLGenerationFlow::test_generate_sql_end_to_end PASSED
tests/evals/test_text_to_sql_evals.py::TestTextToSQLAccuracy::test_sql_generation_keyword_coverage PASSED

======================== 92 passed in 3.24s ========================
```

## Key Testing Principles

### Unit Tests
- Test individual components in isolation
- Use mocks for external dependencies
- Fast execution (< 1s total)
- No database or LLM provider required

### Integration Tests
- Test interaction between components
- Mock external services (LLM, database)
- Validate complete workflows
- Moderate speed (1-3s total)

### Evaluation Tests
- Measure quality metrics and accuracy
- Benchmark performance
- Validate security properties
- Marked as `@pytest.mark.slow` - can take longer
- Run less frequently (before releases)

## Metrics to Monitor

Track these metrics from test output:

1. **Accuracy**: SQL generation keyword coverage ≥80%
2. **Syntax Validity**: ≥80% of generated SQL passes validation
3. **Semantic Correctness**: ≥70% semantic match with natural language
4. **Performance**: <100ms average generation latency
5. **Security**: ≥80% SQL injection prevention rate
6. **Feature Support**: ≥80% SQL feature coverage

## Adding New Tests

### For new SQL features:

1. Add test case to `valid_sql_queries` fixture
2. Add unit test in `test_sql_validator.py`
3. Add integration test in `test_text_to_sql_flow.py`
4. Add eval test in `test_text_to_sql_evals.py`

### For new LLM provider:

1. Create provider class following `LLMProvider` interface
2. Add unit tests in `test_llm_providers.py`
3. Add health check and error handling tests
4. Add to provider router selection logic

### For new security concerns:

1. Add rejection test in `test_sql_validator.py`
2. Add security eval test
3. Update injection attempt lists in `test_text_to_sql_evals.py`

## CI/CD Integration

Recommended GitHub Actions workflow:

```yaml
- name: Run unit tests
  run: pytest tests/unit/ -v

- name: Run integration tests
  run: pytest tests/integration/ -v

- name: Generate coverage
  run: pytest tests/ --cov=app --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### AsyncIO Errors
Ensure `pytest-asyncio` is installed and `asyncio_mode = auto` in pytest.ini

### Import Errors
Make sure `PYTHONPATH` includes the api directory:
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/job-gtm/api"
```

### Mock Not Working
Verify patch paths use full module paths:
```python
@patch("app.services.sql_validator.SQLValidator")
```

### Tests Hanging
Check for missing `AsyncMock` or infinite loops in test setup

## Performance Baselines

Expected test execution times:

- Unit tests: ~1-2 seconds
- Integration tests: ~2-3 seconds
- All evaluation tests: ~10-20 seconds
- Full test suite: ~15-25 seconds

If tests exceed these times, investigate for performance regressions.

## Future Enhancements

- [ ] Add property-based testing with Hypothesis
- [ ] Add mutation testing for test quality
- [ ] Add performance regression tracking
- [ ] Add E2E tests with real database
- [ ] Add LLM provider comparison benchmarks
- [ ] Add SQL execution time benchmarks
- [ ] Add caching effectiveness metrics
- [ ] Add semantic similarity validation
