import os
import json
import fnmatch
from pathlib import Path
from typing import List, Generator

# Assuming ports are accessible (adjust import path as needed)
from unit_test_generator.domain.ports.file_system import FileSystemPort


class FileSystemAdapter(FileSystemPort):
    """Concrete implementation of FileSystemPort using standard Python libraries."""

    def walk_directory(self, root_path: str, ignore_patterns: List[str]) -> Generator[Path, None, None]:
        """
        Recursively walks a directory, yielding Path objects for files.
        Skips paths matching any of the ignore patterns (using fnmatch).
        Patterns should typically end with '/' to match directories.
        """
        root = Path(root_path).resolve()
        for item in root.rglob('*'):
            relative_path_str = str(item.relative_to(root)).replace(os.sep, '/')  # Normalize slashes for matching
            # Add a '/' suffix for directories to match directory patterns like 'build/'
            match_path = relative_path_str + ('/' if item.is_dir() else '')

            # Check against ignore patterns
            is_ignored = False
            for pattern in ignore_patterns:
                if fnmatch.fnmatch(match_path, pattern) or \
                        any(fnmatch.fnmatch(part + '/', pattern) for part in item.relative_to(root).parts if
                            pattern.endswith('/')):
                    # Check if any parent directory matches a directory pattern
                    parent_ignored = False
                    temp_path = item.parent
                    while temp_path != root:
                        rel_parent_str = str(temp_path.relative_to(root)).replace(os.sep, '/') + '/'
                        if any(fnmatch.fnmatch(rel_parent_str, p) for p in ignore_patterns if p.endswith('/')):
                            parent_ignored = True
                            break
                        temp_path = temp_path.parent
                    if parent_ignored:
                        is_ignored = True
                        break

                    # If the direct path matches or a parent dir matches
                    is_ignored = True
                    break  # No need to check other patterns

            if is_ignored:
                # If a directory is ignored, skip its contents implicitly via rglob's behavior
                # If a file is ignored, just continue the loop
                continue

            if item.is_file():
                yield item

    def read_file(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            # Consider logging the error here
            print(f"Error reading file {file_path}: {e}")  # Replace with proper logging
            raise  # Re-raise or handle appropriately

    def write_file(self, file_path: str, content: str):
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"Error writing file {file_path}: {e}")  # Replace with proper logging
            raise

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def get_relative_path(self, full_path: str, base_path: str) -> str:
        # Ensure paths are absolute and resolved for reliable relative path calculation
        full = Path(full_path).resolve()
        base = Path(base_path).resolve()
        return str(full.relative_to(base))

    def make_dirs(self, path: str):
        # Use exist_ok=True to avoid errors if directory already exists
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def get_file_extension(self, file_path: str) -> str:
        return Path(file_path).suffix

    def get_file_stem(self, file_path: str) -> str:
        return Path(file_path).stem

    # --- JSON Helper Methods ---
    def write_json(self, file_path: str, data: dict):
        """Helper specific to this adapters for writing JSON index."""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                # Use custom encoder if needed for complex objects (like Enums)
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error writing JSON file {file_path}: {e}")  # Replace with proper logging
            raise

    def read_json(self, file_path: str) -> dict:
        """Helper specific to this adapters for reading JSON index."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"JSON file not found: {file_path}")  # Replace with proper logging
            return {}  # Return empty dict if not found
        except Exception as e:
            print(f"Error reading JSON file {file_path}: {e}")  # Replace with proper logging
            raise
        