"""
Self-healing use case for fixing compilation errors in generated tests.
"""
import logging
from typing import Dict, Any, Optional, List

from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.build_system import BuildSystemPort
from unit_test_generator.domain.ports.error_parser import ErrorParserPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.code_parser import CodeParserPort

logger = logging.getLogger(__name__)


class SelfHealingUseCase:
    """
    Use case for fixing compilation errors in generated tests.
    """

    def __init__(
        self,
        file_system: FileSystemPort,
        build_system: BuildSystemPort,
        error_parser: ErrorParserPort,
        llm_service: LLMServicePort,
        code_parser: CodeParserPort,
        config: Dict[str, Any] = None
    ):
        """
        Initialize the self-healing use case.

        Args:
            file_system: File system port
            build_system: Build system port
            error_parser: Error parser port
            llm_service: LLM service port
            code_parser: Code parser port
            config: Configuration dictionary
        """
        self.file_system = file_system
        self.build_system = build_system
        self.error_parser = error_parser
        self.llm_service = llm_service
        self.code_parser = code_parser
        self.config = config or {}
        self.max_attempts = self.config.get("self_healing", {}).get("max_attempts", 3)
        self.use_intelligent_fix = self.config.get("self_healing", {}).get("use_intelligent_fix", True)

    def execute(self, test_file_path: str) -> Dict[str, Any]:
        """
        Execute the self-healing use case.

        Args:
            test_file_path: Path to the test file to fix

        Returns:
            Result of the self-healing process
        """
        logger.info(f"Starting self-healing for test file: {test_file_path}")
        
        # Check if the file exists
        if not self.file_system.exists(test_file_path):
            logger.error(f"Test file not found: {test_file_path}")
            return {
                "status": "error",
                "message": f"Test file not found: {test_file_path}"
            }
        
        # Read the initial test code
        initial_test_code = self.file_system.read_file(test_file_path)
        current_test_code = initial_test_code
        
        # Try to compile the test file
        compile_result = self.build_system.compile_test(test_file_path)
        
        # If compilation succeeds, no need to fix
        if compile_result.success:
            logger.info(f"Test file already compiles successfully: {test_file_path}")
            return {
                "status": "success",
                "message": "Test file already compiles successfully"
            }
        
        # Try to fix the compilation errors
        for attempt in range(1, self.max_attempts + 1):
            logger.info(f"Self-healing attempt {attempt}/{self.max_attempts} for {test_file_path}")
            
            # Parse the compilation errors
            errors = self.error_parser.parse_errors(compile_result.error_output)
            
            if not errors:
                logger.warning(f"No errors could be parsed from compilation output")
                break
            
            logger.info(f"Found {len(errors)} errors to fix")
            
            # Generate fixes for the errors
            if self.use_intelligent_fix:
                fixed_code = self._apply_intelligent_fix(current_test_code, errors)
            else:
                fixed_code = self._apply_simple_fix(current_test_code, errors)
            
            # If no changes were made, break
            if fixed_code == current_test_code:
                logger.warning(f"No changes made in attempt {attempt}, stopping")
                break
            
            # Update the test file with the fixed code
            self.file_system.write_file(test_file_path, fixed_code)
            current_test_code = fixed_code
            
            # Try to compile again
            compile_result = self.build_system.compile_test(test_file_path)
            
            # If compilation succeeds, we're done
            if compile_result.success:
                logger.info(f"Self-healing successful after {attempt} attempts")
                return {
                    "status": "success",
                    "message": f"Fixed compilation errors after {attempt} attempts"
                }
        
        # If we get here, we couldn't fix all errors
        logger.warning(f"Could not fix all compilation errors after {self.max_attempts} attempts")
        return {
            "status": "partial_success" if current_test_code != initial_test_code else "failure",
            "message": f"Could not fix all compilation errors after {self.max_attempts} attempts"
        }
    
    def _apply_intelligent_fix(self, test_code: str, errors: List[Dict[str, Any]]) -> str:
        """
        Apply intelligent fixes to the test code based on the errors.
        
        Args:
            test_code: The current test code
            errors: List of parsed errors
            
        Returns:
            Fixed test code
        """
        # This would use the LLM to generate fixes
        context = {
            "test_code": test_code,
            "errors": errors,
            "task": "fix_compilation_errors"
        }
        
        try:
            fixed_code = self.llm_service.generate_fixes(context)
            return fixed_code
        except Exception as e:
            logger.error(f"Error generating intelligent fixes: {e}")
            return self._apply_simple_fix(test_code, errors)
    
    def _apply_simple_fix(self, test_code: str, errors: List[Dict[str, Any]]) -> str:
        """
        Apply simple fixes to the test code based on the errors.
        
        Args:
            test_code: The current test code
            errors: List of parsed errors
            
        Returns:
            Fixed test code
        """
        # Simple rule-based fixes
        fixed_code = test_code
        
        for error in errors:
            error_type = error.get("type")
            line_number = error.get("line_number")
            
            if error_type == "missing_import" and "class" in error:
                # Add import statement
                import_statement = f"import {error['class']}\n"
                fixed_code = import_statement + fixed_code
            
            # Add more simple fixes as needed
        
        return fixed_code
