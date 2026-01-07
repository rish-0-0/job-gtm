"""
LLM Router for selecting and managing different LLM providers
Factory pattern for provider instantiation
"""
import logging
from typing import Dict, Optional
from app.services.llm_provider import LLMProvider, LLMProviderError
from app.services.ollama_provider import OllamaProvider
from app.services.chatgpt_provider import ChatGPTProvider
from app.services.claude_provider import ClaudeProvider

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Routes text-to-SQL requests to appropriate LLM provider
    Manages provider instances and selection
    """

    def __init__(self):
        """Initialize router with all available providers"""
        self._providers: Dict[str, Optional[LLMProvider]] = {}
        logger.info("[LLMRouter] Initializing LLM Router")

        # Initialize providers (lazy loading on first use)
        self._init_providers()

    def _init_providers(self):
        """Initialize provider instances"""
        # Always initialize Ollama (local, no API key needed)
        try:
            self._providers["ollama"] = OllamaProvider()
            logger.info("[LLMRouter] Ollama provider initialized")
        except Exception as e:
            logger.warning(f"[LLMRouter] Failed to initialize Ollama: {e}")
            self._providers["ollama"] = None

        # Initialize ChatGPT (requires API key)
        try:
            self._providers["chatgpt"] = ChatGPTProvider()
            logger.info("[LLMRouter] ChatGPT provider initialized")
        except LLMProviderError as e:
            logger.info(f"[LLMRouter] ChatGPT not available: {e}")
            self._providers["chatgpt"] = None
        except Exception as e:
            logger.warning(f"[LLMRouter] Failed to initialize ChatGPT: {e}")
            self._providers["chatgpt"] = None

        # Initialize Claude (requires API key)
        try:
            self._providers["claude"] = ClaudeProvider()
            logger.info("[LLMRouter] Claude provider initialized")
        except LLMProviderError as e:
            logger.info(f"[LLMRouter] Claude not available: {e}")
            self._providers["claude"] = None
        except Exception as e:
            logger.warning(f"[LLMRouter] Failed to initialize Claude: {e}")
            self._providers["claude"] = None

    def get_provider(self, provider_name: str) -> LLMProvider:
        """
        Get LLM provider by name

        Args:
            provider_name: Provider identifier (ollama, chatgpt, claude)

        Returns:
            LLMProvider instance

        Raises:
            LLMProviderError: If provider not available
        """
        provider_name = provider_name.lower()

        if provider_name not in self._providers:
            available = [p for p in self._providers.keys() if self._providers[p] is not None]
            raise LLMProviderError(
                f"Unknown provider: {provider_name}. Available: {', '.join(available)}"
            )

        provider = self._providers[provider_name]
        if provider is None:
            raise LLMProviderError(
                f"Provider '{provider_name}' not configured or unavailable"
            )

        logger.debug(f"[LLMRouter] Selected provider: {provider_name}")
        return provider

    def get_available_providers(self) -> Dict[str, bool]:
        """
        Get availability status of all providers

        Returns:
            Dict mapping provider names to availability (True/False)
        """
        return {
            name: provider is not None
            for name, provider in self._providers.items()
        }

    def get_fallback_provider(self, exclude: Optional[str] = None) -> Optional[LLMProvider]:
        """
        Get first available fallback provider

        Args:
            exclude: Provider name to exclude from fallback

        Returns:
            LLMProvider instance or None if no fallback available
        """
        # Fallback priority: Ollama -> ChatGPT -> Claude
        priority = ["ollama", "chatgpt", "claude"]

        for provider_name in priority:
            if provider_name == exclude:
                continue

            provider = self._providers.get(provider_name)
            if provider is not None:
                logger.info(f"[LLMRouter] Using fallback provider: {provider_name}")
                return provider

        logger.warning("[LLMRouter] No fallback provider available")
        return None


# Singleton instance
_llm_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """
    Get singleton LLM router instance

    Returns:
        LLMRouter instance
    """
    global _llm_router
    if _llm_router is None:
        _llm_router = LLMRouter()
    return _llm_router
