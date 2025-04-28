# src/unit_test_generator/infrastructure/adk_tools/runner.py
"""
ADK Runner implementation for JUnit Writer.
This module provides a compatibility layer between the ADK Runner and our application.
"""
import logging
import uuid
from typing import Dict, Any, List, Optional

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import BaseTool

logger = logging.getLogger(__name__)

class ADKRunnerAdapter:
    """
    Adapter for ADK Runner that provides a simplified interface for our application.
    This class bridges the gap between the ADK Runner and our application's requirements.
    """
    
    def __init__(
        self,
        agent: LlmAgent,
        config: Dict[str, Any]
    ):
        """
        Initialize the ADK Runner Adapter.
        
        Args:
            agent: The ADK LlmAgent to use
            config: Application configuration
        """
        self.agent = agent
        self.config = config
        self.runner = Runner(
            app_name="JUnitWriter",
            agent=agent,
            session_service=InMemorySessionService()
        )
        logger.info("Initialized ADK Runner Adapter")
    
    def run(self, goal: str, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the ADK agent to achieve a goal.
        
        Args:
            goal: The goal to achieve
            initial_state: The initial state
            
        Returns:
            The final state after running the agent
        """
        logger.info(f"Running ADK agent with goal: {goal}")
        
        # Create a unique session ID
        session_id = str(uuid.uuid4())
        
        try:
            # Prepare the user input
            user_input = f"{goal}\n\nContext: {initial_state}"
            
            # Run the agent
            response = self.runner.run(
                user_input=user_input,
                session_id=session_id
            )
            
            # Process the response
            if response:
                logger.info("ADK agent completed successfully")
                
                # Extract the fixed code from the response if available
                fixed_code = self._extract_code_from_response(response)
                if fixed_code:
                    logger.info("Found fixed code in response")
                    final_state = initial_state.copy()
                    final_state["current_test_code"] = fixed_code
                    final_state["success"] = True
                    return final_state
            
            # If we couldn't extract a fix, return the initial state with success=False
            logger.warning("Could not extract fixed code from response")
            final_state = initial_state.copy()
            final_state["success"] = False
            return final_state
            
        except Exception as e:
            logger.error(f"Error running ADK agent: {e}", exc_info=True)
            # Return the initial state with success=False
            final_state = initial_state.copy()
            final_state["success"] = False
            final_state["error"] = str(e)
            return final_state
    
    def _extract_code_from_response(self, response: Any) -> Optional[str]:
        """
        Extract code from the agent's response.
        
        Args:
            response: The response from the agent
            
        Returns:
            The extracted code, or None if no code was found
        """
        # This is a simplified implementation that assumes the response has a content attribute
        # with a text attribute that contains the code block
        try:
            if hasattr(response, 'content') and response.content:
                text = response.content
                
                # Look for code blocks in the response
                code_block_start = text.find("```")
                if code_block_start != -1:
                    code_block_end = text.find("```", code_block_start + 3)
                    if code_block_end != -1:
                        # Extract the code block (without the backticks)
                        code_block = text[code_block_start + 3:code_block_end].strip()
                        
                        # Remove language identifier if present
                        if code_block.startswith("kotlin") or code_block.startswith("java"):
                            code_block = code_block[code_block.find("\n") + 1:].strip()
                        
                        return code_block
        except Exception as e:
            logger.error(f"Error extracting code from response: {e}", exc_info=True)
        
        return None


class SimplifiedADKRunner:
    """
    A simplified runner for ADK tools.
    This class provides a way to run ADK tools without the full ADK infrastructure.
    It's similar to our previous implementation but uses the official ADK tools.
    """
    
    def __init__(self, tools: List[BaseTool], config: Dict[str, Any]):
        """
        Initialize the SimplifiedADKRunner.
        
        Args:
            tools: List of ADK tools to use
            config: Configuration dictionary
        """
        self.tools = {tool.name: tool for tool in tools}
        self.config = config
        self.max_iterations = config.get('self_healing', {}).get('max_attempts', 3)
        logger.info(f"Initialized SimplifiedADKRunner with {len(tools)} tools")
    
    async def run(self, goal: str, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the tools to achieve the goal.
        
        Args:
            goal: The goal to achieve
            initial_state: The initial state
            
        Returns:
            The final state
        """
        logger.info(f"Running SimplifiedADKRunner with goal: {goal}")
        
        # Initialize state
        state = initial_state.copy()
        state['success'] = False
        state['attempt_count'] = 0
        
        # Create a dummy tool context for compatibility
        tool_context = {}
        
        # Run the self-healing loop
        while state['attempt_count'] < self.max_iterations and not state.get('success', False):
            logger.info(f"Starting iteration {state['attempt_count'] + 1}/{self.max_iterations}")
            
            # Run the test
            if 'test_file_abs_path' in state:
                test_result = await self._run_test(state['test_file_abs_path'], tool_context)
                state['last_test_result'] = test_result
                
                # If the test passed, we're done
                if test_result.get('success', False):
                    state['success'] = True
                    logger.info("Test passed successfully")
                    break
                
                # Parse errors
                if 'output' in test_result:
                    errors = await self._parse_errors(test_result['output'], tool_context)
                    state['last_errors'] = errors
                    
                    # Generate a fix
                    if errors and errors.get('error_count', 0) > 0:
                        fix_result = await self._generate_fix(
                            target_file_path=state.get('target_file_path', ''),
                            target_file_content=state.get('target_file_content', ''),
                            current_test_code=state.get('current_test_code', ''),
                            error_output=test_result.get('output', ''),
                            tool_context=tool_context
                        )
                        
                        if fix_result.get('success', False) and fix_result.get('fixed_code'):
                            # Write the fixed code to the file
                            write_result = await self._write_file(
                                state['test_file_abs_path'],
                                fix_result['fixed_code'],
                                tool_context
                            )
                            
                            if write_result.get('success', False):
                                state['current_test_code'] = fix_result['fixed_code']
                                logger.info("Applied fix to test file")
                            else:
                                logger.error(f"Failed to write fixed code: {write_result.get('error')}")
                        else:
                            logger.warning("Failed to generate a fix")
            
            # Increment attempt count
            state['attempt_count'] += 1
        
        # Return the final state
        return state
    
    async def _run_test(self, test_file_abs_path: str, tool_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a test using the run_test tool.
        
        Args:
            test_file_abs_path: Absolute path to the test file
            tool_context: Tool context
            
        Returns:
            The result of running the test
        """
        if 'run_test' not in self.tools:
            logger.error("run_test tool not found")
            return {"success": False, "error": "run_test tool not found"}
        
        logger.info(f"Running test: {test_file_abs_path}")
        return await self.tools['run_test'].run_async(
            {"test_file_abs_path": test_file_abs_path},
            tool_context
        )
    
    async def _parse_errors(self, raw_output: str, tool_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse errors using the parse_errors tool.
        
        Args:
            raw_output: Raw output from the test run
            tool_context: Tool context
            
        Returns:
            The parsed errors
        """
        if 'parse_errors' not in self.tools:
            logger.error("parse_errors tool not found")
            return {"success": False, "error": "parse_errors tool not found"}
        
        logger.info("Parsing errors from test output")
        return await self.tools['parse_errors'].run_async(
            {"raw_output": raw_output},
            tool_context
        )
    
    async def _generate_fix(
        self,
        target_file_path: str,
        target_file_content: str,
        current_test_code: str,
        error_output: str,
        tool_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a fix using the generate_fix tool.
        
        Args:
            target_file_path: Path to the target file
            target_file_content: Content of the target file
            current_test_code: Current test code
            error_output: Error output from the test run
            tool_context: Tool context
            
        Returns:
            The generated fix
        """
        if 'generate_fix' not in self.tools:
            logger.error("generate_fix tool not found")
            return {"success": False, "error": "generate_fix tool not found"}
        
        logger.info("Generating fix for test")
        return await self.tools['generate_fix'].run_async(
            {
                "target_file_path": target_file_path,
                "target_file_content": target_file_content,
                "current_test_code": current_test_code,
                "error_output": error_output
            },
            tool_context
        )
    
    async def _write_file(self, file_path: str, content: str, tool_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write a file using the write_file tool.
        
        Args:
            file_path: Path to the file
            content: Content to write
            tool_context: Tool context
            
        Returns:
            The result of writing the file
        """
        if 'write_file' not in self.tools:
            logger.error("write_file tool not found")
            return {"success": False, "error": "write_file tool not found"}
        
        logger.info(f"Writing to file: {file_path}")
        return await self.tools['write_file'].run_async(
            {
                "file_path": file_path,
                "content": content
            },
            tool_context
        )
