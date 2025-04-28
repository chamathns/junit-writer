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

        try:
            # Create a goal for test generation
            goal = Goal(
                name="generate_test",
                description=f"Generate unit tests for {target_file_rel_path}",
                success_criteria=["test_code_generated", "test_file_written"]
            )

            # Read the source file content
            target_file_abs_path = self.repo_root / target_file_rel_path
            if not self.file_system.exists(str(target_file_abs_path)):
                return {
                    "status": "error",
                    "message": f"Target source file not found: {target_file_abs_path}"
                }

            file_content = self.file_system.read_file(str(target_file_abs_path))
            if not file_content or file_content.isspace():
                return {
                    "status": "error",
                    "message": "Target file is empty or whitespace-only"
                }

            # Check for existing test file
            from unit_test_generator.application.services.test_output_path_resolver import TestOutputPathResolver
            path_resolver = TestOutputPathResolver(self.config, self.repo_root)
            path_resolver.set_file_system(self.file_system)
            existing_test_file = path_resolver.find_existing_test_file(target_file_rel_path)
            update_mode = existing_test_file is not None

            # Prepare initial state
            initial_state = {
                "target_file_rel_path": target_file_rel_path,
                "target_file_abs_path": str(target_file_abs_path),
                "repo_root": str(self.repo_root),
                "file_content": file_content,
                "update_mode": update_mode,
                "existing_test_file": existing_test_file,
                "language": self.config.get('generation', {}).get('target_language', 'Kotlin'),
                "framework": self.config.get('generation', {}).get('target_framework', 'JUnit5 with MockK')
            }

            logger.info(f"Starting execution of goal: {goal.name}")
            logger.info(f"Initial state: {initial_state}")

            # Execute the goal using the agent coordinator
            result_state = self.agent_coordinator.execute_goal(goal, initial_state)

            logger.info(f"Goal execution completed with success={result_state.success}")

            # Extract results from the final state
            if result_state.success:
                return {
                    "status": "success",
                    "output_path": result_state.data.get("test_file_path"),
                    "message": "Test generation completed successfully"
                }
            else:
                return {
                    "status": "error",
                    "message": result_state.data.get("error_message", "Unknown error during agent-based test generation")
                }
        except Exception as e:
            logger.error(f"Error in agent-based test generation: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error in agent-based test generation: {str(e)}"
            }
