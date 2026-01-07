"""
Ollama LLM Provider for text-to-SQL generation
Uses qwen2.5:7b model by default
"""
import json
import logging
from typing import Dict, Any
from datetime import datetime, timezone
import httpx

from app.config import OLLAMA_URL, OLLAMA_MODEL
from app.services.llm_provider import LLMProvider, LLMProviderError, LLMTimeoutError
from app.utils.prompt_templates import build_text_to_sql_prompt

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider implementation
    Connects to local Ollama service for text-to-SQL generation
    """

    def __init__(
        self,
        base_url: str = OLLAMA_URL,
        model: str = OLLAMA_MODEL
    ):
        """
        Initialize Ollama provider

        Args:
            base_url: Ollama API base URL
            model: Model name to use
        """
        self.base_url = base_url
        self.model = model
        self.timeout = httpx.Timeout(
            connect=30.0,   # 30s to establish connection
            read=120.0,     # 2 minutes for text-to-SQL (simpler than job enrichment)
            write=30.0,     # 30s to send request
            pool=30.0       # 30s to acquire connection from pool
        )
        logger.info(f"[OllamaProvider] Initialized with URL: {base_url}, Model: {model}")

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self.model

    async def generate_sql(
        self,
        natural_query: str,
        schema_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language using Ollama

        Args:
            natural_query: User's question in natural language
            schema_context: Database schema information

        Returns:
            Dict with sql, confidence, model, metadata

        Raises:
            LLMProviderError: If generation fails
            LLMTimeoutError: If request times out
        """
        try:
            start_time = datetime.now(timezone.utc)
            logger.info(f"[OllamaProvider] Generating SQL for query: {natural_query[:100]}...")

            # Build prompt
            prompt = build_text_to_sql_prompt(natural_query, schema_context)
            logger.debug(f"[OllamaProvider] Prompt length: {len(prompt)} chars")

            # Call Ollama API
            result = await self._call_ollama(prompt)

            # Parse response
            sql_data = self._parse_response(result)

            # Add metadata
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            return {
                "sql": sql_data["sql"],
                "confidence": sql_data.get("confidence", 0.9),
                "model": self.model,
                "metadata": {
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "response_tokens": result.get("eval_count", 0),
                    "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
                    "duration_ms": duration_ms,
                    "provider": self.provider_name
                }
            }

        except httpx.TimeoutException as e:
            logger.error(f"[OllamaProvider] Timeout: {e}")
            raise LLMTimeoutError(f"Ollama request timed out: {str(e)}")
        except Exception as e:
            logger.error(f"[OllamaProvider] Error: {e}", exc_info=True)
            raise LLMProviderError(f"Ollama generation failed: {str(e)}")

    async def _call_ollama(self, prompt: str) -> Dict[str, Any]:
        """
        Call Ollama API

        Args:
            prompt: Full prompt for SQL generation

        Returns:
            Ollama API response

        Raises:
            httpx.TimeoutException: On timeout
            httpx.HTTPError: On HTTP errors
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",  # Force JSON output
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic SQL
                "num_predict": 1024,  # SQL queries are shorter than job enrichment
            }
        }

        logger.debug(f"[OllamaProvider] Calling {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            # Log token usage
            prompt_tokens = result.get("prompt_eval_count", 0)
            response_tokens = result.get("eval_count", 0)
            total_duration_s = result.get("total_duration", 0) / 1e9

            logger.info(
                f"[OllamaProvider] Completed: {prompt_tokens} prompt tokens, "
                f"{response_tokens} response tokens, {total_duration_s:.1f}s"
            )

            return result

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Ollama response to extract SQL

        Args:
            response: Raw Ollama API response

        Returns:
            Parsed dict with sql and confidence

        Raises:
            LLMProviderError: If parsing fails
        """
        try:
            # Extract generated text
            response_text = response.get("response", "")

            if not response_text:
                logger.error(f"[OllamaProvider] Empty response from Ollama")
                raise LLMProviderError("Empty response from Ollama")

            logger.debug(f"[OllamaProvider] Response length: {len(response_text)} chars")
            logger.debug(f"[OllamaProvider] Response preview: {response_text[:200]}")

            # Clean response (remove markdown code blocks if present)
            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                lines = lines[1:]  # Remove first line (```json or ```)
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]  # Remove last line (```)
                response_text = "\n".join(lines).strip()

            # Parse JSON
            try:
                sql_data = json.loads(response_text)
                logger.debug(f"[OllamaProvider] Successfully parsed JSON")
            except json.JSONDecodeError as e:
                logger.error(f"[OllamaProvider] JSON parse error: {e}")
                logger.error(f"[OllamaProvider] Failed response: {response_text[:500]}")
                raise LLMProviderError(f"Failed to parse JSON: {e.msg} at position {e.pos}")

            # Validate response has sql field
            if "sql" not in sql_data:
                logger.error(f"[OllamaProvider] Response missing 'sql' field")
                raise LLMProviderError("Response missing 'sql' field")

            return sql_data

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"[OllamaProvider] Parse error: {e}", exc_info=True)
            raise LLMProviderError(f"Failed to parse response: {str(e)}")

    async def health_check(self) -> bool:
        """
        Check if Ollama service is healthy

        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/api/tags"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                logger.info("[OllamaProvider] Health check passed")
                return True
        except Exception as e:
            logger.error(f"[OllamaProvider] Health check failed: {e}")
            return False
