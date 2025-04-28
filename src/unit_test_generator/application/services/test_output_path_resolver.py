import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class TestOutputPathResolver:
    """Resolves the output path for generated test files."""

    def __init__(self, config: Dict[str, Any], repo_root: Path):
        """
        Initializes the resolver.

        Args:
            config: The application configuration dictionary.
            repo_root: The resolved absolute path to the root of the target repository.
        """
        self.config = config
        self.repo_root = repo_root
        self.gen_config = config.get('generation', {})
        self.output_dir = Path(self.gen_config.get('output_dir', 'generated-tests')).resolve()
        self.write_to_repo = self.gen_config.get('write_to_repo', False)
        self.file_system = None  # Will be set by the orchestrator

    def resolve(self, target_source_rel_path_str: str) -> Path:
        """
        Determines the absolute output path for the generated test file.

        Args:
            target_source_rel_path_str: Relative path of the source file from repo root.

        Returns:
            The resolved absolute Path object for the output test file.

        Raises:
            ValueError: If the path structure is unexpected.
        """
        source_path = Path(target_source_rel_path_str)
        parts = list(source_path.parts)
        test_filename = f"{source_path.stem}Test{source_path.suffix}"

        # Try standard src/main -> src/test replacement
        replaced = False
        try:
            main_idx = parts.index("main")
            if main_idx > 0 and parts[main_idx-1] == "src":
                parts[main_idx] = "test"
                replaced = True
        except ValueError:
            pass # 'main' not found

        if replaced:
            test_sub_path = Path(*parts[:-1]) / test_filename
            if self.write_to_repo:
                final_path = self.repo_root / test_sub_path
                logger.debug(f"Resolved test path (in repo): {final_path}")
            else:
                final_path = self.output_dir / test_sub_path
                logger.debug(f"Resolved test path (in output dir): {final_path}")
            return final_path
        else:
            # Fallback if structure doesn't match src/main -> src/test
            logger.warning(f"Could not perform standard 'src/main' -> 'src/test' path replacement for {source_path}. Using fallback structure.")
            if self.write_to_repo:
                # Place relative to repo root, mirroring source relative path
                final_path = self.repo_root / source_path.parent / test_filename
                logger.debug(f"Resolved test path (in repo, fallback): {final_path}")
            else:
                 # Place directly under output_dir, mirroring source relative path
                final_path = self.output_dir / source_path.parent / test_filename
                logger.debug(f"Resolved test path (in output dir, fallback): {final_path}")
            return final_path

    def set_file_system(self, file_system):
        """
        Sets the file system adapter.

        Args:
            file_system: The file system adapter.
        """
        self.file_system = file_system

    def find_existing_test_file(self, target_source_rel_path_str: str) -> Optional[Tuple[Path, str]]:
        """
        Checks if a test file already exists for the given source file.

        Args:
            target_source_rel_path_str: Relative path of the source file from repo root.

        Returns:
            A tuple of (test_file_path, test_file_content) if a test file exists, None otherwise.
        """
        if not self.file_system:
            logger.warning("File system not set in TestOutputPathResolver. Cannot check for existing test files.")
            return None

        # Get the expected test file path
        expected_test_path = self.resolve(target_source_rel_path_str)

        # Check if the file exists
        if self.file_system.file_exists(str(expected_test_path)):
            try:
                test_content = self.file_system.read_file(str(expected_test_path))
                logger.info(f"Found existing test file at {expected_test_path}")
                return (expected_test_path, test_content)
            except Exception as e:
                logger.warning(f"Error reading existing test file {expected_test_path}: {e}")
                return None

        # If not found at the expected path, try alternative locations
        source_path = Path(target_source_rel_path_str)
        test_filename = f"{source_path.stem}Test{source_path.suffix}"

        # Try to find in src/test directory
        try:
            parts = list(source_path.parts)
            if "main" in parts:
                main_idx = parts.index("main")
                if main_idx > 0:
                    parts[main_idx] = "test"
                    alt_test_path = self.repo_root / Path(*parts[:-1]) / test_filename
                    if self.file_system.file_exists(str(alt_test_path)):
                        test_content = self.file_system.read_file(str(alt_test_path))
                        logger.info(f"Found existing test file at alternative location {alt_test_path}")
                        return (alt_test_path, test_content)
        except Exception as e:
            logger.warning(f"Error checking alternative test locations: {e}")

        logger.info(f"No existing test file found for {target_source_rel_path_str}")
        return None

    def set_file_system(self, file_system):
        """Sets the file system adapter."""
        self.file_system = file_system

    def resolve_relative(self, target_source_rel_path_str: str) -> str:
        """
        Determines the relative output path for the generated test file.

        Args:
            target_source_rel_path_str: Relative path of the source file from repo root.

        Returns:
            The resolved relative path string for the output test file.
        """
        source_path = Path(target_source_rel_path_str)
        parts = list(source_path.parts)
        test_filename = f"{source_path.stem}Test{source_path.suffix}"

        # Try standard src/main -> src/test replacement
        replaced = False
        try:
            main_idx = parts.index("main")
            if main_idx > 0 and parts[main_idx-1] == "src":
                parts[main_idx] = "test"
                replaced = True
        except ValueError:
            pass  # 'main' not found

        if not replaced:
            # If we couldn't replace main with test, try other strategies
            if "src" in parts:
                # If there's a src directory but no main, add test after src
                src_idx = parts.index("src")
                if src_idx + 1 < len(parts) and parts[src_idx + 1] != "test":
                    parts.insert(src_idx + 1, "test")
                    replaced = True

        # Replace the filename with the test filename
        parts[-1] = test_filename

        # Join the parts back into a path
        return str(Path(*parts))

    def resolve_absolute(self, target_source_rel_path_str: str) -> Path:
        """
        Determines the absolute output path for the generated test file.

        Args:
            target_source_rel_path_str: Relative path of the source file from repo root.

        Returns:
            The resolved absolute Path object for the output test file.
        """
        rel_path = self.resolve_relative(target_source_rel_path_str)
        return self.repo_root / rel_path
