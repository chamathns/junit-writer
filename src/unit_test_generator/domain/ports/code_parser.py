from abc import ABC, abstractmethod
from typing import List, Dict, Tuple

class CodeParserPort(ABC):
    """Interface for parsing source code to extract imports and usage."""

    @abstractmethod
    def parse(self, content: str, file_path: str) -> Tuple[List[str], Dict[str, float]]:
        """
        Parses source code content.

        Args:
            content: The source code as a string.
            file_path: The path of the file being parsed (for context/logging).

        Returns:
            A tuple containing:
            - List[str]: A list of import strings found (e.g., "com.example.UserService").
            - Dict[str, float]: A dictionary mapping imported symbols/paths to a
                                usage weight (higher means used more).
        """
        pass