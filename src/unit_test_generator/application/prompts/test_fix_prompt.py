# src/unit_test_generator/application/prompts/test_fix_prompt.py
"""
Prompts for generating test fixes.
"""

def get_single_error_analysis_prompt() -> str:
    """
    Returns a prompt template for analyzing a single error.
    """
    return """You are an expert Kotlin developer specializing in JUnit5 and MockK for testing.
Your task is to analyze a specific error in a failing test and provide a detailed fix recommendation.

## Source File Being Tested
```kotlin
{target_file_content}
```

## Current Test Code (Failing)
```kotlin
{current_test_code}
```

## Specific Error Details
- File: {specific_error[file_path]}
- Line: {specific_error[line_number]}
- Error Type: {specific_error[error_type]}
- Error Category: {specific_error[error_category]}
- Message: {specific_error[message]}
- Involved Symbols: {specific_error[involved_symbols]}
- Suggested Fix Approach: {specific_error[suggested_fix]}

## Relevant Dependencies
{relevant_dependencies}

## Instructions
1. Carefully analyze the error in the context of the test code and the source file being tested.
2. Identify the root cause of the error.
3. Provide a detailed explanation of what's wrong and why.
4. Suggest a specific fix for the error, including code changes.
5. If the error involves missing imports, suggest the correct import statements.
6. If the error involves MockK setup, explain how to properly set up the mocks.
7. If the error involves assertions, explain how to fix the assertions.

## Your Analysis
"""

def get_comprehensive_fix_prompt() -> str:
    """
    Returns a prompt template for generating a comprehensive fix based on multiple error analyses.
    """
    return """You are an expert Kotlin developer specializing in JUnit5 and MockK for testing.
Your task is to generate a fixed version of a failing test based on detailed error analyses.

## Source File Being Tested
```kotlin
{target_file_content}
```

## Current Test Code (Failing)
```kotlin
{current_test_code}
```

## Error Analyses
{error_analyses}

## Instructions
1. Review all the error analyses and understand the issues with the current test code.
2. Create a comprehensive fix that addresses all the identified errors.
3. Ensure the fixed code follows best practices for Kotlin, JUnit5, and MockK.
4. Make sure all imports are correct and complete.
5. Ensure proper mock setup and verification.
6. Fix any assertion issues.
7. Maintain the original test's intent and coverage.

## Fixed Test Code
Provide the complete fixed test code below. Include all necessary imports and the entire test class.

```kotlin
// Your fixed code here
```

IMPORTANT: Return the complete test file with all necessary imports and the entire class definition.
Do not omit any parts of the test file. The code should be ready to compile and run without further modifications.
"""
