from abc import ABC, abstractmethod
from typing import List


class EmbeddingServicePort(ABC):
    """Interface for generating text embeddings."""

    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generates an embedding vector for the given text."""
        pass

    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a batch of texts."""
        pass
