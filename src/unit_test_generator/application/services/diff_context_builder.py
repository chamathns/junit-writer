"""
Service for building context for diff-based test generation.
"""
import logging
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

from unit_test_generator.domain.ports.source_control import SourceControlPort
from unit_test_generator.domain.ports.file_system import FileSystemPort

logger = logging.getLogger(__name__)

class DiffContextBuilder:
    """
    Service for building context for diff-based test generation.
    """
    
    def __init__(
        self,
        source_control: SourceControlPort,
        file_system: FileSystemPort,
        repo_root: Path,
    ):
        """
        Initializes the DiffContextBuilder.
        
        Args:
            source_control: The source control adapter.
            file_system: The file system adapter.
            repo_root: The root directory of the repository.
        """
        self.source_control = source_control
        self.file_system = file_system
        self.repo_root = repo_root
    
    def build_diff_context(
        self,
        commit_hash: str,
        file_path: str,
        existing_test_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Builds context for diff-based test generation.
        
        Args:
            commit_hash: The commit hash.
            file_path: The path of the file to generate tests for.
            existing_test_file: The path of the existing test file, if any.
            
        Returns:
            A dictionary containing the context for diff-based test generation.
        """
        logger.info(f"Building diff context for {file_path} at commit {commit_hash}")
        
        # Get the file content at the commit
        target_file_content = self.source_control.get_file_content_at_commit(commit_hash, file_path)
        
        # Get the precise diff
        diff_info = self.source_control.get_precise_file_diff(commit_hash, file_path)
        
        # Get new dependencies
        new_dependencies = self.source_control.get_new_dependencies(commit_hash, file_path)
        
        # Read the existing test file if available
        existing_test_content = ""
        if existing_test_file:
            abs_test_file_path = self.repo_root / existing_test_file
            if abs_test_file_path.exists():
                existing_test_content = self.file_system.read_file(str(abs_test_file_path))
                logger.info(f"Found existing test file: {existing_test_file}")
        
        # Format the added code blocks
        added_code_blocks = self._format_code_blocks(diff_info.get('added_code_blocks', []))
        
        # Format the modified code blocks
        modified_code_blocks = self._format_modified_code_blocks(diff_info.get('modified_code_blocks', []))
        
        # Format the new imports
        new_imports = self._format_imports(diff_info.get('new_imports', []))
        
        # Build the context
        context = {
            'target_file_content': target_file_content,
            'diff_content': diff_info.get('content', ''),
            'added_code_blocks': added_code_blocks,
            'modified_code_blocks': modified_code_blocks,
            'new_imports': new_imports,
            'existing_test_code': existing_test_content,
            'is_new_file': diff_info.get('is_new_file', False),
            'update_mode': bool(existing_test_content),
            'new_dependencies': list(new_dependencies),
        }
        
        return context
    
    def _format_code_blocks(self, code_blocks: List[Dict[str, Any]]) -> str:
        """
        Formats code blocks for inclusion in the prompt.
        
        Args:
            code_blocks: A list of code blocks.
            
        Returns:
            A formatted string representation of the code blocks.
        """
        if not code_blocks:
            return "No added code blocks."
        
        result = []
        for i, block in enumerate(code_blocks, 1):
            content = block.get('content', '')
            start_line = block.get('start_line', 0)
            end_line = block.get('end_line', 0)
            context_before = block.get('context_before', '')
            context_after = block.get('context_after', '')
            
            block_str = f"### Added Block {i} (Lines {start_line}-{end_line}):\n"
            
            if context_before:
                block_str += "Context before:\n```kotlin\n" + context_before + "\n```\n"
            
            block_str += "Added code:\n```kotlin\n" + content + "\n```\n"
            
            if context_after:
                block_str += "Context after:\n```kotlin\n" + context_after + "\n```\n"
            
            result.append(block_str)
        
        return "\n".join(result)
    
    def _format_modified_code_blocks(self, code_blocks: List[Dict[str, Any]]) -> str:
        """
        Formats modified code blocks for inclusion in the prompt.
        
        Args:
            code_blocks: A list of modified code blocks.
            
        Returns:
            A formatted string representation of the modified code blocks.
        """
        if not code_blocks:
            return "No modified code blocks."
        
        result = []
        for i, block in enumerate(code_blocks, 1):
            old_content = block.get('old_content', '')
            new_content = block.get('new_content', '')
            start_line = block.get('start_line', 0)
            end_line = block.get('end_line', 0)
            context_before = block.get('context_before', '')
            context_after = block.get('context_after', '')
            
            block_str = f"### Modified Block {i} (Lines {start_line}-{end_line}):\n"
            
            if context_before:
                block_str += "Context before:\n```kotlin\n" + context_before + "\n```\n"
            
            block_str += "Old code:\n```kotlin\n" + old_content + "\n```\n"
            block_str += "New code:\n```kotlin\n" + new_content + "\n```\n"
            
            if context_after:
                block_str += "Context after:\n```kotlin\n" + context_after + "\n```\n"
            
            result.append(block_str)
        
        return "\n".join(result)
    
    def _format_imports(self, imports: List[str]) -> str:
        """
        Formats imports for inclusion in the prompt.
        
        Args:
            imports: A list of import statements.
            
        Returns:
            A formatted string representation of the imports.
        """
        if not imports:
            return "No new imports."
        
        return "```kotlin\n" + "\n".join(imports) + "\n```"
