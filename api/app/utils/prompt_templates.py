"""
Prompt templates for text-to-SQL generation
Includes schema context and few-shot examples
"""
from typing import Dict, Any, List


def get_schema_context() -> Dict[str, Any]:
    """
    Get database schema context for text-to-SQL generation

    Returns:
        Dictionary with table schema and query examples
    """
    return {
        "table": "mv_root_data",
        "description": "Materialized view of enriched job listings (read-only, already filtered for completed enrichments)",
        "columns": [
            {
                "name": "id",
                "type": "INTEGER",
                "description": "Unique job listing ID"
            },
            {
                "name": "company_title",
                "type": "VARCHAR(255)",
                "description": "Company name"
            },
            {
                "name": "job_role",
                "type": "VARCHAR(255)",
                "description": "Job title/role"
            },
            {
                "name": "job_location_normalized",
                "type": "VARCHAR(255)",
                "description": "Normalized location string"
            },
            {
                "name": "employment_type_normalized",
                "type": "VARCHAR(100)",
                "description": "Employment type",
                "allowed_values": ["Full-time", "Part-time", "Contract", "Internship", "Temporary", "Freelance"]
            },
            {
                "name": "min_salary_usd",
                "type": "NUMERIC(10,2)",
                "description": "Minimum salary in USD (normalized)"
            },
            {
                "name": "max_salary_usd",
                "type": "NUMERIC(10,2)",
                "description": "Maximum salary in USD (normalized)"
            },
            {
                "name": "seniority_level_normalized",
                "type": "VARCHAR(50)",
                "description": "Job seniority level",
                "allowed_values": ["Entry", "Junior", "Mid", "Senior", "Lead", "Principal", "Staff", "Executive"]
            },
            {
                "name": "is_remote",
                "type": "BOOLEAN",
                "description": "Whether job is remote (true/false)"
            },
            {
                "name": "location_city",
                "type": "VARCHAR(100)",
                "description": "City location"
            },
            {
                "name": "location_country",
                "type": "VARCHAR(100)",
                "description": "Country name"
            },
            {
                "name": "company_industry",
                "type": "VARCHAR(100)",
                "description": "Industry sector",
                "examples": ["Technology", "Finance", "Healthcare", "E-commerce"]
            },
            {
                "name": "company_size",
                "type": "VARCHAR(100)",
                "description": "Company size range",
                "allowed_values": ["Startup (1-50)", "Small (51-200)", "Medium (201-1000)", "Large (1001-5000)", "Enterprise (5000+)"]
            },
            {
                "name": "primary_role",
                "type": "VARCHAR(100)",
                "description": "Primary role category",
                "examples": ["Software Engineer", "Data Scientist", "Product Manager"]
            },
            {
                "name": "role_category",
                "type": "VARCHAR(100)",
                "description": "Broader role category",
                "allowed_values": ["Engineering", "Product", "Design", "Data", "Management", "Operations", "Security"]
            },
            {
                "name": "scraper_source",
                "type": "VARCHAR(100)",
                "description": "Source of job listing",
                "examples": ["dice", "simplyhired", "ziprecruiter"]
            },
            {
                "name": "enrichment_status",
                "type": "VARCHAR(50)",
                "description": "Always 'completed' in this view"
            },
            {
                "name": "created_at",
                "type": "TIMESTAMP",
                "description": "When job was created"
            }
        ],
        "examples": [
            {
                "query": "Show me senior software engineer jobs in USA paying over 150k",
                "sql": "SELECT * FROM mv_root_data WHERE seniority_level_normalized = 'Senior' AND primary_role LIKE '%Software Engineer%' AND location_country = 'USA' AND min_salary_usd > 150000 LIMIT 100"
            },
            {
                "query": "Find remote jobs",
                "sql": "SELECT * FROM mv_root_data WHERE is_remote = true LIMIT 100"
            },
            {
                "query": "What's the average salary for data scientists by country?",
                "sql": "SELECT location_country, AVG(min_salary_usd) as avg_min_salary, AVG(max_salary_usd) as avg_max_salary, COUNT(*) as job_count FROM mv_root_data WHERE primary_role LIKE '%Data Scientist%' AND min_salary_usd IS NOT NULL GROUP BY location_country ORDER BY avg_min_salary DESC LIMIT 100"
            },
            {
                "query": "List all engineering jobs in technology companies",
                "sql": "SELECT company_title, job_role, location_city, min_salary_usd, max_salary_usd FROM mv_root_data WHERE role_category = 'Engineering' AND company_industry = 'Technology' LIMIT 100"
            },
            {
                "query": "Count jobs by seniority level",
                "sql": "SELECT seniority_level_normalized, COUNT(*) as job_count FROM mv_root_data GROUP BY seniority_level_normalized ORDER BY job_count DESC LIMIT 100"
            },
            {
                "query": "Show highest paying jobs by company",
                "sql": "SELECT company_title, job_role, location_country, max_salary_usd FROM mv_root_data WHERE max_salary_usd IS NOT NULL ORDER BY max_salary_usd DESC LIMIT 100"
            },
            {
                "query": "Find entry-level jobs posted recently",
                "sql": "SELECT * FROM mv_root_data WHERE seniority_level_normalized = 'Entry' ORDER BY created_at DESC LIMIT 100"
            }
        ]
    }


def build_text_to_sql_prompt(natural_query: str, schema_context: Dict[str, Any]) -> str:
    """
    Build comprehensive prompt for text-to-SQL generation

    Args:
        natural_query: User's natural language question
        schema_context: Database schema context from get_schema_context()

    Returns:
        Formatted prompt string
    """
    # Format columns section
    columns_text = []
    for col in schema_context["columns"]:
        col_desc = f"  - {col['name']} ({col['type']}): {col['description']}"
        if "allowed_values" in col:
            col_desc += f"\n    Values: {', '.join(col['allowed_values'])}"
        if "query_pattern" in col:
            col_desc += f"\n    Query: {col['query_pattern']}"
        if "note" in col:
            col_desc += f"\n    Note: {col['note']}"
        columns_text.append(col_desc)

    # Format examples section
    examples_text = []
    for i, ex in enumerate(schema_context["examples"], 1):
        examples_text.append(f"{i}. Query: \"{ex['query']}\"\n   SQL: {ex['sql']}")

    prompt = f"""You are a PostgreSQL SQL expert. Convert natural language questions to SQL queries.

TARGET TABLE: {schema_context['table']}
DESCRIPTION: {schema_context['description']}

AVAILABLE COLUMNS:
{chr(10).join(columns_text)}

CRITICAL RULES:
1. Generate ONLY valid PostgreSQL SELECT statements
2. Query ONLY from {schema_context['table']} table (this is a materialized view)
3. Use ONLY the 18 columns listed above - NO other tables or columns allowed
4. LIMIT results to 100 rows by default (unless user specifies otherwise)
5. For salary queries: filter out NULL values with "WHERE min_salary_usd IS NOT NULL"
6. For aggregations: Always include COUNT(*) or relevant aggregate function
7. For GROUP BY: Include grouped column in SELECT clause
8. NEVER use DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, or any DDL/DML
9. NEVER reference job_listings_golden or any other table - ONLY mv_root_data
10. The view already filters for completed enrichments - no need to filter enrichment_status
11. Return valid JSON with structure: {{"sql": "SELECT ...", "confidence": 0.95}}

FEW-SHOT EXAMPLES:
{chr(10).join(examples_text)}

USER QUESTION:
{natural_query}

Generate SQL that answers the user's question. Return ONLY JSON in the format:
{{"sql": "SELECT ...", "confidence": 0.95}}
"""
    return prompt


def build_chatgpt_messages(natural_query: str, schema_context: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Build message array for ChatGPT API

    Args:
        natural_query: User's natural language question
        schema_context: Database schema context

    Returns:
        List of message dictionaries for ChatGPT
    """
    system_prompt = build_text_to_sql_prompt("", schema_context).replace(
        f"\n\nUSER QUESTION:\n\n\nGenerate SQL", "\n\nGenerate SQL"
    )

    return [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": natural_query
        }
    ]


def build_claude_system_prompt(schema_context: Dict[str, Any]) -> str:
    """
    Build system prompt for Claude API

    Args:
        schema_context: Database schema context

    Returns:
        System prompt string
    """
    return build_text_to_sql_prompt("", schema_context).replace(
        f"\n\nUSER QUESTION:\n\n\nGenerate SQL", "\n\nGenerate SQL"
    )
