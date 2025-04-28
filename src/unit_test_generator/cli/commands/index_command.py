import logging
import sys
import argparse
from typing import Dict, Any

# Import necessary factories and use cases
from unit_test_generator.cli.adapter_factory import (
    create_file_system_adapter,
    create_embedding_service,
    create_vector_db,
    create_ui_service,
)
from unit_test_generator.application.use_cases.index_repository import IndexRepositoryUseCase
from unit_test_generator.application.services.ui_service import UIService
from unit_test_generator.domain.ports.ui_service import LogLevel

logger = logging.getLogger(__name__)

def handle_index(args: argparse.Namespace, config: Dict[str, Any]):
    """Handles the 'index' command logic."""
    # Create UI service
    ui_adapter = create_ui_service(config)
    ui = UIService(ui_adapter)

    # Display welcome panel
    ui.panel("JUnit Writer - Repository Indexing", "Welcome", border_style="cyan")

    # Create a status display
    status = ui.status("Starting indexing process...")

    try:
        # Instantiate necessary adapters via factory
        status.update("Creating file system adapter...")
        file_system = create_file_system_adapter()

        status.update("Creating embedding service...")
        embedding_service = create_embedding_service(config)

        status.update("Creating vector database...")
        vector_db = create_vector_db(config)

        # Instantiate use case
        status.update("Initializing indexing use case...")
        index_use_case = IndexRepositoryUseCase(
            file_system=file_system,
            embedding_service=embedding_service,
            vector_db=vector_db,
            config=config
        )

        # Execute use case
        populate_rag_flag = not args.no_rag
        status.update(f"Executing index use case... (Force Rescan: {args.force_rescan}, Populate RAG: {populate_rag_flag})")
        result = index_use_case.execute(force_rescan=args.force_rescan, populate_rag=populate_rag_flag)

        # Display results
        status.stop()
        ui.log(f"Indexing execution finished with status: {result.get('status')}", LogLevel.SUCCESS)

        # Create a table for indexed modules
        if 'indexed_modules' in result and result['indexed_modules'] and isinstance(result['indexed_modules'], dict):
            ui.log("Indexed modules:", LogLevel.INFO)
            table = ui.table(["Module", "Source Files", "Test Files"])
            for module, details in result.get('indexed_modules', {}).items():
                table.add_row(
                    module,
                    str(details.get('source_files', 0)),
                    str(details.get('test_files', 0))
                )
            table.render()
        elif 'indexed_modules' in result:
            # Handle the case where indexed_modules is not a dictionary
            ui.log(f"Indexed {result.get('indexed_modules', 0)} modules", LogLevel.INFO)

        ui.panel("Indexing completed successfully!", "Success", border_style="green")

    except Exception as e:
        status.stop()
        ui.log(f"An error occurred during indexing: {e}", LogLevel.ERROR)
        logger.critical(f"An error occurred during indexing: {e}", exc_info=True)
        ui.panel(f"Error: {str(e)}", "Indexing Failed", border_style="red")
        sys.exit(1) # Exit if indexing fails critically