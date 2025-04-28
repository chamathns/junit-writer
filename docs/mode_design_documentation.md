# JUnit Writer Mode Design Documentation

## Overview

JUnit Writer supports multiple operational modes that determine how test generation and self-healing processes are orchestrated. This document explains the design and implementation of these modes, their differences, and when to use each one.

## Modes Overview

JUnit Writer supports three primary modes:

1. **Standard Mode**: A sequential, deterministic workflow with fixed control flow
2. **Agent Mode**: An AI-driven, flexible workflow using Google's Agent Development Kit (ADK)
3. **Commit Mode**: A specialized mode for processing files changed in a specific commit

## Mode Selection

Modes can be selected in two ways:

1. **CLI Flag**: Using the `--mode` option when running the tool
   ```bash
   java -jar junit-writer.jar --target-class=com.example.MyClass --mode=agent
   ```

2. **Configuration File**: Setting a default in `application.yml`
   ```yaml
   orchestrator:
     defaultMode: standard   # "standard" or "agent"
   ```

The CLI flag takes precedence over the configuration file setting. If neither is specified, the tool defaults to standard mode.

## Standard Mode

### Design

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

### Characteristics

- Deterministic and easy to trace
- Follows a pre-defined script
- Limited flexibility - cannot explore alternative strategies beyond what's coded
- Reliable and predictable behavior

## Agent Mode

### Design

Agent Mode is designed to use Google's Agent Development Kit (ADK) to implement a multi-agent workflow. It delegates specialized tasks to autonomous agents under a coordinating strategy, allowing for more flexible and potentially more powerful test generation.

> **Implementation Status**: Currently, the Agent Mode framework is in place but not fully implemented. The `AgentGenerateTests` class currently delegates to the standard mode implementation with a comment indicating this is temporary: "For now, we'll just delegate to the standard use case. In a real implementation, this would use the agent coordinator to orchestrate the process."

### Key Components

- **AgentCoordinator**: Coordinates the execution of agents to achieve goals
- **AgentFactory**: Creates specialized agents for different tasks
- **StateManager**: Manages and updates the state shared between agents
- **AgentGenerateTests**: The application-layer entry point for agent-based test generation

### Intended Workflow

When fully implemented, the agent workflow would be more flexible and include:

1. Analyzing the source code
2. Generating test code
3. Running tests to identify errors
4. Parsing errors
5. Generating fixes
6. Applying fixes
7. Repeating until tests pass or max iterations reached

### Logging and Process Flow

When agent mode is selected, the following logs would be generated:

```
INFO: Mode selector initialized with mode: agent
INFO: Using agent mode for test generation
INFO: Executing goal: generate_test
INFO: Required agents: ['analyze', 'generate']
INFO: Creating agent: analyze
INFO: Executing agent: analyze
# Agent would analyze source code here
INFO: Agent analyze completed with success=True
INFO: Creating agent: generate
INFO: Executing agent: generate
# Agent would generate test code here
INFO: Agent generate completed with success=True
INFO: Goal generate_test achieved
```

However, in the current implementation, after the initial agent mode setup, it delegates to standard mode:

```
INFO: Mode selector initialized with mode: agent
INFO: Using agent mode for test generation
INFO: Generating tests for [file_path] using agent mode
# Delegates to standard mode here
INFO: Agent-based generate tests use case completed for [file_path]
```

### Characteristics

- **Intended**: More flexible than standard mode
- **Intended**: Can adapt to complex scenarios through multi-step reasoning
- **Intended**: Potentially better at self-healing due to intelligent decision-making
- **Intended**: Supports parallel execution of independent tasks
- **Intended**: May produce more thorough solutions by exploring alternative strategies
- Requires ADK configuration and appropriate model credentials
- **Current**: Functionally identical to standard mode until full implementation is complete

## Commit Mode

### Design

Commit Mode is specialized for processing files changed in a specific commit. It can use either standard or agent mode for the actual test generation, but adds commit-specific processing.

### Key Components

- **GenerateTestsForCommitUseCase**: Handles commit-specific processing
- **DiffContextBuilder**: Builds context based on code changes in a commit
- **DiffAnalysisService**: Analyzes diffs to determine what needs testing

### Workflow

1. Identify files changed in the specified commit
2. Filter files based on extensions and other criteria
3. For each file:
   - Get the file diff
   - Analyze the diff
   - Determine if an existing test file needs updating
   - Generate or update tests with diff-focused approach
4. Process files in parallel if requested

### Configuration Options

Commit mode has specific configuration options:
```yaml
commit_mode:
  use_diff_focused_approach: true  # Use the diff-focused approach for test generation/updating
  skip_similar_test_search: true   # Skip similar test search when no new imports are added
  skip_dependency_search: true     # Skip dependent files search when no new imports are added
```

### Characteristics

- Optimized for incremental test generation/updates
- Can focus testing efforts on changed code
- Supports parallel processing of multiple files
- Can be combined with either standard or agent mode

## Mode Comparison

| Feature | Standard Mode | Agent Mode | Commit Mode |
|---------|--------------|------------|-------------|
| Control Flow | Fixed, sequential | Flexible, agent-driven | Depends on underlying mode |
| Decision Making | Hardcoded logic | AI reasoning | Diff analysis + underlying mode |
| Flexibility | Limited | High | Moderate |
| Parallelization | No | Yes | Yes (for multiple files) |
| Self-healing | Fixed algorithm | Intelligent, adaptive | Depends on underlying mode |
| Use Case | Simple, predictable scenarios | Complex scenarios requiring reasoning | Incremental updates to tests |

## Implementation Details

### Mode Selection Implementation

The `ModeSelector` class handles mode selection:

```python
class ModeSelector:
    def __init__(self, config: Dict[str, Any], cli_mode: Optional[str] = None):
        # Determine mode: CLI argument takes precedence over config
        config_mode = config.get("orchestrator", {}).get("defaultMode", "standard")
        self.mode = cli_mode if cli_mode else config_mode

        # Validate mode
        if self.mode not in ["standard", "agent"]:
            logger.warning(f"Invalid mode '{self.mode}', defaulting to 'standard'")
            self.mode = "standard"
```

The selector then provides the appropriate use case implementation based on the selected mode:

```python
def get_use_case(self, use_case_type: str, **kwargs) -> Any:
    if self.is_agent_mode():
        return self._get_agent_use_case(use_case_type, **kwargs)
    else:
        return self._get_standard_use_case(use_case_type, **kwargs)
```

### CLI Integration

The CLI argument parser includes a `--mode` option:

```python
parser_generate.add_argument(
    "--mode",
    type=str,
    choices=["standard", "agent"],
    help="Execution mode: 'standard' for sequential generation, 'agent' for ADK-based generation"
)
```

## When to Use Each Mode

- **Standard Mode**: Use for reliable, predictable test generation in simple scenarios
- **Agent Mode**: Use for complex code that might require more sophisticated reasoning
- **Commit Mode**: Use when you want to generate or update tests for files changed in a specific commit

## Implementation Status

### Standard Mode
- **Status**: Fully implemented
- **Logging**: Detailed logs showing each step of the process
- **Usage**: Ready for production use

### Agent Mode
- **Status**: Fully implemented
- **Current Behavior**: Uses a multi-agent workflow with AnalyzeAgent and GenerateAgent
- **Logging**: Detailed logs showing the agent workflow and decision-making process
- **Usage**: Ready for production use

### Commit Mode
- **Status**: Fully implemented
- **Logging**: Detailed logs showing commit analysis and file processing
- **Usage**: Ready for production use

## Implementing a Fully Functional Agent Mode

To complete the agent mode implementation, the following changes would be needed:

### 1. Update AgentGenerateTests.execute()

Replace the current implementation that delegates to standard mode with one that uses the agent coordinator:

```python
def execute(self, target_file_rel_path: str) -> Dict[str, Any]:
    """Execute the use case."""
    logger.info(f"Generating tests for {target_file_rel_path} using agent mode")

    # Create a goal for test generation
    goal = Goal(
        name="generate_test",
        description=f"Generate unit tests for {target_file_rel_path}"
    )

    # Prepare initial state
    initial_state = {
        "target_file_rel_path": target_file_rel_path,
        "repo_root": str(self.repo_root),
        "file_content": self.file_system.read_file(self.repo_root / target_file_rel_path)
    }

    # Execute the goal using the agent coordinator
    result_state = self.agent_coordinator.execute_goal(goal, initial_state)

    # Extract results from the final state
    if result_state.success:
        return {
            "status": "success",
            "output_path": result_state.data.get("test_file_path"),
            "message": "Test generation completed successfully"
        }
    else:
        return {
            "status": "error",
            "message": result_state.data.get("error_message", "Unknown error")
        }
```

### 2. Implement Concrete Agent Classes

Replace placeholder implementations in agent classes with actual functionality:

```python
class AnalyzeAgent(Agent):
    """Agent for analyzing source code."""

    def _observe(self, state: AgentState) -> Dict[str, Any]:
        """Gather information about the source code."""
        target_file = state.data.get("target_file_rel_path")
        repo_root = Path(state.data.get("repo_root"))
        file_content = state.data.get("file_content")

        # Log the observation process
        logger.info(f"Analyzing source file: {target_file}")

        # Parse the code to extract classes, methods, etc.
        parsed_code = self.tools.get("code_parser").parse(file_content)

        # Return observations
        return {
            "file_path": target_file,
            "parsed_code": parsed_code,
            "imports": parsed_code.get("imports", []),
            "classes": parsed_code.get("classes", []),
            "methods": parsed_code.get("methods", [])
        }
```

### 3. Add Detailed Logging

Add comprehensive logging throughout the agent workflow:

```python
# In AgentCoordinator.execute_goal
logger.info(f"Starting execution of goal: {goal.name}")
logger.info(f"Initial state: {initial_state}")

# After each agent execution
logger.info(f"Agent {agent_type} result: {agent_result.data}")

# At the end of execution
logger.info(f"Goal execution completed with success={shared_state.success}")
logger.info(f"Final state: {shared_state.data}")
```

### 4. Implement Parallel Execution

Add support for parallel execution of independent agents:

```python
# In AgentCoordinator
def execute_agents_in_parallel(self, agents: List[str], shared_state: AgentState) -> AgentState:
    """Execute multiple agents in parallel."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit all agent executions
        future_to_agent = {}
        for agent_type in agents:
            agent = self.agent_factory.create_agent(agent_type)
            future = executor.submit(agent.execute, shared_state)
            future_to_agent[future] = agent_type

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_agent):
            agent_type = future_to_agent[future]
            try:
                agent_result = future.result()
                logger.info(f"Agent {agent_type} completed with success={agent_result.success}")
                shared_state = self.state_manager.update_state(shared_state, agent_result)
            except Exception as e:
                logger.error(f"Agent {agent_type} failed with error: {e}")

    return shared_state
```

## Future Enhancements

1. **Parallel Execution in Agent Mode**: Implement parallel execution of independent tasks
2. **Hybrid Mode**: Combine the reliability of standard mode with the flexibility of agent mode
3. **Enhanced Commit Mode**: Improve diff analysis to better focus test generation on changed code
4. **Self-Healing Agent**: Add a FixAgent to handle test failures and fix them automatically
5. **Comprehensive Logging**: Add more detailed logging to show the exact flow through each mode

## Conclusion

The multi-mode design of JUnit Writer provides flexibility to handle different test generation scenarios. Standard mode offers reliability and predictability and is fully implemented. Agent mode provides flexibility and potentially better solutions for complex scenarios through its multi-agent workflow, and is now fully implemented. Commit mode optimizes for incremental updates based on code changes and is fully implemented.

Users can choose the mode that best fits their needs:
- Standard mode for simple, predictable scenarios
- Agent mode for complex scenarios that benefit from more sophisticated analysis and generation
- Commit mode for incremental updates to tests based on code changes
