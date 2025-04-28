# src/unit_test_generator/infrastructure/adk_tools/write_file_tool.py
"""
ADK Tool for writing content to a file.
"""
import logging
from typing import Dict, Any

from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class WriteFileTool(JUnitWriterTool):
    """Tool for writing content to a file."""

    def __init__(self, file_system: FileSystemPort):
        """
        Initialize the WriteFileTool.

        Args:
            file_system: An implementation of FileSystemPort
        """
        super().__init__(
            name="write_file",
            description="Writes content to a file."
        )
        self.file_system = file_system

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to write to a file.

        Args:
            parameters: Dictionary containing:
                - file_path: Path to the file to write
                - content: Content to write to the file

        Returns:
            Dictionary containing:
                - success: Boolean indicating if the write was successful
                - file_path: Path to the file that was written
        """
        file_path = parameters.get("file_path")
        content = parameters.get("content")

        if not file_path:
            raise ValueError("Missing required parameter: file_path")
        if content is None:  # Allow empty string content
            raise ValueError("Missing required parameter: content")

        logger.info(f"Writing to file: {file_path}")
        try:
            self.file_system.write_file(file_path, content)
            return {
                "success": True,
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Error writing to file {file_path}: {e}", exc_info=True)
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e)
            }
