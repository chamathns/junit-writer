# src/unit_test_generator/application/services/agent_coordinator.py
"""
Coordinator for agent-based execution.
"""
import logging
from typing import Dict, Any, List, Optional, Type

from unit_test_generator.domain.models.agent_models import Agent, AgentState, Goal

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory for creating agents.
    """
    
    def __init__(self, tool_registry, config: Dict[str, Any]):
        """
        Initialize the agent factory.
        
        Args:
            tool_registry: Registry of tools
            config: Configuration dictionary
        """
        self.tool_registry = tool_registry
        self.config = config
        self.agent_classes = {}  # Will be populated by register_agent
    
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
        tools = self.tool_registry.get_tools_for_agent(agent_type)
        
        return agent_class(tools, self.config)


class StateManager:
    """
    Manages shared state between agents.
    """
    
    def initialize_state(self, goal: Goal, initial_state: Optional[Dict[str, Any]] = None) -> AgentState:
        """
        Initialize the state for a goal.
        
        Args:
            goal: The goal
            initial_state: Optional initial state
            
        Returns:
            Initialized state
        """
        return AgentState(goal.name, initial_state or {})
    
    def update_state(self, current_state: AgentState, agent_result: AgentState) -> AgentState:
        """
        Update the state based on agent result.
        
        Args:
            current_state: The current state
            agent_result: The agent result state
            
        Returns:
            Updated state
        """
        # Merge the states
        merged_data = current_state.data.copy()
        merged_data.update(agent_result.data)
        
        # Create a new state with the merged data
        new_state = AgentState(current_state.goal)
        new_state.data = merged_data
        
        # Copy over success flag
        new_state.success = agent_result.success
        
        # Merge artifacts
        new_state.artifacts = current_state.artifacts.copy()
        new_state.artifacts.update(agent_result.artifacts)
        
        return new_state


class AgentCoordinator:
    """
    Coordinates the execution of agents to achieve a goal.
    """
    
    def __init__(self, agent_factory: AgentFactory, state_manager: StateManager, config: Dict[str, Any]):
        """
        Initialize the agent coordinator.
        
        Args:
            agent_factory: Factory for creating agents
            state_manager: Manager for agent state
            config: Configuration dictionary
        """
        self.agent_factory = agent_factory
        self.state_manager = state_manager
        self.config = config
        self.max_goal_attempts = config.get("agents.coordinator.max_goal_attempts", 3)
    
    def execute_goal(self, goal: Goal, initial_state: Optional[Dict[str, Any]] = None) -> AgentState:
        """
        Execute a goal using appropriate agents.
        
        Args:
            goal: The goal to execute
            initial_state: Optional initial state
            
        Returns:
            Final state after execution
        """
        logger.info(f"Executing goal: {goal.name}")
        
        # Determine which agents are needed for this goal
        agent_types = self._determine_required_agents(goal)
        logger.info(f"Required agents: {agent_types}")
        
        # Initialize shared state
        shared_state = self.state_manager.initialize_state(goal, initial_state)
        
        # Execute agents in sequence
        for agent_type in agent_types:
            logger.info(f"Creating agent: {agent_type}")
            agent = self.agent_factory.create_agent(agent_type)
            
            logger.info(f"Executing agent: {agent_type}")
            agent_result = agent.execute(shared_state)
            
            logger.info(f"Agent {agent_type} completed with success={agent_result.success}")
            shared_state = self.state_manager.update_state(shared_state, agent_result)
            
            # Check if we've achieved the goal
            if self._is_goal_achieved(goal, shared_state):
                logger.info(f"Goal {goal.name} achieved")
                break
        
        return shared_state
    
    def _determine_required_agents(self, goal: Goal) -> List[str]:
        """
        Determine which agents are required for a goal.
        
        Args:
            goal: The goal
            
        Returns:
            List of required agent types
        """
        # This is a simple mapping of goals to required agents
        # In a real implementation, this could be more sophisticated
        goal_to_agents = {
            "index_repository": ["index"],
            "generate_test": ["analyze", "generate"],
            "fix_test": ["fix"],
            "analyze_code": ["analyze"]
        }
        
        return goal_to_agents.get(goal.name, [])
    
    def _is_goal_achieved(self, goal: Goal, state: AgentState) -> bool:
        """
        Determine if a goal has been achieved.
        
        Args:
            goal: The goal
            state: The current state
            
        Returns:
            True if the goal has been achieved, False otherwise
        """
        return goal.is_achieved(state)
