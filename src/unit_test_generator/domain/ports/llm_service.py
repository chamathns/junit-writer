from abc import ABC, abstractmethod
from typing import Dict, Any

class LLMServicePort(ABC):
    """Interface for interacting with a Large Language Model service."""

    @abstractmethod
    def generate_tests(self, context_payload: Dict[str, Any]) -> str:
        """
        Generates unit test code based on the provided context.

        Args:
            context_payload: A dictionary containing structured context, including
                             target file info and similar examples.

        Returns:
            The generated unit test code as a string.
            Returns an empty string or raises an exception on failure.
        """
        pass