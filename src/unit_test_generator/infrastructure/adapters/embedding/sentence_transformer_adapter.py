import logging
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import numpy as np

from unit_test_generator.domain.ports.embedding_service import EmbeddingServicePort

logger = logging.getLogger(__name__)


class SentenceTransformerAdapter(EmbeddingServicePort):
    """Embedding service implementation using Sentence Transformers."""

    def __init__(self, config: Dict[str, Any]):
        self.model_name = config['embedding']['model_name']
        try:
            logger.info(f"Loading Sentence Transformer model: {self.model_name}")
            # Consider adding device selection (e.g., 'cuda' if available)
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Sentence Transformer model '{self.model_name}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Sentence Transformer model '{self.model_name}': {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize SentenceTransformer model: {e}") from e

    def generate_embedding(self, text: str) -> List[float]:
        """Generates an embedding vector for the given text."""
        try:
            # encode() returns a numpy array, convert to list
            embedding = self.model.encode(text, convert_to_numpy=False)
            # Ensure it's a flat list of floats
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            if isinstance(embedding, list) and all(isinstance(x, float) for x in embedding):
                return embedding
            else:
                logger.error(f"Unexpected embedding format for text: {type(embedding)}")
                # Handle error case appropriately, maybe return empty list or raise specific error
                return []
        except Exception as e:
            logger.error(f"Error generating embedding for text: {e}", exc_info=True)
            return []  # Return empty list on error

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a batch of texts."""
        try:
            logger.debug(f"Generating embeddings for {len(texts)} texts...")
            # Convert to numpy to ensure we get a standard format
            embeddings = self.model.encode(texts, convert_to_numpy=True,
                                           show_progress_bar=False)  # Progress bar can be noisy

            # Ensure it's a list of lists of floats
            if isinstance(embeddings, np.ndarray):
                # If it's a 2D array (batch of embeddings)
                if len(embeddings.shape) == 2:
                    result = [emb.tolist() for emb in embeddings]
                else:
                    # Single embedding
                    result = [embeddings.tolist()]
            else:
                # Handle case where it might be a list of tensors
                result = [emb.tolist() if hasattr(emb, 'tolist') else list(emb) for emb in embeddings]

            logger.debug(f"Generated {len(result)} embeddings.")
            return result
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}", exc_info=True)
            return [[] for _ in texts]  # Return list of empty lists on error