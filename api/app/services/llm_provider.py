"""
Abstract LLM Provider interface for text-to-SQL generation
Supports multiple LLM providers: Ollama, ChatGPT, Claude
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers
    Defines interface for text-to-SQL generation
    """

    @abstractmethod
    async def generate_sql(
        self,
        natural_query: str,
        schema_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language query

        Args:
            natural_query: User's natural language question
            schema_context: Database schema information including:
                - table: Target table name
                - columns: List of column definitions
                - examples: Few-shot examples

        Returns:
            Dictionary containing:
                {
                    "sql": "SELECT ...",  # Generated SQL query
                    "confidence": 0.95,   # Confidence score (0-1)
                    "model": "qwen2.5:7b",  # Model used
                    "metadata": {
                        "prompt_tokens": 1200,
                        "response_tokens": 150,
                        "duration_ms": 3500
                    }
                }

        Raises:
            Exception: If LLM call fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if LLM provider is available and responsive

        Returns:
            True if healthy, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Get provider name identifier

        Returns:
            Provider name (e.g., "ollama", "chatgpt", "claude")
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Get model name/version being used

        Returns:
            Model identifier (e.g., "qwen2.5:7b", "gpt-4o-mini")
        """
        pass


class LLMProviderError(Exception):
    """Custom exception for LLM provider errors"""
    pass


class LLMTimeoutError(LLMProviderError):
    """Exception for LLM request timeouts"""
    pass


class LLMValidationError(LLMProviderError):
    """Exception for LLM response validation failures"""
    pass
