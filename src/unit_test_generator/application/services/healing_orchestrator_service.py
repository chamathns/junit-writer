# src/unit_test_generator/application/services/healing_orchestrator_service.py
"""
Service for orchestrating the healing process.
"""
import logging
import time
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple

from unit_test_generator.domain.ports.error_analysis import (
    ErrorAnalysisPort, DependencyResolutionPort, FixGenerationPort, HealingOrchestratorPort
)
from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError
from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.build_system import BuildSystemPort
from unit_test_generator.domain.models.error_analysis import (
    AnalyzedError, DependencyContext, FixProposal, HealingResult
)

logger = logging.getLogger(__name__)

class HealingOrchestratorService(HealingOrchestratorPort):
    """Service for orchestrating the healing process."""

    def __init__(self,
                error_parser: ErrorParserPort,
                error_analyzer: ErrorAnalysisPort,
                dependency_resolver: DependencyResolutionPort,
                fix_generator: FixGenerationPort,
                file_system: FileSystemPort,
                build_system: BuildSystemPort,
                config: Dict[str, Any]):
        """
        Initialize the service.

        Args:
            error_parser: Service for parsing errors
            error_analyzer: Service for analyzing errors
            dependency_resolver: Service for resolving dependencies
            fix_generator: Service for generating fixes
            file_system: File system adapter
            build_system: Build system adapter
            config: Application configuration
        """
        self.error_parser = error_parser
        self.error_analyzer = error_analyzer
        self.dependency_resolver = dependency_resolver
        self.fix_generator = fix_generator
        self.fs = file_system
        self.build_system = build_system
        self.config = config
        self.max_parallel_agents = config.get('self_healing', {}).get('max_parallel_agents', 3)

    def heal(self,
            source_file_path: str,
            source_code: str,
            test_file_path: str,
            test_code: str,
            error_output: str) -> HealingResult:
        """
        Orchestrates the healing process.

        Args:
            source_file_path: Path to the source file
            source_code: Content of the source file
            test_file_path: Path to the test file
            test_code: Content of the test file
            error_output: Error output from the build system

        Returns:
            Result of the healing process
        """
        logger.info(f"Starting healing process for {test_file_path}")

        start_time = time.time()

        # 1. Parse errors from build output
        parsed_errors = self.error_parser.parse_output(error_output)
        error_count = len(parsed_errors)

        if not parsed_errors:
            logger.warning("No errors found in build output")
            return HealingResult(
                success=False,
                fixed_code=test_code,
                error_count_before=0,
                error_count_after=0,
                message="No errors found in build output"
            )

        logger.info(f"Found {error_count} errors in build output")

        # 2. Limit the number of errors to analyze (focus on most important)
        # Sort errors by type priority: Compilation > TestFailure > Runtime > Other
        def error_priority(error):
            priorities = {"Compilation": 0, "TestFailure": 1, "Runtime": 2}
            return priorities.get(error.error_type, 3)

        sorted_errors = sorted(parsed_errors, key=error_priority)
        errors_to_analyze = sorted_errors[:min(len(sorted_errors), self.max_parallel_agents)]

        logger.info(f"Analyzing {len(errors_to_analyze)} errors in parallel (out of {error_count} total)")

        # 3. Process errors in parallel
        analyzed_errors, dependency_contexts = self._process_errors_in_parallel(
            errors_to_analyze, source_file_path, source_code, test_code
        )

        if not analyzed_errors:
            logger.warning("No errors were successfully analyzed")
            return HealingResult(
                success=False,
                fixed_code=test_code,
                error_count_before=error_count,
                error_count_after=error_count,
                dependency_contexts={},
                message="Failed to analyze errors"
            )

        # 4. Generate fixes for analyzed errors
        fix_proposals = self._generate_fixes_for_errors(
            analyzed_errors, dependency_contexts, source_code, test_code
        )

        if not fix_proposals:
            logger.warning("No fix proposals were generated")
            return HealingResult(
                success=False,
                fixed_code=test_code,
                analyzed_errors=analyzed_errors,
                dependency_contexts=dependency_contexts,
                error_count_before=error_count,
                error_count_after=error_count,
                message="Failed to generate fixes"
            )

        # 5. Consolidate fixes into a single solution
        fixed_code = self.fix_generator.consolidate_fixes(fix_proposals, test_code)

        # 6. Write the fixed code to the test file
        self.fs.write_file(test_file_path, fixed_code)

        # 7. Run the test to see if the fix worked
        test_result = self.build_system.run_test(test_file_path)

        # 8. Check if the fix was successful
        if test_result.success:
            logger.info(f"Fix was successful for {test_file_path}")
            return HealingResult(
                success=True,
                fixed_code=fixed_code,
                analyzed_errors=analyzed_errors,
                fix_proposals=fix_proposals,
                dependency_contexts=dependency_contexts,
                execution_time=time.time() - start_time,
                error_count_before=error_count,
                error_count_after=0,
                message="Fix was successful"
            )
        else:
            # Parse errors from the new output
            new_errors = self.error_parser.parse_output(test_result.output)
            logger.warning(f"Fix was partially successful. Reduced errors from {error_count} to {len(new_errors)}")

            return HealingResult(
                success=False,
                fixed_code=fixed_code,
                analyzed_errors=analyzed_errors,
                fix_proposals=fix_proposals,
                dependency_contexts=dependency_contexts,
                execution_time=time.time() - start_time,
                error_count_before=error_count,
                error_count_after=len(new_errors),
                message=f"Fix was partially successful. Reduced errors from {error_count} to {len(new_errors)}"
            )

    def _process_errors_in_parallel(self,
                                  errors: List[ParsedError],
                                  source_file_path: str,
                                  source_code: str,
                                  test_code: str) -> Tuple[List[AnalyzedError], Dict[str, DependencyContext]]:
        """
        Processes errors in parallel.

        Args:
            errors: List of parsed errors
            source_file_path: Path to the source file
            source_code: Content of the source file
            test_code: Content of the test file

        Returns:
            Tuple of (analyzed_errors, dependency_contexts)
        """
        analyzed_errors = []
        dependency_contexts = {}

        def process_error(error: ParsedError) -> Tuple[Optional[AnalyzedError], Optional[DependencyContext]]:
            """Processes a single error."""
            try:
                # 1. Resolve dependencies for the error
                dependency_context = self.dependency_resolver.resolve_dependencies(
                    error, source_file_path, test_file_path
                )

                # 2. Analyze the error with the dependency context
                analyzed_error = self.error_analyzer.analyze_error(
                    error, source_code, test_code, dependency_context
                )

                return analyzed_error, dependency_context

            except Exception as e:
                logger.error(f"Error processing error {id(error)}: {e}", exc_info=True)
                return None, None

        # Process errors in parallel using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_parallel_agents) as executor:
            # Submit all tasks
            future_to_error = {executor.submit(process_error, error): error for error in errors}

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_error):
                error = future_to_error[future]
                try:
                    analyzed_error, dependency_context = future.result()
                    if analyzed_error and dependency_context:
                        analyzed_errors.append(analyzed_error)
                        dependency_contexts[analyzed_error.error_id] = dependency_context
                except Exception as e:
                    logger.error(f"Error processing result for {error.error_type}: {e}", exc_info=True)

        return analyzed_errors, dependency_contexts

    def _generate_fixes_for_errors(self,
                                 analyzed_errors: List[AnalyzedError],
                                 dependency_contexts: Dict[str, DependencyContext],
                                 source_code: str,
                                 test_code: str) -> List[FixProposal]:
        """
        Generates fixes for analyzed errors.

        Args:
            analyzed_errors: List of analyzed errors
            dependency_contexts: Dictionary mapping error IDs to dependency contexts
            source_code: Content of the source file
            test_code: Content of the test file

        Returns:
            List of fix proposals
        """
        fix_proposals = []

        def generate_fix(analyzed_error: AnalyzedError) -> Optional[FixProposal]:
            """Generates a fix for a single analyzed error."""
            try:
                # Get the dependency context for this error
                dependency_context = dependency_contexts.get(analyzed_error.error_id)
                if not dependency_context:
                    logger.warning(f"No dependency context found for error {analyzed_error.error_id}")
                    dependency_context = DependencyContext()

                # Generate a fix
                fix_proposal = self.fix_generator.generate_fix(
                    analyzed_error, source_code, test_code, dependency_context
                )

                return fix_proposal

            except Exception as e:
                logger.error(f"Error generating fix for error {analyzed_error.error_id}: {e}", exc_info=True)
                return None

        # Generate fixes in parallel using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_parallel_agents) as executor:
            # Submit all tasks
            future_to_error = {executor.submit(generate_fix, error): error for error in analyzed_errors}

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_error):
                error = future_to_error[future]
                try:
                    fix_proposal = future.result()
                    if fix_proposal:
                        fix_proposals.append(fix_proposal)
                except Exception as e:
                    logger.error(f"Error processing fix result for {error.error_id}: {e}", exc_info=True)

        return fix_proposals
