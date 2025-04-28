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

            if not response_text:
                logger.error("LLM returned empty response for error parsing.")
                # If LLM parsing fails but regex parsing found errors, return the regex errors
                if regex_errors:
                    logger.info("Falling back to regex parsing results.")
                    return regex_errors
                return [ParsedError(message="LLM returned empty response during error parsing.")]

            logger.debug(f"LLM raw response for error parsing:\n{response_text}")

            # Attempt to parse the response as JSON
            try:
                # Clean potential markdown fences if LLM adds them despite instructions
                cleaned_response = response_text.strip()
                
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
                    logger.warning("No valid errors found in LLM response.")
                    # If LLM parsing fails but regex parsing found errors, return the regex errors
                    if regex_errors:
                        logger.info("Falling back to regex parsing results.")
                        return regex_errors
                    # Create a generic error if no valid errors were found
                    return [ParsedError(
                        message="Failed to extract structured errors from build output.",
                        error_type="Unknown",
                        involved_symbols=[]
                    )]
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode LLM response as JSON: {e}")
                logger.error(f"LLM Response Text was:\n{response_text}")
                
                # If LLM parsing fails but regex parsing found errors, return the regex errors
                if regex_errors:
                    logger.info("JSON decode error. Falling back to regex parsing results.")
                    return regex_errors
                
                # Create a generic error if no valid errors were found
                return [ParsedError(
                    message=f"Failed to decode LLM response as JSON: {e}",
                    error_type="Unknown",
                    involved_symbols=[]
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

    def _get_llm_prompt(self, raw_output: str, regex_errors: List[ParsedError]) -> str:
        """Constructs the prompt for the LLM."""
        # Load the prompt template from the prompts directory
        try:
            from unit_test_generator.application.prompts.error_parsing_prompt import get_error_parsing_prompt
            prompt_template = get_error_parsing_prompt()
        except ImportError:
            logger.warning("Could not import error_parsing_prompt. Using fallback prompt template.")
            # Fallback to hardcoded template if import fails
            prompt_template = """You are an expert build log analyzer for {language} projects using {build_tool} and {test_framework}.
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

        # Add information about regex parsing results if available
        if regex_errors:
            regex_info = "\nRegex parsing found the following potential errors:\n"
            for i, error in enumerate(regex_errors):
                regex_info += f"{i+1}. {error.error_type}: {error.message}"
                if error.file_path:
                    regex_info += f" in {error.file_path}"
                if error.line_number:
                    regex_info += f" at line {error.line_number}"
                if error.involved_symbols:
                    regex_info += f" involving {', '.join(error.involved_symbols)}"
                regex_info += "\n"
            
            # Add the regex info to the raw output
            raw_output_snippet += regex_info

        # Use a safer string formatting approach to avoid KeyError
        try:
            return prompt_template.format(
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
