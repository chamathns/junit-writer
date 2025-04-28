"""
Factory for creating agents.
"""
import logging
from typing import Dict, Any, Type

from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.embedding_service import EmbeddingServicePort
from unit_test_generator.domain.ports.vector_db import VectorDBPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.code_parser import CodeParserPort
from unit_test_generator.domain.models.agent_models import Agent

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory for creating agents.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        llm_service: LLMServicePort,
        file_system: FileSystemPort,
        embedding_service: EmbeddingServicePort,
        vector_db: VectorDBPort,
        code_parser: CodeParserPort
    ):
        """
        Initialize the agent factory.

        Args:
            config: Configuration dictionary
            llm_service: LLM service port
            file_system: File system port
            embedding_service: Embedding service port
            vector_db: Vector database port
            code_parser: Code parser port
        """
        self.config = config
        self.llm_service = llm_service
        self.file_system = file_system
        self.embedding_service = embedding_service
        self.vector_db = vector_db
        self.code_parser = code_parser
        self.agent_classes = {}  # Will be populated by register_agent

        # Register built-in agents
        self._register_built_in_agents()

    def register_agent(self, agent_type: str, agent_class: Type[Agent]) -> None:
        """
        Register an agent class for a specific type.

        Args:
            agent_type: The type of agent
            agent_class: The agent class
        """
        self.agent_classes[agent_type] = agent_class

    def create_agent(self, agent_type: str) -> Agent:
        """
        Create an agent of the specified type.

        Args:
            agent_type: The type of agent to create

        Returns:
            An instance of the specified agent type

        Raises:
            ValueError: If the agent type is unknown
        """
        logger.info(f"Creating agent of type: {agent_type}")

        if agent_type not in self.agent_classes:
            logger.error(f"Unknown agent type: {agent_type}")
            raise ValueError(f"Unknown agent type: {agent_type}")

        agent_class = self.agent_classes[agent_type]
        logger.info(f"Using agent class: {agent_class.__name__}")

        tools = self._get_tools_for_agent(agent_type)
        logger.info(f"Created tools for agent: {list(tools.keys())}")

        agent = agent_class(agent_type, tools, self.config)
        logger.info(f"Agent {agent_type} created successfully")

        return agent

    def _register_built_in_agents(self) -> None:
        """Register built-in agents."""
        # Import here to avoid circular imports
        from unit_test_generator.application.agents.analyze_agent import AnalyzeAgent
        from unit_test_generator.application.agents.generate_agent import GenerateAgent
        from unit_test_generator.application.agents.fix_agent import FixAgent
        from unit_test_generator.application.agents.index_agent import IndexAgent
        from unit_test_generator.application.agents.reasoning_agent import ReasoningAgent

        self.register_agent("analyze", AnalyzeAgent)
        self.register_agent("generate", GenerateAgent)
        self.register_agent("fix", FixAgent)
        self.register_agent("index", IndexAgent)
        self.register_agent("reasoning", ReasoningAgent)

    def _get_tools_for_agent(self, agent_type: str) -> Dict[str, Any]:
        """
        Get the tools for a specific agent type.

        Args:
            agent_type: The type of agent

        Returns:
            Dictionary of tools for the agent
        """
        logger.info(f"Getting tools for agent type: {agent_type}")

        # Create basic tools available to all agents
        tools = {
            "file_system": self.file_system,
            "llm": self.llm_service,
            "embedding": self.embedding_service,
            "vector_db": self.vector_db,
            "code_parser": self.code_parser
        }

        # Verify tools are not None
        for tool_name, tool in tools.items():
            if tool is None:
                logger.warning(f"Tool {tool_name} is None for agent {agent_type}")
            else:
                logger.info(f"Tool {tool_name} is available for agent {agent_type}: {type(tool).__name__}")

        # Add agent-specific tools
        if agent_type == "analyze":
            # Add analyze-specific tools
            logger.info("Adding analyze-specific tools")
            pass
        elif agent_type == "generate":
            # Add generate-specific tools
            logger.info("Adding generate-specific tools")

            # Import necessary tools
            from unit_test_generator.cli.adapter_factory import (
                create_build_system, create_run_terminal_test_tool,
                create_get_terminal_output_tool, create_list_terminal_processes_tool
            )

            # Create build system
            build_system = create_build_system(self.config)

            # Create terminal test tools
            run_terminal_test_tool = create_run_terminal_test_tool(build_system)
            get_terminal_output_tool = create_get_terminal_output_tool(build_system)
            list_terminal_processes_tool = create_list_terminal_processes_tool(build_system)

            # Add tools to the generate agent
            tools["run_terminal_test"] = run_terminal_test_tool
            tools["get_terminal_output"] = get_terminal_output_tool
            tools["list_terminal_processes"] = list_terminal_processes_tool

            logger.info(f"Added terminal test tools to generate agent")
        elif agent_type == "fix":
            # Add fix-specific tools
            logger.info("Adding fix-specific tools")

            # Import necessary tools
            from unit_test_generator.cli.adapter_factory import (
                create_build_system, create_error_parser, create_run_test_tool,
                create_parse_errors_tool, create_generate_fix_tool, create_intelligent_fix_tool,
                create_run_terminal_test_tool, create_get_terminal_output_tool, create_list_terminal_processes_tool
            )

            # Create build system and error parser
            build_system = create_build_system(self.config)
            error_parser = create_error_parser(self.config, self.llm_service)

            # Create tools for the fix agent
            run_test_tool = create_run_test_tool(build_system)
            parse_errors_tool = create_parse_errors_tool(error_parser)

            # Create dependency resolver for fix tools
            from unit_test_generator.application.services.dependency_resolver import DependencyResolverService
            dependency_resolver = DependencyResolverService(self.file_system, self.config)

            # Create fix tools
            generate_fix_tool = create_generate_fix_tool(self.llm_service, error_parser, dependency_resolver, self.config)

            # Create healing orchestrator if needed
            try:
                # Create error analyzer and fix generator
                from unit_test_generator.application.services.error_analysis_service import ErrorAnalysisService
                from unit_test_generator.application.services.fix_generation_service import FixGenerationService
                from unit_test_generator.application.services.dependency_resolution_service import DependencyResolutionService
                from unit_test_generator.application.services.healing_orchestrator_service import HealingOrchestratorService

                # Create dependency resolution service
                dependency_resolution_service = DependencyResolutionService(
                    file_system=self.file_system,
                    config=self.config
                )

                # Create error analyzer
                error_analyzer = ErrorAnalysisService(
                    llm_service=self.llm_service,
                    dependency_resolver=dependency_resolution_service,
                    config=self.config
                )

                # Create fix generator
                fix_generator = FixGenerationService(
                    llm_service=self.llm_service,
                    config=self.config
                )

                # Create healing orchestrator
                healing_orchestrator = HealingOrchestratorService(
                    error_parser=error_parser,
                    error_analyzer=error_analyzer,
                    dependency_resolver=dependency_resolution_service,
                    fix_generator=fix_generator,
                    file_system=self.file_system,
                    build_system=build_system,
                    config=self.config
                )

                # Create intelligent fix tool
                intelligent_fix_tool = create_intelligent_fix_tool(healing_orchestrator, self.config)
                tools["intelligent_fix"] = intelligent_fix_tool
                logger.info("Added intelligent_fix tool to fix agent")
            except (ImportError, AttributeError) as e:
                logger.warning(f"Could not create intelligent fix tool: {e}")

            # Create terminal test tools
            run_terminal_test_tool = create_run_terminal_test_tool(build_system)
            get_terminal_output_tool = create_get_terminal_output_tool(build_system)
            list_terminal_processes_tool = create_list_terminal_processes_tool(build_system)

            # Add tools to the fix agent
            tools["run_test"] = run_test_tool
            tools["parse_errors"] = parse_errors_tool
            tools["generate_fix"] = generate_fix_tool
            tools["run_terminal_test"] = run_terminal_test_tool
            tools["get_terminal_output"] = get_terminal_output_tool
            tools["list_terminal_processes"] = list_terminal_processes_tool

            logger.info(f"Added {len(tools) - 5} fix-specific tools to fix agent")
        elif agent_type == "index":
            # Add index-specific tools
            logger.info("Adding index-specific tools")
            pass
        elif agent_type == "reasoning":
            # Add reasoning-specific tools
            logger.info("Adding reasoning-specific tools")

            # Import necessary tools
            from unit_test_generator.cli.adapter_factory import (
                create_build_system, create_error_parser, create_run_test_tool,
                create_parse_errors_tool, create_generate_fix_tool, create_intelligent_fix_tool,
                create_run_terminal_test_tool, create_get_terminal_output_tool, create_list_terminal_processes_tool
            )

            # Create build system and error parser
            build_system = create_build_system(self.config)
            error_parser = create_error_parser(self.config, self.llm_service)

            # Create tools for the reasoning agent
            run_test_tool = create_run_test_tool(build_system)
            parse_errors_tool = create_parse_errors_tool(error_parser)

            # Create dependency resolver for reasoning tools
            from unit_test_generator.application.services.dependency_resolver import DependencyResolverService
            dependency_resolver = DependencyResolverService(self.file_system, self.config)

            # Create fix tools
            generate_fix_tool = create_generate_fix_tool(self.llm_service, error_parser, dependency_resolver, self.config)

            # Create terminal test tools
            run_terminal_test_tool = create_run_terminal_test_tool(build_system)
            get_terminal_output_tool = create_get_terminal_output_tool(build_system)
            list_terminal_processes_tool = create_list_terminal_processes_tool(build_system)

            # Create healing orchestrator if needed
            try:
                # Create error analyzer and fix generator
                from unit_test_generator.application.services.error_analysis_service import ErrorAnalysisService
                from unit_test_generator.application.services.fix_generation_service import FixGenerationService
                from unit_test_generator.application.services.dependency_resolution_service import DependencyResolutionService
                from unit_test_generator.application.services.healing_orchestrator_service import HealingOrchestratorService

                # Create dependency resolution service
                dependency_resolution_service = DependencyResolutionService(
                    file_system=self.file_system,
                    config=self.config
                )

                # Create error analyzer
                error_analyzer = ErrorAnalysisService(
                    llm_service=self.llm_service,
                    dependency_resolver=dependency_resolution_service,
                    config=self.config
                )

                # Create fix generator
                fix_generator = FixGenerationService(
                    llm_service=self.llm_service,
                    config=self.config
                )

                # Create healing orchestrator
                healing_orchestrator = HealingOrchestratorService(
                    error_parser=error_parser,
                    error_analyzer=error_analyzer,
                    dependency_resolver=dependency_resolution_service,
                    fix_generator=fix_generator,
                    file_system=self.file_system,
                    build_system=build_system,
                    config=self.config
                )

                # Create intelligent fix tool
                intelligent_fix_tool = create_intelligent_fix_tool(healing_orchestrator, self.config)
                tools["intelligent_fix"] = intelligent_fix_tool
                logger.info("Added intelligent_fix tool to reasoning agent")

                # Create analyze errors tool
                from unit_test_generator.infrastructure.adk_tools.analyze_errors_tool import AnalyzeErrorsTool
                analyze_errors_tool = AnalyzeErrorsTool(self.llm_service, error_parser, self.config)
                tools["analyze_errors"] = analyze_errors_tool
                logger.info("Added analyze_errors tool to reasoning agent")

                # Create identify dependencies tool
                from unit_test_generator.infrastructure.adk_tools.identify_dependencies_tool import IdentifyDependenciesTool
                identify_dependencies_tool = IdentifyDependenciesTool(self.llm_service, dependency_resolution_service, self.config)
                tools["identify_dependencies"] = identify_dependencies_tool
                logger.info("Added identify_dependencies tool to reasoning agent")
            except (ImportError, AttributeError) as e:
                logger.warning(f"Could not create advanced reasoning tools: {e}")

            # Add tools to the reasoning agent
            tools["run_test"] = run_test_tool
            tools["parse_errors"] = parse_errors_tool
            tools["generate_fix"] = generate_fix_tool
            tools["run_terminal_test"] = run_terminal_test_tool
            tools["get_terminal_output"] = get_terminal_output_tool
            tools["list_terminal_processes"] = list_terminal_processes_tool

            logger.info(f"Added {len(tools) - 5} reasoning-specific tools to reasoning agent")

        return tools
