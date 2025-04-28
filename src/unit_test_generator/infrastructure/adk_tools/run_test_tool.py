# src/unit_test_generator/infrastructure/adk_tools/run_test_tool.py
"""
ADK Tool for running tests using the build system.
"""
import logging
import time
from typing import Dict, Any, Optional, List

from unit_test_generator.domain.ports.build_system import BuildSystemPort, BuildStatus
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class RunTestTool(JUnitWriterTool):
    """Tool for running tests using the build system."""

    def __init__(self, build_system: BuildSystemPort):
        """
        Initialize the RunTestTool.

        Args:
            build_system: An implementation of BuildSystemPort
        """
        super().__init__(
            name="run_test",
            description="Runs a test file using the build system and returns the result.",
            is_long_running=True  # Mark as long-running since test execution can take time
        )
        self.build_system = build_system

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to run a test.

        Args:
            parameters: Dictionary containing:
                - test_file_abs_path: Absolute path to the test file
                - compile_only: (Optional) If True, only compile the test without running it
                - verify_environment: (Optional) If True, verify the build environment first
                - timeout: (Optional) Custom timeout in seconds

        Returns:
            Dictionary containing:
                - success: Boolean indicating if the test passed
                - status: String indicating the build status (success, compilation_error, etc.)
                - output: Raw output from the build system
                - error_details: Structured error information if available
                - execution_time: Time taken to execute in seconds
                - build_info: Information about the build system
        """
        # Extract parameters
        test_file_abs_path = parameters.get("test_file_abs_path")
        compile_only = parameters.get("compile_only", False)
        verify_environment = parameters.get("verify_environment", True)

        if not test_file_abs_path:
            raise ValueError("Missing required parameter: test_file_abs_path")

        # Verify environment if requested
        if verify_environment:
            logger.info("Verifying build environment before running test")
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
                    },
                    "execution_time": 0.0,
                    "build_info": self.build_system.get_build_info()
                }

        # Execute the appropriate build operation
        start_time = time.time()
        if compile_only:
            logger.info(f"Compiling test: {test_file_abs_path}")
            result = self.build_system.compile_test(test_file_abs_path)
            operation = "compilation"
        else:
            logger.info(f"Running test: {test_file_abs_path}")
            result = self.build_system.run_test(test_file_abs_path)
            operation = "execution"

        # Calculate execution time if not provided in result
        execution_time = result.execution_time or (time.time() - start_time)

        # Log the result
        if result.success:
            logger.info(f"Test {operation} succeeded in {execution_time:.2f} seconds")
        else:
            logger.warning(f"Test {operation} failed with status: {result.status}")
            if result.error_details:
                error_type = result.error_details.get("error_type", "unknown")
                logger.debug(f"Error type: {error_type}")

        # Prepare the response
        response = {
            "success": result.success,
            "status": result.status.value,
            "output": result.output,
            "execution_time": execution_time,
            "build_info": self.build_system.get_build_info()
        }

        # Include error details if available
        if result.error_details:
            response["error_details"] = result.error_details

            # Extract key error information for easier access
            if "error_lines" in result.error_details and result.error_details["error_lines"]:
                # Get the first few error lines for quick reference
                error_lines = result.error_details["error_lines"]
                response["error_summary"] = error_lines[0] if isinstance(error_lines[0], str) else "\n".join(error_lines[:3])

            # Include file locations if available
            if "file_locations" in result.error_details:
                response["file_locations"] = result.error_details["file_locations"]

        return response


class VerifyBuildEnvironmentTool(JUnitWriterTool):
    """Tool for verifying the build environment."""

    def __init__(self, build_system: BuildSystemPort):
        """
        Initialize the VerifyBuildEnvironmentTool.

        Args:
            build_system: An implementation of BuildSystemPort
        """
        super().__init__(
            name="verify_build_environment",
            description="Verifies that the build environment is properly configured."
        )
        self.build_system = build_system

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to verify the build environment.

        Args:
            parameters: Dictionary (no parameters required)

        Returns:
            Dictionary containing:
                - success: Boolean indicating if the environment is valid
                - message: Message with details about the environment
                - build_info: Information about the build system
        """
        logger.info("Verifying build environment")
        success, message = self.build_system.verify_environment()

        return {
            "success": success,
            "message": message,
            "build_info": self.build_system.get_build_info()
        }
