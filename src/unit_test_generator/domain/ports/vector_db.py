from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class VectorDBPort(ABC):
    """Interface for interacting with a vector database."""

    @abstractmethod
    def upsert_documents(self, doc_ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]]):
        """Adds or updates multiple documents with their embeddings and metadata."""
        pass

    @abstractmethod
    def find_similar(self, embedding: List[float], n_results: int, filter_metadata: Optional[Dict[str, Any]] = None) -> \
    List[Dict[str, Any]]:
        """Finds similar documents based on embedding."""
        pass

    # Add other methods as needed (e.g., delete, get_by_id, count)
    @abstractmethod
    def count(self) -> int:
        """Returns the number of documents in the collection."""
        pass
