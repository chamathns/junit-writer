from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class ParsedError:
    """Structured representation of a compilation or test error."""
    file_path: Optional[str] = None # Relative path preferred
    line_number: Optional[int] = None
    message: str = ""
    error_type: str = "Unknown" # e.g., 'Compilation', 'TestFailure', 'Runtime'
    involved_symbols: List[str] = field(default_factory=list)
    error_category: str = "Other" # e.g., 'UnresolvedReference', 'TypeMismatch'
    suggested_fix: str = "" # e.g., 'Add missing import'

class ErrorParserPort(ABC):
    """Interface for parsing build/test output to extract errors."""

    @abstractmethod
    def parse_output(self, raw_output: str) -> List[ParsedError]:
        """
        Parses raw build/test output string.

        Args:
            raw_output: The combined stdout/stderr from the build tool.

        Returns:
            A list of structured ParsedError objects found in the output.
        """
        pass