# src/unit_test_generator/infrastructure/adk_tools/read_file_tool.py
"""
ADK Tool for reading content from a file.
"""
import logging
from typing import Dict, Any

from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class ReadFileTool(JUnitWriterTool):
    """Tool for reading content from a file."""

    def __init__(self, file_system: FileSystemPort):
        """
        Initialize the ReadFileTool.

        Args:
            file_system: An implementation of FileSystemPort
        """
        super().__init__(
            name="read_file",
            description="Reads content from a file."
        )
        self.file_system = file_system

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to read from a file.

        Args:
            parameters: Dictionary containing:
                - file_path: Path to the file to read

        Returns:
            Dictionary containing:
                - success: Boolean indicating if the read was successful
                - content: Content of the file
                - file_path: Path to the file that was read
        """
        file_path = parameters.get("file_path")

        if not file_path:
            raise ValueError("Missing required parameter: file_path")

        logger.info(f"Reading from file: {file_path}")
        try:
            if not self.file_system.exists(file_path):
                return {
                    "success": False,
                    "file_path": file_path,
                    "error": f"File not found: {file_path}"
                }

            content = self.file_system.read_file(file_path)
            return {
                "success": True,
                "content": content,
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Error reading from file {file_path}: {e}", exc_info=True)
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e)
            }
