import logging
import concurrent.futures
from typing import Dict, Any, List, Optional
from pathlib import Path

# Domain Ports
from unit_test_generator.domain.ports.source_control import SourceControlPort
from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort

# Application Use Cases
from unit_test_generator.application.use_cases.generate_tests import GenerateTestsUseCase

# Application Services
from unit_test_generator.application.services.diff_analysis_service import DiffAnalysisService
from unit_test_generator.application.services.diff_context_builder import DiffContextBuilder
from unit_test_generator.application.services.test_output_path_resolver import TestOutputPathResolver

# Application Prompts
from unit_test_generator.application.prompts.diff_focused_test_prompt import (
    get_diff_focused_test_generation_prompt,
    get_diff_focused_test_update_prompt
)

logger = logging.getLogger(__name__)

class GenerateTestsForCommitUseCase:
    """
    Use case for generating unit tests for files changed in a commit.
    Gets the list of changed files from the source control system and
    delegates to GenerateTestsUseCase for each file.
    """
    def __init__(
        self,
        # --- Ports ---
        source_control: SourceControlPort,
        file_system: FileSystemPort,
        llm_service: LLMServicePort,
        # --- Use Cases ---
        generate_tests_use_case: GenerateTestsUseCase,
        # --- Config ---
        config: Dict[str, Any],
    ):
        """Initializes the use case with all necessary dependencies."""
        self.source_control = source_control
        self.file_system = file_system
        self.llm_service = llm_service
        self.generate_tests_use_case = generate_tests_use_case
        self.config = config
        self.repo_root = Path(self.config['repository']['root_path']).resolve()

        # Initialize services
        self.diff_analysis_service = DiffAnalysisService()
        self.diff_context_builder = DiffContextBuilder(
            source_control=source_control,
            file_system=file_system,
            repo_root=self.repo_root
        )
        self.path_resolver = TestOutputPathResolver(config, self.repo_root)
        self.path_resolver.set_file_system(file_system)

        # Configure options
        commit_mode_config = self.config.get('commit_mode', {})
        self.use_diff_focused_approach = commit_mode_config.get('use_diff_focused_approach', True)
        self.skip_similar_test_search = commit_mode_config.get('skip_similar_test_search', True)
        self.skip_dependency_search = commit_mode_config.get('skip_dependency_search', True)

        logger.debug("GenerateTestsForCommitUseCase initialized.")

    def execute(
        self,
        commit_hash_or_file_path: str,
        file_extensions: Optional[List[str]] = None,
        parallel: bool = False,
        max_workers: int = 4
    ) -> Dict[str, Any]:
        """
        Executes the test generation process for files changed in a commit or a single file.

        Args:
            commit_hash_or_file_path: Either a commit hash to check or a file path to generate tests for.
            file_extensions: Optional list of file extensions to filter by (only used for commit mode).
            parallel: Whether to process files in parallel (only used for commit mode).
            max_workers: Maximum number of parallel workers (only used for commit mode).

        Returns:
            A dictionary with results for each file.
        """
        # Check if the input is a commit hash or a file path
        is_file_path = '/' in commit_hash_or_file_path or '\\' in commit_hash_or_file_path

        if is_file_path:
            logger.info(f"GenerateTestsForCommitUseCase executing for file: {commit_hash_or_file_path}")
            return self._process_single_file(commit_hash_or_file_path)
        else:
            # Treat as commit hash
            commit_hash = commit_hash_or_file_path
            logger.info(f"GenerateTestsForCommitUseCase executing for commit: {commit_hash}")

            try:
                # 1. Get the list of changed files
                changed_files = self.source_control.get_changed_files(commit_hash, file_extensions)

                if not changed_files:
                    logger.warning(f"No matching files found in commit {commit_hash}")
                    return {
                        "status": "warning",
                        "message": f"No matching files found in commit {commit_hash}",
                        "results": {}
                    }

                logger.info(f"Found {len(changed_files)} files to process in commit {commit_hash}")

                # 2. Generate tests for each file
                results = {}

                # Process files with diff analysis
                if parallel and len(changed_files) > 1:
                    # Process files in parallel
                    logger.info(f"Processing {len(changed_files)} files in parallel with {max_workers} workers")
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                        # Create a dictionary mapping futures to file paths
                        future_to_file = {
                            executor.submit(self._process_file_with_diff, commit_hash, file_path): file_path
                            for file_path in changed_files
                        }

                        # Process results as they complete
                        for future in concurrent.futures.as_completed(future_to_file):
                            file_path = future_to_file[future]
                            try:
                                result = future.result()
                                results[file_path] = result
                                logger.info(f"Completed test generation for {file_path} with status: {result.get('status')}")
                            except Exception as e:
                                logger.error(f"Error generating tests for {file_path}: {e}", exc_info=True)
                                results[file_path] = {
                                    "status": "error",
                                    "message": f"Error: {str(e)}"
                                }
                else:
                    # Process files sequentially
                    logger.info(f"Processing {len(changed_files)} files sequentially")
                    for file_path in changed_files:
                        try:
                            logger.info(f"Generating tests for {file_path}")
                            result = self._process_file_with_diff(commit_hash, file_path)
                            results[file_path] = result
                            logger.info(f"Completed test generation for {file_path} with status: {result.get('status')}")
                        except Exception as e:
                            logger.error(f"Error generating tests for {file_path}: {e}", exc_info=True)
                            results[file_path] = {
                                "status": "error",
                                "message": f"Error: {str(e)}"
                            }

                # 3. Summarize results
                success_count = sum(1 for result in results.values() if result.get('status', '').startswith('success'))
                error_count = len(results) - success_count

                return {
                    "status": "success" if error_count == 0 else "partial_success" if success_count > 0 else "error",
                    "message": f"Generated tests for {success_count}/{len(results)} files",
                    "results": results
                }

            except Exception as e:
                logger.critical(f"Unexpected error in GenerateTestsForCommitUseCase for {commit_hash}: {e}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Unexpected UseCase error: {e}",
                    "results": {}
                }

    def _process_file_with_diff(self, commit_hash: str, file_path: str) -> Dict[str, Any]:
        """
        Processes a single file with diff analysis.

        Args:
            commit_hash: The commit hash.
            file_path: The path of the file to process.

        Returns:
            The result of the test generation process.
        """
        try:
            # 1. Find the test file path
            test_file_path = self.path_resolver.resolve_relative(file_path)
            abs_test_file_path = self.repo_root / test_file_path
            test_file_exists = abs_test_file_path.exists()
            existing_test_file = test_file_path if test_file_exists else None

            # 2. Check if we should use the diff-focused approach
            if self.use_diff_focused_approach:
                # Use the diff-focused approach
                logger.info(f"Using diff-focused approach for {file_path}")
                return self._generate_test_with_diff_focused_approach(
                    commit_hash=commit_hash,
                    file_path=file_path,
                    existing_test_file=existing_test_file
                )
            else:
                # Use the original approach
                logger.info(f"Using original approach for {file_path}")

                # Convert relative path to absolute path
                abs_file_path = self.repo_root / file_path

                # Check if the file exists in the repository
                if not abs_file_path.exists():
                    logger.warning(f"File {file_path} does not exist in the repository. It may have been deleted after the commit.")
                    # Get the file content from git instead
                    try:
                        # Get the file content at the commit
                        # Access the repo through the GitAdapter
                        file_content = self.source_control.get_file_content_at_commit(commit_hash, file_path)
                    except Exception as e:
                        logger.error(f"Error getting file content from git: {e}")
                        raise ValueError(f"Cannot process file {file_path}: File does not exist and cannot be retrieved from git")
                else:
                    # Read the file content from the file system
                    file_content = self.file_system.read_file(str(abs_file_path))

                # Get the diff for the file
                diff_info = self.source_control.get_file_diff(commit_hash, file_path)

                # Analyze the diff
                diff_analysis = self.diff_analysis_service.analyze_diff(diff_info, file_content)

                # Generate or update the test file
                if test_file_exists:
                    # Update existing test file with diff-based approach
                    logger.info(f"Updating existing test file for {file_path} based on diff analysis")
                    return self._generate_test_with_diff(file_path, diff_info, diff_analysis, test_file_path)
                else:
                    # Generate new test file
                    logger.info(f"Generating new test file for {file_path}")
                    # Pass the file content directly to avoid reading the file again
                    return self.generate_tests_use_case.execute(file_path)

        except Exception as e:
            logger.error(f"Error processing file {file_path} with diff: {e}", exc_info=True)
            raise

    def _clean_code_block_markers(self, code: str) -> str:
        """
        Cleans markdown code block markers from the generated code.

        Args:
            code: The code to clean.

        Returns:
            The cleaned code.
        """
        if not code:
            return code

        # Check if the code starts with ```kotlin or ``` and ends with ```
        if code.startswith("```kotlin"):
            # Remove the ```kotlin from the beginning
            code = code[len("```kotlin"):].lstrip()
        elif code.startswith("```"):
            # Remove the ``` from the beginning
            code = code[len("```"):].lstrip()
            # If the first line is just a language identifier (kotlin, java, etc.), remove it
            lines = code.split('\n', 1)
            if len(lines) > 1 and lines[0].strip().lower() in ["kotlin", "java", "python", "typescript", "javascript"]:
                code = lines[1]

        # Remove the ``` from the end if present
        if code.endswith("```"):
            code = code[:code.rfind("```")].rstrip()

        # Also check for any nested code blocks and remove them
        while "```" in code:
            start_idx = code.find("```")
            end_idx = code.find("```", start_idx + 3)
            if end_idx == -1:
                break
            # Remove the entire code block including the markers
            code = code[:start_idx] + code[end_idx + 3:]

        return code

    def _get_test_file_path(self, file_path: str) -> str:
        """
        Gets the path of the test file for a given source file.

        Args:
            file_path: The path of the source file.

        Returns:
            The path of the test file.
        """
        # This is a simplified version of what would typically be done by the TestOutputPathResolver
        # In a real implementation, you'd use the TestOutputPathResolver from the generate_tests_use_case
        file_path = Path(file_path)
        file_name = file_path.name
        file_stem = file_path.stem

        # Replace 'main' with 'test' in the path
        test_path = str(file_path).replace('/main/', '/test/')

        # Add 'Test' suffix if not already present
        if not file_stem.endswith('Test'):
            test_path = test_path.replace(file_name, f"{file_stem}Test{file_path.suffix}")

        return test_path

    def _generate_test_with_diff_focused_approach(self, commit_hash: str, file_path: str, existing_test_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates or updates a test file using the diff-focused approach.

        Args:
            commit_hash: The commit hash.
            file_path: The path of the source file.
            existing_test_file: The path of the existing test file, if any.

        Returns:
            The result of the test generation process.
        """
        try:
            # 1. Build the diff context
            context = self.diff_context_builder.build_diff_context(
                commit_hash=commit_hash,
                file_path=file_path,
                existing_test_file=existing_test_file
            )

            # 2. Determine the output path
            output_path = self.path_resolver.resolve_absolute(file_path)
            rel_output_path = str(output_path.relative_to(self.repo_root))

            # 3. Select the appropriate prompt template
            if context['update_mode']:
                logger.info(f"Using update prompt for {file_path}")
                prompt_template = get_diff_focused_test_update_prompt()
            else:
                logger.info(f"Using generation prompt for {file_path}")
                prompt_template = get_diff_focused_test_generation_prompt()

            # 4. Format the added code blocks for the prompt
            added_blocks = context.get('added_code_blocks', 'No added code blocks.')
            modified_blocks = context.get('modified_code_blocks', 'No modified code blocks.')
            new_imports = context.get('new_imports', 'No new imports.')

            # 5. Determine if we should skip similar test search and dependency search
            has_new_imports = len(context.get('new_dependencies', [])) > 0
            skip_similar_tests = self.skip_similar_test_search and not has_new_imports
            skip_dependencies = self.skip_dependency_search and not has_new_imports

            if skip_similar_tests:
                logger.info(f"Skipping similar test search for {file_path} (no new imports)")
            if skip_dependencies:
                logger.info(f"Skipping dependency search for {file_path} (no new imports)")

            # 6. Generate the test code
            logger.info(f"Generating test code for {file_path} with diff-focused approach")
            test_code = self.llm_service.generate_tests({
                'task': 'diff_focused_test_generation',
                'target_file_path': file_path,
                'target_file_content': context['target_file_content'],
                'diff_content': context['diff_content'],
                'added_code_blocks': added_blocks,
                'modified_code_blocks': modified_blocks,
                'new_imports': new_imports,
                'existing_test_code': context.get('existing_test_code', ''),
                'update_mode': context['update_mode'],
                'prompt_template': prompt_template,
                'skip_similar_test_search': skip_similar_tests,
                'skip_dependency_search': skip_dependencies
            })

            # 7. Clean the test code to remove any markdown code block markers
            cleaned_test_code = self._clean_code_block_markers(test_code)

            # 8. Write the test file
            self.file_system.write_file(str(output_path), cleaned_test_code)

            # 8. Return the result
            return {
                'status': 'success_generated_only',
                'output_path': rel_output_path,
                'message': f"Generated test file at {rel_output_path}"
            }

        except Exception as e:
            logger.error(f"Error generating test with diff-focused approach: {e}", exc_info=True)
            return {
                'status': 'error',
                'message': f"Error: {str(e)}"
            }

    def _process_single_file(self, file_path: str) -> Dict[str, Any]:
        """
        Processes a single file without diff analysis.

        Args:
            file_path: The path of the file to process.

        Returns:
            The result of the test generation process.
        """
        try:
            logger.info(f"Processing single file: {file_path}")

            # Generate the test file
            result = self.generate_tests_use_case.execute(file_path)

            # Get the test file path
            test_file_path = result.get("test_file_path")
            if not test_file_path:
                logger.warning(f"No test file path returned for {file_path}")
                return {
                    "status": "error",
                    "message": f"No test file path returned for {file_path}"
                }

            # Commit the changes
            try:
                # Add the test file to the staging area
                self.source_control.add_file(test_file_path)

                # Create a commit message
                commit_message = f"Add tests for {file_path}"

                # Commit the changes
                self.source_control.commit(commit_message)

                logger.info(f"Successfully committed changes for {test_file_path}")

                return {
                    "status": "success",
                    "message": f"Generated and committed test file at {test_file_path}",
                    "test_file_path": test_file_path,
                    "commit_success": True
                }
            except Exception as e:
                logger.error(f"Error committing changes: {e}", exc_info=True)

                return {
                    "status": "partial_success",
                    "message": f"Generated test file at {test_file_path} but failed to commit: {str(e)}",
                    "test_file_path": test_file_path,
                    "commit_success": False,
                    "commit_error": str(e)
                }

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}", exc_info=True)

            return {
                "status": "error",
                "message": f"Error: {str(e)}"
            }

    def _generate_test_with_diff(self, file_path: str, diff_info: Dict[str, Any], diff_analysis: Dict[str, Any], test_file_path: str) -> Dict[str, Any]:
        """
        Generates or updates a test file based on diff analysis.

        Args:
            file_path: The path of the source file.
            diff_info: The diff information from the source control system.
            diff_analysis: The analysis of the diff.
            test_file_path: The path of the test file.

        Returns:
            The result of the test generation process.
        """
        # In a real implementation, you'd modify the context payload for the LLM to include the diff information
        # For now, we'll just use the existing generate_tests_use_case with a custom context

        # Convert to absolute paths
        abs_file_path = self.repo_root / file_path
        abs_test_file_path = self.repo_root / test_file_path

        # Read the existing test file
        test_file_content = ""
        if abs_test_file_path.exists():
            test_file_content = self.file_system.read_file(str(abs_test_file_path))

        # Create a custom context with diff information
        # This would typically be done by modifying the context builder in the generate_tests_use_case
        # For now, we'll just pass the file path and let the use case handle it

        # TODO: Implement a proper way to pass the diff information to the LLM
        # For now, we'll just use the existing generate_tests_use_case
        return self.generate_tests_use_case.execute(file_path)