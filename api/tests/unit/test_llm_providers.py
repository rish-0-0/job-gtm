"""
Unit tests for LLM providers
Tests Claude, ChatGPT, and Ollama providers
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_provider import (
    LLMProvider,
    LLMProviderError,
    LLMTimeoutError,
    LLMValidationError,
)


@pytest.mark.unit
class TestLLMProviderInterface:
    """Test suite for LLM provider interface"""

    def test_llm_provider_is_abstract(self):
        """Test that LLMProvider cannot be instantiated directly"""
        with pytest.raises(TypeError):
            LLMProvider()

    def test_llm_provider_requires_generate_sql_method(self):
        """Test that LLMProvider requires generate_sql method"""
        class IncompleteProvider(LLMProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_llm_provider_error_inheritance(self):
        """Test that LLMProviderError inherits from Exception"""
        error = LLMProviderError("Test error")
        assert isinstance(error, Exception)

    def test_llm_timeout_error_inheritance(self):
        """Test that LLMTimeoutError inherits from LLMProviderError"""
        error = LLMTimeoutError("Timeout occurred")
        assert isinstance(error, LLMProviderError)
        assert isinstance(error, Exception)

    def test_llm_validation_error_inheritance(self):
        """Test that LLMValidationError inherits from LLMProviderError"""
        error = LLMValidationError("Validation failed")
        assert isinstance(error, LLMProviderError)
        assert isinstance(error, Exception)


@pytest.mark.unit
@pytest.mark.requires_llm
class TestClaudeProvider:
    """Test suite for Claude provider"""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Mock Anthropic client"""
        with patch("app.services.claude_provider.AsyncAnthropic") as mock:
            yield mock.return_value

    @pytest.fixture
    async def claude_provider(self, mock_anthropic_client):
        """Create Claude provider with mocked client"""
        from app.services.claude_provider import ClaudeProvider
        provider = ClaudeProvider()
        provider.client = mock_anthropic_client
        return provider

    @pytest.mark.asyncio
    async def test_generate_sql_success(self, claude_provider, mock_anthropic_client, schema_context, mock_llm_response):
        """Test successful SQL generation"""
        # Mock the API response
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"sql": "SELECT * FROM mv_root_data"}')]
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

        result = await claude_provider.generate_sql("How many jobs?", schema_context)

        assert result is not None
        assert "sql" in result
        assert isinstance(result["sql"], str)

    @pytest.mark.asyncio
    async def test_generate_sql_with_metadata(self, claude_provider, mock_anthropic_client, schema_context):
        """Test that metadata is included in response"""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"sql": "SELECT COUNT(*) FROM mv_root_data"}')]
        mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

        result = await claude_provider.generate_sql("How many jobs?", schema_context)

        assert "metadata" in result
        assert "prompt_tokens" in result["metadata"]
        assert "response_tokens" in result["metadata"]
        assert "duration_ms" in result["metadata"]

    @pytest.mark.asyncio
    async def test_health_check_success(self, claude_provider, mock_anthropic_client):
        """Test successful health check"""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"status": "ok"}')]
        mock_anthropic_client.messages.create = AsyncMock(return_value=mock_message)

        health = await claude_provider.health_check()

        assert health is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, claude_provider, mock_anthropic_client):
        """Test failed health check"""
        mock_anthropic_client.messages.create = AsyncMock(side_effect=Exception("Connection failed"))

        health = await claude_provider.health_check()

        assert health is False

    def test_provider_name(self, claude_provider):
        """Test provider name property"""
        assert claude_provider.provider_name == "claude"

    def test_model_name(self, claude_provider):
        """Test model name property"""
        assert isinstance(claude_provider.model_name, str)
        assert len(claude_provider.model_name) > 0


@pytest.mark.unit
@pytest.mark.requires_llm
class TestChatGPTProvider:
    """Test suite for ChatGPT provider"""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client"""
        with patch("app.services.chatgpt_provider.AsyncOpenAI") as mock:
            yield mock.return_value

    @pytest.fixture
    async def chatgpt_provider(self, mock_openai_client):
        """Create ChatGPT provider with mocked client"""
        from app.services.chatgpt_provider import ChatGPTProvider
        provider = ChatGPTProvider()
        provider.client = mock_openai_client
        return provider

    @pytest.mark.asyncio
    async def test_generate_sql_success(self, chatgpt_provider, mock_openai_client, schema_context):
        """Test successful SQL generation"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"sql": "SELECT * FROM mv_root_data"}'))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await chatgpt_provider.generate_sql("How many jobs?", schema_context)

        assert result is not None
        assert "sql" in result
        assert isinstance(result["sql"], str)

    @pytest.mark.asyncio
    async def test_health_check_success(self, chatgpt_provider, mock_openai_client):
        """Test successful health check"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"status": "ok"}'))]
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        health = await chatgpt_provider.health_check()

        assert health is True

    def test_provider_name(self, chatgpt_provider):
        """Test provider name property"""
        assert chatgpt_provider.provider_name == "chatgpt"

    def test_model_name(self, chatgpt_provider):
        """Test model name property"""
        assert isinstance(chatgpt_provider.model_name, str)
        assert len(chatgpt_provider.model_name) > 0


@pytest.mark.unit
@pytest.mark.requires_llm
class TestOllamaProvider:
    """Test suite for Ollama provider"""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx async client"""
        with patch("app.services.ollama_provider.httpx.AsyncClient") as mock:
            yield mock.return_value

    @pytest.fixture
    async def ollama_provider(self, mock_httpx_client):
        """Create Ollama provider with mocked client"""
        from app.services.ollama_provider import OllamaProvider
        provider = OllamaProvider()
        provider.client = mock_httpx_client
        return provider

    @pytest.mark.asyncio
    async def test_generate_sql_success(self, ollama_provider, mock_httpx_client, schema_context):
        """Test successful SQL generation"""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={"response": '{"sql": "SELECT * FROM mv_root_data"}'})
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        result = await ollama_provider.generate_sql("How many jobs?", schema_context)

        assert result is not None
        assert "sql" in result

    @pytest.mark.asyncio
    async def test_health_check_success(self, ollama_provider, mock_httpx_client):
        """Test successful health check"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        health = await ollama_provider.health_check()

        assert health is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, ollama_provider, mock_httpx_client):
        """Test failed health check"""
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Connection failed"))

        health = await ollama_provider.health_check()

        assert health is False

    def test_provider_name(self, ollama_provider):
        """Test provider name property"""
        assert ollama_provider.provider_name == "ollama"


@pytest.mark.unit
class TestLLMProviderResponse:
    """Test suite for LLM provider response validation"""

    def test_valid_response_structure(self, mock_llm_response):
        """Test that response has required fields"""
        assert "sql" in mock_llm_response
        assert "confidence" in mock_llm_response
        assert "model" in mock_llm_response
        assert "metadata" in mock_llm_response

    def test_response_sql_is_string(self, mock_llm_response):
        """Test that SQL in response is a string"""
        assert isinstance(mock_llm_response["sql"], str)
        assert len(mock_llm_response["sql"]) > 0

    def test_response_confidence_is_float(self, mock_llm_response):
        """Test that confidence is a float between 0 and 1"""
        assert isinstance(mock_llm_response["confidence"], float)
        assert 0 <= mock_llm_response["confidence"] <= 1

    def test_response_metadata_fields(self, mock_llm_response):
        """Test that metadata contains expected fields"""
        metadata = mock_llm_response["metadata"]
        assert "prompt_tokens" in metadata
        assert "response_tokens" in metadata
        assert "duration_ms" in metadata
        assert isinstance(metadata["prompt_tokens"], int)
        assert isinstance(metadata["response_tokens"], int)
        assert isinstance(metadata["duration_ms"], int)


@pytest.mark.unit
class TestLLMProviderErrors:
    """Test suite for LLM provider error handling"""

    def test_timeout_error_raised(self):
        """Test that timeout errors are properly raised"""
        with pytest.raises(LLMTimeoutError):
            raise LLMTimeoutError("Request timed out after 30 seconds")

    def test_validation_error_raised(self):
        """Test that validation errors are properly raised"""
        with pytest.raises(LLMValidationError):
            raise LLMValidationError("Invalid response format")

    def test_provider_error_raised(self):
        """Test that provider errors are properly raised"""
        with pytest.raises(LLMProviderError):
            raise LLMProviderError("Provider connection failed")

    def test_error_message_preserved(self):
        """Test that error messages are preserved"""
        msg = "Detailed error message"
        error = LLMProviderError(msg)
        assert str(error) == msg
