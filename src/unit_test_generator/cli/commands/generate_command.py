# src/unit_test_generator/cli/commands/generate_command.py
import logging
import sys
import argparse
from typing import Dict, Any, List
from pathlib import Path

# Import factories
from unit_test_generator.cli.adapter_factory import (
    create_file_system_adapter, create_embedding_service, create_vector_db,
    create_llm_service, create_code_parser, create_dependency_resolver,
    create_build_system, create_error_parser, create_source_control, # Added source control
    create_ui_service, # UI Service
    # ADK Tool Factories (ensure these are imported)
    create_read_file_tool, create_write_file_tool, create_run_test_tool,
    create_parse_errors_tool, create_generate_fix_tool, create_resolve_dependencies_tool,
)
# Import Use Cases
from unit_test_generator.application.use_cases.generate_tests import GenerateTestsUseCase
from unit_test_generator.application.use_cases.generate_tests_for_commit import GenerateTestsForCommitUseCase
# Import ADK Runner classes
from unit_test_generator.infrastructure.adk_tools.runner import ADKRunnerAdapter, SimplifiedADKRunner
# Import UI Service
from unit_test_generator.application.services.ui_service import UIService
from unit_test_generator.domain.ports.ui_service import LogLevel

logger = logging.getLogger(__name__)

def handle_generate(args: argparse.Namespace, config: Dict[str, Any]):
    """Handles the 'generate' command logic."""
    # Create UI service
    ui_adapter = create_ui_service(config)
    ui = UIService(ui_adapter)

    # Display welcome panel
    mode_name = args.mode if hasattr(args, 'mode') and args.mode else config.get('generation', {}).get('mode', 'standard')
    ui.panel(f"JUnit Writer - Test Generation ({mode_name.capitalize()} Mode)", "Welcome", border_style="cyan")

    # Get the mode from CLI args if provided
    cli_mode = args.mode if hasattr(args, 'mode') else None
    ui.log(f"Mode: {cli_mode if cli_mode else 'Using default from config'}", LogLevel.INFO)

    # Create a status display
    status = ui.status("Initializing test generation...")

    # Initialize the mode selector with the CLI mode
    from unit_test_generator.application.services.mode_selector import ModeSelector, UseCaseFactory
    from unit_test_generator.cli.adapter_factory import create_agent_factory, create_state_manager, create_agent_coordinator
    mode_selector = ModeSelector(config, cli_mode)

    try:
        # Instantiate necessary adapters and services via factory
        status.update("Creating file system adapter...")
        file_system = create_file_system_adapter()

        status.update("Creating embedding service...")
        embedding_service = create_embedding_service(config)

        status.update("Creating vector database...")
        vector_db = create_vector_db(config)

        status.update("Creating LLM service...")
        llm_service = create_llm_service(config)

        status.update("Creating code parser...")
        code_parser = create_code_parser(config)

        status.update("Creating dependency resolver...")
        dependency_resolver = create_dependency_resolver(config, file_system)

        status.update("Creating build system...")
        build_system = create_build_system(config) # Still needed for RunTestTool

        status.update("Creating error parser...")
        error_parser = create_error_parser(config, llm_service) # Still needed for ParseErrorsTool

        status.update("Creating source control adapter...")
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
            ui.log(f"Target '{target_norm}' identified as a commit hash", LogLevel.INFO)

            # Parse file extensions from args
            file_extensions = args.file_extensions.split(',') if args.file_extensions else ['.kt', '.java']
            ui.log(f"Using file extensions filter: {file_extensions}", LogLevel.INFO)

            # Instantiate the commit-based use case
            status.update("Creating commit-based test generation use case...")
            generate_tests_for_commit_use_case = GenerateTestsForCommitUseCase(
                source_control=source_control,
                file_system=file_system,
                llm_service=llm_service,
                generate_tests_use_case=generate_use_case,
                config=config
            )

            # Execute the commit-based use case
            status.update(f"Generating tests for commit: {target_norm}...")

            # Create a progress bar for parallel processing if enabled
            progress = None
            if args.parallel:
                # Estimate number of files to process (this is approximate)
                estimated_files = 10  # Default estimate
                try:
                    # Try to get actual count from source control
                    changed_files = source_control.get_changed_files(target_norm, file_extensions)
                    estimated_files = len(changed_files)
                except Exception:
                    pass

                progress = ui.progress(estimated_files, f"Processing {estimated_files} files in parallel...")

            result = generate_tests_for_commit_use_case.execute(
                commit_hash_or_file_path=target_norm,
                file_extensions=file_extensions,
                parallel=args.parallel,
                max_workers=args.max_workers
            )

            # Close progress bar if it was created
            if progress:
                progress.close()

            # Stop the status display
            status.stop()

            # Display results
            if result.get('status', '').startswith('success') or result.get('status') == 'partial_success':
                ui.log(f"Generation for commit {target_norm} finished successfully", LogLevel.SUCCESS)

                # Create a table for generated files
                if 'generated_files' in result and result['generated_files']:
                    ui.panel("Generated Test Files", border_style="green")
                    table = ui.table(["Source File", "Test File", "Status"])
                    for file_result in result.get('generated_files', []):
                        status_str = file_result.get('status', 'unknown')
                        status_style = "green" if status_str.startswith('success') else "yellow"
                        table.add_row(
                            file_result.get('source_file', 'N/A'),
                            file_result.get('test_file', 'N/A'),
                            f"[{status_style}]{status_str}[/{status_style}]"
                        )
                    table.render()
            else:
                # Check if there's a detailed message
                if result.get('message'):
                    ui.log(f"Generation failed: {result.get('message')}", LogLevel.ERROR)
                else:
                    ui.log("Generation completed with issues", LogLevel.WARNING)

                # Log details for each file
                if 'results' in result and result['results']:
                    table = ui.table(["Source File", "Status", "Details"])
                    for file_path, file_result in result.get('results', {}).items():
                        status = file_result.get('status', 'unknown')
                        if status.startswith('success'):
                            details = f"Tests at: {file_result.get('output_path')}"
                            table.add_row(file_path, f"[green]{status}[/green]", details)
                        else:
                            details = file_result.get('message', 'No details')
                            table.add_row(file_path, f"[yellow]{status}[/yellow]", details)
                    table.render()
        else:
            # Target is a file path, use the single-file use case
            ui.log(f"Target '{target_norm}' identified as a file path", LogLevel.INFO)
            status.update(f"Generating tests for file: {target_norm}...")
            result = generate_use_case.execute(target_file_rel_path=target_norm)

            # Stop the status display
            status.stop()

            # Display results
            if result.get('status', '').startswith('success'):
                ui.log(f"Generation execution finished successfully", LogLevel.SUCCESS)
                ui.log(f"Final tests at: {result.get('output_path')}", LogLevel.INFO)

                # Show code preview if available
                if 'test_content' in result and result['test_content']:
                    ui.panel("Generated Test Preview", border_style="green")
                    ui.syntax(result['test_content'][:500] + "...\n(truncated)", "kotlin")
            elif result.get('message'):
                ui.log(f"Generation failed: {result.get('message')}", LogLevel.ERROR)

            # Show final success panel
            if result.get('status', '').startswith('success'):
                ui.panel(f"Test generation completed successfully!\nOutput: {result.get('output_path')}", "Success", border_style="green")
            else:
                ui.panel(f"Test generation completed with issues.\n{result.get('message', '')}", "Completed", border_style="yellow")

    except Exception as e:
        # Stop any active status display
        if 'status' in locals():
            status.stop()

        ui.log(f"An error occurred during test generation: {e}", LogLevel.ERROR)
        logger.critical(f"An error occurred during test generation command: {e}", exc_info=True)
        ui.panel(f"Error: {str(e)}", "Generation Failed", border_style="red")
        sys.exit(1)
