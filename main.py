import logging
import sys
from pathlib import Path
# No longer need argparse here

# --- Project Setup ---
project_root = Path(__file__).parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# --- CLI Specific Imports ---
# Setup helpers
from unit_test_generator.cli.config_loader import load_and_resolve_config, ensure_app_directories
from unit_test_generator.cli.logging_setup import setup_logging
# Argument Parser
from unit_test_generator.cli.argument_parser import parse_arguments # Import the function
# Command handlers
from unit_test_generator.cli.commands.index_command import handle_index
from unit_test_generator.cli.commands.generate_command import handle_generate

# --- Initialize Logger (basic config until setup_logging is called) ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__) # Get root logger instance


# --- Main Application Entry Point ---
def main():
    """Main function to parse args, setup, and dispatch command."""
    args = parse_arguments() # Use the imported function

    try:
        # Initial setup: Load config, configure logging, ensure directories
        config = load_and_resolve_config(project_root)
        setup_logging(config) # Reconfigure logging properly based on config
        ensure_app_directories(config)
    except Exception as e:
        logger.critical(f"Critical error during application setup: {e}", exc_info=True)
        sys.exit(1)

    logger.info(f"Executing command: {args.command}")

    # Dispatch to the appropriate command handler
    if args.command == "index":
        handle_index(args, config)
    elif args.command == "generate":
        handle_generate(args, config)
    else:
        # This case should be unreachable due to argparse 'required=True'
        logger.error(f"Unknown command encountered: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    main()