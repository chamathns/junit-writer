# src/unit_test_generator/application/services/error_analysis_service.py
"""
Service for analyzing errors in detail.
"""
import logging
import time
from typing import List, Dict, Any, Optional

from unit_test_generator.domain.ports.error_parser import ParsedError
from unit_test_generator.domain.ports.error_analysis import (
    ErrorAnalysisPort, DependencyResolutionPort
)
from unit_test_generator.domain.models.error_analysis import (
    AnalyzedError, DependencyContext, ErrorCategory, ErrorSeverity, ErrorContext
)
from unit_test_generator.domain.ports.llm_service import LLMServicePort

logger = logging.getLogger(__name__)

class ErrorAnalysisService(ErrorAnalysisPort):
    """Service for analyzing errors in detail."""

    def __init__(self,
                llm_service: LLMServicePort,
                dependency_resolver: DependencyResolutionPort,
                config: Dict[str, Any]):
        """
        Initialize the service.

        Args:
            llm_service: LLM service for analysis
            dependency_resolver: Service for resolving dependencies
            config: Application configuration
        """
        self.llm_service = llm_service
        self.dependency_resolver = dependency_resolver
        self.config = config

    def analyze_error(self,
                     error: ParsedError,
                     source_code: str,
                     test_code: str,
                     dependency_context: DependencyContext) -> AnalyzedError:
        """
        Analyzes a specific error in detail.

        Args:
            error: The parsed error to analyze
            source_code: The source code being tested
            test_code: The test code that produced the error
            dependency_context: Context of dependencies for the error

        Returns:
            An analyzed error with detailed information
        """
        error_id = str(id(error))
        logger.info(f"Analyzing error {error_id}: {error.error_type}")

        start_time = time.time()

        # Create error context
        context = ErrorContext(
            file_path=error.file_path or "",
            line_number=error.line_number,
            code_snippet=self._extract_code_snippet(test_code, error.line_number),
            related_symbols=error.involved_symbols
        )

        # Map error type to category and severity
        category = self._map_error_type_to_category(error.error_type)
        severity = self._determine_severity(error, category)

        # Prepare dependency information for LLM analysis
        primary_deps = []
        for dep in dependency_context.primary_dependencies:
            primary_deps.append({
                "path": dep.path,
                "content": dep.content,
                "relevance": dep.relevance_score,
                "is_test_file": dep.is_test_file,
                "symbols": dep.symbols,
                "imports": dep.imports
            })

        secondary_deps = []
        for dep in dependency_context.secondary_dependencies:
            # For secondary dependencies, only include high relevance ones to avoid context bloat
            if dep.relevance_score >= 0.5:
                secondary_deps.append({
                    "path": dep.path,
                    "content": dep.content,
                    "relevance": dep.relevance_score,
                    "is_test_file": dep.is_test_file,
                    "symbols": dep.symbols,
                    "imports": dep.imports
                })

        # Prepare context for LLM analysis
        analysis_context = {
            "task": "analyze_error",
            "error": {
                "message": error.message,
                "type": error.error_type,
                "file_path": error.file_path,
                "line_number": error.line_number,
                "involved_symbols": list(error.involved_symbols)
            },
            "source_code": source_code,
            "test_code": test_code,
            "dependencies": {
                "primary": primary_deps,
                "secondary": secondary_deps,
                "imported_symbols": dependency_context.imported_symbols,
                "used_symbols": dependency_context.used_symbols,
                "error_related_symbols": dependency_context.error_related_symbols
            },
            "language": self.config.get('generation', {}).get('target_language', 'Kotlin'),
            "framework": self.config.get('generation', {}).get('target_framework', 'JUnit5 with MockK')
        }

        # Call LLM for detailed analysis
        try:
            analysis_response = self.llm_service.generate_tests(analysis_context)

            # Parse the response to extract structured information
            analysis_result = self._parse_analysis_response(analysis_response)

            # Create the analyzed error
            analyzed_error = AnalyzedError(
                error_id=error_id,
                message=error.message,
                category=category,
                severity=severity,
                context=context,
                root_cause=analysis_result.get("root_cause"),
                suggested_fixes=analysis_result.get("suggested_fixes", []),
                dependencies=analysis_result.get("dependencies", []),
                analysis_notes=analysis_result.get("analysis_notes"),
                confidence=analysis_result.get("confidence", 0.5)
            )

            logger.info(f"Completed analysis of error {error_id} in {time.time() - start_time:.2f}s")
            return analyzed_error

        except Exception as e:
            logger.error(f"Error analyzing error {error_id}: {e}", exc_info=True)

            # Return a basic analyzed error if analysis fails
            return AnalyzedError(
                error_id=error_id,
                message=error.message,
                category=category,
                severity=severity,
                context=context,
                root_cause=f"Analysis failed: {str(e)}",
                confidence=0.0
            )

    def _extract_code_snippet(self, code: str, line_number: Optional[int]) -> Optional[str]:
        """Extracts a code snippet around the error line."""
        if not code or not line_number:
            return None

        lines = code.splitlines()
        if line_number <= 0 or line_number > len(lines):
            return None

        # Extract a few lines before and after the error line
        context_lines = 3
        start_line = max(0, line_number - context_lines - 1)
        end_line = min(len(lines), line_number + context_lines)

        return "\n".join(lines[start_line:end_line])

    def _map_error_type_to_category(self, error_type: str) -> ErrorCategory:
        """Maps error type to error category."""
        mapping = {
            "Compilation": ErrorCategory.COMPILATION,
            "TestFailure": ErrorCategory.ASSERTION,
            "Runtime": ErrorCategory.RUNTIME,
            "BuildFailure": ErrorCategory.CONFIGURATION
        }
        return mapping.get(error_type, ErrorCategory.UNKNOWN)

    def _determine_severity(self, error: ParsedError, category: ErrorCategory) -> ErrorSeverity:
        """Determines the severity of an error."""
        if category == ErrorCategory.COMPILATION:
            return ErrorSeverity.CRITICAL
        elif category == ErrorCategory.ASSERTION:
            return ErrorSeverity.HIGH
        elif category == ErrorCategory.RUNTIME:
            return ErrorSeverity.HIGH
        elif category == ErrorCategory.CONFIGURATION:
            return ErrorSeverity.CRITICAL
        else:
            return ErrorSeverity.MEDIUM

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parses the LLM analysis response."""
        # This is a simplified implementation
        # In a real implementation, you would parse the JSON response

        # Default values
        result = {
            "root_cause": None,
            "suggested_fixes": [],
            "dependencies": [],
            "analysis_notes": None,
            "confidence": 0.5
        }

        # Simple parsing based on section headers
        if "ROOT CAUSE:" in response:
            parts = response.split("ROOT CAUSE:")
            if len(parts) > 1:
                root_cause_section = parts[1].split("\n\n")[0].strip()
                result["root_cause"] = root_cause_section

        if "SUGGESTED FIXES:" in response:
            parts = response.split("SUGGESTED FIXES:")
            if len(parts) > 1:
                fixes_section = parts[1].split("\n\n")[0].strip()
                result["suggested_fixes"] = [fix.strip() for fix in fixes_section.split("\n- ") if fix.strip()]

        if "DEPENDENCIES:" in response:
            parts = response.split("DEPENDENCIES:")
            if len(parts) > 1:
                deps_section = parts[1].split("\n\n")[0].strip()
                result["dependencies"] = [dep.strip() for dep in deps_section.split("\n- ") if dep.strip()]

        if "ANALYSIS NOTES:" in response:
            parts = response.split("ANALYSIS NOTES:")
            if len(parts) > 1:
                notes_section = parts[1].split("\n\n")[0].strip()
                result["analysis_notes"] = notes_section

        if "CONFIDENCE:" in response:
            parts = response.split("CONFIDENCE:")
            if len(parts) > 1:
                confidence_text = parts[1].split("\n")[0].strip()
                try:
                    # Try to parse confidence as a float between 0 and 1
                    confidence = float(confidence_text)
                    result["confidence"] = max(0.0, min(1.0, confidence))
                except ValueError:
                    # If parsing fails, try to map text to a value
                    confidence_mapping = {
                        "very low": 0.1,
                        "low": 0.3,
                        "medium": 0.5,
                        "high": 0.7,
                        "very high": 0.9
                    }
                    for text, value in confidence_mapping.items():
                        if text in confidence_text.lower():
                            result["confidence"] = value
                            break

        return result
