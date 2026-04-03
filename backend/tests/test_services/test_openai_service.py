"""
Tests for OpenAI Service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.openai_service import OpenAIService, MODEL_CONFIGS


class TestOpenAIServicePromptRendering:
    """Test prompt rendering functionality."""
    
    def test_render_prompt_basic(self):
        """Test basic prompt rendering with placeholders."""
        service = OpenAIService()
        
        template = "Hello {{name}}, you work at {{company}}."
        row_data = {"name": "John", "company": "Acme"}
        
        result = service.render_prompt(template, row_data)
        
        assert result == "Hello John, you work at Acme."
    
    def test_render_prompt_missing_placeholder(self):
        """Test rendering with missing data returns empty string for placeholder."""
        service = OpenAIService()
        
        template = "Hello {{name}}, your email is {{email}}."
        row_data = {"name": "John"}
        
        result = service.render_prompt(template, row_data)
        
        assert result == "Hello John, your email is ."
    
    def test_render_prompt_none_value(self):
        """Test rendering with None value."""
        service = OpenAIService()
        
        template = "Hello {{name}}."
        row_data = {"name": None}
        
        result = service.render_prompt(template, row_data)
        
        assert result == "Hello ."
    
    def test_render_prompt_special_characters(self):
        """Test rendering with special characters in values."""
        service = OpenAIService()
        
        template = "Company: {{company}}"
        row_data = {"company": "Acme & Sons <Inc>"}
        
        result = service.render_prompt(template, row_data)
        
        assert result == "Company: Acme & Sons <Inc>"


class TestModelConfigs:
    """Test model configuration."""
    
    def test_model_configs_exist(self):
        """Test that model configs are defined."""
        assert "gpt-4o" in MODEL_CONFIGS
        assert "gpt-4o-mini" in MODEL_CONFIGS
        assert "o1" in MODEL_CONFIGS
    
    def test_get_model_config_known_model(self):
        """Test getting config for known model."""
        service = OpenAIService()
        
        config = service._get_model_config("gpt-4o-mini")
        
        assert config["max_tokens"] == 4096
        assert config["supports_system"] is True
    
    def test_get_model_config_unknown_model(self):
        """Test getting config for unknown model returns default."""
        service = OpenAIService()
        
        config = service._get_model_config("unknown-model")
        
        # Should return gpt-4o-mini config as default
        assert config["max_tokens"] == 4096


class TestOpenAIServiceConnection:
    """Test OpenAI service connection handling."""
    
    def test_service_without_api_key(self):
        """Test service without API key."""
        service = OpenAIService(api_key=None)
        
        assert service.client is None
    
    def test_service_with_api_key(self):
        """Test service with API key creates client."""
        service = OpenAIService(api_key="test-key")
        
        assert service.client is not None
    
    def test_set_api_key(self):
        """Test setting API key after initialization."""
        service = OpenAIService(api_key=None)
        assert service.client is None
        
        service.set_api_key("new-key")
        
        assert service.client is not None
        assert service.api_key == "new-key"


class TestOpenAIServiceEnrichment:
    """Test enrichment functionality."""
    
    @pytest.mark.asyncio
    async def test_enrich_single_row_no_api_key(self):
        """Test enrichment fails without API key."""
        service = OpenAIService(api_key=None)
        
        with pytest.raises(ValueError, match="API key not configured"):
            await service.enrich_single_row("Test prompt")
    
    @pytest.mark.asyncio
    async def test_enrich_single_row_success(self):
        """Test successful single row enrichment."""
        service = OpenAIService(api_key="test-key")
        
        # Mock the OpenAI client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Enriched result"
        mock_response.usage.total_tokens = 100
        
        with patch.object(
            service.client.chat.completions, 
            'create', 
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await service.enrich_single_row("Test prompt", model="gpt-4o-mini")
        
        assert result["success"] is True
        assert result["result"] == "Enriched result"
        assert result["tokens_used"] == 100
    
    @pytest.mark.asyncio
    async def test_enrich_single_row_with_system_prompt(self):
        """Test enrichment with system prompt."""
        service = OpenAIService(api_key="test-key")
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Result"
        mock_response.usage.total_tokens = 50
        
        with patch.object(
            service.client.chat.completions,
            'create',
            new_callable=AsyncMock,
            return_value=mock_response
        ) as mock_create:
            await service.enrich_single_row(
                "Test prompt",
                system_prompt="You are a helpful assistant",
                model="gpt-4o-mini"
            )
            
            # Verify system prompt was included
            call_args = mock_create.call_args
            messages = call_args.kwargs.get('messages', call_args.args[0] if call_args.args else [])
            assert any(m.get('role') == 'system' for m in messages)
    
    @pytest.mark.asyncio
    async def test_enrich_single_row_reasoning_model(self):
        """Test enrichment with reasoning model (o1/o3)."""
        service = OpenAIService(api_key="test-key")
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Reasoning result"
        mock_response.usage.total_tokens = 200
        
        with patch.object(
            service.client.chat.completions,
            'create',
            new_callable=AsyncMock,
            return_value=mock_response
        ) as mock_create:
            result = await service.enrich_single_row(
                "Test prompt",
                system_prompt="System prompt",
                model="o1-mini"
            )
            
            # Reasoning models use max_completion_tokens instead of max_tokens
            call_args = mock_create.call_args
            assert 'max_completion_tokens' in call_args.kwargs


class TestOpenAIServiceTestConnection:
    """Test connection testing functionality."""
    
    @pytest.mark.asyncio
    async def test_connection_no_client(self):
        """Test connection check without client."""
        service = OpenAIService(api_key=None)
        
        result = await service.test_connection()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_connection_success(self):
        """Test successful connection check."""
        service = OpenAIService(api_key="test-key")
        
        with patch.object(
            service.client.models,
            'list',
            new_callable=AsyncMock
        ):
            result = await service.test_connection()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test failed connection check."""
        service = OpenAIService(api_key="test-key")
        
        with patch.object(
            service.client.models,
            'list',
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed")
        ):
            result = await service.test_connection()
        
        assert result is False
