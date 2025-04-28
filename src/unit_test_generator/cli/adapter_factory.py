import logging
from typing import Dict, Any, List

# Import necessary adapters
from unit_test_generator.infrastructure.adapters.file_system_adapter import FileSystemAdapter
from unit_test_generator.infrastructure.adapters.embedding.sentence_transformer_adapter import SentenceTransformerAdapter
from unit_test_generator.infrastructure.adapters.vector_db.chroma_adapter import ChromaDBAdapter
from unit_test_generator.infrastructure.adapters.llm.google_gemini_adapter import GoogleGeminiAdapter
from unit_test_generator.infrastructure.adapters.llm.mock_llm_adapter import MockLLMAdapter
from unit_test_generator.infrastructure.adapters.parsing.simulated_parser_adapter import SimulatedParserAdapter
from unit_test_generator.infrastructure.adapters.build_system.gradle_adapter import GradleAdapter
from unit_test_generator.infrastructure.adapters.error_parsing.enhanced_llm_error_parser import EnhancedLLMErrorParserAdapter
from unit_test_generator.infrastructure.adapters.error_parsing.regex_error_parser_adapter import RegexErrorParserAdapter
from unit_test_generator.infrastructure.adapters.error_parsing.hybrid_error_parser_adapter import HybridErrorParserAdapter
from unit_test_generator.infrastructure.adapters.source_control.git_adapter import GitAdapter

# Import application services
from unit_test_generator.application.services.dependency_resolver import DependencyResolverService
from unit_test_generator.application.services.error_analysis_service import ErrorAnalysisService
from unit_test_generator.application.services.dependency_resolution_service import DependencyResolutionService
from unit_test_generator.application.services.fix_generation_service import FixGenerationService
from unit_test_generator.application.services.healing_orchestrator_service import HealingOrchestratorService
from unit_test_generator.application.services.intelligent_context_builder import IntelligentContextBuilder
from unit_test_generator.application.services.layer_aware_test_generator import LayerAwareTestGenerator

# Import domain models
from unit_test_generator.domain.models.dependency_graph import DependencyGraphManager

# Import ADK tools
from unit_test_generator.infrastructure.adk_tools import (
    RunTestTool,
    VerifyBuildEnvironmentTool,
    RunTerminalTestTool,
    GetTerminalOutputTool,
    ListTerminalProcessesTool,
    KillTerminalProcessTool,
    ParseErrorsTool,
    GenerateFixTool,
    WriteFileTool,
    ReadFileTool,
    ResolveDependenciesTool
)
from unit_test_generator.infrastructure.adk_tools.intelligent_fix_tool import IntelligentFixTool
from unit_test_generator.infrastructure.adk_tools.analyze_errors_tool import AnalyzeErrorsTool
from unit_test_generator.infrastructure.adk_tools.identify_dependencies_tool import IdentifyDependenciesTool

# Import ADK components
from google.adk.tools import BaseTool

# Import JUnit Writer ADK components
from unit_test_generator.infrastructure.adk_tools.agent import create_adk_agent
from unit_test_generator.infrastructure.adk_tools.runner import ADKRunnerAdapter, SimplifiedADKRunner

# Import necessary ports (for type hinting)
from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.embedding_service import EmbeddingServicePort
from unit_test_generator.domain.ports.vector_db import VectorDBPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.code_parser import CodeParserPort
from unit_test_generator.domain.ports.build_system import BuildSystemPort
from unit_test_generator.domain.ports.error_parser import ErrorParserPort
from unit_test_generator.domain.ports.source_control import SourceControlPort
from unit_test_generator.domain.ports.dependency_resolver import DependencyResolverPort
from unit_test_generator.domain.ports.error_analysis import (
    ErrorAnalysisPort, DependencyResolutionPort, FixGenerationPort, HealingOrchestratorPort
)

logger = logging.getLogger(__name__)

def create_file_system_adapter() -> FileSystemPort:
    logger.debug("Creating FileSystemAdapter")
    return FileSystemAdapter()

def create_embedding_service(config: Dict[str, Any]) -> EmbeddingServicePort:
    provider = config.get('embedding', {}).get('provider', 'sentence_transformer')
    logger.debug(f"Creating EmbeddingService for provider: {provider}")
    if provider == 'sentence_transformer':
        return SentenceTransformerAdapter(config)
    # Add other providers like 'openai' here if needed
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")

def create_vector_db(config: Dict[str, Any]) -> VectorDBPort:
    provider = config.get('vector_db', {}).get('provider', 'chroma')
    logger.debug(f"Creating VectorDB for provider: {provider}")
    if provider == 'chroma':
        return ChromaDBAdapter(config)
    # Add other providers like 'pinecone' here if needed
    else:
        raise ValueError(f"Unsupported vector DB provider: {provider}")

def create_llm_service(config: Dict[str, Any]) -> LLMServicePort:
    provider = config.get('generation', {}).get('llm_provider', 'mock')
    logger.info(f"Creating LLMService for provider: {provider}")
    if provider == 'google_gemini':
        return GoogleGeminiAdapter(config)
    elif provider == 'mock':
        return MockLLMAdapter(config)
    # Add other providers like 'openai', 'anthropic' here
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def create_code_parser(config: Dict[str, Any] = None) -> CodeParserPort:
    """Creates a code parser adapter.

    Args:
        config: Optional configuration dictionary

    Returns:
        An implementation of CodeParserPort
    """
    logger.debug("Creating SimulatedParserAdapter")
    return SimulatedParserAdapter()

def create_dependency_resolver(config: Dict[str, Any], file_system: FileSystemPort) -> DependencyResolverService:
    logger.debug("Creating DependencyResolverService")
    # Basic resolver is used as a fallback for the dependency discovery agent
    return DependencyResolverService(file_system=file_system, config=config)

def create_dependency_graph_manager(config: Dict[str, Any], file_system: FileSystemPort) -> DependencyGraphManager:
    """Create a dependency graph manager for intelligent context building."""
    logger.info("Creating DependencyGraphManager")

    # Load repository index
    try:
        import json
        index_file_path = config['indexing']['index_file_path']
        if not file_system.exists(index_file_path):
            logger.warning(f"Repository index file not found at {index_file_path}")
            return None

        index_content = file_system.read_file(index_file_path)
        if not index_content:
            logger.warning("Repository index file is empty")
            return None

        repository_index = json.loads(index_content)
        return DependencyGraphManager(repository_index=repository_index, file_system=file_system)
    except Exception as e:
        logger.error(f"Error creating dependency graph manager: {e}", exc_info=True)
        return None

def create_intelligent_context_builder(config: Dict[str, Any],
                                     dependency_graph: DependencyGraphManager,
                                     llm_service: LLMServicePort,
                                     file_system: FileSystemPort) -> IntelligentContextBuilder:
    """Create an intelligent context builder for comprehensive test generation."""
    logger.info("Creating IntelligentContextBuilder")
    return IntelligentContextBuilder(
        dependency_graph=dependency_graph,
        llm_service=llm_service,
        file_system=file_system,
        config=config
    )

def create_layer_aware_test_generator(config: Dict[str, Any],
                                    llm_service: LLMServicePort,
                                    context_builder: IntelligentContextBuilder) -> LayerAwareTestGenerator:
    """Create a layer-aware test generator."""
    logger.info("Creating LayerAwareTestGenerator")
    return LayerAwareTestGenerator(
        llm_service=llm_service,
        context_builder=context_builder,
        config=config
    )

def create_build_system(config: Dict[str, Any]) -> BuildSystemPort:
    build_type = config.get('build_system', {}).get('type', 'gradle')
    logger.info(f"Creating BuildSystem for type: {build_type}")
    if build_type == 'gradle':
        return GradleAdapter(config)
    # Add 'maven' or other types here
    else:
        raise ValueError(f"Unsupported build system type: {build_type}")

def create_error_parser(config: Dict[str, Any], llm_service: LLMServicePort) -> ErrorParserPort:
    parser_type = config.get('error_parsing', {}).get('adapter', 'hybrid') # Default to hybrid
    logger.info(f"Creating ErrorParser for type: {parser_type}")

    if parser_type == 'hybrid':
        # Hybrid parser that combines regex and LLM approaches
        return HybridErrorParserAdapter(llm_service=llm_service, config=config)
    elif parser_type == 'enhanced_llm':
        # Enhanced LLM parser with better Kotlin/JUnit5/MockK support
        return EnhancedLLMErrorParserAdapter(llm_service=llm_service, config=config)
    elif parser_type == 'regex':
        # Regex-based parser optimized for Kotlin/JUnit5/MockK errors
        return RegexErrorParserAdapter(config=config)
    elif parser_type in ['llm', 'junit_gradle']:
        # For backward compatibility, map deprecated parsers to recommended alternatives
        logger.warning(f"Parser type '{parser_type}' is deprecated. Using 'hybrid' parser instead.")
        return HybridErrorParserAdapter(llm_service=llm_service, config=config)
    else:
        raise ValueError(f"Unsupported error parsing adapter type: {parser_type}")

# ADK Tool Factory Functions

def create_run_test_tool(build_system: BuildSystemPort) -> RunTestTool:
    logger.debug("Creating RunTestTool")
    return RunTestTool(build_system=build_system)

def create_verify_build_environment_tool(build_system: BuildSystemPort) -> VerifyBuildEnvironmentTool:
    logger.debug("Creating VerifyBuildEnvironmentTool")
    return VerifyBuildEnvironmentTool(build_system=build_system)

def create_run_terminal_test_tool(build_system: BuildSystemPort) -> RunTerminalTestTool:
    logger.debug("Creating RunTerminalTestTool")
    return RunTerminalTestTool(build_system=build_system)

def create_get_terminal_output_tool(build_system: BuildSystemPort) -> GetTerminalOutputTool:
    logger.debug("Creating GetTerminalOutputTool")
    return GetTerminalOutputTool(build_system=build_system)

def create_list_terminal_processes_tool(build_system: BuildSystemPort) -> ListTerminalProcessesTool:
    logger.debug("Creating ListTerminalProcessesTool")
    return ListTerminalProcessesTool(build_system=build_system)

def create_kill_terminal_process_tool(build_system: BuildSystemPort) -> KillTerminalProcessTool:
    logger.debug("Creating KillTerminalProcessTool")
    return KillTerminalProcessTool(build_system=build_system)

def create_parse_errors_tool(error_parser: ErrorParserPort) -> ParseErrorsTool:
    logger.debug("Creating ParseErrorsTool")
    return ParseErrorsTool(error_parser=error_parser)

def create_generate_fix_tool(llm_service: LLMServicePort, error_parser: ErrorParserPort, dependency_resolver: DependencyResolverService, config: Dict[str, Any]) -> GenerateFixTool:
    logger.debug("Creating GenerateFixTool with parallel error analysis capabilities")
    return GenerateFixTool(
        llm_service=llm_service,
        error_parser=error_parser,
        dependency_resolver=dependency_resolver,
        config=config
    )

# Error Analysis Service
def create_error_analysis_service(
    llm_service: LLMServicePort,
    dependency_resolution_service: DependencyResolutionPort,
    config: Dict[str, Any]
) -> ErrorAnalysisPort:
    logger.debug("Creating ErrorAnalysisService")
    return ErrorAnalysisService(
        llm_service=llm_service,
        dependency_resolver=dependency_resolution_service,
        config=config
    )

# Dependency Resolution Service
def create_dependency_resolution_service(
    file_system: FileSystemPort,
    config: Dict[str, Any]
) -> DependencyResolutionPort:
    logger.debug("Creating DependencyResolutionService")
    return DependencyResolutionService(
        file_system=file_system,
        config=config
    )

# Fix Generation Service
def create_fix_generation_service(
    llm_service: LLMServicePort,
    config: Dict[str, Any]
) -> FixGenerationPort:
    logger.debug("Creating FixGenerationService")
    return FixGenerationService(
        llm_service=llm_service,
        config=config
    )

# Healing Orchestrator Service
def create_healing_orchestrator_service(
    error_parser: ErrorParserPort,
    error_analyzer: ErrorAnalysisPort,
    dependency_resolver: DependencyResolutionPort,
    fix_generator: FixGenerationPort,
    file_system: FileSystemPort,
    build_system: BuildSystemPort,
    config: Dict[str, Any]
) -> HealingOrchestratorPort:
    logger.debug("Creating HealingOrchestratorService")
    return HealingOrchestratorService(
        error_parser=error_parser,
        error_analyzer=error_analyzer,
        dependency_resolver=dependency_resolver,
        fix_generator=fix_generator,
        file_system=file_system,
        build_system=build_system,
        config=config
    )

# Intelligent Fix Tool
def create_intelligent_fix_tool(
    healing_orchestrator: HealingOrchestratorPort,
    config: Dict[str, Any]
) -> IntelligentFixTool:
    logger.debug("Creating IntelligentFixTool")
    return IntelligentFixTool(
        healing_orchestrator=healing_orchestrator,
        config=config
    )

def create_write_file_tool(file_system: FileSystemPort) -> WriteFileTool:
    logger.debug("Creating WriteFileTool")
    return WriteFileTool(file_system=file_system)

def create_read_file_tool(file_system: FileSystemPort) -> ReadFileTool:
    logger.debug("Creating ReadFileTool")
    return ReadFileTool(file_system=file_system)

def create_resolve_dependencies_tool(dependency_resolver: DependencyResolverService) -> ResolveDependenciesTool:
    logger.debug("Creating ResolveDependenciesTool")
    return ResolveDependenciesTool(dependency_resolver=dependency_resolver)

# Analyze Errors Tool
def create_analyze_errors_tool(
    llm_service: LLMServicePort,
    error_parser: ErrorParserPort,
    config: Dict[str, Any]
) -> AnalyzeErrorsTool:
    logger.debug("Creating AnalyzeErrorsTool")
    return AnalyzeErrorsTool(
        llm_service=llm_service,
        error_parser=error_parser,
        config=config
    )

# Identify Dependencies Tool
def create_identify_dependencies_tool(
    llm_service: LLMServicePort,
    dependency_resolver: DependencyResolverPort,
    config: Dict[str, Any]
) -> IdentifyDependenciesTool:
    logger.debug("Creating IdentifyDependenciesTool")
    return IdentifyDependenciesTool(
        llm_service=llm_service,
        dependency_resolver=dependency_resolver,
        config=config
    )

def create_source_control(config: Dict[str, Any]) -> SourceControlPort:
    """Creates a source control adapter."""
    logger.info("Creating source control adapter")
    repo_root = config.get('repository', {}).get('root_path', '.')
    return GitAdapter(repo_root=repo_root)

def create_adk_reasoning_engine(tools: List[BaseTool], config: Dict[str, Any], llm_service: LLMServicePort) -> ADKRunnerAdapter:
    logger.info("Creating ADK components")

    # Determine which approach to use based on config
    use_full_adk = config.get('adk', {}).get('use_full_adk', False)

    if use_full_adk:
        # Create an ADK agent
        agent = create_adk_agent(tools=tools, config=config)

        # Create an ADK runner adapter
        runner = ADKRunnerAdapter(agent=agent, config=config)
        logger.info("Created ADK Runner Adapter with full ADK integration")
    else:
        # Create a simplified ADK runner
        runner = SimplifiedADKRunner(tools=tools, config=config)
        logger.info("Created SimplifiedADKRunner for compatibility")

    return runner


# --- Agent Mode Factory Functions ---

def create_agent_factory(config: Dict[str, Any], llm_service: LLMServicePort, file_system: FileSystemPort,
                        embedding_service: EmbeddingServicePort, vector_db: VectorDBPort,
                        code_parser: CodeParserPort) -> 'AgentFactory':
    """Create an agent factory for agent mode."""
    logger.info("Creating AgentFactory")
    from unit_test_generator.application.agents.agent_factory import AgentFactory
    return AgentFactory(config, llm_service, file_system, embedding_service, vector_db, code_parser)


def create_state_manager() -> 'StateManager':
    """Create a state manager for agent mode."""
    logger.info("Creating StateManager")
    from unit_test_generator.application.agents.state_manager import StateManager
    return StateManager()


def create_agent_coordinator(agent_factory: 'AgentFactory', state_manager: 'StateManager', config: Dict[str, Any]) -> 'AgentCoordinator':
    """Create an agent coordinator for agent mode."""
    logger.info("Creating AgentCoordinator")
    from unit_test_generator.application.services.agent_coordinator import AgentCoordinator
    return AgentCoordinator(agent_factory, state_manager, config)
