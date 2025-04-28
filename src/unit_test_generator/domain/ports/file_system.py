from abc import ABC, abstractmethod
from typing import List, Optional, Generator
from pathlib import Path


class FileSystemPort(ABC):
    """Interface for interacting with the file system."""

    @abstractmethod
    def walk_directory(self, root_path: str, ignore_dirs: List[str]) -> Generator[Path, None, None]:
        """
        Recursively walks a directory, yielding Path objects for files.
        Skips specified directory names.
        """
        pass

    @abstractmethod
    def read_file(self, file_path: str) -> str:
        """Reads the content of a file."""
        pass

    @abstractmethod
    def write_file(self, file_path: str, content: str):
        """Writes content to a file, creating directories if needed."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Checks if a file or directory exists."""
        pass

    @abstractmethod
    def get_relative_path(self, full_path: str, base_path: str) -> str:
        """Calculates the relative path."""
        pass

    @abstractmethod
    def make_dirs(self, path: str):
        """Creates directories recursively."""
        pass

    @abstractmethod
    def get_file_extension(self, file_path: str) -> str:
        """Returns the file extension (e.g., '.kt')."""
        pass

    @abstractmethod
    def get_file_stem(self, file_path: str) -> str:
        """Returns the filename without the extension."""
        pass
