# src/unit_test_generator/application/services/fix_generation_service.py
"""
Service for generating fixes for errors.
"""
import logging
import time
import difflib
from typing import List, Dict, Any, Optional

from unit_test_generator.domain.ports.error_analysis import FixGenerationPort
from unit_test_generator.domain.models.error_analysis import (
    AnalyzedError, DependencyContext, FixProposal
)
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.application.utils.code_block_parser import parse_llm_code_block

logger = logging.getLogger(__name__)

class FixGenerationService(FixGenerationPort):
    """Service for generating fixes for errors."""

    def __init__(self,
                llm_service: LLMServicePort,
                config: Dict[str, Any]):
        """
        Initialize the service.

        Args:
            llm_service: LLM service for fix generation
            config: Application configuration
        """
        self.llm_service = llm_service
        self.config = config

    def generate_fix(self,
                    analyzed_error: AnalyzedError,
                    source_code: str,
                    test_code: str,
                    dependency_context: DependencyContext) -> FixProposal:
        """
        Generates a fix for an analyzed error.

        Args:
            analyzed_error: The analyzed error
            source_code: The source code being tested
            test_code: The test code that produced the error
            dependency_context: Context of dependencies

        Returns:
            A proposed fix for the error
        """
        error_id = analyzed_error.error_id
        logger.info(f"Generating fix for error {error_id}")

        start_time = time.time()

        # Prepare dependency content
        dependency_content = {}
        for dep in dependency_context.primary_dependencies:
            path = dep["path"]
            dependency_content[path] = {
                "path": path,
                "relevance": dep["relevance"],
                "content": self._load_dependency_content(path)
            }

        # Prepare context for LLM fix generation
        fix_context = {
            "task": "generate_fix",
            "analyzed_error": {
                "error_id": analyzed_error.error_id,
                "message": analyzed_error.message,
                "category": analyzed_error.category.value,
                "severity": analyzed_error.severity.value,
                "context": {
                    "file_path": analyzed_error.context.file_path,
                    "line_number": analyzed_error.context.line_number,
                    "code_snippet": analyzed_error.context.code_snippet,
                    "related_symbols": analyzed_error.context.related_symbols
                },
                "root_cause": analyzed_error.root_cause,
                "suggested_fixes": analyzed_error.suggested_fixes
            },
            "source_code": source_code,
            "test_code": test_code,
            "dependencies": dependency_content,
            "language": self.config.get('generation', {}).get('target_language', 'Kotlin'),
            "framework": self.config.get('generation', {}).get('target_framework', 'JUnit5 with MockK')
        }

        # Call LLM for fix generation
        try:
            fix_response = self.llm_service.generate_tests(fix_context)

            # Parse the response to extract the fixed code
            fixed_code = parse_llm_code_block(
                fix_response,
                self.config.get('generation', {}).get('target_language', 'Kotlin')
            )

            if not fixed_code:
                logger.warning(f"Failed to extract fixed code for error {error_id}")
                return FixProposal(
                    error_id=error_id,
                    original_code=test_code,
                    fixed_code=test_code,
                    explanation="Failed to extract fixed code from LLM response",
                    confidence=0.0
                )

            # Extract explanation from response
            explanation = self._extract_explanation(fix_response)

            # Calculate affected lines
            affected_lines = self._calculate_affected_lines(test_code, fixed_code)

            # Create fix proposal
            fix_proposal = FixProposal(
                error_id=error_id,
                original_code=test_code,
                fixed_code=fixed_code,
                explanation=explanation,
                confidence=0.7,  # Default confidence
                affected_lines=affected_lines,
                dependencies_added=self._extract_dependencies_added(fix_response),
                dependencies_removed=[]
            )

            logger.info(f"Generated fix for error {error_id} in {time.time() - start_time:.2f}s")
            return fix_proposal

        except Exception as e:
            logger.error(f"Error generating fix for error {error_id}: {e}", exc_info=True)

            # Return a basic fix proposal if generation fails
            return FixProposal(
                error_id=error_id,
                original_code=test_code,
                fixed_code=test_code,
                explanation=f"Fix generation failed: {str(e)}",
                confidence=0.0
            )

    def consolidate_fixes(self,
                         fix_proposals: List[FixProposal],
                         current_test_code: str) -> str:
        """
        Consolidates multiple fix proposals into a single fixed code.

        Args:
            fix_proposals: List of fix proposals
            current_test_code: Current test code

        Returns:
            Consolidated fixed code
        """
        if not fix_proposals:
            return current_test_code

        logger.info(f"Consolidating {len(fix_proposals)} fix proposals")

        # Sort fix proposals by confidence
        sorted_proposals = sorted(fix_proposals, key=lambda p: p.confidence, reverse=True)

        # If there's only one proposal, return its fixed code
        if len(sorted_proposals) == 1:
            return sorted_proposals[0].fixed_code

        # Prepare context for LLM consolidation
        consolidation_context = {
            "task": "consolidate_fixes",
            "current_test_code": current_test_code,
            "fix_proposals": [
                {
                    "error_id": p.error_id,
                    "fixed_code": p.fixed_code,
                    "explanation": p.explanation,
                    "confidence": p.confidence,
                    "affected_lines": p.affected_lines
                }
                for p in sorted_proposals
            ],
            "language": self.config.get('generation', {}).get('target_language', 'Kotlin'),
            "framework": self.config.get('generation', {}).get('target_framework', 'JUnit5 with MockK')
        }

        # Call LLM for consolidation
        try:
            consolidation_response = self.llm_service.generate_tests(consolidation_context)

            # Parse the response to extract the consolidated code
            consolidated_code = parse_llm_code_block(
                consolidation_response,
                self.config.get('generation', {}).get('target_language', 'Kotlin')
            )

            if not consolidated_code:
                logger.warning("Failed to extract consolidated code")
                # Fall back to the highest confidence fix
                return sorted_proposals[0].fixed_code

            logger.info("Successfully consolidated fix proposals")
            return consolidated_code

        except Exception as e:
            logger.error(f"Error consolidating fixes: {e}", exc_info=True)

            # Fall back to the highest confidence fix
            return sorted_proposals[0].fixed_code

    def _load_dependency_content(self, path: str) -> str:
        """Loads the content of a dependency file."""
        try:
            # This would need to be implemented with a file system adapter
            # For now, return a placeholder
            return f"// Content of {path} would be loaded here"
        except Exception as e:
            logger.error(f"Error loading content for {path}: {e}")
            return f"// Error loading content: {str(e)}"

    def _extract_explanation(self, response: str) -> str:
        """Extracts explanation from LLM response."""
        if "EXPLANATION:" in response:
            parts = response.split("EXPLANATION:")
            if len(parts) > 1:
                explanation_section = parts[1].split("\n\n")[0].strip()
                return explanation_section

        # If no explanation section, return a generic message
        return "Fix generated based on error analysis"

    def _calculate_affected_lines(self, original_code: str, fixed_code: str) -> List[int]:
        """Calculates which lines were affected by the fix."""
        affected_lines = []

        # Split the code into lines
        original_lines = original_code.splitlines()
        fixed_lines = fixed_code.splitlines()

        # Use difflib to find differences
        diff = difflib.unified_diff(original_lines, fixed_lines, n=0)

        # Skip the first two lines (header)
        next(diff, None)
        next(diff, None)

        # Parse the diff to find affected line numbers
        for line in diff:
            if line.startswith('@@'):
                # Parse the line numbers from the @@ line
                # Format: @@ -start,count +start,count @@
                parts = line.split()
                if len(parts) >= 2:
                    line_info = parts[1]
                    if line_info.startswith('-'):
                        line_range = line_info[1:].split(',')[0]
                        try:
                            start_line = int(line_range)
                            affected_lines.append(start_line)
                        except ValueError:
                            pass

        return affected_lines

    def _extract_dependencies_added(self, response: str) -> List[str]:
        """Extracts dependencies added from LLM response."""
        if "DEPENDENCIES ADDED:" in response:
            parts = response.split("DEPENDENCIES ADDED:")
            if len(parts) > 1:
                deps_section = parts[1].split("\n\n")[0].strip()
                return [dep.strip() for dep in deps_section.split("\n- ") if dep.strip()]

        # If no dependencies section, check for import statements in the response
        import re
        import_pattern = re.compile(r'import\s+([\w.]+)(?:\s+as\s+[\w]+)?')
        matches = import_pattern.findall(response)

        return list(set(matches))  # Remove duplicates
