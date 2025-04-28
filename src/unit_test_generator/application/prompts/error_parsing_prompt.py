# src/unit_test_generator/application/prompts/error_parsing_prompt.py
"""
Prompts for error parsing.
"""

def get_error_parsing_prompt() -> str:
    """
    Returns a prompt template for parsing build/test errors.
    """
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
