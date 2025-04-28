import logging
import subprocess
import os
import time
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

from unit_test_generator.domain.ports.build_system import (
    BuildSystemPort,
    TestRunResult,
    BuildStatus
)
from unit_test_generator.infrastructure.utils.terminal_process_manager import terminal_manager

logger = logging.getLogger(__name__)

class GradleAdapter(BuildSystemPort):
    """Build system interaction implementation for Gradle."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.repo_root = Path(config['repository']['root_path']).resolve()

        # Load build system configuration with defaults
        build_config = config.get('build_system', {})
        self.gradle_command = build_config.get('command', './gradlew')
        self.fallback_commands = build_config.get('fallback_commands', ['gradle', './gradlew.bat'])

        # Handle pre_args as either string or list
        pre_args = build_config.get('pre_args', '--stacktrace')
        self.pre_args = pre_args.split() if isinstance(pre_args, str) else pre_args

        self.timeout = build_config.get('timeout', 120)
        self.verify_before_run = build_config.get('verify_before_run', True)
        self.compile_before_run = build_config.get('compile_before_run', True)

        # Terminal execution settings
        self.terminal_settings = build_config.get('terminal', {})
        self.use_terminal = self.terminal_settings.get('enabled', True)
        self.terminal_title_prefix = self.terminal_settings.get('title_prefix', 'JUnit Writer Test')

        # Module mapping configuration
        self.module_mapping = build_config.get('module_mapping', {})
        self.mapping_strategy = self.module_mapping.get('strategy', 'path_based')
        self.explicit_modules = self.module_mapping.get('modules', {})

        # Test roots from indexing config
        self.test_roots = config.get('indexing', {}).get('test_roots', ['src/test/kotlin'])

        # Store reference to terminal manager for direct access
        self.terminal_manager = terminal_manager

        # Cache for verified commands
        self._verified_command = None

    def verify_environment(self) -> Tuple[bool, str]:
        """Verifies that Gradle is properly installed and configured."""
        logger.info("Verifying Gradle environment...")

        # Try primary command first, then fallbacks
        commands_to_try = [self.gradle_command] + self.fallback_commands

        for cmd in commands_to_try:
            # Check if command exists
            if cmd.startswith('./') and not Path(self.repo_root / cmd[2:]).exists():
                logger.debug(f"Command {cmd} not found in repository root")
                continue

            if not cmd.startswith('./') and shutil.which(cmd) is None:
                logger.debug(f"Command {cmd} not found in PATH")
                continue

            # Try running version command
            try:
                result = subprocess.run(
                    [cmd, '--version'],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False
                )

                if result.returncode == 0:
                    # Cache the working command
                    self._verified_command = cmd
                    version_info = self._parse_gradle_version(result.stdout)
                    return True, f"Gradle environment verified. Using {cmd} - {version_info}"
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
                logger.warning(f"Error verifying Gradle command {cmd}: {e}")

        # If we get here, no command worked
        return False, "Failed to verify Gradle environment. No working Gradle command found."

    def _parse_gradle_version(self, version_output: str) -> str:
        """Extract Gradle version from version command output."""
        match = re.search(r'Gradle ([\d.]+)', version_output)
        if match:
            return f"Gradle {match.group(1)}"
        return "Unknown Gradle version"

    def _map_path_to_gradle_task(self, test_file_abs_path: Path) -> Tuple[str, str]:
        """
        Maps an absolute test file path to a Gradle module and fully qualified class name.
        Supports different mapping strategies.
        """
        try:
            relative_path = test_file_abs_path.relative_to(self.repo_root)
            parts = relative_path.parts

            # Different mapping strategies
            if self.mapping_strategy == 'explicit':
                # Use explicit module mapping if available
                for module_path, module_name in self.explicit_modules.items():
                    if str(relative_path).startswith(module_path):
                        # Found matching module
                        module = module_name
                        break
                else:
                    # Default to path-based if no explicit match
                    module = self._path_based_module_mapping(parts)
            else:
                # Default path-based mapping
                module = self._path_based_module_mapping(parts)

            # Get fully qualified class name
            fqn = self._extract_class_fqn(relative_path, test_file_abs_path)

            return module, fqn

        except Exception as e:
            logger.error(f"Failed to map path {test_file_abs_path} to Gradle task/class: {e}", exc_info=True)
            raise ValueError(f"Path mapping failed: {e}") from e

    def _path_based_module_mapping(self, path_parts: Tuple[str, ...]) -> str:
        """Extract module name from path parts using path-based strategy."""
        # Handle root module case
        if len(path_parts) <= 1:
            return ""

        # Standard multi-module project: first part is the module name
        module_name = f":{path_parts[0]}"

        # Handle nested modules (e.g., :parent:child)
        # This is a simplified approach - for complex module structures,
        # explicit mapping would be better
        if len(path_parts) > 2 and path_parts[1] != 'src':
            # Check if this might be a nested module
            potential_module = Path(*path_parts[:2])
            if (self.repo_root / potential_module / 'build.gradle').exists() or \
               (self.repo_root / potential_module / 'build.gradle.kts').exists():
                module_name = f":{path_parts[0]}:{path_parts[1]}"

        return module_name

    def _extract_class_fqn(self, relative_path: Path, abs_path: Path) -> str:
        """Extract fully qualified class name from the test file path."""
        parts = relative_path.parts

        # Try to find the test root directory in the path
        for test_root in self.test_roots:
            test_root_parts = Path(test_root).parts
            for i in range(len(parts) - len(test_root_parts) + 1):
                if parts[i:i+len(test_root_parts)] == test_root_parts:
                    # Found the test root, package starts after this
                    pkg_start_idx = i + len(test_root_parts)
                    if pkg_start_idx < len(parts):
                        fqn = ".".join(parts[pkg_start_idx:]).replace(abs_path.suffix, '')
                        return fqn

        # Fallback: try to find src/test/kotlin pattern
        pkg_start_idx = -1
        for i, part in enumerate(parts):
            if part == 'kotlin' and i > 1 and parts[i-1] == 'test' and parts[i-2] == 'src':
                pkg_start_idx = i + 1
                break

        if pkg_start_idx != -1 and pkg_start_idx < len(parts):
            fqn = ".".join(parts[pkg_start_idx:]).replace(abs_path.suffix, '')
            return fqn

        # Last resort: just use the filename without extension
        return abs_path.stem

    def _get_gradle_command(self) -> str:
        """Get the verified Gradle command or try to verify one."""
        if self._verified_command:
            return self._verified_command

        # Try to verify and get a working command
        success, _ = self.verify_environment()
        if success and self._verified_command:
            return self._verified_command

        # Fall back to configured command if verification failed
        return self.gradle_command

    def _execute_gradle_command(self, command: List[str], operation: str) -> Tuple[bool, BuildStatus, str, Dict[str, Any]]:
        """Execute a Gradle command and process the result."""
        command_str = " ".join(command)
        logger.info(f"Executing Gradle command: {command_str}")

        start_time = time.time()
        error_details = {}

        try:
            result = subprocess.run(
                command,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False
            )

            execution_time = time.time() - start_time
            success = result.returncode == 0
            output = f"--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}"

            # Determine status based on output and return code
            status = BuildStatus.SUCCESS if success else self._determine_error_status(result.stderr, result.stdout)

            # Extract error details if available
            if not success:
                error_details = self._extract_error_details(result.stderr, result.stdout, status)
                logger.debug(f"{operation} failed with status {status}:\n{output}")
            else:
                logger.info(f"{operation} succeeded in {execution_time:.2f} seconds")

            return success, status, output, error_details

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            logger.error(f"{operation} timed out after {execution_time:.2f} seconds")
            return False, BuildStatus.RUNTIME_ERROR, f"Error: {operation} timed out after {self.timeout} seconds", {
                "error_type": "timeout",
                "command": command_str,
                "timeout": self.timeout
            }

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error during {operation}: {e}", exc_info=True)
            return False, BuildStatus.UNKNOWN_ERROR, f"Error executing {operation}: {e}", {
                "error_type": "exception",
                "error_message": str(e),
                "command": command_str
            }

    def _determine_error_status(self, stderr: str, stdout: str) -> BuildStatus:
        """Determine the type of build error from output."""
        combined = stderr + stdout

        # Common compilation error patterns
        if re.search(r'Compilation failed|compilation failed|Compilation error|Could not compile', combined):
            return BuildStatus.COMPILATION_ERROR

        # Configuration errors
        if re.search(r'Configuration failed|configuration failed|Could not resolve|Could not find|Invalid configuration', combined):
            return BuildStatus.CONFIGURATION_ERROR

        # Runtime errors in tests
        if re.search(r'Test failed|test failed|Execution failed|execution failed', combined):
            return BuildStatus.RUNTIME_ERROR

        # Environment errors
        if re.search(r'No such file or directory|not found|Cannot run program|JAVA_HOME|JDK', combined):
            return BuildStatus.ENVIRONMENT_ERROR

        # Default to unknown
        return BuildStatus.UNKNOWN_ERROR

    def _extract_error_details(self, stderr: str, stdout: str, status: BuildStatus) -> Dict[str, Any]:
        """Extract structured error details from build output."""
        combined = stderr + stdout
        details = {
            "error_type": status.value,
            "error_lines": []
        }

        # Extract relevant error lines based on status
        if status == BuildStatus.COMPILATION_ERROR:
            # Look for compilation errors
            error_lines = re.findall(r'(?:error:|Compilation failed|compilation error)[^\n]*(?:\n\s+[^\n]+)*', combined)
            if error_lines:
                details["error_lines"] = error_lines

            # Try to extract file and line information
            file_info = re.findall(r'([\w./]+\.(?:kt|java)):(\d+)(?::(\d+))?', combined)
            if file_info:
                details["file_locations"] = [
                    {"file": f, "line": int(l), "column": int(c) if c else None}
                    for f, l, c in file_info
                ]

        elif status == BuildStatus.RUNTIME_ERROR:
            # Look for test failure information
            test_failures = re.findall(r'Test .*? failed[^\n]*(?:\n\s+[^\n]+)*', combined)
            if test_failures:
                details["error_lines"] = test_failures

            # Try to extract assertion failures
            assertions = re.findall(r'(?:expected|actual|AssertionError)[^\n]*(?:\n\s+[^\n]+)*', combined)
            if assertions:
                details["assertions"] = assertions

        elif status == BuildStatus.CONFIGURATION_ERROR:
            # Look for configuration problems
            config_errors = re.findall(r'(?:Could not|Failed to|configuration error)[^\n]*(?:\n\s+[^\n]+)*', combined)
            if config_errors:
                details["error_lines"] = config_errors

        # If we couldn't extract specific errors, include some context
        if not details["error_lines"]:
            # Get last few lines that might contain error info
            lines = combined.splitlines()
            details["error_lines"] = lines[-10:] if len(lines) > 10 else lines

        return details

    def compile_test(self, test_file_abs_path_str: str) -> TestRunResult:
        """Compiles a test file without running it."""
        test_file_abs_path = Path(test_file_abs_path_str).resolve()
        logger.info(f"Attempting to compile test file: {test_file_abs_path}")

        # Verify environment if configured to do so
        if self.verify_before_run:
            env_valid, env_message = self.verify_environment()
            if not env_valid:
                logger.error(f"Environment verification failed: {env_message}")
                return TestRunResult(
                    success=False,
                    status=BuildStatus.ENVIRONMENT_ERROR,
                    output=f"Environment verification failed: {env_message}"
                )

        try:
            # Map path to Gradle module and class
            module, test_class_fqn = self._map_path_to_gradle_task(test_file_abs_path)

            # Use compileTestKotlin or compileTestJava task based on file extension
            if test_file_abs_path.suffix.lower() == '.kt':
                compile_task = f"{module}:compileTestKotlin"
            else:
                compile_task = f"{module}:compileTestJava"

            # Construct command
            gradle_cmd = self._get_gradle_command()
            command = [
                gradle_cmd,
                *self.pre_args,
                compile_task
            ]

            # Execute the compile command
            success, status, output, error_details = self._execute_gradle_command(command, "Test compilation")

            # Create execution time
            execution_time = time.time() - time.time()  # This will be close to 0, just a placeholder

            return TestRunResult(
                success=success,
                status=status,
                output=output,
                error_details=error_details,
                execution_time=execution_time
            )

        except ValueError as e:  # From path mapping
            logger.error(f"Skipping compilation due to path mapping error: {e}")
            return TestRunResult(
                success=False,
                status=BuildStatus.CONFIGURATION_ERROR,
                output=f"Error: Could not determine compilation task. {e}",
                error_details={"error_type": "path_mapping", "error_message": str(e)}
            )
        except Exception as e:
            logger.error(f"Error during test compilation: {e}", exc_info=True)
            return TestRunResult(
                success=False,
                status=BuildStatus.UNKNOWN_ERROR,
                output=f"Error during test compilation: {e}",
                error_details={"error_type": "exception", "error_message": str(e)}
            )

    def run_test(self, test_file_abs_path_str: str) -> TestRunResult:
        """Compiles and runs a specific test file."""
        test_file_abs_path = Path(test_file_abs_path_str).resolve()
        logger.info(f"Attempting to run test file: {test_file_abs_path}")

        # Verify environment if configured to do so
        if self.verify_before_run:
            env_valid, env_message = self.verify_environment()
            if not env_valid:
                logger.error(f"Environment verification failed: {env_message}")
                return TestRunResult(
                    success=False,
                    status=BuildStatus.ENVIRONMENT_ERROR,
                    output=f"Environment verification failed: {env_message}"
                )

        # Compile test first if configured to do so
        if self.compile_before_run:
            compile_result = self.compile_test(test_file_abs_path_str)
            if not compile_result.success:
                logger.warning("Test compilation failed, skipping test execution")
                return compile_result

        start_time = time.time()

        try:
            # Map path to Gradle module and class
            module, test_class_fqn = self._map_path_to_gradle_task(test_file_abs_path)
            test_task = f"{module}:test"
            test_filter = f"--tests \"{test_class_fqn}\""  # Quotes handle special chars

            # Construct command
            gradle_cmd = self._get_gradle_command()
            command = [
                gradle_cmd,
                *self.pre_args,
                test_task,
                test_filter
            ]

            # Execute the test command
            success, status, output, error_details = self._execute_gradle_command(command, "Test execution")
            execution_time = time.time() - start_time

            return TestRunResult(
                success=success,
                status=status,
                output=output,
                error_details=error_details,
                execution_time=execution_time
            )

        except ValueError as e:  # From path mapping
            logger.error(f"Skipping test run due to path mapping error: {e}")
            return TestRunResult(
                success=False,
                status=BuildStatus.CONFIGURATION_ERROR,
                output=f"Error: Could not determine test task. {e}",
                error_details={"error_type": "path_mapping", "error_message": str(e)},
                execution_time=time.time() - start_time
            )
        except Exception as e:
            logger.error(f"Error running test: {e}", exc_info=True)
            return TestRunResult(
                success=False,
                status=BuildStatus.UNKNOWN_ERROR,
                output=f"Error running test: {e}",
                error_details={"error_type": "exception", "error_message": str(e)},
                execution_time=time.time() - start_time
            )

    def get_build_info(self) -> Dict[str, Any]:
        """Returns information about the Gradle build system."""
        info = {
            "type": "gradle",
            "command": self._get_gradle_command(),
            "repo_root": str(self.repo_root),
            "configuration": {
                "pre_args": self.pre_args,
                "timeout": self.timeout,
                "verify_before_run": self.verify_before_run,
                "compile_before_run": self.compile_before_run,
                "mapping_strategy": self.mapping_strategy,
                "terminal": {
                    "enabled": self.use_terminal,
                    "title_prefix": self.terminal_title_prefix
                }
            }
        }

        # Try to get Gradle version
        try:
            success, message = self.verify_environment()
            if success:
                info["version"] = message
            else:
                info["version"] = "Unknown (verification failed)"
        except Exception as e:
            info["version"] = f"Error getting version: {e}"

        return info

    def run_test_in_terminal(self, test_file_abs_path: str, title: str = None) -> TestRunResult:
        """Runs a test in a separate terminal window."""
        test_file_abs_path = Path(test_file_abs_path).resolve()
        logger.info(f"Attempting to run test file in terminal: {test_file_abs_path}")

        # Verify environment if configured to do so
        if self.verify_before_run:
            env_valid, env_message = self.verify_environment()
            if not env_valid:
                logger.error(f"Environment verification failed: {env_message}")
                return TestRunResult(
                    success=False,
                    status=BuildStatus.ENVIRONMENT_ERROR,
                    output=f"Environment verification failed: {env_message}"
                )

        try:
            # Map path to Gradle module and class
            module, test_class_fqn = self._map_path_to_gradle_task(test_file_abs_path)
            test_task = f"{module}:test"
            test_filter = f"--tests \"{test_class_fqn}\""  # Quotes handle special chars

            # Construct command
            gradle_cmd = self._get_gradle_command()
            command = [
                gradle_cmd,
                *self.pre_args,
                test_task,
                test_filter
            ]

            # Create a title for the terminal window
            window_title = title or f"{self.terminal_title_prefix}: {test_class_fqn}"

            # Run the command in a terminal
            terminal_id, output_file = terminal_manager.run_in_terminal(
                command=command,
                cwd=str(self.repo_root),
                title=window_title,
                capture_output=True
            )

            logger.info(f"Started test in terminal {terminal_id}: {test_class_fqn}")

            return TestRunResult(
                success=True,  # Initially successful (terminal launched)
                status=BuildStatus.RUNNING,
                output=f"Test running in terminal {terminal_id}. Output will be captured to {output_file}",
                terminal_id=terminal_id,
                output_file=output_file
            )

        except ValueError as e:  # From path mapping
            logger.error(f"Skipping terminal test run due to path mapping error: {e}")
            return TestRunResult(
                success=False,
                status=BuildStatus.CONFIGURATION_ERROR,
                output=f"Error: Could not determine test task. {e}",
                error_details={"error_type": "path_mapping", "error_message": str(e)}
            )
        except Exception as e:
            logger.error(f"Error running test in terminal: {e}", exc_info=True)
            return TestRunResult(
                success=False,
                status=BuildStatus.UNKNOWN_ERROR,
                output=f"Error running test in terminal: {e}",
                error_details={"error_type": "exception", "error_message": str(e)}
            )

    def get_terminal_output(self, terminal_id: int) -> str:
        """Gets the output from a terminal process."""
        return terminal_manager.get_output(terminal_id)

    def kill_terminal_process(self, terminal_id: int) -> bool:
        """Kills a terminal process."""
        return terminal_manager.kill_process(terminal_id)

    def list_terminal_processes(self) -> List[Dict[str, Any]]:
        """Lists all terminal processes."""
        return terminal_manager.list_processes()
