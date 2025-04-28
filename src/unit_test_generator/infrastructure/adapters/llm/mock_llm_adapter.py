import logging
import os
from typing import Dict, Any
from pathlib import Path

from unit_test_generator.domain.ports.llm_service import LLMServicePort

logger = logging.getLogger(__name__)

class MockLLMAdapter(LLMServicePort):
    """A mock LLM adapter for testing without API calls."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("MockLLMAdapter initialized.")

    def generate_tests(self, context_payload: Dict[str, Any]) -> str:
        """Generates a mock test response."""
        # Log files being added to context
        self._log_context_files(context_payload)

        prompt = self._build_prompt(context_payload) # Build prompt for logging/debugging
        logger.info(f"--- MockLLMAdapter: Received Context Payload ---")
        # Avoid logging potentially huge code snippets in production INFO logs
        # logger.info(json.dumps(context_payload, indent=2, default=str))
        logger.info(f"--- MockLLMAdapter: Built Prompt (first 500 chars) ---\n{prompt[:500]}...\n------------------------------------")

        # Mock token counting
        logger.info(f"Token count - Input: {len(prompt) // 4} (estimated)")

        target_file_path = context_payload.get("target_file_path", "UnknownTarget.kt")
        class_name = Path(target_file_path).stem
        test_class_name = f"{class_name}Test"
        language = self.config.get('generation', {}).get('target_language', 'Kotlin').lower()

        # Simulate a Kotlin test file based on the target
        mock_test_code = f"""
// Mock generated tests for {class_name}
// Target File: {target_file_path}
// Based on context including {len(context_payload.get('similar_files_with_tests', []))} similar file(s).

package com.example.generated // TODO: Infer package correctly

import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.*
// import io.mockk.* // Uncomment if mocking is needed

class {test_class_name} {{

    // TODO: Instantiate the class under test, potentially with mocks
    // private val service = {class_name}()

    @Test
    fun `mock test for {class_name}`() {{
        // Given
        println("Running mock test for {class_name}")
        val expected = true

        // When
        val actual = true // Placeholder logic

        // Then
        assertEquals(expected, actual, "This is a mock assertion.")
    }}

    // TODO: Add more tests based on public methods in {class_name}
    // TODO: Consider edge cases and different scenarios.
}}
        """
        # Wrap in markdown block like a real LLM might
        response = f"```{language}\n{mock_test_code.strip()}\n```"
        logger.info(f"--- MockLLMAdapter: Returning Mock Response ---")
        logger.debug(f"Response (first 500 chars): {response[:500]}...")

        # Mock token usage information
        input_tokens = len(prompt) // 4  # Rough estimate
        output_tokens = len(response) // 4  # Rough estimate
        logger.info(f"Token usage - Input: {input_tokens}, Output: {output_tokens}, Total: {input_tokens + output_tokens} (estimated)")

        # Return raw response with markdown code block intact
        return response

    def _build_prompt(self, context_payload: Dict[str, Any]) -> str:
        """Builds a detailed prompt for the LLM (used for logging/debugging mock)."""
        target_file_path = context_payload.get("target_file_path")
        target_file_content = context_payload.get("target_file_content")
        similar_files_info = context_payload.get("similar_files_with_tests", [])
        gen_config = self.config.get('generation', {})
        language = gen_config.get('target_language', 'Kotlin')
        framework = gen_config.get('target_framework', 'JUnit5 with MockK')

        prompt = f"You are an expert software engineer specializing in writing unit tests in {language} using {framework}.\n"
        prompt += f"Your task is to generate comprehensive and idiomatic unit tests for the target file provided below.\n\n"
        prompt += "CONTEXT:\n"
        prompt += "-------\n\n"
        prompt += f"Target file to test (`{target_file_path}`):\n"
        prompt += f"```{language.lower()}\n{target_file_content}\n```\n\n"

        if similar_files_info:
            prompt += "Reference examples from the same codebase (similar source files and their tests):\n\n"
            for i, similar_info in enumerate(similar_files_info):
                source_path = similar_info['source_file_path']
                source_content = similar_info['source_file_content']
                test_path = similar_info['test_file_path'] # Assuming one test file for simplicity in mock prompt
                test_content = similar_info['test_file_content']

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
            prompt += "Code for relevant imported classes from the project:\n\n"
            # Use target language for code block formatting
            lang_tag = context_payload.get("language", "kotlin").lower()

            for dep_info in dependency_files:
                dep_path = dep_info['dependency_path']
                dep_content = dep_info['content']
                prompt += f"Dependency File (`{dep_path}`):\n"
                prompt += f"```{lang_tag}\n{dep_content}\n```\n\n"

        prompt += "INSTRUCTIONS:\n"
        prompt += "------------\n"
        prompt += f"1. Write unit tests for the public methods and functionalities in the target file `{target_file_path}`.\n"
        prompt += f"2. Follow the testing conventions, structure, and style observed in the reference examples, if provided.\n"
        prompt += f"3. Use {framework} for assertions, mocking (if necessary), and test structure.\n"
        prompt += "4. Ensure tests cover typical use cases, edge cases (nulls, empty inputs, boundaries), and potential error conditions.\n"
        prompt += "5. Include necessary imports and package declarations.\n"
        prompt += "6. Output *only* the complete test file content within a single markdown code block (e.g., ```kotlin ... ```).\n\n"
        prompt += "Generated Test Code:\n"

        return prompt

    def _parse_response(self, response_text: str) -> str:
        """Extracts code from a markdown code block."""
        logger.debug("Parsing LLM response...")
        if "```" in response_text:
            parts = response_text.split("```", 2) # Split max 2 times
            if len(parts) > 1:
                code_block = parts[1]
                # Remove optional language tag from the first line
                if '\n' in code_block:
                    first_line, rest = code_block.split('\n', 1)
                    if first_line.strip().isalpha() and first_line.strip().islower():
                        logger.debug(f"Removed language tag '{first_line.strip()}'")
                        return rest.strip()
                return code_block.strip()
            else:
                logger.warning("Found '```' but couldn't parse code block structure.")
                return response_text.strip() # Fallback
        else:
            logger.debug("No markdown code block found, returning raw response.")
            return response_text.strip() # Assume plain code if no backticks

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