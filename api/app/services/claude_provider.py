"""
Claude (Anthropic) LLM Provider for text-to-SQL generation
Uses Claude Sonnet 4.5 model by default
"""
import json
import logging
from typing import Dict, Any
from datetime import datetime, timezone
import anthropic
from anthropic import AsyncAnthropic

from app.config import ANTHROPIC_API_KEY
from app.services.llm_provider import LLMProvider, LLMProviderError, LLMTimeoutError
from app.utils.prompt_templates import build_claude_system_prompt

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    """
    Anthropic Claude provider implementation
    Uses Claude Sonnet 4.5 for high-quality text-to-SQL generation
    """

    def __init__(
        self,
        api_key: str = ANTHROPIC_API_KEY,
        model: str = "claude-sonnet-4-5-20250929"
    ):
        """
        Initialize Claude provider

        Args:
            api_key: Anthropic API key
            model: Model name (default: claude-sonnet-4-5-20250929)

        Raises:
            LLMProviderError: If API key is missing
        """
        if not api_key:
            raise LLMProviderError("Anthropic API key not configured")

        self.model = model
        self.client = AsyncAnthropic(
            api_key=api_key,
            timeout=30.0,  # 30 second timeout
        )
        logger.info(f"[ClaudeProvider] Initialized with model: {model}")

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self.model

    async def generate_sql(
        self,
        natural_query: str,
        schema_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language using Claude

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
            logger.info(f"[ClaudeProvider] Generating SQL for query: {natural_query[:100]}...")

            # Build system prompt
            system_prompt = build_claude_system_prompt(schema_context)
            logger.debug(f"[ClaudeProvider] System prompt length: {len(system_prompt)} chars")

            # Call Claude API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0.1,  # Low temperature for deterministic SQL
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": natural_query
                    }
                ]
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
                    "prompt_tokens": usage.input_tokens if usage else 0,
                    "response_tokens": usage.output_tokens if usage else 0,
                    "total_tokens": (usage.input_tokens + usage.output_tokens) if usage else 0,
                    "duration_ms": duration_ms,
                    "provider": self.provider_name
                }
            }

        except anthropic.APITimeoutError as e:
            logger.error(f"[ClaudeProvider] Timeout: {e}")
            raise LLMTimeoutError(f"Claude request timed out: {str(e)}")
        except anthropic.APIError as e:
            logger.error(f"[ClaudeProvider] API error: {e}")
            raise LLMProviderError(f"Claude API error: {str(e)}")
        except Exception as e:
            logger.error(f"[ClaudeProvider] Error: {e}", exc_info=True)
            raise LLMProviderError(f"Claude generation failed: {str(e)}")

    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse Claude response to extract SQL

        Args:
            response: Anthropic API response object

        Returns:
            Parsed dict with sql and confidence

        Raises:
            LLMProviderError: If parsing fails
        """
        try:
            # Extract content from first content block
            if not response.content:
                logger.error(f"[ClaudeProvider] No content in response")
                raise LLMProviderError("No response from Claude")

            # Get text from first content block
            content = response.content[0].text if response.content else ""
            if not content:
                logger.error(f"[ClaudeProvider] Empty content in response")
                raise LLMProviderError("Empty response from Claude")

            logger.debug(f"[ClaudeProvider] Response length: {len(content)} chars")

            # Clean response (remove markdown if present)
            content = content.strip()
            if content.startswith("```json"):
                lines = content.split("\n")
                lines = lines[1:]  # Remove first line
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]  # Remove last line
                content = "\n".join(lines).strip()

            # Parse JSON
            try:
                sql_data = json.loads(content)
                logger.debug(f"[ClaudeProvider] Successfully parsed JSON")
            except json.JSONDecodeError as e:
                logger.error(f"[ClaudeProvider] JSON parse error: {e}")
                logger.error(f"[ClaudeProvider] Failed content: {content[:500]}")
                raise LLMProviderError(f"Failed to parse JSON: {e.msg}")

            # Validate response has sql field
            if "sql" not in sql_data:
                logger.error(f"[ClaudeProvider] Response missing 'sql' field")
                raise LLMProviderError("Response missing 'sql' field")

            return sql_data

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"[ClaudeProvider] Parse error: {e}", exc_info=True)
            raise LLMProviderError(f"Failed to parse response: {str(e)}")

    async def health_check(self) -> bool:
        """
        Check if Claude API is accessible

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple API call to check connectivity
            # Create a minimal message to test the API
            await self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            logger.info("[ClaudeProvider] Health check passed")
            return True
        except Exception as e:
            logger.error(f"[ClaudeProvider] Health check failed: {e}")
            return False
