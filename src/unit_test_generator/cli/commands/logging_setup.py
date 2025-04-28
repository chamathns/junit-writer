import logging
import sys
from typing import Dict, Any

def setup_logging(config: Dict[str, Any]):
    """Configures logging based on the application configuration."""
    log_config = config.get('logging', {})
    level_name = log_config.get('level', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_file = log_config.get('log_file') # Path is already resolved

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        try:
            # Ensure parent directory exists (should be done by ensure_app_directories)
            handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
        except Exception as e:
            print(f"Warning: Could not configure file logging to {log_file}: {e}", file=sys.stderr)


    # Use force=True to allow reconfiguration if called multiple times (e.g., in tests)
    logging.basicConfig(level=level, format=log_format, handlers=handlers, force=True)

    # Suppress verbose logs from dependencies
    dependencies_to_silence = {
        "chromadb": logging.WARNING,
        "sentence_transformers": logging.WARNING,
        "httpx": logging.WARNING,
        "google.api_core": logging.WARNING,
        "google.auth": logging.WARNING,
        "urllib3": logging.WARNING,
    }
    for name, lvl in dependencies_to_silence.items():
        logging.getLogger(name).setLevel(lvl)

    logging.info(f"Logging configured. Level: {level_name}, File: {log_file or 'None'}")