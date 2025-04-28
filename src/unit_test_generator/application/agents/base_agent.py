"""
Base agent class for all agents.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from unit_test_generator.domain.models.agent_state import AgentState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base agent class for all agents.
    """

    def __init__(self, tools: Dict[str, Any], config: Dict[str, Any]):
        """
        Initialize the base agent.

        Args:
            tools: Dictionary of tools available to the agent
            config: Application configuration
        """
        self.tools = tools
        self.config = config
        logger.info(f"BaseAgent initialized with {len(tools)} tools")

    def execute(self, state: AgentState) -> AgentState:
        """
        Execute the agent.

        Args:
            state: The current state

        Returns:
            Updated state
        """
        logger.info(f"Executing agent: {self.__class__.__name__}")

        # Execute the agent loop
        try:
            # Observe the environment
            observations = self._observe(state)
            logger.info(f"Agent observed state with {len(observations)} observations")

            # Think about the observations
            thoughts = self._think(observations, state)
            logger.info(f"Agent thought about observations with {len(thoughts)} thoughts")

            # Decide what actions to take
            actions = self._decide_actions(thoughts)
            logger.info(f"Agent decided on {len(actions)} actions")

            # Execute the actions
            updated_state = self._execute_actions(actions, state)
            logger.info(f"Agent executed actions and updated state")

            # Check if we've achieved our goal
            success = self._is_success(updated_state)
            logger.info(f"Agent success: {success}")

            # Update the state with success
            updated_state = updated_state.update({"success": success})

            return updated_state
        except Exception as e:
            logger.error(f"Error executing agent: {e}", exc_info=True)
            return state.update({
                "success": False,
                "error_message": f"Error executing agent: {str(e)}"
            })

    @abstractmethod
    def _observe(self, state: AgentState) -> Dict[str, Any]:
        """
        Observe the current state and gather information.

        Args:
            state: The current state

        Returns:
            Dictionary of observations
        """
        pass

    @abstractmethod
    def _think(self, observations: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """
        Reason about the observations and decide what to do.

        Args:
            observations: Observations about the current state
            state: The current state

        Returns:
            Thoughts about what to do next
        """
        pass

    @abstractmethod
    def _decide_actions(self, thoughts: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Decide what actions to take based on thoughts.

        Args:
            thoughts: Thoughts about what to do next

        Returns:
            List of actions to take
        """
        pass

    @abstractmethod
    def _execute_actions(self, actions: List[Dict[str, Any]], state: AgentState) -> AgentState:
        """
        Execute the actions and update the state.

        Args:
            actions: List of actions to take
            state: The current state

        Returns:
            Updated state
        """
        pass

    @abstractmethod
    def _is_success(self, state: AgentState) -> bool:
        """
        Determine if the agent has achieved its goal.

        Args:
            state: The current state

        Returns:
            True if the goal has been achieved, False otherwise
        """
        pass
