"""
Enhanced LLM-based error parser for Kotlin/JUnit5/MockK errors.
"""
import logging
import json
import re
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
        # Load the prompt template from the prompts directory
        try:
            from unit_test_generator.application.prompts.error_parsing_prompt import get_error_parsing_prompt
            return get_error_parsing_prompt()
        except ImportError:
            logger.warning("Could not import error_parsing_prompt. Using fallback prompt template.")
            # Fallback to hardcoded template if import fails
            return """You are an expert build log analyzer for {language} projects using {build_tool} and {test_framework}.
Your task is to meticulously analyze the provided build/test output and extract structured information about any errors found (compilation errors, test failures, runtime exceptions during tests, or general build failures).

Input Build/Test Output:
------------------------
{raw_output}
------------------------

For each error found, extract the following information:
1. file_path: The path to the file where the error occurred (if available)
2. line_number: The line number where the error occurred (if available)
3. message: The error message
4. error_type: The type of error (e.g., 'Compilation', 'TestFailure', 'Runtime', 'BuildFailure')
5. error_category: A more specific categorization of the error (e.g., 'UnresolvedReference', 'TypeMismatch', 'AssertionFailure')
6. involved_symbols: A list of symbols (classes, methods, variables) involved in the error
7. suggested_fix_approach: A brief suggestion on how to fix the error

IMPORTANT: Your response MUST be a valid JSON array, not Kotlin code or any other format. For example: [{"file_path": "path/to/file.kt", "line_number": 42, "message": "Error message", "error_type": "Compilation", "error_category": "UnresolvedReference", "involved_symbols": ["com.example.Class"], "suggested_fix_approach": "Add missing import for com.example.Class"}]

JSON Output:
"""

    def _build_prompt(self, raw_output: str) -> str:
        """Constructs the prompt for the LLM."""
        # Get context from config (could be cached)
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
            middle_size = max_output_chars - len(beginning) - len(end)
            
            # Try to find error sections in the middle
            middle_candidates = ["error:", "Error:", "ERROR:", "FAILURE:", "BUILD FAILED"]
            middle = ""
            for candidate in middle_candidates:
                if candidate in raw_output:
                    # Find the position of the error
                    pos = raw_output.find(candidate)
                    # Extract a section around the error
                    start = max(0, pos - middle_size // 2)
                    end_pos = min(len(raw_output), pos + middle_size // 2)
                    middle = raw_output[start:end_pos]
                    break
            
            # If no error sections found, just take the middle
            if not middle:
                middle_start = len(beginning)
                middle_end = len(raw_output) - len(end)
                middle_center = (middle_start + middle_end) // 2
                middle = raw_output[middle_center - middle_size // 2:middle_center + middle_size // 2]
            
            raw_output_snippet = f"{beginning}\n...\n{middle}\n...\n{end}"
        else:
            raw_output_snippet = raw_output

        # Use a safer string formatting approach to avoid KeyError
        try:
            return self.prompt_template.format(
                language=language,
                build_tool=build_tool,
                test_framework=test_framework,
                raw_output=raw_output_snippet
            )
        except KeyError as e:
            logger.error(f"Error formatting prompt template: {e}")
            # Fallback to a simpler template if the main one has formatting issues
            fallback_template = """Analyze this build output and return a JSON array of errors:

{raw_output}

Return format: [{{
  "file_path": "path/to/file.kt",
  "line_number": 42,
  "message": "Error message",
  "error_type": "Compilation",
  "error_category": "UnresolvedReference",
  "involved_symbols": ["com.example.Class"],
  "suggested_fix_approach": "Add missing import for com.example.Class"
}}]

IMPORTANT: Your response MUST be a valid JSON array, not Kotlin code.
"""
            return fallback_template.format(raw_output=raw_output_snippet)

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
        # logger.debug(f"LLM Error Parsing Prompt:\n{prompt}") # Log prompt only if needed

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

                # Check if the response is wrapped in a code block
                if cleaned_response.startswith("```json") and cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[7:-3].strip()
                elif cleaned_response.startswith("```") and cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[3:-3].strip()

                # Parse the JSON response
                parsed_data = json.loads(cleaned_response)
                
                if not isinstance(parsed_data, list):
                    logger.warning(f"LLM response is not a list: {type(parsed_data)}")
                    parsed_data = [parsed_data]  # Convert to list if it's a single object
                
                # Validate and convert to ParsedError objects
                structured_errors: List[ParsedError] = []
                for item in parsed_data:
                    if not isinstance(item, dict):
                        logger.warning(f"Skipping invalid item in LLM JSON response (not a dict): {item}")
                        continue
                    try:
                        # Basic validation and type conversion
                        line_num = item.get("line_number")
                        structured_errors.append(ParsedError(
                            file_path=item.get("file_path"),
                            line_number=int(line_num) if line_num is not None else None,
                            message=str(item.get("message", "")),
                            error_type=str(item.get("error_type", "Unknown")),
                            error_category=str(item.get("error_category", "Other")),
                            involved_symbols=item.get("involved_symbols", []),
                            suggested_fix=str(item.get("suggested_fix_approach", ""))
                        ))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Skipping invalid error object structure in LLM response: {item}. Error: {e}")
                
                if structured_errors:
                    logger.info(f"Successfully parsed {len(structured_errors)} errors from LLM response.")
                    return structured_errors
                else:
                    logger.warning("No valid errors found in LLM response. Using fallback regex parsing.")
                    return self._fallback_regex_parsing(raw_output)

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

        # Combine all symbols
        all_symbols = []
        all_symbols.extend(class_names)
        all_symbols.extend(unresolved_symbols)
        all_symbols.extend(missing_imports)
        for match in type_mismatches:
            all_symbols.extend(match)

        # Determine error category
        error_category = "Other"
        if unresolved_symbols:
            error_category = "UnresolvedReference"
        elif missing_imports:
            error_category = "MissingImport"
        elif type_mismatches:
            error_category = "TypeMismatch"

        # Create a ParsedError with the extracted information
        return [ParsedError(
            file_path=file_path,
            line_number=line_number,
            message=message,
            error_type="Compilation",  # Assume compilation error as default
            error_category=error_category,
            involved_symbols=all_symbols,
            suggested_fix="Review the error message and fix the code accordingly."
        )]
