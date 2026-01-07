"""
ChatGPT (OpenAI) LLM Provider for text-to-SQL generation
Uses gpt-4o-mini model by default
"""
import json
import logging
from typing import Dict, Any
from datetime import datetime, timezone
import openai
from openai import AsyncOpenAI

from app.config import OPENAI_API_KEY
from app.services.llm_provider import LLMProvider, LLMProviderError, LLMTimeoutError
from app.utils.prompt_templates import build_chatgpt_messages

logger = logging.getLogger(__name__)


class ChatGPTProvider(LLMProvider):
    """
    OpenAI ChatGPT provider implementation
    Uses GPT-4o-mini for cost-effective text-to-SQL generation
    """

    def __init__(
        self,
        api_key: str = OPENAI_API_KEY,
        model: str = "gpt-4o-mini"
    ):
        """
        Initialize ChatGPT provider

        Args:
            api_key: OpenAI API key
            model: Model name (default: gpt-4o-mini)

        Raises:
            LLMProviderError: If API key is missing
        """
        if not api_key:
            raise LLMProviderError("OpenAI API key not configured")

        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=30.0,  # 30 second timeout
        )
        logger.info(f"[ChatGPTProvider] Initialized with model: {model}")

    @property
    def provider_name(self) -> str:
        return "chatgpt"

    @property
    def model_name(self) -> str:
        return self.model

    async def generate_sql(
        self,
        natural_query: str,
        schema_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language using ChatGPT

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
            logger.info(f"[ChatGPTProvider] Generating SQL for query: {natural_query[:100]}...")

            # Build messages
            messages = build_chatgpt_messages(natural_query, schema_context)
            logger.debug(f"[ChatGPTProvider] Built messages with {len(messages)} parts")

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # Low temperature for deterministic SQL
                response_format={"type": "json_object"},  # Force JSON response
                max_tokens=1024,  # SQL queries are concise
            )

            # Parse response
            sql_data = self._parse_response(response)

            # Add metadata
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            usage = response.usage
            return {
                "sql": sql_data["sql"],
                "confidence": sql_data.get("confidence", 0.95),
                "model": self.model,
                "metadata": {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "response_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                    "duration_ms": duration_ms,
                    "provider": self.provider_name
                }
            }

        except openai.APITimeoutError as e:
            logger.error(f"[ChatGPTProvider] Timeout: {e}")
            raise LLMTimeoutError(f"ChatGPT request timed out: {str(e)}")
        except openai.APIError as e:
            logger.error(f"[ChatGPTProvider] API error: {e}")
            raise LLMProviderError(f"ChatGPT API error: {str(e)}")
        except Exception as e:
            logger.error(f"[ChatGPTProvider] Error: {e}", exc_info=True)
            raise LLMProviderError(f"ChatGPT generation failed: {str(e)}")

    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse ChatGPT response to extract SQL

        Args:
            response: OpenAI API response object

        Returns:
            Parsed dict with sql and confidence

        Raises:
            LLMProviderError: If parsing fails
        """
        try:
            # Extract content from first choice
            if not response.choices:
                logger.error(f"[ChatGPTProvider] No choices in response")
                raise LLMProviderError("No response from ChatGPT")

            content = response.choices[0].message.content
            if not content:
                logger.error(f"[ChatGPTProvider] Empty content in response")
                raise LLMProviderError("Empty response from ChatGPT")

            logger.debug(f"[ChatGPTProvider] Response length: {len(content)} chars")

            # Parse JSON
            try:
                sql_data = json.loads(content)
                logger.debug(f"[ChatGPTProvider] Successfully parsed JSON")
            except json.JSONDecodeError as e:
                logger.error(f"[ChatGPTProvider] JSON parse error: {e}")
                logger.error(f"[ChatGPTProvider] Failed content: {content[:500]}")
                raise LLMProviderError(f"Failed to parse JSON: {e.msg}")

            # Validate response has sql field
            if "sql" not in sql_data:
                logger.error(f"[ChatGPTProvider] Response missing 'sql' field")
                raise LLMProviderError("Response missing 'sql' field")

            return sql_data

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"[ChatGPTProvider] Parse error: {e}", exc_info=True)
            raise LLMProviderError(f"Failed to parse response: {str(e)}")

    async def health_check(self) -> bool:
        """
        Check if OpenAI API is accessible

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple API call to check connectivity
            await self.client.models.retrieve(self.model)
            logger.info("[ChatGPTProvider] Health check passed")
            return True
        except Exception as e:
            logger.error(f"[ChatGPTProvider] Health check failed: {e}")
            return False
