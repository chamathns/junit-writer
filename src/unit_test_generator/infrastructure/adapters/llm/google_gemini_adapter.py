import logging
import os
from typing import Dict, Any
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from pathlib import Path
import traceback
from datetime import datetime

from unit_test_generator.domain.ports.llm_service import LLMServicePort

logger = logging.getLogger(__name__)

class GoogleGeminiAdapter(LLMServicePort):
    """LLM service implementation using Google Gemini."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get('generation', {}).get('model_name', 'gemini-1.5-flash-latest')
        api_key = config.get('generation', {}).get('api_key') or os.environ.get("GOOGLE_API_KEY")

        if not api_key:
            logger.error("Google API Key not found in config or environment variable GOOGLE_API_KEY.")
            raise ValueError("Missing Google API Key for Gemini.")

        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Google Gemini Adapter initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to configure Google Generative AI: {e}", exc_info=True)
            raise RuntimeError(f"Could not initialize Google Gemini client: {e}") from e

    def generate_tests(self, context_payload: Dict[str, Any]) -> str:
        """Generates unit tests using the configured Gemini model."""
        # Log files being added to context
        self._log_context_files(context_payload)

        prompt = self._build_prompt(context_payload)
        logger.info(f"Sending request to Gemini model: {self.model_name}")
        logger.debug(f"Prompt (first 500 chars): {prompt[:500]}...")

        # Save the prompt to a file for debugging/analysis
        self._save_prompt_to_file(prompt, context_payload.get("task", "generate_tests"))

        # Count tokens before sending request
        try:
            token_count_response = self.model.count_tokens(prompt)
            logger.info(f"Token count - Input: {token_count_response.total_tokens}")
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}")

        # Configure generation parameters (optional)
        generation_config = genai.types.GenerationConfig(
            # temperature=0.7, # Example: Adjust creativity
            # max_output_tokens=8192 # Example: Set max output size
        )
        # Configure safety settings (important for code generation)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings,
                # stream=False # Use stream=True for large responses or progress indication
            )

            # Handle potential safety blocks or empty responses
            if not response.candidates:
                 # Check prompt feedback for block reason
                 block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
                 logger.error(f"Gemini request blocked. Reason: {block_reason}")
                 # You might want to inspect response.prompt_feedback further
                 return f"// Error: Generation blocked by safety filters. Reason: {block_reason}"

            generated_text = response.text
            logger.info("Received response from Gemini.")
            logger.debug(f"Response (first 500 chars): {generated_text[:500]}...")

            # Try to get token usage information
            try:
                usage_metadata = getattr(response, 'usage_metadata', None)
                if usage_metadata:
                    logger.info(f"Token usage - Input: {usage_metadata.prompt_token_count}, Output: {usage_metadata.candidates_token_count}, Total: {usage_metadata.total_token_count}")
            except Exception as e:
                logger.warning(f"Failed to get token usage information: {e}")

            # Return raw response with markdown code block intact
            return generated_text

        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google API Error during Gemini request: {e}", exc_info=True)
            return f"// Error: Google API Error - {e}"
        except Exception as e:
            logger.error(f"Unexpected error during Gemini request: {e}", exc_info=True)
            return f"// Error: Unexpected error generating tests - {e}"

    def _build_prompt(self, context_payload: Dict[str, Any]) -> str:
        """Builds the detailed prompt for the Gemini model."""
        # Initialize common variables
        target_file_path = context_payload.get("target_file_path")
        target_file_content = context_payload.get("target_file_content", "")
        similar_files_info = context_payload.get("similar_files_with_tests", [])
        gen_config = self.config.get('generation', {})
        language = gen_config.get('target_language', 'Kotlin')
        framework = gen_config.get('target_framework', 'JUnit5 with MockK')

        # Initialize token count and max tokens for context size tracking
        token_count = len(target_file_content) if target_file_content else 0  # Very rough estimate
        max_tokens = gen_config.get('context_max_tokens', 15000)

        # Check the task type
        task = context_payload.get("task", "generate_tests")
        update_mode = context_payload.get("update_mode", False)
        existing_test_file = context_payload.get("existing_test_file")
        existing_test_content = context_payload.get("existing_test_content")

        # Handle different task types with specialized prompts
        if task == "dependency_discovery":
            return self._build_dependency_discovery_prompt(context_payload)
        elif task == "diff_focused_test_generation":
            return self._build_diff_focused_prompt(context_payload)
        elif task == "parse_errors":
            # Use the prompt provided by the error parser
            if "prompt" in context_payload:
                logger.info("Using provided prompt for error parsing task")
                return context_payload["prompt"]
            else:
                logger.warning("No prompt provided for error parsing task. Using fallback prompt.")
                # Fallback prompt if none provided
                return self._build_error_parsing_fallback_prompt(context_payload)
        elif "current_test_code" in context_payload and "error_output" in context_payload:
            # --- Build FIX Prompt ---
            prompt = f"You are an expert software engineer debugging unit tests...\n"
            prompt += f"The following unit test file (`{target_file_path.replace('main', 'test') if target_file_path else 'N/A'}Test.kt`) failed.\n\n"  # Adjust test path logic
            prompt += f"Source Code Under Test (`{target_file_path}`):\n"
            prompt += f"```{context_payload.get('language', 'kotlin').lower()}\n{target_file_content}\n```\n\n"
            prompt += f"Current Failing Test Code:\n"
            prompt += f"```{context_payload.get('language', 'kotlin').lower()}\n{context_payload.get('current_test_code')}\n```\n\n"
            prompt += f"Errors Encountered:\n{context_payload.get('error_output')}\n\n"
            prompt += "INSTRUCTIONS:\n"
            prompt += "1. Analyze the errors and the provided source and test code.\n"
            prompt += "2. Identify the root cause of the failure(s).\n"
            prompt += "3. Provide a corrected version of the *entire* test file.\n"
            prompt += "4. Ensure the corrected code is complete, includes necessary imports, and addresses the reported errors.\n"
            prompt += f"5. Use the {context_payload.get('framework', 'JUnit5 with MockK')} framework correctly.\n"
            prompt += f"6. Output *only* the complete corrected test file content within a single markdown code block (```{context_payload.get('language', 'kotlin').lower()} ... ```).\n\n"
            prompt += "Corrected Test Code:\n"
        elif update_mode and existing_test_content:
            # --- Build UPDATE Prompt ---
            prompt = f"You are an expert software engineer specializing in updating unit tests in {language} using {framework}.\n"
            prompt += f"Your task is to update an existing test file to align with changes in the source file.\n\n"
            prompt += "CONTEXT:\n"
            prompt += "-------\n\n"
            prompt += f"Target file to test (`{target_file_path}`):\n"
            prompt += f"```{language.lower()}\n{target_file_content}\n```\n\n"
            prompt += f"Existing test file (`{existing_test_file}`):\n"
            prompt += f"```{language.lower()}\n{existing_test_content}\n```\n\n"

            # Include any custom instructions from the context payload
            if "instruction" in context_payload:
                prompt += f"SPECIFIC INSTRUCTIONS:\n{context_payload['instruction']}\n\n"

            # Add detailed instructions for updating the test file
            prompt += "INSTRUCTIONS:\n"
            prompt += "------------\n"
            prompt += "1. Analyze both the source file and the existing test file carefully.\n"
            prompt += "2. Identify what has changed in the source file that requires test updates.\n"
            prompt += "3. Update the existing test file to cover the changes in the source file.\n"
            prompt += "4. Preserve existing test methods and functionality where possible.\n"
            prompt += "5. Add new test methods only for new or modified functionality in the source file.\n"
            prompt += "6. Ensure the updated test file maintains the same structure, style, and naming conventions as the existing one.\n"
            prompt += "7. Do not remove existing tests unless they are no longer applicable due to removed functionality.\n"
            prompt += "8. If you need to modify an existing test, try to keep the changes minimal and focused on the affected parts.\n"
            prompt += "9. Make sure all imports are correctly updated if new classes or methods are used.\n"
            prompt += f"10. Output *only* the complete updated test file content within a single markdown code block starting with ```{language.lower()} and ending with ```.\n\n"
            prompt += "Updated Test Code:\n"
        else:
            # --- Build GENERATION Prompt ---
            prompt = f"You are an expert software engineer specializing in writing unit tests in {language} using {framework}.\n"
            prompt += f"Your task is to generate comprehensive and idiomatic unit tests for the target file provided below.\n\n"
            prompt += "CONTEXT:\n"
            prompt += "-------\n\n"
            prompt += f"Target file to test (`{target_file_path}`):\n"
            prompt += f"```{language.lower()}\n{target_file_content}\n```\n\n"

        if similar_files_info:
            prompt += "Reference examples from the same codebase (similar source files and their tests):\n\n"
            # Limit context size to avoid exceeding model limits

            for i, similar_info in enumerate(similar_files_info):
                source_path = similar_info['source_file_path']
                source_content = similar_info['source_file_content']
                test_path = similar_info['test_file_path'] # Assuming one test file per entry for simplicity
                test_content = similar_info['test_file_content']

                # Estimate token increase and check limit
                added_tokens = len(source_content) + len(test_content)
                if token_count + added_tokens > max_tokens:
                    logger.warning(f"Context limit reached. Skipping remaining {len(similar_files_info) - i} similar examples.")
                    break
                token_count += added_tokens

                prompt += f"Example {i+1}:\n"
                prompt += f"  Similar Source File (`{source_path}`):\n"
                prompt += f"  ```{language.lower()}\n{source_content}\n```\n"
                prompt += f"  Corresponding Unit Test File (`{test_path}`):\n"
                prompt += f"  ```{language.lower()}\n{test_content}\n```\n\n"

        # Add dependency files if available
        dependency_files = context_payload.get("dependency_files", [])
        if dependency_files:
            prompt += "Relevant dependency files from the codebase:\n\n"
            for i, dep_file in enumerate(dependency_files):
                dep_path = dep_file.get('file_path')
                dep_content = dep_file.get('content')
                dep_relevance = dep_file.get('relevance', 'Unknown')

                # Skip if no content
                if not dep_content:
                    continue

                # Estimate token increase and check limit
                added_tokens = len(dep_content)
                if token_count + added_tokens > max_tokens:
                    logger.warning(f"Context limit reached. Skipping remaining {len(dependency_files) - i} dependency files.")
                    break
                token_count += added_tokens

                prompt += f"Dependency {i+1} (`{dep_path}`, relevance: {dep_relevance}):\n"
                prompt += f"```{language.lower()}\n{dep_content}\n```\n\n"

        # Add custom instructions if provided
        if "instruction" in context_payload and not update_mode:
            prompt += f"SPECIFIC INSTRUCTIONS:\n{context_payload['instruction']}\n\n"

        # Add standard instructions if not already added (for generation mode)
        if not update_mode and not "current_test_code" in context_payload:
            prompt += "INSTRUCTIONS:\n"
            prompt += "------------\n"
            prompt += f"1. Write complete, runnable unit tests for the public methods and functionalities in the target file `{target_file_path}`. Do not attempt to write tests for private methods.\n"
            prompt += "2. Strictly follow the testing conventions, structure (package, imports, class annotations), and style observed in the reference examples, if provided. Match the import style and library usage (e.g., MockK vs Mockito).\n"
            prompt += f"3. Use {framework} for assertions, mocking (if necessary), and test structure (e.g., `@Test`, `@BeforeEach`).\n"
            prompt += "4. Ensure tests cover typical use cases, edge cases (nulls, empty inputs, boundaries), and potential error conditions.\n"
            prompt += "5. Infer the correct package declaration for the test file based on the target file's path and project conventions.\n"
            prompt += "6. Include all necessary imports, especially for DTO classes and models.\n"
            prompt += "7. Pay close attention to mocking dependencies if the target class has collaborators. Use MockK if seen in examples.\n"
            prompt += "8. Make sure to properly handle DTO classes in your tests - use appropriate constructors or builder patterns if available.\n"
            prompt += "9. For any DTO or model classes, ensure you create valid test instances with all required fields.\n"
            prompt += f"10. Output *only* the complete test file content within a single markdown code block starting with ```{language.lower()} and ending with ```. Do not include any explanations or introductory text outside the code block.\n\n"
            prompt += "Generated Test Code:\n"
            # No need to add ``` here, the model should add it based on instructions

        return prompt

    def _build_error_parsing_fallback_prompt(self, context_payload: Dict[str, Any]) -> str:
        """Builds a fallback prompt for error parsing when none is provided."""
        language = context_payload.get("language", self.config.get('generation', {}).get('target_language', 'Kotlin'))
        build_tool = context_payload.get("build_tool", "Gradle")
        test_framework = context_payload.get("framework", self.config.get('generation', {}).get('target_framework', 'JUnit5'))
        raw_output = context_payload.get("raw_output", "")

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

        prompt = f"""You are an expert build log analyzer for {language} projects using {build_tool} and {test_framework}.
Your task is to meticulously analyze the provided build/test output and extract structured information about any errors found (compilation errors, test failures, runtime exceptions during tests, or general build failures).

Input Build/Test Output:
------------------------
{raw_output_snippet}
------------------------

For each error found, extract the following information:
1. file_path: The path to the file where the error occurred (if available)
2. line_number: The line number where the error occurred (if available)
3. message: The error message
4. error_type: The type of error (e.g., 'Compilation', 'TestFailure', 'Runtime', 'BuildFailure')
5. error_category: A more specific categorization of the error (e.g., 'UnresolvedReference', 'TypeMismatch', 'AssertionFailure')
6. involved_symbols: A list of symbols (classes, methods, variables) involved in the error
7. suggested_fix_approach: A brief suggestion on how to fix the error

IMPORTANT: Your response MUST be a valid JSON array, not Kotlin code or any other format. For example: [{{"file_path": "path/to/file.kt", "line_number": 42, "message": "Error message", "error_type": "Compilation", "error_category": "UnresolvedReference", "involved_symbols": ["com.example.Class"], "suggested_fix_approach": "Add missing import for com.example.Class"}}]

JSON Output:
"""

        return prompt

    def _build_dependency_discovery_prompt(self, context_payload: Dict[str, Any]) -> str:
        """Builds a prompt for dependency discovery."""
        source_file_path = context_payload.get("source_file_path")
        source_content = context_payload.get("source_content")
        imports = context_payload.get("imports", [])
        package = context_payload.get("package", "")
        language = context_payload.get("language", "Kotlin")

        prompt = f"You are an expert software engineer specializing in {language} development.\n"
        prompt += "Your task is to analyze a source file and identify all dependencies needed for writing comprehensive unit tests.\n\n"

        prompt += f"Source File (`{source_file_path}`):\n"
        prompt += f"```{language.lower()}\n{source_content}\n```\n\n"

        if package:
            prompt += f"Source file package: {package}\n\n"

        if imports:
            prompt += "Imports found in the file:\n"
            for imp in imports:
                prompt += f"- {imp}\n"
            prompt += "\n"

        prompt += "INSTRUCTIONS:\n"
        prompt += "------------\n"
        prompt += "1. Analyze the source file and identify all dependencies that would be needed to write comprehensive unit tests.\n"
        prompt += "2. Focus on identifying:\n"
        prompt += "   - Classes/interfaces that are extended or implemented\n"
        prompt += "   - External services or components that are used\n"
        prompt += "   - DTOs, models, or other data structures used in method signatures\n"
        prompt += "   - Utility classes that might be needed\n"
        prompt += "3. For each dependency, provide:\n"
        prompt += "   - The fully qualified name (with package)\n"
        prompt += "   - A relevance score from 0.0 to 1.0 (where 1.0 is highest relevance)\n"
        prompt += "   - A brief explanation of why this dependency is needed for testing\n\n"
        prompt += "OUTPUT FORMAT:\n"
        prompt += "-------------\n"
        prompt += "Return a JSON array of dependency objects with the following structure:\n"
        prompt += "[\n"
        prompt += "  {\n"
        prompt += "    \"name\": \"fully.qualified.ClassName\",\n"
        prompt += "    \"relevance\": 0.9,\n"
        prompt += "    \"reason\": \"Used as a parameter in method X\"\n"
        prompt += "  },\n"
        prompt += "  ...\n"
        prompt += "]\n\n"

        # Add examples if available
        if "example_dependencies" in context_payload:
            prompt += "EXAMPLES:\n"
            prompt += "--------\n"
            for dep in context_payload["example_dependencies"]:
                prompt += f"{dep['name']}: {dep['relevance']} ({dep['reason']})\n"
            prompt += "\n"
        else:
            # Generic examples
            prompt += "EXAMPLES:\n"
            prompt += "--------\n"
            if language.lower() == "kotlin":
                # Kotlin-specific examples
                prompt += "org.example.service.UserService: 1.0 (Primary dependency, needs to be mocked in tests)\n"
                prompt += "org.example.model.UserDTO: 0.9 (Used in method parameters and return values)\n"
                prompt += "org.example.util.DateFormatter: 0.7 (Used for formatting dates in the class)\n"
                prompt += "org.example.config.AppConfig: 0.5 (Might be needed for configuration values)\n"
            else:
                # Generic examples
                prompt += "com.example.SomeDTO: 1.0 (Critical for testing, used in method parameters)\n"
                prompt += "com.example.SomeService: 0.9 (Needs to be mocked in tests)\n"
        prompt += "...and so on\n\n"
        prompt += "Make sure to include the FULL package path for each dependency.\n"
        prompt += "Focus on dependencies from the same codebase, especially from the same package.\n"

        return prompt

    def _build_diff_focused_prompt(self, context_payload: Dict[str, Any]) -> str:
        """Builds a prompt for diff-focused test generation."""
        # Get the prompt template from the context payload
        prompt_template = context_payload.get("prompt_template", "")

        # If no template is provided, use a default template
        if not prompt_template:
            if context_payload.get("update_mode", False):
                from unit_test_generator.application.prompts.diff_focused_test_prompt import get_diff_focused_test_update_prompt
                prompt_template = get_diff_focused_test_update_prompt()
            else:
                from unit_test_generator.application.prompts.diff_focused_test_prompt import get_diff_focused_test_generation_prompt
                prompt_template = get_diff_focused_test_generation_prompt()

        # Add optimization instructions if needed
        optimization_instructions = ""
        if self.config.get('generation', {}).get('optimize_for_readability', False):
            optimization_instructions = "\n11. Optimize the tests for readability and maintainability. Use clear variable names and add comments where necessary."

        # Format the prompt template with the context payload
        prompt = prompt_template.format(
            target_file_content=context_payload.get("target_file_content", ""),
            diff_content=context_payload.get("diff_content", ""),
            added_code_blocks=context_payload.get("added_code_blocks", "No added code blocks."),
            modified_code_blocks=context_payload.get("modified_code_blocks", "No modified code blocks."),
            new_imports=context_payload.get("new_imports", "No new imports."),
            existing_test_code=context_payload.get("existing_test_code", ""),
            optimization_instructions=optimization_instructions
        )

        return prompt

    def _parse_response(self, response_text: str) -> str:
        """Extracts code from a markdown code block."""
        logger.debug("Parsing LLM response...")
        # Handle potential leading/trailing whitespace and find the first code block
        response_text = response_text.strip()
        start_tag = f"```{self.config.get('generation', {}).get('target_language', 'Kotlin').lower()}"
        end_tag = "```"

        start_index = response_text.find(start_tag)
        if start_index != -1:
            # Find the end tag *after* the start tag
            end_index = response_text.find(end_tag, start_index + len(start_tag))
            if end_index != -1:
                code = response_text[start_index + len(start_tag):end_index].strip()
                logger.debug("Extracted code block.")
                return code
            else:
                # Found start tag but no end tag, maybe truncated? Return what's after start tag.
                logger.warning("Found start code tag but no end tag. Returning partial content.")
                return response_text[start_index + len(start_tag):].strip()
        elif response_text.startswith("```") and response_text.endswith("```"):
             # Handle generic ``` block if specific language tag wasn't found/used
             parts = response_text.split("```", 2)
             if len(parts) > 1:
                 code_block = parts[1]
                 # Check if the first line might be a language tag
                 lines = code_block.split("\n", 1)
                 if len(lines) > 1 and lines[0].strip() in ["kotlin", "java", "python", "typescript", "javascript"]:
                     return lines[1].strip()
                 return code_block.strip()

        # No code block found, return as is (might be JSON or other format)
        logger.debug("No code block found in response. Returning raw text.")
        return response_text

    def _log_context_files(self, context_payload: Dict[str, Any]) -> None:
        """Logs information about files included in the context."""
        # Log target file
        target_file = context_payload.get("target_file_path")
        if target_file:
            logger.info(f"Target file: {target_file}")

        # Log similar files
        similar_files = context_payload.get("similar_files_with_tests", [])
        if similar_files:
            logger.info(f"Including {len(similar_files)} similar files in context")
            for i, file_info in enumerate(similar_files):
                logger.debug(f"Similar file {i+1}: {file_info.get('source_file_path')} with test {file_info.get('test_file_path')}")

        # Log dependency files
        dependency_files = context_payload.get("dependency_files", [])
        if dependency_files:
            logger.info(f"Including {len(dependency_files)} dependency files in context")
            for i, file_info in enumerate(dependency_files):
                logger.debug(f"Dependency {i+1}: {file_info.get('file_path')} (relevance: {file_info.get('relevance', 'Unknown')})")

    def _save_prompt_to_file(self, prompt: str, task_type: str) -> None:
        """Saves the prompt to a file for debugging and analysis."""
        try:
            # Import required modules
            import os
            import traceback
            from datetime import datetime

            # Try to get the repository root
            repo_root = self.config.get('repository', {}).get('root_path')
            if not repo_root:
                # Try to infer from current working directory
                repo_root = os.getcwd()
                logger.debug(f"Repository root not specified in config, using current directory: {repo_root}")

            # Create absolute paths
            prompts_dir = os.path.join(repo_root, "var", "prompts")
            temp_file = os.path.join(repo_root, "temp_llm_query.txt")

            # Create directory if it doesn't exist
            os.makedirs(prompts_dir, exist_ok=True)
            logger.info(f"Created/verified prompts directory: {prompts_dir}")

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(prompts_dir, f"{task_type}_{timestamp}.txt")

            # Write prompt to file
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(prompt)
                logger.info(f"Saved prompt to file: {filename}")
            except Exception as file_error:
                logger.error(f"Error writing to {filename}: {file_error}\n{traceback.format_exc()}")
                # Try writing to temp file as fallback
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(prompt)
                logger.info(f"Saved prompt to temp file: {temp_file}")

        except Exception as e:
            logger.error(f"Failed to save prompt to file: {e}")

            # Last resort: try to save to /tmp
            try:
                # Try to save to /tmp directory which should be writable
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                tmp_filename = f"/tmp/{task_type}_{timestamp}.txt"

                with open(tmp_filename, "w", encoding="utf-8") as f:
                    f.write(prompt)
                logger.info(f"Saved prompt to fallback location: {tmp_filename}")
            except Exception as tmp_error:
                logger.error(f"Failed to save prompt to fallback location: {tmp_error}")
