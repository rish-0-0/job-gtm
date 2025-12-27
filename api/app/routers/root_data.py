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
    """
    offset = (page - 1) * page_size

    # Parse sort and group_by params
    order_clause = build_sort_clause(sort)
    group_columns = parse_group_by(group_by)

    # Get total count
    count_result = db.execute(text("SELECT COUNT(*) FROM mv_root_data"))
    total = count_result.scalar()

    # Build the query with dynamic ORDER BY
    # If grouping, we order by group columns first, then by the user's sort
    if group_columns:
        group_order = ", ".join(group_columns)
        if order_clause != "ORDER BY id":
            # Combine group columns with user sort
            user_sort = order_clause.replace("ORDER BY ", "")
            final_order = f"ORDER BY {group_order}, {user_sort}"
        else:
            final_order = f"ORDER BY {group_order}, id"
    else:
        final_order = order_clause

    query = text(f"""
        SELECT
            id,
            company_title,
            job_role,
            job_location_normalized,
            employment_type_normalized,
            min_salary_usd,
            max_salary_usd,
            seniority_level_normalized,
            is_remote,
            location_city,
            location_country,
            company_industry,
            company_size,
            primary_role,
            role_category,
            scraper_source,
            enrichment_status,
            created_at
        FROM mv_root_data
        {final_order}
        LIMIT :limit OFFSET :offset
    """)

    result = db.execute(query, {"limit": page_size, "offset": offset})
    rows = result.fetchall()

    # Convert to list of dicts
    columns = [
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

    data = []
    for row in rows:
        row_dict = {}
        for i, col in enumerate(columns):
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
    }
