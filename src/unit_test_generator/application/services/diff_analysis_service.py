"""
Service for analyzing diffs and extracting relevant information for test generation.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DiffAnalysisService:
    """
    Service for analyzing diffs and extracting relevant information for test generation.
    """
    
    def __init__(self):
        """Initializes the DiffAnalysisService."""
        pass
    
    def analyze_diff(self, diff_info: Dict[str, Any], file_content: str) -> Dict[str, Any]:
        """
        Analyzes a diff and extracts relevant information for test generation.
        
        Args:
            diff_info: The diff information from the source control system.
            file_content: The current content of the file.
            
        Returns:
            A dictionary containing analysis results, including:
            - 'changed_methods': List of method names that were changed
            - 'added_methods': List of method names that were added
            - 'modified_methods': List of method names that were modified
            - 'affected_code_blocks': List of code blocks that were affected
            - 'summary': A summary of the changes
        """
        # Initialize result
        result = {
            'changed_methods': [],
            'added_methods': [],
            'modified_methods': [],
            'affected_code_blocks': [],
            'summary': ''
        }
        
        # If this is a new file, all methods are new
        if diff_info['is_new_file']:
            result['summary'] = "New file added"
            return result
        
        # Extract affected lines
        affected_lines = set(diff_info['added_lines'] + diff_info['modified_lines'])
        
        # Split the file content into lines
        lines = file_content.split('\n')
        
        # Extract affected code blocks
        affected_blocks = self._extract_affected_code_blocks(lines, affected_lines)
        result['affected_code_blocks'] = affected_blocks
        
        # Extract method names from affected blocks
        method_names = self._extract_method_names(affected_blocks)
        
        # Categorize methods as added or modified
        for method_name in method_names:
            # Check if the method is entirely new or just modified
            # This is a simplistic approach - in a real implementation, you'd need more sophisticated analysis
            if all(line_num in diff_info['added_lines'] for line_num in method_names[method_name]['line_range']):
                result['added_methods'].append(method_name)
            else:
                result['modified_methods'].append(method_name)
        
        # Combine added and modified methods into changed_methods
        result['changed_methods'] = result['added_methods'] + result['modified_methods']
        
        # Generate a summary
        result['summary'] = self._generate_summary(result)
        
        return result
    
    def _extract_affected_code_blocks(self, lines: List[str], affected_lines: set) -> List[Dict[str, Any]]:
        """
        Extracts affected code blocks from the file content.
        
        Args:
            lines: The file content as a list of lines.
            affected_lines: Set of line numbers that were affected.
            
        Returns:
            A list of dictionaries, each containing:
            - 'start_line': The start line number of the block
            - 'end_line': The end line number of the block
            - 'content': The content of the block
        """
        blocks = []
        current_block = None
        
        for i, line in enumerate(lines, 1):
            if i in affected_lines:
                # Start a new block if we're not already in one
                if current_block is None:
                    current_block = {
                        'start_line': i,
                        'end_line': i,
                        'content': [line]
                    }
                else:
                    # Continue the current block
                    current_block['end_line'] = i
                    current_block['content'].append(line)
            else:
                # If we were in a block, add it to the list and reset
                if current_block is not None:
                    # Add some context lines before and after
                    context_before = max(1, current_block['start_line'] - 3)
                    context_after = min(len(lines), current_block['end_line'] + 3)
                    
                    # Add context lines to the block
                    context_lines_before = lines[context_before-1:current_block['start_line']-1]
                    context_lines_after = lines[current_block['end_line']:context_after]
                    
                    current_block['context_before'] = context_lines_before
                    current_block['context_after'] = context_lines_after
                    current_block['content'] = '\n'.join(current_block['content'])
                    
                    blocks.append(current_block)
                    current_block = None
        
        # Don't forget to add the last block if we're still in one
        if current_block is not None:
            # Add some context lines before and after
            context_before = max(1, current_block['start_line'] - 3)
            context_after = min(len(lines), current_block['end_line'] + 3)
            
            # Add context lines to the block
            context_lines_before = lines[context_before-1:current_block['start_line']-1]
            context_lines_after = lines[current_block['end_line']:context_after]
            
            current_block['context_before'] = context_lines_before
            current_block['context_after'] = context_lines_after
            current_block['content'] = '\n'.join(current_block['content'])
            
            blocks.append(current_block)
        
        return blocks
    
    def _extract_method_names(self, affected_blocks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Extracts method names from affected code blocks.
        
        Args:
            affected_blocks: List of affected code blocks.
            
        Returns:
            A dictionary mapping method names to information about the method.
        """
        method_names = {}
        
        for block in affected_blocks:
            # This is a simplistic approach - in a real implementation, you'd need more sophisticated parsing
            # For Kotlin, look for lines that match method patterns
            content = block['content']
            
            # Look for method declarations
            # This is a very basic regex that won't catch all cases
            import re
            method_matches = re.finditer(r'fun\s+(\w+)\s*\(', content)
            
            for match in method_matches:
                method_name = match.group(1)
                method_names[method_name] = {
                    'line_range': range(block['start_line'], block['end_line'] + 1),
                    'block': block
                }
        
        return method_names
    
    def _generate_summary(self, analysis_result: Dict[str, Any]) -> str:
        """
        Generates a summary of the changes.
        
        Args:
            analysis_result: The analysis result.
            
        Returns:
            A summary string.
        """
        added_count = len(analysis_result['added_methods'])
        modified_count = len(analysis_result['modified_methods'])
        
        if added_count == 0 and modified_count == 0:
            return "No methods were added or modified"
        
        summary_parts = []
        
        if added_count > 0:
            summary_parts.append(f"{added_count} method{'s' if added_count != 1 else ''} added")
        
        if modified_count > 0:
            summary_parts.append(f"{modified_count} method{'s' if modified_count != 1 else ''} modified")
        
        return ", ".join(summary_parts)
