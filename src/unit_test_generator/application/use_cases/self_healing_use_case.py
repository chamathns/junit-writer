"""
Self-healing use case for fixing test errors.
"""
import logging
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.build_system import BuildSystemPort
from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.code_parser import CodeParserPort
from unit_test_generator.application.services.error_analysis_service import ErrorAnalysisService
from unit_test_generator.application.services.fix_generation_service import FixGenerationService
from unit_test_generator.domain.models.error_analysis import AnalyzedError, DependencyContext

logger = logging.getLogger(__name__)

class SelfHealingUseCase:
    """
    Use case for self-healing test errors.
    """

    def __init__(self,
                file_system: FileSystemPort,
                build_system: BuildSystemPort,
                error_parser: ErrorParserPort,
                llm_service: LLMServicePort,
                code_parser: CodeParserPort,
                config: Dict[str, Any]):
        """
        Initializes the use case.

        Args:
            file_system: File system port for reading and writing files.
            build_system: Build system port for compiling and running tests.
            error_parser: Error parser port for parsing build output.
            llm_service: LLM service port for generating fixes.
            code_parser: Code parser port for parsing code.
            config: Application configuration.
        """
        self.file_system = file_system
        self.build_system = build_system
        self.error_parser = error_parser
        self.llm_service = llm_service
        self.code_parser = code_parser
        self.config = config
        
        # Initialize services
        self.error_analysis_service = ErrorAnalysisService(
            llm_service=llm_service,
            dependency_resolver=None,  # This would need to be injected
            config=config
        )
        self.fix_generation_service = FixGenerationService(
            llm_service=llm_service,
            config=config
        )
        
        logger.info("SelfHealingUseCase initialized.")

    def execute(self,
               source_file_path: str,
               test_file_path: str,
               max_attempts: int = 3) -> Dict[str, Any]:
        """
        Executes the self-healing process.

        Args:
            source_file_path: Path to the source file being tested.
            test_file_path: Path to the test file that needs healing.
            max_attempts: Maximum number of healing attempts.

        Returns:
            Dictionary with the result of the healing process.
        """
        logger.info(f"Starting self-healing for test file: {test_file_path}")
        start_time = time.time()
        
        # Read the source and test files
        source_code = self.file_system.read_file(source_file_path)
        test_code = self.file_system.read_file(test_file_path)
        
        if not source_code or not test_code:
            logger.error(f"Failed to read source or test file.")
            return {
                "success": False,
                "message": "Failed to read source or test file.",
                "attempts": 0,
                "fixed_code": None,
                "elapsed_time": time.time() - start_time
            }
        
        # Initialize healing state
        attempt = 0
        current_test_code = test_code
        last_errors = None
        success = False
        
        # Healing loop
        while attempt < max_attempts and not success:
            attempt += 1
            logger.info(f"Healing attempt {attempt}/{max_attempts}")
            
            # Write the current test code to the file
            self.file_system.write_file(test_file_path, current_test_code)
            
            # Compile and run the test
            build_result = self.build_system.compile_test(test_file_path)
            
            # Check if the build was successful
            if build_result.status == "success":
                logger.info(f"Test compiled successfully on attempt {attempt}.")
                
                # Run the test to see if it passes
                run_result = self.build_system.run_test(test_file_path)
                
                if run_result.status == "success":
                    logger.info(f"Test passed successfully on attempt {attempt}.")
                    success = True
                    break
                else:
                    logger.info(f"Test compiled but failed execution on attempt {attempt}.")
                    # Parse the test execution errors
                    last_errors = self.error_parser.parse_output(run_result.output)
            else:
                logger.info(f"Test failed to compile on attempt {attempt}.")
                # Parse the compilation errors
                last_errors = self.error_parser.parse_output(build_result.output)
            
            # If no errors were found, but the build/run failed, create a generic error
            if not last_errors:
                logger.warning(f"No specific errors found on attempt {attempt}, but build/run failed.")
                last_errors = [ParsedError(
                    message="Build or test execution failed but no specific errors were identified.",
                    error_type="Unknown",
                    involved_symbols=[],
                    error_category="Other",
                    suggested_fix="Review the build output manually to identify the issue."
                )]
            
            # Log the errors
            logger.info(f"Found {len(last_errors)} errors on attempt {attempt}.")
            for i, error in enumerate(last_errors):
                logger.info(f"Error {i+1}: {error.error_type} - {error.error_category} - {error.message}")
            
            # Analyze the errors
            analyzed_errors = []
            for error in last_errors:
                # Create a minimal dependency context
                dependency_context = DependencyContext(
                    primary_dependencies=[],
                    secondary_dependencies=[],
                    imported_symbols=[],
                    used_symbols=[],
                    error_related_symbols=error.involved_symbols
                )
                
                # Analyze the error
                analyzed_error = self.error_analysis_service.analyze_error(
                    error=error,
                    source_code=source_code,
                    test_code=current_test_code,
                    dependency_context=dependency_context
                )
                analyzed_errors.append(analyzed_error)
            
            # Generate fixes for the errors
            if len(analyzed_errors) == 1:
                # Generate a fix for a single error
                fix_proposal = self.fix_generation_service.generate_fix(
                    analyzed_error=analyzed_errors[0],
                    source_code=source_code,
                    test_code=current_test_code,
                    dependency_context=dependency_context
                )
                
                # Update the current test code
                if fix_proposal.fixed_code and fix_proposal.fixed_code != current_test_code:
                    current_test_code = fix_proposal.fixed_code
                    logger.info(f"Applied fix for error on attempt {attempt}.")
                else:
                    logger.warning(f"Fix generation did not change the code on attempt {attempt}.")
                    # If the fix didn't change the code, break the loop to avoid infinite loops
                    break
            else:
                # Consolidate fixes for multiple errors
                fix_proposals = []
                for analyzed_error in analyzed_errors:
                    fix_proposal = self.fix_generation_service.generate_fix(
                        analyzed_error=analyzed_error,
                        source_code=source_code,
                        test_code=current_test_code,
                        dependency_context=dependency_context
                    )
                    fix_proposals.append(fix_proposal)
                
                # Consolidate the fixes
                consolidated_code = self.fix_generation_service.consolidate_fixes(
                    fix_proposals=fix_proposals,
                    current_test_code=current_test_code
                )
                
                # Update the current test code
                if consolidated_code and consolidated_code != current_test_code:
                    current_test_code = consolidated_code
                    logger.info(f"Applied consolidated fix for {len(analyzed_errors)} errors on attempt {attempt}.")
                else:
                    logger.warning(f"Consolidated fix did not change the code on attempt {attempt}.")
                    # If the fix didn't change the code, break the loop to avoid infinite loops
                    break
        
        # Write the final test code to the file
        self.file_system.write_file(test_file_path, current_test_code)
        
        # Return the result
        elapsed_time = time.time() - start_time
        logger.info(f"Self-healing completed in {elapsed_time:.2f}s with success={success}, attempts={attempt}")
        
        return {
            "success": success,
            "message": "Test healed successfully." if success else "Failed to heal test after maximum attempts.",
            "attempts": attempt,
            "fixed_code": current_test_code,
            "elapsed_time": elapsed_time
        }
