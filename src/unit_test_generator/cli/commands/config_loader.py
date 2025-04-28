import yaml
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_and_resolve_config(project_root: Path, config_path="config/application.yml") -> dict:
    """Loads YAML configuration and resolves relative paths."""
    absolute_config_path = project_root / config_path
    logger.debug(f"Attempting to load configuration from: {absolute_config_path}")
    try:
        with open(absolute_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        if not config_data:
             raise ValueError("Configuration file is empty or invalid.")

        # Resolve paths relative to project_root
        resolve_path(config_data, project_root, ['repository', 'root_path'], '.')
        resolve_path(config_data, project_root, ['indexing', 'index_file_path'], 'var/index/repository_index.json')
        resolve_path(config_data, project_root, ['vector_db', 'path'], 'var/rag_db/chroma')
        resolve_path(config_data, project_root, ['generation', 'output_dir'], 'generated-tests')
        resolve_path(config_data, project_root, ['logging', 'log_file']) # Optional

        logger.info(f"Configuration loaded successfully from {absolute_config_path}")
        return config_data

    except FileNotFoundError:
        logger.critical(f"Configuration file not found at {absolute_config_path}")
        sys.exit(1)
    except Exception as err:
        logger.critical(f"Error loading or resolving configuration from {absolute_config_path}: {err}", exc_info=True)
        sys.exit(1)

def resolve_path(config: dict, root: Path, keys: list, default: str | None = None):
    """Helper to get, resolve, and update a path in the config dict."""
    current = config
    for key in keys[:-1]:
        current = current.get(key, {})
        if not isinstance(current, dict): # Path segment not found or not dict
             if default is None and keys[-1] == 'log_file': return # Log file is optional
             logger.warning(f"Config path {'->'.join(keys)} structure invalid. Using default '{default}' if available.")
             current = {} # Reset to avoid errors below
             break

    last_key = keys[-1]
    relative_path = current.get(last_key, default)

    if relative_path is not None:
        resolved_path = str((root / relative_path).resolve())
        current[last_key] = resolved_path
        logger.debug(f"Resolved config path '{'.'.join(keys)}': {relative_path} -> {resolved_path}")

def ensure_app_directories(config: dict):
    """Creates necessary directories based on resolved config paths."""
    logger.debug("Ensuring application directories exist...")
    paths_to_ensure = [
        config.get('indexing', {}).get('index_file_path'),
        config.get('vector_db', {}).get('path'),
        config.get('generation', {}).get('output_dir'),
        config.get('logging', {}).get('log_file')
    ]
    for file_or_dir_path in paths_to_ensure:
        if file_or_dir_path:
            path_obj = Path(file_or_dir_path)
            # If it looks like a file path, ensure parent dir exists.
            # If it looks like a dir path (e.g., chroma path), ensure it exists.
            target_dir = path_obj.parent if '.' in path_obj.name else path_obj
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {target_dir}")
            except OSError as e:
                 logger.error(f"Failed to create directory {target_dir}: {e}", exc_info=True)
                 # Decide if this is critical enough to exit
                 # sys.exit(1)