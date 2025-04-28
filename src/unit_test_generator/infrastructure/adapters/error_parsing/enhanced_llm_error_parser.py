import logging
import json
from typing import List, Dict, Any, Optional

from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError
from unit_test_generator.domain.ports.llm_service import LLMServicePort

logger = logging.getLogger(__name__)

class EnhancedLLMErrorParserAdapter(ErrorParserPort):
    """
    Enhanced error parser that uses an LLM to extract detailed information from build/test output.
    Specifically optimized for Kotlin/JUnit5/MockK errors.
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
        self.prompt_template = self._get_default_prompt_template()
        logger.info("EnhancedLLMErrorParserAdapter initialized.")

    def _get_default_prompt_template(self) -> str:
        """Provides the default prompt template for error parsing."""
        return """You are an expert build log analyzer for {language} projects using {build_tool} and {test_framework}.
Your task is to meticulously analyze the provided build/test output and extract structured information about any errors found (compilation errors, test failures, runtime exceptions during tests, or general build failures).

Input Build/Test Output:
------------------------
{raw_output}
------------------------

Instructions:
1. Carefully examine the entire output for any indication of failure.
2. Identify distinct errors. A single underlying issue might manifest across multiple lines (e.g., a compilation error message followed by the problematic code line). Group related lines into a single error object where appropriate.
3. For each distinct error found, extract the following information:
    - `file_path`: The file path where the error occurred. Prioritize relative paths from the project root if discernible (e.g., `app/src/main/kotlin/com/example/MyClass.kt`). If only a filename or absolute path is available, provide that. Use `null` if no specific file is associated.
    - `line_number`: The specific line number where the error is reported, if available. Use `null` if not applicable or not found.
    - `message`: A concise, descriptive message summarizing the error. Include the core reason for the failure.
    - `error_type`: Classify the error as accurately as possible using one of these exact strings: 'Compilation', 'TestFailure', 'Runtime', 'BuildFailure', 'Unknown'.
    - `involved_symbols`: A JSON list of strings containing relevant fully qualified class names (e.g., `com.example.UserService`), method names (e.g., `getUserById`), or type names (e.g., `String`, `User`) mentioned in the error message or stack trace that seem directly related to the error's cause. Extract these precisely as they appear. If none are clearly identifiable, provide an empty list `[]`.
    - `error_category`: Categorize the error more specifically using one of these strings: 'UnresolvedReference', 'TypeMismatch', 'MissingDependency', 'NullPointerException', 'AssertionFailure', 'MockkVerificationFailure', 'SyntaxError', 'Other'.
    - `suggested_fix_approach`: A brief description of how this type of error is typically fixed, e.g., "Add missing import", "Fix method signature", "Initialize mock properly", etc.
4. Format your entire response *only* as a single JSON list containing zero or more error objects matching the structure described above. Do not include any introductory text, explanations, summaries, or markdown formatting outside the JSON list itself.
5. If absolutely no errors are found in the output, return an empty JSON list: `[]`.

Common Kotlin/JUnit5/MockK Error Patterns to Look For:
- "Unresolved reference" - Usually indicates a missing import or undefined symbol
- "Type mismatch" - Indicates incompatible types in an assignment or function call
- "io.mockk.MockKException" - Indicates a problem with mock setup or verification
- "org.opentest4j.AssertionFailedError" - Indicates a failed assertion in a test
- "kotlin.UninitializedPropertyAccessException" - Indicates accessing a property before initialization
- "java.lang.NullPointerException" - Indicates a null reference was accessed
- "Cannot access class" - Usually indicates a visibility issue (private/internal class)
- "Missing constructor" - Indicates trying to instantiate a class without proper constructor

IMPORTANT: Your response MUST be a valid JSON array, not Kotlin code or any other format. For example: [{"file_path": "path/to/file.kt", "line_number": 42, "message": "Error message", "error_type": "Compilation", "error_category": "UnresolvedReference", "involved_symbols": ["com.example.Class"], "suggested_fix_approach": "Add missing import for com.example.Class"}]

JSON Output:
""" # The LLM should append the JSON list here

    def _build_prompt(self, raw_output: str) -> str:
        """Constructs the prompt for the LLM."""
        # Get context from config (could be cached)
        language = self.config.get('generation', {}).get('target_language', 'Kotlin')
        build_tool = self.config.get('build_system', {}).get('type', 'Gradle')
        test_framework = self.config.get('generation', {}).get('target_framework', 'JUnit5') # Simplified framework name

        # Limit raw output size to avoid excessive prompt length
        max_output_chars = 15000 # Increased from 10000 to capture more context
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

        # Create a simple prompt that doesn't use string formatting for the JSON example
        prompt = "You are an expert build log analyzer for " + language + " projects using " + build_tool + " and " + test_framework + "."
        prompt += """
Your task is to meticulously analyze the provided build/test output and extract structured information about any errors found (compilation errors, test failures, runtime exceptions during tests, or general build failures).

Input Build/Test Output:
------------------------
""" + raw_output_snippet + """
------------------------

Instructions:
1. Carefully examine the entire output for any indication of failure.
2. Identify distinct errors. A single underlying issue might manifest across multiple lines (e.g., a compilation error message followed by the problematic code line). Group related lines into a single error object where appropriate.
3. For each distinct error found, extract the following information:
    - file_path: The file path where the error occurred. Prioritize relative paths from the project root if discernible (e.g., app/src/main/kotlin/com/example/MyClass.kt). If only a filename or absolute path is available, provide that. Use null if no specific file is associated.
    - line_number: The specific line number where the error is reported, if available. Use null if not applicable or not found.
    - message: A concise, descriptive message summarizing the error. Include the core reason for the failure.
    - error_type: Classify the error as accurately as possible using one of these exact strings: 'Compilation', 'TestFailure', 'Runtime', 'BuildFailure', 'Unknown'.
    - involved_symbols: A JSON list of strings containing relevant fully qualified class names (e.g., com.example.UserService), method names (e.g., getUserById), or type names (e.g., String, User) mentioned in the error message or stack trace that seem directly related to the error's cause. Extract these precisely as they appear. If none are clearly identifiable, provide an empty list [].
    - error_category: Categorize the error more specifically using one of these strings: 'UnresolvedReference', 'TypeMismatch', 'MissingDependency', 'NullPointerException', 'AssertionFailure', 'MockkVerificationFailure', 'SyntaxError', 'Other'.
    - suggested_fix_approach: A brief description of how this type of error is typically fixed, e.g., "Add missing import", "Fix method signature", "Initialize mock properly", etc.
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

IMPORTANT: Your response MUST be a valid JSON array, not Kotlin code or any other format. For example: [{"file_path": "path/to/file.kt", "line_number": 42, "message": "Error message", "error_type": "Compilation", "error_category": "UnresolvedReference", "involved_symbols": ["com.example.Class"], "suggested_fix_approach": "Add missing import for com.example.Class"}]

JSON Output:
"""
        return prompt

    def parse_output(self, raw_output: str) -> List[ParsedError]:
        """Parses raw build output using an LLM call."""
        if not raw_output:
            logger.info("Build output is empty. No errors to parse.")
            return []

        if "BUILD SUCCESSFUL" in raw_output and "BUILD FAILED" not in raw_output:
            logger.info("Build output indicates success. No errors to parse.")
            return []

        # If there's output but no clear success message, we should try to find errors
        # If the LLM fails to find specific errors, we'll create a generic one

        prompt = self._build_prompt(raw_output)
        logger.info("Requesting error analysis from LLM...")
        logger.debug(f"LLM Error Parsing Prompt:\n{prompt}") # Log prompt for debugging

        try:
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

            if not response_text:
                logger.error("LLM returned empty response for error parsing.")
                return [ParsedError(message="LLM returned empty response during error parsing.")]

            logger.debug(f"LLM raw response for error parsing:\n{response_text}")

            # Attempt to parse the response as JSON
            try:
                # Clean potential markdown fences if LLM adds them despite instructions
                cleaned_response = response_text.strip()

                # Check if the response looks like Kotlin code instead of JSON
                if cleaned_response.startswith("```kotlin") or \
                   ("package " in cleaned_response and "import " in cleaned_response and "class " in cleaned_response):
                    logger.warning("LLM returned Kotlin code instead of JSON. Extracting information from build output directly.")
                    return self._fallback_regex_parsing(raw_output)

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
                            suggested_fix=item.get("suggested_fix_approach", "")
                        )
                        structured_errors.append(error)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Skipping invalid error object structure in LLM response: {item}. Error: {e}")

                logger.info(f"LLM successfully parsed {len(structured_errors)} errors.")

                # If the LLM didn't find any errors but we know there are errors (since we're here),
                # create a generic error
                if not structured_errors and "BUILD FAILED" in raw_output:
                    logger.warning("LLM didn't find any errors but build failed. Creating a generic error.")
                    return [ParsedError(
                        message="Build failed but no specific errors were identified. Check raw output for details.",
                        error_type="Unknown",
                        involved_symbols=[],
                        error_category="Other",
                        suggested_fix="Review the build output manually to identify the issue."
                    )]

                return structured_errors

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode LLM response as JSON: {e}")
                logger.error(f"LLM Response Text was:\n{response_text}")
                return self._fallback_regex_parsing(raw_output)

            except ValueError as e:
                 logger.error(f"LLM JSON response validation failed: {e}")
                 logger.error(f"LLM Response Text was:\n{response_text}")
                 return self._fallback_regex_parsing(raw_output)

        except Exception as e:
            logger.error(f"Error during LLM call for error parsing: {e}", exc_info=True)
            return [ParsedError(message=f"LLM call failed during error parsing: {e}")]

    def _fallback_regex_parsing(self, raw_output: str) -> List[ParsedError]:
        """
        Fallback method to extract error information using regex patterns.
        This is used when the LLM fails to provide a valid JSON response.
        """
        logger.info("Using fallback regex parsing for error extraction")
        import re
        errors = []

        # Try to extract file paths
        file_paths = re.findall(r'([\w./]+\.kt)', raw_output)
        file_path = file_paths[0] if file_paths else None

        # Try to extract line numbers
        line_numbers = re.findall(r':(\d+):', raw_output)
        line_number = int(line_numbers[0]) if line_numbers else None

        # Try to extract class names
        class_names = re.findall(r'class\s+([A-Z][\w]+)', raw_output)

        # Try to extract import statements to find potential dependencies
        imports = re.findall(r'import\s+([\w.]+)', raw_output)

        # Try to extract error messages
        error_messages = re.findall(r'error:\s*([^\n]+)', raw_output)
        message = error_messages[0] if error_messages else "Failed to parse build output. See raw output for details."

        # Try to extract unresolved symbols from error messages
        unresolved_symbols = re.findall(r'Unresolved reference: ([\w.]+)', raw_output)

        # Try to extract missing imports from error messages
        missing_imports = re.findall(r"Cannot access class '([\w.]+)'", raw_output)

        # Try to extract type mismatch errors
        type_mismatches = re.findall(r"Type mismatch: inferred type is ([\w.]+) but ([\w.]+) was expected", raw_output)

        # Add all extracted symbols to the involved symbols
        involved_symbols = list(set(class_names + imports + unresolved_symbols + missing_imports))
        if type_mismatches:
            for mismatch in type_mismatches:
                involved_symbols.extend(mismatch)

        # Filter out common words that are not likely to be symbols
        common_words = ['Failed', 'Error', 'Exception', 'Warning', 'Info', 'Debug', 'Trace']
        involved_symbols = [s for s in involved_symbols if s not in common_words]

        # Determine error category
        error_category = "Other"
        suggested_fix = "Review the build output manually to identify the issue."

        if unresolved_symbols:
            error_category = "UnresolvedReference"
            suggested_fix = f"Add missing import for {', '.join(unresolved_symbols)}"
        elif type_mismatches:
            error_category = "TypeMismatch"
            suggested_fix = "Fix type mismatch in assignment or function call"
        elif "MockKException" in raw_output:
            error_category = "MockkVerificationFailure"
            suggested_fix = "Fix mock setup or verification"
        elif "AssertionFailedError" in raw_output:
            error_category = "AssertionFailure"
            suggested_fix = "Fix failing assertion in test"
        elif "NullPointerException" in raw_output:
            error_category = "NullPointerException"
            suggested_fix = "Handle null reference properly"
        elif "Cannot access class" in raw_output:
            error_category = "MissingDependency"
            suggested_fix = "Fix visibility issue or add missing dependency"

        # Create a ParsedError with the extracted information
        errors.append(ParsedError(
            message=message,
            error_type="Compilation" if "error:" in raw_output else "Unknown",
            file_path=file_path,
            line_number=line_number,
            involved_symbols=involved_symbols,
            error_category=error_category,
            suggested_fix=suggested_fix
        ))

        return errors
