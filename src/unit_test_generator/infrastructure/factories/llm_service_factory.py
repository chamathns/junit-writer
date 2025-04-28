# src/unit_test_generator/infrastructure/factories/llm_service_factory.py
"""
Factory for creating LLM service instances.
"""
import logging
from typing import Dict, Any

from unit_test_generator.domain.ports.llm_service import LLMServicePort

logger = logging.getLogger(__name__)


class LLMServiceFactory:
    """
    Factory for creating LLM service instances.
    """
    
    @staticmethod
    def create_llm_service(config: Dict[str, Any]) -> LLMServicePort:
        """
        Create an LLM service based on configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            An instance of LLMServicePort
            
        Raises:
            ValueError: If the LLM provider is unknown
        """
        provider = config.get("generation", {}).get("llm_provider", "google_gemini")
        
        logger.info(f"Creating LLM service for provider: {provider}")
        
        if provider == "mcp":
            # Import here to avoid circular imports
            from unit_test_generator.infrastructure.adapters.llm.mcp_client_adapter import MCPClientAdapter
            return MCPClientAdapter(config)
        elif provider == "google_gemini":
            # Import here to avoid circular imports
            from unit_test_generator.infrastructure.adapters.llm.google_gemini_adapter import GoogleGeminiAdapter
            return GoogleGeminiAdapter(config)
        elif provider == "openai":
            # Import here to avoid circular imports
            from unit_test_generator.infrastructure.adapters.llm.openai_adapter import OpenAIAdapter
            return OpenAIAdapter(config)
        elif provider == "mock":
            # Import here to avoid circular imports
            from unit_test_generator.infrastructure.adapters.llm.mock_llm_adapter import MockLLMAdapter
            return MockLLMAdapter(config)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
