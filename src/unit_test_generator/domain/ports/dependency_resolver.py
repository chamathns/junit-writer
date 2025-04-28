"""
Port interface for dependency resolver.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple


class DependencyResolverPort(ABC):
    """
    Port interface for dependency resolver.
    """

    @abstractmethod
    def resolve_dependencies(self, symbols: List[str], weights: Dict[str, float], target_module: str) -> List[Tuple[str, float]]:
        """
        Resolve dependencies for a list of symbols.

        Args:
            symbols: List of symbols to resolve dependencies for
            weights: Dictionary mapping symbols to their weights
            target_module: Target module to resolve dependencies for

        Returns:
            List of tuples containing dependency file paths and their relevance scores
        """
        pass
