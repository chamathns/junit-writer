"""
Reasoning Agent for multi-step reasoning and acting.
"""
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from unit_test_generator.application.agents.base_agent import BaseAgent
from unit_test_generator.domain.models.agent_state import AgentState

logger = logging.getLogger(__name__)

class ReasoningAgent(BaseAgent):
    """
    Agent that can perform multi-step reasoning and acting to fix tests.
    This agent uses multiple LLM calls to analyze errors, reason about them,
    and take appropriate actions to fix tests.
    """

    def __init__(self, tools: Dict[str, Any], config: Dict[str, Any]):
        """
        Initialize the reasoning agent.

        Args:
            tools: Dictionary of tools available to the agent
            config: Application configuration
        """
        super().__init__(tools, config)
        self.max_reasoning_steps = config.get("agent", {}).get("max_reasoning_steps", 5)
        self.max_fix_attempts = config.get("agent", {}).get("max_fix_attempts", 3)
        logger.info(f"ReasoningAgent initialized with {len(tools)} tools")

    def _observe(self, state: AgentState) -> Dict[str, Any]:
        """
        Observe the current state and gather information.

        Args:
            state: The current state

        Returns:
            Dictionary of observations
        """
        logger.info("Reasoning agent observing state")
        
        # Get the test file path and code
        test_file_path = state.data.get("test_file_path")
        test_code = state.data.get("test_code")
        
        # Get the target file path and content
        target_file_abs_path = state.data.get("target_file_abs_path")
        target_file_content = state.data.get("target_file_content")
        
        # Check if we have a terminal ID (for getting output)
        terminal_id = state.data.get("terminal_id")
        terminal_output = ""
        
        # If we have a terminal ID, get the output
        if terminal_id is not None:
            get_terminal_output_tool = self.tools.get("get_terminal_output")
            if get_terminal_output_tool:
                try:
                    terminal_result = get_terminal_output_tool._execute({
                        "terminal_id": terminal_id
                    })
                    terminal_output = terminal_result.get("output", "")
                    logger.info(f"Got terminal output from terminal {terminal_id}, length: {len(terminal_output)}")
                except Exception as e:
                    logger.error(f"Error getting terminal output: {e}", exc_info=True)
        
        # Parse errors from terminal output
        errors = []
        raw_error_output = terminal_output
        
        if raw_error_output:
            parse_errors_tool = self.tools.get("parse_errors")
            if parse_errors_tool:
                try:
                    parsed_errors = parse_errors_tool._execute({
                        "raw_output": raw_error_output
                    })
                    errors = parsed_errors.get("errors", [])
                    logger.info(f"Parsed {len(errors)} errors from terminal output")
                except Exception as e:
                    logger.error(f"Error parsing errors: {e}", exc_info=True)
        
        # Return observations
        return {
            "test_file_path": test_file_path,
            "test_code": test_code,
            "target_file_abs_path": target_file_abs_path,
            "target_file_content": target_file_content,
            "terminal_id": terminal_id,
            "raw_error_output": raw_error_output,
            "errors": errors,
            "can_fix": bool(test_file_path and test_code and (errors or raw_error_output)),
            "reasoning_step": state.data.get("reasoning_step", 0),
            "fix_attempts": state.data.get("fix_attempts", 0)
        }

    def _think(self, observations: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """
        Reason about the observations and decide what to do.

        Args:
            observations: Observations about the current state
            state: The current state

        Returns:
            Thoughts about what to do next
        """
        logger.info("Reasoning agent thinking about what to do")
        
        # Check if we can fix the test
        can_fix = observations.get("can_fix", False)
        if not can_fix:
            logger.info("Cannot fix the test")
            return {
                "can_fix": False,
                "reason": "Cannot fix the test",
                "needs_fixing": False
            }
        
        # Get the current reasoning step
        reasoning_step = observations.get("reasoning_step", 0)
        fix_attempts = observations.get("fix_attempts", 0)
        
        # Check if we've reached the maximum number of reasoning steps
        if reasoning_step >= self.max_reasoning_steps:
            logger.info(f"Reached maximum number of reasoning steps ({self.max_reasoning_steps})")
            return {
                "can_fix": False,
                "reason": f"Reached maximum number of reasoning steps ({self.max_reasoning_steps})",
                "needs_fixing": False
            }
        
        # Check if we've reached the maximum number of fix attempts
        if fix_attempts >= self.max_fix_attempts:
            logger.info(f"Reached maximum number of fix attempts ({self.max_fix_attempts})")
            return {
                "can_fix": False,
                "reason": f"Reached maximum number of fix attempts ({self.max_fix_attempts})",
                "needs_fixing": False
            }
        
        # Get the errors and raw error output
        errors = observations.get("errors", [])
        raw_error_output = observations.get("raw_error_output", "")
        
        # If we have no errors and no raw error output, we can't fix anything
        if not errors and not raw_error_output:
            logger.info("No errors to fix")
            return {
                "can_fix": False,
                "reason": "No errors to fix",
                "needs_fixing": False
            }
        
        # Determine the next step based on the current reasoning step
        if reasoning_step == 0:
            # First step: Analyze errors
            logger.info("First reasoning step: Analyzing errors")
            return {
                "can_fix": True,
                "action": "analyze_errors",
                "errors": errors,
                "raw_error_output": raw_error_output,
                "test_file_path": observations.get("test_file_path"),
                "test_code": observations.get("test_code"),
                "target_file_abs_path": observations.get("target_file_abs_path"),
                "target_file_content": observations.get("target_file_content"),
                "needs_fixing": True
            }
        elif reasoning_step == 1:
            # Second step: Identify missing dependencies
            logger.info("Second reasoning step: Identifying missing dependencies")
            return {
                "can_fix": True,
                "action": "identify_dependencies",
                "errors": errors,
                "raw_error_output": raw_error_output,
                "test_file_path": observations.get("test_file_path"),
                "test_code": observations.get("test_code"),
                "target_file_abs_path": observations.get("target_file_abs_path"),
                "target_file_content": observations.get("target_file_content"),
                "error_analysis": state.data.get("error_analysis", {}),
                "needs_fixing": True
            }
        else:
            # Final step: Generate fix
            logger.info("Final reasoning step: Generating fix")
            return {
                "can_fix": True,
                "action": "generate_fix",
                "errors": errors,
                "raw_error_output": raw_error_output,
                "test_file_path": observations.get("test_file_path"),
                "test_code": observations.get("test_code"),
                "target_file_abs_path": observations.get("target_file_abs_path"),
                "target_file_content": observations.get("target_file_content"),
                "error_analysis": state.data.get("error_analysis", {}),
                "dependencies": state.data.get("dependencies", {}),
                "needs_fixing": True
            }

    def _decide_actions(self, thoughts: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Decide what actions to take based on thoughts.

        Args:
            thoughts: Thoughts about what to do next

        Returns:
            List of actions to take
        """
        logger.info("Reasoning agent deciding actions")
        
        # Check if we need to fix anything
        needs_fixing = thoughts.get("needs_fixing", False)
        if not needs_fixing:
            logger.info("No actions needed")
            return []
        
        # Get the action to take
        action = thoughts.get("action")
        
        if action == "analyze_errors":
            # Use the analyze_errors tool
            analyze_errors_tool = self.tools.get("analyze_errors")
            if analyze_errors_tool:
                return [{
                    "tool": "analyze_errors",
                    "args": {
                        "raw_error_output": thoughts.get("raw_error_output", ""),
                        "errors": thoughts.get("errors", []),
                        "test_file_path": thoughts.get("test_file_path"),
                        "test_code": thoughts.get("test_code"),
                        "target_file_path": thoughts.get("target_file_abs_path"),
                        "target_file_content": thoughts.get("target_file_content")
                    }
                }]
            else:
                logger.warning("Analyze errors tool not available, falling back to intelligent fix")
                return [{
                    "tool": "intelligent_fix",
                    "args": {
                        "target_file_path": thoughts.get("target_file_abs_path"),
                        "target_file_content": thoughts.get("target_file_content"),
                        "test_file_path": thoughts.get("test_file_path"),
                        "current_test_code": thoughts.get("test_code"),
                        "error_output": thoughts.get("raw_error_output", "")
                    }
                }]
        
        elif action == "identify_dependencies":
            # Use the identify_dependencies tool
            identify_dependencies_tool = self.tools.get("identify_dependencies")
            if identify_dependencies_tool:
                return [{
                    "tool": "identify_dependencies",
                    "args": {
                        "error_analysis": thoughts.get("error_analysis", {}),
                        "test_file_path": thoughts.get("test_file_path"),
                        "target_file_path": thoughts.get("target_file_abs_path")
                    }
                }]
            else:
                logger.warning("Identify dependencies tool not available, skipping to generate fix")
                return [{
                    "tool": "intelligent_fix",
                    "args": {
                        "target_file_path": thoughts.get("target_file_abs_path"),
                        "target_file_content": thoughts.get("target_file_content"),
                        "test_file_path": thoughts.get("test_file_path"),
                        "current_test_code": thoughts.get("test_code"),
                        "error_output": thoughts.get("raw_error_output", "")
                    }
                }]
        
        elif action == "generate_fix":
            # Use the intelligent_fix tool with enhanced context
            intelligent_fix_tool = self.tools.get("intelligent_fix")
            if intelligent_fix_tool:
                return [{
                    "tool": "intelligent_fix",
                    "args": {
                        "target_file_path": thoughts.get("target_file_abs_path"),
                        "target_file_content": thoughts.get("target_file_content"),
                        "test_file_path": thoughts.get("test_file_path"),
                        "current_test_code": thoughts.get("test_code"),
                        "error_output": thoughts.get("raw_error_output", ""),
                        "error_analysis": thoughts.get("error_analysis", {}),
                        "dependencies": thoughts.get("dependencies", {})
                    }
                }]
            else:
                logger.warning("Intelligent fix tool not available, falling back to generate fix")
                return [{
                    "tool": "generate_fix",
                    "args": {
                        "target_file_path": thoughts.get("target_file_abs_path"),
                        "target_file_content": thoughts.get("target_file_content"),
                        "test_file_path": thoughts.get("test_file_path"),
                        "current_test_code": thoughts.get("test_code"),
                        "error_output": thoughts.get("raw_error_output", "")
                    }
                }]
        
        else:
            logger.warning(f"Unknown action: {action}")
            return []

    def _execute_actions(self, actions: List[Dict[str, Any]], state: AgentState) -> AgentState:
        """
        Execute the actions and update the state.

        Args:
            actions: List of actions to take
            state: The current state

        Returns:
            Updated state
        """
        logger.info(f"Reasoning agent executing {len(actions)} actions")
        
        # If there are no actions, return the current state
        if not actions:
            logger.info("No actions to execute")
            return state
        
        # Execute each action and collect results
        results = []
        for action in actions:
            tool_name = action.get("tool")
            args = action.get("args", {})
            
            logger.info(f"Executing tool: {tool_name}")
            tool = self.tools.get(tool_name)
            
            if not tool:
                logger.error(f"Tool {tool_name} not found")
                results.append({
                    "success": False,
                    "error": f"Tool {tool_name} not found"
                })
                continue
            
            try:
                # Log the tool arguments for debugging
                logger.info(f"Tool {tool_name} arguments: {args.keys()}")
                
                result = tool._execute(args)
                results.append(result)
                logger.info(f"Tool {tool_name} executed successfully")
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                results.append({
                    "success": False,
                    "error": f"Error executing tool {tool_name}: {str(e)}"
                })
        
        # Update the state based on the results
        updated_state = state
        
        # Get the current reasoning step and fix attempts
        reasoning_step = state.data.get("reasoning_step", 0)
        fix_attempts = state.data.get("fix_attempts", 0)
        
        # Increment the reasoning step
        reasoning_step += 1
        
        # Process the results based on the action
        for result in results:
            if not result.get("success", False):
                continue
            
            # If we have an error analysis result, store it
            if "analysis" in result:
                updated_state = updated_state.update({
                    "error_analysis": result.get("analysis", {})
                })
            
            # If we have a dependencies result, store it
            if "dependencies" in result:
                updated_state = updated_state.update({
                    "dependencies": result.get("dependencies", {})
                })
            
            # If we have a fixed code result, store it and run the test
            if "fixed_code" in result:
                fixed_code = result.get("fixed_code")
                test_file_path = state.data.get("test_file_path")
                
                # Update the state with the fixed code
                updated_state = updated_state.update({
                    "test_code": fixed_code
                })
                
                # Write the fixed code to the test file
                try:
                    with open(test_file_path, "w") as f:
                        f.write(fixed_code)
                    logger.info(f"Wrote fixed code to {test_file_path}")
                except Exception as e:
                    logger.error(f"Error writing fixed code to {test_file_path}: {e}", exc_info=True)
                
                # Run the test in a terminal
                run_terminal_test_tool = self.tools.get("run_terminal_test")
                if run_terminal_test_tool:
                    try:
                        terminal_result = run_terminal_test_tool._execute({
                            "test_file_abs_path": test_file_path,
                            "title": f"Test for {Path(test_file_path).name}"
                        })
                        
                        terminal_id = terminal_result.get("terminal_id")
                        output_file = terminal_result.get("output_file")
                        
                        # Update the state with the terminal information
                        updated_state = updated_state.update({
                            "terminal_id": terminal_id,
                            "output_file": output_file,
                            "test_running": True
                        })
                        
                        # Increment the fix attempts
                        fix_attempts += 1
                        
                        # Reset the reasoning step to 0 to start the process again
                        reasoning_step = 0
                    except Exception as e:
                        logger.error(f"Error running test in terminal: {e}", exc_info=True)
        
        # Update the state with the new reasoning step and fix attempts
        updated_state = updated_state.update({
            "reasoning_step": reasoning_step,
            "fix_attempts": fix_attempts
        })
        
        return updated_state

    def _is_success(self, state: AgentState) -> bool:
        """
        Determine if the agent has achieved its goal.

        Args:
            state: The current state

        Returns:
            True if the goal has been achieved, False otherwise
        """
        # Check if we've reached the maximum number of reasoning steps or fix attempts
        reasoning_step = state.data.get("reasoning_step", 0)
        fix_attempts = state.data.get("fix_attempts", 0)
        
        if reasoning_step >= self.max_reasoning_steps:
            logger.info(f"Reached maximum number of reasoning steps ({self.max_reasoning_steps})")
            return True
        
        if fix_attempts >= self.max_fix_attempts:
            logger.info(f"Reached maximum number of fix attempts ({self.max_fix_attempts})")
            return True
        
        # Check if the test is running
        test_running = state.data.get("test_running", False)
        
        # If the test is running, check if it's successful
        if test_running:
            terminal_id = state.data.get("terminal_id")
            if terminal_id is not None:
                get_terminal_output_tool = self.tools.get("get_terminal_output")
                if get_terminal_output_tool:
                    try:
                        terminal_result = get_terminal_output_tool._execute({
                            "terminal_id": terminal_id
                        })
                        terminal_output = terminal_result.get("output", "")
                        
                        # Check if the test passed
                        if "BUILD SUCCESSFUL" in terminal_output and "BUILD FAILED" not in terminal_output:
                            logger.info("Test passed successfully")
                            return True
                    except Exception as e:
                        logger.error(f"Error getting terminal output: {e}", exc_info=True)
        
        # If we're still in the reasoning process, we're not done yet
        if reasoning_step > 0 and reasoning_step < self.max_reasoning_steps:
            return False
        
        # If we've made a fix attempt but haven't reached the maximum, we're not done yet
        if fix_attempts > 0 and fix_attempts < self.max_fix_attempts:
            return False
        
        # Default to not done
        return False
