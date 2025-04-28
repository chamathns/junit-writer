# src/unit_test_generator/application/services/dependency_resolution_service.py
"""
Service for resolving dependencies for errors.
"""
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from unit_test_generator.domain.ports.error_parser import ParsedError
from unit_test_generator.domain.ports.error_analysis import DependencyResolutionPort
from unit_test_generator.domain.models.error_analysis import DependencyContext, DependencyFile
from unit_test_generator.domain.ports.file_system import FileSystemPort

logger = logging.getLogger(__name__)

class DependencyResolutionService(DependencyResolutionPort):
    """Service for resolving dependencies for errors."""

    def __init__(self,
                file_system: FileSystemPort,
                config: Dict[str, Any]):
        """
        Initialize the service.

        Args:
            file_system: File system adapter
            config: Application configuration
        """
        self.fs = file_system
        self.config = config
        self.index_file_path = config['indexing']['index_file_path']
        self._repository_index: Optional[Dict] = None

    def resolve_dependencies(self,
                           error: ParsedError,
                           source_file_path: str,
                           test_file_path: str) -> DependencyContext:
        """
        Resolves dependencies relevant to an error.

        Args:
            error: The parsed error
            source_file_path: Path to the source file
            test_file_path: Path to the test file

        Returns:
            Context of dependencies for the error
        """
        logger.info(f"Resolving dependencies for error in {source_file_path}")

        # Extract symbols from error
        symbols = list(error.involved_symbols) if error.involved_symbols else []
        logger.info(f"Extracted {len(symbols)} symbols from error: {symbols}")

        # If no symbols are explicitly mentioned, try to infer from error message
        if not symbols and error.message:
            inferred_symbols = self._infer_symbols_from_message(error.message)
            symbols.extend(inferred_symbols)
            logger.info(f"Inferred {len(inferred_symbols)} symbols from error message: {inferred_symbols}")

        # If still no symbols, try to extract from the source file path
        if not symbols and source_file_path:
            # Extract the class name from the file path
            import os
            file_name = os.path.basename(source_file_path)
            class_name = None
            if file_name.endswith('.kt'):
                class_name = file_name[:-3]
                symbols.append(class_name)
                logger.info(f"Extracted class name from file path: {class_name}")

            # Also add the package name if we can infer it
            package_match = None
            try:
                content = self.fs.read_file(source_file_path)
                import re
                package_match = re.search(r'package\s+([\w.]+)', content)
            except Exception as e:
                logger.warning(f"Could not read source file to extract package: {e}")

            if package_match:
                package_name = package_match.group(1)
                logger.info(f"Extracted package name from source file: {package_name}")
                if class_name:
                    fully_qualified_name = f"{package_name}.{class_name}"
                    symbols.append(fully_qualified_name)
                    logger.info(f"Added fully qualified class name: {fully_qualified_name}")
                symbols.append(package_name)

        # If we have a test file path, also try to extract symbols from it
        if not symbols and test_file_path:
            try:
                test_content = self.fs.read_file(test_file_path)
                # Extract imports from the test file
                import re
                imports = re.findall(r'import\s+([\w.]+)', test_content)
                symbols.extend(imports)

                # Extract class names from the test file
                class_names = re.findall(r'class\s+([A-Z][\w]+)', test_content)
                symbols.extend(class_names)
            except Exception as e:
                logger.warning(f"Could not read test file to extract symbols: {e}")

        # Determine target module from file path
        target_module = Path(source_file_path).parts[0] if Path(source_file_path).parts else "unknown"

        # Create weights (all equal for now)
        weights = {symbol: 1.0 for symbol in symbols}
        logger.info(f"Created weights for {len(symbols)} symbols: {weights}")

        # Resolve primary dependencies
        primary_deps = self._resolve_symbols_to_files(symbols, weights, target_module)
        logger.info(f"Resolved {len(primary_deps)} primary dependencies: {primary_deps}")

        # Extract imported symbols from primary dependencies
        imported_symbols = self._extract_imported_symbols(primary_deps)

        # Resolve secondary dependencies (dependencies of dependencies)
        secondary_weights = {symbol: 0.5 for symbol in imported_symbols}
        secondary_deps = self._resolve_symbols_to_files(imported_symbols, secondary_weights, target_module)

        # Load the content of primary dependencies
        primary_dep_paths = [path for path, _ in primary_deps]

        # Always add the source file itself as a dependency
        if source_file_path:
            if source_file_path not in primary_dep_paths:
                logger.info(f"Adding source file {source_file_path} as dependency")
                primary_dep_paths.append(source_file_path)
                primary_deps.append((source_file_path, 1.0))

            # Also try to find the corresponding test file if it exists
            test_file_path_guess = source_file_path.replace('/main/', '/test/').replace('.kt', 'Test.kt')
            logger.info(f"Looking for existing test file at {test_file_path_guess}")
            try:
                if self.fs.file_exists(test_file_path_guess) and test_file_path_guess not in primary_dep_paths:
                    logger.info(f"Found existing test file {test_file_path_guess}")
                    primary_dep_paths.append(test_file_path_guess)
                    primary_deps.append((test_file_path_guess, 0.9))
            except Exception as e:
                logger.warning(f"Could not check for existing test file: {e}")

            # Add all files in the same directory as the source file
            source_dir = os.path.dirname(source_file_path)
            logger.info(f"Adding all files in the same directory: {source_dir}")
            try:
                files = self.fs.list_files(source_dir)
                logger.info(f"Found {len(files)} files in {source_dir}")
                for file in files:
                    if file.endswith('.kt') and file != source_file_path and file not in primary_dep_paths:
                        logger.info(f"Adding related file {file} from same package")
                        primary_dep_paths.append(file)
                        primary_deps.append((file, 0.8))
            except Exception as e:
                logger.warning(f"Could not list files in {source_dir}: {e}")

        # If no dependencies were found, add some common dependencies
        if not primary_deps:
            logger.warning("No dependencies found. Adding common dependencies.")

            # Try to find related files in the same package
            if source_file_path:
                source_dir = os.path.dirname(source_file_path)
                logger.info(f"Looking for related files in {source_dir}")
                try:
                    files = self.fs.list_files(source_dir)
                    logger.info(f"Found {len(files)} files in {source_dir}: {files}")
                    for file in files:
                        if file.endswith('.kt') and file != source_file_path and file not in primary_dep_paths:
                            logger.info(f"Adding related file {file} from same package")
                            primary_dep_paths.append(file)
                            primary_deps.append((file, 0.8))
                except Exception as e:
                    logger.warning(f"Could not list files in {source_dir}: {e}")

        primary_dep_files = self.load_dependency_content(primary_dep_paths)

        # Set relevance scores from the resolved dependencies
        for dep_file in primary_dep_files:
            for path, weight in primary_deps:
                if dep_file.path == path:
                    dep_file.relevance_score = weight
                    break

        # Load the content of secondary dependencies
        secondary_dep_paths = [path for path, _ in secondary_deps]
        secondary_dep_files = self.load_dependency_content(secondary_dep_paths)

        # Set relevance scores from the resolved dependencies
        for dep_file in secondary_dep_files:
            for path, weight in secondary_deps:
                if dep_file.path == path:
                    dep_file.relevance_score = weight
                    break

        # Add the test file itself as a dependency if it exists and isn't already included
        if test_file_path and test_file_path not in primary_dep_paths:
            try:
                test_content = self.fs.read_file(test_file_path)
                test_dep = DependencyFile(
                    path=test_file_path,
                    content=test_content,
                    relevance_score=1.0,
                    is_test_file=True
                )
                primary_dep_files.append(test_dep)
                logger.info(f"Added test file {test_file_path} as dependency")
            except Exception as e:
                logger.warning(f"Could not load test file {test_file_path}: {e}")

        # If still no dependencies, create a generic dependency with the error information
        if not primary_dep_files:
            logger.warning("No dependencies found or loaded. Creating a generic dependency with error information.")
            generic_dep = DependencyFile(
                path="error_info.txt",
                content=f"Error message: {error.message}\nError type: {error.error_type}\nFile path: {error.file_path}\nLine number: {error.line_number}\nInvolved symbols: {error.involved_symbols}",
                relevance_score=0.5,
                is_test_file=False
            )
            primary_dep_files.append(generic_dep)

        # Create dependency context
        return DependencyContext(
            primary_dependencies=primary_dep_files,
            secondary_dependencies=secondary_dep_files,
            imported_symbols=imported_symbols,
            used_symbols=symbols,
            error_related_symbols=list(error.involved_symbols)
        )

    def load_dependency_content(self, dependency_paths: List[str]) -> List[DependencyFile]:
        """
        Loads the content of dependency files.

        Args:
            dependency_paths: Paths to dependency files

        Returns:
            List of DependencyFile objects with content loaded
        """
        logger.info(f"Loading content for {len(dependency_paths)} dependencies")

        dependency_files = []
        for path in dependency_paths:
            try:
                content = self.fs.read_file(path)

                # Extract symbols and imports from the file
                symbols = self.extract_symbols_from_file(path, content)
                imports = self._extract_imports_from_content(content)

                # Determine if this is a test file
                is_test_file = 'test' in path.lower() or path.lower().endswith('test.kt')

                # Create a DependencyFile object
                dep_file = DependencyFile(
                    path=path,
                    content=content,
                    relevance_score=1.0,  # Default score, will be updated later
                    is_test_file=is_test_file,
                    symbols=symbols,
                    imports=imports
                )

                dependency_files.append(dep_file)
                logger.debug(f"Loaded content for {path} with {len(symbols)} symbols")
            except Exception as e:
                logger.error(f"Error loading content for {path}: {e}")
                # Create a placeholder dependency file
                dep_file = DependencyFile(
                    path=path,
                    content=f"// Error loading content: {str(e)}",
                    relevance_score=0.1  # Low relevance for failed loads
                )
                dependency_files.append(dep_file)

        return dependency_files

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

    def _infer_symbols_from_message(self, message: str) -> List[str]:
        """Infers symbols from an error message."""
        # Simple extraction of potential class names from error message
        # This is a basic implementation - could be improved with more sophisticated NLP
        words = message.split()
        potential_symbols = [word for word in words
                           if word and word[0].isupper() and not word.isupper()]
        return list(set(potential_symbols))  # Remove duplicates

    def _resolve_symbols_to_files(self,
                                symbols: List[str],
                                weights: Dict[str, float],
                                target_module: str) -> List[Tuple[str, float]]:
        """Resolves symbols to file paths with weights."""
        logger.info(f"Resolving {len(symbols)} symbols to files in module {target_module}")
        repo_index = self._load_repository_index()
        if not repo_index or not repo_index.get('modules'):
            logger.warning("Repository index is empty or has no modules")
            return []

        resolved_deps = {}  # path -> weight

        # Build a lookup map: package.Class -> relative_path
        path_lookup: Dict[str, str] = {}
        module_count = len(repo_index['modules'])
        logger.info(f"Building lookup map from {module_count} modules")

        for module_name, module_data in repo_index['modules'].items():
            source_files_count = len(module_data.get('source_files', []))
            logger.info(f"Module {module_name} has {source_files_count} source files")

            for file_info in module_data.get('source_files', []):
                relative_path = file_info.get('relative_path')
                if not relative_path:
                    continue

                # Try to infer package.Class from path (Kotlin/Java specific)
                try:
                    path_obj = Path(relative_path)
                    # Find the start of the package structure after src/.../kotlin/
                    parts = path_obj.parts
                    pkg_start_idx = -1
                    for i, part in enumerate(parts):
                        if part == 'kotlin' and i > 1 and parts[i-1] == 'main' and parts[i-2] == 'src':
                            pkg_start_idx = i + 1
                            break
                    if pkg_start_idx != -1:
                        package_class = ".".join(parts[pkg_start_idx:]).replace(path_obj.suffix, '')
                        path_lookup[package_class] = relative_path
                        logger.debug(f"Added lookup: {package_class} -> {relative_path}")
                except Exception:
                    logger.debug(f"Could not infer package.Class for path: {relative_path}")

        # Resolve symbols to paths
        logger.info(f"Resolving {len(symbols)} symbols using lookup map with {len(path_lookup)} entries")
        for symbol in symbols:
            if symbol.endswith(".*"):  # Skip wildcards for now
                logger.debug(f"Skipping wildcard import: {symbol}")
                continue

            # Try direct match in lookup
            if symbol in path_lookup:
                resolved_path = path_lookup[symbol]
                weight = weights.get(symbol, 1.0)
                if resolved_path not in resolved_deps:
                    resolved_deps[resolved_path] = weight
                    logger.info(f"Resolved symbol '{symbol}' to path '{resolved_path}' with weight {weight:.2f}")
            else:
                # Try partial match
                partial_matches = 0
                for package_class, path in path_lookup.items():
                    if symbol in package_class:
                        partial_matches += 1
                        weight = weights.get(symbol, 0.5) * 0.8  # Lower weight for partial match
                        if path not in resolved_deps or weight > resolved_deps[path]:
                            resolved_deps[path] = weight
                            logger.info(f"Partially resolved symbol '{symbol}' to path '{path}' with weight {weight:.2f}")

                if partial_matches == 0:
                    logger.warning(f"Could not resolve symbol: {symbol}")

        # Sort by weight descending
        sorted_deps = sorted(resolved_deps.items(), key=lambda item: item[1], reverse=True)
        logger.info(f"Resolved {len(sorted_deps)} dependencies for symbols")
        return sorted_deps

    def _extract_imported_symbols(self, dependencies: List[Tuple[str, float]]) -> List[str]:
        """Extracts imported symbols from dependencies."""
        imported_symbols = []
        for dep_path, _ in dependencies:
            try:
                content = self.fs.read_file(dep_path)
                imports = self._extract_imports_from_content(content)
                imported_symbols.extend(imports)
            except Exception as e:
                logger.error(f"Error extracting imports from {dep_path}: {e}")

        return list(set(imported_symbols))  # Remove duplicates

    def _extract_imports_from_content(self, content: str) -> List[str]:
        """Extracts import statements from file content."""
        # Simple regex-based extraction of imports
        import re
        import_pattern = re.compile(r'import\s+([\w.]+)(?:\s+as\s+[\w]+)?')
        matches = import_pattern.findall(content)
        return matches

    def find_related_test_files(self, source_file_path: str) -> List[str]:
        """Finds test files related to a source file."""
        logger.info(f"Finding related test files for {source_file_path}")

        related_tests = []

        # Convert source path to potential test path
        if '/main/' in source_file_path:
            potential_test_path = source_file_path.replace('/main/', '/test/')
            if not potential_test_path.endswith('Test.kt'):
                # Remove .kt extension and add Test.kt
                if potential_test_path.endswith('.kt'):
                    potential_test_path = potential_test_path[:-3] + 'Test.kt'
                else:
                    potential_test_path = potential_test_path + 'Test.kt'

            # Check if the potential test file exists
            try:
                if self.fs.file_exists(potential_test_path):
                    related_tests.append(potential_test_path)
                    logger.debug(f"Found related test file: {potential_test_path}")
            except Exception as e:
                logger.warning(f"Error checking for test file {potential_test_path}: {e}")

        # Use repository index to find other potential test files
        repo_index = self._load_repository_index()
        if repo_index and repo_index.get('modules'):
            # Extract class name from source file path
            import os
            class_name = os.path.basename(source_file_path)
            if class_name.endswith('.kt'):
                class_name = class_name[:-3]

            # Search for test files that might reference this class
            for module_data in repo_index['modules'].values():
                for file_info in module_data.get('test_files', []):
                    test_path = file_info.get('relative_path')
                    if not test_path:
                        continue

                    # Check if the test file name suggests it's related
                    if class_name in test_path or class_name + 'Test' in test_path:
                        if test_path not in related_tests:
                            related_tests.append(test_path)
                            logger.debug(f"Found potential related test file: {test_path}")

        return related_tests

    def extract_symbols_from_file(self, file_path: str, file_content: str) -> List[str]:
        """Extracts symbols (classes, methods, etc.) from a file."""
        symbols = []

        # Extract package name
        import re
        package_match = re.search(r'package\s+([\w.]+)', file_content)
        package_name = package_match.group(1) if package_match else ''

        # Extract class names
        class_pattern = re.compile(r'\b(?:class|interface|object|enum class)\s+([A-Z][\w]+)')
        class_matches = class_pattern.findall(file_content)

        # Add fully qualified class names
        for class_name in class_matches:
            if package_name:
                symbols.append(f"{package_name}.{class_name}")
            else:
                symbols.append(class_name)

        # Extract function names (only top-level functions)
        func_pattern = re.compile(r'\bfun\s+([a-z][\w]+)\s*\(')
        func_matches = func_pattern.findall(file_content)

        # Add fully qualified function names for top-level functions
        for func_name in func_matches:
            if package_name:
                symbols.append(f"{package_name}.{func_name}")
            else:
                symbols.append(func_name)

        return symbols
