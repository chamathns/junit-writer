"""
Hybrid error parser that combines regex and LLM approaches.
"""
import logging
import json
from typing import List, Dict, Any, Optional

from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.infrastructure.adapters.error_parsing.regex_error_parser_adapter import RegexErrorParserAdapter

logger = logging.getLogger(__name__)

class HybridErrorParserAdapter(ErrorParserPort):
    """
    Hybrid error parser that combines regex and LLM approaches.
    First tries to parse errors using regex patterns, then falls back to LLM if needed.
    """

    def __init__(self, llm_service: LLMServicePort, config: Dict[str, Any]):
        """
        Initializes the adapter.

        Args:
            llm_service: An instance of LLMServicePort to make API calls.
            config: The application configuration dictionary.
        """
        self.llm_service = llm_service
        self.config = config
        self.regex_parser = RegexErrorParserAdapter(config)
        logger.info("HybridErrorParserAdapter initialized.")

    def _get_llm_prompt(self, raw_output: str, regex_errors: List[ParsedError]) -> str:
        """Constructs the prompt for the LLM."""
        language = self.config.get('generation', {}).get('target_language', 'Kotlin')
        build_tool = self.config.get('build_system', {}).get('type', 'Gradle')
        test_framework = self.config.get('generation', {}).get('target_framework', 'JUnit5')

        # Limit raw output size to avoid excessive prompt length
        max_output_chars = 15000
        if len(raw_output) > max_output_chars:
            logger.warning(f"Raw build output exceeds {max_output_chars} chars. Truncating for LLM parser.")
            # Truncate smartly - keep beginning and end, and look for error sections in the middle
            beginning = raw_output[:max_output_chars // 3]
            end = raw_output[-max_output_chars // 3:]

            # Try to find error sections in the middle
            middle_section = ""
            error_indicators = ["error:", "Error:", "Exception:", "FAILED", "BUILD FAILED"]
            for indicator in error_indicators:
                if indicator in raw_output:
                    # Find the position of the error indicator
                    pos = raw_output.find(indicator)
                    # Extract a section around the error
                    start = max(0, pos - 1000)
                    end_pos = min(len(raw_output), pos + 3000)
                    middle_section += raw_output[start:end_pos] + "\n...\n"

            # If we found error sections, use them; otherwise, just use beginning and end
            if middle_section:
                raw_output_snippet = f"{beginning}\n...\n{middle_section}\n...\n{end}"
            else:
                raw_output_snippet = f"{beginning}\n...\n{end}"
        else:
            raw_output_snippet = raw_output

        # Include regex parsing results in the prompt
        regex_results = ""
        if regex_errors:
            regex_results = "Regex parsing found the following errors:\n"
            for i, error in enumerate(regex_errors):
                regex_results += f"Error {i+1}:\n"
                regex_results += f"  - File: {error.file_path}\n"
                regex_results += f"  - Line: {error.line_number}\n"
                regex_results += f"  - Type: {error.error_type}\n"
                regex_results += f"  - Category: {error.error_category}\n"
                regex_results += f"  - Message: {error.message}\n"
                regex_results += f"  - Symbols: {', '.join(error.involved_symbols)}\n"
                regex_results += f"  - Suggested Fix: {error.suggested_fix}\n"
        else:
            regex_results = "Regex parsing did not find any specific errors.\n"

        prompt = "You are an expert build log analyzer for " + language + " projects using " + build_tool + " and " + test_framework + "."
        prompt += """
Your task is to meticulously analyze the provided build/test output and extract structured information about any errors found (compilation errors, test failures, runtime exceptions during tests, or general build failures).

Input Build/Test Output:
------------------------
""" + raw_output_snippet + """
------------------------

Regex Parsing Results:
----------------------
""" + regex_results + """
----------------------

Instructions:
1. Carefully examine the entire output for any indication of failure.
2. Consider the regex parsing results, but feel free to identify additional errors or provide more detailed information.
3. For each distinct error found, extract the following information:
    - file_path: The file path where the error occurred. Prioritize relative paths from the project root if discernible (e.g., app/src/main/kotlin/com/example/MyClass.kt). If only a filename or absolute path is available, provide that. Use null if no specific file is associated.
    - line_number: The specific line number where the error is reported, if available. Use null if not applicable or not found.
    - message: A concise, descriptive message summarizing the error. Include the core reason for the failure.
    - error_type: Classify the error as accurately as possible using one of these exact strings: 'Compilation', 'TestFailure', 'Runtime', 'BuildFailure', 'Unknown'.
    - involved_symbols: A JSON list of strings containing relevant fully qualified class names (e.g., com.example.UserService), method names (e.g., getUserById), or type names (e.g., String, User) mentioned in the error message or stack trace that seem directly related to the error's cause. Extract these precisely as they appear. If none are clearly identifiable, provide an empty list [].
    - error_category: Categorize the error more specifically using one of these strings: 'UnresolvedReference', 'TypeMismatch', 'MissingDependency', 'NullPointerException', 'AssertionFailure', 'MockkVerificationFailure', 'SyntaxError', 'Other'.
    - suggested_fix: A brief description of how this type of error is typically fixed, e.g., "Add missing import", "Fix method signature", "Initialize mock properly", etc.
4. Format your entire response *only* as a single JSON list containing zero or more error objects matching the structure described above. Do not include any introductory text, explanations, summaries, or markdown formatting outside the JSON list itself.
5. If absolutely no errors are found in the output, return an empty JSON list: [].

Common Kotlin/JUnit5/MockK Error Patterns to Look For:
- "Unresolved reference" - Usually indicates a missing import or undefined symbol
- "Type mismatch" - Indicates incompatible types in an assignment or function call
- "io.mockk.MockKException" - Indicates a problem with mock setup or verification
- "org.opentest4j.AssertionFailedError" - Indicates a failed assertion in a test
- "kotlin.UninitializedPropertyAccessException" - Indicates accessing a property before initialization
- "java.lang.NullPointerException" - Indicates a null reference was accessed
- "Cannot access class" - Usually indicates a visibility issue (private/internal class)
- "Missing constructor" - Indicates trying to instantiate a class without proper constructor

IMPORTANT: Your response MUST be a valid JSON array, not Kotlin code or any other format.

JSON Output:
"""
        return prompt

    def _parse_llm_response(self, response_text: str, raw_output: Optional[str] = None) -> List[ParsedError]:
        """Parses the LLM response into a list of ParsedError objects."""
        if not response_text:
            logger.error("LLM returned empty response for error parsing.")
            return []

        logger.debug(f"LLM raw response for error parsing:\n{response_text}")

        # Attempt to parse the response as JSON
        try:
            # Clean potential markdown fences if LLM adds them despite instructions
            cleaned_response = response_text.strip()

            # Check if the response looks like Kotlin code instead of JSON
            if cleaned_response.startswith("```kotlin") or \
               ("package " in cleaned_response and "import " in cleaned_response and "class " in cleaned_response):
                logger.warning("LLM returned Kotlin code instead of JSON.")
                # Try to extract error information from the code
                return self._extract_errors_from_code(cleaned_response, raw_output=raw_output)

            # Remove markdown code fences if present
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[len("```json"):].strip()
            elif cleaned_response.startswith("```"):
                 cleaned_response = cleaned_response[len("```"):].strip()
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-len("```")].strip()

            parsed_data = json.loads(cleaned_response)
            if not isinstance(parsed_data, list):
                raise ValueError("LLM response is not a JSON list.")

            # Validate and convert to ParsedError objects
            structured_errors: List[ParsedError] = []
            for item in parsed_data:
                if not isinstance(item, dict):
                    logger.warning(f"Skipping invalid item in LLM JSON response (not a dict): {item}")
                    continue
                try:
                    # Basic validation and type conversion
                    line_num = item.get("line_number")
                    error = ParsedError(
                        file_path=item.get("file_path"),
                        line_number=int(line_num) if line_num is not None else None,
                        message=str(item.get("message", "")),
                        error_type=str(item.get("error_type", "Unknown")),
                        involved_symbols=item.get("involved_symbols", []),
                        error_category=item.get("error_category", "Other"),
                        suggested_fix=item.get("suggested_fix", "")
                    )
                    structured_errors.append(error)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid error object structure in LLM response: {item}. Error: {e}")

            logger.info(f"LLM successfully parsed {len(structured_errors)} errors.")
            return structured_errors

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode LLM response as JSON: {e}")
            logger.error(f"LLM Response Text was:\n{response_text}")
            return []

        except ValueError as e:
             logger.error(f"LLM JSON response validation failed: {e}")
             logger.error(f"LLM Response Text was:\n{response_text}")
             return []

    def parse_output(self, raw_output: str) -> List[ParsedError]:
        """Parses raw build output using a hybrid approach of regex and LLM."""
        if not raw_output:
            logger.info("Build output is empty. No errors to parse.")
            return []

        if "BUILD SUCCESSFUL" in raw_output and "BUILD FAILED" not in raw_output:
            logger.info("Build output indicates success. No errors to parse.")
            return []

        # First, try to parse errors using regex patterns
        regex_errors = self.regex_parser.parse_output(raw_output)

        # If regex parsing found clear errors, return them
        if regex_errors and all(error.error_category != "Other" for error in regex_errors):
            logger.info(f"Regex parsing found {len(regex_errors)} clear errors. Skipping LLM parsing.")
            return regex_errors

        # If regex parsing didn't find clear errors or found only generic ones, try LLM parsing
        logger.info("Regex parsing didn't find clear errors. Trying LLM parsing.")

        try:
            # Prepare the prompt for the LLM
            prompt = self._get_llm_prompt(raw_output, regex_errors)

            # Create a context dictionary with the prompt
            context = {
                "prompt": prompt,
                "task": "parse_errors",  # Signal that this is an error parsing task
                "language": self.config.get('generation', {}).get('target_language', 'Kotlin'),
                "framework": self.config.get('generation', {}).get('target_framework', 'JUnit5'),
                "response_format": "json",  # Explicitly request JSON format
                "format_instructions": "Return a JSON array of error objects, not code"
            }

            # Call the LLM service
            response_text = self.llm_service.generate_tests(context)

            # Parse the LLM response
            llm_errors = self._parse_llm_response(response_text, raw_output=raw_output)

            # If LLM parsing found errors, return them
            if llm_errors:
                logger.info(f"LLM parsing found {len(llm_errors)} errors.")
                return llm_errors

            # If neither regex nor LLM parsing found clear errors, but we know there are errors,
            # return the regex errors (even if they're generic)
            if regex_errors:
                logger.info("Falling back to regex parsing results.")
                return regex_errors

            # If all else fails, create a generic error
            logger.warning("Neither regex nor LLM parsing found errors, but build failed. Creating a generic error.")
            return [ParsedError(
                message="Build failed but no specific errors were identified. Check raw output for details.",
                error_type="Unknown",
                involved_symbols=[],
                error_category="Other",
                suggested_fix="Review the build output manually to identify the issue."
            )]

        except Exception as e:
            logger.error(f"Error during LLM call for error parsing: {e}", exc_info=True)

            # If LLM parsing fails but regex parsing found errors, return the regex errors
            if regex_errors:
                logger.info("LLM parsing failed. Falling back to regex parsing results.")
                return regex_errors

            # If all else fails, create a generic error
            return [ParsedError(
                message=f"Error parsing failed: {e}",
                error_type="Unknown",
                involved_symbols=[],
                error_category="Other",
                suggested_fix="Review the build output manually to identify the issue."
            )]

    def _extract_errors_from_code(self, code_response: str, raw_output: Optional[str] = None) -> List[ParsedError]:
        """
        Extracts error information from Kotlin code returned by the LLM.
        This is a fallback method when the LLM returns code instead of JSON.

        Args:
            code_response: The code response from the LLM
            raw_output: The raw build output (optional)

        Returns:
            A list of ParsedError objects
        """
        errors = []

        # Clean up code response
        if code_response.startswith("```kotlin"):
            code_response = code_response[len("```kotlin"):]
        if code_response.endswith("```"):
            code_response = code_response[:code_response.rfind("```")]

        code_response = code_response.strip()

        # Look for common error patterns in the code
        lines = code_response.split("\n")

        # Check if this is a placeholder test
        is_placeholder = False
        for line in lines:
            if "placeholder" in line.lower() or "dummy test" in line.lower() or "assert(true)" in line:
                is_placeholder = True
                break

        if is_placeholder:
            # This is a placeholder test, which means the original test had serious issues
            # Create a more specific error
            errors.append(ParsedError(
                message="Test file has compilation errors that need to be fixed. Do not replace with placeholder test.",
                error_type="Compilation",
                involved_symbols=[],
                error_category="SyntaxError",
                suggested_fix="Fix the specific compilation errors in the original test file instead of replacing it."
            ))

            # Try to extract more specific information from raw output if available
            if raw_output:
                # Look for common Kotlin error patterns
                if "Unresolved reference" in raw_output:
                    errors.append(ParsedError(
                        message="Unresolved reference in test file",
                        error_type="Compilation",
                        involved_symbols=[],
                        error_category="UnresolvedReference",
                        suggested_fix="Add missing import or fix the reference"
                    ))
                elif "Type mismatch" in raw_output:
                    errors.append(ParsedError(
                        message="Type mismatch in test file",
                        error_type="Compilation",
                        involved_symbols=[],
                        error_category="TypeMismatch",
                        suggested_fix="Fix the type mismatch"
                    ))

        # If no specific errors were found, add a generic error
        if not errors:
            errors.append(ParsedError(
                message="Unknown compilation error in test file",
                error_type="Compilation",
                involved_symbols=[],
                error_category="Other",
                suggested_fix="Fix compilation errors in the test file"
            ))

        return errors