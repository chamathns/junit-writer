# JUnit Writer Architecture Diagrams

## High-Level Architecture

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

## Standard Mode Workflow

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

## Agent Mode Workflow

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

## Clean Architecture Layers

```
┌───────────────────────────────────────────────────────────┐
│                                                           │
│                     CLI / UI Layer                        │
│                                                           │
└───────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────┐
│                                                           │
│                   Application Layer                       │
│                                                           │
│  ┌─────────────────────┐      ┌─────────────────────┐    │
│  │                     │      │                     │    │
│  │    Use Cases        │      │   Orchestrators     │    │
│  │                     │      │                     │    │
│  └─────────────────────┘      └─────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────┐
│                                                           │
│                     Domain Layer                          │
│                                                           │
│  ┌─────────────────────┐      ┌─────────────────────┐    │
│  │                     │      │                     │    │
│  │      Models         │      │       Ports         │    │
│  │                     │      │                     │    │
│  └─────────────────────┘      └─────────────────────┘    │
│                                                           │
│  ┌─────────────────────┐      ┌─────────────────────┐    │
│  │                     │      │                     │    │
│  │     Services        │      │     Exceptions      │    │
│  │                     │      │                     │    │
│  └─────────────────────┘      └─────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────┐
│                                                           │
│                 Infrastructure Layer                      │
│                                                           │
│  ┌─────────────────────┐      ┌─────────────────────┐    │
│  │                     │      │                     │    │
│  │      Adapters       │      │    External APIs    │    │
│  │                     │      │                     │    │
│  └─────────────────────┘      └─────────────────────┘    │
│                                                           │
│  ┌─────────────────────┐      ┌─────────────────────┐    │
│  │                     │      │                     │    │
│  │    Repositories     │      │      ADK Tools      │    │
│  │                     │      │                     │    │
│  └─────────────────────┘      └─────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│               │     │               │     │               │
│  Source Code  │────▶│  Dependency   │────▶│  RAG Search   │
│               │     │  Resolution   │     │               │
└───────────────┘     └───────────────┘     └───────┬───────┘
                                                    │
                                                    ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│               │     │               │     │               │
│  Test Runner  │◀────│  Test File    │◀────│  LLM Service  │
│               │     │               │     │               │
└───────┬───────┘     └───────────────┘     └───────────────┘
        │
        ▼
┌───────────────┐     ┌───────────────┐
│               │     │               │
│  Error Parser │────▶│  Test Fixer   │
│               │     │               │
└───────────────┘     └───────────────┘
```

## Component Interaction Diagram

```
                      ┌───────────────────┐
                      │                   │
                      │       CLI         │
                      │                   │
                      └─────────┬─────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│                        ModeSelector                           │
│                                                               │
└───────────┬───────────────────────────────┬───────────────────┘
            │                               │
            ▼                               ▼
┌───────────────────────┐       ┌───────────────────────────────┐
│                       │       │                               │
│  StandardOrchestrator │       │      AgentCoordinator         │
│                       │       │                               │
└───────────┬───────────┘       └───────────────┬───────────────┘
            │                                   │
            ▼                                   ▼
┌───────────────────────┐       ┌───────────────────────────────┐
│                       │       │                               │
│  Domain Services      │       │      Agent Factory            │
│                       │       │                               │
└───────────┬───────────┘       └───────────────┬───────────────┘
            │                                   │
            ▼                                   ▼
┌───────────────────────┐       ┌───────────────────────────────┐
│                       │       │                               │
│  Infrastructure       │       │      ADK Tools                │
│  Adapters             │       │                               │
│                       │       │                               │
└───────────────────────┘       └───────────────────────────────┘
```
