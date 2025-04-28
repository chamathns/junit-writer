# src/unit_test_generator/infrastructure/adk_tools/resolve_dependencies_tool.py
"""
ADK Tool for resolving dependencies.
"""
import logging
from typing import Dict, Any, List

from unit_test_generator.application.services.dependency_resolver import DependencyResolverService
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class ResolveDependenciesTool(JUnitWriterTool):
    """Tool for resolving dependencies."""

    def __init__(self, dependency_resolver: DependencyResolverService):
        """
        Initialize the ResolveDependenciesTool.

        Args:
            dependency_resolver: An instance of DependencyResolverService
        """
        super().__init__(
            name="resolve_dependencies",
            description="Resolves symbols to file paths."
        )
        self.dependency_resolver = dependency_resolver

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to resolve dependencies.

        Args:
            parameters: Dictionary containing:
                - symbols: List of symbols to resolve
                - module: (Optional) Module name for context

        Returns:
            Dictionary containing:
                - resolved_paths: Dictionary mapping symbols to file paths
                - success: Boolean indicating if the resolution was successful
        """
        symbols = parameters.get("symbols")
        module = parameters.get("module", "")

        if not symbols:
            raise ValueError("Missing required parameter: symbols")
        if not isinstance(symbols, list):
            raise ValueError("Parameter 'symbols' must be a list")

        logger.info(f"Resolving {len(symbols)} symbols")
        try:
            # Create a simple usage weight dictionary (all equal weights)
            usage_weights = {symbol: 1.0 for symbol in symbols}

            # Use the dependency resolver to resolve the symbols
            resolved = self.dependency_resolver.resolve_dependencies(symbols, usage_weights, module)

            # Convert to a simple dictionary for the response
            resolved_paths = {}
            for symbol, weight in resolved:
                # Get the file path from the dependency resolver
                file_path = self.dependency_resolver.get_file_path_for_symbol(symbol)
                resolved_paths[symbol] = file_path

            return {
                "resolved_paths": resolved_paths,
                "success": True
            }
        except Exception as e:
            logger.error(f"Error resolving dependencies: {e}", exc_info=True)
            return {
                "resolved_paths": {},
                "success": False,
                "error": str(e)
            }
