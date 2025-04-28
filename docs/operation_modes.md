# JUnit Writer Operation Modes

JUnit Writer supports multiple operation modes that determine how test generation and self-healing processes are orchestrated. This document explains each mode, its benefits, and when to use it.

## Available Modes

JUnit Writer supports three primary modes:

1. **Standard Mode**: A sequential, deterministic workflow with fixed control flow
2. **Agent Mode**: An AI-driven, flexible workflow using Google's Agent Development Kit (ADK)
3. **Commit Mode**: A specialized mode for processing files changed in a specific commit

## Selecting a Mode

You can select a mode in two ways:

1. **CLI Flag**: Using the `--mode` option when running the tool
   ```bash
   python main.py generate path/to/your/SourceFile.kt --mode=agent
   ```

2. **Configuration File**: Setting a default in `application.yml`
   ```yaml
   orchestrator:
     defaultMode: standard   # "standard" or "agent"
   ```

The CLI flag takes precedence over the configuration file setting. If neither is specified, the tool defaults to standard mode.

## Standard Mode

### Overview

Standard Mode implements a fixed, sequential algorithm for test generation and self-healing. It follows a predetermined path through the test generation process, with all decision points hardcoded in the control flow.

### Key Components

- **TestGenerationOrchestrator**: The main orchestrator that coordinates the entire process
- **GenerateTestsUseCase**: The application-layer entry point that sets up dependencies and delegates to the orchestrator

### Workflow

1. Initial setup (read, embed, parse source file)
2. Resolve dependencies
3. Perform RAG search for similar code
4. Check for existing test file
5. Build context for LLM
6. Generate initial test code
7. Write test file
8. Run self-healing if enabled

![Standard Mode Workflow](diagrams/architecture_mermaid.md#standard-mode-workflow)

### Characteristics

- **Deterministic**: Follows the same path every time
- **Predictable**: Easy to trace and debug
- **Efficient**: Typically faster than agent mode for simple cases
- **Limited Flexibility**: Cannot explore alternative strategies beyond what's coded

### When to Use Standard Mode

- For simple, straightforward classes
- When you need predictable, consistent results
- When you want faster test generation
- For most day-to-day test generation tasks

## Agent Mode

### Overview

Agent Mode uses a multi-agent workflow powered by Google's Agent Development Kit (ADK) to generate and fix tests. It delegates specialized tasks to autonomous agents under a coordinating strategy, allowing for more flexible and potentially more powerful test generation. The ADK provides a framework for creating, coordinating, and executing multiple AI agents that can work together to solve complex problems.

### Key Components

- **AgentCoordinator**: Coordinates the execution of agents to achieve goals
- **AnalyzeAgent**: Analyzes the source code structure
- **GenerateAgent**: Generates test code based on analysis
- **RunTestAgent**: Runs and evaluates tests
- **FixAgent**: Fixes test failures

### Workflow

1. The AgentCoordinator initializes the process
2. The AnalyzeAgent analyzes the source code structure
3. The GenerateAgent generates test code based on the analysis
4. The RunTestAgent runs the tests and evaluates the results
5. If tests fail, the FixAgent attempts to fix the issues
6. Steps 4-5 repeat until tests pass or max attempts are reached

![Agent Mode Workflow](diagrams/architecture_mermaid.md#agent-mode-workflow)

### Characteristics

- **Flexible**: Can adapt to complex scenarios through multi-step reasoning
- **Intelligent**: Makes decisions based on analysis of code and errors
- **Thorough**: May produce better solutions by exploring alternative strategies
- **Resource-Intensive**: Typically requires more time and computational resources

### When to Use Agent Mode

- For complex classes with many dependencies
- When standard mode produces unsatisfactory results
- When you need more thorough test coverage
- For classes with complex business logic

## Commit Mode

### Overview

Commit Mode is specialized for processing files changed in a specific commit. It can use either standard or agent mode for the actual test generation, but adds commit-specific processing.

### Key Components

- **GenerateTestsForCommitUseCase**: Coordinates the generation of tests for files in a commit
- **SourceControlAdapter**: Interfaces with the version control system

### Workflow

1. Identify files changed in the specified commit
2. Filter files based on extension and other criteria
3. For each file, generate tests using either standard or agent mode
4. Optionally, process files in parallel

### Characteristics

- **Focused**: Targets only files changed in a specific commit
- **Efficient**: Can process multiple files in parallel
- **Flexible**: Can use either standard or agent mode for test generation
- **Integration-Friendly**: Works well with CI/CD pipelines

### When to Use Commit Mode

- After making changes to multiple files
- In CI/CD pipelines to automatically generate tests for changed files
- When you want to focus testing efforts on recently changed code

## Mode Comparison

| Feature | Standard Mode | Agent Mode | Commit Mode |
|---------|--------------|------------|-------------|
| Control Flow | Fixed, sequential | Flexible, agent-driven | Depends on underlying mode |
| Decision Making | Hardcoded logic | AI reasoning | Diff analysis + underlying mode |
| Flexibility | Limited | High | Moderate |
| Parallelization | No | Yes | Yes (for multiple files) |
| Self-healing | Fixed algorithm | Intelligent, adaptive | Depends on underlying mode |
| Speed | Faster | Slower | Depends on number of files |
| Use Case | Simple, predictable scenarios | Complex scenarios requiring reasoning | Incremental updates to tests |

## Configuration Options

### Standard Mode Configuration

```yaml
orchestrator:
  defaultMode: standard

generation:
  # Standard generation settings
  context_similarity_threshold: 0.75
  context_max_rag_examples: 6
  context_max_dependency_files: 15
  context_max_tokens: 300000

self_healing:
  enabled: true
  max_attempts: 3
```

### Agent Mode Configuration

```yaml
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

### Commit Mode Configuration

```yaml
# Commit mode can use either standard or agent mode
orchestrator:
  defaultMode: standard  # or "agent"

# Commit-specific settings
commit_mode:
  use_diff_focused_approach: true
  skip_similar_test_search: true
  skip_dependency_search: true
```

## Best Practices

1. **Start with Standard Mode**: Begin with standard mode for most cases, and switch to agent mode if needed
2. **Use Commit Mode for Batch Processing**: When working with multiple files, use commit mode
3. **Adjust Configuration Based on Results**: Fine-tune configuration settings based on the results you get
4. **Consider File Complexity**: Use agent mode for complex files with many dependencies
5. **Balance Speed and Quality**: Standard mode is faster, but agent mode may produce better results for complex cases

## Conclusion

JUnit Writer's multi-mode design provides flexibility to handle different test generation scenarios. By choosing the appropriate mode for your specific needs, you can optimize the test generation process for both speed and quality.

For more information on configuration options, see the [Configuration Guide](configuration.md).
