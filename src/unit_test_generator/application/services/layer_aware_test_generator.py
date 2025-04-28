"""
Layer-aware test generator for different architectural layers.
"""
import logging
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.application.services.intelligent_context_builder import IntelligentContextBuilder

logger = logging.getLogger(__name__)

class LayerAwareTestGenerator:
    """
    Generates tests with awareness of architectural layers.
    """
    
    def __init__(self, 
                llm_service: LLMServicePort, 
                context_builder: IntelligentContextBuilder, 
                config: Dict[str, Any]):
        """
        Initialize the layer-aware test generator.
        
        Args:
            llm_service: LLM service for test generation
            context_builder: Intelligent context builder
            config: Application configuration
        """
        self.llm_service = llm_service
        self.context_builder = context_builder
        self.config = config
    
    def generate_tests(self, source_file: str, source_content: str, imports: List[str]) -> str:
        """
        Generate tests for a source file with layer-specific strategies.
        
        Args:
            source_file: Path to the source file
            source_content: Content of the source file
            imports: List of imports extracted from the source file
            
        Returns:
            Generated test code
        """
        # Determine the architectural layer
        layer = self._determine_layer(source_file, source_content)
        logger.info(f"Generating tests for {source_file} (layer: {layer})")
        
        # Build comprehensive context
        context = self.context_builder.build_context(source_file, source_content, imports)
        
        # Add layer-specific instructions
        context["layer"] = layer
        context["layer_instructions"] = self._get_layer_instructions(layer)
        
        # Generate tests using the LLM
        test_code = self.llm_service.generate_tests(context)
        
        return test_code
    
    def _determine_layer(self, source_file: str, source_content: str) -> str:
        """
        Determine the architectural layer of the source file.
        
        Args:
            source_file: Path to the source file
            source_content: Content of the source file
            
        Returns:
            Layer name: "domain", "application", "infrastructure", "presentation", or "unknown"
        """
        # Check file path for layer indicators
        path_patterns = {
            "domain": [r'/domain/', r'/model/', r'/entity/'],
            "application": [r'/service/', r'/usecase/', r'/application/'],
            "infrastructure": [r'/repository/', r'/dao/', r'/adapter/', r'/infrastructure/'],
            "presentation": [r'/controller/', r'/rest/', r'/ui/', r'/presentation/'],
            "dto": [r'/dto/', r'/request/', r'/response/']
        }
        
        for layer, patterns in path_patterns.items():
            for pattern in patterns:
                if re.search(pattern, source_file, re.IGNORECASE):
                    return layer
        
        # Check package declaration
        package_match = re.search(r'package\s+([\w.]+)', source_content)
        if package_match:
            package = package_match.group(1)
            
            if re.search(r'\.domain\.', package) or re.search(r'\.model\.', package) or re.search(r'\.entity\.', package):
                return "domain"
            elif re.search(r'\.service\.', package) or re.search(r'\.usecase\.', package) or re.search(r'\.application\.', package):
                return "application"
            elif re.search(r'\.repository\.', package) or re.search(r'\.dao\.', package) or re.search(r'\.infrastructure\.', package):
                return "infrastructure"
            elif re.search(r'\.controller\.', package) or re.search(r'\.rest\.', package) or re.search(r'\.presentation\.', package):
                return "presentation"
            elif re.search(r'\.dto\.', package) or re.search(r'\.request\.', package) or re.search(r'\.response\.', package):
                return "dto"
        
        # Check class annotations and imports
        if re.search(r'@Entity', source_content) or re.search(r'@Table', source_content):
            return "domain"
        elif re.search(r'@Service', source_content) or re.search(r'@Component', source_content):
            return "application"
        elif re.search(r'@Repository', source_content) or re.search(r'@Dao', source_content):
            return "infrastructure"
        elif re.search(r'@RestController', source_content) or re.search(r'@Controller', source_content):
            return "presentation"
        elif re.search(r'data class', source_content, re.IGNORECASE) or re.search(r'class.*DTO', source_content):
            return "dto"
        
        # Default to unknown
        return "unknown"
    
    def _get_layer_instructions(self, layer: str) -> str:
        """
        Get layer-specific testing instructions.
        
        Args:
            layer: Architectural layer
            
        Returns:
            Layer-specific instructions for test generation
        """
        if layer == "domain":
            return """
            For domain layer classes:
            1. Focus on testing business rules, invariants, and domain logic
            2. Test entity behavior, value objects, and domain services
            3. Avoid mocking domain objects; use real instances
            4. Test validation rules and constraints
            5. Ensure domain objects maintain their invariants
            """
        elif layer == "application":
            return """
            For application layer classes:
            1. Focus on testing use cases and application services
            2. Mock infrastructure dependencies (repositories, external services)
            3. Verify that the service orchestrates the domain correctly
            4. Test error handling and edge cases
            5. Verify that application events are properly triggered
            """
        elif layer == "infrastructure":
            return """
            For infrastructure layer classes:
            1. Focus on testing integration with external systems
            2. Use appropriate test doubles (mocks, stubs) for external dependencies
            3. Test mapping between domain and external representations
            4. Verify error handling and resilience
            5. Consider using integration tests for repositories
            """
        elif layer == "presentation":
            return """
            For presentation layer classes:
            1. Focus on testing request/response handling
            2. Mock application services and use cases
            3. Test input validation and error responses
            4. Verify correct mapping between DTOs and domain objects
            5. Test authorization and authentication if applicable
            """
        elif layer == "dto":
            return """
            For DTO classes:
            1. Focus on testing serialization/deserialization
            2. Test validation annotations if present
            3. Test mapping to/from domain objects
            4. Verify builder patterns or factory methods
            5. Test equals/hashCode implementations if overridden
            """
        else:
            return """
            General testing guidelines:
            1. Test public methods and behaviors
            2. Mock external dependencies
            3. Test happy paths and error cases
            4. Verify edge cases and boundary conditions
            5. Follow the testing conventions used in the project
            """
