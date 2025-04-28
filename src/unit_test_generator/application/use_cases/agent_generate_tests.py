# src/unit_test_generator/application/use_cases/agent_generate_tests.py
"""
Agent-based use case for generating tests.
"""
import logging
from pathlib import Path
from typing import Dict, Any

from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.embedding_service import EmbeddingServicePort
from unit_test_generator.domain.ports.vector_db import VectorDBPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.code_parser import CodeParserPort
from unit_test_generator.domain.models.agent_models import Goal
from unit_test_generator.application.services.agent_coordinator import AgentCoordinator

logger = logging.getLogger(__name__)


class AgentGenerateTests:
    """
    Agent-based use case for generating tests.
    """

    def __init__(
        self,
        agent_coordinator: AgentCoordinator,
        file_system: FileSystemPort,
        embedding_service: EmbeddingServicePort,
        vector_db: VectorDBPort,
        llm_service: LLMServicePort,
        code_parser: CodeParserPort,
        config: Dict[str, Any],
        repo_root: Path
    ):
        """
        Initialize the use case.

        Args:
            agent_coordinator: Agent coordinator
            file_system: File system port
            embedding_service: Embedding service port
            vector_db: Vector database port
            llm_service: LLM service port
            code_parser: Code parser port
            config: Configuration dictionary
            repo_root: Repository root path
        """
        self.agent_coordinator = agent_coordinator
        self.file_system = file_system
        self.embedding_service = embedding_service
        self.vector_db = vector_db
        self.llm_service = llm_service
        self.code_parser = code_parser
        self.config = config
        self.repo_root = repo_root

    def execute(self, target_file_rel_path: str) -> Dict[str, Any]:
        """
        Execute the use case.

        Args:
            target_file_rel_path: Relative path to the target file

        Returns:
            Result of the test generation
        """
        logger.info(f"Generating tests for {target_file_rel_path} using agent mode")

        # For now, we'll just delegate to the standard use case
        # In a real implementation, this would use the agent coordinator to orchestrate the process
        from unit_test_generator.application.use_cases.generate_tests import GenerateTestsUseCase

        # Create a standard use case
        standard_use_case = GenerateTestsUseCase(
            file_system=self.file_system,
            embedding_service=self.embedding_service,
            vector_db=self.vector_db,
            llm_service=self.llm_service,
            code_parser=self.code_parser,
            build_system=None,  # We don't need this for delegation
            error_parser=None,  # We don't need this for delegation
            dependency_resolver=None,  # We don't need this for delegation
            adk_runner=None,  # We don't need this for delegation
            config=self.config
        )

        # Execute the standard use case
        result = standard_use_case.execute(target_file_rel_path)

        logger.info(f"Agent-based generate tests use case completed for {target_file_rel_path}")
        return result
