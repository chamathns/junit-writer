import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

# Domain Ports
from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.embedding_service import EmbeddingServicePort
from unit_test_generator.domain.ports.vector_db import VectorDBPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.code_parser import CodeParserPort
from unit_test_generator.domain.ports.build_system import BuildSystemPort
from unit_test_generator.domain.ports.error_parser import ErrorParserPort

# Application Services & Orchestrator
from unit_test_generator.application.services.dependency_resolver import DependencyResolverService
from unit_test_generator.application.services.context_builder import ContextBuilder
from unit_test_generator.application.services.test_output_path_resolver import TestOutputPathResolver
from unit_test_generator.application.orchestrators.test_generation_orchestrator import TestGenerationOrchestrator, TestGenerationError

# ADK Components (Type Hinting)
from google.adk.tools import BaseTool
from unit_test_generator.infrastructure.adk_tools.runner import ADKRunnerAdapter, SimplifiedADKRunner

logger = logging.getLogger(__name__)

class GenerateTestsUseCase:
    """
    Use case entry point for generating unit tests.
    Sets up dependencies and delegates execution to the TestGenerationOrchestrator.
    """
    def __init__(
        self,
        # --- Ports ---
        file_system: FileSystemPort,
        embedding_service: EmbeddingServicePort,
        vector_db: VectorDBPort,
        llm_service: LLMServicePort,
        code_parser: CodeParserPort,
        build_system: BuildSystemPort,
        error_parser: ErrorParserPort,
        # --- Services ---
        dependency_resolver: DependencyResolverService,
        # --- Optional ADK Components ---
        adk_runner: Optional[Union[ADKRunnerAdapter, SimplifiedADKRunner]],
        # --- Config ---
        config: Dict[str, Any],
    ):
        """Initializes the use case with all necessary dependencies."""
        self.file_system = file_system
        self.embedding_service = embedding_service
        self.vector_db = vector_db
        self.llm_service = llm_service
        self.code_parser = code_parser
        self.build_system = build_system
        self.error_parser = error_parser
        self.dependency_resolver = dependency_resolver
        self.adk_runner = adk_runner
        self.config = config
        self.repo_root = Path(self.config['repository']['root_path']).resolve()
        logger.debug("GenerateTestsUseCase initialized.")


    def execute(self, target_file_rel_path: str) -> Dict[str, Any]:
        """
        Executes the test generation process by orchestrating dependencies.

        Args:
            target_file_rel_path: Relative path to the source file needing tests.

        Returns:
            A dictionary indicating the outcome (status, output_path/message).
        """
        logger.info(f"GenerateTestsUseCase executing for: {target_file_rel_path}")
        try:
            # 1. Instantiate helper components needed by the orchestrator
            path_resolver = TestOutputPathResolver(self.config, self.repo_root)
            context_builder = ContextBuilder(self.config, self.repo_root, self.file_system)

            # 2. Instantiate the orchestrator, injecting all dependencies
            orchestrator = TestGenerationOrchestrator(
                file_system=self.file_system,
                embedding_service=self.embedding_service,
                vector_db=self.vector_db,
                llm_service=self.llm_service,
                code_parser=self.code_parser,
                dependency_resolver=self.dependency_resolver,
                context_builder=context_builder,
                path_resolver=path_resolver,
                # Pass ADK runner directly
                adk_runner=self.adk_runner,
                config=self.config,
                repo_root=self.repo_root,
            )

            # 3. Delegate execution to the orchestrator
            result = orchestrator.run(target_file_rel_path)
            return result

        except TestGenerationError as e:
             # Catch specific orchestration errors if needed, though orchestrator handles internal ones
             logger.error(f"Orchestration failed at UseCase level: {e.message}")
             return {"status": e.status, "message": e.message}
        except Exception as e:
            logger.critical(f"Unexpected error in GenerateTestsUseCase for {target_file_rel_path}: {e}", exc_info=True)
            return {"status": "error", "message": f"Unexpected UseCase error: {e}"}