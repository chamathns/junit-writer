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
        if agent_type not in self.agent_classes:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        agent_class = self.agent_classes[agent_type]
        tools = self._get_tools_for_agent(agent_type)
        
        return agent_class(agent_type, tools, self.config)
    
    def _register_built_in_agents(self) -> None:
        """Register built-in agents."""
        # Import here to avoid circular imports
        from unit_test_generator.application.agents.analyze_agent import AnalyzeAgent
        from unit_test_generator.application.agents.generate_agent import GenerateAgent
        from unit_test_generator.application.agents.fix_agent import FixAgent
        from unit_test_generator.application.agents.index_agent import IndexAgent
        
        self.register_agent("analyze", AnalyzeAgent)
        self.register_agent("generate", GenerateAgent)
        self.register_agent("fix", FixAgent)
        self.register_agent("index", IndexAgent)
    
    def _get_tools_for_agent(self, agent_type: str) -> Dict[str, Any]:
        """
        Get the tools for a specific agent type.
        
        Args:
            agent_type: The type of agent
            
        Returns:
            Dictionary of tools for the agent
        """
        # Create basic tools available to all agents
        tools = {
            "file_system": self.file_system,
            "llm": self.llm_service,
            "embedding": self.embedding_service,
            "vector_db": self.vector_db,
            "code_parser": self.code_parser
        }
        
        # Add agent-specific tools
        if agent_type == "analyze":
            # Add analyze-specific tools
            pass
        elif agent_type == "generate":
            # Add generate-specific tools
            pass
        elif agent_type == "fix":
            # Add fix-specific tools
            pass
        elif agent_type == "index":
            # Add index-specific tools
            pass
        
        return tools
