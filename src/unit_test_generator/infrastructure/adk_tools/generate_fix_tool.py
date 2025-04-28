# src/unit_test_generator/infrastructure/adk_tools/generate_fix_tool.py
"""
ADK Tool for generating fixes for failing tests.
"""
import logging
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple

from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError
from unit_test_generator.application.utils.code_block_parser import parse_llm_code_block
from unit_test_generator.application.services.dependency_resolver import DependencyResolverService
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class GenerateFixTool(JUnitWriterTool):
    """Tool for generating fixes for failing tests using parallel error analysis."""

    def __init__(self,
                 llm_service: LLMServicePort,
                 error_parser: ErrorParserPort,
                 dependency_resolver: DependencyResolverService,
                 config: Dict[str, Any]):
        """
        Initialize the GenerateFixTool.

        Args:
            llm_service: An implementation of LLMServicePort
            error_parser: An implementation of ErrorParserPort
            dependency_resolver: Service for resolving dependencies
            config: Application configuration
        """
        super().__init__(
            name="generate_fix",
            description="Generates a fix for a failing test based on intelligent error analysis."
        )
        self.llm_service = llm_service
        self.error_parser = error_parser
        self.dependency_resolver = dependency_resolver
        self.config = config
        self.max_parallel_agents = config.get('self_healing', {}).get('max_parallel_agents', 3)

    def _parse_errors(self, error_output: str) -> List[ParsedError]:
        """
        Parse errors from build output.

        Args:
            error_output: Raw error output from the build system

        Returns:
            List of structured ParsedError objects
        """
        logger.info("Parsing errors from build output")
        try:
            parsed_errors = self.error_parser.parse_output(error_output)
            logger.info(f"Parsed {len(parsed_errors)} errors from build output")
            return parsed_errors
        except Exception as e:
            logger.error(f"Error parsing build output: {e}", exc_info=True)
            # Return a generic error if parsing fails
            return [ParsedError(
                message=f"Failed to parse errors: {str(e)}",
                error_type="ParsingError"
            )]

    def _resolve_dependencies_for_error(self, error: ParsedError, target_file_path: str) -> List[Tuple[str, float]]:
        """
        Resolve dependencies needed to fix a specific error.

        Args:
            error: The parsed error
            target_file_path: Path to the source file being tested

        Returns:
            List of tuples (dependency_path, relevance_score)
        """
        logger.info(f"Resolving dependencies for error: {error.error_type}")
        try:
            # Extract symbols from error
            symbols = error.involved_symbols

            # If no symbols are explicitly mentioned, try to infer from error message
            if not symbols and error.message:
                # Simple extraction of potential class names from error message
                # This is a basic implementation - could be improved with more sophisticated NLP
                words = error.message.split()
                potential_symbols = [word for word in words
                                   if word and word[0].isupper() and not word.isupper()]
                symbols = list(set(potential_symbols))  # Remove duplicates

            if not symbols:
                logger.warning("No symbols found in error to resolve dependencies")
                return []

            # Determine target module from file path
            from pathlib import Path
            target_module = Path(target_file_path).parts[0] if Path(target_file_path).parts else "unknown"

            # Create weights (all equal for now)
            weights = {symbol: 1.0 for symbol in symbols}

            # Resolve dependencies
            dependencies = self.dependency_resolver.resolve_dependencies(symbols, weights, target_module)
            logger.info(f"Resolved {len(dependencies)} dependencies for error")
            return dependencies
        except Exception as e:
            logger.error(f"Error resolving dependencies: {e}", exc_info=True)
            return []

    def _analyze_error_async(self,
                         error: ParsedError,
                         target_file_path: str,
                         target_file_content: str,
                         current_test_code: str,
                         language: str,
                         framework: str) -> Dict[str, Any]:
        """
        Analyze a single error and generate a fix recommendation.
        This is designed to run as a separate task.

        Args:
            error: The parsed error
            target_file_path: Path to the source file being tested
            target_file_content: Content of the source file
            current_test_code: Current test code that's failing
            language: Programming language
            framework: Testing framework

        Returns:
            Dictionary with analysis results and fix recommendation
        """
        error_id = id(error)  # Use object id as a unique identifier
        logger.info(f"Agent {error_id} analyzing error: {error.error_type}")

        try:
            # 1. Resolve dependencies for this error
            dependencies = self._resolve_dependencies_for_error(error, target_file_path)

            # 2. Prepare dependency content (up to 3 most relevant dependencies)
            dependency_content = []
            for dep_path, score in dependencies[:3]:  # Limit to top 3 dependencies
                try:
                    # This would need to be implemented or use a file system adapter
                    # For now, we'll just include the paths
                    dependency_content.append({
                        "path": dep_path,
                        "relevance_score": score
                    })
                except Exception as e:
                    logger.warning(f"Could not load dependency content for {dep_path}: {e}")

            # 3. Create a focused prompt for this specific error
            error_context = {
                "target_file_path": target_file_path,
                "target_file_content": target_file_content,
                "current_test_code": current_test_code,
                "specific_error": {
                    "file_path": error.file_path,
                    "line_number": error.line_number,
                    "message": error.message,
                    "error_type": error.error_type,
                    "error_category": error.error_category,
                    "suggested_fix": error.suggested_fix,
                    "involved_symbols": error.involved_symbols
                },
                "relevant_dependencies": dependency_content,
                "language": language,
                "framework": framework,
                "task": "analyze_single_error"  # Signal that this is a focused analysis
            }

            # 4. Call LLM to analyze this specific error
            logger.info(f"Agent {error_id} requesting analysis from LLM")
            analysis_response = self.llm_service.generate_tests(error_context)

            # 5. Return the analysis results
            return {
                "error_id": error_id,
                "error_type": error.error_type,
                "error_category": error.error_category,
                "error_message": error.message,
                "suggested_fix": error.suggested_fix,
                "analysis": analysis_response,
                "dependencies": [dep[0] for dep in dependencies],
                "success": bool(analysis_response)
            }

        except Exception as e:
            logger.error(f"Error in agent {error_id}: {e}", exc_info=True)
            return {
                "error_id": error_id,
                "error_type": error.error_type if hasattr(error, 'error_type') else "Unknown",
                "error_category": error.error_category if hasattr(error, 'error_category') else "Other",
                "error_message": error.message if hasattr(error, 'message') else str(e),
                "suggested_fix": error.suggested_fix if hasattr(error, 'suggested_fix') else "",
                "analysis": f"Failed to analyze: {str(e)}",
                "dependencies": [],
                "success": False
            }

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to generate a fix using parallel error analysis.

        Args:
            parameters: Dictionary containing:
                - target_file_path: Path to the source file being tested
                - target_file_content: Content of the source file
                - current_test_code: Current test code that's failing
                - error_output: Error output from the build system
                - language: (Optional) Programming language
                - framework: (Optional) Testing framework

        Returns:
            Dictionary containing:
                - fixed_code: The fixed test code
                - success: Boolean indicating if a fix was generated
                - analysis: Detailed analysis of errors and fixes
        """
        # Extract required parameters
        target_file_path = parameters.get("target_file_path")
        target_file_content = parameters.get("target_file_content")
        current_test_code = parameters.get("current_test_code")
        error_output = parameters.get("error_output")

        # Check required parameters
        if not all([target_file_path, target_file_content, current_test_code, error_output]):
            missing = []
            if not target_file_path: missing.append("target_file_path")
            if not target_file_content: missing.append("target_file_content")
            if not current_test_code: missing.append("current_test_code")
            if not error_output: missing.append("error_output")
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")

        # Extract optional parameters or use defaults from config
        language = parameters.get("language", self.config.get('generation', {}).get('target_language', 'Kotlin'))
        framework = parameters.get("framework", self.config.get('generation', {}).get('target_framework', 'JUnit5 with MockK'))

        try:
            # 1. Parse errors from build output
            parsed_errors = self._parse_errors(error_output)
            if not parsed_errors:
                logger.warning("No errors found in build output")
                return {
                    "fixed_code": None,
                    "success": False,
                    "message": "No errors found in build output",
                    "analysis": {"errors": []}
                }

            # 2. Limit the number of errors to analyze (focus on most important)
            # Sort errors by type and category priority
            def error_priority(error):
                # Primary sort by error type: Compilation > TestFailure > Runtime > Other
                type_priorities = {"Compilation": 0, "TestFailure": 1, "Runtime": 2}
                type_priority = type_priorities.get(error.error_type, 3)

                # Secondary sort by error category
                category_priorities = {
                    "UnresolvedReference": 0,  # Missing imports are usually easy to fix
                    "MissingDependency": 1,   # Missing dependencies are critical
                    "TypeMismatch": 2,        # Type mismatches are common
                    "MockkVerificationFailure": 3,  # MockK issues are important for tests
                    "NullPointerException": 4,  # NPEs are critical
                    "AssertionFailure": 5,    # Assertion failures may need logic changes
                    "SyntaxError": 6,         # Syntax errors are fundamental
                    "Other": 7                # Other errors are less categorized
                }
                category_priority = category_priorities.get(error.error_category, 7)

                # Return a tuple for multi-level sorting
                return (type_priority, category_priority)

            sorted_errors = sorted(parsed_errors, key=error_priority)
            errors_to_analyze = sorted_errors[:min(len(sorted_errors), self.max_parallel_agents)]

            logger.info(f"Analyzing {len(errors_to_analyze)} errors in parallel (out of {len(parsed_errors)} total)")

            # 3. Analyze errors in parallel using ThreadPoolExecutor
            # This avoids issues with nested event loops
            error_analyses = []

            def analyze_error_sync(error):
                """Synchronous wrapper for error analysis"""
                # This is a simple wrapper that calls the analysis method directly
                # and handles any exceptions
                try:
                    # Call the analysis method directly (it's no longer async)
                    result = self._analyze_error_async(
                        error=error,
                        target_file_path=target_file_path,
                        target_file_content=target_file_content,
                        current_test_code=current_test_code,
                        language=language,
                        framework=framework
                    )
                except Exception as e:
                    logger.error(f"Error analyzing error: {e}", exc_info=True)
                    # Return a basic error result
                    result = {
                        "error_id": id(error),
                        "error_type": error.error_type if hasattr(error, 'error_type') else "Unknown",
                        "error_category": error.error_category if hasattr(error, 'error_category') else "Other",
                        "error_message": error.message if hasattr(error, 'message') else str(e),
                        "suggested_fix": error.suggested_fix if hasattr(error, 'suggested_fix') else "",
                        "analysis": f"Failed to analyze: {str(e)}",
                        "dependencies": [],
                        "success": False
                    }
                return result

            # Process errors in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_parallel_agents) as executor:
                # Submit all tasks
                future_to_error = {executor.submit(analyze_error_sync, error): error for error in errors_to_analyze}

                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_error):
                    error = future_to_error[future]
                    try:
                        result = future.result()
                        if result:
                            error_analyses.append(result)
                    except Exception as e:
                        logger.error(f"Error processing result for {error.error_type}: {e}", exc_info=True)
                        # Add a basic error result
                        error_analyses.append({
                            "error_id": id(error),
                            "error_type": error.error_type if hasattr(error, 'error_type') else "Unknown",
                            "error_category": error.error_category if hasattr(error, 'error_category') else "Other",
                            "error_message": error.message if hasattr(error, 'message') else str(e),
                            "suggested_fix": error.suggested_fix if hasattr(error, 'suggested_fix') else "",
                            "analysis": f"Failed to process result: {str(e)}",
                            "dependencies": [],
                            "success": False
                        })

            # 4. Consolidate analyses into a comprehensive fix
            logger.info("Consolidating error analyses into a comprehensive fix")

            # Prepare the consolidated context with all analyses
            consolidated_context = {
                "target_file_path": target_file_path,
                "target_file_content": target_file_content,
                "current_test_code": current_test_code,
                "language": language,
                "framework": framework,
                "error_analyses": error_analyses,
                "all_errors_count": len(parsed_errors),
                "analyzed_errors_count": len(errors_to_analyze),
                "task": "generate_comprehensive_fix"
            }

            # 5. Generate the final fix
            logger.info("Requesting comprehensive fix from LLM")
            suggested_fixed_code_raw = self.llm_service.generate_tests(consolidated_context)

            # Parse the response to get only the code block
            suggested_fixed_code = parse_llm_code_block(
                suggested_fixed_code_raw,
                language
            )

            # 6. Return the results
            if suggested_fixed_code and suggested_fixed_code != current_test_code:
                logger.info("Successfully generated a comprehensive fix")
                return {
                    "fixed_code": suggested_fixed_code,
                    "success": True,
                    "analysis": {
                        "errors": error_analyses,
                        "total_errors": len(parsed_errors),
                        "analyzed_errors": len(errors_to_analyze)
                    }
                }
            elif suggested_fixed_code == current_test_code:
                logger.warning("LLM returned the same code as before")
                return {
                    "fixed_code": current_test_code,
                    "success": False,
                    "message": "LLM returned the same code as before",
                    "analysis": {"errors": error_analyses}
                }
            else:
                logger.warning("LLM did not return a valid code block for the fix")
                return {
                    "fixed_code": None,
                    "success": False,
                    "message": "LLM did not return a valid code block",
                    "analysis": {"errors": error_analyses}
                }

        except Exception as e:
            logger.error(f"Error during fix generation: {e}", exc_info=True)
            return {
                "fixed_code": None,
                "success": False,
                "message": f"Error during fix generation: {str(e)}",
                "analysis": {"error": str(e)}
            }
