#!/usr/bin/env python3
"""
Test script for running the fix agent.
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
from unit_test_generator.cli.adapter_factory import (
    create_file_system_adapter, create_embedding_service, create_vector_db,
    create_llm_service, create_code_parser
)

def main():
    """Main function to test the fix agent."""
    # Load configuration
    import yaml
    with open('config/application.yml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Create real dependencies
    file_system = create_file_system_adapter()
    embedding_service = create_embedding_service(config)
    vector_db = create_vector_db(config)
    llm_service = create_llm_service(config)
    code_parser = create_code_parser(config)
    
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
    repo_root = Path(config['repository']['root_path'])
    agent_generate_tests = AgentGenerateTests(
        agent_coordinator=agent_coordinator,
        file_system=file_system,
        embedding_service=embedding_service,
        vector_db=vector_db,
        llm_service=llm_service,
        code_parser=code_parser,
        config=config,
        repo_root=repo_root
    )
    
    # Get the target file from command line arguments
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
    else:
        # Default target file
        target_file = "src/main/kotlin/com/example/SampleClass.kt"
    
    # Execute the use case
    print(f"Generating tests for {target_file} with agent mode...")
    result = agent_generate_tests.execute(target_file)
    
    # Print the result
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
