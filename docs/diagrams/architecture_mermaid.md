# JUnit Writer Architecture Diagrams (Mermaid)

## High-Level Architecture

```mermaid
flowchart TD
    CLI["CLI (User Input)"] --> OF["Orchestrator Factory"]
    OF -->|"--mode selects path"| SM["Standard Mode<br/>TestGenerationOrchestrator<br/>(Sequential workflow)"]
    OF -->|"--mode selects path"| AM["Agent Mode<br/>AgentCoordinator (ADK)<br/>(Multi-agent orchestration)"]

    subgraph Domain["Domain Layer"]
        DM["Domain Models<br/>- TestSpec<br/>- JUnitTest<br/>- ErrorAnalysis"]
        DP["Domain Ports<br/>- LLM<br/>- TestRunner<br/>- etc."]
    end

    SM --> Domain
    AM --> Domain

    Domain --> IL["Infrastructure Layer<br/>- CLI Adapter<br/>- LLM API Client<br/>- Test Runner<br/>- Code Editor<br/>- ADK library & agents"]
```

## Standard Mode Workflow

```mermaid
flowchart LR
    IS["Initial Setup<br/>(Read, Embed, Parse)"] --> RD["Resolve<br/>Dependencies"]
    RD --> RS["RAG Search"]
    RS --> GTC["Generate Test<br/>Code"]
    GTC --> WTF["Write Test<br/>File"]
    WTF --> SH["Self-Healing<br/>(if enabled)"]
```

## Agent Mode Workflow

```mermaid
flowchart TD
    AC["AgentCoordinator<br/>(Start)"] --> AA["AnalyzeAgent<br/>(Analyze code structure)"]
    AA --> GA["GenerateAgent<br/>(Generate test code)"]
    GA --> RTA["RunTestAgent<br/>(Run and evaluate test)"]
    RTA --> FA["FixAgent<br/>(Fix test failures)"]
    FA -.-> RTA
```

## Clean Architecture Layers

```mermaid
flowchart TD
    CLI["CLI / UI Layer"] --> AL["Application Layer"]

    subgraph AL["Application Layer"]
        UC["Use Cases"] --- OR["Orchestrators"]
    end

    AL --> DL["Domain Layer"]

    subgraph DL["Domain Layer"]
        MO["Models"] --- PO["Ports"]
        SE["Services"] --- EX["Exceptions"]
    end

    DL --> IL["Infrastructure Layer"]

    subgraph IL["Infrastructure Layer"]
        AD["Adapters"] --- EA["External APIs"]
        RE["Repositories"] --- AT["ADK Tools"]
    end
```

## Data Flow Diagram

```mermaid
flowchart LR
    SC["Source Code"] --> DR["Dependency<br/>Resolution"]
    DR --> RS["RAG Search"]
    RS --> LS["LLM Service"]
    LS --> TF["Test File"]
    TF --> TR["Test Runner"]
    TR --> EP["Error Parser"]
    EP --> TFX["Test Fixer"]
```

## Component Interaction Diagram

```mermaid
flowchart TD
    CLI["CLI"] --> MS["ModeSelector"]
    MS --> SO["StandardOrchestrator"]
    MS --> AC["AgentCoordinator"]
    SO --> DS["Domain Services"]
    AC --> AF["Agent Factory"]
    DS --> IA["Infrastructure\nAdapters"]
    AF --> AT["ADK Tools"]
```
