# src/unit_test_generator/domain/models/agent_models.py
"""
Domain models for the agent-based approach.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class AgentState:
    """
    Represents the state of an agent during execution.
    """

    def __init__(self, goal: str, initial_state: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent state.

        Args:
            goal: The goal the agent is trying to achieve
            initial_state: Optional initial state
        """
        self.goal = goal
        self.data = initial_state or {}
        self.success = False
        self.iteration = 0
        self.observations = []
        self.thoughts = []
        self.actions = []
        self.results = []
        self.artifacts = {}

    def update(self, new_data: Dict[str, Any]) -> 'AgentState':
        """
        Update the state with new data.

        Args:
            new_data: New data to add to the state

        Returns:
            Updated state
        """
        # Create a new state object to maintain immutability
        new_state = AgentState(self.goal)

        # Copy existing data
        new_state.data = self.data.copy()
        new_state.success = self.success
        new_state.iteration = self.iteration
        new_state.observations = self.observations.copy()
        new_state.thoughts = self.thoughts.copy()
        new_state.actions = self.actions.copy()
        new_state.results = self.results.copy()
        new_state.artifacts = self.artifacts.copy()

        # Update with new data
        new_state.data.update(new_data)

        # Update success if provided
        if 'success' in new_data:
            new_state.success = new_data['success']

        # Update artifacts if provided
        if 'artifacts' in new_data:
            new_state.artifacts.update(new_data['artifacts'])

        return new_state

    def add_observation(self, observation: Any) -> 'AgentState':
        """Add an observation to the state."""
        new_state = self.update({})
        new_state.observations.append(observation)
        return new_state

    def add_thought(self, thought: Any) -> 'AgentState':
        """Add a thought to the state."""
        new_state = self.update({})
        new_state.thoughts.append(thought)
        return new_state

    def add_action(self, action: Any) -> 'AgentState':
        """Add an action to the state."""
        new_state = self.update({})
        new_state.actions.append(action)
        return new_state

    def add_result(self, result: Any) -> 'AgentState':
        """Add a result to the state."""
        new_state = self.update({})
        new_state.results.append(result)
        return new_state

    def increment_iteration(self) -> 'AgentState':
        """Increment the iteration counter."""
        new_state = self.update({})
        new_state.iteration += 1
        return new_state

    def mark_success(self) -> 'AgentState':
        """Mark the state as successful."""
        return self.update({'success': True})

    def mark_failure(self) -> 'AgentState':
        """Mark the state as failed."""
        return self.update({'success': False})

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the state data."""
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Get a value from the state data using dictionary syntax."""
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the state data."""
        return key in self.data


class Agent(ABC):
    """
    Base class for all agents.
    """

    def __init__(self, name: str, tools: Dict[str, Any], config: Dict[str, Any]):
        """
        Initialize the agent.

        Args:
            name: The name of the agent
            tools: Dictionary of tools available to the agent
            config: Configuration dictionary
        """
        self.name = name
        self.tools = tools
        self.config = config
        self.max_iterations = config.get(f"agents.{name}.max_iterations", 5)

    def execute(self, state: AgentState) -> AgentState:
        """
        Execute the agent's loop until success or max iterations.

        Args:
            state: The current state

        Returns:
            Updated state after execution
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Executing agent {self.name} with max iterations {self.max_iterations}")

        try:
            current_state = state

            # Force at least one iteration
            force_iteration = True

            while (current_state.iteration < self.max_iterations and not current_state.success) or force_iteration:
                logger.info(f"Agent {self.name} iteration {current_state.iteration + 1}/{self.max_iterations}")

                # Observe current state
                logger.info(f"Agent {self.name} observing state")
                observations = self._observe(current_state)
                logger.info(f"Agent {self.name} observations: {observations.keys() if observations else 'None'}")
                current_state = current_state.add_observation(observations)

                # Think about the problem
                logger.info(f"Agent {self.name} thinking about observations")
                thoughts = self._think(observations, current_state)
                logger.info(f"Agent {self.name} thoughts: {thoughts.keys() if thoughts else 'None'}")
                current_state = current_state.add_thought(thoughts)

                # Decide on actions
                logger.info(f"Agent {self.name} deciding on actions")
                actions = self._decide_actions(thoughts, current_state)
                logger.info(f"Agent {self.name} decided on {len(actions)} actions")
                current_state = current_state.add_action(actions)

                # Execute actions
                logger.info(f"Agent {self.name} executing actions")
                results = self._execute_actions(actions, current_state)
                logger.info(f"Agent {self.name} action results: {len(results)}")
                current_state = current_state.add_result(results)

                # Update state
                logger.info(f"Agent {self.name} updating state")
                current_state = self._update_state(current_state, results)

                # Increment iteration counter
                current_state = current_state.increment_iteration()

                # Turn off force_iteration after first iteration
                force_iteration = False

                # Check if we've achieved success
                success = self._is_success(current_state)
                logger.info(f"Agent {self.name} success check: {success}")
                if success:
                    logger.info(f"Agent {self.name} achieved success")
                    current_state = current_state.mark_success()
        except Exception as e:
            logger.error(f"Error executing agent {self.name}: {e}", exc_info=True)
            return state.update({
                "success": False,
                "error_message": f"Error executing agent {self.name}: {str(e)}"
            })

        return current_state

    @abstractmethod
    def _observe(self, state: AgentState) -> Dict[str, Any]:
        """
        Gather information about the current state.

        Args:
            state: The current state

        Returns:
            Observations about the current state
        """
        pass

    @abstractmethod
    def _think(self, observations: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """
        Reason about the problem and possible solutions.

        Args:
            observations: Observations about the current state
            state: The current state

        Returns:
            Thoughts about the problem
        """
        pass

    @abstractmethod
    def _decide_actions(self, thoughts: Dict[str, Any], state: AgentState) -> List[Dict[str, Any]]:
        """
        Decide on actions to take.

        Args:
            thoughts: Thoughts about the problem
            state: The current state

        Returns:
            List of actions to take
        """
        pass

    def _execute_actions(self, actions: List[Dict[str, Any]], state: AgentState) -> List[Dict[str, Any]]:
        """
        Execute the specified actions.

        Args:
            actions: List of actions to take
            state: The current state

        Returns:
            Results of the actions
        """
        results = []

        for action in actions:
            tool_name = action.get('tool')
            tool_args = action.get('args', {})

            if tool_name not in self.tools:
                results.append({
                    'tool': tool_name,
                    'success': False,
                    'error': f"Tool '{tool_name}' not found"
                })
                continue

            try:
                tool_result = self.tools[tool_name].execute(tool_args)
                results.append({
                    'tool': tool_name,
                    'success': True,
                    'result': tool_result
                })
            except Exception as e:
                results.append({
                    'tool': tool_name,
                    'success': False,
                    'error': str(e)
                })

        return results

    @abstractmethod
    def _update_state(self, state: AgentState, results: List[Dict[str, Any]]) -> AgentState:
        """
        Update the state based on action results.

        Args:
            state: The current state
            results: Results of the actions

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


class Goal:
    """
    Represents a goal that an agent is trying to achieve.
    """

    def __init__(self, name: str, description: str, success_criteria: Optional[List[str]] = None):
        """
        Initialize the goal.

        Args:
            name: The name of the goal
            description: A description of the goal
            success_criteria: List of criteria for success (optional)
        """
        self.name = name
        self.description = description
        self.success_criteria = success_criteria or []

    def is_achieved(self, state: AgentState) -> bool:
        """
        Determine if the goal has been achieved.

        Args:
            state: The current state

        Returns:
            True if the goal has been achieved, False otherwise
        """
        # If there are no success criteria, just check the success flag
        if not self.success_criteria:
            return state.success

        # Check if all success criteria are met
        for criterion in self.success_criteria:
            if not state.data.get(criterion, False):
                return False

        return True
