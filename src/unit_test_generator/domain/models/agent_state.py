"""
Agent state model.
"""
from typing import Dict, Any, Optional


class AgentState:
    """
    Represents the state of an agent.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None, artifacts: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent state.

        Args:
            data: Dictionary of state data
            artifacts: Dictionary of artifacts
        """
        self.data = data or {}
        self.artifacts = artifacts or {}
        self.success = False

    def update(self, data: Dict[str, Any]) -> 'AgentState':
        """
        Update the state with new data.

        Args:
            data: Dictionary of new data

        Returns:
            Updated state
        """
        # Create a new state with updated data
        new_data = self.data.copy()
        new_data.update(data)

        # Create a new state
        new_state = AgentState(new_data, self.artifacts.copy())
        
        # Update success if provided
        if "success" in data:
            new_state.success = data["success"]
        else:
            new_state.success = self.success

        return new_state

    def add_artifact(self, name: str, artifact: Any) -> 'AgentState':
        """
        Add an artifact to the state.

        Args:
            name: Name of the artifact
            artifact: The artifact

        Returns:
            Updated state
        """
        # Create a new state with the same data
        new_state = AgentState(self.data.copy(), self.artifacts.copy())
        
        # Add the artifact
        new_state.artifacts[name] = artifact
        
        # Copy success
        new_state.success = self.success

        return new_state

    def get_artifact(self, name: str) -> Any:
        """
        Get an artifact from the state.

        Args:
            name: Name of the artifact

        Returns:
            The artifact, or None if not found
        """
        return self.artifacts.get(name)

    def __str__(self) -> str:
        """
        Get a string representation of the state.

        Returns:
            String representation
        """
        return f"AgentState(success={self.success}, data_keys={list(self.data.keys())}, artifact_keys={list(self.artifacts.keys())})"
