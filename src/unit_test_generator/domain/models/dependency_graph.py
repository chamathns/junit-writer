"""
Dependency graph model for intelligent context building.
"""
import logging
import re
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
import networkx as nx

logger = logging.getLogger(__name__)

class DependencyGraphManager:
    """
    Manages a graph of dependencies between classes in the repository.
    Provides methods for intelligent context building based on architectural layers.
    """
    
    def __init__(self, repository_index: Dict[str, Any], file_system):
        """
        Initialize the dependency graph manager.
        
        Args:
            repository_index: The repository index data
            file_system: File system adapter for reading files
        """
        self.repository_index = repository_index
        self.fs = file_system
        self.repo_root = self._get_repo_root()
        
        # Initialize the dependency graph
        self.dependency_graph = nx.DiGraph()
        
        # Maps for efficient lookups
        self.path_to_symbol_map = {}  # file_path -> fully_qualified_name
        self.symbol_to_path_map = {}  # fully_qualified_name -> file_path
        self.package_to_paths_map = {}  # package -> [file_paths]
        
        # Architectural layer classification
        self.layer_map = {}  # file_path -> layer_name
        
        # Build the graph and maps
        self._build_symbol_maps()
        self._build_dependency_graph()
        self._classify_architectural_layers()
        
        logger.info(f"Dependency graph built with {len(self.dependency_graph.nodes)} nodes and "
                   f"{len(self.dependency_graph.edges)} edges")
    
    def _get_repo_root(self) -> str:
        """Get the repository root path."""
        if self.repository_index and 'repository' in self.repository_index:
            return self.repository_index['repository'].get('root_path', '')
        return ''
    
    def _build_symbol_maps(self):
        """Build maps for efficient symbol and path lookups."""
        if not self.repository_index or 'modules' not in self.repository_index:
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
                            self.path_to_symbol_map[relative_path] = full_class_path
                            self.symbol_to_path_map[full_class_path] = relative_path
                            
                            # Store package mappings
                            if package not in self.package_to_paths_map:
                                self.package_to_paths_map[package] = []
                            self.package_to_paths_map[package].append(relative_path)
                            
                            # Add node to graph
                            self.dependency_graph.add_node(relative_path, 
                                                          symbol=full_class_path,
                                                          package=package,
                                                          class_name=class_name)
                except Exception as e:
                    logger.debug(f"Could not infer package for path: {relative_path}: {e}")
    
    def _build_dependency_graph(self):
        """Build a directed graph of dependencies between classes."""
        # Process each file to extract imports
        for file_path, symbol in self.path_to_symbol_map.items():
            try:
                # Read file content
                abs_path = Path(self.repo_root) / file_path
                content = self.fs.read_file(str(abs_path))
                if not content:
                    continue
                
                # Extract imports
                imports = self._extract_imports(content)
                
                # Add edges for each import that exists in our symbol map
                for imp in imports:
                    if imp in self.symbol_to_path_map:
                        target_path = self.symbol_to_path_map[imp]
                        # Add edge: file_path depends on target_path
                        self.dependency_graph.add_edge(file_path, target_path, type="import")
                    else:
                        # Try partial matches (for cases where we import a package but use specific classes)
                        for sym, path in self.symbol_to_path_map.items():
                            if sym.startswith(imp + ".") or imp.startswith(sym + "."):
                                self.dependency_graph.add_edge(file_path, path, type="partial_import")
                                break
            except Exception as e:
                logger.debug(f"Error processing file {file_path}: {e}")
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements from file content."""
        imports = []
        # Match import statements in Kotlin/Java
        import_pattern = re.compile(r'import\s+([\w.]+)(?:\s+as\s+\w+)?')
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith("import "):
                match = import_pattern.match(line)
                if match:
                    imports.append(match.group(1))
        
        return imports
    
    def _classify_architectural_layers(self):
        """Classify files into architectural layers based on package structure."""
        layer_patterns = {
            "domain": [r'\.domain\.', r'\.model\.', r'\.entity\.'],
            "application": [r'\.service\.', r'\.usecase\.', r'\.application\.'],
            "infrastructure": [r'\.repository\.', r'\.dao\.', r'\.adapter\.', r'\.infrastructure\.'],
            "presentation": [r'\.controller\.', r'\.rest\.', r'\.ui\.', r'\.presentation\.'],
            "dto": [r'\.dto\.', r'\.request\.', r'\.response\.']
        }
        
        for file_path, symbol in self.path_to_symbol_map.items():
            # Default layer
            self.layer_map[file_path] = "unknown"
            
            # Check package against layer patterns
            for layer, patterns in layer_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, symbol, re.IGNORECASE):
                        self.layer_map[file_path] = layer
                        break
                if self.layer_map[file_path] != "unknown":
                    break
    
    def get_dependencies_for_testing(self, source_file: str, max_depth: int = 2) -> List[Tuple[str, float]]:
        """
        Get dependencies needed for testing a source file.
        
        Args:
            source_file: The source file path
            max_depth: Maximum depth for transitive dependencies
            
        Returns:
            List of tuples (file_path, relevance_score)
        """
        if source_file not in self.dependency_graph:
            logger.warning(f"Source file {source_file} not found in dependency graph")
            return []
        
        # Get direct dependencies (outgoing edges)
        direct_deps = list(self.dependency_graph.successors(source_file))
        
        # Get transitive dependencies up to max_depth
        transitive_deps = set()
        current_level = set(direct_deps)
        
        for depth in range(1, max_depth):
            next_level = set()
            for dep in current_level:
                next_deps = list(self.dependency_graph.successors(dep))
                next_level.update(next_deps)
            
            # Remove already processed nodes to avoid cycles
            next_level -= set(direct_deps)
            next_level -= transitive_deps
            
            transitive_deps.update(next_level)
            current_level = next_level
            
            if not current_level:
                break
        
        # Calculate relevance scores
        scored_deps = []
        
        # Direct dependencies have higher scores
        for dep in direct_deps:
            layer = self.layer_map.get(dep, "unknown")
            # DTOs and domain models are most important
            if layer == "dto" or layer == "domain":
                score = 1.0
            # Application services are next
            elif layer == "application":
                score = 0.9
            # Infrastructure components
            elif layer == "infrastructure":
                score = 0.8
            # Other dependencies
            else:
                score = 0.7
            
            scored_deps.append((dep, score))
        
        # Transitive dependencies have lower scores based on depth
        for dep in transitive_deps:
            layer = self.layer_map.get(dep, "unknown")
            # Base score depends on layer
            if layer == "dto" or layer == "domain":
                base_score = 0.8
            elif layer == "application":
                base_score = 0.7
            elif layer == "infrastructure":
                base_score = 0.6
            else:
                base_score = 0.5
            
            # Adjust for depth (deeper = lower score)
            # We don't know exact depth here, but it's > 1
            score = base_score * 0.8  # Apply a penalty for being transitive
            
            scored_deps.append((dep, score))
        
        # Sort by score descending
        scored_deps.sort(key=lambda x: x[1], reverse=True)
        
        return scored_deps
    
    def get_dependents(self, source_file: str, max_depth: int = 1) -> List[Tuple[str, float]]:
        """
        Get classes that depend on the source file.
        
        Args:
            source_file: The source file path
            max_depth: Maximum depth for transitive dependents
            
        Returns:
            List of tuples (file_path, relevance_score)
        """
        if source_file not in self.dependency_graph:
            logger.warning(f"Source file {source_file} not found in dependency graph")
            return []
        
        # Get direct dependents (incoming edges)
        direct_deps = list(self.dependency_graph.predecessors(source_file))
        
        # Calculate relevance scores
        scored_deps = []
        
        for dep in direct_deps:
            layer = self.layer_map.get(dep, "unknown")
            # Test files are most important
            if "test" in dep.lower():
                score = 1.0
            # Application services are next
            elif layer == "application":
                score = 0.9
            # Other dependencies
            else:
                score = 0.7
            
            scored_deps.append((dep, score))
        
        # Sort by score descending
        scored_deps.sort(key=lambda x: x[1], reverse=True)
        
        return scored_deps
    
    def get_layer_context(self, source_file: str, max_files: int = 5) -> List[str]:
        """
        Get context from the same architectural layer.
        
        Args:
            source_file: The source file path
            max_files: Maximum number of files to return
            
        Returns:
            List of file paths in the same layer
        """
        if source_file not in self.layer_map:
            logger.warning(f"Source file {source_file} not found in layer map")
            return []
        
        layer = self.layer_map.get(source_file)
        same_layer_files = [
            path for path, l in self.layer_map.items() 
            if l == layer and path != source_file
        ]
        
        # Try to find files in the same package first
        source_package = None
        if source_file in self.path_to_symbol_map:
            source_symbol = self.path_to_symbol_map[source_file]
            source_package = ".".join(source_symbol.split(".")[:-1])
        
        if source_package and source_package in self.package_to_paths_map:
            same_package_files = [
                path for path in self.package_to_paths_map[source_package]
                if path != source_file
            ]
            
            # Prioritize files from the same package
            result = same_package_files[:max_files]
            
            # If we need more, add from the same layer but different packages
            if len(result) < max_files:
                additional = [
                    path for path in same_layer_files 
                    if path not in same_package_files
                ][:max_files - len(result)]
                
                result.extend(additional)
            
            return result
        
        # If no package match, just return files from the same layer
        return same_layer_files[:max_files]
    
    def get_architectural_context(self, source_file: str) -> Dict[str, List[str]]:
        """
        Get context organized by architectural layers.
        
        Args:
            source_file: The source file path
            
        Returns:
            Dictionary mapping layer names to lists of file paths
        """
        # Get dependencies
        dependencies = self.get_dependencies_for_testing(source_file)
        dep_paths = [path for path, _ in dependencies]
        
        # Organize by layer
        layers = {}
        for path in dep_paths:
            layer = self.layer_map.get(path, "unknown")
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(path)
        
        return layers
