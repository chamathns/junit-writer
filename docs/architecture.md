# JUnit Writer Architecture

JUnit Writer follows clean architecture principles to ensure maintainability, testability, and flexibility. This document provides an overview of the system architecture, key components, and their interactions.

## Clean Architecture Overview

JUnit Writer is structured in three main layers:

1. **Domain Layer**: Contains the core business logic, entities, and interfaces (ports)
2. **Application Layer**: Contains use cases and orchestration logic
3. **Infrastructure Layer**: Contains implementations of interfaces defined in the domain layer (adapters)

This separation ensures that the core business logic is independent of external frameworks and libraries, making it easier to test and maintain.

## Architecture Diagram

```
                        [ CLI (User Input) ]
                              |
                     +--------v--------+       (--mode selects path)
                     |  Orchestrator   |
                     |    Factory      |       (chooses Standard vs Agent orchestrator)
                     +---+---------+---+
                         |         |
           --------------|---------|--------------
           |             |         |             |
   [ Standard Mode ]     |         |    [ Agent Mode ]
   TestGenerationOrchestrator      |     AgentCoordinator (ADK)
   (Sequential workflow)           |     (Multi-agent orchestration)
                         |         |
                         v         v
                (calls common Domain services & uses models)
                         |         |
           --------------|---------|--------------
                         |         
                   [ Domain Layer ] 
                 - TestSpec, JUnitTest models
                 - ErrorAnalysis model
                 - Domain logic for generation & healing
                 - Ports (LLM, TestRunner, etc.)
                         |
           --------------|-------------------------------
                         |          
                  [ Infrastructure Layer ]
                 - CLI Adapter (parses args, invokes orchestrator)
                 - LLM API Client (implements LLM port)
                 - Test Runner (implements runner port)
                 - Code Editor (implements fix port)
                 - ADK library & agents (tools for agent mode)
```

## Key Components

### Domain Layer

The domain layer contains the core business logic and entities:

#### Domain Models

- **TestSpec**: Represents the specification for a test to be generated
- **JUnitTest**: Represents a generated JUnit test
- **ErrorAnalysis**: Represents the analysis of compilation or test errors
- **DependencyGraph**: Represents the dependency relationships between files

#### Domain Ports (Interfaces)

- **FileSystemPort**: Interface for file system operations
- **EmbeddingServicePort**: Interface for embedding generation
- **VectorDBPort**: Interface for vector database operations
- **LLMServicePort**: Interface for LLM interactions
- **CodeParserPort**: Interface for parsing code
- **TestRunnerPort**: Interface for running tests
- **UIServicePort**: Interface for user interface interactions

### Application Layer

The application layer contains use cases and orchestration logic:

#### Use Cases

- **GenerateTestsUseCase**: Coordinates the generation of tests for a single file
- **GenerateTestsForCommitUseCase**: Coordinates the generation of tests for files in a commit
- **IndexRepositoryUseCase**: Coordinates the indexing of a repository

#### Orchestrators

- **TestGenerationOrchestrator**: Orchestrates the standard mode test generation workflow
- **AgentCoordinator**: Orchestrates the agent mode test generation workflow using multiple agents

#### Services

- **DependencyResolverService**: Resolves dependencies between files
- **ContextBuilder**: Builds context for LLM prompts
- **ModeSelector**: Selects the appropriate mode based on configuration and CLI arguments
- **UIService**: Provides user interface functionality

### Infrastructure Layer

The infrastructure layer contains implementations of interfaces defined in the domain layer:

#### Adapters

- **FileSystemAdapter**: Implements file system operations
- **EmbeddingServiceAdapter**: Implements embedding generation
- **VectorDBAdapter**: Implements vector database operations
- **LLMServiceAdapter**: Implements LLM interactions
- **CodeParserAdapter**: Implements code parsing
- **TestRunnerAdapter**: Implements test running
- **UIAdapter**: Implements user interface interactions

#### CLI

- **ArgumentParser**: Parses command-line arguments
- **CommandHandlers**: Handles specific commands (index, generate)

#### ADK Tools

- **RunTestTool**: Tool for running tests
- **ParseErrorsTool**: Tool for parsing errors
- **GenerateFixTool**: Tool for generating fixes
- **ReadFileTool**: Tool for reading files
- **WriteFileTool**: Tool for writing files
- **ResolveDependenciesTool**: Tool for resolving dependencies

## Workflow Diagrams

### Standard Mode Workflow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Initial Setup  │────▶│    Resolve      │────▶│   RAG Search    │
│ (Read, Embed,   │     │  Dependencies   │     │                 │
│    Parse)       │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐     ┌────────▼────────┐
│   Self-Healing  │◀────│   Write Test    │◀────│  Generate Test  │
│  (if enabled)   │     │      File       │     │      Code       │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Agent Mode Workflow

```
┌─────────────────┐
│ AgentCoordinator│
│    (Start)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  AnalyzeAgent   │────▶│  GenerateAgent  │
│ (Analyze code   │     │ (Generate test  │
│  structure)     │     │     code)       │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌─────────────────┐
│    FixAgent     │◀────│   RunTestAgent  │
│ (Fix test       │     │ (Run and        │
│  failures)      │     │  evaluate test) │
└─────────────────┘     └─────────────────┘
```

## Design Patterns

JUnit Writer uses several design patterns:

- **Factory Pattern**: For creating adapters and services
- **Strategy Pattern**: For selecting different modes of operation
- **Adapter Pattern**: For interfacing with external systems
- **Facade Pattern**: For providing a simplified interface to complex subsystems
- **Command Pattern**: For encapsulating commands as objects
- **Observer Pattern**: For event handling and progress reporting

## Extensibility

The clean architecture and use of interfaces make JUnit Writer highly extensible:

- New LLM providers can be added by implementing the LLMServicePort
- New test frameworks can be supported by extending the test generation logic
- New languages can be supported by implementing appropriate parsers
- New operation modes can be added by creating new orchestrators

## Conclusion

JUnit Writer's architecture follows clean architecture principles to ensure maintainability, testability, and flexibility. The separation of concerns between layers allows for easy extension and modification of the system without affecting the core business logic.
