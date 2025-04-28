# src/unit_test_generator/infrastructure/adk_tools/parse_errors_tool.py
"""
ADK Tool for parsing errors from build/test output.
"""
import logging
from typing import Dict, Any, List

from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class ParseErrorsTool(JUnitWriterTool):
    """Tool for parsing errors from build/test output."""

    def __init__(self, error_parser: ErrorParserPort):
        """
        Initialize the ParseErrorsTool.

        Args:
            error_parser: An implementation of ErrorParserPort
        """
        super().__init__(
            name="parse_errors",
            description="Parses errors from build/test output."
        )
        self.error_parser = error_parser

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to parse errors.

        Args:
            parameters: Dictionary containing:
                - raw_output: Raw output from the build system

        Returns:
            Dictionary containing:
                - errors: List of parsed errors
                - error_count: Number of errors found
        """
        raw_output = parameters.get("raw_output")
        if not raw_output:
            raise ValueError("Missing required parameter: raw_output")

        logger.info("Parsing errors from build output")
        parsed_errors = self.error_parser.parse_output(raw_output)

        # Convert ParsedError objects to dictionaries
        errors_as_dicts = []
        for error in parsed_errors:
            errors_as_dicts.append({
                "file_path": error.file_path,
                "line_number": error.line_number,
                "message": error.message,
                "error_type": error.error_type,
                "involved_symbols": error.involved_symbols
            })

        return {
            "errors": errors_as_dicts,
            "error_count": len(errors_as_dicts)
        }
