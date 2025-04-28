import logging
import re
import os
import difflib
from typing import List, Optional, Dict, Any, Set, Tuple
from pathlib import Path
import git

from unit_test_generator.domain.ports.source_control import SourceControlPort

logger = logging.getLogger(__name__)

class GitAdapter(SourceControlPort):
    """Implementation of SourceControlPort using GitPython."""

    def __init__(self, repo_root: str):
        """
        Initializes the GitAdapter.

        Args:
            repo_root: The root directory of the Git repository.
        """
        self.repo_root = Path(repo_root).resolve()
        try:
            self.repo = git.Repo(self.repo_root)
            logger.info(f"Git repository initialized at {self.repo_root}")
        except git.InvalidGitRepositoryError:
            logger.error(f"Invalid Git repository at {self.repo_root}")
            raise ValueError(f"Invalid Git repository at {self.repo_root}")
        except Exception as e:
            logger.error(f"Error initializing Git repository: {e}")
            raise

    def get_changed_files(self, commit_hash: str, file_extensions: Optional[List[str]] = None) -> List[str]:
        """
        Gets the list of files changed in a commit.

        Args:
            commit_hash: The commit hash to check.
            file_extensions: Optional list of file extensions to filter by (e.g., ['.kt', '.java']).

        Returns:
            A list of relative paths to the changed files.
        """
        try:
            # Validate commit hash
            if not self.is_commit_hash(commit_hash):
                raise ValueError(f"Invalid commit hash: {commit_hash}")

            # Get the commit object
            commit = self.repo.commit(commit_hash)

            # Get the parent commit
            parent = commit.parents[0] if commit.parents else None

            # Get the diff between the commit and its parent
            if parent:
                diffs = parent.diff(commit)
            else:
                # For the first commit, get all files
                diffs = commit.diff(git.NULL_TREE)

            # Get the list of changed files
            changed_files = []
            for diff in diffs:
                # Skip deleted files
                if diff.deleted_file:
                    continue

                # Get the path of the changed file
                file_path = diff.b_path

                # Filter by file extension if specified
                if file_extensions:
                    file_ext = Path(file_path).suffix
                    if file_ext not in file_extensions:
                        continue

                # Add the file path to the list
                changed_files.append(file_path)

            logger.info(f"Found {len(changed_files)} changed files in commit {commit_hash}")
            return changed_files

        except git.GitCommandError as e:
            logger.error(f"Git command error: {e}")
            raise ValueError(f"Git command error: {e}")
        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            raise

    def get_file_diff(self, commit_hash: str, file_path: str) -> Dict[str, Any]:
        """
        Gets the diff for a specific file in a commit.

        Args:
            commit_hash: The commit hash to check.
            file_path: The path of the file to get the diff for.

        Returns:
            A dictionary containing diff information, including:
            - 'content': The diff content as a string
            - 'added_lines': List of line numbers that were added
            - 'modified_lines': List of line numbers that were modified
            - 'removed_lines': List of line numbers that were removed
            - 'is_new_file': Boolean indicating if this is a new file
        """
        try:
            # Validate commit hash
            if not self.is_commit_hash(commit_hash):
                raise ValueError(f"Invalid commit hash: {commit_hash}")

            # Get the commit object
            commit = self.repo.commit(commit_hash)

            # Get the parent commit
            parent = commit.parents[0] if commit.parents else None

            # Initialize result dictionary
            result = {
                'content': '',
                'added_lines': [],
                'modified_lines': [],
                'removed_lines': [],
                'is_new_file': False
            }

            # Get the diff between the commit and its parent
            if parent:
                # Get the diff for the specific file
                diffs = parent.diff(commit, paths=[file_path])

                # If no diffs found for the file, return empty result
                if not diffs:
                    logger.warning(f"No diff found for file {file_path} in commit {commit_hash}")
                    return result

                # Get the diff object for the file
                diff = diffs[0]

                # Check if this is a new file
                result['is_new_file'] = diff.new_file

                # Get the diff content
                # Use git diff command to get a more readable diff
                diff_cmd = ['git', 'diff', f"{parent.hexsha}..{commit.hexsha}", '--', file_path]
                diff_output = self.repo.git.execute(diff_cmd)
                result['content'] = diff_output

                # Parse the diff to identify added, modified, and removed lines
                added_lines = []
                modified_lines = []
                removed_lines = []

                # Get the diff as a list of lines
                diff_lines = diff_output.split('\n')
                current_line = 0

                # Skip the header lines
                for i, line in enumerate(diff_lines):
                    if line.startswith('@@'):
                        # Parse the line numbers from the @@ line
                        # Format: @@ -old_start,old_count +new_start,new_count @@
                        line_info = line.split('@@')[1].strip()
                        new_line_info = line_info.split('+')[1].split(',')[0]
                        current_line = int(new_line_info) - 1  # -1 because we'll increment before using
                        break

                # Process the diff lines
                for line in diff_lines[i+1:]:
                    if line.startswith('+'):
                        # Added line
                        current_line += 1
                        added_lines.append(current_line)
                    elif line.startswith('-'):
                        # Removed line - don't increment current_line
                        removed_lines.append(current_line)
                    elif not line.startswith('\\'):
                        # Context line or other non-special line
                        current_line += 1

                # Store the line numbers
                result['added_lines'] = added_lines
                result['removed_lines'] = removed_lines

                # For simplicity, consider lines adjacent to removed lines as modified
                for removed in removed_lines:
                    if removed+1 not in removed_lines and removed+1 in added_lines:
                        modified_lines.append(removed+1)
                        # Remove from added lines since we're considering it modified
                        if removed+1 in added_lines:
                            added_lines.remove(removed+1)

                result['modified_lines'] = modified_lines
                result['added_lines'] = added_lines  # Update after potential modifications
            else:
                # For the first commit, the entire file is new
                result['is_new_file'] = True

                # Get the file content
                file_content = self.repo.git.show(f"{commit.hexsha}:{file_path}")
                result['content'] = file_content

                # All lines are added
                result['added_lines'] = list(range(1, len(file_content.split('\n')) + 1))

            return result

        except git.GitCommandError as e:
            logger.error(f"Git command error: {e}")
            raise ValueError(f"Git command error: {e}")
        except Exception as e:
            logger.error(f"Error getting file diff: {e}")
            raise

    def get_precise_file_diff(self, commit_hash: str, file_path: str) -> Dict[str, Any]:
        """
        Gets a more precise diff for a specific file in a commit, focusing on the actual code changes.

        Args:
            commit_hash: The commit hash to check.
            file_path: The path of the file to get the diff for.

        Returns:
            A dictionary containing precise diff information, including:
            - 'content': The diff content as a string (only the changed parts with minimal context)
            - 'added_code_blocks': List of added code blocks with their context
            - 'modified_code_blocks': List of modified code blocks with their context
            - 'removed_code_blocks': List of removed code blocks with their context
            - 'new_imports': List of new imports added in the commit
            - 'is_new_file': Boolean indicating if this is a new file
        """
        try:
            # Validate commit hash
            if not self.is_commit_hash(commit_hash):
                raise ValueError(f"Invalid commit hash: {commit_hash}")

            # Get the commit object
            commit = self.repo.commit(commit_hash)

            # Get the parent commit
            parent = commit.parents[0] if commit.parents else None

            # Initialize result dictionary
            result = {
                'content': '',
                'added_code_blocks': [],
                'modified_code_blocks': [],
                'removed_code_blocks': [],
                'new_imports': [],
                'is_new_file': False
            }

            # If no parent, this is a new file
            if not parent:
                result['is_new_file'] = True
                file_content = self.get_file_content_at_commit(commit_hash, file_path)
                result['content'] = file_content

                # Extract imports
                imports = self._extract_imports(file_content)
                result['new_imports'] = imports

                # The entire file is an added code block
                result['added_code_blocks'].append({
                    'content': file_content,
                    'start_line': 1,
                    'end_line': len(file_content.split('\n'))
                })

                return result

            # Get the diff for the specific file
            diffs = parent.diff(commit, paths=[file_path])

            # If no diffs found for the file, return empty result
            if not diffs:
                logger.warning(f"No diff found for file {file_path} in commit {commit_hash}")
                return result

            # Get the diff object for the file
            diff = diffs[0]

            # Check if this is a new file
            result['is_new_file'] = diff.new_file

            if diff.new_file:
                # For a new file, get the content and extract imports
                file_content = self.get_file_content_at_commit(commit_hash, file_path)
                result['content'] = file_content

                # Extract imports
                imports = self._extract_imports(file_content)
                result['new_imports'] = imports

                # The entire file is an added code block
                result['added_code_blocks'].append({
                    'content': file_content,
                    'start_line': 1,
                    'end_line': len(file_content.split('\n'))
                })

                return result

            # Get the content of the file before and after the commit
            old_content = self.repo.git.show(f"{parent.hexsha}:{file_path}") if not diff.new_file else ""
            new_content = self.repo.git.show(f"{commit.hexsha}:{file_path}")

            # Use git diff command to get a more readable diff
            diff_cmd = ['git', 'diff', '--unified=3', f"{parent.hexsha}..{commit.hexsha}", '--', file_path]
            diff_output = self.repo.git.execute(diff_cmd)
            result['content'] = diff_output

            # Extract imports from both versions
            old_imports = self._extract_imports(old_content)
            new_imports = self._extract_imports(new_content)

            # Find new imports
            result['new_imports'] = list(set(new_imports) - set(old_imports))

            # Use difflib to get a more detailed diff
            old_lines = old_content.split('\n')
            new_lines = new_content.split('\n')

            # Get the diff as a sequence matcher
            matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

            # Process the diff to extract code blocks
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'replace':
                    # Modified code block
                    old_block = '\n'.join(old_lines[i1:i2])
                    new_block = '\n'.join(new_lines[j1:j2])

                    # Add context lines
                    context_before = max(0, j1 - 3)
                    context_after = min(len(new_lines), j2 + 3)
                    context_before_lines = new_lines[context_before:j1] if j1 > context_before else []
                    context_after_lines = new_lines[j2:context_after] if j2 < context_after else []

                    result['modified_code_blocks'].append({
                        'old_content': old_block,
                        'new_content': new_block,
                        'start_line': j1 + 1,  # 1-based line numbers
                        'end_line': j2,
                        'context_before': '\n'.join(context_before_lines),
                        'context_after': '\n'.join(context_after_lines)
                    })
                elif tag == 'delete':
                    # Removed code block
                    removed_block = '\n'.join(old_lines[i1:i2])

                    result['removed_code_blocks'].append({
                        'content': removed_block,
                        'start_line': i1 + 1,  # 1-based line numbers
                        'end_line': i2
                    })
                elif tag == 'insert':
                    # Added code block
                    added_block = '\n'.join(new_lines[j1:j2])

                    # Add context lines
                    context_before = max(0, j1 - 3)
                    context_after = min(len(new_lines), j2 + 3)
                    context_before_lines = new_lines[context_before:j1] if j1 > context_before else []
                    context_after_lines = new_lines[j2:context_after] if j2 < context_after else []

                    result['added_code_blocks'].append({
                        'content': added_block,
                        'start_line': j1 + 1,  # 1-based line numbers
                        'end_line': j2,
                        'context_before': '\n'.join(context_before_lines),
                        'context_after': '\n'.join(context_after_lines)
                    })

            return result

        except git.GitCommandError as e:
            logger.error(f"Git command error: {e}")
            raise ValueError(f"Git command error: {e}")
        except Exception as e:
            logger.error(f"Error getting precise file diff: {e}")
            raise

    def _extract_imports(self, content: str) -> List[str]:
        """
        Extracts import statements from code content.

        Args:
            content: The code content to extract imports from.

        Returns:
            A list of import statements.
        """
        imports = []
        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)

        return imports

    def get_file_content_at_commit(self, commit_hash: str, file_path: str) -> str:
        """
        Gets the content of a file at a specific commit.

        Args:
            commit_hash: The commit hash to check.
            file_path: The path of the file to get the content for.

        Returns:
            The content of the file at the specified commit.
        """
        try:
            # Validate commit hash
            if not self.is_commit_hash(commit_hash):
                raise ValueError(f"Invalid commit hash: {commit_hash}")

            # Get the commit object
            commit = self.repo.commit(commit_hash)

            # Get the file content at the commit
            file_content = self.repo.git.show(f"{commit.hexsha}:{file_path}")

            return file_content

        except git.GitCommandError as e:
            logger.error(f"Git command error: {e}")
            raise ValueError(f"Git command error: {e}")
        except Exception as e:
            logger.error(f"Error getting file content at commit: {e}")
            raise

    def get_new_dependencies(self, commit_hash: str, file_path: str) -> Set[str]:
        """
        Identifies new dependencies introduced by changes in a commit.

        Args:
            commit_hash: The commit hash to check.
            file_path: The path of the file to check for new dependencies.

        Returns:
            A set of file paths representing new dependencies introduced by the changes.
        """
        try:
            # Get the precise diff to extract new imports
            diff_info = self.get_precise_file_diff(commit_hash, file_path)

            # If there are no new imports, return an empty set
            if not diff_info['new_imports']:
                return set()

            # Extract potential dependency paths from the new imports
            new_dependencies = set()

            for import_stmt in diff_info['new_imports']:
                # Parse the import statement to extract the package/module name
                if import_stmt.startswith('import '):
                    # Handle 'import package.module' or 'import package.module as alias'
                    module_path = import_stmt[7:].split(' as ')[0].strip()
                    # Convert package.module to package/module
                    file_path = module_path.replace('.', '/')
                    new_dependencies.add(file_path)
                elif import_stmt.startswith('from '):
                    # Handle 'from package.module import Class'
                    parts = import_stmt.split(' import ')
                    if len(parts) == 2:
                        module_path = parts[0][5:].strip()  # Remove 'from ' prefix
                        # Convert package.module to package/module
                        file_path = module_path.replace('.', '/')
                        new_dependencies.add(file_path)

            return new_dependencies

        except Exception as e:
            logger.error(f"Error getting new dependencies: {e}")
            return set()

    def is_commit_hash(self, value: str) -> bool:
        """
        Checks if a value is a valid commit hash.

        Args:
            value: The value to check.

        Returns:
            True if the value is a valid commit hash, False otherwise.
        """
        try:
            # Check if the value is a valid SHA-1 hash (40 hex characters)
            if re.match(r'^[0-9a-f]{40}$', value, re.IGNORECASE):
                return True

            # Check if the value is a valid abbreviated SHA-1 hash (at least 7 hex characters)
            if re.match(r'^[0-9a-f]{7,39}$', value, re.IGNORECASE):
                # Try to resolve it to a commit
                self.repo.commit(value)
                return True

            # Check if the value is a valid reference (branch, tag, etc.)
            if value in self.repo.references:
                return True

            # Check special references like HEAD, HEAD~1, etc.
            if value.startswith('HEAD') or value in ['HEAD', 'HEAD~1', 'HEAD^']:
                self.repo.commit(value)
                return True

            return False

        except (git.GitCommandError, ValueError):
            return False
        except Exception as e:
            logger.error(f"Error checking commit hash: {e}")
            return False