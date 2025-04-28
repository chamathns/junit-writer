# src/unit_test_generator/infrastructure/adk_tools/simplified_runner.py
"""
Simplified runner for ADK tools.
This module provides a simplified way to run ADK tools without the full ADK infrastructure.
"""
import logging
from typing import Dict, Any, List, Optional

from unit_test_generator.infrastructure.adk_tools.base import ADKToolBase

logger = logging.getLogger(__name__)

class SimplifiedADKRunner:
    """
    A simplified runner for ADK tools.
    This class provides a way to run ADK tools without the full ADK infrastructure.
    """
    
    def __init__(self, tools: List[ADKToolBase], config: Dict[str, Any]):
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
    
    def run(self, goal: str, initial_state: Dict[str, Any]) -> Dict[str, Any]:
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
        
        # Run the self-healing loop
        while state['attempt_count'] < self.max_iterations and not state.get('success', False):
            logger.info(f"Starting iteration {state['attempt_count'] + 1}/{self.max_iterations}")
            
            # Run the test
            if 'test_file_abs_path' in state:
                test_result = self._run_test(state['test_file_abs_path'])
                state['last_test_result'] = test_result
                
                # If the test passed, we're done
                if test_result.get('success', False):
                    state['success'] = True
                    logger.info("Test passed successfully")
                    break
                
                # Parse errors
                if 'output' in test_result:
                    errors = self._parse_errors(test_result['output'])
                    state['last_errors'] = errors
                    
                    # Generate a fix
                    if errors and errors.get('error_count', 0) > 0:
                        fix_result = self._generate_fix(
                            target_file_path=state.get('target_file_path', ''),
                            target_file_content=state.get('target_file_content', ''),
                            current_test_code=state.get('current_test_code', ''),
                            error_output=test_result.get('output', '')
                        )
                        
                        if fix_result.get('success', False) and fix_result.get('fixed_code'):
                            # Write the fixed code to the file
                            write_result = self._write_file(
                                state['test_file_abs_path'],
                                fix_result['fixed_code']
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
    
    def _run_test(self, test_file_abs_path: str) -> Dict[str, Any]:
        """
        Run a test using the run_test tool.
        
        Args:
            test_file_abs_path: Absolute path to the test file
            
        Returns:
            The result of running the test
        """
        if 'run_test' not in self.tools:
            logger.error("run_test tool not found")
            return {"success": False, "error": "run_test tool not found"}
        
        logger.info(f"Running test: {test_file_abs_path}")
        return self.tools['run_test'].process_llm_request({"test_file_abs_path": test_file_abs_path})
    
    def _parse_errors(self, raw_output: str) -> Dict[str, Any]:
        """
        Parse errors using the parse_errors tool.
        
        Args:
            raw_output: Raw output from the test run
            
        Returns:
            The parsed errors
        """
        if 'parse_errors' not in self.tools:
            logger.error("parse_errors tool not found")
            return {"success": False, "error": "parse_errors tool not found"}
        
        logger.info("Parsing errors from test output")
        return self.tools['parse_errors'].process_llm_request({"raw_output": raw_output})
    
    def _generate_fix(self, target_file_path: str, target_file_content: str, current_test_code: str, error_output: str) -> Dict[str, Any]:
        """
        Generate a fix using the generate_fix tool.
        
        Args:
            target_file_path: Path to the target file
            target_file_content: Content of the target file
            current_test_code: Current test code
            error_output: Error output from the test run
            
        Returns:
            The generated fix
        """
        if 'generate_fix' not in self.tools:
            logger.error("generate_fix tool not found")
            return {"success": False, "error": "generate_fix tool not found"}
        
        logger.info("Generating fix for test")
        return self.tools['generate_fix'].process_llm_request({
            "target_file_path": target_file_path,
            "target_file_content": target_file_content,
            "current_test_code": current_test_code,
            "error_output": error_output
        })
    
    def _write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Write a file using the write_file tool.
        
        Args:
            file_path: Path to the file
            content: Content to write
            
        Returns:
            The result of writing the file
        """
        if 'write_file' not in self.tools:
            logger.error("write_file tool not found")
            return {"success": False, "error": "write_file tool not found"}
        
        logger.info(f"Writing to file: {file_path}")
        return self.tools['write_file'].process_llm_request({
            "file_path": file_path,
            "content": content
        })
