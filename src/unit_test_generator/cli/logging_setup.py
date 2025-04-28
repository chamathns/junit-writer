import logging
import os
import sys
from typing import Dict, Any

# Try to import Rich components for enhanced logging
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from unit_test_generator.infrastructure.adapters.ui.rich_ui_adapter import RichLoggingHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Try to import colorama for basic color support as fallback
try:
    import colorama
    colorama.init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


def setup_logging(config: Dict[str, Any]):
    """Configures logging based on the application configuration."""
    log_config = config.get('logging', {})
    level_name = log_config.get('level', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_file = log_config.get('log_file') # Path is already resolved

    # Check if enhanced UI is enabled
    ui_config = config.get('ui', {})
    enhanced_logging = ui_config.get('enhanced_logging', True)

    # Configure handlers based on available libraries and configuration
    if enhanced_logging and RICH_AVAILABLE:
        # Use Rich for enhanced console logging
        console = Console()
        handlers = [RichLoggingHandler(
            console=console,
            show_time=True,
            show_level=True,
            show_path=False,
            markup=True
        )]

        # Rich format is different
        rich_format = "%(message)s"

        if log_file:
            try:
                # Still use regular file handler for log files
                handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
            except Exception as e:
                console.print(f"[yellow]Warning: Could not configure file logging to {log_file}: {e}[/yellow]")

        # Configure the root logger
        logging.basicConfig(level=level, format=rich_format, handlers=handlers, force=True)

    else:
        # Standard logging with optional colorama enhancement
        handlers = [logging.StreamHandler(sys.stdout)]
        if log_file:
            try:
                handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
            except Exception as e:
                print(f"Warning: Could not configure file logging to {log_file}: {e}", file=sys.stderr)

        # Use force=True to allow reconfiguration if called multiple times
        logging.basicConfig(level=level, format=log_format, handlers=handlers, force=True)

        # Add basic color formatting with colorama if available
        if enhanced_logging and COLORAMA_AVAILABLE:
            # Monkey patch the logging.StreamHandler.emit method to add colors
            original_emit = logging.StreamHandler.emit

            def colored_emit(self, record):
                # Add colors based on log level
                if record.levelno >= logging.CRITICAL:
                    record.levelname = f"{colorama.Fore.RED}{colorama.Style.BRIGHT}{record.levelname}{colorama.Style.RESET_ALL}"
                elif record.levelno >= logging.ERROR:
                    record.levelname = f"{colorama.Fore.RED}{record.levelname}{colorama.Style.RESET_ALL}"
                elif record.levelno >= logging.WARNING:
                    record.levelname = f"{colorama.Fore.YELLOW}{record.levelname}{colorama.Style.RESET_ALL}"
                elif record.levelno >= logging.INFO:
                    record.levelname = f"{colorama.Fore.CYAN}{record.levelname}{colorama.Style.RESET_ALL}"

                original_emit(self, record)

            logging.StreamHandler.emit = colored_emit

    # Suppress verbose logs from dependencies
    dependencies_to_silence = {
        "chromadb": logging.WARNING,
        "sentence_transformers": logging.WARNING,
        "httpx": logging.WARNING,
        "google.api_core": logging.WARNING,
        "google.auth": logging.WARNING,
        "urllib3": logging.WARNING,
        "tqdm": logging.WARNING,  # Suppress tqdm logs
    }
    for name, lvl in dependencies_to_silence.items():
        logging.getLogger(name).setLevel(lvl)

    logging.info(f"Logging configured. Level: {level_name}, File: {log_file or 'None'}")