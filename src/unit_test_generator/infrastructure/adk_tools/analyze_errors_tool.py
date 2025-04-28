"""
ADK Tool for analyzing errors in depth using LLM.
"""
import logging
import json
from typing import Dict, Any, List

from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.error_parser import ErrorParserPort
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class AnalyzeErrorsTool(JUnitWriterTool):
    """Tool for analyzing errors in depth using LLM."""

    def __init__(self, llm_service: LLMServicePort, error_parser: ErrorParserPort, config: Dict[str, Any]):
        """
        Initialize the AnalyzeErrorsTool.

        Args:
            llm_service: An implementation of LLMServicePort
            error_parser: An implementation of ErrorParserPort
            config: Application configuration
        """
        super().__init__(
            name="analyze_errors",
            description="Analyzes errors in depth using LLM to understand root causes and potential fixes."
        )
        self.llm_service = llm_service
        self.error_parser = error_parser
        self.config = config

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to analyze errors.

        Args:
            parameters: Dictionary containing:
                - raw_error_output: Raw output from the build system
                - errors: List of parsed errors (optional)
                - test_file_path: Path to the test file
                - test_code: Content of the test file
                - target_file_path: Path to the target file
                - target_file_content: Content of the target file

        Returns:
            Dictionary containing:
                - analysis: Detailed analysis of errors
                - success: Boolean indicating if analysis was successful
        """
        # Extract parameters
        raw_error_output = parameters.get("raw_error_output", "")
        errors = parameters.get("errors", [])
        test_file_path = parameters.get("test_file_path")
        test_code = parameters.get("test_code")
        target_file_path = parameters.get("target_file_path")
        target_file_content = parameters.get("target_file_content")

        # Check required parameters
        if not raw_error_output and not errors:
            raise ValueError("Missing required parameter: either raw_error_output or errors must be provided")
        if not test_file_path or not test_code:
            raise ValueError("Missing required parameters: test_file_path and test_code")
        if not target_file_path or not target_file_content:
            raise ValueError("Missing required parameters: target_file_path and target_file_content")

        # If we don't have parsed errors but have raw output, parse it
        if not errors and raw_error_output:
            try:
                parsed_errors = self.error_parser.parse_output(raw_error_output)
                errors = []
                for error in parsed_errors:
                    errors.append({
                        "file_path": error.file_path,
                        "line_number": error.line_number,
                        "message": error.message,
                        "error_type": error.error_type,
                        "involved_symbols": error.involved_symbols
                    })
                logger.info(f"Parsed {len(errors)} errors from raw output")
            except Exception as e:
                logger.error(f"Error parsing raw output: {e}", exc_info=True)

        # Build the prompt for the LLM
        prompt = self._build_prompt(
            raw_error_output=raw_error_output,
            errors=errors,
            test_file_path=test_file_path,
            test_code=test_code,
            target_file_path=target_file_path,
            target_file_content=target_file_content
        )

        # Call the LLM service
        try:
            context = {
                "prompt": prompt,
                "task": "analyze_errors",
                "language": self.config.get('generation', {}).get('target_language', 'Kotlin'),
                "framework": self.config.get('generation', {}).get('target_framework', 'JUnit5'),
                "response_format": "json"
            }

            logger.info("Requesting error analysis from LLM")
            response_text = self.llm_service.generate_tests(context)

            if not response_text:
                logger.error("LLM returned empty response for error analysis")
                return {
                    "success": False,
                    "message": "LLM returned empty response for error analysis",
                    "analysis": {}
                }

            # Parse the LLM response
            try:
                analysis = json.loads(response_text)
                logger.info("Successfully parsed LLM response as JSON")
                return {
                    "success": True,
                    "analysis": analysis
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode LLM response as JSON: {e}")
                logger.error(f"LLM Response Text was:\n{response_text}")
                
                # Try to extract some basic information from the response
                return {
                    "success": False,
                    "message": f"Failed to decode LLM response as JSON: {e}",
                    "analysis": {
                        "raw_response": response_text,
                        "errors": errors
                    }
                }

        except Exception as e:
            logger.error(f"Error during LLM call for error analysis: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error during LLM call for error analysis: {e}",
                "analysis": {
                    "errors": errors
                }
            }

    def _build_prompt(self, raw_error_output: str, errors: List[Dict[str, Any]],
                     test_file_path: str, test_code: str,
                     target_file_path: str, target_file_content: str) -> str:
        """
        Build the prompt for the LLM.

        Args:
            raw_error_output: Raw output from the build system
            errors: List of parsed errors
            test_file_path: Path to the test file
            test_code: Content of the test file
            target_file_path: Path to the target file
            target_file_content: Content of the target file

        Returns:
            Prompt for the LLM
        """
        prompt = f"""
You are an expert Kotlin developer specializing in JUnit5 and MockK testing.

I need your help to analyze errors in a test file. Please provide a detailed analysis of the errors, including:
1. Root causes of each error
2. Missing dependencies or imports
3. Incorrect test setup or assertions
4. Potential fixes for each error

Here is the information:

# Test File Path
{test_file_path}

# Test Code
```kotlin
{test_code}
```

# Target File Path (file being tested)
{target_file_path}

# Target File Content
```kotlin
{target_file_content}
```

"""

        # Add parsed errors if available
        if errors:
            prompt += "\n# Parsed Errors\n"
            for i, error in enumerate(errors):
                prompt += f"## Error {i+1}\n"
                prompt += f"- File: {error.get('file_path', 'Unknown')}\n"
                prompt += f"- Line: {error.get('line_number', 'Unknown')}\n"
                prompt += f"- Type: {error.get('error_type', 'Unknown')}\n"
                prompt += f"- Message: {error.get('message', 'Unknown')}\n"
                
                if error.get('involved_symbols'):
                    prompt += f"- Involved Symbols: {', '.join(error.get('involved_symbols', []))}\n"
                
                prompt += "\n"

        # Add raw error output
        if raw_error_output:
            prompt += "\n# Raw Build/Test Output\n"
            prompt += "```\n"
            prompt += raw_error_output
            prompt += "\n```\n"

        # Add instructions for the response format
        prompt += """
# Response Format
Please provide your analysis in JSON format with the following structure:
```json
{
  "root_causes": [
    {
      "description": "Detailed description of the root cause",
      "severity": "HIGH|MEDIUM|LOW",
      "related_code": "Specific code snippet causing the issue"
    }
  ],
  "missing_dependencies": [
    {
      "type": "IMPORT|CLASS|FUNCTION|PROPERTY",
      "name": "Name of the missing dependency",
      "package": "Package where it should be imported from",
      "importance": "HIGH|MEDIUM|LOW"
    }
  ],
  "test_issues": [
    {
      "type": "SETUP|ASSERTION|MOCK|OTHER",
      "description": "Description of the issue",
      "line_number": 123,
      "code_snippet": "Problematic code snippet"
    }
  ],
  "recommended_fixes": [
    {
      "description": "Description of the fix",
      "code_before": "Code before the fix",
      "code_after": "Code after the fix",
      "confidence": "HIGH|MEDIUM|LOW"
    }
  ],
  "summary": "Overall summary of the issues and recommended approach"
}
```

Focus on providing actionable insights that will help fix the test.
"""

        return prompt
