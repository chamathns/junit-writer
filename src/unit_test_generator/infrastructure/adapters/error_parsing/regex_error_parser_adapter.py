"""
Regex-based error parser for Kotlin/JUnit5/MockK errors.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Pattern, Match

from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError

logger = logging.getLogger(__name__)

class RegexErrorParserAdapter(ErrorParserPort):
    """
    Error parser that uses regex patterns to extract information from build output.
    Specifically optimized for Kotlin/JUnit5/MockK errors.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the adapter.

        Args:
            config: The application configuration dictionary.
        """
        self.config = config
        self.patterns = self._compile_patterns()
        logger.info("RegexErrorParserAdapter initialized with %d patterns.", len(self.patterns))

    def _compile_patterns(self) -> List[Dict[str, Any]]:
        """Compiles regex patterns for different error types."""
        return [
            # Unresolved reference errors
            {
                "pattern": re.compile(r"Unresolved reference: ([a-zA-Z0-9_]+)"),
                "error_type": "Compilation",
                "error_category": "UnresolvedReference",
                "suggested_fix": "Add missing import or define the referenced symbol",
                "extract_symbol": lambda match: match.group(1)
            },
            # Type mismatch errors
            {
                "pattern": re.compile(r"Type mismatch: inferred type is ([a-zA-Z0-9_.<>?]+) but ([a-zA-Z0-9_.<>?]+) was expected"),
                "error_type": "Compilation",
                "error_category": "TypeMismatch",
                "suggested_fix": "Fix the type mismatch by using the correct type or adding a type conversion",
                "extract_symbol": lambda match: [match.group(1), match.group(2)]
            },
            # MockK verification errors
            {
                "pattern": re.compile(r"(io\.mockk\.MockKException: )(.*?)(?:\n|$)"),
                "error_type": "TestFailure",
                "error_category": "MockkVerificationFailure",
                "suggested_fix": "Fix the mock setup or verification",
                "extract_message": lambda match: match.group(2)
            },
            # Assertion failures
            {
                "pattern": re.compile(r"(org\.opentest4j\.AssertionFailedError: )(.*?)(?:\n|$)"),
                "error_type": "TestFailure",
                "error_category": "AssertionFailure",
                "suggested_fix": "Fix the assertion or the code being tested",
                "extract_message": lambda match: match.group(2)
            },
            # Null pointer exceptions
            {
                "pattern": re.compile(r"(java\.lang\.NullPointerException)(.*?)(?:\n|$)"),
                "error_type": "Runtime",
                "error_category": "NullPointerException",
                "suggested_fix": "Add null checks or initialize the variable properly",
                "extract_message": lambda match: match.group(2) if match.group(2) else "Null pointer exception"
            },
            # Missing imports
            {
                "pattern": re.compile(r"Cannot access '([a-zA-Z0-9_]+)' which is a private name in package '([a-zA-Z0-9_.]+)'"),
                "error_type": "Compilation",
                "error_category": "MissingDependency",
                "suggested_fix": "Add the correct import or use a public API",
                "extract_symbol": lambda match: f"{match.group(2)}.{match.group(1)}"
            },
            # File path and line number extraction
            {
                "pattern": re.compile(r"([a-zA-Z0-9_/\\.-]+\.kt):(\d+)(?::\d+)?:"),
                "extract_file_path": lambda match: match.group(1),
                "extract_line_number": lambda match: int(match.group(2))
            },
            # General error message extraction
            {
                "pattern": re.compile(r"e: (.*?)(?:\n|$)"),
                "extract_message": lambda match: match.group(1)
            }
        ]

    def _extract_file_path_and_line(self, raw_output: str) -> Dict[str, Any]:
        """Extracts file path and line number from build output."""
        result = {"file_path": None, "line_number": None}
        
        for pattern_dict in self.patterns:
            if "extract_file_path" in pattern_dict:
                pattern = pattern_dict["pattern"]
                for match in pattern.finditer(raw_output):
                    result["file_path"] = pattern_dict["extract_file_path"](match)
                    if "extract_line_number" in pattern_dict:
                        result["line_number"] = pattern_dict["extract_line_number"](match)
                    break
        
        return result

    def _extract_error_details(self, raw_output: str) -> Dict[str, Any]:
        """Extracts error details from build output."""
        result = {
            "error_type": "Unknown",
            "error_category": "Other",
            "message": "",
            "suggested_fix": "",
            "involved_symbols": []
        }
        
        # Try to find a matching error pattern
        for pattern_dict in self.patterns:
            if "error_type" in pattern_dict:
                pattern = pattern_dict["pattern"]
                match = pattern.search(raw_output)
                if match:
                    result["error_type"] = pattern_dict["error_type"]
                    result["error_category"] = pattern_dict["error_category"]
                    result["suggested_fix"] = pattern_dict["suggested_fix"]
                    
                    if "extract_message" in pattern_dict:
                        result["message"] = pattern_dict["extract_message"](match)
                    
                    if "extract_symbol" in pattern_dict:
                        symbols = pattern_dict["extract_symbol"](match)
                        if isinstance(symbols, list):
                            result["involved_symbols"] = symbols
                        else:
                            result["involved_symbols"] = [symbols]
                    
                    break
        
        # If no specific error message was found, try to extract a general one
        if not result["message"]:
            for pattern_dict in self.patterns:
                if "extract_message" in pattern_dict and "error_type" not in pattern_dict:
                    pattern = pattern_dict["pattern"]
                    match = pattern.search(raw_output)
                    if match:
                        result["message"] = pattern_dict["extract_message"](match)
                        break
        
        # If still no message, use a default one
        if not result["message"]:
            result["message"] = "Unknown error occurred during build or test execution"
        
        return result

    def parse_output(self, raw_output: str) -> List[ParsedError]:
        """Parses raw build output using regex patterns."""
        if not raw_output:
            logger.info("Build output is empty. No errors to parse.")
            return []

        if "BUILD SUCCESSFUL" in raw_output and "BUILD FAILED" not in raw_output:
            logger.info("Build output indicates success. No errors to parse.")
            return []

        logger.info("Parsing build output with regex patterns.")
        
        # Extract file path and line number
        location_info = self._extract_file_path_and_line(raw_output)
        
        # Extract error details
        error_details = self._extract_error_details(raw_output)
        
        # Combine the information
        error = ParsedError(
            file_path=location_info["file_path"],
            line_number=location_info["line_number"],
            message=error_details["message"],
            error_type=error_details["error_type"],
            involved_symbols=error_details["involved_symbols"],
            error_category=error_details["error_category"],
            suggested_fix=error_details["suggested_fix"]
        )
        
        logger.info(f"Parsed error: {error.error_type} - {error.error_category}")
        return [error]
