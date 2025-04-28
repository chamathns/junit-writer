# src/unit_test_generator/domain/ports/error_analysis.py
"""
Ports for error analysis and self-healing.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from unit_test_generator.domain.models.error_analysis import (
    AnalyzedError, DependencyContext, DependencyFile, FixProposal, HealingResult
)
from unit_test_generator.domain.ports.error_parser import ParsedError

class ErrorAnalysisPort(ABC):
    """Interface for analyzing errors."""

    @abstractmethod
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
        pass

class DependencyResolutionPort(ABC):
    """Interface for resolving dependencies for errors."""

    @abstractmethod
    def resolve_dependencies(self,
                           error: ParsedError,
                           source_file_path: str,
                           test_file_path: str) -> DependencyContext:
        """
        Resolves dependencies relevant to an error.

        Args:
            error: The parsed error
            source_file_path: Path to the source file
            test_file_path: Path to the test file

        Returns:
            Context of dependencies for the error
        """
        pass

    @abstractmethod
    def load_dependency_content(self, dependency_paths: List[str]) -> List[DependencyFile]:
        """
        Loads the content of dependency files.

        Args:
            dependency_paths: Paths to dependency files

        Returns:
            List of DependencyFile objects with content loaded
        """
        pass

    @abstractmethod
    def find_related_test_files(self, source_file_path: str) -> List[str]:
        """
        Finds test files related to a source file.

        Args:
            source_file_path: Path to the source file

        Returns:
            List of paths to related test files
        """
        pass

    @abstractmethod
    def extract_symbols_from_file(self, file_path: str, file_content: str) -> List[str]:
        """
        Extracts symbols (classes, methods, etc.) from a file.

        Args:
            file_path: Path to the file
            file_content: Content of the file

        Returns:
            List of symbols found in the file
        """
        pass

class FixGenerationPort(ABC):
    """Interface for generating fixes for errors."""

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

class HealingOrchestratorPort(ABC):
    """Interface for orchestrating the healing process."""

    @abstractmethod
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
        pass
