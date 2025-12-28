from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Any

from app.database import get_db

router = APIRouter()

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


@router.get("/root-data")
def get_root_data(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    sort: Optional[str] = Query(None, description="Sort columns: col1:asc,col2:desc"),
    group_by: Optional[str] = Query(None, description="Group by columns: col1,col2"),
    db: Session = Depends(get_db),
):
    """
    Get paginated data from the mv_root_data materialized view.

    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 500)
    - sort: Comma-separated sort columns with direction (e.g., "company_title:asc,min_salary_usd:desc")
    - group_by: Comma-separated columns to group by (e.g., "company_industry,seniority_level_normalized")

    When group_by is specified, only the grouped columns are returned.
    """
    offset = (page - 1) * page_size

    # Parse group_by params
    group_columns = parse_group_by(group_by)

    if group_columns:
        # GROUP BY mode: only return grouped columns
        columns_sql = ", ".join(group_columns)
        group_by_sql = ", ".join(group_columns)

        # Count distinct groups
        count_query = text(f"""
            SELECT COUNT(*) FROM (
                SELECT {columns_sql}
                FROM mv_root_data
                GROUP BY {group_by_sql}
            ) subq
        """)
        count_result = db.execute(count_query)
        total = count_result.scalar()

        # Build ORDER BY for grouped query
        order_parts = []
        for col in group_columns:
            order_parts.append(f"{col} ASC NULLS LAST")
        order_clause = f"ORDER BY {', '.join(order_parts)}"

        # Fetch grouped data
        query = text(f"""
            SELECT {columns_sql}
            FROM mv_root_data
            GROUP BY {group_by_sql}
            {order_clause}
            LIMIT :limit OFFSET :offset
        """)

        result = db.execute(query, {"limit": page_size, "offset": offset})
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
        }

    else:
        # Normal mode: return all columns
        order_clause = build_sort_clause(sort)

        # Get total count
        count_result = db.execute(text("SELECT COUNT(*) FROM mv_root_data"))
        total = count_result.scalar()

        columns_sql = ", ".join(ALL_COLUMNS)
        query = text(f"""
            SELECT {columns_sql}
            FROM mv_root_data
            {order_clause}
            LIMIT :limit OFFSET :offset
        """)

        result = db.execute(query, {"limit": page_size, "offset": offset})
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
        }


@router.get("/root-data/charts/salary-by-location")
def get_salary_by_location(
    limit: int = Query(15, ge=1, le=50, description="Number of locations to return"),
    db: Session = Depends(get_db),
):
    """
    Get average minimum salary grouped by location country.
    Returns top locations by average salary for chart visualization.
    """
    query = text("""
        SELECT
            location_country,
            ROUND(AVG(min_salary_usd)::numeric, 0) as avg_min_salary,
            ROUND(AVG(max_salary_usd)::numeric, 0) as avg_max_salary,
            COUNT(*) as job_count
        FROM mv_root_data
        WHERE min_salary_usd IS NOT NULL
          AND min_salary_usd > 0
          AND location_country IS NOT NULL
          AND location_country != ''
        GROUP BY location_country
        HAVING COUNT(*) >= 5
        ORDER BY AVG(min_salary_usd) DESC
        LIMIT :limit
    """)

    result = db.execute(query, {"limit": limit})
    rows = result.fetchall()

    data = []
    for row in rows:
        data.append({
            "location": row.location_country,
            "avgMinSalary": int(row.avg_min_salary) if row.avg_min_salary else 0,
            "avgMaxSalary": int(row.avg_max_salary) if row.avg_max_salary else 0,
            "jobCount": row.job_count,
        })

    return {
        "data": data,
        "metric": "avg_min_salary",
        "groupBy": "location_country",
    }
