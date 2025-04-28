# src/unit_test_generator/application/prompts/diff_based_test_prompt.py
"""
Prompts for generating tests based on diffs.
"""

def get_diff_based_test_generation_prompt() -> str:
    """
    Returns a prompt template for generating tests based on diffs.
    """
    return """You are an expert Kotlin developer specializing in JUnit5 and MockK for testing.
Your task is to generate or update unit tests for a file that has been modified in a commit.

## Source File Being Tested
```kotlin
{target_file_content}
```

## Diff Information
```diff
{diff_content}
```

## Changes Summary
{diff_summary}

## Affected Methods
{affected_methods}

## Existing Test File (if available)
```kotlin
{existing_test_code}
```

## Instructions
1. Focus on writing tests for the methods that have been added or modified in the diff.
2. If an existing test file is provided, update it to cover the changes while preserving existing tests.
3. If no existing test file is provided, create a new test file from scratch.
4. Ensure the tests follow best practices for Kotlin, JUnit5, and MockK.
5. Make sure all imports are correct and complete.
6. Ensure proper mock setup and verification.
7. Write assertions that verify the expected behavior.
8. Do not remove existing tests unless they are no longer applicable due to the changes.

## Generated/Updated Test Code
Provide the complete test code below. Include all necessary imports and the entire test class.

```kotlin
// Your test code here
```

IMPORTANT: Return the complete test file with all necessary imports and the entire class definition.
Do not omit any parts of the test file. The code should be ready to compile and run without further modifications.
"""

def get_diff_based_test_update_prompt() -> str:
    """
    Returns a prompt template for updating tests based on diffs.
    """
    return """You are an expert Kotlin developer specializing in JUnit5 and MockK for testing.
Your task is to update an existing test file to cover changes made to the source file in a commit.

## Source File Being Tested
```kotlin
{target_file_content}
```

## Diff Information
```diff
{diff_content}
```

## Changes Summary
{diff_summary}

## Affected Methods
{affected_methods}

## Existing Test File
```kotlin
{existing_test_code}
```

## Instructions
1. Focus on updating tests for the methods that have been modified in the diff.
2. Add new tests for methods that have been added in the diff.
3. Preserve existing tests for methods that have not been changed.
4. Ensure the tests follow best practices for Kotlin, JUnit5, and MockK.
5. Make sure all imports are correct and complete.
6. Ensure proper mock setup and verification.
7. Write assertions that verify the expected behavior.
8. Do not remove existing tests unless they are no longer applicable due to the changes.

## Updated Test Code
Provide the complete updated test code below. Include all necessary imports and the entire test class.

```kotlin
// Your updated test code here
```

IMPORTANT: Return the complete test file with all necessary imports and the entire class definition.
Do not omit any parts of the test file. The code should be ready to compile and run without further modifications.
"""
