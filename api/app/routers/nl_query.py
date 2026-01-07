"""
Natural Language Query Router
Text-to-SQL API endpoints for converting natural language to SQL
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.config import NL_QUERY_SIMILARITY_THRESHOLD
from app.services.llm_router import get_llm_router
from app.services.llm_provider import LLMProviderError, LLMTimeoutError
from app.services.sql_validator import get_sql_validator
from app.services.embedding_service import get_embedding_service
from app.utils.redis_client import get_redis_client
from app.utils.prompt_templates import get_schema_context

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class NLQueryRequest(BaseModel):
    """Request model for natural language query"""
    query: str
    llm_provider: str = "ollama"  # ollama | chatgpt | claude
    force_regenerate: bool = False  # Skip cache

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query length and detect prompt injection"""
        # Character limit validation
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Query must be at least 5 characters")
        if len(v) > 500:
            raise ValueError("Query must be at most 500 characters")

        # Prompt injection detection (basic patterns)
        dangerous_patterns = [
            r"ignore\s+previous\s+instructions",
            r"disregard\s+.*\s+instructions",
            r"system\s*:\s*you\s+are",
            r"<\|.*\|>",  # Special tokens
            r"#{3,}",  # Multiple hashes (markdown injection)
            r"forget\s+everything",
            r"new\s+instructions",
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                logger.warning(f"[NLQuery] Prompt injection attempt: {v[:100]}")
                raise ValueError("Potentially unsafe query detected. Please rephrase.")

        return v

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate LLM provider"""
        v = v.lower()
        if v not in ["ollama", "chatgpt", "claude"]:
            raise ValueError("Invalid LLM provider. Must be: ollama, chatgpt, or claude")
        return v


class NLQueryResponse(BaseModel):
    """Response model for natural language query"""
    sql: str
    cache_hit: bool
    llm_provider: str
    similarity_score: Optional[float] = None
    execution_count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/generate", response_model=NLQueryResponse)
async def generate_sql(
    request: NLQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Generate SQL from natural language query

    This endpoint converts natural language questions about job listings
    into valid SQL queries. It uses a two-tier caching strategy and supports
    multiple LLM providers.

    Flow:
    1. Check Redis cache (exact match)
    2. Check PostgreSQL with pgvector similarity
    3. Generate new SQL using LLM
    4. Validate SQL for safety
    5. Store in cache

    Args:
        request: Natural language query request
        db: Database session

    Returns:
        NLQueryResponse with generated SQL and metadata

    Raises:
        HTTPException: On validation or generation errors
    """
    try:
        logger.info(f"[NLQuery] ========== START PROCESSING ==========")
        logger.info(f"[NLQuery] Query: {request.query}")
        logger.info(f"[NLQuery] Provider: {request.llm_provider}, Force regenerate: {request.force_regenerate}")

        # Generate query hash for caching
        query_hash = hashlib.sha256(request.query.encode()).hexdigest()
        logger.info(f"[NLQuery] Query hash: {query_hash}")

        # Step 1: Check Redis cache (exact match) if not forcing regeneration
        if not request.force_regenerate:
            logger.info(f"[NLQuery] Step 1: Checking Redis cache...")
            cache_result = await _check_redis_cache(query_hash)
            if cache_result:
                logger.info(f"[NLQuery] ✓ Redis cache HIT - returning cached result")
                return NLQueryResponse(
                    sql=cache_result["sql"],
                    cache_hit=True,
                    llm_provider=cache_result["llm_provider"],
                    execution_count=cache_result.get("execution_count"),
                    metadata=cache_result.get("metadata")
                )
            logger.info(f"[NLQuery] ✗ Redis cache MISS")

        # Step 2: Check PostgreSQL with similarity search
        if not request.force_regenerate:
            logger.info(f"[NLQuery] Step 2: Checking similarity cache...")
            logger.info(f"[NLQuery] Generating embedding for query...")
            embedding = get_embedding_service().encode(request.query)
            logger.info(f"[NLQuery] Embedding generated, searching similar queries...")
            similarity_result = await _check_similarity_cache(db, embedding)

            if similarity_result:
                logger.info(
                    f"[NLQuery] ✓ Similarity cache HIT "
                    f"(score: {similarity_result['similarity_score']:.3f})"
                )

                # Store in Redis for future exact matches
                await _store_in_redis(query_hash, similarity_result)

                return NLQueryResponse(
                    sql=similarity_result["sql"],
                    cache_hit=True,
                    llm_provider=similarity_result["llm_provider"],
                    similarity_score=similarity_result["similarity_score"],
                    execution_count=similarity_result.get("execution_count"),
                    metadata=similarity_result.get("metadata")
                )
            logger.info(f"[NLQuery] ✗ Similarity cache MISS")

        # Step 3: Generate new SQL using LLM
        logger.info(f"[NLQuery] Step 3: Generating SQL with LLM ({request.llm_provider})...")
        sql_result = await _generate_sql_with_llm(request.query, request.llm_provider)
        logger.info(f"[NLQuery] ✓ LLM generation complete")
        logger.info(f"[NLQuery] Generated SQL: {sql_result['sql']}")

        # Step 4: Validate SQL
        logger.info(f"[NLQuery] Step 4: Validating generated SQL...")
        validator = get_sql_validator()
        is_valid, error_msg = validator.validate(sql_result["sql"])

        if not is_valid:
            logger.warning(f"[NLQuery] ✗ SQL validation FAILED: {error_msg}")
            logger.warning(f"[NLQuery] Invalid SQL: {sql_result['sql']}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Generated SQL failed validation",
                    "reason": error_msg,
                    "suggestion": "Try rephrasing your question"
                }
            )

        logger.info(f"[NLQuery] ✓ SQL validation PASSED")

        # Sanitize SQL (add safety constraints)
        logger.info(f"[NLQuery] Sanitizing SQL...")
        sql_result["sql"] = validator.sanitize(sql_result["sql"])
        logger.info(f"[NLQuery] ✓ SQL sanitized: {sql_result['sql']}")

        # Step 5: Store in cache
        logger.info(f"[NLQuery] Step 5: Storing in cache...")
        embedding = get_embedding_service().encode(request.query)
        await _store_in_cache(
            db=db,
            query_text=request.query,
            query_hash=query_hash,
            embedding=embedding,
            sql=sql_result["sql"],
            llm_provider=request.llm_provider,
            llm_model=sql_result["model"],
            metadata=sql_result.get("metadata", {})
        )
        logger.info(f"[NLQuery] ✓ Cached successfully")

        logger.info(f"[NLQuery] ========== COMPLETE ==========")
        return NLQueryResponse(
            sql=sql_result["sql"],
            cache_hit=False,
            llm_provider=request.llm_provider,
            metadata=sql_result.get("metadata")
        )

    except HTTPException:
        raise
    except LLMTimeoutError as e:
        logger.error(f"[NLQuery] LLM timeout: {e}")
        raise HTTPException(
            status_code=504,
            detail=f"LLM request timed out: {str(e)}"
        )
    except LLMProviderError as e:
        logger.error(f"[NLQuery] LLM provider error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"[NLQuery] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/providers")
async def get_available_providers():
    """
    Get list of available LLM providers

    Returns:
        Dict with provider availability status
    """
    router = get_llm_router()
    providers = router.get_available_providers()

    return {
        "providers": [
            {
                "name": name,
                "available": available,
                "display_name": name.title()
            }
            for name, available in providers.items()
        ]
    }


# Helper functions
async def _check_redis_cache(query_hash: str) -> Optional[Dict[str, Any]]:
    """Check Redis cache for exact match"""
    try:
        redis = await get_redis_client()
        cached = await redis.get(f"nlquery:{query_hash}")
        if cached:
            # Increment execution count
            if "execution_count" in cached:
                cached["execution_count"] += 1
            return cached
        return None
    except Exception as e:
        logger.warning(f"[NLQuery] Redis cache check failed: {e}")
        return None


async def _check_similarity_cache(
    db: Session,
    embedding: list
) -> Optional[Dict[str, Any]]:
    """Check PostgreSQL for similar queries using pgvector"""
    try:
        # Format embedding as PostgreSQL array
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Use string formatting for vector type casting (can't use bind params with ::vector)
        query = text(f"""
            SELECT
                query_text,
                generated_sql,
                llm_provider,
                llm_model,
                execution_count,
                metadata,
                1 - (query_embedding <=> '{embedding_str}'::vector) as similarity
            FROM nl_query_cache
            WHERE validated = true
            ORDER BY query_embedding <=> '{embedding_str}'::vector
            LIMIT 1
        """)

        result = db.execute(query)
        row = result.fetchone()

        if row and row.similarity >= NL_QUERY_SIMILARITY_THRESHOLD:
            # Update execution count and last_used_at
            update = text("""
                UPDATE nl_query_cache
                SET execution_count = execution_count + 1,
                    last_used_at = NOW()
                WHERE query_text = :query
            """)
            db.execute(update, {"query": row.query_text})
            db.commit()

            return {
                "sql": row.generated_sql,
                "llm_provider": row.llm_provider,
                "similarity_score": float(row.similarity),
                "execution_count": row.execution_count + 1,
                "metadata": row.metadata
            }

        return None

    except Exception as e:
        logger.warning(f"[NLQuery] Similarity cache check failed: {e}")
        db.rollback()
        return None


async def _generate_sql_with_llm(
    query: str,
    provider_name: str
) -> Dict[str, Any]:
    """Generate SQL using specified LLM provider"""
    router = get_llm_router()
    provider = router.get_provider(provider_name)
    schema_context = get_schema_context()

    result = await provider.generate_sql(query, schema_context)
    return result


async def _store_in_redis(query_hash: str, data: Dict[str, Any]):
    """Store query result in Redis"""
    try:
        redis = await get_redis_client()
        await redis.set(f"nlquery:{query_hash}", data)
        logger.debug(f"[NLQuery] Stored in Redis: {query_hash}")
    except Exception as e:
        logger.warning(f"[NLQuery] Redis storage failed: {e}")


async def _store_in_cache(
    db: Session,
    query_text: str,
    query_hash: str,
    embedding: list,
    sql: str,
    llm_provider: str,
    llm_model: str,
    metadata: Dict[str, Any]
):
    """Store query and SQL in both Redis and PostgreSQL"""
    # Store in PostgreSQL
    try:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        metadata_json = json.dumps(metadata)

        # Use f-string for both vector and jsonb type casting, but bind params for user data
        insert = text(f"""
            INSERT INTO nl_query_cache (
                query_text, query_hash, query_embedding, generated_sql,
                llm_provider, llm_model, validated, execution_count,
                last_used_at, metadata
            ) VALUES (
                :query_text, :query_hash, '{embedding_str}'::vector, :sql,
                :provider, :model, true, 1,
                NOW(), '{metadata_json}'::jsonb
            )
            ON CONFLICT (query_hash) DO UPDATE
            SET execution_count = nl_query_cache.execution_count + 1,
                last_used_at = NOW()
        """)

        db.execute(insert, {
            "query_text": query_text,
            "query_hash": query_hash,
            "sql": sql,
            "provider": llm_provider,
            "model": llm_model
        })
        db.commit()
        logger.debug(f"[NLQuery] Stored in PostgreSQL: {query_hash}")

    except Exception as e:
        logger.error(f"[NLQuery] PostgreSQL storage failed: {e}")
        db.rollback()

    # Store in Redis
    await _store_in_redis(query_hash, {
        "sql": sql,
        "llm_provider": llm_provider,
        "execution_count": 1,
        "metadata": metadata
    })


# Execute SQL Request/Response Models
class ExecuteSQLRequest(BaseModel):
    """Request model for SQL execution"""
    sql: str

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, v: str) -> str:
        """Re-validate SQL for safety"""
        validator = get_sql_validator()
        is_valid, error_msg = validator.validate(v)
        if not is_valid:
            raise ValueError(f"Invalid SQL: {error_msg}")
        return v


class ExecuteSQLResponse(BaseModel):
    """Response model for SQL execution"""
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: int


@router.post("/execute", response_model=ExecuteSQLResponse)
async def execute_sql(
    request: ExecuteSQLRequest,
    db: Session = Depends(get_db)
):
    """
    Execute a validated SQL query and return results.

    Security measures:
    - SQL is re-validated before execution
    - Executed in read-only transaction
    - 10 second statement timeout
    - Row limit enforced (max 1000 rows)

    Args:
        request: SQL execution request with validated SQL
        db: Database session

    Returns:
        ExecuteSQLResponse with query results

    Raises:
        HTTPException: On validation or execution errors
    """
    try:
        logger.info(f"[NLQuery] Executing SQL: {request.sql[:100]}...")

        # Re-validate SQL (already validated in request model, but double-check)
        validator = get_sql_validator()
        is_valid, error_msg = validator.validate(request.sql)
        if not is_valid:
            logger.warning(f"[NLQuery] SQL validation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        # Execute with safety constraints
        start_time = time.time()

        # Read-only transaction with timeout
        db.execute(text("BEGIN TRANSACTION READ ONLY"))
        db.execute(text("SET LOCAL statement_timeout = '10s'"))

        result = db.execute(text(request.sql))
        rows = result.fetchall()
        columns = list(result.keys())

        db.execute(text("COMMIT"))

        # Convert to list of dicts with type formatting
        data = []
        for row in rows[:1000]:  # Limit to 1000 rows max
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Format special types for JSON serialization
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, Decimal):
                    value = float(value)
                row_dict[col] = value
            data.append(row_dict)

        execution_time = int((time.time() - start_time) * 1000)

        logger.info(
            f"[NLQuery] Query executed successfully: "
            f"{len(data)} rows, {len(columns)} columns, {execution_time}ms"
        )

        return ExecuteSQLResponse(
            columns=columns,
            rows=data,
            row_count=len(data),
            execution_time_ms=execution_time
        )

    except HTTPException:
        raise
    except Exception as e:
        db.execute(text("ROLLBACK"))
        logger.error(f"[NLQuery] SQL execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query execution failed: {str(e)}"
        )
