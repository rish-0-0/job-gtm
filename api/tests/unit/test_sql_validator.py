"""
Unit tests for SQL validator
Tests validation, sanitization, and security features
"""
import pytest
from app.services.sql_validator import SQLValidator, get_sql_validator


@pytest.mark.unit
class TestSQLValidator:
    """Test suite for SQLValidator class"""

    @pytest.fixture
    def validator(self):
        """Create a fresh SQL validator instance"""
        return SQLValidator()

    # ==================== VALIDATION TESTS ====================

    def test_simple_select_query_valid(self, validator):
        """Test that simple SELECT query passes validation"""
        sql = "SELECT * FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True
        assert error == ""

    def test_select_with_where_valid(self, validator):
        """Test SELECT query with WHERE clause passes validation"""
        sql = "SELECT * FROM mv_root_data WHERE is_remote = true"
        is_valid, error = validator.validate(sql)
        assert is_valid is True
        assert error == ""

    def test_select_with_aggregation_valid(self, validator):
        """Test SELECT with aggregation functions passes validation"""
        sql = "SELECT primary_role, COUNT(*) FROM mv_root_data GROUP BY primary_role"
        is_valid, error = validator.validate(sql)
        assert is_valid is True
        assert error == ""

    def test_select_with_multiple_conditions_valid(self, validator):
        """Test SELECT with complex WHERE conditions passes validation"""
        sql = "SELECT * FROM mv_root_data WHERE is_remote = true AND min_salary_usd > 100000"
        is_valid, error = validator.validate(sql)
        assert is_valid is True
        assert error == ""

    # ==================== REJECTION TESTS ====================

    def test_drop_table_rejected(self, validator, invalid_sql_queries):
        """Test that DROP TABLE is rejected"""
        sql = invalid_sql_queries["drop_table"]
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "DROP" in error or "Dangerous keyword" in error

    def test_update_statement_rejected(self, validator, invalid_sql_queries):
        """Test that UPDATE statements are rejected"""
        sql = invalid_sql_queries["update_query"]
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "UPDATE" in error or "Dangerous keyword" in error

    def test_delete_statement_rejected(self, validator):
        """Test that DELETE statements are rejected"""
        sql = "DELETE FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "Dangerous keyword" in error

    def test_insert_statement_rejected(self, validator):
        """Test that INSERT statements are rejected"""
        sql = "INSERT INTO mv_root_data VALUES (1, 'test')"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "Dangerous keyword" in error

    def test_comment_injection_rejected(self, validator):
        """Test that SQL comments are rejected"""
        sql = "SELECT * FROM mv_root_data -- comment"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "comment" in error.lower()

    def test_block_comment_rejected(self, validator):
        """Test that block comments are rejected"""
        sql = "SELECT * FROM mv_root_data /* comment */"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "comment" in error.lower()

    def test_multiple_statements_rejected(self, validator):
        """Test that multiple statements separated by semicolon are rejected"""
        sql = "SELECT * FROM mv_root_data; DELETE FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "Multiple statements" in error or "SQL injection" in error

    def test_union_injection_rejected(self, validator):
        """Test that suspicious UNION queries are rejected"""
        sql = "SELECT * FROM mv_root_data UNION SELECT * FROM other_table"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "UNION" in error or "Suspicious" in error

    def test_non_select_statement_rejected(self, validator):
        """Test that non-SELECT statements are rejected"""
        sql = "UPDATE mv_root_data SET salary = 100000"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "SELECT" in error

    def test_wrong_table_rejected(self, validator):
        """Test that queries referencing wrong table are rejected"""
        sql = "SELECT * FROM other_table"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "mv_root_data" in error

    def test_invalid_column_rejected(self, validator):
        """Test that queries with invalid columns are rejected"""
        sql = "SELECT invalid_column FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "Invalid columns" in error

    def test_unbalanced_parentheses_rejected(self, validator):
        """Test that queries with unbalanced parentheses are rejected"""
        sql = "SELECT * FROM mv_root_data WHERE (id = 1"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "parentheses" in error.lower()

    def test_xp_command_rejected(self, validator):
        """Test that xp_* commands are rejected"""
        sql = "SELECT xp_cmdshell('whoami') FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "xp_" in error or "Dangerous" in error

    # ==================== COLUMN VALIDATION TESTS ====================

    def test_all_valid_columns_allowed(self, validator):
        """Test that all whitelisted columns are allowed"""
        columns = [
            "id", "company_title", "job_role", "job_location_normalized",
            "employment_type_normalized", "min_salary_usd", "max_salary_usd",
            "seniority_level_normalized", "is_remote", "location_city",
            "location_country", "company_industry", "company_size",
            "primary_role", "role_category", "scraper_source",
            "enrichment_status", "created_at"
        ]

        # Test query with all columns
        sql = f"SELECT {', '.join(columns)} FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True
        assert error == ""

    def test_wildcard_allowed(self, validator):
        """Test that SELECT * is allowed"""
        sql = "SELECT * FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True
        assert error == ""

    def test_column_alias_not_validated(self, validator):
        """Test that column aliases don't trigger validation errors"""
        sql = "SELECT COUNT(*) as job_count FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True
        assert error == ""

    # ==================== SANITIZATION TESTS ====================

    def test_sanitize_adds_limit(self, validator, valid_sql_queries):
        """Test that sanitize adds LIMIT if missing"""
        sql = valid_sql_queries["simple_select"]
        sanitized = validator.sanitize(sql)
        assert "LIMIT" in sanitized
        assert "LIMIT 100" in sanitized

    def test_sanitize_preserves_existing_limit(self, validator):
        """Test that sanitize preserves existing LIMIT"""
        sql = "SELECT * FROM mv_root_data LIMIT 50"
        sanitized = validator.sanitize(sql)
        assert "LIMIT 50" in sanitized
        assert "LIMIT 100" not in sanitized

    def test_sanitize_removes_trailing_semicolon(self, validator):
        """Test that sanitize removes trailing semicolon"""
        sql = "SELECT * FROM mv_root_data;"
        sanitized = validator.sanitize(sql)
        assert not sanitized.endswith(";")

    def test_sanitize_strips_whitespace(self, validator):
        """Test that sanitize strips leading/trailing whitespace"""
        sql = "   SELECT * FROM mv_root_data   "
        sanitized = validator.sanitize(sql)
        assert sanitized == sanitized.strip()

    # ==================== EDGE CASES ====================

    def test_case_insensitive_validation(self, validator):
        """Test that validation is case-insensitive"""
        sql = "select * from mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_extra_whitespace_valid(self, validator):
        """Test that extra whitespace doesn't break validation"""
        sql = "SELECT    *    FROM    mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_string_literals_not_parsed(self, validator):
        """Test that SQL keywords inside string literals are not validated"""
        sql = "SELECT * FROM mv_root_data WHERE job_role LIKE 'DROP%'"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_qualified_column_names(self, validator):
        """Test that qualified column names (table.column) work"""
        sql = "SELECT mv_root_data.id FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_between_operator(self, validator):
        """Test BETWEEN operator is allowed"""
        sql = "SELECT * FROM mv_root_data WHERE min_salary_usd BETWEEN 100000 AND 150000"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_in_operator(self, validator):
        """Test IN operator is allowed"""
        sql = "SELECT * FROM mv_root_data WHERE primary_role IN ('Engineer', 'Manager')"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_case_expression(self, validator):
        """Test CASE expressions are allowed"""
        sql = "SELECT CASE WHEN is_remote THEN 'Remote' ELSE 'On-site' END FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_aggregate_functions(self, validator):
        """Test aggregate functions are allowed"""
        sql = "SELECT primary_role, COUNT(*), AVG(min_salary_usd), MAX(max_salary_usd) FROM mv_root_data GROUP BY primary_role"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_string_functions(self, validator):
        """Test string functions are allowed"""
        sql = "SELECT UPPER(company_title), LOWER(primary_role), LENGTH(job_role) FROM mv_root_data"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_order_by_with_direction(self, validator):
        """Test ORDER BY with ASC/DESC is allowed"""
        sql = "SELECT * FROM mv_root_data ORDER BY created_at DESC"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_group_by_having(self, validator):
        """Test GROUP BY with HAVING clause is allowed"""
        sql = "SELECT primary_role, COUNT(*) as count FROM mv_root_data GROUP BY primary_role HAVING COUNT(*) > 10"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    # ==================== SINGLETON TESTS ====================

    def test_get_sql_validator_singleton(self):
        """Test that get_sql_validator returns singleton"""
        validator1 = get_sql_validator()
        validator2 = get_sql_validator()
        assert validator1 is validator2


@pytest.mark.unit
class TestSQLValidatorExtracted:
    """Tests for internal extraction and parsing logic"""

    @pytest.fixture
    def validator(self):
        """Create a fresh SQL validator instance"""
        return SQLValidator()

    def test_extract_columns_simple(self, validator):
        """Test column extraction from simple query"""
        sql = "SELECT id, company_title FROM mv_root_data"
        columns = validator._extract_column_names(sql)
        assert "id" in columns
        assert "company_title" in columns

    def test_extract_columns_ignores_keywords(self, validator):
        """Test that SQL keywords are not extracted as columns"""
        sql = "SELECT COUNT(*) FROM mv_root_data WHERE id > 0"
        columns = validator._extract_column_names(sql)
        assert "count" not in columns
        assert "where" not in columns

    def test_extract_columns_from_where_clause(self, validator):
        """Test column extraction from WHERE clause"""
        sql = "SELECT * FROM mv_root_data WHERE min_salary_usd > 100000 AND is_remote = true"
        columns = validator._extract_column_names(sql)
        assert "min_salary_usd" in columns
        assert "is_remote" in columns

    def test_extract_columns_ignores_string_literals(self, validator):
        """Test that columns inside string literals are ignored"""
        sql = "SELECT * FROM mv_root_data WHERE job_role LIKE '%Engineer%'"
        columns = validator._extract_column_names(sql)
        # Engineer inside quotes should not be in columns
        assert "engineer" not in columns or len([c for c in columns if c == "engineer"]) == 0
