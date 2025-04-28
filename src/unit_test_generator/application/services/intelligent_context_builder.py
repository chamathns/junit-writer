"""
Intelligent context builder for comprehensive test generation.
"""
import logging
from typing import Dict, List, Set, Tuple, Any
from pathlib import Path

from unit_test_generator.domain.models.dependency_graph import DependencyGraphManager
from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort

logger = logging.getLogger(__name__)

class IntelligentContextBuilder:
    """
    Builds comprehensive context for test generation based on dependency graph analysis.
    """
    
    def __init__(self, 
                dependency_graph: DependencyGraphManager, 
                llm_service: LLMServicePort, 
                file_system: FileSystemPort, 
                config: Dict[str, Any]):
        """
        Initialize the intelligent context builder.
        
        Args:
            dependency_graph: Dependency graph manager
            llm_service: LLM service for code analysis
            file_system: File system adapter for reading files
            config: Application configuration
        """
        self.dependency_graph = dependency_graph
        self.llm_service = llm_service
        self.fs = file_system
        self.config = config
        self.repo_root = Path(config['repository']['root_path'])
        
        # Context building parameters
        self.max_context_tokens = config.get('generation', {}).get('context_max_tokens', 300000)
        self.max_dependencies = config.get('generation', {}).get('context_max_dependency_files', 15)
        self.max_layer_examples = 3
    
    def build_context(self, source_file: str, source_content: str, imports: List[str]) -> Dict[str, Any]:
        """
        Build comprehensive context for test generation.
        
        Args:
            source_file: Path to the source file
            source_content: Content of the source file
            imports: List of imports extracted from the source file
            
        Returns:
            Context payload for test generation
        """
        logger.info(f"Building intelligent context for {source_file}")
        
        # Initialize context payload
        context = {
            "target_file_path": source_file,
            "target_file_content": source_content,
            "similar_files_with_tests": [],
            "dependency_files": [],
            "language": self.config.get('generation', {}).get('target_language', 'Kotlin'),
            "framework": self.config.get('generation', {}).get('target_framework', 'JUnit5 with MockK')
        }
        
        # Track token usage
        current_token_count = self._estimate_tokens(source_content)
        
        # Get architectural context
        arch_context = self.dependency_graph.get_architectural_context(source_file)
        
        # Add domain model context first (most important)
        domain_files = arch_context.get("domain", []) + arch_context.get("dto", [])
        dependencies_added = 0
        
        for file_path in domain_files:
            if dependencies_added >= self.max_dependencies:
                break
                
            try:
                file_content = self._read_file_content(file_path)
                if not file_content:
                    continue
                    
                # Check token limit
                added_tokens = self._estimate_tokens(file_content)
                if current_token_count + added_tokens > self.max_context_tokens:
                    logger.warning(f"Token limit reached. Skipping domain file: {file_path}")
                    continue
                    
                # Add to context
                context["dependency_files"].append({
                    "dependency_path": file_path,
                    "content": file_content,
                    "layer": "domain"
                })
                
                dependencies_added += 1
                current_token_count += added_tokens
                logger.info(f"Added domain model file: {file_path}")
            except Exception as e:
                logger.warning(f"Error adding domain file {file_path}: {e}")
        
        # Add application service dependencies
        app_files = arch_context.get("application", [])
        for file_path in app_files:
            if dependencies_added >= self.max_dependencies:
                break
                
            try:
                file_content = self._read_file_content(file_path)
                if not file_content:
                    continue
                    
                # Check token limit
                added_tokens = self._estimate_tokens(file_content)
                if current_token_count + added_tokens > self.max_context_tokens:
                    logger.warning(f"Token limit reached. Skipping application file: {file_path}")
                    continue
                    
                # Add to context
                context["dependency_files"].append({
                    "dependency_path": file_path,
                    "content": file_content,
                    "layer": "application"
                })
                
                dependencies_added += 1
                current_token_count += added_tokens
                logger.info(f"Added application service file: {file_path}")
            except Exception as e:
                logger.warning(f"Error adding application file {file_path}: {e}")
        
        # Add infrastructure dependencies
        infra_files = arch_context.get("infrastructure", [])
        for file_path in infra_files:
            if dependencies_added >= self.max_dependencies:
                break
                
            try:
                file_content = self._read_file_content(file_path)
                if not file_content:
                    continue
                    
                # Check token limit
                added_tokens = self._estimate_tokens(file_content)
                if current_token_count + added_tokens > self.max_context_tokens:
                    logger.warning(f"Token limit reached. Skipping infrastructure file: {file_path}")
                    continue
                    
                # Add to context
                context["dependency_files"].append({
                    "dependency_path": file_path,
                    "content": file_content,
                    "layer": "infrastructure"
                })
                
                dependencies_added += 1
                current_token_count += added_tokens
                logger.info(f"Added infrastructure file: {file_path}")
            except Exception as e:
                logger.warning(f"Error adding infrastructure file {file_path}: {e}")
        
        # Add other dependencies if we still have room
        other_files = arch_context.get("unknown", []) + arch_context.get("presentation", [])
        for file_path in other_files:
            if dependencies_added >= self.max_dependencies:
                break
                
            try:
                file_content = self._read_file_content(file_path)
                if not file_content:
                    continue
                    
                # Check token limit
                added_tokens = self._estimate_tokens(file_content)
                if current_token_count + added_tokens > self.max_context_tokens:
                    logger.warning(f"Token limit reached. Skipping other file: {file_path}")
                    continue
                    
                # Add to context
                context["dependency_files"].append({
                    "dependency_path": file_path,
                    "content": file_content,
                    "layer": "other"
                })
                
                dependencies_added += 1
                current_token_count += added_tokens
                logger.info(f"Added other dependency file: {file_path}")
            except Exception as e:
                logger.warning(f"Error adding other file {file_path}: {e}")
        
        # Add similar files with tests (if we have RAG results, this would be added elsewhere)
        # This is just a placeholder for integration with the existing RAG system
        
        logger.info(f"Built context with {dependencies_added} dependency files. "
                   f"Token count: {current_token_count}/{self.max_context_tokens}")
        
        return context
    
    def _read_file_content(self, file_path: str) -> str:
        """Read content of a file."""
        try:
            abs_path = self.repo_root / file_path
            content = self.fs.read_file(str(abs_path))
            return content
        except Exception as e:
            logger.debug(f"Error reading file {file_path}: {e}")
            return ""
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in a text."""
        # Simple estimation: 1 token ≈ 4 characters for code
        return len(text) // 4
