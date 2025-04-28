from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple, Set

class SourceControlPort(ABC):
    """Interface for interacting with source control systems."""

    @abstractmethod
    def get_changed_files(self, commit_hash: str, file_extensions: Optional[List[str]] = None) -> List[str]:
        """
        Gets the list of files changed in a commit.

        Args:
            commit_hash: The commit hash to check.
            file_extensions: Optional list of file extensions to filter by (e.g., ['.kt', '.java']).

        Returns:
            A list of relative paths to the changed files.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_file_content_at_commit(self, commit_hash: str, file_path: str) -> str:
        """
        Gets the content of a file at a specific commit.

        Args:
            commit_hash: The commit hash to check.
            file_path: The path of the file to get the content for.

        Returns:
            The content of the file at the specified commit.
        """
        pass

    @abstractmethod
    def get_new_dependencies(self, commit_hash: str, file_path: str) -> Set[str]:
        """
        Identifies new dependencies introduced by changes in a commit.

        Args:
            commit_hash: The commit hash to check.
            file_path: The path of the file to check for new dependencies.

        Returns:
            A set of file paths representing new dependencies introduced by the changes.
        """
        pass

    @abstractmethod
    def is_commit_hash(self, value: str) -> bool:
        """
        Checks if a value is a valid commit hash.

        Args:
            value: The value to check.

        Returns:
            True if the value is a valid commit hash, False otherwise.
        """
        pass