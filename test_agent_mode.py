#!/usr/bin/env python3
"""
Test script for running the agent mode.
"""
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Import the necessary components
from unit_test_generator.application.services.mode_selector import ModeSelector
from unit_test_generator.application.services.agent_coordinator import AgentCoordinator, StateManager
from unit_test_generator.application.agents.agent_factory import AgentFactory
from unit_test_generator.application.use_cases.agent_generate_tests import AgentGenerateTests

# Mock dependencies for testing
from unittest.mock import MagicMock

def main():
    """Main function to test the agent mode."""
    # Create mock dependencies
    file_system = MagicMock()
    embedding_service = MagicMock()
    vector_db = MagicMock()
    llm_service = MagicMock()
    code_parser = MagicMock()
    
    # Mock config
    config = {
        "repository": {
            "root_path": "/path/to/repo"
        },
        "generation": {
            "target_language": "Kotlin",
            "target_framework": "JUnit5 with MockK"
        },
        "orchestrator": {
            "defaultMode": "agent"
        },
        "agents": {
            "enabled": True
        }
    }
    
    # Create the mode selector
    mode_selector = ModeSelector(config, "agent")
    
    # Create the agent factory
    agent_factory = AgentFactory(
        config=config,
        llm_service=llm_service,
        file_system=file_system,
        embedding_service=embedding_service,
        vector_db=vector_db,
        code_parser=code_parser
    )
    
    # Create the state manager
    state_manager = StateManager()
    
    # Create the agent coordinator
    agent_coordinator = AgentCoordinator(
        agent_factory=agent_factory,
        state_manager=state_manager,
        config=config
    )
    
    # Create the agent generate tests use case
    agent_generate_tests = AgentGenerateTests(
        agent_coordinator=agent_coordinator,
        file_system=file_system,
        embedding_service=embedding_service,
        vector_db=vector_db,
        llm_service=llm_service,
        code_parser=code_parser,
        config=config,
        repo_root=Path("/path/to/repo")
    )
    
    # Execute the use case
    result = agent_generate_tests.execute("path/to/source/file.kt")
    
    # Print the result
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
