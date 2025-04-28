# src/unit_test_generator/infrastructure/adk_tools/agent.py
"""
ADK Agent implementation for JUnit Writer.
"""
import logging
from typing import Dict, Any, List, Optional

from google.adk.agents import LlmAgent
from google.adk.tools import BaseTool

logger = logging.getLogger(__name__)

def create_adk_agent(
    tools: List[BaseTool],
    config: Dict[str, Any],
    model_name: Optional[str] = None
) -> LlmAgent:
    """
    Create an ADK LlmAgent for test fixing.
    
    Args:
        tools: List of tools to provide to the agent
        config: Application configuration
        model_name: Optional model name to use (defaults to config value)
        
    Returns:
        An ADK LlmAgent configured for test fixing
    """
    # Get the model name from config if not provided
    if not model_name:
        model_name = config.get('generation', {}).get('model_name', 'gemini-1.5-flash')
    
    # Create the agent
    agent = LlmAgent(
        name="TestFixAgent",
        description="Agent that fixes failing tests",
        tools=tools,
        model=model_name,
        instruction="""
        You are an expert test fixer. Your goal is to fix failing tests.
        
        When presented with a failing test, you should:
        1. Analyze the error message to understand what's failing
        2. Examine the test code and the target code being tested
        3. Generate a fix for the test that addresses the error
        4. Make sure the fix is compatible with the testing framework
        
        Use the provided tools to:
        - Run tests to check if they pass
        - Parse error messages to understand failures
        - Generate fixes for failing tests
        - Write the fixed code to the test file
        - Read files to get more context if needed
        - Resolve dependencies if you need to understand related code
        """
    )
    
    logger.info(f"Created ADK LlmAgent with {len(tools)} tools")
    return agent
