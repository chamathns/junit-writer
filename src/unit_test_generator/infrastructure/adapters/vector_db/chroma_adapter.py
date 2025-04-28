import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions  # Import for configuring collection

from unit_test_generator.domain.ports.vector_db import VectorDBPort

logger = logging.getLogger(__name__)


class ChromaDBAdapter(VectorDBPort):
    """Vector DB implementation using ChromaDB."""

    def __init__(self, config: Dict[str, Any]):
        self.db_path = config['vector_db']['path']
        self.collection_name = config['vector_db']['collection_name']
        self.embedding_model_name = config['embedding']['model_name']  # Needed to configure collection
        self.distance_metric = config['vector_db'].get('distance_metric', 'cosine')  # Default to cosine

        try:
            logger.info(f"Initializing ChromaDB client with path: {self.db_path}")
            self.client = chromadb.PersistentClient(path=self.db_path)

            # Define the embedding function based on the config (must match the EmbeddingService)
            # This tells Chroma how to handle potential future queries if embeddings aren't provided
            chroma_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model_name
            )

            logger.info(f"Getting or creating ChromaDB collection: {self.collection_name}")
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=chroma_embedding_fn,  # Associate the function type with the collection
                metadata={"hnsw:space": self.distance_metric}  # Configure distance metric
            )
            logger.info(f"ChromaDB collection '{self.collection_name}' ready. Count: {self.collection.count()}")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize ChromaDB: {e}") from e

    def upsert_documents(self, doc_ids: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]]):
        """Adds or updates multiple documents with their embeddings and metadata."""
        if not doc_ids:
            logger.warning("upsert_documents called with empty lists.")
            return

        # ChromaDB requires metadata values to be str, int, float, or bool.
        # Ensure metadata is compliant.
        sanitized_metadatas = []
        for meta in metadatas:
            sanitized = {}
            for k, v in meta.items():
                if isinstance(v, (str, int, float, bool)):
                    sanitized[k] = v
                elif v is None:
                    continue  # Skip None values or replace with placeholder if needed
                else:
                    # Convert other types (like lists) to strings or handle appropriately
                    sanitized[k] = str(v)
                    logger.debug(f"Metadata value for key '{k}' converted to string: {v}")
            sanitized_metadatas.append(sanitized)

        try:
            logger.debug(f"Upserting {len(doc_ids)} documents into collection '{self.collection_name}'...")
            # Provide embeddings directly since we generated them externally
            self.collection.upsert(
                ids=doc_ids,
                embeddings=embeddings,
                metadatas=sanitized_metadatas
            )
            logger.info(f"Successfully upserted {len(doc_ids)} documents.")
        except Exception as e:
            logger.error(f"Error upserting documents into ChromaDB: {e}", exc_info=True)
            # Depending on the error, you might want partial success handling or re-raising

    def find_similar(self, embedding: List[float], n_results: int, filter_metadata: Optional[Dict[str, Any]] = None) -> \
    List[Dict[str, Any]]:
        """Finds similar documents based on embedding."""
        try:
            logger.debug(f"Querying collection '{self.collection_name}' for {n_results} similar results.")
            results = self.collection.query(
                query_embeddings=[embedding],  # Query expects a list of embeddings
                n_results=n_results,
                where=filter_metadata,  # Optional filter dictionary
                include=['metadatas', 'distances', 'documents']  # Include desired fields
            )
            logger.debug(f"Query returned {len(results.get('ids', [[]])[0])} results.")

            # Process results into a more usable list of dictionaries
            output = []
            if results and results.get('ids') and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    entry = {
                        "id": doc_id,
                        "metadata": results['metadatas'][0][i] if results.get('metadatas') else None,
                        "distance": results['distances'][0][i] if results.get('distances') else None,
                        "document": results['documents'][0][i] if results.get('documents') else None,
                    }
                    output.append(entry)
            return output

        except Exception as e:
            logger.error(f"Error querying ChromaDB: {e}", exc_info=True)
            return []

    def count(self) -> int:
        """Returns the number of documents in the collection."""
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Error getting count from ChromaDB collection '{self.collection_name}': {e}", exc_info=True)
            return -1  # Indicate error
