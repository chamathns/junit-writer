from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional, Dict, Any, List

class BuildStatus(Enum):
    """Status codes for build operations."""
    SUCCESS = "success"
    COMPILATION_ERROR = "compilation_error"
    RUNTIME_ERROR = "runtime_error"
    CONFIGURATION_ERROR = "configuration_error"
    ENVIRONMENT_ERROR = "environment_error"
    UNKNOWN_ERROR = "unknown_error"
    RUNNING = "running"  # For asynchronous/terminal execution

@dataclass
class TestRunResult:
    """Result of attempting to run a test."""
    success: bool
    status: BuildStatus
    output: str  # Combined stdout/stderr from the build tool
    error_details: Optional[Dict[str, Any]] = None  # Structured error information if available
    execution_time: Optional[float] = None  # Time taken to execute in seconds
    terminal_id: Optional[int] = None  # ID of the terminal if running in a separate terminal
    output_file: Optional[str] = None  # Path to the output file if running in a separate terminal

class BuildSystemPort(ABC):
    """Interface for interacting with the project's build system."""

    @abstractmethod
    def verify_environment(self) -> Tuple[bool, str]:
        """
        Verifies that the build environment is properly configured.

        Returns:
            Tuple of (success, message) indicating if the environment is valid
            and providing details about any issues.
        """
        pass

    @abstractmethod
    def compile_test(self, test_file_abs_path: str) -> TestRunResult:
        """
        Compiles a specific test file without running it.

        Args:
            test_file_abs_path: The absolute path to the test file to compile.

        Returns:
            TestRunResult indicating compilation success and capturing output.
        """
        pass

    @abstractmethod
    def run_test(self, test_file_abs_path: str) -> TestRunResult:
        """
        Compiles and runs a specific test file within the target project.

        Args:
            test_file_abs_path: The absolute path to the test file to run.

        Returns:
            TestRunResult indicating success and capturing output.
        """
        pass

    @abstractmethod
    def get_build_info(self) -> Dict[str, Any]:
        """
        Returns information about the build system configuration.

        Returns:
            Dictionary containing build system details like version, configuration, etc.
        """
        pass

    @abstractmethod
    def run_test_in_terminal(self, test_file_abs_path: str, title: str = None) -> TestRunResult:
        """
        Runs a test in a separate terminal window.

        Args:
            test_file_abs_path: The absolute path to the test file to run.
            title: Optional title for the terminal window.

        Returns:
            TestRunResult with terminal_id and output_file set.
            The status will be BuildStatus.RUNNING if the terminal was launched successfully.
        """
        pass

    @abstractmethod
    def get_terminal_output(self, terminal_id: int) -> str:
        """
        Gets the output from a terminal process.

        Args:
            terminal_id: The ID of the terminal process.

        Returns:
            The output from the terminal process.
        """
        pass

    @abstractmethod
    def kill_terminal_process(self, terminal_id: int) -> bool:
        """
        Kills a terminal process.

        Args:
            terminal_id: The ID of the terminal process.

        Returns:
            True if the process was killed, False otherwise.
        """
        pass

    @abstractmethod
    def list_terminal_processes(self) -> List[Dict[str, Any]]:
        """
        Lists all terminal processes.

        Returns:
            A list of dictionaries containing information about terminal processes.
        """
        pass