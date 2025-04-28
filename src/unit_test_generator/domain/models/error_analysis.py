# src/unit_test_generator/domain/models/error_analysis.py
"""
Domain models for error analysis and self-healing.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional

class ErrorSeverity(Enum):
    """Severity levels for errors."""
    CRITICAL = "critical"  # Prevents compilation or execution
    HIGH = "high"          # Causes test failures
    MEDIUM = "medium"      # Affects functionality but tests still run
    LOW = "low"            # Minor issues (style, warnings)

class ErrorCategory(Enum):
    """Categories of errors."""
    COMPILATION = "compilation"  # Syntax or compilation errors
    TYPE = "type"                # Type mismatches
    DEPENDENCY = "dependency"    # Missing or incorrect dependencies
    MOCK = "mock"                # Issues with mocking
    ASSERTION = "assertion"      # Failed assertions
    RUNTIME = "runtime"          # Runtime exceptions
    CONFIGURATION = "configuration"  # Build or environment configuration issues
    UNKNOWN = "unknown"          # Unclassified errors

@dataclass
class ErrorContext:
    """Context information for an error."""
    file_path: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    code_snippet: Optional[str] = None
    stack_trace: Optional[str] = None
    related_symbols: List[str] = field(default_factory=list)

@dataclass
class AnalyzedError:
    """An error that has been analyzed."""
    error_id: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    context: ErrorContext
    root_cause: Optional[str] = None
    suggested_fixes: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    analysis_notes: Optional[str] = None
    confidence: float = 0.0  # 0.0 to 1.0

@dataclass
class DependencyFile:
    """Represents a dependency file with its content and metadata."""
    path: str
    content: str
    relevance_score: float = 1.0
    is_test_file: bool = False
    symbols: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)

@dataclass
class DependencyContext:
    """Context of dependencies for an error."""
    primary_dependencies: List[DependencyFile] = field(default_factory=list)
    secondary_dependencies: List[DependencyFile] = field(default_factory=list)
    imported_symbols: List[str] = field(default_factory=list)
    used_symbols: List[str] = field(default_factory=list)
    error_related_symbols: List[str] = field(default_factory=list)

@dataclass
class FixProposal:
    """A proposed fix for an error."""
    error_id: str
    original_code: str
    fixed_code: str
    explanation: str
    confidence: float = 0.0  # 0.0 to 1.0
    affected_lines: List[int] = field(default_factory=list)
    dependencies_added: List[str] = field(default_factory=list)
    dependencies_removed: List[str] = field(default_factory=list)

@dataclass
class HealingResult:
    """Result of a healing cycle."""
    success: bool
    fixed_code: Optional[str] = None
    analyzed_errors: List[AnalyzedError] = field(default_factory=list)
    fix_proposals: List[FixProposal] = field(default_factory=list)
    dependency_contexts: Dict[str, DependencyContext] = field(default_factory=dict)  # error_id -> DependencyContext
    execution_time: float = 0.0
    error_count_before: int = 0
    error_count_after: int = 0
    message: Optional[str] = None
