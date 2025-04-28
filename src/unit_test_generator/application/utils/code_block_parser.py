"""
Utility functions for parsing code blocks from LLM responses.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def parse_llm_code_block(response_text: str, language: str = "kotlin") -> Optional[str]:
    """
    Extracts code from a markdown code block.

    Args:
        response_text: The LLM response text
        language: The programming language

    Returns:
        The extracted code, or None if no code block is found
    """
    logger.debug("Parsing LLM response for code block...")
    if not response_text or not isinstance(response_text, str):
        logger.warning("Empty or non-string LLM response")
        return None

    response_text = response_text.strip()

    # Define possible start tags
    language_tag = f"```{language.lower()}"
    generic_tag = "```"
    possible_start_tags = [language_tag, generic_tag]
    end_tag = "```"

    # Try to find any of the start tags
    start_tag = None
    start_index = -1

    for tag in possible_start_tags:
        idx = response_text.find(tag)
        if idx != -1 and (start_index == -1 or idx < start_index):
            start_index = idx
            start_tag = tag

    # If we found a start tag
    if start_index != -1 and start_tag:
        # Find the end tag after the start tag
        content_start = start_index + len(start_tag)
        end_index = response_text.find(end_tag, content_start)

        if end_index != -1:
            # Extract the code between the tags
            code = response_text[content_start:end_index].strip()

            # Basic validation of the extracted code
            if code:
                logger.debug(f"Successfully extracted code block of {len(code)} characters")

                # Check for nested code blocks within the extracted code
                # This handles cases where the LLM includes markdown code blocks in the generated code
                nested_code_blocks = []
                nested_start_index = 0
                while True:
                    nested_start = code.find("```", nested_start_index)
                    if nested_start == -1:
                        break

                    nested_end = code.find("```", nested_start + 3)
                    if nested_end == -1:
                        break

                    # Extract the nested code block (without the backticks)
                    nested_block = code[nested_start:nested_end + 3]
                    nested_code_blocks.append(nested_block)
                    nested_start_index = nested_end + 3

                # Remove all nested code blocks
                for nested_block in nested_code_blocks:
                    code = code.replace(nested_block, "")

                # If we found and removed nested code blocks, log it
                if nested_code_blocks:
                    logger.info(f"Removed {len(nested_code_blocks)} nested code blocks from the generated code")

                return code
            else:
                logger.warning("LLM response contained an empty code block")
                return None
        else:
            logger.warning("Found start code tag but no end tag in LLM response")
            # Try to extract everything after the start tag as a fallback
            code = response_text[content_start:].strip()
            if code and len(code) > 50:  # Arbitrary minimum length for valid code
                logger.warning("Using partial code block (no end tag found)")
                return code
            return None

    # If no code block is found, check if the entire response might be valid code
    # This is a fallback for LLMs that might not format their response in code blocks
    if response_text and len(response_text) > 50:
        # Check for some basic indicators that this might be code
        if ("package " in response_text or "import " in response_text) and \
           ("class " in response_text or "fun " in response_text):
            logger.warning("No code block found, but response appears to be Kotlin code. Using entire response.")

            # Check for and remove any markdown code blocks in the raw response
            if "```" in response_text:
                logger.warning("Found code block markers in raw response, removing them")
                # Simple approach: remove all occurrences of ```
                cleaned_response = response_text.replace("```kotlin", "").replace("```", "")
                return cleaned_response.strip()

            return response_text

    logger.warning("Could not find valid code block in LLM response")
    return None
