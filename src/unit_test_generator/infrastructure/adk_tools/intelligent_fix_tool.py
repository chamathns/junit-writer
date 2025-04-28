# src/unit_test_generator/infrastructure/adk_tools/intelligent_fix_tool.py
"""
ADK Tool for intelligent test fixing.
"""
import logging
from typing import Dict, Any

from unit_test_generator.domain.ports.error_analysis import HealingOrchestratorPort
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class IntelligentFixTool(JUnitWriterTool):
    """Tool for intelligent test fixing using parallel error analysis."""

    def __init__(self, healing_orchestrator: HealingOrchestratorPort, config: Dict[str, Any]):
        """
        Initialize the IntelligentFixTool.

        Args:
            healing_orchestrator: An implementation of HealingOrchestratorPort
            config: Application configuration
        """
        super().__init__(
            name="intelligent_fix",
            description="Intelligently fixes failing tests using parallel error analysis and dependency resolution."
        )
        self.healing_orchestrator = healing_orchestrator
        self.config = config

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to generate an intelligent fix.

        Args:
            parameters: Dictionary containing:
                - target_file_path: Path to the source file being tested
                - target_file_content: Content of the source file
                - test_file_path: Path to the test file
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
        test_file_path = parameters.get("test_file_path")
        current_test_code = parameters.get("current_test_code")
        error_output = parameters.get("error_output")

        # Check required parameters
        if not all([target_file_path, target_file_content, test_file_path, current_test_code, error_output]):
            missing = []
            if not target_file_path: missing.append("target_file_path")
            if not target_file_content: missing.append("target_file_content")
            if not test_file_path: missing.append("test_file_path")
            if not current_test_code: missing.append("current_test_code")
            if not error_output: missing.append("error_output")
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")

        # Extract optional parameters or use defaults from config
        language = parameters.get("language", self.config.get('generation', {}).get('target_language', 'Kotlin'))
        framework = parameters.get("framework", self.config.get('generation', {}).get('target_framework', 'JUnit5 with MockK'))

        try:
            # Call the healing orchestrator to fix the test
            healing_result = self.healing_orchestrator.heal(
                source_file_path=target_file_path,
                source_code=target_file_content,
                test_file_path=test_file_path,
                test_code=current_test_code,
                error_output=error_output
            )

            # Prepare the response
            if healing_result.success:
                logger.info("Successfully fixed the test")
                return {
                    "fixed_code": healing_result.fixed_code,
                    "success": True,
                    "analysis": {
                        "errors": [
                            {
                                "error_id": error.error_id,
                                "message": error.message,
                                "category": error.category.value,
                                "severity": error.severity.value,
                                "root_cause": error.root_cause,
                                "suggested_fixes": error.suggested_fixes,
                                "dependencies": error.dependencies,
                                "confidence": error.confidence,
                                "context": {
                                    "file_path": error.context.file_path,
                                    "line_number": error.context.line_number,
                                    "related_symbols": error.context.related_symbols
                                }
                            }
                            for error in healing_result.analyzed_errors
                        ],
                        "fixes": [
                            {
                                "error_id": fix.error_id,
                                "explanation": fix.explanation,
                                "confidence": fix.confidence,
                                "affected_lines": fix.affected_lines,
                                "dependencies_added": fix.dependencies_added,
                                "dependencies_removed": fix.dependencies_removed
                            }
                            for fix in healing_result.fix_proposals
                        ],
                        "dependencies": {
                            "count": sum(len(dep_context.primary_dependencies) + len(dep_context.secondary_dependencies)
                                      for dep_context in healing_result.dependency_contexts.values()),
                            "primary_count": sum(len(dep_context.primary_dependencies)
                                             for dep_context in healing_result.dependency_contexts.values()),
                            "secondary_count": sum(len(dep_context.secondary_dependencies)
                                               for dep_context in healing_result.dependency_contexts.values()),
                            "paths": list(set([dep.path
                                           for dep_context in healing_result.dependency_contexts.values()
                                           for dep in dep_context.primary_dependencies]))
                        },
                        "execution_time": healing_result.execution_time,
                        "error_count_before": healing_result.error_count_before,
                        "error_count_after": healing_result.error_count_after,
                        "message": healing_result.message
                    }
                }
            else:
                logger.warning(f"Failed to fix the test: {healing_result.message}")
                return {
                    "fixed_code": healing_result.fixed_code,
                    "success": False,
                    "message": healing_result.message,
                    "analysis": {
                        "errors": [
                            {
                                "error_id": error.error_id,
                                "message": error.message,
                                "category": error.category.value,
                                "severity": error.severity.value,
                                "root_cause": error.root_cause,
                                "suggested_fixes": error.suggested_fixes
                            }
                            for error in healing_result.analyzed_errors
                        ],
                        "fixes": [
                            {
                                "error_id": fix.error_id,
                                "explanation": fix.explanation,
                                "confidence": fix.confidence,
                                "affected_lines": fix.affected_lines
                            }
                            for fix in healing_result.fix_proposals
                        ],
                        "execution_time": healing_result.execution_time,
                        "error_count_before": healing_result.error_count_before,
                        "error_count_after": healing_result.error_count_after
                    }
                }

        except Exception as e:
            logger.error(f"Error during intelligent fix generation: {e}", exc_info=True)
            return {
                "fixed_code": None,
                "success": False,
                "message": f"Error during intelligent fix generation: {str(e)}",
                "analysis": {"error": str(e)}
            }
