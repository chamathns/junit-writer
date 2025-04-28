"""
Models for repository index and dependency resolution.
"""
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class RepositoryIndexManager:
    """
    Manager for repository index operations, providing efficient lookups for dependency resolution.
    """
    
    def __init__(self, repository_index: Dict):
        """
        Initialize the repository index manager.
        
        Args:
            repository_index: The raw repository index data
        """
        self.repository_index = repository_index
        self._package_to_path_map = {}
        self._class_to_path_map = {}
        self._path_to_package_map = {}
        self._package_prefixes = set()
        
        # Build lookup maps for efficient resolution
        self._build_lookup_maps()
    
    def _build_lookup_maps(self):
        """Build lookup maps for efficient dependency resolution."""
        if not self.repository_index or not self.repository_index.get('modules'):
            logger.warning("Repository index is empty or invalid")
            return
            
        for module_name, module_data in self.repository_index['modules'].items():
            for file_info in module_data.get('source_files', []):
                relative_path = file_info.get('relative_path')
                if not relative_path:
                    continue
                    
                # Try to infer package and class from path
                try:
                    path_obj = Path(relative_path)
                    # Find the start of the package structure after src/.../kotlin/
                    parts = path_obj.parts
                    pkg_start_idx = -1
                    for i, part in enumerate(parts):
                        if part in ('kotlin', 'java') and i > 1 and parts[i-1] in ('main', 'test') and parts[i-2] == 'src':
                            pkg_start_idx = i + 1
                            break
                            
                    if pkg_start_idx != -1:
                        # Get package and class name
                        package_parts = parts[pkg_start_idx:-1]
                        class_name = path_obj.stem
                        
                        if package_parts:
                            # Full package path
                            package = ".".join(package_parts)
                            full_class_path = f"{package}.{class_name}"
                            
                            # Store mappings
                            self._package_to_path_map[package] = relative_path
                            self._class_to_path_map[full_class_path] = relative_path
                            self._path_to_package_map[relative_path] = package
                            
                            # Store package prefixes for partial matching
                            current_prefix = ""
                            for part in package_parts:
                                if current_prefix:
                                    current_prefix += "."
                                current_prefix += part
                                self._package_prefixes.add(current_prefix)
                except Exception as e:
                    logger.debug(f"Could not infer package for path: {relative_path}: {e}")
    
    def resolve_symbol_to_path(self, symbol: str) -> Optional[str]:
        """
        Resolve a symbol (class or package) to a file path.
        
        Args:
            symbol: The symbol to resolve (e.g., com.example.MyClass)
            
        Returns:
            The file path if found, None otherwise
        """
        # Direct match for fully qualified class name
        if symbol in self._class_to_path_map:
            return self._class_to_path_map[symbol]
            
        # Direct match for package
        if symbol in self._package_to_path_map:
            return self._package_to_path_map[symbol]
            
        # Try to find the closest package match
        matching_packages = []
        for pkg_prefix in self._package_prefixes:
            if symbol.startswith(pkg_prefix + "."):
                matching_packages.append(pkg_prefix)
        
        if matching_packages:
            # Find the longest matching package
            best_match = max(matching_packages, key=len)
            return self._package_to_path_map.get(best_match)
            
        # Try to extract package and class name
        parts = symbol.split(".")
        if len(parts) > 1:
            # Try different combinations of package and class
            for i in range(len(parts) - 1, 0, -1):
                package = ".".join(parts[:i])
                class_name = parts[i]
                
                # Check if this package exists
                if package in self._package_to_path_map:
                    # Look for files in this package that might match the class
                    package_path = self._package_to_path_map[package]
                    package_dir = Path(package_path).parent
                    
                    # Construct potential file path
                    potential_path = package_dir / f"{class_name}.kt"
                    if str(potential_path) in self._path_to_package_map:
                        return str(potential_path)
        
        return None
    
    def is_repository_symbol(self, symbol: str) -> bool:
        """
        Check if a symbol belongs to the repository.
        
        Args:
            symbol: The symbol to check
            
        Returns:
            True if the symbol belongs to the repository, False otherwise
        """
        # Check if the symbol or any prefix of it is in our maps
        if symbol in self._class_to_path_map or symbol in self._package_to_path_map:
            return True
            
        # Check if it starts with any known package prefix
        for prefix in self._package_prefixes:
            if symbol.startswith(prefix + "."):
                return True
                
        return False
    
    def get_all_paths_for_package(self, package_prefix: str) -> List[str]:
        """
        Get all file paths for a package prefix.
        
        Args:
            package_prefix: The package prefix to search for
            
        Returns:
            List of file paths
        """
        paths = []
        for full_class_path, path in self._class_to_path_map.items():
            if full_class_path.startswith(package_prefix + "."):
                paths.append(path)
        return paths
