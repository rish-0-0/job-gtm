"""
SQL Validator for text-to-SQL feature
Ensures generated SQL is safe and follows security best practices
"""
import logging
import re
from typing import Tuple, Set

logger = logging.getLogger(__name__)


class SQLValidator:
    """
    Validates generated SQL queries for safety and correctness
    Prevents SQL injection, DDL/DML operations, and ensures read-only queries
    """

    # Whitelist of allowed SQL keywords
    ALLOWED_KEYWORDS: Set[str] = {
        'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'ILIKE',
        'BETWEEN', 'IS', 'NULL', 'ORDER', 'BY', 'LIMIT', 'OFFSET', 'ASC', 'DESC',
        'COUNT', 'AVG', 'SUM', 'MIN', 'MAX', 'GROUP', 'HAVING', 'DISTINCT',
        'JOIN', 'LEFT', 'RIGHT', 'INNER', 'ON', 'AS', 'COALESCE', 'CASE', 'WHEN',
        'THEN', 'ELSE', 'END', 'CAST', 'EXTRACT', 'DATE_PART', 'INTERVAL',
        # JSONB operators
        'JSONB_ARRAY_ELEMENTS', 'JSONB_EACH', 'JSONB_EXISTS', 'JSONB_TYPEOF',
        # String functions
        'UPPER', 'LOWER', 'TRIM', 'SUBSTRING', 'LENGTH', 'CONCAT',
        # Math functions
        'ROUND', 'FLOOR', 'CEIL', 'ABS',
        # Boolean
        'TRUE', 'FALSE',
    }

    # Blacklist of dangerous keywords/patterns
    DANGEROUS_KEYWORDS: Set[str] = {
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE',
        'GRANT', 'REVOKE', 'EXECUTE', 'EXEC', 'CALL', 'PROCEDURE', 'FUNCTION',
        'TRIGGER', 'INDEX', 'VIEW', 'SCHEMA', 'DATABASE', 'TABLE',
        # SQL injection patterns
        'xp_', 'sp_', 'UTL_', 'DBMS_',
        # Comments
        '--', '/*', '*/',
    }

    # Allowed table - ONLY mv_root_data materialized view
    ALLOWED_TABLE = "mv_root_data"

    # Whitelisted queryable columns from mv_root_data (18 columns total)
    # This is the ONLY table accessible for text-to-SQL queries
    VALID_COLUMNS: Set[str] = {
        'id',
        'company_title',
        'job_role',
        'job_location_normalized',
        'employment_type_normalized',
        'min_salary_usd',
        'max_salary_usd',
        'seniority_level_normalized',
        'is_remote',
        'location_city',
        'location_country',
        'company_industry',
        'company_size',
        'primary_role',
        'role_category',
        'scraper_source',
        'enrichment_status',
        'created_at'
    }

    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        Validate SQL query for safety

        Args:
            sql: SQL query string to validate

        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message is empty string
        """
        sql_upper = sql.upper()

        logger.debug(f"[SQLValidator] Validating SQL: {sql[:100]}...")

        # 1. Check for dangerous keywords
        for keyword in self.DANGEROUS_KEYWORDS:
            if keyword in sql_upper:
                logger.warning(f"[SQLValidator] Dangerous keyword detected: {keyword}")
                return False, f"Dangerous keyword detected: {keyword}"

        # 2. Must start with SELECT
        if not sql_upper.strip().startswith('SELECT'):
            logger.warning(f"[SQLValidator] Query must start with SELECT")
            return False, "Query must be a SELECT statement"

        # 3. Must reference allowed table
        if self.ALLOWED_TABLE not in sql.lower():
            logger.warning(f"[SQLValidator] Query must reference table: {self.ALLOWED_TABLE}")
            return False, f"Query must reference table: {self.ALLOWED_TABLE}"

        # 4. Check for multiple statements (SQL injection via semicolon)
        sql_clean = sql.rstrip(';').strip()
        if ';' in sql_clean:
            logger.warning(f"[SQLValidator] Multiple statements not allowed")
            return False, "Multiple statements not allowed (SQL injection risk)"

        # 5. Check for comment injection
        if '--' in sql or '/*' in sql or '*/' in sql:
            logger.warning(f"[SQLValidator] SQL comments not allowed")
            return False, "SQL comments not allowed (SQL injection risk)"

        # 6. Validate column names against whitelist
        columns = self._extract_column_names(sql)
        invalid_cols = [c for c in columns if c not in self.VALID_COLUMNS and c not in ('*',)]
        if invalid_cols:
            logger.warning(f"[SQLValidator] Invalid columns: {invalid_cols}")
            return False, f"Invalid columns: {', '.join(invalid_cols[:5])}"

        # 7. Check for stacked queries (union injection)
        if re.search(r'\bUNION\s+SELECT\b', sql_upper):
            # UNION is allowed but check if it's suspicious
            if sql_upper.count('SELECT') > 2:
                logger.warning(f"[SQLValidator] Suspicious UNION query with multiple SELECTs")
                return False, "Suspicious UNION query pattern detected"

        # 8. Validate parentheses are balanced
        if sql.count('(') != sql.count(')'):
            logger.warning(f"[SQLValidator] Unbalanced parentheses")
            return False, "Unbalanced parentheses in SQL query"

        logger.info(f"[SQLValidator] SQL validation passed")
        return True, ""

    def sanitize(self, sql: str) -> str:
        """
        Add safety constraints to SQL query

        Args:
            sql: SQL query to sanitize

        Returns:
            Sanitized SQL query
        """
        sql = sql.strip().rstrip(';')

        logger.debug(f"[SQLValidator] Sanitizing SQL...")

        # Note: mv_root_data already filters WHERE enrichment_status = 'completed'
        # No need to add it again in queries

        # Add LIMIT if not present
        if 'LIMIT' not in sql.upper():
            sql += " LIMIT 100"

        logger.debug(f"[SQLValidator] Sanitized SQL: {sql[:100]}...")
        return sql

    def _extract_column_names(self, sql: str) -> Set[str]:
        """
        Extract column names from SQL query for validation

        Args:
            sql: SQL query

        Returns:
            Set of column names found
        """
        # Remove string literals first to avoid extracting them as column names
        # Match both single and double quoted strings
        sql_no_strings = re.sub(r"'[^']*'", '', sql)
        sql_no_strings = re.sub(r'"[^"]*"', '', sql_no_strings)

        # Remove ORDER BY clause (can reference aliases)
        sql_no_order = re.sub(r'\bORDER\s+BY\s+[^;]+?(?=\s*(?:LIMIT|OFFSET|$))', '', sql_no_strings, flags=re.IGNORECASE)

        # Remove GROUP BY clause
        sql_no_group = re.sub(r'\bGROUP\s+BY\s+[^;]+?(?=\s*(?:HAVING|ORDER|LIMIT|OFFSET|$))', '', sql_no_order, flags=re.IGNORECASE)

        # Remove HAVING clause
        sql_no_having = re.sub(r'\bHAVING\s+[^;]+?(?=\s*(?:ORDER|LIMIT|OFFSET|$))', '', sql_no_group, flags=re.IGNORECASE)

        # Remove aliases (everything after AS keyword until comma or end of clause)
        # This prevents false positives like "COUNT(*) as job_count" triggering "job_count" validation
        sql_no_aliases = re.sub(r'\bAS\s+[a-z_][a-z0-9_]*', '', sql_no_having, flags=re.IGNORECASE)

        # Simple regex to extract column names (not perfect but good enough)
        # Matches patterns like: column_name, table.column_name
        pattern = r'\b([a-z_][a-z0-9_]*)\b'
        matches = re.findall(pattern, sql_no_aliases.lower())

        # Filter out SQL keywords
        keywords_lower = {k.lower() for k in self.ALLOWED_KEYWORDS}
        columns = {m for m in matches if m not in keywords_lower and m != self.ALLOWED_TABLE.lower()}

        logger.debug(f"[SQLValidator] Extracted columns: {columns}")
        return columns


# Singleton instance
_sql_validator = None


def get_sql_validator() -> SQLValidator:
    """
    Get singleton SQL validator instance

    Returns:
        SQLValidator instance
    """
    global _sql_validator
    if _sql_validator is None:
        _sql_validator = SQLValidator()
    return _sql_validator
