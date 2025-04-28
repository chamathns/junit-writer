"""
Agent for fixing test code.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from unit_test_generator.domain.models.agent_models import Agent, AgentState
from unit_test_generator.domain.ports.error_parser import ParsedError

logger = logging.getLogger(__name__)


class FixAgent(Agent):
    """
    Agent for fixing test code.
    """

    def __init__(self, name: str, tools: Dict[str, Any], config: Dict[str, Any]):
        """
        Initialize the fix agent.

        Args:
            name: The name of the agent
            tools: Dictionary of tools available to the agent
            config: Configuration dictionary
        """
        super().__init__(name, tools, config)
        self.max_iterations = config.get(f"agents.{name}.max_iterations", 5)

    def _observe(self, state: AgentState) -> Dict[str, Any]:
        """
        Gather information about the test code and errors.

        Args:
            state: The current state

        Returns:
            Observations about the test code and errors
        """
        logger.info("Fix agent observing state")

        # Extract necessary information from state
        test_file_path = state.data.get("test_file_path")
        test_code = state.data.get("test_code")
        target_file_abs_path = state.data.get("target_file_abs_path")
        target_file_content = state.data.get("file_content")

        if not test_file_path or not test_code:
            logger.error("Missing test file path or test code in state")
            return {
                "error": "Missing test file path or test code",
                "can_fix": False
            }

        # Run the test to see if it passes
        logger.info(f"Running test: {test_file_path}")
        run_test_tool = self.tools.get("run_test")
        if not run_test_tool:
            logger.error("Run test tool not available")
            return {
                "error": "Run test tool not available",
                "can_fix": False
            }

        # First try to compile the test
        compile_result = run_test_tool._execute({
            "test_file_abs_path": test_file_path,
            "compile_only": True
        })

        # Check if compilation succeeded
        if compile_result.get("success", False):
            logger.info("Test compilation succeeded, running test")
            # Now run the test
            run_result = run_test_tool._execute({
                "test_file_abs_path": test_file_path,
                "compile_only": False
            })

            if run_result.get("success", False):
                logger.info("Test execution succeeded")
                return {
                    "test_passed": True,
                    "can_fix": False,  # No need to fix if test passes
                    "test_file_path": test_file_path,
                    "test_code": test_code,
                    "target_file_abs_path": target_file_abs_path,
                    "target_file_content": target_file_content
                }
            else:
                logger.info("Test execution failed, parsing errors")
                # Parse errors from test execution
                parse_errors_tool = self.tools.get("parse_errors")
                if not parse_errors_tool:
                    logger.error("Parse errors tool not available")
                    return {
                        "test_passed": False,
                        "can_fix": True,
                        "raw_error_output": run_result.get("output", ""),
                        "test_file_path": test_file_path,
                        "test_code": test_code,
                        "target_file_abs_path": target_file_abs_path,
                        "target_file_content": target_file_content
                    }

                parsed_errors = parse_errors_tool._execute({
                    "raw_output": run_result.get("output", "")
                })

                return {
                    "test_passed": False,
                    "can_fix": True,
                    "errors": parsed_errors.get("errors", []),
                    "raw_error_output": run_result.get("output", ""),
                    "test_file_path": test_file_path,
                    "test_code": test_code,
                    "target_file_abs_path": target_file_abs_path,
                    "target_file_content": target_file_content
                }
        else:
            logger.info("Test compilation failed, parsing errors")
            # Parse errors from compilation
            parse_errors_tool = self.tools.get("parse_errors")
            if not parse_errors_tool:
                logger.error("Parse errors tool not available")
                return {
                    "test_passed": False,
                    "can_fix": True,
                    "raw_error_output": compile_result.get("output", ""),
                    "test_file_path": test_file_path,
                    "test_code": test_code,
                    "target_file_abs_path": target_file_abs_path,
                    "target_file_content": target_file_content
                }

            parsed_errors = parse_errors_tool._execute({
                "raw_output": compile_result.get("output", "")
            })

            return {
                "test_passed": False,
                "can_fix": True,
                "errors": parsed_errors.get("errors", []),
                "raw_error_output": compile_result.get("output", ""),
                "test_file_path": test_file_path,
                "test_code": test_code,
                "target_file_abs_path": target_file_abs_path,
                "target_file_content": target_file_content
            }

    def _think(self, observations: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """
        Reason about how to fix the test code.

        Args:
            observations: Observations about the test code and errors
            state: The current state

        Returns:
            Thoughts about test fixing
        """
        logger.info("Fix agent thinking about how to fix the test")

        # Check if we can fix the test
        can_fix = observations.get("can_fix", False)
        if not can_fix:
            logger.info("Cannot fix the test")
            if observations.get("test_passed", False):
                return {
                    "can_fix": False,
                    "reason": "Test already passes",
                    "needs_fixing": False
                }
            else:
                return {
                    "can_fix": False,
                    "reason": observations.get("error", "Unknown error"),
                    "needs_fixing": False
                }

        # Check if we have errors to fix
        errors = observations.get("errors", [])
        raw_error_output = observations.get("raw_error_output")

        # Log the error information for debugging
        logger.info(f"Found {len(errors)} structured errors")
        logger.info(f"Raw error output available: {raw_error_output is not None}")
        if raw_error_output:
            logger.info(f"Raw error output length: {len(raw_error_output)}")

        if not errors and not raw_error_output:
            logger.warning("No errors to fix")
            return {
                "can_fix": False,
                "reason": "No errors to fix",
                "needs_fixing": False
            }

        # Determine the approach to fixing the test
        if errors:
            logger.info(f"Found {len(errors)} structured errors to fix")
            # Use intelligent fix if we have structured errors
            return {
                "can_fix": True,
                "approach": "intelligent",
                "errors": errors,
                "raw_error_output": raw_error_output,
                "test_file_path": observations.get("test_file_path"),
                "test_code": observations.get("test_code"),
                "target_file_abs_path": observations.get("target_file_abs_path"),
                "target_file_content": observations.get("target_file_content"),
                "needs_fixing": True
            }
        else:
            logger.info("Using raw error output for fixing")
            # Use raw error output if we don't have structured errors
            return {
                "can_fix": True,
                "approach": "intelligent",  # Try intelligent approach first
                "raw_error_output": raw_error_output,
                "test_file_path": observations.get("test_file_path"),
                "test_code": observations.get("test_code"),
                "target_file_abs_path": observations.get("target_file_abs_path"),
                "target_file_content": observations.get("target_file_content"),
                "needs_fixing": True
            }

    def _decide_actions(self, thoughts: Dict[str, Any], state: AgentState) -> List[Dict[str, Any]]:
        """
        Decide on actions to take.

        Args:
            thoughts: Thoughts about test fixing
            state: The current state

        Returns:
            List of actions to take
        """
        logger.info("Fix agent deciding on actions")

        # Check if we need to fix the test
        if not thoughts.get("needs_fixing", False):
            logger.info("No fixing needed")
            return []

        # Get the approach to fixing the test
        approach = thoughts.get("approach")
        if approach == "intelligent":
            logger.info("Using intelligent fix approach")
            # Use the intelligent fix tool if available
            intelligent_fix_tool = self.tools.get("intelligent_fix")
            if intelligent_fix_tool:
                # Make sure we have the raw error output
                raw_error_output = thoughts.get("raw_error_output")
                if not raw_error_output:
                    logger.warning("Missing raw_error_output in thoughts, this will cause the intelligent_fix tool to fail")
                    logger.debug(f"Available thought keys: {list(thoughts.keys())}")

                # Log the error output for debugging
                logger.info(f"Raw error output length: {len(raw_error_output) if raw_error_output else 0}")

                return [{
                    "tool": "intelligent_fix",
                    "args": {
                        "target_file_path": thoughts.get("target_file_abs_path"),
                        "target_file_content": thoughts.get("target_file_content"),
                        "test_file_path": thoughts.get("test_file_path"),
                        "current_test_code": thoughts.get("test_code"),
                        "error_output": raw_error_output or "Compilation error occurred but no detailed output was captured."
                    }
                }]
            else:
                logger.warning("Intelligent fix tool not available, falling back to generate fix")
                # Fall back to generate fix
                approach = "raw"

        if approach == "raw":
            logger.info("Using generate fix approach")
            # Use the generate fix tool
            generate_fix_tool = self.tools.get("generate_fix")
            if generate_fix_tool:
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
                logger.error("No fix tools available")
                return []

        logger.error(f"Unknown approach: {approach}")
        return []

    def _execute_actions(self, actions: List[Dict[str, Any]], state: AgentState) -> List[Dict[str, Any]]:
        """
        Execute the actions.

        Args:
            actions: List of actions to take
            state: The current state

        Returns:
            Results of the actions
        """
        logger.info(f"Fix agent executing {len(actions)} actions")
        results = []

        for action in actions:
            tool_name = action.get("tool")
            args = action.get("args", {})

            logger.info(f"Executing tool: {tool_name}")
            tool = self.tools.get(tool_name)
            if not tool:
                logger.error(f"Tool not found: {tool_name}")
                results.append({
                    "success": False,
                    "error": f"Tool not found: {tool_name}"
                })
                continue

            try:
                # Log the tool arguments for debugging
                logger.info(f"Tool {tool_name} arguments: {args.keys()}")
                if 'error_output' in args:
                    logger.info(f"Error output length: {len(args['error_output']) if args['error_output'] else 0}")

                result = tool._execute(args)
                results.append(result)
                logger.info(f"Tool {tool_name} executed successfully")
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                results.append({
                    "success": False,
                    "error": f"Error executing tool {tool_name}: {str(e)}"
                })

        return results

    def _update_state(self, state: AgentState, results: List[Dict[str, Any]]) -> AgentState:
        """
        Update the state based on action results.

        Args:
            state: The current state
            results: Results of the actions

        Returns:
            Updated state
        """
        logger.info("Fix agent updating state")

        # If no results, return the original state
        if not results:
            logger.info("No results to update state with")
            return state.update({
                "fix_complete": True,
                "fix_success": False,
                "fix_message": "No actions were taken"
            })

        # Check if any of the results were successful
        success = any(result.get("success", False) for result in results)

        # If successful, update the test code
        if success:
            logger.info("Fix was successful")
            # Find the result with the fixed code
            for result in results:
                if result.get("success", False) and "fixed_code" in result:
                    fixed_code = result.get("fixed_code")
                    logger.info(f"Found fixed code of length {len(fixed_code) if fixed_code else 0}")

                    # Write the fixed code to the file
                    test_file_path = state.data.get("test_file_path")
                    if test_file_path and fixed_code:
                        logger.info(f"Writing fixed code to {test_file_path}")
                        file_system = self.tools.get("file_system")
                        if file_system:
                            try:
                                file_system._execute({"path": test_file_path, "content": fixed_code})
                                logger.info("Successfully wrote fixed code to file")
                            except Exception as e:
                                logger.error(f"Error writing fixed code to file: {e}")
                                return state.update({
                                    "fix_complete": True,
                                    "fix_success": False,
                                    "fix_message": f"Error writing fixed code to file: {str(e)}",
                                    "fixed_code": fixed_code
                                })

                    # Update the state with the fixed code
                    return state.update({
                        "test_code": fixed_code,
                        "fix_complete": True,
                        "fix_success": True,
                        "fix_message": "Successfully fixed the test",
                        "test_fixed": True
                    })

        # If not successful, return the original state with an error message
        logger.warning("Fix was not successful")
        error_messages = [result.get("error", "Unknown error") for result in results if "error" in result]
        error_message = "; ".join(error_messages) if error_messages else "Unknown error during fix"

        return state.update({
            "fix_complete": True,
            "fix_success": False,
            "fix_message": error_message
        })

    def _is_success(self, state: AgentState) -> bool:
        """
        Determine if the test fixing is complete.

        Args:
            state: The current state

        Returns:
            True if the test fixing is complete, False otherwise
        """
        # Check if the fix is complete
        fix_complete = state.data.get("fix_complete", False)

        # If the fix is complete, check if it was successful
        if fix_complete:
            fix_success = state.data.get("fix_success", False)
            logger.info(f"Fix complete with success={fix_success}")

            # If the fix was successful, run the test again to verify
            if fix_success and state.data.get("test_fixed", False):
                test_file_path = state.data.get("test_file_path")
                if test_file_path:
                    logger.info(f"Verifying fix by running test again: {test_file_path}")
                    run_test_tool = self.tools.get("run_test")
                    if run_test_tool:
                        try:
                            run_result = run_test_tool._execute({
                                "test_file_abs_path": test_file_path,
                                "compile_only": False
                            })

                            if run_result.get("success", False):
                                logger.info("Test now passes, fix was successful")
                                return True
                            else:
                                logger.warning("Test still fails after fix")
                                return False
                        except Exception as e:
                            logger.error(f"Error verifying fix: {e}")
                            return False

        return fix_complete
