# JUnit Writer Configuration Guide

JUnit Writer uses a YAML configuration file to customize its behavior. This document provides a comprehensive guide to all available configuration options.

## Configuration File Location

The configuration file is located at `config/application.yml`. You can create this file by copying the example configuration:

```bash
cp config/application.yml.example config/application.yml
```

## Configuration Sections

The configuration file is organized into several sections:

1. [General Settings](#general-settings)
2. [UI Settings](#ui-settings)
3. [Repository Indexing Settings](#repository-indexing-settings)
4. [Test Generation Settings](#test-generation-settings)
5. [Error Parsing Settings](#error-parsing-settings)
6. [Orchestrator Settings](#orchestrator-settings)
7. [Agent Configuration](#agent-configuration)
8. [Self-Healing Settings](#self-healing-settings)

## General Settings

These settings control general application behavior, including logging.

```yaml
logging:
  level: INFO                # Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: '%(asctime)s - %(name)s - %(levelname)s [%(module)s:%(lineno)d] - %(message)s'
  log_file: "var/logs/app.log"  # Path to log file
```

## UI Settings

These settings control the user interface appearance and behavior.

```yaml
ui:
  type: "rich"               # UI type: 'rich' (default) or 'tqdm'
  enhanced_logging: true     # Enable enhanced logging with colors and formatting
  progress_style: "spinner"  # Progress bar style (only for rich UI): 'bar', 'spinner', or 'text'
  theme: "default"           # Color theme: 'default', 'dark', 'light'
```

## Repository Indexing Settings

These settings control how the repository is indexed.

```yaml
repository:
  root_path: "/path/to/your/kotlin/project"  # Path to the repository root
  exclude_patterns:                           # Patterns to exclude from indexing
    - "**/.git/**"
    - "**/build/**"
    - "**/target/**"
  include_patterns:                           # Patterns to include in indexing
    - "**/*.kt"
    - "**/*.java"
  test_file_patterns:                         # Patterns to identify test files
    - "**/*Test.kt"
    - "**/*Tests.kt"
    - "**/test/**/*.kt"
  index_file: "var/repository_index.json"     # Path to the index file
```

## Test Generation Settings

These settings control how tests are generated.

```yaml
generation:
  # LLM Provider configuration
  llm_provider: "google_gemini"     # Options: "google_gemini", "mock"
  model_name: "gemini-2.0-flash"    # Model name to use

  # API Key: Set the GOOGLE_API_KEY environment variable
  # Or uncomment and set here (less secure):
  # api_key: "YOUR_API_KEY_HERE"

  # Output directory for generated tests (relative to project root)
  output_dir: "generated-tests"

  # RAG Context settings for generation
  context_similarity_threshold: 0.75  # Minimum similarity score (0.0 to 1.0)
  context_max_rag_examples: 6         # Max RAG examples to include
  context_max_dependency_files: 15    # Max dependency files to include
  context_max_tokens: 300000          # Target token limit for context

  # Intelligent context building
  use_intelligent_context: true    # Use the intelligent context builder with dependency graph
  use_layer_aware_generation: true # Use layer-aware test generation

  # Prompting settings
  target_language: "Kotlin"
  target_framework: "JUnit5 with MockK"
```

## Error Parsing Settings

These settings control how errors are parsed during self-healing.

```yaml
error_parsing:
  adapter: "regex"  # Options: "llm", "regex"
```

## Orchestrator Settings

These settings control the orchestration of test generation.

```yaml
orchestrator:
  defaultMode: standard   # "standard" or "agent"; used if CLI --mode not specified
```

## Agent Configuration

These settings control the behavior of agents in agent mode.

```yaml
agents:
  enabled: true
  coordinator:
    max_goal_attempts: 3

  # Individual agent configuration
  index:
    model: "gemini-2.0-flash"
    max_iterations: 3

  generate:
    model: "gemini-2.0-pro"
    max_iterations: 5
    success_criteria:
      - "compiles_successfully"
      - "covers_public_methods"

  fix:
    model: "gemini-2.0-pro"
    max_iterations: 3
    success_criteria:
      - "compiles_successfully"

  analyze:
    model: "gemini-2.0-flash"
    max_iterations: 2
```

## Self-Healing Settings

These settings control the self-healing behavior.

```yaml
self_healing:
  enabled: true     # Whether to attempt to fix compilation errors
  max_attempts: 3   # Maximum number of fix attempts
  max_parallel_agents: 3  # Maximum number of parallel error analysis agents
  use_intelligent_fix: true  # Use the new intelligent error analysis system
```

## Environment Variables

Some configuration options can be set using environment variables:

- `GOOGLE_API_KEY`: Google Gemini API key
- `JUNIT_WRITER_CONFIG_PATH`: Path to the configuration file
- `JUNIT_WRITER_REPO_ROOT`: Repository root path

Environment variables take precedence over values in the configuration file.

## Example Configurations

### Basic Configuration

```yaml
logging:
  level: INFO
  log_file: "var/logs/app.log"

repository:
  root_path: "/path/to/your/kotlin/project"

generation:
  llm_provider: "google_gemini"
  model_name: "gemini-2.0-flash"
  output_dir: "generated-tests"

orchestrator:
  defaultMode: standard

self_healing:
  enabled: true
  max_attempts: 3
```

### Agent Mode Configuration

```yaml
logging:
  level: INFO
  log_file: "var/logs/app.log"

repository:
  root_path: "/path/to/your/kotlin/project"

generation:
  llm_provider: "google_gemini"
  model_name: "gemini-2.0-flash"
  output_dir: "generated-tests"

orchestrator:
  defaultMode: agent

agents:
  enabled: true
  coordinator:
    max_goal_attempts: 3
  generate:
    model: "gemini-2.0-flash"
    max_iterations: 5
  fix:
    model: "gemini-2.0-flash"
    max_iterations: 3

self_healing:
  enabled: true
  max_attempts: 3
```

### Advanced RAG Configuration

```yaml
logging:
  level: INFO
  log_file: "var/logs/app.log"

repository:
  root_path: "/path/to/your/kotlin/project"

generation:
  llm_provider: "google_gemini"
  model_name: "gemini-2.0-flash"
  output_dir: "generated-tests"
  context_similarity_threshold: 0.85
  context_max_rag_examples: 10
  context_max_dependency_files: 20
  context_max_tokens: 500000
  use_intelligent_context: true
  use_layer_aware_generation: true

orchestrator:
  defaultMode: standard

self_healing:
  enabled: true
  max_attempts: 3
```

## Configuration Best Practices

1. **Security**: Store API keys in environment variables rather than in the configuration file
2. **Performance**: Adjust `context_max_rag_examples` and `context_max_dependency_files` based on your project's complexity
3. **Customization**: Start with the default configuration and adjust settings as needed
4. **Testing**: Test different configurations to find the optimal settings for your project

## Troubleshooting

If you encounter issues with your configuration:

1. Check the log file for error messages
2. Verify that all paths are correct and accessible
3. Ensure that API keys are set correctly
4. Try running with default settings to isolate the issue

For more help, see the [Getting Started](getting_started.md) guide.
