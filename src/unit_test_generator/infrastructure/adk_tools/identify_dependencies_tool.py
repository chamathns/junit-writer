"""
ADK Tool for identifying and fetching missing dependencies.
"""
import logging
import json
from typing import Dict, Any, List
from pathlib import Path

from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.dependency_resolver import DependencyResolverPort
from unit_test_generator.infrastructure.adk_tools.base import JUnitWriterTool

logger = logging.getLogger(__name__)

class IdentifyDependenciesTool(JUnitWriterTool):
    """Tool for identifying and fetching missing dependencies."""

    def __init__(self, llm_service: LLMServicePort, dependency_resolver: DependencyResolverPort, config: Dict[str, Any]):
        """
        Initialize the IdentifyDependenciesTool.

        Args:
            llm_service: An implementation of LLMServicePort
            dependency_resolver: An implementation of DependencyResolverPort
            config: Application configuration
        """
        super().__init__(
            name="identify_dependencies",
            description="Identifies and fetches missing dependencies based on error analysis."
        )
        self.llm_service = llm_service
        self.dependency_resolver = dependency_resolver
        self.config = config

    def _execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool to identify and fetch dependencies.

        Args:
            parameters: Dictionary containing:
                - error_analysis: Analysis of errors from the AnalyzeErrorsTool
                - test_file_path: Path to the test file
                - target_file_path: Path to the target file

        Returns:
            Dictionary containing:
                - dependencies: Dictionary of dependencies
                - success: Boolean indicating if dependencies were identified
        """
        # Extract parameters
        error_analysis = parameters.get("error_analysis", {})
        test_file_path = parameters.get("test_file_path")
        target_file_path = parameters.get("target_file_path")

        # Check required parameters
        if not error_analysis:
            raise ValueError("Missing required parameter: error_analysis")
        if not test_file_path:
            raise ValueError("Missing required parameter: test_file_path")
        if not target_file_path:
            raise ValueError("Missing required parameter: target_file_path")

        # Extract missing dependencies from the error analysis
        missing_dependencies = error_analysis.get("missing_dependencies", [])
        
        # If we don't have missing dependencies, try to extract them from the root causes
        if not missing_dependencies:
            root_causes = error_analysis.get("root_causes", [])
            for root_cause in root_causes:
                description = root_cause.get("description", "")
                if "import" in description.lower() or "missing" in description.lower() or "not found" in description.lower():
                    # Try to extract the missing dependency from the description
                    missing_dependencies.append({
                        "type": "IMPORT",
                        "name": self._extract_symbol_from_description(description),
                        "package": "unknown",
                        "importance": "HIGH"
                    })

        # If we still don't have missing dependencies, try to extract them from the test issues
        if not missing_dependencies:
            test_issues = error_analysis.get("test_issues", [])
            for issue in test_issues:
                description = issue.get("description", "")
                if "import" in description.lower() or "missing" in description.lower() or "not found" in description.lower():
                    # Try to extract the missing dependency from the description
                    missing_dependencies.append({
                        "type": "IMPORT",
                        "name": self._extract_symbol_from_description(description),
                        "package": "unknown",
                        "importance": "HIGH"
                    })

        # If we still don't have missing dependencies, try to extract them from the recommended fixes
        if not missing_dependencies:
            recommended_fixes = error_analysis.get("recommended_fixes", [])
            for fix in recommended_fixes:
                description = fix.get("description", "")
                code_after = fix.get("code_after", "")
                if "import" in description.lower() or "import" in code_after.lower():
                    # Try to extract the missing dependency from the code_after
                    missing_dependencies.append({
                        "type": "IMPORT",
                        "name": self._extract_symbol_from_code(code_after),
                        "package": "unknown",
                        "importance": "HIGH"
                    })

        # If we still don't have missing dependencies, return an empty result
        if not missing_dependencies:
            logger.info("No missing dependencies identified")
            return {
                "success": False,
                "message": "No missing dependencies identified",
                "dependencies": {}
            }

        # Extract symbols from missing dependencies
        symbols = []
        for dep in missing_dependencies:
            name = dep.get("name")
            if name:
                symbols.append(name)

        # If we don't have any symbols, return an empty result
        if not symbols:
            logger.info("No symbols identified from missing dependencies")
            return {
                "success": False,
                "message": "No symbols identified from missing dependencies",
                "dependencies": {}
            }

        # Determine target module from file path
        target_module = Path(target_file_path).parts[0] if Path(target_file_path).parts else "unknown"

        # Create weights (all equal for now)
        weights = {symbol: 1.0 for symbol in symbols}

        # Resolve dependencies
        try:
            dependencies = self.dependency_resolver.resolve_dependencies(symbols, weights, target_module)
            logger.info(f"Resolved {len(dependencies)} dependencies")

            # Convert dependencies to a dictionary
            dependency_dict = {}
            for dep_path, score in dependencies:
                try:
                    # Read the dependency file
                    with open(dep_path, "r") as f:
                        content = f.read()
                    
                    # Add the dependency to the dictionary
                    dependency_dict[dep_path] = {
                        "path": dep_path,
                        "content": content,
                        "relevance_score": score
                    }
                except Exception as e:
                    logger.error(f"Error reading dependency file {dep_path}: {e}", exc_info=True)

            return {
                "success": True,
                "dependencies": dependency_dict
            }
        except Exception as e:
            logger.error(f"Error resolving dependencies: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error resolving dependencies: {e}",
                "dependencies": {}
            }

    def _extract_symbol_from_description(self, description: str) -> str:
        """
        Extract a symbol from a description.

        Args:
            description: Description of an error or issue

        Returns:
            Extracted symbol or empty string
        """
        # Look for patterns like "Cannot resolve symbol X" or "Class X not found"
        import re
        
        # Try to match "Cannot resolve symbol X"
        match = re.search(r"[Cc]annot resolve (?:symbol|class|method|property) ['`]?([A-Za-z0-9_]+)['`]?", description)
        if match:
            return match.group(1)
        
        # Try to match "Class X not found"
        match = re.search(r"[Cc]lass ['`]?([A-Za-z0-9_]+)['`]? not found", description)
        if match:
            return match.group(1)
        
        # Try to match "Unresolved reference: X"
        match = re.search(r"[Uu]nresolved reference: ['`]?([A-Za-z0-9_]+)['`]?", description)
        if match:
            return match.group(1)
        
        # Try to match any word that looks like a class name (starts with uppercase)
        match = re.search(r"['`]?([A-Z][A-Za-z0-9_]+)['`]?", description)
        if match:
            return match.group(1)
        
        # If all else fails, return an empty string
        return ""

    def _extract_symbol_from_code(self, code: str) -> str:
        """
        Extract a symbol from code.

        Args:
            code: Code snippet

        Returns:
            Extracted symbol or empty string
        """
        # Look for import statements
        import re
        
        # Try to match "import X" or "import X.Y"
        match = re.search(r"import\s+([A-Za-z0-9_.]+)", code)
        if match:
            # Extract the last part of the import
            import_path = match.group(1)
            return import_path.split(".")[-1]
        
        # If all else fails, return an empty string
        return ""
