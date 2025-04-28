import logging
import json
from typing import List, Dict, Any, Optional

from unit_test_generator.domain.ports.error_parser import ErrorParserPort, ParsedError
from unit_test_generator.domain.ports.llm_service import LLMServicePort

logger = logging.getLogger(__name__)

class LLMErrorParserAdapter(ErrorParserPort):
    """
    Parses build/test output using an LLM call to extract structured errors.
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
        # Consider loading prompt template from config or file if complex
        self.prompt_template = self._get_default_prompt_template()
        logger.info("LLMErrorParserAdapter initialized.")

    def _get_default_prompt_template(self) -> str:
        """Provides the default prompt template for error parsing."""
        # This could be loaded from config['error_parsing']['prompt_template_path']
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
4. Format your entire response *only* as a single JSON list containing zero or more error objects matching the structure described above. Do not include any introductory text, explanations, summaries, or markdown formatting outside the JSON list itself.
5. If absolutely no errors are found in the output, return an empty JSON list: `[]`.

IMPORTANT: Your response MUST be a valid JSON array, not Kotlin code or any other format. For example: [{{"file_path": "path/to/file.kt", "line_number": 42, "message": "Error message", "error_type": "Compilation", "involved_symbols": ["com.example.Class"]}}]

JSON Output:
""" # The LLM should append the JSON list here

    def _build_prompt(self, raw_output: str) -> str:
        """Constructs the prompt for the LLM."""
        # Get context from config (could be cached)
        language = self.config.get('generation', {}).get('target_language', 'Kotlin')
        build_tool = self.config.get('build_system', {}).get('type', 'Gradle')
        test_framework = self.config.get('generation', {}).get('target_framework', 'JUnit5') # Simplified framework name

        # Limit raw output size to avoid excessive prompt length
        max_output_chars = 10000 # Configurable?
        if len(raw_output) > max_output_chars:
            logger.warning(f"Raw build output exceeds {max_output_chars} chars. Truncating for LLM parser.")
            # Truncate smartly - keep beginning and end
            raw_output_snippet = f"{raw_output[:max_output_chars // 2]}\n...\n{raw_output[-max_output_chars // 2:]}"
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
  "involved_symbols": ["com.example.Class"]
}}]

IMPORTANT: Your response MUST be a valid JSON array, not Kotlin code.
"""
            return fallback_template.format(raw_output=raw_output_snippet)

    def parse_output(self, raw_output: str) -> List[ParsedError]:
        """Parses raw build output using an LLM call."""
        if not raw_output:
            logger.info("Build output is empty. No errors to parse.")
            return []

        if "BUILD SUCCESSFUL" in raw_output:
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
                    # Try to extract information from the build output directly
                    import re

                    # Try to extract file paths
                    file_paths = re.findall(r'([\w./]+\.kt)', raw_output)
                    file_path = file_paths[0] if file_paths else None

                    # Try to extract class names from the source file
                    class_names = re.findall(r'class\s+([A-Z][\w]+)', raw_output)

                    # Try to extract import statements to find potential dependencies
                    imports = re.findall(r'import\s+([\w.]+)', raw_output)

                    # Try to extract error messages
                    error_messages = re.findall(r'error:\s*([^\n]+)', raw_output)
                    message = error_messages[0] if error_messages else "Failed to parse build output. LLM returned code instead of error analysis."

                    # Try to extract unresolved symbols from error messages
                    unresolved_symbols = re.findall(r'Unresolved reference: ([\w.]+)', raw_output)

                    # Try to extract missing imports from error messages
                    missing_imports = re.findall(r"Cannot access class '([\w.]+)'", raw_output)

                    # Add all extracted symbols to the involved symbols
                    involved_symbols = list(set(class_names + imports + unresolved_symbols + missing_imports))

                    # Filter out common words that are not likely to be symbols
                    common_words = ['Failed', 'Error', 'Exception', 'Warning', 'Info', 'Debug', 'Trace']
                    involved_symbols = [s for s in involved_symbols if s not in common_words]

                    # Create a ParsedError with the extracted information
                    return [ParsedError(
                        message=message,
                        error_type="Compilation",  # Assume compilation error as default
                        file_path=file_path,
                        involved_symbols=involved_symbols
                    )]

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
                        structured_errors.append(ParsedError(
                            file_path=item.get("file_path"),
                            line_number=int(line_num) if line_num is not None else None,
                            message=str(item.get("message", "")),
                            error_type=str(item.get("error_type", "Unknown")),
                            involved_symbols=item.get("involved_symbols", [])
                        ))
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
                        involved_symbols=[]
                    )]

                return structured_errors

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode LLM response as JSON: {e}")
                logger.error(f"LLM Response Text was:\n{response_text}")

                # Fallback: Try to extract some basic information from the build output
                # This ensures we can continue with the self-healing process
                import re

                # Try to extract file paths
                file_paths = re.findall(r'([\w./]+\.kt)', raw_output)
                file_path = file_paths[0] if file_paths else None

                # Try to extract class names
                class_names = re.findall(r'class\s+([A-Z][\w]+)', raw_output)

                # Try to extract error messages
                error_messages = re.findall(r'error:\s*([^\n]+)', raw_output)
                message = error_messages[0] if error_messages else "Failed to parse build output. See raw output for details."

                # Create a ParsedError with the extracted information
                return [ParsedError(
                    message=message,
                    error_type="Compilation",  # Assume compilation error as default
                    file_path=file_path,
                    involved_symbols=class_names
                )]
            except ValueError as e:
                 logger.error(f"LLM JSON response validation failed: {e}")
                 logger.error(f"LLM Response Text was:\n{response_text}")

                 # Fallback: Create a generic error
                 return [ParsedError(
                    message="Failed to validate error structure. See raw output for details.",
                    error_type="Unknown",
                    involved_symbols=[]
                 )]


        except Exception as e:
            logger.error(f"Error during LLM call for error parsing: {e}", exc_info=True)
            return [ParsedError(message=f"LLM call failed during error parsing: {e}")]