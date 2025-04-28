# src/unit_test_generator/application/prompts/diff_focused_test_prompt.py
"""
Prompts for generating tests based on diffs with a focus on the changes only.
"""

def get_diff_focused_test_generation_prompt() -> str:
    """
    Returns a prompt template for generating tests based on diffs, focusing only on the changes.
    """
    return """You are an expert Kotlin developer specializing in JUnit5 and MockK for testing.
Your task is to generate or update unit tests for a file that has been modified in a commit.

## Source File Being Tested
```kotlin
{target_file_content}
```

## Changes Made in the Commit
```diff
{diff_content}
```

## Added Code Blocks
{added_code_blocks}

## Modified Code Blocks
{modified_code_blocks}

## New Imports
{new_imports}

## Existing Test File (if available)
```kotlin
{existing_test_code}
```

## Instructions
1. Focus ONLY on writing tests for the methods that have been added or modified in the diff.
2. If an existing test file is provided, update it to cover the changes while preserving existing tests.
3. If no existing test file is provided, create a new test file that tests the changed methods.
4. Do NOT attempt to test methods that were not changed.
5. Ensure the tests follow best practices for Kotlin, JUnit5, and MockK.
6. Make sure all imports are correct and complete.
7. Ensure proper mock setup and verification.
8. Write assertions that verify the expected behavior.
9. Do not remove existing tests unless they are no longer applicable due to the changes.
10. Do not attempt to write tests for private methods. Only test public methods and include cases where the private
method is called by a public method.{optimization_instructions}

## Generated/Updated Test Code
Provide the complete test code below. Include all necessary imports and the entire test class.

```kotlin
// Your test code here
```

IMPORTANT: Return the complete test file with all necessary imports and the entire class definition.
Do not omit any parts of the test file. The code should be ready to compile and run without further modifications.
"""

def get_diff_focused_test_update_prompt() -> str:
    """
    Returns a prompt template for updating tests based on diffs, focusing only on the changes.
    """
    return """You are an expert Kotlin developer specializing in JUnit5 and MockK for testing.
Your task is to update an existing test file to cover changes made to the source file in a commit.

## Source File Being Tested
```kotlin
{target_file_content}
```

## Changes Made in the Commit
```diff
{diff_content}
```

## Added Code Blocks
{added_code_blocks}

## Modified Code Blocks
{modified_code_blocks}

## New Imports
{new_imports}

## Existing Test File
```kotlin
{existing_test_code}
```

## Instructions
1. Focus ONLY on updating tests for the methods that have been modified in the diff.
2. Add new tests ONLY for methods that have been added in the diff.
3. Preserve existing tests for methods that have not been changed.
4. Do NOT attempt to test methods that were not changed.
5. Ensure the tests follow best practices for Kotlin, JUnit5, and MockK.
6. Make sure all imports are correct and complete.
7. Ensure proper mock setup and verification.
8. Write assertions that verify the expected behavior.
9. Do not remove existing tests unless they are no longer applicable due to the changes.{optimization_instructions}

## Updated Test Code
Provide the complete updated test code below. Include all necessary imports and the entire test class.

```kotlin
// Your updated test code here
```

IMPORTANT: Return the complete test file with all necessary imports and the entire class definition.
Do not omit any parts of the test file. The code should be ready to compile and run without further modifications.
"""
