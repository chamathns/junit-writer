# src/unit_test_generator/application/services/mode_selector.py
"""
Service for selecting between standard and agent modes.
"""
import logging
from typing import Dict, Any, Type, Optional

from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.embedding_service import EmbeddingServicePort
from unit_test_generator.domain.ports.vector_db import VectorDBPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.code_parser import CodeParserPort
from unit_test_generator.domain.ports.build_system import BuildSystemPort
from unit_test_generator.domain.ports.error_parser import ErrorParserPort

logger = logging.getLogger(__name__)


class ModeSelector:
    """
    Service for selecting between standard and agent modes.
    """

    def __init__(self, config: Dict[str, Any], cli_mode: Optional[str] = None):
        """
        Initialize the mode selector.

        Args:
            config: Configuration dictionary
            cli_mode: Mode specified via CLI, overrides config if provided
        """
        self.config = config

        # Determine mode: CLI argument takes precedence over config
        config_mode = config.get("orchestrator", {}).get("defaultMode", "standard")
        self.mode = cli_mode if cli_mode else config_mode

        # Validate mode
        if self.mode not in ["standard", "agent"]:
            logger.warning(f"Invalid mode '{self.mode}', defaulting to 'standard'")
            self.mode = "standard"

        logger.info(f"Mode selector initialized with mode: {self.mode}")

    def is_agent_mode(self) -> bool:
        """
        Check if agent mode is enabled.

        Returns:
            True if agent mode is enabled, False otherwise
        """
        # Check if mode is set to agent and the agents configuration is enabled
        agents_enabled = self.config.get("agents", {}).get("enabled", True)
        return self.mode == "agent" and agents_enabled

    def get_use_case(self, use_case_type: str, **kwargs) -> Any:
        """
        Get the appropriate use case implementation based on the selected mode.

        Args:
            use_case_type: The type of use case to get
            **kwargs: Additional arguments for the use case

        Returns:
            An instance of the use case

        Raises:
            ValueError: If the use case type is unknown
        """
        if self.is_agent_mode():
            return self._get_agent_use_case(use_case_type, **kwargs)
        else:
            return self._get_standard_use_case(use_case_type, **kwargs)

    def _get_standard_use_case(self, use_case_type: str, **kwargs) -> Any:
        """
        Get a standard use case implementation.

        Args:
            use_case_type: The type of use case to get
            **kwargs: Additional arguments for the use case

        Returns:
            An instance of the standard use case

        Raises:
            ValueError: If the use case type is unknown
        """
        # Import here to avoid circular imports
        from unit_test_generator.application.use_cases.index_repository import IndexRepositoryUseCase
        from unit_test_generator.application.use_cases.generate_tests import GenerateTestsUseCase
        from unit_test_generator.application.use_cases.self_healing import SelfHealingUseCase

        if use_case_type == "index_repository":
            return IndexRepositoryUseCase(
                file_system=kwargs.get("file_system"),
                embedding_service=kwargs.get("embedding_service"),
                vector_db=kwargs.get("vector_db"),
                config=self.config
            )
        elif use_case_type == "generate_tests":
            return GenerateTestsUseCase(
                file_system=kwargs.get("file_system"),
                embedding_service=kwargs.get("embedding_service"),
                vector_db=kwargs.get("vector_db"),
                llm_service=kwargs.get("llm_service"),
                code_parser=kwargs.get("code_parser"),
                dependency_resolver=kwargs.get("dependency_resolver"),
                build_system=kwargs.get("build_system"),
                error_parser=kwargs.get("error_parser"),
                adk_runner=kwargs.get("adk_runner"),
                config=self.config
            )
        elif use_case_type == "self_healing":
            return SelfHealingUseCase(
                file_system=kwargs.get("file_system"),
                build_system=kwargs.get("build_system"),
                error_parser=kwargs.get("error_parser"),
                llm_service=kwargs.get("llm_service"),
                code_parser=kwargs.get("code_parser"),
                config=self.config
            )
        else:
            raise ValueError(f"Unknown use case type: {use_case_type}")

    def _get_agent_use_case(self, use_case_type: str, **kwargs) -> Any:
        """
        Get an agent-based use case implementation.

        Args:
            use_case_type: The type of use case to get
            **kwargs: Additional arguments for the use case

        Returns:
            An instance of the agent-based use case

        Raises:
            ValueError: If the use case type is unknown
        """
        # Import here to avoid circular imports
        from unit_test_generator.application.use_cases.index_repository import IndexRepositoryUseCase
        from unit_test_generator.application.use_cases.agent_generate_tests import AgentGenerateTests
        from unit_test_generator.application.use_cases.self_healing import SelfHealingUseCase

        if use_case_type == "index_repository":
            # Use standard implementation for now
            return IndexRepositoryUseCase(
                file_system=kwargs.get("file_system"),
                embedding_service=kwargs.get("embedding_service"),
                vector_db=kwargs.get("vector_db"),
                config=self.config
            )
        elif use_case_type == "generate_tests":
            return AgentGenerateTests(
                agent_coordinator=kwargs.get("agent_coordinator"),
                file_system=kwargs.get("file_system"),
                embedding_service=kwargs.get("embedding_service"),
                vector_db=kwargs.get("vector_db"),
                llm_service=kwargs.get("llm_service"),
                code_parser=kwargs.get("code_parser"),
                config=self.config,
                repo_root=kwargs.get("repo_root")
            )
        elif use_case_type == "self_healing":
            # Use standard implementation for now
            return SelfHealingUseCase(
                file_system=kwargs.get("file_system"),
                build_system=kwargs.get("build_system"),
                error_parser=kwargs.get("error_parser"),
                llm_service=kwargs.get("llm_service"),
                code_parser=kwargs.get("code_parser"),
                config=self.config
            )
        else:
            raise ValueError(f"Unknown use case type: {use_case_type}")


class UseCaseFactory:
    """
    Factory for creating use cases.
    """

    def __init__(
        self,
        mode_selector: ModeSelector,
        file_system: FileSystemPort,
        embedding_service: EmbeddingServicePort,
        vector_db: VectorDBPort,
        llm_service: LLMServicePort,
        code_parser: CodeParserPort,
        build_system: BuildSystemPort,
        error_parser: ErrorParserPort,
        agent_coordinator: Optional[Any] = None,
        config: Dict[str, Any] = None
    ):
        """
        Initialize the use case factory.

        Args:
            mode_selector: Mode selector service
            file_system: File system port
            embedding_service: Embedding service port
            vector_db: Vector database port
            llm_service: LLM service port
            code_parser: Code parser port
            build_system: Build system port
            error_parser: Error parser port
            agent_coordinator: Optional agent coordinator
            config: Configuration dictionary
        """
        self.mode_selector = mode_selector
        self.file_system = file_system
        self.embedding_service = embedding_service
        self.vector_db = vector_db
        self.llm_service = llm_service
        self.code_parser = code_parser
        self.build_system = build_system
        self.error_parser = error_parser
        self.agent_coordinator = agent_coordinator
        self.config = config or {}

    def create_use_case(self, use_case_type: str, **kwargs) -> Any:
        """
        Create a use case of the specified type.

        Args:
            use_case_type: The type of use case to create
            **kwargs: Additional arguments for the use case

        Returns:
            An instance of the use case
        """
        # Combine default dependencies with any provided in kwargs
        dependencies = {
            "file_system": self.file_system,
            "embedding_service": self.embedding_service,
            "vector_db": self.vector_db,
            "llm_service": self.llm_service,
            "code_parser": self.code_parser,
            "build_system": self.build_system,
            "error_parser": self.error_parser,
            "agent_coordinator": self.agent_coordinator,
            "config": self.config
        }
        dependencies.update(kwargs)

        return self.mode_selector.get_use_case(use_case_type, **dependencies)
