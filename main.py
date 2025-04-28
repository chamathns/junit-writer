import yaml
import logging
import sys
import os
from pathlib import Path

# Ensure the src directory is in the Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Now import components
from unit_test_generator.infrastructure.adapters.file_system_adapter import FileSystemAdapter
from unit_test_generator.infrastructure.adapters.embedding.sentence_transformer_adapter import \
    SentenceTransformerAdapter
from unit_test_generator.infrastructure.adapters.vector_db.chroma_adapter import ChromaDBAdapter
from unit_test_generator.application.use_cases.index_repository import IndexRepositoryUseCase


# --- Configuration Loading ---
def load_config(config_path="config/application.yml"):
    """Loads YAML configuration file."""
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        # Resolve relative paths in config relative to project root
        repo_path = config_data.get('repository', {}).get('root_path', '.')
        config_data['repository']['root_path'] = str((project_root / repo_path).resolve())

        index_path = config_data.get('indexing', {}).get('index_file_path', 'var/index/repository_index.json')
        config_data['indexing']['index_file_path'] = str((project_root / index_path).resolve())

        db_path = config_data.get('vector_db', {}).get('path', 'var/rag_db/chroma')
        config_data['vector_db']['path'] = str((project_root / db_path).resolve())

        log_path = config_data.get('logging', {}).get('log_file')
        if log_path:
            config_data['logging']['log_file'] = str((project_root / log_path).resolve())
            Path(config_data['logging']['log_file']).parent.mkdir(parents=True, exist_ok=True)

        return config_data
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration from {config_path}: {e}", file=sys.stderr)
        sys.exit(1)


# --- Logging Setup ---
def setup_logging(config):
    """Configures logging based on the loaded configuration."""
    log_config = config.get('logging', {})
    level = getattr(logging, log_config.get('level', 'INFO').upper(), logging.INFO)
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_file = log_config.get('log_file')

    handlers = [logging.StreamHandler(sys.stdout)]  # Log to console by default
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(level=level, format=log_format, handlers=handlers)
    # Suppress overly verbose logs from dependencies if needed
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # ChromaDB uses httpx


# --- Main Execution ---
if __name__ == "__main__":
    print("Loading configuration...")
    config = load_config()

    print("Setting up logging...")
    setup_logging(config)
    logger = logging.getLogger(__name__)  # Get logger after setup

    logger.info("--- Starting Unit Test Generator Indexing ---")

    # --- Create necessary directories ---
    # Ensure var directories exist based on resolved paths
    Path(config['indexing']['index_file_path']).parent.mkdir(parents=True, exist_ok=True)
    Path(config['vector_db']['path']).mkdir(parents=True, exist_ok=True)
    if config.get('logging', {}).get('log_file'):
        Path(config['logging']['log_file']).parent.mkdir(parents=True, exist_ok=True)

    # --- Instantiate Adapters (Dependencies) ---
    logger.info("Instantiating infrastructure adapters...")
    try:
        file_system = FileSystemAdapter()
        # Pass only the relevant config sections to adapters
        embedding_service = SentenceTransformerAdapter(config)
        vector_db = ChromaDBAdapter(config)
    except Exception as e:
        logger.critical(f"Failed to instantiate infrastructure adapters: {e}", exc_info=True)
        sys.exit(1)

    # --- Instantiate Use Case ---
    logger.info("Instantiating IndexRepositoryUseCase...")
    try:
        index_use_case = IndexRepositoryUseCase(
            file_system=file_system,
            embedding_service=embedding_service,
            vector_db=vector_db,
            config=config  # Pass the full config or just relevant parts
        )
    except Exception as e:
        logger.critical(f"Failed to instantiate IndexRepositoryUseCase: {e}", exc_info=True)
        sys.exit(1)

    # --- Execute Use Case ---
    logger.info("Executing indexing use case...")
    try:
        # Set force_rescan=True if you always want to rescan regardless of index file
        # Set populate_rag=True to enable embedding and DB population
        result = index_use_case.execute(force_rescan=False, populate_rag=True)
        logger.info(f"Indexing execution finished with status: {result.get('status')}")
        logger.info(f"Indexed modules: {result.get('indexed_modules')}")
    except Exception as e:
        logger.critical(f"An error occurred during use case execution: {e}", exc_info=True)
        sys.exit(1)

    logger.info("--- Indexing Process Complete ---")
