import logging
import re
from typing import List, Optional
from pathlib import Path

from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError

logger = logging.getLogger(__name__)

class JUnitGradleErrorParserAdapter(ErrorParserPort):
    """
    Parses Gradle/JUnit output for common error patterns.
    WARNING: Uses basic regex, may miss errors or parse incorrectly. Needs refinement.
    """

    # Regex patterns (examples, need significant refinement for robustness)
    # Basic Kotlin/Java compilation error: e: /path/to/File.kt: (line, col): error message
    COMPILATION_ERROR_REGEX = re.compile(r"[ew]:\s*(?P<path>.*?\.k?t):\s*\((?P<line>\d+),\s*\d+\):\s*(?P<message>.*)")
    # Basic JUnit test failure header
    TEST_FAILURE_HEADER_REGEX = re.compile(r"^\s*(?P<test_name>\w+)\(.*\)\s+FAILED$", re.MULTILINE)
    # Simple stack trace line pointing to test file
    STACK_TRACE_TEST_LINE_REGEX = re.compile(r"^\s+at\s+(?P<fqn>[\w\.$<>]+)\((?P<file>.*?\.kt):(?P<line>\d+)\)")


    def parse_output(self, raw_output: str) -> List[ParsedError]:
        logger.debug("Parsing build/test output for errors...")
        errors: List[ParsedError] = []
        lines = raw_output.splitlines()

        # --- Pass 1: Compilation Errors ---
        for line in lines:
            match = self.COMPILATION_ERROR_REGEX.search(line)
            if match:
                data = match.groupdict()
                # Attempt to make path relative (assuming it's absolute)
                # This needs the repo_root, which isn't easily available here.
                # TODO: Inject repo_root or handle path normalization later.
                file_path = data.get('path')
                errors.append(ParsedError(
                    file_path=file_path, # Might be absolute
                    line_number=int(data.get('line', 0)),
                    message=data.get('message', '').strip(),
                    error_type="Compilation"
                ))

        # --- Pass 2: Test Failures (Very Basic) ---
        # This is highly simplified. Real JUnit output parsing is complex.
        in_failure_block = False
        current_failure: Optional[ParsedError] = None
        for line in lines:
             header_match = self.TEST_FAILURE_HEADER_REGEX.search(line)
             if header_match:
                 in_failure_block = True
                 # Create a basic error for the test failure
                 current_failure = ParsedError(
                     message=f"Test failed: {header_match.group('test_name')}",
                     error_type="TestFailure"
                 )
                 errors.append(current_failure)
                 continue

             if in_failure_block and current_failure:
                 # Look for the first stack trace line pointing to a test file
                 stack_match = self.STACK_TRACE_TEST_LINE_REGEX.search(line)
                 if stack_match and stack_match.group('file').endswith("Test.kt"): # Crude check
                     data = stack_match.groupdict()
                     current_failure.file_path = data.get('file') # Might be just filename
                     current_failure.line_number = int(data.get('line', 0))
                     # Add more stack trace info to message?
                     # current_failure.message += f"\n  at {line.strip()}"
                     in_failure_block = False # Found relevant line, stop block
                     current_failure = None
                 elif line.strip() == "" or "BUILD FAILED" in line:
                     # End of block or build failure message
                     in_failure_block = False
                     current_failure = None

        if not errors and "BUILD FAILED" in raw_output:
             # Generic build failure if no specific errors parsed
             errors.append(ParsedError(message="Build failed. Check raw output.", error_type="BuildFailure"))

        logger.info(f"Parsed {len(errors)} potential errors from output.")
        return errors