# src/unit_test_generator/cli/commands/generate_command.py
import logging
import sys
import argparse
from typing import Dict, Any, List
from pathlib import Path

# Import factories
from unit_test_generator.cli.commands.adapter_factory import (
    create_file_system_adapter, create_embedding_service, create_vector_db,
    create_llm_service, create_code_parser, create_dependency_resolver,
    create_build_system, create_error_parser, create_source_control, # Added source control
    # ADK Tool Factories (ensure these are imported)
    create_read_file_tool, create_write_file_tool, create_run_test_tool,
    create_parse_errors_tool, create_generate_fix_tool, create_resolve_dependencies_tool,
)
# Import Use Cases
from unit_test_generator.application.use_cases.generate_tests import GenerateTestsUseCase
from unit_test_generator.application.use_cases.generate_tests_for_commit import GenerateTestsForCommitUseCase
# Import ADK Runner classes
from unit_test_generator.infrastructure.adk_tools.runner import ADKRunnerAdapter, SimplifiedADKRunner

logger = logging.getLogger(__name__)

def handle_generate(args: argparse.Namespace, config: Dict[str, Any]):
    """Handles the 'generate' command logic."""
    # Get the mode from CLI args if provided
    cli_mode = args.mode if hasattr(args, 'mode') else None
    logger.info(f"CLI mode: {cli_mode if cli_mode else 'not specified'}")

    # Initialize the mode selector with the CLI mode
    from unit_test_generator.application.services.mode_selector import ModeSelector, UseCaseFactory
    from unit_test_generator.cli.adapter_factory import create_agent_factory, create_state_manager, create_agent_coordinator
    mode_selector = ModeSelector(config, cli_mode)
    logger.info("--- Starting Test Generation Process ---")
    try:
        # Instantiate necessary adapters and services via factory
        file_system = create_file_system_adapter()
        embedding_service = create_embedding_service(config)
        vector_db = create_vector_db(config)
        llm_service = create_llm_service(config)
        code_parser = create_code_parser(config)
        dependency_resolver = create_dependency_resolver(config, file_system)
        build_system = create_build_system(config) # Still needed for RunTestTool
        error_parser = create_error_parser(config, llm_service) # Still needed for ParseErrorsTool
        source_control = create_source_control(config) # For commit-based mode

        # --- Instantiate ADK Tools ---
        adk_tools = [
            create_read_file_tool(file_system),
            create_write_file_tool(file_system),
            create_run_test_tool(build_system),
            create_parse_errors_tool(error_parser),
            create_generate_fix_tool(llm_service, error_parser, dependency_resolver, config),
            create_resolve_dependencies_tool(dependency_resolver),
        ]
        logger.info(f"Created {len(adk_tools)} ADK tools.")

        # --- Instantiate ADK Runner/Engine ---
        # Use the create_adk_reasoning_engine function from adapter_factory
        from unit_test_generator.cli.adapter_factory import create_adk_reasoning_engine
        adk_runner = create_adk_reasoning_engine(adk_tools, config, llm_service)

        # Create the use case factory
        use_case_factory = UseCaseFactory(
            mode_selector=mode_selector,
            file_system=file_system,
            embedding_service=embedding_service,
            vector_db=vector_db,
            llm_service=llm_service,
            code_parser=code_parser,
            build_system=build_system,
            error_parser=error_parser,
            config=config
        )

        # If agent mode is enabled, create the agent coordinator
        if mode_selector.is_agent_mode():
            logger.info("Using agent mode for test generation")
            # Create agent factory and state manager
            agent_factory = create_agent_factory(config, llm_service, file_system, embedding_service, vector_db, code_parser)
            state_manager = create_state_manager()

            # Create agent coordinator
            agent_coordinator = create_agent_coordinator(agent_factory, state_manager, config)

            # Update the use case factory with the agent coordinator
            use_case_factory.agent_coordinator = agent_coordinator
        else:
            logger.info("Using standard mode for test generation")

        # Create the generate tests use case
        generate_use_case = use_case_factory.create_use_case(
            "generate_tests",
            dependency_resolver=dependency_resolver,
            adk_runner=adk_runner,
            repo_root=Path(config['repository']['root_path']).resolve()
        )

        # Normalize target path
        target_norm = args.target.replace('\\', '/') # Normalize path

        # Determine if the target is a file path or a commit hash
        is_commit_hash = source_control.is_commit_hash(target_norm)

        if is_commit_hash:
            # Target is a commit hash, use the commit-based use case
            logger.info(f"Target '{target_norm}' identified as a commit hash")

            # Parse file extensions from args
            file_extensions = args.file_extensions.split(',') if args.file_extensions else ['.kt', '.java']
            logger.info(f"Using file extensions filter: {file_extensions}")

            # Instantiate the commit-based use case
            generate_tests_for_commit_use_case = GenerateTestsForCommitUseCase(
                source_control=source_control,
                file_system=file_system,
                llm_service=llm_service,
                generate_tests_use_case=generate_use_case,
                config=config
            )

            # Execute the commit-based use case
            logger.info(f"Executing generate tests for commit: {target_norm}")
            result = generate_tests_for_commit_use_case.execute(
                commit_hash=target_norm,
                file_extensions=file_extensions,
                parallel=args.parallel,
                max_workers=args.max_workers
            )

            # Log results
            logger.info(f"Generation for commit {target_norm} finished with status: {result.get('status')}")
            if result.get('status', '').startswith('success') or result.get('status') == 'partial_success':
                logger.info(result.get('message', 'Generation completed'))
                # Log details for each file
                for file_path, file_result in result.get('results', {}).items():
                    status = file_result.get('status', 'unknown')
                    if status.startswith('success'):
                        logger.info(f"  - {file_path}: {status} - Tests at: {file_result.get('output_path')}")
                    else:
                        logger.warning(f"  - {file_path}: {status} - {file_result.get('message', 'No details')}")
            else:
                logger.error(f"Generation failed: {result.get('message')}")
        else:
            # Target is a file path, use the single-file use case
            logger.info(f"Target '{target_norm}' identified as a file path")
            logger.info(f"Executing generate use case for file: {target_norm}")
            result = generate_use_case.execute(target_file_rel_path=target_norm)

            # Log results
            logger.info(f"Generation execution finished with status: {result.get('status')}")
            if result.get('status', '').startswith('success'):
                logger.info(f"Final tests at: {result.get('output_path')}")
            elif result.get('message'):
                logger.error(f"Generation failed: {result.get('message')}")

    except Exception as e:
        logger.critical(f"An error occurred during test generation command: {e}", exc_info=True)
        sys.exit(1)
    logger.info("--- Test Generation Process Complete ---")
