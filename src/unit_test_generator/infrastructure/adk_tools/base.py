# src/unit_test_generator/infrastructure/adk_tools/base.py
"""
Base classes and utilities for ADK tools.
"""
import logging
from typing import Dict, Any, Optional, List, Type

from google.adk.tools import BaseTool

logger = logging.getLogger(__name__)

# This is a compatibility wrapper to make it easier to transition from our custom tools
# to the official ADK tools
class JUnitWriterTool(BaseTool):
    """
    Base class for all ADK tools in the JUnit Writer application.
    This class extends the official ADK BaseTool and provides a compatibility layer
    for our existing tool implementations.
    """

    def __init__(self, name: str, description: str, is_long_running: bool = False):
        """
        Initialize the JUnit Writer tool.

        Args:
            name: The name of the tool
            description: A description of what the tool does
            is_long_running: Whether the tool is a long-running operation
        """
        super().__init__(name=name, description=description, is_long_running=is_long_running)
        logger.debug(f"Initialized JUnit Writer tool: {name}")

    async def run_async(self, args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
        """
        Run the tool with the given arguments and context.
        This method is required by the ADK BaseTool class.

        Args:
            args: The arguments for the tool
            tool_context: The context for the tool

        Returns:
            The result of running the tool
        """
        try:
            logger.debug(f"Running tool {self.name} with arguments: {args}")
            result = self._execute(args)
            logger.debug(f"Tool {self.name} execution successful")
            return result
        except Exception as e:
            logger.error(f"Error running tool {self.name}: {e}", exc_info=True)
            return {"error": str(e), "success": False}

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool's core functionality.
        This method should be overridden by subclasses.

        Args:
            parameters: The parameters passed to the tool

        Returns:
            A dictionary containing the tool's response
        """
        raise NotImplementedError(f"Tool {self.name} does not implement _execute")
