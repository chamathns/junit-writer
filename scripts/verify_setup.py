#!/usr/bin/env python3
"""
Verification script to check if JUnit Writer is properly set up.
This script checks:
1. Python version
2. Required dependencies
3. Configuration file
4. API key access
"""

import os
import sys
import importlib
import yaml
from pathlib import Path

# Define colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_status(message, status, details=None):
    """Print a status message with color coding."""
    status_color = {
        "OK": GREEN,
        "WARNING": YELLOW,
        "ERROR": RED
    }.get(status, RESET)
    
    print(f"{message:<50} [{status_color}{status}{RESET}]")
    if details:
        print(f"  {details}")

def check_python_version():
    """Check if Python version is 3.8 or higher."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_status("Python version (3.8+ required)", "ERROR", 
                    f"Found Python {version.major}.{version.minor}.{version.micro}")
        return False
    else:
        print_status("Python version (3.8+ required)", "OK", 
                    f"Found Python {version.major}.{version.minor}.{version.micro}")
        return True

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        "yaml", "google", "sentence_transformers", "chromadb"
    ]
    
    all_ok = True
    for package in required_packages:
        try:
            if package == "yaml":
                importlib.import_module("yaml")
            else:
                importlib.import_module(package)
            print_status(f"Required package: {package}", "OK")
        except ImportError:
            print_status(f"Required package: {package}", "ERROR", "Not installed")
            all_ok = False
    
    return all_ok

def check_config_file():
    """Check if configuration file exists and is valid."""
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config" / "application.yml"
    
    if not config_path.exists():
        print_status("Configuration file", "ERROR", f"Not found at {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check essential config sections
        required_sections = ["repository", "indexing", "embedding", "vector_db", "generation"]
        missing_sections = [section for section in required_sections if section not in config]
        
        if missing_sections:
            print_status("Configuration file", "WARNING", 
                        f"Missing sections: {', '.join(missing_sections)}")
            return False
        
        # Check repository path
        repo_path = config.get("repository", {}).get("root_path", "")
        if not repo_path or not Path(repo_path).exists():
            print_status("Repository path", "WARNING", 
                        f"Path does not exist: {repo_path}")
            return False
        
        print_status("Configuration file", "OK")
        return True
    
    except Exception as e:
        print_status("Configuration file", "ERROR", f"Invalid YAML: {str(e)}")
        return False

def check_api_key():
    """Check if API key is available."""
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config" / "application.yml"
    
    if not config_path.exists():
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        llm_provider = config.get("generation", {}).get("llm_provider", "")
        
        if llm_provider == "google_gemini":
            api_key = config.get("generation", {}).get("api_key", "")
            if not api_key:
                api_key = os.environ.get("GOOGLE_API_KEY", "")
            
            if not api_key:
                print_status("Google Gemini API key", "ERROR", "Not found in config or environment")
                return False
            else:
                print_status("Google Gemini API key", "OK")
                return True
        
        elif llm_provider == "openai":
            api_key = config.get("generation", {}).get("api_key", "")
            if not api_key:
                api_key = os.environ.get("OPENAI_API_KEY", "")
            
            if not api_key:
                print_status("OpenAI API key", "ERROR", "Not found in config or environment")
                return False
            else:
                print_status("OpenAI API key", "OK")
                return True
        
        elif llm_provider == "mock":
            print_status("LLM API key", "OK", "Using mock LLM provider (no API key needed)")
            return True
        
        else:
            print_status("LLM provider", "WARNING", f"Unknown provider: {llm_provider}")
            return False
    
    except Exception as e:
        print_status("API key check", "ERROR", str(e))
        return False

def main():
    """Run all verification checks."""
    print(f"\n{BOLD}JUnit Writer Setup Verification{RESET}\n")
    
    python_ok = check_python_version()
    deps_ok = check_dependencies()
    config_ok = check_config_file()
    api_ok = check_api_key()
    
    print("\n" + "-" * 60)
    
    if all([python_ok, deps_ok, config_ok, api_ok]):
        print(f"\n{GREEN}{BOLD}All checks passed! JUnit Writer is ready to use.{RESET}\n")
        print("You can now run:")
        print("  python main.py index       # To index your repository")
        print("  python main.py generate    # To generate tests for a file")
    else:
        print(f"\n{YELLOW}{BOLD}Some checks failed. Please fix the issues above before using JUnit Writer.{RESET}\n")
    
    print("\n")

if __name__ == "__main__":
    main()
