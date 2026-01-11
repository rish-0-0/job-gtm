from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
import json
import re

from app.database import get_db

router = APIRouter()


# ==================== FILTER SYSTEM ====================

class FilterCondition(BaseModel):
    """Single filter condition"""
    column: str
    operator: str
    value: Any
    logic: Optional[str] = None  # AND/OR - connects to next filter


class FilterGroup(BaseModel):
    """Group of filter conditions"""
    filters: List[FilterCondition]


# Valid operators for filtering
VALID_OPERATORS = {
    "=": "=",
    "!=": "!=",
    "<>": "<>",
    ">": ">",
    "<": "<",
    ">=": ">=",
    "<=": "<=",
    "LIKE": "LIKE",
    "ILIKE": "ILIKE",
    "NOT LIKE": "NOT LIKE",
    "NOT ILIKE": "NOT ILIKE",
    "IN": "IN",
    "NOT IN": "NOT IN",
    "IS NULL": "IS NULL",
    "IS NOT NULL": "IS NOT NULL",
    "BETWEEN": "BETWEEN",
}

# Column types for validation and UI hints
COLUMN_TYPES = {
    "id": "integer",
    "company_title": "text",
    "job_role": "text",
    "job_location_normalized": "text",
    "employment_type_normalized": "text",
    "min_salary_usd": "numeric",
    "max_salary_usd": "numeric",
    "seniority_level_normalized": "text",
    "is_remote": "boolean",
    "location_city": "text",
    "location_country": "text",
    "company_industry": "text",
    "company_size": "text",
    "primary_role": "text",
    "role_category": "text",
    "scraper_source": "text",
    "enrichment_status": "text",
    "created_at": "timestamp",
}


def parse_filters(filter_json: Optional[str]) -> tuple[str, Dict[str, Any]]:
    """
    Parse JSON filter string into SQL WHERE clause and parameters.

    Returns:
        tuple of (where_clause, params_dict)

    Example input:
    [
        {"column": "min_salary_usd", "operator": ">", "value": 100000, "logic": "AND"},
        {"column": "min_salary_usd", "operator": "<", "value": 150000, "logic": "AND"},
        {"column": "location_city", "operator": "ILIKE", "value": "%delhi%"}
    ]
    """
    if not filter_json:
        return "", {}

    try:
        filters = json.loads(filter_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid filter JSON: {str(e)}")

    if not isinstance(filters, list) or len(filters) == 0:
        return "", {}

    where_parts = []
    params = {}

    for i, f in enumerate(filters):
        # Validate column
        column = f.get("column", "").strip()
        if column not in COLUMN_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid column: {column}. Valid columns: {list(COLUMN_TYPES.keys())}"
            )

        # Validate operator
        operator = f.get("operator", "").strip().upper()
        if operator not in VALID_OPERATORS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid operator: {operator}. Valid operators: {list(VALID_OPERATORS.keys())}"
            )

        value = f.get("value")
        logic = f.get("logic", "").strip().upper() if f.get("logic") else None

        # Validate logic (only AND/OR allowed, and only if not last filter)
        if logic and logic not in ("AND", "OR"):
            raise HTTPException(status_code=400, detail=f"Invalid logic: {logic}. Use AND or OR.")

        param_name = f"p{i}"

        # Build condition based on operator
        if operator in ("IS NULL", "IS NOT NULL"):
            condition = f"{column} {operator}"
        elif operator == "BETWEEN":
            # Value should be [min, max]
            if not isinstance(value, list) or len(value) != 2:
                raise HTTPException(status_code=400, detail="BETWEEN requires [min, max] value")
            params[f"{param_name}_min"] = value[0]
            params[f"{param_name}_max"] = value[1]
            condition = f"{column} BETWEEN :{param_name}_min AND :{param_name}_max"
        elif operator in ("IN", "NOT IN"):
            # Value should be a list
            if not isinstance(value, list):
                raise HTTPException(status_code=400, detail=f"{operator} requires a list value")
            # Create individual parameters for each value
            in_params = []
            for j, v in enumerate(value):
                pname = f"{param_name}_{j}"
                params[pname] = v
                in_params.append(f":{pname}")
            condition = f"{column} {operator} ({', '.join(in_params)})"
        elif operator in ("LIKE", "ILIKE", "NOT LIKE", "NOT ILIKE"):
            params[param_name] = value
            condition = f"{column} {operator} :{param_name}"
        else:
            # Standard comparison operators
            params[param_name] = value
            condition = f"{column} {operator} :{param_name}"

        where_parts.append(condition)

        # Add logic connector if not last filter and logic is specified
        if logic and i < len(filters) - 1:
            where_parts.append(logic)

    if where_parts:
        # Clean up: remove trailing AND/OR if present
        while where_parts and where_parts[-1] in ("AND", "OR"):
            where_parts.pop()

        where_clause = "WHERE " + " ".join(where_parts)
        return where_clause, params

    return "", {}

# Valid columns for sorting to prevent SQL injection
VALID_SORT_COLUMNS = [
    "id",
    "company_title",
    "job_role",
    "job_location_normalized",
    "employment_type_normalized",
    "min_salary_usd",
    "max_salary_usd",
    "seniority_level_normalized",
    "is_remote",
    "location_city",
    "location_country",
    "company_industry",
    "company_size",
    "primary_role",
    "role_category",
    "scraper_source",
    "enrichment_status",
    "created_at",
]

# Columns that can be grouped by
GROUPABLE_COLUMNS = [
    "company_industry",
    "seniority_level_normalized",
    "location_country",
    "is_remote",
    "employment_type_normalized",
    "primary_role",
    "role_category",
    "scraper_source",
]


def build_sort_clause(sort_param: Optional[str]) -> str:
    """
    Parse 'col1:asc,col2:desc' into SQL ORDER BY clause.
    Returns 'ORDER BY id' if invalid or empty.
    """
    if not sort_param:
        return "ORDER BY id"

    clauses = []
    for part in sort_param.split(","):
        if ":" not in part:
            continue
        col, direction = part.split(":", 1)
        col = col.strip()
        direction = direction.strip().lower()
        if col in VALID_SORT_COLUMNS and direction in ("asc", "desc"):
            # Cast boolean columns to integer for proper sorting
            if col == "is_remote":
                clauses.append(f"({col}::int) {direction.upper()}")
            else:
                clauses.append(f"{col} {direction.upper()}")

    return f"ORDER BY {', '.join(clauses)}" if clauses else "ORDER BY id"


def parse_group_by(group_by_param: Optional[str]) -> List[str]:
    """
    Parse comma-separated group by columns.
    Returns list of valid column names.
    """
    if not group_by_param:
        return []

    groups = []
    for col in group_by_param.split(","):
        col = col.strip()
        if col in GROUPABLE_COLUMNS:
            groups.append(col)

    return groups


# All columns available in mv_root_data
ALL_COLUMNS = [
    "id",
    "company_title",
    "job_role",
    "job_location_normalized",
    "employment_type_normalized",
    "min_salary_usd",
    "max_salary_usd",
    "seniority_level_normalized",
    "is_remote",
    "location_city",
    "location_country",
    "company_industry",
    "company_size",
    "primary_role",
    "role_category",
    "scraper_source",
    "enrichment_status",
    "created_at",
]


@router.get("/root-data/columns")
def get_root_data_columns():
    """
    Get column metadata for mv_root_data view.

    Returns column names, types, and valid operators for each type.
    Used by the UI to build filter dropdowns.
    """
    # Operators by column type
    operators_by_type = {
        "integer": ["=", "!=", ">", "<", ">=", "<=", "BETWEEN", "IN", "NOT IN", "IS NULL", "IS NOT NULL"],
        "numeric": ["=", "!=", ">", "<", ">=", "<=", "BETWEEN", "IN", "NOT IN", "IS NULL", "IS NOT NULL"],
        "text": ["=", "!=", "LIKE", "ILIKE", "NOT LIKE", "NOT ILIKE", "IN", "NOT IN", "IS NULL", "IS NOT NULL"],
        "boolean": ["=", "IS NULL", "IS NOT NULL"],
        "timestamp": ["=", "!=", ">", "<", ">=", "<=", "BETWEEN", "IS NULL", "IS NOT NULL"],
    }

    columns = []
    for col, col_type in COLUMN_TYPES.items():
        columns.append({
            "name": col,
            "type": col_type,
            "operators": operators_by_type.get(col_type, ["="]),
            "sortable": col in VALID_SORT_COLUMNS,
            "groupable": col in GROUPABLE_COLUMNS,
        })

    return {
        "columns": columns,
        "view_name": "mv_root_data",
        "valid_logic": ["AND", "OR"],
    }


@router.get("/root-data")
def get_root_data(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    sort: Optional[str] = Query(None, description="Sort columns: col1:asc,col2:desc"),
    group_by: Optional[str] = Query(None, description="Group by columns: col1,col2"),
    filters: Optional[str] = Query(None, description="JSON array of filter conditions"),
    db: Session = Depends(get_db),
):
    """
    Get paginated data from the mv_root_data materialized view.

    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)
    - sort: Comma-separated sort columns with direction (e.g., "company_title:asc,min_salary_usd:desc")
    - group_by: Comma-separated columns to group by (e.g., "company_industry,seniority_level_normalized")
    - filters: JSON array of filter conditions. Example:
      [
        {"column": "min_salary_usd", "operator": ">", "value": 100000, "logic": "AND"},
        {"column": "location_city", "operator": "ILIKE", "value": "%delhi%"}
      ]

    When group_by is specified, only the grouped columns are returned.
    """
    offset = (page - 1) * page_size

    # Parse filters
    where_clause, filter_params = parse_filters(filters)

    # Parse group_by params
    group_columns = parse_group_by(group_by)

    if group_columns:
        # GROUP BY mode: only return grouped columns
        columns_sql = ", ".join(group_columns)
        group_by_sql = ", ".join(group_columns)

        # Count distinct groups (with filters)
        count_query = text(f"""
            SELECT COUNT(*) FROM (
                SELECT {columns_sql}
                FROM mv_root_data
                {where_clause}
                GROUP BY {group_by_sql}
            ) subq
        """)
        count_result = db.execute(count_query, filter_params)
        total = count_result.scalar()

        # Build ORDER BY for grouped query
        order_parts = []
        for col in group_columns:
            order_parts.append(f"{col} ASC NULLS LAST")
        order_clause = f"ORDER BY {', '.join(order_parts)}"

        # Fetch grouped data (with filters)
        query = text(f"""
            SELECT {columns_sql}
            FROM mv_root_data
            {where_clause}
            GROUP BY {group_by_sql}
            {order_clause}
            LIMIT :limit OFFSET :offset
        """)

        query_params = {"limit": page_size, "offset": offset, **filter_params}
        result = db.execute(query, query_params)
        rows = result.fetchall()

        # Convert to list of dicts using only group columns
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(group_columns):
                value = row[i]
                row_dict[col] = value
            data.append(row_dict)

        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
            "columns": group_columns,
            "grouped": True,
            "filters_applied": filters is not None,
        }

    else:
        # Normal mode: return all columns
        order_clause = build_sort_clause(sort)

        # Get total count (with filters)
        count_query = f"SELECT COUNT(*) FROM mv_root_data {where_clause}"
        count_result = db.execute(text(count_query), filter_params)
        total = count_result.scalar()

        columns_sql = ", ".join(ALL_COLUMNS)
        query = text(f"""
            SELECT {columns_sql}
            FROM mv_root_data
            {where_clause}
            {order_clause}
            LIMIT :limit OFFSET :offset
        """)

        query_params = {"limit": page_size, "offset": offset, **filter_params}
        result = db.execute(query, query_params)
        rows = result.fetchall()

        # Convert to list of dicts
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(ALL_COLUMNS):
                value = row[i]
                # Handle special types
                if col == "created_at" and value:
                    value = value.isoformat()
                elif col in ("min_salary_usd", "max_salary_usd") and value:
                    value = float(value)
                row_dict[col] = value
            data.append(row_dict)

        return {
            "data": data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
            "columns": ALL_COLUMNS,
            "grouped": False,
            "filters_applied": filters is not None,
        }


@router.get("/root-data/charts/salary-by-location")
def get_salary_by_location(
    limit: int = Query(15, ge=1, le=50, description="Number of locations to return"),
    db: Session = Depends(get_db),
):
    """
    Get average minimum salary grouped by job location.
    Returns top locations by average salary for chart visualization.
    """
    query = text("""
        SELECT
            job_location_normalized,
            ROUND(AVG(min_salary_usd)::numeric, 0) as avg_min_salary,
            ROUND(AVG(max_salary_usd)::numeric, 0) as avg_max_salary,
            COUNT(*) as job_count
        FROM mv_root_data
        WHERE min_salary_usd IS NOT NULL
          AND min_salary_usd > 0
          AND job_location_normalized IS NOT NULL
          AND job_location_normalized != ''
        GROUP BY job_location_normalized
        HAVING COUNT(*) >= 5
        ORDER BY AVG(min_salary_usd) DESC
        LIMIT :limit
    """)

    result = db.execute(query, {"limit": limit})
    rows = result.fetchall()

    data = []
    for row in rows:
        data.append({
            "location": row.job_location_normalized,
            "avgMinSalary": int(row.avg_min_salary) if row.avg_min_salary else 0,
            "avgMaxSalary": int(row.avg_max_salary) if row.avg_max_salary else 0,
            "jobCount": row.job_count,
        })

    return {
        "data": data,
        "metric": "avg_min_salary",
        "groupBy": "job_location_normalized",
    }
