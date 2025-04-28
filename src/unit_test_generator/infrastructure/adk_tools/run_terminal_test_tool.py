# src/unit_test_generator/infrastructure/adk_tools/run_terminal_test_tool.py
"""
ADK Tool for running tests in a separate terminal window.
"""
import logging
import time
from typing import Dict, Any, Optional, List

from unit_test_generator.domain.ports.build_system import BuildSystemPort, BuildStatus
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class RunTerminalTestTool(JUnitWriterTool):
    """Tool for running tests in a separate terminal window."""

    def __init__(self, build_system: BuildSystemPort):
        """
        Initialize the RunTerminalTestTool.

        Args:
            build_system: An implementation of BuildSystemPort
        """
        super().__init__(
            name="run_terminal_test",
            description="Runs a test file in a separate terminal window and returns the result.",
            is_long_running=True  # Mark as long-running since test execution can take time
        )
        self.build_system = build_system

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to run a test in a terminal.

        Args:
            parameters: Dictionary containing:
                - test_file_abs_path: Absolute path to the test file
                - title: (Optional) Title for the terminal window
                - verify_environment: (Optional) If True, verify the build environment first

        Returns:
            Dictionary containing:
                - success: Boolean indicating if the terminal was launched
                - status: String indicating the build status (running, environment_error, etc.)
                - output: Initial output message
                - terminal_id: ID of the terminal process
                - output_file: Path to the output file
        """
        # Extract parameters
        test_file_abs_path = parameters.get("test_file_abs_path")
        title = parameters.get("title")
        verify_environment = parameters.get("verify_environment", True)

        if not test_file_abs_path:
            raise ValueError("Missing required parameter: test_file_abs_path")

        # Verify environment if requested
        if verify_environment:
            logger.info("Verifying build environment before running test in terminal")
            env_valid, env_message = self.build_system.verify_environment()
            if not env_valid:
                logger.error(f"Build environment verification failed: {env_message}")
                return {
                    "success": False,
                    "status": BuildStatus.ENVIRONMENT_ERROR.value,
                    "output": f"Environment verification failed: {env_message}",
                    "error_details": {
                        "error_type": "environment",
                        "error_message": env_message
                    }
                }

        # Run the test in a terminal
        logger.info(f"Running test in terminal: {test_file_abs_path}")
        result = self.build_system.run_test_in_terminal(test_file_abs_path, title)

        # Prepare the response
        response = {
            "success": result.success,
            "status": result.status.value,
            "output": result.output,
            "terminal_id": result.terminal_id,
            "output_file": result.output_file
        }

        # Include error details if available
        if result.error_details:
            response["error_details"] = result.error_details

        return response


class GetTerminalOutputTool(JUnitWriterTool):
    """Tool for getting output from a terminal process."""

    def __init__(self, build_system: BuildSystemPort):
        """
        Initialize the GetTerminalOutputTool.

        Args:
            build_system: An implementation of BuildSystemPort
        """
        super().__init__(
            name="get_terminal_output",
            description="Gets the output from a terminal process."
        )
        self.build_system = build_system

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to get terminal output.

        Args:
            parameters: Dictionary containing:
                - terminal_id: ID of the terminal process

        Returns:
            Dictionary containing:
                - output: The output from the terminal process
                - success: Boolean indicating if the output was retrieved successfully
        """
        terminal_id = parameters.get("terminal_id")
        if not terminal_id:
            raise ValueError("Missing required parameter: terminal_id")

        try:
            terminal_id = int(terminal_id)
        except ValueError:
            raise ValueError(f"Invalid terminal_id: {terminal_id}. Must be an integer.")

        logger.info(f"Getting output from terminal {terminal_id}")
        output = self.build_system.get_terminal_output(terminal_id)

        return {
            "output": output,
            "success": True
        }


class ListTerminalProcessesTool(JUnitWriterTool):
    """Tool for listing terminal processes."""

    def __init__(self, build_system: BuildSystemPort):
        """
        Initialize the ListTerminalProcessesTool.

        Args:
            build_system: An implementation of BuildSystemPort
        """
        super().__init__(
            name="list_terminal_processes",
            description="Lists all terminal processes."
        )
        self.build_system = build_system

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to list terminal processes.

        Args:
            parameters: Dictionary (no parameters required)

        Returns:
            Dictionary containing:
                - processes: List of dictionaries containing information about terminal processes
                - count: Number of processes
        """
        logger.info("Listing terminal processes")
        processes = self.build_system.list_terminal_processes()

        return {
            "processes": processes,
            "count": len(processes),
            "success": True
        }


class KillTerminalProcessTool(JUnitWriterTool):
    """Tool for killing a terminal process."""

    def __init__(self, build_system: BuildSystemPort):
        """
        Initialize the KillTerminalProcessTool.

        Args:
            build_system: An implementation of BuildSystemPort
        """
        super().__init__(
            name="kill_terminal_process",
            description="Kills a terminal process."
        )
        self.build_system = build_system

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to kill a terminal process.

        Args:
            parameters: Dictionary containing:
                - terminal_id: ID of the terminal process

        Returns:
            Dictionary containing:
                - success: Boolean indicating if the process was killed
                - message: Message about the result
        """
        terminal_id = parameters.get("terminal_id")
        if not terminal_id:
            raise ValueError("Missing required parameter: terminal_id")

        try:
            terminal_id = int(terminal_id)
        except ValueError:
            raise ValueError(f"Invalid terminal_id: {terminal_id}. Must be an integer.")

        logger.info(f"Killing terminal process {terminal_id}")
        success = self.build_system.kill_terminal_process(terminal_id)

        if success:
            message = f"Successfully killed terminal process {terminal_id}"
        else:
            message = f"Failed to kill terminal process {terminal_id}"

        return {
            "success": success,
            "message": message
        }
