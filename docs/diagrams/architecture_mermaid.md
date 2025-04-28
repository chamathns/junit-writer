# JUnit Writer Architecture Diagrams (Mermaid)

## High-Level Architecture

```mermaid
flowchart TD
    CLI["CLI (User Input)"] --> OF["Orchestrator Factory"]
    OF -->|"--mode selects path"| SM["Standard Mode\nTestGenerationOrchestrator\n(Sequential workflow)"]
    OF -->|"--mode selects path"| AM["Agent Mode\nAgentCoordinator (ADK)\n(Multi-agent orchestration)"]
    
    subgraph Domain["Domain Layer"]
        DM["Domain Models\n- TestSpec\n- JUnitTest\n- ErrorAnalysis"]
        DP["Domain Ports\n- LLM\n- TestRunner\n- etc."]
    end
    
    SM --> Domain
    AM --> Domain
    
    Domain --> IL["Infrastructure Layer\n- CLI Adapter\n- LLM API Client\n- Test Runner\n- Code Editor\n- ADK library & agents"]
```

## Standard Mode Workflow

```mermaid
flowchart LR
    IS["Initial Setup\n(Read, Embed, Parse)"] --> RD["Resolve\nDependencies"]
    RD --> RS["RAG Search"]
    RS --> GTC["Generate Test\nCode"]
    GTC --> WTF["Write Test\nFile"]
    WTF --> SH["Self-Healing\n(if enabled)"]
```

## Agent Mode Workflow

```mermaid
flowchart TD
    AC["AgentCoordinator\n(Start)"] --> AA["AnalyzeAgent\n(Analyze code structure)"]
    AA --> GA["GenerateAgent\n(Generate test code)"]
    GA --> RTA["RunTestAgent\n(Run and evaluate test)"]
    RTA --> FA["FixAgent\n(Fix test failures)"]
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
    SC["Source Code"] --> DR["Dependency\nResolution"]
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
