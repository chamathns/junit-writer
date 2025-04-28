import logging
import re
from typing import List, Dict, Tuple
from pathlib import Path

from unit_test_generator.domain.ports.code_parser import CodeParserPort

logger = logging.getLogger(__name__)

class SimulatedParserAdapter(CodeParserPort):
    """A simulated code parser that uses regex patterns instead of a real AST parser.

    This adapter provides a simplified implementation that extracts imports and
    estimates usage weights using regular expressions. It's optimized specifically
    for Kotlin code.

    For production use, this should be replaced with a real AST-based parser.
    """

    def __init__(self):
        # Kotlin patterns
        self.import_pattern = re.compile(r'^\s*import\s+([\w\.]+)(?:\s+as\s+[\w]+)?\s*$', re.MULTILINE)
        self.package_pattern = re.compile(r'^\s*package\s+([\w\.]+)\s*$', re.MULTILINE)
        self.class_pattern = re.compile(r'\b(?:class|interface|object|enum\s+class)\s+([\w<>]+)')
        self.function_pattern = re.compile(r'\bfun\s+([\w<>]+)\s*\(')
        self.property_pattern = re.compile(r'\b(?:val|var)\s+([\w<>]+)\s*:')
        self.companion_pattern = re.compile(r'\bcompanion\s+object\b')
        self.constructor_pattern = re.compile(r'\bconstructor\s*\(')

        # Patterns for inheritance and implementation
        self.inheritance_pattern = re.compile(r':\s*([\w<>.]+)(?:\s*,\s*|\s*\{)')

        logger.info("SimulatedParserAdapter initialized for Kotlin code.")

    def parse(self, content: str, file_path: str) -> Tuple[List[str], Dict[str, float]]:
        """Parses Kotlin source code to extract imports and estimate usage weights."""
        if not content or not file_path:
            logger.warning(f"Empty content or file path provided for parsing: {file_path}")
            return [], {}

        # Verify it's a Kotlin file
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in ('.kt', '.kts'):
            logger.warning(f"Not a Kotlin file: {file_path}")
            return [], {}

        # Extract imports
        imports = self._extract_imports(content)

        # Extract package
        package_match = self.package_pattern.search(content)
        package_name = package_match.group(1) if package_match else ""

        # Estimate usage weights
        usage_weights = self._estimate_usage_weights(content, imports)

        logger.debug(f"Parsed {file_path}: found {len(imports)} imports with {len(usage_weights)} weighted usages")
        return imports, usage_weights

    def _extract_imports(self, content: str) -> List[str]:
        """Extracts import statements from Kotlin code."""
        imports = []
        for match in self.import_pattern.finditer(content):
            import_path = match.group(1).strip()
            imports.append(import_path)
        return imports

    def _estimate_usage_weights(self, content: str, imports: List[str]) -> Dict[str, float]:
        """Estimates usage weights for imported symbols in Kotlin code.

        This function analyzes how frequently each imported symbol is used in the code
        and assigns a weight based on its usage pattern. Higher weights indicate
        more important dependencies.

        Args:
            content: The Kotlin source code content to analyze
            imports: List of import statements extracted from the code

        Returns:
            Dictionary mapping import paths to their usage weight (0.0 to 1.0)
        """
        usage_weights = {}

        # Extract all identifiers from the code for faster lookup
        # This regex finds all word boundaries that might be identifiers
        all_identifiers = re.findall(r'\b[A-Za-z][A-Za-z0-9_]*\b', content)
        identifier_counts = {}
        for identifier in all_identifiers:
            identifier_counts[identifier] = identifier_counts.get(identifier, 0) + 1

        # Calculate total number of identifiers for normalization
        total_identifiers = len(all_identifiers)
        if total_identifiers == 0:
            return {import_path: 0.0 for import_path in imports}

        for import_path in imports:
            # Extract the class/object name (last part of the import path)
            parts = import_path.split(".")
            if not parts:
                usage_weights[import_path] = 0.0
                continue

            symbol = parts[-1]

            # Get the count for this symbol
            count = identifier_counts.get(symbol, 0)

            # Additional checks for more accurate weighting
            # Check for constructor usage (ClassName())
            constructor_pattern = r'\b' + re.escape(symbol) + r'\s*\('
            constructor_matches = len(re.findall(constructor_pattern, content))

            # Check for companion object access (ClassName.something)
            companion_access_pattern = r'\b' + re.escape(symbol) + r'\.[A-Za-z][A-Za-z0-9_]*'
            companion_matches = len(re.findall(companion_access_pattern, content))

            # Calculate a composite score
            # - Base usage: how often the symbol appears
            # - Constructor usage: creating instances is important
            # - Companion object usage: accessing static-like members indicates importance
            base_score = count / max(50, total_identifiers)  # Cap at 50 identifiers for normalization
            constructor_score = min(0.3, constructor_matches * 0.1)  # Constructor usage is important
            companion_score = min(0.2, companion_matches * 0.05)  # Companion access is somewhat important

            # Combine scores with a cap at 1.0
            combined_score = min(1.0, base_score + constructor_score + companion_score)

            # Boost score if the symbol appears in class definitions or inheritance
            class_def_pattern = r'(?:class|interface|object|enum\s+class)\s+[^{]*\b' + re.escape(symbol) + r'\b'
            extends_pattern = r':\s*[^{]*\b' + re.escape(symbol) + r'\b'

            if re.search(class_def_pattern, content) or re.search(extends_pattern, content):
                combined_score = min(1.0, combined_score + 0.3)  # Significant boost for inheritance/implementation

            # Check if it's used in annotations (very important in Kotlin)
            annotation_pattern = r'@' + re.escape(symbol) + r'\b'
            if re.search(annotation_pattern, content):
                combined_score = min(1.0, combined_score + 0.25)  # Boost for annotation usage

            # Check if it's used in generics (type parameters)
            generics_pattern = r'<[^>]*\b' + re.escape(symbol) + r'\b[^>]*>'
            if re.search(generics_pattern, content):
                combined_score = min(1.0, combined_score + 0.15)  # Boost for generic type usage

            usage_weights[import_path] = combined_score

        return usage_weights