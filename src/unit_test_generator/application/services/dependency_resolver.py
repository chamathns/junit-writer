# src/unit_test_generator/application/services/dependency_resolver.py
import logging
from typing import List, Dict, Tuple, Optional
from pathlib import Path

from unit_test_generator.domain.ports.file_system import FileSystemPort
# Assuming RepositoryStructure model is available if needed,
# but simple index dict might suffice here.

logger = logging.getLogger(__name__)

class DependencyResolverService:
    """
    Resolves parsed imports to project-local file paths using the repository index.
    """
    def __init__(self, file_system: FileSystemPort, config: Dict):
        self.fs = file_system
        self.config = config
        self.index_file_path = config['indexing']['index_file_path']
        self._repository_index: Optional[Dict] = None # Cache for the index

    def _load_repository_index(self) -> Dict:
        """Loads the repository index JSON file."""
        if self._repository_index is None:
            logger.debug(f"Loading repository index from: {self.index_file_path}")
            try:
                # Use FileSystemAdapter's helper if available, otherwise standard read
                if hasattr(self.fs, 'read_json'):
                    self._repository_index = self.fs.read_json(self.index_file_path)
                else:
                    # Fallback if read_json isn't on the port/adapter
                    content = self.fs.read_file(self.index_file_path)
                    import json
                    self._repository_index = json.loads(content)

                if not self._repository_index or 'modules' not in self._repository_index:
                     logger.error(f"Repository index file is empty or invalid: {self.index_file_path}")
                     self._repository_index = {"modules": {}} # Prevent repeated load attempts
                else:
                     logger.info(f"Repository index loaded successfully. Modules: {list(self._repository_index.get('modules', {}).keys())}")

            except Exception as e:
                logger.error(f"Failed to load repository index {self.index_file_path}: {e}", exc_info=True)
                self._repository_index = {"modules": {}} # Prevent repeated load attempts
        return self._repository_index

    def resolve_dependencies(
        self,
        imports: List[str],
        usage_weights: Dict[str, float],
        target_file_module: str # Pass the module of the file being analyzed
    ) -> List[Tuple[str, float]]:
        """
        Resolves imports to relative file paths within the project and sorts by weight.

        Args:
            imports: List of import strings (e.g., "com.example.UserService").
            usage_weights: Dict mapping import strings to usage weights.
            target_file_module: The module name of the source file where imports were found.

        Returns:
            List of tuples: [(relative_path, weight), ...], sorted descending by weight.
        """
        repo_index = self._load_repository_index()
        if not repo_index or not repo_index.get('modules'):
            return []

        resolved_deps = {} # path -> weight

        # Build a lookup map: package.Class -> relative_path
        # This is a simplification; real resolution might need more complex matching
        path_lookup: Dict[str, str] = {}
        for module_data in repo_index['modules'].values():
            for file_info in module_data.get('source_files', []):
                relative_path = file_info.get('relative_path')
                if not relative_path: continue
                # Try to infer package.Class from path (Kotlin/Java specific)
                # e.g., app/src/main/kotlin/com/example/MyClass.kt -> com.example.MyClass
                try:
                    path_obj = Path(relative_path)
                    # Find the start of the package structure after src/.../kotlin/
                    parts = path_obj.parts
                    pkg_start_idx = -1
                    for i, part in enumerate(parts):
                         # Adjust if source_roots config changes
                        if part == 'kotlin' and i > 1 and parts[i-1] == 'main' and parts[i-2] == 'src':
                            pkg_start_idx = i + 1
                            break
                    if pkg_start_idx != -1:
                        package_class = ".".join(parts[pkg_start_idx:]).replace(path_obj.suffix, '')
                        path_lookup[package_class] = relative_path
                except Exception:
                    logger.debug(f"Could not infer package.Class for path: {relative_path}")


        logger.debug(f"Attempting to resolve {len(imports)} imports for file in module '{target_file_module}'.")
        for imp in imports:
            if imp.endswith(".*"): # Skip wildcards for now (complex to resolve)
                logger.debug(f"Skipping wildcard import: {imp}")
                continue

            # Try direct match in lookup
            if imp in path_lookup:
                resolved_path = path_lookup[imp]
                weight = usage_weights.get(imp, 1.0) # Default weight if not found
                # Add only if not already present or if new weight is higher?
                # For now, just add if found.
                if resolved_path not in resolved_deps:
                     resolved_deps[resolved_path] = weight
                     logger.debug(f"Resolved import '{imp}' to path '{resolved_path}' with weight {weight:.2f}")
            else:
                # TODO: Add more sophisticated matching if needed (e.g., relative imports)
                logger.debug(f"Could not resolve import '{imp}' to a project file.")
                pass

        # Sort by weight descending
        sorted_deps = sorted(resolved_deps.items(), key=lambda item: item[1], reverse=True)
        logger.info(f"Resolved {len(sorted_deps)} project-local dependencies.")
        return sorted_deps