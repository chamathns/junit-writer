"""
Manager for agent state.
"""
import logging
from typing import Dict, Any, Optional

from unit_test_generator.domain.models.agent_models import AgentState, Goal

logger = logging.getLogger(__name__)


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
