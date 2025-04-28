"""
Agent for generating test code.
"""
import logging
from pathlib import Path
from typing import Dict, Any, List

from unit_test_generator.domain.models.agent_models import Agent, AgentState

logger = logging.getLogger(__name__)


class GenerateAgent(Agent):
    """
    Agent for generating test code.
    """

    def _observe(self, state: AgentState) -> Dict[str, Any]:
        """
        Gather information about the source code and analysis.

        Args:
            state: The current state

        Returns:
            Observations about the source code and analysis
        """
        logger.info(f"Generate agent observing state: {state.data.keys()}")
        logger.info(f"Generate agent state iteration: {state.iteration}")
        logger.info(f"Generate agent state success: {state.success}")

        # Force the agent to execute at least one iteration
        if state.iteration == 0 and state.success:
            logger.info("Resetting success flag to force at least one iteration")
            state = state.mark_failure()

        target_file_rel_path = state.data.get("target_file_rel_path")
        file_content = state.data.get("file_content")
        complexity = state.data.get("complexity", "medium")
        approach = state.data.get("approach", "standard")
        has_good_examples = state.data.get("has_good_examples", False)
        update_mode = state.data.get("update_mode", False)
        existing_test_file = state.data.get("existing_test_file")
        rag_results = state.data.get("rag_results", [])

        logger.info(f"Generating tests for {target_file_rel_path} with complexity {complexity} and approach {approach}")
        logger.info(f"Update mode: {update_mode}, Has good examples: {has_good_examples}")
        logger.info(f"Existing test file: {existing_test_file}")

        # If update mode, read the existing test file
        existing_test_content = None
        if update_mode and existing_test_file:
            try:
                file_system = self.tools.get("file_system")
                if file_system:
                    logger.info(f"Reading existing test file: {existing_test_file}")
                    if isinstance(existing_test_file, tuple):
                        # If it's a tuple, the first element is the path and the second is the content
                        existing_test_path, existing_test_content = existing_test_file
                        logger.info(f"Using provided test content from tuple for {existing_test_path}")
                    else:
                        # Otherwise, read the file from disk
                        existing_test_content = file_system.read_file(existing_test_file)
                        logger.info(f"Read existing test file from disk: {existing_test_file}")
                else:
                    logger.error("File system tool not available")
            except Exception as e:
                logger.error(f"Error reading existing test file: {e}")

        return {
            "file_path": target_file_rel_path,
            "file_content": file_content,
            "complexity": complexity,
            "approach": approach,
            "has_good_examples": has_good_examples,
            "update_mode": update_mode,
            "existing_test_file": existing_test_file,
            "existing_test_content": existing_test_content,
            "rag_results": rag_results
        }

    def _think(self, observations: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """
        Reason about how to generate tests.

        Args:
            observations: Observations about the source code and analysis
            state: The current state

        Returns:
            Thoughts about test generation
        """
        logger.info(f"Generate agent thinking about observations: {observations.keys()}")

        file_path = observations.get("file_path")
        complexity = observations.get("complexity")
        approach = observations.get("approach")
        update_mode = observations.get("update_mode")
        existing_test_content = observations.get("existing_test_content")

        # Determine the generation strategy
        if update_mode:
            strategy = "update"
            logger.info(f"Using update strategy for {file_path}")
            logger.info(f"Existing test content available: {existing_test_content is not None}")
        elif approach == "incremental":
            strategy = "incremental"
            logger.info(f"Using incremental strategy for {file_path} due to high complexity")
        else:
            strategy = "standard"
            logger.info(f"Using standard strategy for {file_path}")

        # Determine if we should use RAG examples
        use_rag = observations.get("has_good_examples", False)
        logger.info(f"Using RAG examples: {use_rag}")

        return {
            "strategy": strategy,
            "use_rag": use_rag,
            "generation_ready": True
        }

    def _decide_actions(self, thoughts: Dict[str, Any], state: AgentState) -> List[Dict[str, Any]]:
        """
        Decide on actions to take.

        Args:
            thoughts: Thoughts about test generation
            state: The current state

        Returns:
            List of actions to take
        """
        logger.info(f"Generate agent deciding actions based on thoughts: {thoughts}")

        strategy = thoughts.get("strategy", "standard")
        use_rag = thoughts.get("use_rag", False)

        # Build context for LLM
        observations = state.observations[-1] if state.observations else {}
        logger.info(f"Using observations from state: {observations.keys() if observations else 'None'}")

        context = {
            "target_file_path": observations.get("file_path"),
            "target_file_content": observations.get("file_content"),
            "language": state.data.get("language", "Kotlin"),
            "framework": state.data.get("framework", "JUnit5 with MockK"),
            "update_mode": observations.get("update_mode", False),
            "existing_test_content": observations.get("existing_test_content"),
            "similar_files_with_tests": observations.get("rag_results", []) if use_rag else []
        }

        logger.info(f"Built context for LLM: {context.keys()}")
        logger.info(f"Update mode: {context.get('update_mode')}, Existing test content available: {context.get('existing_test_content') is not None}")

        # Generate tests using LLM
        logger.info(f"Deciding to use LLM to generate tests with strategy: {strategy}")
        return [{"tool": "llm", "args": {
            "action": "generate_tests",
            "context": context,
            "strategy": strategy
        }}]

    def _execute_actions(self, actions: List[Dict[str, Any]], state: AgentState) -> List[Dict[str, Any]]:
        """
        Execute the actions.

        Args:
            actions: List of actions to take
            state: The current state

        Returns:
            Results of the actions
        """
        logger.info(f"Generate agent executing {len(actions)} actions")
        results = []

        for i, action in enumerate(actions):
            tool_name = action.get("tool")
            args = action.get("args", {})
            logger.info(f"Executing action {i+1}/{len(actions)}: tool={tool_name}, args={args.keys()}")

            if tool_name == "llm":
                llm_action = args.get("action")
                context = args.get("context", {})
                strategy = args.get("strategy", "standard")
                logger.info(f"LLM action: {llm_action}, strategy: {strategy}")

                if llm_action == "generate_tests":
                    try:
                        llm_service = self.tools.get("llm")
                        logger.info(f"LLM service: {type(llm_service).__name__ if llm_service else None}")

                        if not llm_service:
                            logger.error("LLM service not found in tools")
                            results.append({
                                "success": False,
                                "error": "LLM service not found in tools"
                            })
                            return results

                        # Generate tests using LLM
                        logger.info(f"Generating tests using LLM with strategy: {strategy}")
                        logger.info(f"Context keys: {context.keys()}")

                        # Always generate new tests, even in update mode
                        if False:  # Disabled the shortcut to use existing content
                            logger.info("Using existing test content for update mode")
                            # In update mode, we can just use the existing test content
                            generated_code_raw = context.get("existing_test_content")
                            logger.info(f"Using existing test content of length: {len(generated_code_raw) if generated_code_raw else 0}")
                        else:
                            # Generate new tests
                            try:
                                logger.info("Calling LLM service to generate tests")
                                generated_code_raw = llm_service.generate_tests(context)
                                logger.info(f"LLM returned generated code of length: {len(generated_code_raw) if generated_code_raw else 0}")
                            except Exception as e:
                                logger.error(f"Error calling LLM service: {e}")
                                # For now, in case of error, use existing test content if available
                                if context.get("update_mode") and context.get("existing_test_content"):
                                    logger.info("Falling back to existing test content after LLM error")
                                    generated_code_raw = context.get("existing_test_content")
                                    logger.info(f"Using existing test content of length: {len(generated_code_raw) if generated_code_raw else 0}")
                                else:
                                    logger.error("No fallback available, re-raising exception")
                                    raise

                        # Parse the code block
                        try:
                            from unit_test_generator.application.utils.code_block_parser import parse_llm_code_block
                            logger.info("Parsing generated code block")
                            generated_code = parse_llm_code_block(
                                generated_code_raw,
                                context.get("language", "kotlin")
                            )
                            logger.info(f"Parsed code block, result length: {len(generated_code) if generated_code else 0}")

                            if not generated_code:
                                logger.error("LLM failed to generate test code or returned invalid format")
                                results.append({
                                    "success": False,
                                    "error": "LLM failed to generate test code or returned invalid format"
                                })
                            else:
                                logger.info("Successfully received generated test code")
                                results.append({
                                    "success": True,
                                    "generated_code": generated_code
                                })
                        except Exception as e:
                            logger.error(f"Error parsing code block: {e}")
                            # If we're in update mode and have existing test content, use it directly
                            if context.get("update_mode") and context.get("existing_test_content"):
                                logger.info("Using existing test content directly due to parsing error")
                                results.append({
                                    "success": True,
                                    "generated_code": context.get("existing_test_content")
                                })
                            else:
                                results.append({
                                    "success": False,
                                    "error": f"Error parsing code block: {str(e)}"
                                })
                    except Exception as e:
                        logger.error(f"Error generating tests: {e}")
                        results.append({
                            "success": False,
                            "error": str(e)
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
        logger.info(f"Updating state with {len(results)} action results")

        # Check if we have any successful results
        success = False
        generated_code = None
        error_message = None

        for i, result in enumerate(results):
            logger.info(f"Processing result {i+1}/{len(results)}: success={result.get('success', False)}")
            if result.get("success", False):
                success = True
                generated_code = result.get("generated_code")
                logger.info(f"Found successful result with generated code of length: {len(generated_code) if generated_code else 0}")
            else:
                error_message = result.get("error", "Unknown error during test generation")
                logger.info(f"Found error result: {error_message}")

        if success and generated_code:
            logger.info("Successfully generated code, writing to file")
            # Write the generated code to a file
            try:
                file_system = self.tools.get("file_system")
                if not file_system:
                    logger.error("File system tool not available")
                    return state.update({
                        "test_code": generated_code,
                        "generation_complete": True,
                        "success": False,
                        "error_message": "File system tool not available",
                        "test_code_generated": True,
                        "test_file_written": False
                    })

                target_file_rel_path = state.data.get("target_file_rel_path")
                repo_root = state.data.get("repo_root")
                logger.info(f"Target file: {target_file_rel_path}, Repo root: {repo_root}")

                # Determine the output path
                from unit_test_generator.application.services.test_output_path_resolver import TestOutputPathResolver
                path_resolver = TestOutputPathResolver(self.config, Path(repo_root))
                path_resolver.set_file_system(file_system)
                output_test_abs_path = path_resolver.resolve(target_file_rel_path)
                logger.info(f"Resolved output path: {output_test_abs_path}")

                # Write the file
                logger.info(f"Writing generated test code to {output_test_abs_path}")
                file_system.write_file(str(output_test_abs_path), generated_code)
                logger.info(f"Successfully wrote test file of length {len(generated_code)}")

                # Update the state
                logger.info("Updating state with success=True")
                return state.update({
                    "test_code": generated_code,
                    "test_file_path": str(output_test_abs_path),
                    "test_file_rel_path": str(output_test_abs_path.relative_to(Path(repo_root))),
                    "generation_complete": True,
                    "success": True,
                    "test_code_generated": True,
                    "test_file_written": True
                })
            except Exception as e:
                logger.error(f"Error writing test file: {e}", exc_info=True)
                return state.update({
                    "test_code": generated_code,
                    "generation_complete": True,
                    "success": False,
                    "error_message": f"Error writing test file: {e}",
                    "test_code_generated": True,
                    "test_file_written": False
                })
        else:
            # Update the state with the error
            logger.info(f"Updating state with success=False, error: {error_message}")
            return state.update({
                "generation_complete": True,
                "success": False,
                "error_message": error_message,
                "test_code_generated": False,
                "test_file_written": False
            })

    def _is_success(self, state: AgentState) -> bool:
        """
        Determine if the agent has achieved its goal.

        Args:
            state: The current state

        Returns:
            True if the goal has been achieved, False otherwise
        """
        # Generation is successful if the test code was generated and written to a file
        return state.data.get("test_code_generated", False) and state.data.get("test_file_written", False)
