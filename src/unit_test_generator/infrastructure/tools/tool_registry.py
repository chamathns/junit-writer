# src/unit_test_generator/infrastructure/tools/tool_registry.py
"""
Registry for tools used by agents.
"""
import logging
from typing import Dict, Any, List, Type

logger = logging.getLogger(__name__)


class Tool:
    """
    Base class for all tools.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize the tool.
        
        Args:
            name: The name of the tool
            description: A description of what the tool does
        """
        self.name = name
        self.description = description
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with the given arguments.
        
        Args:
            args: The arguments for the tool
            
        Returns:
            The result of executing the tool
            
        Raises:
            NotImplementedError: If the tool does not implement execute
        """
        raise NotImplementedError(f"Tool {self.name} does not implement execute")


class ToolRegistry:
    """
    Registry for tools used by agents.
    """
    
    def __init__(self):
        """
        Initialize the tool registry.
        """
        self.tools = {}
        self.agent_tools = {}
    
    def register_tool(self, tool: Tool) -> None:
        """
        Register a tool.
        
        Args:
            tool: The tool to register
        """
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    def register_agent_tool(self, agent_type: str, tool_name: str) -> None:
        """
        Register a tool for a specific agent type.
        
        Args:
            agent_type: The type of agent
            tool_name: The name of the tool
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not registered")
        
        if agent_type not in self.agent_tools:
            self.agent_tools[agent_type] = []
        
        self.agent_tools[agent_type].append(tool_name)
        logger.debug(f"Registered tool {tool_name} for agent {agent_type}")
    
    def get_tool(self, name: str) -> Tool:
        """
        Get a tool by name.
        
        Args:
            name: The name of the tool
            
        Returns:
            The tool
            
        Raises:
            ValueError: If the tool is not registered
        """
        if name not in self.tools:
            raise ValueError(f"Tool {name} not registered")
        
        return self.tools[name]
    
    def get_tools_for_agent(self, agent_type: str) -> Dict[str, Tool]:
        """
        Get all tools for a specific agent type.
        
        Args:
            agent_type: The type of agent
            
        Returns:
            Dictionary of tools for the agent
        """
        if agent_type not in self.agent_tools:
            return {}
        
        return {name: self.tools[name] for name in self.agent_tools[agent_type] if name in self.tools}
    
    def list_tools(self) -> List[str]:
        """
        List all registered tools.
        
        Returns:
            List of tool names
        """
        return list(self.tools.keys())
    
    def list_agent_tools(self, agent_type: str) -> List[str]:
        """
        List all tools for a specific agent type.
        
        Args:
            agent_type: The type of agent
            
        Returns:
            List of tool names
        """
        if agent_type not in self.agent_tools:
            return []
        
        return self.agent_tools[agent_type]


class ToolFactory:
    """
    Factory for creating tools.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the tool factory.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.tool_classes = {}
    
    def register_tool_class(self, name: str, tool_class: Type[Tool]) -> None:
        """
        Register a tool class.
        
        Args:
            name: The name of the tool
            tool_class: The tool class
        """
        self.tool_classes[name] = tool_class
    
    def create_tool(self, name: str, **kwargs) -> Tool:
        """
        Create a tool instance.
        
        Args:
            name: The name of the tool
            **kwargs: Additional arguments for the tool
            
        Returns:
            An instance of the tool
            
        Raises:
            ValueError: If the tool class is not registered
        """
        if name not in self.tool_classes:
            raise ValueError(f"Tool class {name} not registered")
        
        tool_class = self.tool_classes[name]
        return tool_class(**kwargs)
