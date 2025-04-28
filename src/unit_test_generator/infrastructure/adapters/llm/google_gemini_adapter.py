import logging
import os
from typing import Dict, Any
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from pathlib import Path

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
        target_file_content = context_payload.get("target_file_content")
        similar_files_info = context_payload.get("similar_files_with_tests", [])
        gen_config = self.config.get('generation', {})
        language = gen_config.get('target_language', 'Kotlin')
        framework = gen_config.get('target_framework', 'JUnit5 with MockK')

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
            token_count = len(target_file_content) # Very rough estimate
            max_tokens = gen_config.get('context_max_tokens', 15000)

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
        else:
            prompt += "No similar files with existing tests were found for reference.\n"
            prompt += f"Please generate tests based solely on the target file's content and general best practices for {language} with {framework}.\n\n"

        # Include Dependency Files
        dependency_files = context_payload.get("dependency_files", [])
        if dependency_files:
            # Separate DTOs from other dependencies for better organization
            dto_files = [dep for dep in dependency_files if dep.get('is_dto', False)]
            other_deps = [dep for dep in dependency_files if not dep.get('is_dto', False)]

            # Use target language for code block formatting
            lang_tag = context_payload.get("language", "kotlin").lower()

            # First show DTO and model classes (important for test structure)
            if dto_files:
                prompt += "DTO and Model Classes (important for test structure):\n\n"
                for dep_info in dto_files:
                    dep_path = dep_info['dependency_path']
                    dep_content = dep_info['content']
                    prompt += f"DTO/Model (`{dep_path}`):\n"
                    prompt += f"```{lang_tag}\n{dep_content}\n```\n\n"

            # Then show other dependencies
            if other_deps:
                prompt += "Other relevant imported classes from the project:\n\n"
                for dep_info in other_deps:
                    dep_path = dep_info['dependency_path']
                    dep_content = dep_info['content']
                    prompt += f"Dependency (`{dep_path}`):\n"
                    prompt += f"```{lang_tag}\n{dep_content}\n```\n\n"

        prompt += "INSTRUCTIONS:\n"
        prompt += "------------\n"
        prompt += (f"1. Write complete, runnable unit tests for the public methods and functionalities in the target file `{target_file_path}`. Do not attempt to write tests for private methods.\n")
        prompt += f"2. Strictly follow the testing conventions, structure (package, imports, class annotations), and style observed in the reference examples, if provided. Match the import style and library usage (e.g., MockK vs Mockito).\n"
        prompt += f"3. Use {framework} for assertions, mocking (if necessary), and test structure (e.g., `@Test`, `@BeforeEach`).\n"
        prompt += "4. Ensure tests cover typical use cases, edge cases (nulls, empty inputs, boundaries), and potential error conditions.\n"
        prompt += "5. Infer the correct package declaration for the test file based on the target file's path and project conventions.\n"
        prompt += "6. Include all necessary imports, especially for DTO classes and models.\n"
        prompt += "7. Pay close attention to mocking dependencies if the target class has collaborators. Use MockK if seen in examples.\n"
        prompt += "8. Make sure to properly handle DTO classes in your tests - use appropriate constructors or builder patterns if available.\n"
        prompt += "9. For any DTO or model classes, ensure you create valid test instances with all required fields.\n"
        prompt += "10. Output *only* the complete test file content within a single markdown code block starting with ```{language.lower()} and ending with ```. Do not include any explanations or introductory text outside the code block.\n\n"
        prompt += "Generated Test Code:\n"
        # No need to add ``` here, the model should add it based on instructions

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

        # Check if we should skip similar test search and dependency search
        skip_similar_test_search = context_payload.get("skip_similar_test_search", False)
        skip_dependency_search = context_payload.get("skip_dependency_search", False)

        # Add optimization instructions if needed
        optimization_instructions = ""
        if skip_similar_test_search or skip_dependency_search:
            optimization_instructions += "\nOPTIMIZATION INSTRUCTIONS:\n"
            if skip_similar_test_search:
                optimization_instructions += "- Skip similar test search as no new imports were added.\n"
            if skip_dependency_search:
                optimization_instructions += "- Skip dependency search as no new imports were added.\n"

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
        prompt += "1. Analyze the source code and identify all dependencies that would be needed for testing.\n"
        prompt += "2. Focus on identifying:\n"
        prompt += "   - DTO classes and models used in the code (especially in method parameters and return types)\n"
        prompt += "   - Service classes that might need to be mocked\n"
        prompt += "   - Repository classes that need to be mocked\n"
        prompt += "   - Utility classes that might be needed\n"
        prompt += "   - Any other dependencies critical for testing\n"
        prompt += "3. For Kotlin specifically, pay attention to:\n"
        prompt += "   - Classes used in constructor parameters\n"
        prompt += "   - Classes used with dependency injection (e.g., @Autowired, @Inject)\n"
        prompt += "   - Extension functions that might be used\n"
        prompt += "   - Companion object references\n"
        prompt += "4. For each dependency, assign an importance score (0.0-1.0) where 1.0 is most important.\n"
        prompt += "5. Return your analysis in the following format:\n\n"
        prompt += "DEPENDENCIES:\n"

        # Add examples based on the actual imports to guide the model
        if imports:
            # Find a few imports that look like they might be from the same codebase
            repo_imports = [imp for imp in imports if not (imp.startswith("java.") or imp.startswith("kotlin.") or imp.startswith("org.springframework."))]
            if repo_imports:
                for i, imp in enumerate(repo_imports[:3]):
                    if ".dto." in imp.lower() or imp.endswith("DTO"):
                        prompt += f"{imp}: 1.0 (Critical DTO class used in the code)\n"
                    elif ".repository." in imp.lower() or imp.endswith("Repository"):
                        prompt += f"{imp}: 0.9 (Repository that needs to be mocked)\n"
                    elif ".service." in imp.lower() or imp.endswith("Service"):
                        prompt += f"{imp}: 0.9 (Service that needs to be mocked)\n"
                    else:
                        prompt += f"{imp}: 0.8 (Used in the code)\n"
            else:
                # Generic examples
                prompt += "com.example.SomeDTO: 1.0 (Critical for testing, used in method parameters)\n"
                prompt += "com.example.SomeService: 0.9 (Needs to be mocked in tests)\n"
        else:
            # Generic examples
            prompt += "com.example.SomeDTO: 1.0 (Critical for testing, used in method parameters)\n"
            prompt += "com.example.SomeService: 0.9 (Needs to be mocked in tests)\n"

        prompt += "...and so on\n\n"
        prompt += "Make sure to include the FULL package path for each dependency.\n"
        prompt += "Focus on dependencies from the same codebase, especially from the same package.\n"

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
                 # Remove optional language tag from the first line
                 if '\n' in code_block:
                     first_line, rest = code_block.split('\n', 1)
                     if first_line.strip().isalpha() and first_line.strip().islower():
                         logger.debug(f"Removed language tag '{first_line.strip()}' from generic block")
                         return rest.strip()
                 return code_block.strip()

        logger.warning("Could not find expected markdown code block. Returning raw response.")
        return response_text # Assume plain code if no block found

    def _log_context_files(self, context_payload: Dict[str, Any]) -> None:
        """Logs information about files being added to the context."""
        # Log target file
        target_file_path = context_payload.get("target_file_path")
        if target_file_path:
            logger.info(f"Adding target file to context: {target_file_path}")

        # Log similar files
        similar_files = context_payload.get("similar_files_with_tests", [])
        if similar_files:
            logger.info(f"Adding {len(similar_files)} similar files to context:")
            for i, similar_info in enumerate(similar_files):
                source_path = similar_info.get('source_file_path', 'unknown')
                test_path = similar_info.get('test_file_path', 'unknown')
                logger.info(f"  Similar file {i+1}: {source_path} with test {test_path}")

        # Log dependency files
        dependency_files = context_payload.get("dependency_files", [])
        if dependency_files:
            logger.info(f"Adding {len(dependency_files)} dependency files to context:")
            for i, dep_info in enumerate(dependency_files):
                dep_path = dep_info.get('dependency_path', 'unknown')
                logger.info(f"  Dependency file {i+1}: {dep_path}")

    def _save_prompt_to_file(self, prompt: str, task_type: str):
        """Saves the prompt to a file for debugging and analysis."""
        try:
            import os
            import traceback
            from datetime import datetime
            from pathlib import Path

            # Get the repository root directory from config
            repo_root = self.config.get('repository', {}).get('root_path', '')
            if not repo_root:
                logger.warning("Repository root path not found in config, using current directory")
                repo_root = os.getcwd()

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

            # Also save to temp_llm_query.txt for easy access
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(prompt)
                logger.info(f"Saved prompt to temp file: {temp_file}")
            except Exception as temp_error:
                logger.error(f"Error writing to temp file: {temp_error}\n{traceback.format_exc()}")

        except Exception as e:
            logger.error(f"Failed to save prompt to file: {e}\n{traceback.format_exc()}")

            # Last resort: try to save to /tmp
            try:
                import os
                from datetime import datetime

                # Try to save to /tmp directory which should be writable
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                tmp_filename = f"/tmp/{task_type}_{timestamp}.txt"

                with open(tmp_filename, "w", encoding="utf-8") as f:
                    f.write(prompt)
                logger.info(f"Saved prompt to fallback location: {tmp_filename}")
            except Exception as tmp_error:
                logger.error(f"Failed to save prompt to fallback location: {tmp_error}")
