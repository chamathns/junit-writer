import logging
import sys
import argparse
from typing import Dict, Any

# Import necessary factories and use cases
from unit_test_generator.cli.adapter_factory import (
    create_file_system_adapter,
    create_embedding_service,
    create_vector_db,
)
from unit_test_generator.application.use_cases.index_repository import IndexRepositoryUseCase

logger = logging.getLogger(__name__)

def handle_index(args: argparse.Namespace, config: Dict[str, Any]):
    """Handles the 'index' command logic."""
    logger.info("--- Starting Indexing Process ---")
    try:
        # Instantiate necessary adapters via factory
        file_system = create_file_system_adapter()
        embedding_service = create_embedding_service(config)
        vector_db = create_vector_db(config)

        # Instantiate use case
        index_use_case = IndexRepositoryUseCase(
            file_system=file_system,
            embedding_service=embedding_service,
            vector_db=vector_db,
            config=config
        )

        # Execute use case
        populate_rag_flag = not args.no_rag
        logger.info(f"Executing index use case... (Force Rescan: {args.force_rescan}, Populate RAG: {populate_rag_flag})")
        result = index_use_case.execute(force_rescan=args.force_rescan, populate_rag=populate_rag_flag)

        logger.info(f"Indexing execution finished with status: {result.get('status')}")
        logger.info(f"Indexed modules: {result.get('indexed_modules')}")

    except Exception as e:
        logger.critical(f"An error occurred during indexing: {e}", exc_info=True)
        sys.exit(1) # Exit if indexing fails critically
    logger.info("--- Indexing Process Complete ---")