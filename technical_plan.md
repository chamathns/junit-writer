# Technical Plan for JUnit Writer – Standard vs Agent Mode Integration

## Overview

This technical plan outlines how to extend the existing **JUnit Writer** architecture to support two operational modes – *Standard Mode* and *Agent Mode* – while preserving a clean hexagonal design. The goal is to **share core logic** (domain and application layer code) between modes, diverging only in orchestration. In *Standard Mode*, a sequential `TestGenerationOrchestrator` will directly coordinate test generation and self-healing. In *Agent Mode*, a new ADK-powered `AgentCoordinator` will orchestrate multiple specialized agents (for generation, error analysis, healing, etc.) to achieve the same outcome. Both modes will leverage the same domain models (e.g. test specifications, error reports) and ports (interfaces to external systems), aligning with clean architecture principles where the Application layer acts as an orchestrator over the Domain logic ([Rules to Better Clean Architecture | SSW.Rules](https://www.ssw.com.au/rules/rules-to-better-clean-architecture/#:~:text=2,the%20system%20and%20enforcing%20invariants)). A CLI flag `--mode` will allow explicit selection of the mode at runtime. The following sections detail the updated architecture, component responsibilities, model/port adjustments, CLI behavior, self-healing approach, parallelization in agent mode, configuration changes, and a phased implementation plan.

## Updated High-Level Architecture Diagram

**Architecture Overview:** The system will maintain a three-layer clean architecture (Domain, Application, Infrastructure), now with two orchestration pathways in the Application layer. The core/domain logic remains unified and independent of the orchestration mode, ensuring minimal duplication. Below is a high-level outline of the layers and components:

- **Domain Layer (Core):** Contains business logic and data models for test generation. Key domain models include *Test Specification* (details of class/methods under test), *GeneratedTestSuite* (the output JUnit tests), and *ErrorAnalysis* (structured information about test failures). Domain services encapsulate logic like *test case generation rules*, *error classification*, and *test/code patch application*. These are pure logic, not depending on whether we use agents or not. The Domain layer exposes *ports* (interfaces) for any external interactions needed (e.g., calling an LLM, compiling/running code), and it enforces invariants and rules of test generation. This design ensures the Application layer can orchestrate domain operations without duplicating logic ([Rules to Better Clean Architecture | SSW.Rules](https://www.ssw.com.au/rules/rules-to-better-clean-architecture/#:~:text=2,the%20system%20and%20enforcing%20invariants)).

- **Application Layer (Use Cases):** Houses orchestrator components that coordinate the workflow. We will introduce two orchestrators:
  - **Standard Orchestrator:** A use-case class (e.g. `TestGenerationOrchestrator`) that implements the test generation and healing flow as a direct, sequential process (non-agent). It invokes domain services/ports in order (generate → run → analyze → heal) to produce passing JUnit tests.
  - **Agent Orchestrator:** A new `AgentCoordinator` component that leverages Google’s ADK to manage a team of agents for test generation and self-healing. It sets up a coordinator/dispatcher agent and specialized sub-agents for each task. The *AgentCoordinator* still resides in the Application layer, orchestrating domain logic via agents instead of direct calls. The two orchestrators share as much code as possible by calling into common domain services and models; they only differ in control flow (one is hardcoded sequence, the other is agent-driven). Both orchestrators implement a common interface (e.g. `TestGenerationUseCase`) or follow the same port so that the CLI can invoke either interchangeably.

- **Infrastructure Layer (Adapters):** Contains implementations of the domain ports and external interfaces, as well as the CLI. Examples:
  - *CLI Adapter:* Parses command-line arguments (including `--mode`) and calls the appropriate Application layer orchestrator.
  - *LLM Service Adapter:* Implements the LLM port (for example, calling OpenAI/Vertex AI API) for generating test content or analyzing errors in Standard Mode. In Agent Mode, ADK may handle LLM calls internally, but we will configure it to use the same model credentials (ensuring consistency in model usage).
  - *Test Runner Adapter:* Implements running the compiled JUnit tests (e.g. invoking Maven/JUnit engine) and returns results in a domain-friendly format.
  - *Code Editor/Compiler Adapter:* If needed, applies fixes to the code or tests (e.g. inserting the generated tests into files, or making code changes if suggested).
  - *ADK Integration:* The ADK library is used here to create and run agents. While ADK is an external framework, we treat it as part of the Infrastructure that the AgentCoordinator uses. For instance, we might wrap test execution as an ADK *Tool* that agents can call. The AgentCoordinator will translate domain objects to/from ADK agent context (prompts, tool inputs/outputs).

All dependencies flow inward (in classic clean architecture style): both orchestrators depend on domain interfaces and models, and infrastructure implements the interfaces. This preserves a flexible design where adding the agent mode does not ripple changes through the domain logic. **Figure 1** below conceptually illustrates the architecture with the two modes coexisting (shared core, divergent orchestration):

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

*Figure 1: High-level architecture with dual orchestration modes (Standard vs Agent). Both modes leverage the same Domain models/services and Infrastructure adapters; only the Application-layer orchestration differs.*

## Detailed Component Responsibilities (Standard Orchestrator vs Agent Orchestrator)

In this section we detail how each mode’s orchestrator functions, highlighting the division of responsibilities between Standard and Agent paths. Both orchestrators aim to achieve the same end result (a suite of passing JUnit tests), but via different control mechanisms. The *Standard Orchestrator* uses a fixed sequential algorithm, whereas the *Agent Orchestrator* uses the ADK-driven multi-agent workflow. The core/domain operations (generate test, run test, analyze failure, apply fix) remain conceptually the same in both. Below we break down responsibilities for each orchestrator:

### Standard Mode Orchestrator (Sequential Workflow)

- **Component:** `TestGenerationOrchestrator` (existing class, possibly refined). This is the primary coordinator in standard mode.
- **Responsibility:** Directly orchestrates the test generation flow step-by-step, invoking domain services and ports in a predetermined sequence. It does not employ any agent; instead, it calls functions/procedures.
- **Workflow:** 
  1. **Initialize Generation:** Prepare input data for test generation (e.g. identify target class or methods, possibly gather method signatures via reflection or source code). This yields a *TestSpecification* domain object describing what to test.
  2. **Generate Tests:** Invoke the *Test Generation* use-case in the domain. Likely this calls an LLM via a port (e.g. `LLMService.generateTests(spec)`) to produce candidate test code. The orchestrator may provide a prompt template and context (like code under test) to the LLM. The result is captured as a domain model, e.g. a *GeneratedTestSuite* (containing test class code or AST).
  3. **Compile & Run Tests:** Use the *Test Runner port* to compile and execute the generated tests against the target code. This could involve saving the tests to a .java file and invoking JUnit (perhaps via an embedded JUnit runner or an external process). The result is a *TestResult* domain object indicating success or failures (including any stack traces or error messages).
  4. **Analyze Failures:** If tests failed or did not compile, call the *ErrorAnalysis* logic. For example, use an `ErrorAnalyzer` domain service or directly call an LLM (via a port) to interpret the failure output. The output is an *ErrorAnalysis* domain model capturing the root cause and possibly suggestions for fixes. At this point, the orchestrator decides on a remedy. For instance, if the failure is due to an assertion mismatch, the fix might be to adjust the expected value in the test; if due to a null pointer exception in the code under test, the fix might involve either altering the test to handle it or flagging a potential bug.
  5. **Apply Healing (Fixes):** Invoke the appropriate healing action. This could mean modifying the generated tests or even generating a patch for the source code. In Standard mode, this might be another LLM call (e.g., "Given the test failure analysis, propose a corrected test or code change"). Alternatively, the orchestrator might apply a simple heuristic fix (like catch an exception, or adjust an assertion) if it’s straightforward. The fixed output is then updated in the *GeneratedTestSuite* or in the source code via a port.
  6. **Loop & Retry:** The orchestrator repeats the cycle: re-run tests to see if the fix resolved the issues. It will iterate until all tests pass or a maximum number of attempts is reached. This loop is explicitly coded in the orchestrator. For example:
     ```java
     for(int attempt=1; attempt<=MAX_ATTEMPTS; attempt++){
         generateTests();
         result = runTests();
         if(result.isSuccess()) break;
         analysis = analyzeErrors(result);
         applyFix(analysis);
     }
     ```
     Each iteration uses updated information. If max attempts exceeded, it may abort and report failure.
- **Output:** On success, the orchestrator returns or persists the final passing JUnit test suite (and possibly writes it to files). On failure, it returns an error or partial result with tests that still fail.
- **Error Handling:** The Standard orchestrator must handle exceptions at each step (e.g., API failures, compilation errors) and decide whether to retry or fail. It uses simple conditional logic for flow control.
- **Characteristic:** Deterministic and easy to trace. All decisions are encoded in the control flow. However, it may be limited in flexibility – it follows a pre-defined script and might not explore alternative strategies beyond what’s coded.

### Agent Mode Orchestrator (ADK Multi-Agent Workflow)

- **Component:** `AgentCoordinator` (new Application-layer class). This component utilizes Google’s **Agent Development Kit (ADK)** to manage a group of agents that collectively perform test generation and self-healing. The AgentCoordinator essentially sets up the multi-agent system and triggers it.
- **Responsibility:** Orchestrates the same overall workflow (generate → run → analyze → fix) but via autonomous agents that communicate and act. The AgentCoordinator’s job is to configure these agents, start the process, and monitor/collect results. Importantly, core logic (test content generation, error reasoning) is still in the domain or in the prompts given to agents – the difference is that agents themselves can make decisions and run in flexible order as needed.
- **Agent Hierarchy & Roles:** We propose an agent team with a **Coordinator agent** and specialized sub-agents:
  - **Coordinator Agent:** An ADK **LlmAgent** acting as a dispatcher or high-level planner. It receives the high-level goal (e.g. *"Generate a complete JUnit test suite for class X that passes all tests"*). The coordinator breaks down the task and delegates to sub-agents accordingly ([Multi-agent systems - Agent Development Kit](https://google.github.io/adk-docs/agents/multi-agents/#:~:text=Coordinator%2FDispatcher%20Pattern%C2%B6)). In ADK’s terms, this follows the *Coordinator/Dispatcher pattern*, where a central agent manages specialist agents ([Multi-agent systems - Agent Development Kit](https://google.github.io/adk-docs/agents/multi-agents/#:~:text=,sub_agents)). The coordinator’s prompt (instructions) encodes the strategy: for example, it might be instructed *"If generation of tests is needed, invoke the Test Generation Agent; if tests fail, invoke the Healing Agent,"* etc. This can be achieved via ADK’s LLM-driven delegation or explicit tool invocation.
  - **Test Generation Agent:** A specialized *LLM Agent* responsible for writing JUnit tests. Its prompt might be along the lines of *"You are TestGeneratorAgent. Given the source code or specification of class X, produce JUnit 5 test methods covering its functionality."* It uses the LLM to generate test code. This agent might output the tests in a format the system can capture (perhaps as code text or structured data). The domain’s test generation knowledge (like templates or naming conventions) can be baked into this agent’s prompt or provided as reference.
  - **Test Execution Agent/Tool:** Rather than an LLM agent, test execution is a deterministic action. We will expose running tests as an ADK **Tool** that agents can call. ADK allows defining custom tools (functions) accessible to agents ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=1,messages%2C%20events%2C%20and%20state%20management)). We will implement a tool (e.g. `run_tests_tool`) that, when invoked, triggers the Domain’s TestRunner port to compile and run the current tests, then returns the results (perhaps summarized). This tool can be called by the coordinator or a dedicated agent to get test results. (Alternatively, we could have a simple *BaseAgent* that just runs tests when activated, but using a tool is straightforward).
  - **Error Analysis Agent:** An LLM agent specialized in interpreting test failures. It would take the test results (especially any failures) and analyze the cause. Its instruction might be *"You are ErrorAnalyzerAgent. Given test failure output (stack traces, assertions), identify the likely cause and suggest what to change in the tests or code."* This agent’s output would populate the *ErrorAnalysis* domain model (e.g., it could return a structured explanation and a proposed solution).
  - **Healing Agent (Test Fixer Agent):** An LLM agent focused on applying the fix. This could potentially be combined with the ErrorAnalysis agent (one agent could both identify and propose fix), but separating concerns can be cleaner. The Healing agent’s role: *"Given an error analysis and the current test/code, provide the revised test code or code fix to resolve the issue."* For example, if the error analysis says “expected output was wrong”, the Healing agent would adjust the expected value in the test; if it says “method under test throws an exception”, perhaps catch it or adjust the test expectation. The output is a patch or new version of the test (or a code change). We may implement this as part of the Test Generation agent (just re-generate tests with constraints) or a separate agent. In design, having a separate *Fixer agent* that specifically takes error context and produces a diff or updated code is useful.
- **Workflow & Orchestration:** The AgentCoordinator can implement the workflow in two possible ways:
  1. **LLM-driven Orchestration:** Make the Coordinator agent truly autonomous in deciding steps. The coordinator LLM agent could be given high-level instructions to decide when to call each sub-agent. It could use ADK’s **AutoFlow** delegation (where the coordinator’s LLM output triggers `transfer_to_agent` calls) ([Multi-agent systems - Agent Development Kit](https://google.github.io/adk-docs/agents/multi-agents/#:~:text=Leverages%20an%20LlmAgent%27s%20understanding%20to,suitable%20agents%20within%20the%20hierarchy)) ([Multi-agent systems - Agent Development Kit](https://google.github.io/adk-docs/agents/multi-agents/#:~:text=,wrapped)). For instance, after generation, the coordinator might see that tests need running and issue a function call to the `run_tests_tool`; based on results, it might delegate to the ErrorAnalysis agent, and so on. This is very dynamic but requires a well-crafted prompt for the coordinator and clear agent descriptions.
  2. **Structured Workflow Orchestration:** Use ADK’s *workflow agents* to orchestrate a fixed loop with more control. ADK supports **Sequential, Parallel, and Loop agents** for predictable patterns ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=capabilities%2C%20enabling%20natural%2C%20human,routing%20for%20more%20adaptive%20behavior)). We can set up a Sequential flow of [Generate → Run → Analyze → Fix] and wrap it in a Loop agent that repeats until success. For example, define:
     - A `SequentialAgent` that first invokes TestGenerationAgent, then calls `run_tests_tool`. If the result indicates failure, it then invokes ErrorAnalysisAgent and HealingAgent to update the tests.
     - A `LoopAgent` that repeats the SequentialAgent until a stopping condition is met (all tests pass or max iterations) ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=The%20,until%20a%20condition%20is%20met)). The stopping condition can be evaluated via a small custom agent or a callback that checks the last test results.
     Using ADK’s LoopAgent provides a clear structure: *“keep generating and fixing until tests pass.”* The framework will handle the loop logic, avoiding infinite cycles by either a provided condition or a max iteration bound ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=loop_agent%20%3D%20LoopAgent%28%20name%3D,Optional%20maximum%20iterations)) ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=iterative_processor%20%3D%20LoopAgent%28%20name%3D,task_processor)).
  In practice, we might combine both approaches: structured looping for the high-level repetition, but within each loop iteration, allow the coordinator or agents some autonomy (e.g., the generation agent might internally decide how many tests to write, and the healing agent might decide how to fix).
- **Parallelization:** In agent mode, certain tasks can be run concurrently when appropriate (discussed more in the Parallelization section below). The AgentCoordinator could, for example, use a `ParallelAgent` to spawn multiple generation agents for different target classes or multiple fix attempts in parallel, then gather results ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=)) ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=Parallel%20execution%20is%20particularly%20useful,for)). The coordinator might also run test execution and analysis in parallel for multiple failing tests. Essentially, ADK allows fan-out of independent tasks, which the Standard orchestrator cannot do as easily.
- **State and Data Flow:** Agents will share state via the ADK context. For instance, the TestGeneration agent’s output (the test code) needs to be accessible to the run_tests tool and subsequently to the error analysis agent. ADK facilitates this by storing outputs in a state store (each agent can put outputs into the shared state for others to read) ([Multi-agent systems - Agent Development Kit](https://google.github.io/adk-docs/agents/multi-agents/#:~:text=agent_A%20%3D%20LlmAgent%28name%3D,stored%20in%20state%20key%20%27capital_city)). The AgentCoordinator will map these inputs/outputs to domain models:
  - After the generation agent finishes, the AgentCoordinator can take the returned test code (perhaps as a string) and construct a *GeneratedTestSuite* domain object. This can be passed to the test-runner tool or kept in memory.
  - Test results from the tool are captured (the tool can directly produce an *ErrorAnalysis* or *TestResult* object, or a JSON that the next agent consumes).
  - The healing agent’s output (modified code) is applied via the domain (e.g., using the Code Editor port to actually apply the diff to the in-memory test representation).
- **Output:** When the loop completes successfully, the AgentCoordinator collects the final test suite from the generation agent’s state (which has been updated through any healing steps) and returns it. The end result is equivalent: a passing JUnit test suite. If the agents exhaust the max attempts without success, the coordinator will report failure (and possibly include the last error analysis for debugging).
- **Error Handling:** Unlike the Standard orchestrator which uses try/catch, in Agent mode the error handling is partly learned behavior (the error analysis agent’s job) and partly built into the agent framework. The coordinator needs to handle cases like an agent failing (exception or no answer) – ADK’s runner should surface errors which we can catch. We will implement timeouts or guardrails for agents (so a stuck agent doesn’t hang the system). If, say, the generation agent times out or produces invalid code, the coordinator can either retry that agent or abort with an error message. These control paths will be part of the AgentCoordinator’s logic or the loop conditions (e.g., if repeated failures of a certain type occur, break out).
- **Summary:** The Agent orchestrator delegates specialized tasks to autonomous agents under a coordinating strategy. This mode should produce the same outcomes as Standard mode, but with more flexibility. It leverages the *Coordinator/Dispatcher pattern* (central agent routing tasks to sub-agents) ([Multi-agent systems - Agent Development Kit](https://google.github.io/adk-docs/agents/multi-agents/#:~:text=Coordinator%2FDispatcher%20Pattern%C2%B6)) combined with *Sequential/Loop patterns* for workflow control. The core domain knowledge (how to generate a test, how to interpret errors) remains centralized, but execution is distributed among agents.

By separating responsibilities in this way, we ensure both orchestrators cover all necessary steps to generate and verify tests. The Standard orchestrator is straightforward and uses static logic, whereas the Agent orchestrator introduces an intelligent, modular approach where each agent focuses on a sub-problem. Crucially, **both orchestrators rely on the same domain operations** – for example, whether the ErrorAnalysis is done via an LLM agent or a direct function, the *ErrorAnalysis* domain model and any logic to parse stack traces is shared. This fulfills the requirement of maximizing shared core logic while just changing the orchestration mechanism.

## Proposed Updates to Domain Models and Ports

To accommodate the new Agent Mode (and to streamline both modes), we propose a few **refinements to domain models and ports**. These changes ensure that the domain layer can represent all information needed for agent-driven workflows (which may produce richer data, or require more granular control) without sacrificing the integrity of the clean architecture. Our focus is to keep domain models flexible and comprehensive so that orchestrators (either mode) can do their job effectively.

**1. Domain Models Enhancements:**

- **TestSpecification & Context Models:** Ensure we have a clear domain model for the input specification of what to generate tests for. If not already present, define a `TestSpecification` (or similar) containing details like target class name, class source code or reflection info, methods to focus on, etc. This model is used by both modes to inform test generation. In agent mode, this spec might be serialized or provided to the TestGeneration agent’s prompt.
- **GeneratedTestSuite Model:** Represent the suite of tests generated, possibly including metadata like which methods of the target class are covered, how many tests, etc. In standard mode this might be just a string of code or an AST. We might refine it to a structured form (e.g., a list of `TestCase` objects with their content). This helps if agents need to modify individual tests – they could target a specific `TestCase` object. Both modes will use this model to pass the current state of tests between generation and execution.
- **ErrorAnalysis Model:** This is explicitly mentioned for expansion. Currently, it might hold basic info like an error message or a suggestion. We plan to extend it to better support agent-driven troubleshooting:
  - Include a **classification of error type** (e.g., CompilationError, TestFailure, RuntimeException, AssertionError, etc.).
  - Store the **raw output or stack trace** of failures for reference.
  - Provide fields for **root cause hypothesis** and **recommended action**. For instance, an ErrorAnalysis instance might say: *type=AssertionFailure, cause="expected value mismatch", recommendation="update expected value to actual output 42 in testMethod1".* In standard mode, this can be filled by parsing error text or by an LLM’s response. In agent mode, the ErrorAnalysis agent would explicitly produce these details (which we convert into the model).
  - Possibly hold a list of **failing test cases** with identifiers, so we know exactly which tests failed (useful for targeted fixes by agents).
  This richer model allows the orchestrators to make decisions (the standard orchestrator can switch on error type to decide a fix strategy; the agent coordinator can pass the structured info to the Healing agent).
- **TestResult Model:** Ensure the output of the test run is captured in a structured domain model. This likely includes:
  - A boolean allPassed flag.
  - A list of failures (with test name, error type, message).
  - Maybe code coverage info or other metrics (if needed later).
  This model is used in both modes – in standard mode, the TestRunner port produces it for loop logic; in agent mode, the run_tests tool can produce the same for agents to analyze.
- **Patch or Fix Model:** If our healing process involves making modifications (to either test code or production code), we might introduce a domain model to represent a *code patch*. For example, a `CodeModification` model that has a target (which file or test), a diff or description of change, and possibly an applied/not applied state. In standard mode, this might not have been explicit (the orchestrator might have just applied changes directly). But for agent mode, an agent might propose a fix in text form (like “change assertion on line 30 to assertEquals(42, result)”). Capturing that in a model ensures we can consistently apply it via a port (e.g., a Code Editor port that takes a CodeModification and applies it to the codebase). This also helps if we want to log or review what changes were made by the AI.

**2. Domain Services/Logic Adjustments:**

- **ErrorAnalysis Service:** We might formalize an `ErrorAnalysisService` in the domain that can produce an ErrorAnalysis given a TestResult. In standard mode, one implementation might call OpenAI to interpret the failure (if it’s complex), or do simple rule-based parsing for known patterns. In agent mode, we might not use this service directly, since the ErrorAnalysis agent is effectively doing the job. However, having this service means we could still fall back to direct analysis if needed, or even use it to double-check the agent’s analysis. We can also reuse any parsing logic (e.g., regex to find exception type) in both modes. We could allow the agent to output raw text which we then feed into this service to structure it, but ideally the agent would output structured data.
- **TestGeneration Service:** Similarly, encapsulate any domain-specific prompting or post-processing of generated tests in a service. For instance, formatting the code, ensuring the test methods have @Test annotations, etc. In standard mode, this wraps the LLM call and then possibly does some cleanup. In agent mode, the generation agent might handle a lot itself, but we can still reuse utility methods for validating or adjusting the output. We could expose a method like `TestGenerationService.postProcess(rawTestCode)` to normalize formatting or add any boilerplate, and use that in both modes.
- **Self-Healing Logic:** If there are any algorithms or heuristics for fixing tests without AI (e.g., if an assertion fails and actual value is numeric, just substitute it), those belong in domain services as well. That way, even the agent mode could call these as tools. For example, we could have a simple rule: “if a test assertion expected X but got Y, change expected to Y.” The Healing agent might come up with the same, but having it in code means we could potentially offer it as a non-LLM tool for the agent (ADK tool). However, since the question focuses on using agents for healing, we will primarily rely on LLM reasoning, but it’s good to keep domain heuristics for trivial fixes.

**3. Ports (Interfaces) Refinements:**

- **LLM Port:** There is likely an existing port interface for calling the language model (e.g. `LLMService` with methods like `generateTests(prompt)` or `analyzeError(prompt)`). We should ensure this port can be used by Standard mode as before. In Agent mode, the ADK will handle LLM calls internally via its agent definitions (likely using its own integration to models). However, we might still use the LLM port in agent mode indirectly:
  - We could configure ADK’s model access to go through our LLM service (if ADK allows custom model providers) – though ADK typically can directly call the model with an API key. It might be simpler to let ADK call the model directly since it’s designed for that, and just ensure the same API keys and settings are applied. No major changes needed to the LLM port except possibly allowing it to be bypassed by ADK in agent mode.
  - If the Standard mode had multiple LLM providers or strategies, ensure those can still be configured (maybe via `application.yml`) and that ADK is set to use the desired provider (ADK supports multiple providers via LiteLlm integration ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=different%20agents%20handle%20specific%20tasks%2C,use%20other%20agents%20as%20tools))).
- **TestRunner Port:** Confirm this interface returns a structured TestResult as described. We might expand it to also accept or return additional info needed by agents (for example, perhaps a flag to run in a sandbox or to collect coverage). Likely no major change; just ensure it can be invoked as a tool easily (taking the GeneratedTestSuite or the file path as input).
- **CodeEditor/Repository Port:** If the system writes tests to files or modifies code, abstract that behind a port. For example, `CodeRepositoryPort` with methods to read/write code files, so that in Standard mode we write tests out, and in Agent mode, we might not write to disk until the end (keeping tests in memory). The Healing agent’s suggestions will be applied via this port (could be as simple as string replacement in memory or as complex as AST manipulation).
- **Configuration Port:** If any configuration is accessed in the domain (hopefully not; usually config is handled in outer layers), ensure that agent-specific config (like agent timeouts or model parameters) is not leaking into domain. The application layer should translate config into appropriate settings when constructing agents or orchestrators.

By making these model and port adjustments, we ensure the domain layer can fully support the agent workflow:
- The domain models will carry all the info the agents produce/need, avoiding loss of information (for instance, an agent might output a detailed diagnosis – our ErrorAnalysis can hold it).
- The domain services/utilities provide consistency (ensuring, say, test code formatting is uniform whether an agent wrote it or a direct call did).
- The ports remain the single points for any external effect (ensuring even the agent mode interacts with external world via well-defined interfaces, except for the LLM which is inherently part of the agent itself).

These changes are designed to be **minimal but sufficient**. They do not drastically alter the existing architecture; rather, they extend the domain to be richer and more flexible. We will implement these refinements in a backward-compatible way so that the Standard mode continues to work with perhaps just some extra fields being set (e.g., Standard mode might not use all new fields in ErrorAnalysis, but they’ll be there for Agent mode).

## CLI Behavior (including mode selection)

We will enhance the Command Line Interface to allow explicit selection of Standard vs Agent mode, while maintaining a user-friendly experience. The CLI is the entry point (likely a `main` method or a Spring Boot command runner) that parses user input and triggers the test generation process. Key changes and behaviors:

- **`--mode` Flag:** Introduce a new CLI option `--mode` (or `-m`) that accepts two values: `"standard"` or `"agent"`. The user can choose the mode when running the tool. For example:
  ```bash
  java -jar junit-writer.jar --target-class=com.example.MyClass --mode=agent
  ```
  If `--mode` is not provided, the default behavior will be to run in Standard mode for now (to preserve backward compatibility). We will also implement an **auto-detection** or default from configuration: e.g., if the config file has `mode: agent` as a default, we use that when no flag is given. But an explicit flag always takes precedence.
- **CLI Help/Usage:** Update the CLI help text to describe the `--mode` option and the available values. Make it clear what each mode means (perhaps something like: *standard = sequential generation, agent = ADK multi-agent generation*). Users should understand the difference.
- **Mode Handling in Code:** In the CLI bootstrap code, after parsing arguments:
  - Determine the mode (default to "standard" if not specified or if invalid value given, perhaps print a warning and default).
  - Instantiate or retrieve the appropriate orchestrator. This could be done via a simple if/else:
    ```java
    if(mode.equals("agent")) {
        orchestrator = new AgentCoordinator(...);
    } else {
        orchestrator = new TestGenerationOrchestrator(...);
    }
    orchestrator.execute(spec);
    ```
    Alternatively, use a factory pattern: e.g. `OrchestratorFactory.create(mode)` returns an implementation of a common interface. This abstracts the creation logic. For example, the factory might read some config (like to configure the AgentCoordinator with certain agent parameters).
  - Pass any necessary dependencies to the orchestrator. For instance, the Standard orchestrator might need an instance of LLMService, TestRunner, etc (these could be injected via a DI container or built manually from config). The AgentCoordinator might need a reference to the ADK environment or to the same services for tools.
- **Configuration-based Mode Selection:** As a nice-to-have, implement logic to pick mode based on config if the user doesn’t supply `--mode`. For example, in `application.yml`:
  ```yaml
  orchestrator:
    defaultMode: agent   # could be "standard" or "agent"
  ```
  The CLI loader can check this defaultMode. If set to "agent", and the user didn’t override, it will choose agent mode. If not set, default is "standard". This allows setting a global default (e.g., eventually if agent mode becomes very stable, the config default could be flipped to agent).
- **Mutual Exclusivity and Validation:** Ensure that the CLI prevents contradictory options. For example, if in the future there are other mode-like flags, handle conflicts. Currently, just ensure `--mode` only accepts the two values, and give a clear error if an unsupported value is passed.
- **CLI Output Differences:** The CLI in both modes should output key information to the user, but we might tailor it slightly:
  - In Standard mode, it might print step-by-step logs (e.g. "Generating tests...", "Running tests...", "Test failed, analyzing error...").
  - In Agent mode, since the agents might have more verbose interaction, we could either print a high-level summary of what the agents are doing or allow a verbose flag to stream agent reasoning. For initial implementation, we might keep output similar (e.g. "Agent coordinator: generated initial tests, running tests... error found, agent is fixing..."). We should be careful not to overwhelm the user with internal agent prompts unless in a debug mode.
  - If the user is interested, we could allow an environment variable or log file to capture the agent dialogues for troubleshooting.
- **Fallback Behavior:** If the user selects agent mode but the system is not properly configured for it (for instance, ADK not initialized or missing API keys for the model), the tool should handle this gracefully. Ideally, we detect such an issue at startup – e.g., if `--mode=agent` but Google ADK isn’t available or model credentials missing, we should inform the user and either abort with an error or fallback to standard mode with a warning. Because agent mode is a new feature, a clear message like "Agent mode is not available: [reason]. Falling back to standard mode." would be helpful. This makes the CLI robust.
- **Consistent Invocation Interface:** Regardless of mode, the CLI likely calls something like `orchestrator.run(spec)` and waits for result. We want the user experience to be uniform: at the end, they get either a success message ("Tests generated and saved to ...") or a failure summary. Internally, the orchestrators produce those results possibly in different ways, but from CLI perspective it's one interface. If we implement a `TestGenerationUseCase` interface that both orchestrators adhere to, the CLI can treat them polymorphically.
- **Integration with Config (application.yml):** The CLI should load configuration (e.g., for LLM API keys, agent settings) before initializing the orchestrator. We should ensure that if config defines some mode-specific settings, those are passed correctly. For example, `application.yml` might have an `agent:` section for agent-specific tuning (see Configuration section). The CLI or OrchestratorFactory will read that if mode is agent and configure the AgentCoordinator accordingly.

In summary, the CLI will explicitly expose mode selection to the user, giving them control. It will default safely and validate input. The actual branching to different orchestrations is encapsulated right after argument parsing. From that point on, each orchestrator runs its course. This explicit mode flag meets the requirement and also makes it easier to experiment and compare the two modes. Users can easily toggle to agent mode via CLI to try the new capability, and revert to standard mode if needed, all via a simple command-line option.

## Self-Healing Strategy in Both Modes

Self-healing refers to the system’s ability to automatically fix or regenerate tests (or code) when the initial output does not pass. Both Standard and Agent modes implement self-healing, but the mechanism and flexibility differ. We will ensure both modes use a consistent *strategy* for self-healing: detect the failure, identify the cause, apply a fix, and retry – until success or a limit. However, the *implementation* of this strategy differs between the modes:

**Standard Mode Self-Healing:**

- **Looping Strategy:** In standard mode, the self-healing is realized with an explicit loop in code (as described in the Standard Orchestrator section). After running tests and getting a TestResult, the orchestrator checks if any failures exist. If yes, it enters a “healing iteration.”
- **Error Analysis:** The orchestrator calls a component (possibly an `ErrorAnalyzer` service or directly an LLM via a port) to analyze why the test failed. For instance, it may prompt an LLM with: *"The following test failed with this error... How can we fix the test or code?"* The result of this analysis is structured into the ErrorAnalysis model (with cause and suggested fix).
- **Decision on Fix Type:** Based on the analysis, the orchestrator decides whether to adjust the test or the code under test:
  - If the analysis indicates the test made a wrong assumption (e.g., expected output incorrect, or missing handling of an exception), the fix is to change the test. The orchestrator might call back into the LLM with a refined prompt, like *"Modify the test to account for X (as per analysis)"*, or apply a known pattern (e.g., update expected value).
  - If the analysis suggests the code under test has a bug (less common if the code is assumed correct, but possible), the orchestrator could either report that or attempt to generate a patch for the code. This depends on project scope; assuming we focus on test generation, we likely stick to fixing tests, not production code, unless explicitly intended.
- **Applying the Fix:** The orchestrator uses either automated rules or LLM guidance to modify the tests:
  - It could regenerate the entire test suite with additional instructions (e.g., *"Regenerate tests for X, but make sure to handle the null case that caused failure."*). This sometimes is easier than patching the code.
  - Or it could patch just the failing test. For example, if one assertion is wrong, it can adjust that assertion. Perhaps it calls an LLM function `LLMService.fixTest(failingTest, analysis)` which returns a corrected code snippet for that test.
  - The domain model (GeneratedTestSuite) is updated accordingly (either replaced or partially modified).
- **Re-run Tests:** After applying the fix, the orchestrator compiles and runs the tests again via the TestRunner port. It then again checks results.
- **Repeat or Terminate:** It will repeat this cycle until tests pass or we hit a maximum number of iterations (which might be configured, say 3 attempts or 5 attempts). If maximum is reached, the process stops to avoid infinite loops, and reports that self-healing was unable to resolve all issues.
- **Example:** Suppose the generated test expected a method to return 5 but it actually returns 4, causing an assertion failure. The Standard orchestrator sees the failure, asks the LLM, which responds "The expected value is off by 1; adjust the expected to 4." The orchestrator then modifies the test code to expect 4 instead of 5, re-runs, and if now all tests pass, finishes. If something else fails, it continues.

- **Limitations:** The Standard mode healing is only as good as the rules or LLM prompts we pre-defined. If a failure is complex or the fix isn’t obvious, multiple iterations might occur. The orchestrator might have to prompt iteratively with more context. There is less flexibility to try different strategies beyond what we code. However, this deterministic loop ensures a controlled, predictable process.

**Agent Mode Self-Healing:**

- **Agent-Driven Iteration:** In Agent mode, self-healing is handled by the interplay of agents, potentially using ADK’s LoopAgent to automatically repeat until success ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=The%20,until%20a%20condition%20is%20met)). The general strategy – analyze error and fix – is the same, but the agent system can be more **adaptive and concurrent** in finding a solution.
- **Coordinator Oversight:** The coordinator agent (or the static workflow defined in AgentCoordinator) will detect that the tests did not pass and trigger the healing sequence. Because we can define a LoopAgent with a condition “while tests not passed, iterate,” the agent system inherently knows to continue iterating until done (or until a set max). The condition can be checked either by an automated flag from the test run tool (allPassed boolean) or by an agent that evaluates the TestResult.
- **Error Analysis Agent:** The error analysis agent in this mode takes the TestResult (failures) as input and produces a detailed analysis (just like the LLM in standard mode, but now possibly more sophisticated since it’s an agent prompt specifically tuned for this). Because this agent is an LLM, it can incorporate reasoning or even ask for more info if needed (though likely all info is provided). The output populates the ErrorAnalysis model – and since this agent is part of the multi-agent system, the information is now available in the shared state for others.
- **Healing Agent Actions:** Once the error is analyzed, the coordinator or workflow triggers the Healing (Test Fixer) agent. This agent uses the analysis to propose a change. One advantage in agent mode is that the Healing agent could potentially come up with *multiple approaches* or update its approach if the first fix doesn’t work. For instance, it might recall previous attempts from the shared state and try a different angle if the last fix failed. This kind of adaptive behavior could be achieved if we allow the agent to see history or if the coordinator prompts it with *"The last fix didn't solve it, try something else."*
- **Parallel Healing (optional):** Agent mode could even attempt multiple fixes in parallel if one failure could be solved in different ways – although we must apply them one at a time to test. Alternatively, if multiple tests failed for different reasons, the agent system might handle each in parallel:
  - e.g., If test A and test B both failed, we could spawn two healing agents concurrently to fix each (this would leverage ADK’s parallel execution to speed up addressing multiple failures). Then integrate both fixes and rerun. This parallel failure resolution is something the Standard loop wouldn’t do (it would likely fix one by one or together but sequentially).
- **Human-like Problem Solving:** Because agents have the full power of LLM reasoning, they might do more complex self-healing strategies. For instance, an agent could decide to write an entirely new test if the current one is fundamentally wrong, or even decide to adjust the target code (if we allow it). The coordinator could negotiate between agents – e.g., an agent might say "This failure indicates a bug in the code under test," and perhaps the system could then either log that or involve a different agent or output a message.
- **Termination:** The loop will terminate when the Test Execution tool returns all tests passed. The coordinator can then conclude and output the result. We will set a maximum iterations to avoid endless loops on unsolvable problems (configurable, say 5 or 10). Because the agent mode is more dynamic, it's possible it might find a solution in fewer iterations or require more creative attempts, but a safety cutoff is still needed.
- **Comparison to Standard:** Both modes fundamentally do similar retries, but the **agent mode may achieve better fixes** due to the flexibility of the LLM agents. For example, if a test is failing due to a tricky logic, the agent might decide to test a different aspect or change the approach of the test in a way a hardcoded loop wouldn’t. Agents can incorporate context and reasoning across iterations (the coordinator can remember what was tried before via state). Standard mode, unless we code it, wouldn’t “remember” past attempts beyond perhaps not repeating the same prompt.
- **Use of Domain Knowledge:** We will still use the domain’s knowledge in self-healing: e.g., if the ErrorAnalysis model’s classification is available, the agent can use that. The healing agent could call into domain utilities if needed (or we expose those as ADK tools). For instance, if a trivial fix is obvious, the agent could invoke a tool that applies it directly, rather than reasoning from scratch. This blend ensures that agent mode doesn’t always reinvent the wheel for simple fixes.
- **Logging and Visibility:** Self-healing in agent mode might be less transparent from the outside (since the conversation is internal). We will consider logging each iteration’s outcome for the user or developer to see: e.g., "Iteration 2: 1 test still failing, agent suggests changing expected output to 42." This is useful for trust and debugging.

In both modes, the self-healing strategy adheres to the same principle: *automatically converge on a working test suite.* The differences lie in how the decisions are made (coded logic vs AI reasoning) and the potential thoroughness of the search for a solution. We expect the agent mode to handle more complex scenarios (thanks to multi-step reasoning) and possibly reduce manual intervention, whereas standard mode provides a reliable, if somewhat rigid, procedure. We will implement self-healing in agent mode to be as deterministic as possible (using LoopAgent for structure) to avoid chaotic behavior, essentially mirroring the standard mode’s loop but with intelligent decision-making at each step.

Finally, it's important that if self-healing cannot fix the issues (in either mode), the system clearly reports what went wrong. For example, if after X tries the tests still fail, output the remaining failing tests and the last known analysis. This way a developer can take over if needed. This failure-handling is part of the orchestrators’ responsibility – e.g., after the loop, if not all tests passed, print a message like "Could not produce a passing test suite after 5 attempts. Last error: ...".

## Parallelization Strategy in Agent Mode

One of the advantages of the Agent Mode is the ability to perform certain tasks in **parallel**, leveraging ADK’s support for concurrent agent execution ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=)). In Standard Mode, the process is inherently sequential (each step happens one after the other). In Agent Mode, we can identify independent tasks and run them concurrently to improve efficiency and possibly achieve better results through diversity. Our parallelization strategy will focus on areas that benefit from parallel execution without violating the logical dependencies of the workflow.

**Opportunities for Parallelization:**

1. **Generating Tests for Multiple Targets:** If the tool is asked to generate tests for multiple classes or modules in one run (for example, user wants tests for Class A, B, and C in one invocation), the agent coordinator can spawn separate generation agents for each class in parallel. Using ADK’s `ParallelAgent`, we can fan-out these generation tasks ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=data_gatherer%20%3D%20ParallelAgent%28%20name%3D)). Each sub-agent works on a different target independently, calling the LLM. This would significantly cut down the overall time (nearly parallelizing what would have been sequential in standard mode). After generation, the coordinator can sequentially or concurrently run tests for each; if one fails, only that one enters a healing loop, while others might proceed. This granular parallelism means the slowest target dictates the total time, but we don’t waste time doing them one by one.

2. **Parallel Test Case Generation:** Even for a single target class, we could attempt to generate tests in parallel. For instance, two generation agents could be given slightly different prompts or focus (one generates normal cases, another generates edge cases) simultaneously, or split by method (one agent writes tests for method1, another for method2). Afterward, their outputs combine into one suite. This approach could produce a richer test suite faster. However, it requires careful merging and might produce overlapping or redundant tests. We might hold this idea for a future enhancement once basic agent mode is stable. It’s conceptually feasible with ADK.

3. **Parallel Error Analysis and Fixes:** If multiple tests fail, or multiple issues are identified, agents could address them in parallel:
   - Suppose after running tests, we have 3 failing tests, each possibly for different reasons. In standard mode, we’d typically handle them one by one or together in one LLM prompt. In agent mode, we could instantiate an ErrorAnalysis agent for each failing test concurrently to diagnose each issue. ADK can run these as sub-agents in parallel to gather all failure diagnoses at once. Once we have all analyses, we could either feed them to a single Healing agent or even have multiple Healing agents each fix a specific test. The fixes would need to be merged if they touch different tests (which is manageable if separate).
   - The benefit is time saved when dealing with multiple failures and the ability for each agent to focus deeply on one problem. After parallel fixes, we would rerun the tests. This is essentially a *Parallel -> Gather* pattern (analyze all, fix all, then verify) as opposed to iterative one-by-one fixing. 
   - We must ensure the fixes don’t conflict. If two failing tests actually stem from the same root cause in code, two separate fixes might both try to change the code. To mitigate conflict, the coordinator agent could recognize a common cause and perhaps choose a single fix. Or, simpler: handle one at a time if dependencies are detected. Parallel fixing is most useful when issues are independent.
   - ADK’s parallel execution is well-suited for *independent tasks that do not share state* ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=Parallel%20execution%20is%20particularly%20useful,for)). We will carefully partition tasks to fit that criterion.

4. **Diverse Solution Attempts:** Another form of parallelization is not about independent input tasks, but multiple attempts for the same task. For example, if a test is failing, we could have two Healing agents propose two different fixes simultaneously, then either pick the best or try each. This is speculative parallelism. We could run both fixes by branching the state (one agent edits the test one way, another a different way) and then run both versions of tests (one after the other or if we had resources even in parallel processes) to see which fix actually passes. This ensures we explore more solutions within the same iteration. However, this increases complexity. A simpler approach is sequential (try one fix, if it fails, try another). We might not implement this initially, but the architecture can support it if we, say, clone the state and use a ParallelAgent with two subflows each with a different fix approach, then a join to check results. We mention it as a possibility for the future once basic agent mode works.

**Using ADK Workflow Agents for Parallelism:**

ADK provides the `ParallelAgent` construct to run sub-agents concurrently and wait for all to complete ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=)). We will utilize this in our AgentCoordinator setup:
- For multi-class generation, wrap multiple TestGenerationAgents inside a ParallelAgent.
- For multi-failure analysis, wrap multiple ErrorAnalysisAgents inside a ParallelAgent.
- The coordinator (or the parent workflow) then collects outputs. ADK will handle synchronization (it effectively awaits all parallel tasks).
- The benefit, as noted in ADK documentation, is reduced total processing time when tasks are independent ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=Parallel%20execution%20is%20particularly%20useful,for)). In our context, generating or analyzing different things are independent and thus perfect for parallel execution.

**Concurrency Considerations:**
- The parallel agents will each call the LLM (assuming each uses an LLM) potentially at the same time. This means higher load and possibly hitting rate limits or concurrency limits of the API. We should ensure our LLM provider can handle it or throttle appropriately. Config could allow limiting the number of concurrent agents if needed.
- Running tests concurrently (if we ever consider that) would need separate JVM processes or threads for isolation, since running two sets of tests in one JVM simultaneously could conflict. It’s simpler to run tests sequentially after parallel generation, rather than truly concurrently running JUnit for two suites. So parallelism is more for generation and analysis steps.
- Shared state: ADK’s state management means if agents need to write to shared memory (like the same GeneratedTestSuite), we must be careful. In parallel generation for separate classes, they have separate state sections, no conflict. In parallel analysis of separate failures, each can write to separate parts of state (e.g., keyed by test name). The coordinator or a subsequent step merges them into one ErrorAnalysis aggregate if needed.
- **Parallel vs Sequential trade-off:** While parallelism can speed things up, it can also make debugging harder (more things happening at once) and uses more resources. We will enable parallel flows where it clearly benefits and is safe. In initial implementation, we might keep things sequential except for obvious cases like multi-class input. Over time, we can introduce more parallel steps once proven.

**Configuration for Parallelism:** We will add config options (in application.yml) to control parallelism:
  - e.g., `agent.parallelEnabled: true/false` to easily switch off parallel features if needed.
  - Possibly `agent.maxParallelAgents: N` to limit concurrency (to avoid overloading the system or API).
  - The coordinator can read these and decide to use parallel or just sequential loops.
  
**Example Scenario:**
- User requests tests for 2 classes (`A` and `B`) in agent mode. The AgentCoordinator uses:
  - A ParallelAgent to invoke two TestGenerationAgents at once (one for A, one for B).
  - Waits, gets two test suites. Then sequentially goes through each for self-healing (or could even run both test suites in parallel if isolated).
  - This yields both sets of tests roughly in the time of one LLM call (plus overhead) instead of two sequential calls.
- If class A’s tests fail and B’s pass, the coordinator can focus healing agents on A while perhaps already delivering B’s tests.
- This parallel approach dramatically reduces idle time waiting for LLM or I/O.

In summary, **Agent Mode will exploit parallelism for independent tasks** to improve performance and thoroughness. By using ADK’s parallel orchestration capabilities, we can *reduce total processing time for independent tasks by executing them concurrently* ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=Parallel%20execution%20is%20particularly%20useful,for)). The system will be designed to identify when tasks are independent (different classes, different failing tests, etc.) and run them in parallel, while tasks that depend on each other (you must generate tests before running them, or you need analysis before a fix) remain sequential. This hybrid approach keeps the workflow logically correct but more efficient than a purely linear process.

## Configuration Changes (`application.yml`)

To support the dual-mode operation and new agent functionality, we will introduce updates to the configuration (assuming a YAML config like `application.yml` or similar is used). The configuration will provide default settings for mode, as well as various parameters for the agent system and possibly LLM usage. Keeping configuration external allows tuning without code changes and enables auto-detection logic for modes.

**Proposed Configuration Sections:**

1. **Mode Selection:**
   ```yaml
   orchestrator:
     defaultMode: standard   # "standard" or "agent"; used if CLI --mode not specified
   ```
   This top-level `orchestrator.defaultMode` key sets the default mode. As noted, if user supplies `--mode`, that overrides this. If not, the application reads this value. By default, we might set it to "standard" initially. A user or deployer can change it to "agent" if they want agent mode by default for their use-case. This provides the *auto-detection from config* mentioned – e.g., if someone always wants agent mode, they set this once.

2. **Agent Settings:**
   We add an `agent:` section to house ADK/agent-specific settings:
   ```yaml
   agent:
     enabled: true                # Master switch if we want to quickly disable agent features
     maxIterations: 5             # Max self-healing iterations in Agent mode (loop limit)
     parallelEnabled: true        # Whether to use parallel flows when possible
     maxParallelAgents: 3         # Limit on concurrent agents to avoid overload
     model:
       provider: "openai"         # e.g., which LLM provider to use within ADK (openai, google, etc.)
       modelName: "gpt-4"         # default model name for LLM agents (if using openai)
       apiKey: "${OPENAI_API_KEY}"# reference to environment or secret, if needed
     logging:
       level: "INFO"
       traceInteractions: false   # if true, log detailed agent messages
   ```
   - `enabled`: could be used by the application to completely disallow agent mode if set to false (the CLI could throw an error or ignore `--mode=agent` if this is false). This might be useful if the environment cannot support ADK or for safe-mode.
   - `maxIterations`: The number of times the LoopAgent or coordinator will attempt fixes. This can be tweaked; perhaps in simpler projects 3 is enough, in complex ones maybe 5-7. We expose it so users can adjust based on how long they are willing to let the AI iterate.
   - `parallelEnabled` and `maxParallelAgents`: control parallelism as discussed. If `parallelEnabled` is false, the AgentCoordinator will refrain from using ParallelAgents and instead do things sequentially (even if conceptually could be parallel). `maxParallelAgents` can ensure we don't spawn too many simultaneous tasks (like if dozens of classes need tests, maybe we batch or limit at a time).
   - `model` sub-section: Configures the LLM usage in agent mode:
     - `provider`: Could be "openai", "anthropic", "google" etc., depending on what's supported. ADK via LiteLLM can integrate with various providers ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=different%20agents%20handle%20specific%20tasks%2C,use%20other%20agents%20as%20tools)). We should allow specifying which to use. This might default to whatever is already used in standard mode (if we had openai there, use openai here).
     - `modelName`: the specific model (GPT-4, Claude-v1, etc.). Possibly multiple models for different agents could be configured, but that might be overkill now. We could allow advanced config like `agents:` listing each agent's model, but initially one model for all LLM agents is fine.
     - `apiKey`: We might store the API key or reference in config. Storing plain API keys in YAML is not ideal; better to reference an environment variable or use a secret management. The snippet above suggests using an env var. ADK will need the key to call the model. We have to ensure ADK is configured to pick this up (likely via its environment or a call in code to set up credentials).
   - `logging` for agent: We might want verbose logging for agent internals only when needed. `traceInteractions: true` could mean we log all prompts and responses of agents to the console or a file. Normally false to avoid cluttering output.
   - There could be other ADK tunables we include (like timeouts for agent responses, max tokens, etc.), but those can be added as needed.

3. **Standard Mode Settings (if any):**
   For parity, we might have:
   ```yaml
   standard:
     maxIterations: 3   # separate setting for standard mode loop attempts, if we want it configurable
   ```
   This allows tweaking the self-healing attempts in standard mode as well. It could default differently from agent mode if desired. If not specified, we can reuse `agent.maxIterations` for both, or just hardcode in standard orchestrator.

4. **Shared Settings:**
   - **LLM Settings**: If the standard mode also uses an LLM (likely it does for generation and maybe analysis), we probably already have config for that (like `openai.apiKey`, etc.). We should ensure that there’s alignment between those settings and the agent’s model settings. Possibly unify them:
     ```yaml
     llm:
       provider: openai
       model: gpt-4
       apiKey: ...
     ```
     And both standard and agent use this unless overridden. Alternatively, keep them separate if we might use different models for standard vs agent (not likely beneficial; probably unify).
   - **Output Paths**: Possibly config where to save generated tests, etc., but that’s outside our focus here.

5. **ADK Specific Config**:
   If ADK requires any initialization config (like enabling the web UI or such), we might include it. But ADK seems to primarily be a library we use programmatically. If needed, we might specify something like:
   ```yaml
   adk:
     someSetting: value
   ```
   But likely not needed unless ADK needs to know, say, where to store sessions (by default in-memory is fine for our use-case).

**Configuration Loading and Use:**
- We will load these config values at startup (e.g., via Spring Boot config binding or a manual YAML parser).
- The CLI or OrchestratorFactory will read `orchestrator.defaultMode` to decide mode if no CLI flag.
- When constructing the AgentCoordinator, we will pass in the relevant config:
  - e.g., `maxIterations` for loop, `parallelEnabled` flags, and model configuration to initialize ADK agents.
  - The ADK model provider may require environment variables; if using Google’s ADK with OpenAI, ADK might read OPENAI_API_KEY from environment. We must ensure our application sets that (via config or explicitly in code) before running agents.
  - Logging settings might be applied to configure log levels or our own logging of agent steps.
- For standard orchestrator, use `standard.maxIterations` if provided for its loop count.
- The rest of the application (domain, ports) can also use config if needed. For example, the LLMService might pick up `llm.model` and `llm.apiKey` to call the appropriate model.

**Backward Compatibility and Defaults:**
- If the config file is not updated, the application should assume reasonable defaults (Standard mode, a default model like GPT-4 if none specified, etc.) so that existing usage doesn’t break.
- Document these new config options in the project README or docs so users can configure as needed.

By centralizing these settings in `application.yml`, we allow flexibility and adherence to the clean architecture (since no magic constants are hardcoded in orchestrators). It also simplifies mode toggling – e.g., one could flip a config switch to change default behavior in a CI pipeline or so. And importantly, the `--mode` CLI flag gives immediate control, while the config provides a persistent default and advanced tuning especially for Agent mode which might require more parameters (model, parallelism, etc.).

## Implementation Plan (Phase by Phase)

Implementing this dual-mode support will be done in a series of phases to incrementally add functionality and ensure stability at each step. The phases are designed so that at the end of each, we have a working system (even if not with full agent capabilities initially). This allows testing and feedback throughout the process. Below is a step-by-step plan:

1. **Phase 1: Refactor and Prepare Orchestration Layer**  
   *Goal:* Lay the groundwork by separating orchestration logic from core logic and defining the structure for multiple modes.  
   **Tasks:**  
   - Abstract the orchestration into a common interface or base class. For example, define an interface `TestGenerationUseCase` with a method like `generateTests(TestSpecification spec)`. The existing `TestGenerationOrchestrator` will implement this interface.  
   - Ensure the existing orchestrator (standard mode) is using domain services/ports properly (no hardcoded API calls that violate hex architecture). Refactor if needed: e.g., if it was directly calling an OpenAI API, route that through an LLMService port implementation. This ensures the logic is testable and swappable.  
   - No functional changes yet, just cleanup: ensure domain models like ErrorAnalysis, TestResult are being used (introduce them if the logic was inlined) so that later we can expand them.  
   - Introduce a placeholder for AgentCoordinator (implement the same interface but maybe throw UnsupportedOperation or log “not implemented” for now). This allows the project to compile with both classes present.  
   - Update the project structure if needed, e.g., create an `application` package for orchestrators if not already, to clearly separate from domain.  
   - Write unit tests for the standard orchestrator (if not existing) to lock in current behavior as baseline.

2. **Phase 2: Domain Model and Port Enhancements**  
   *Goal:* Extend domain models and ports to support the upcoming agent mode features, without changing external behavior yet.  
   **Tasks:**  
   - Expand the **ErrorAnalysis** domain model with fields for error type, details, suggestions as discussed. Adjust any existing code that creates or uses ErrorAnalysis to fill new fields if data is available. If not, ensure they handle null/default for new fields to avoid breaking anything.  
   - Implement a **TestResult** model if not present, or extend it to carry structured failure info (so far maybe just a boolean and a list of strings; make it a list of structured failure objects). Adapt the TestRunner port interface to return this model. Adjust the TestRunner adapter to populate it (parsing JUnit output, etc.).  
   - Create a domain model for **TestSpecification** (if not already) to formalize input. Use it in orchestrator interface and ensure CLI translates user input (class name, etc.) into this spec.  
   - Add a **CodeModification** or similar model if planning to use it, along with a port (e.g., `CodeEditorPort.applyPatch(CodeModification)` stub). Implementation can be simple (like find & replace in file) for now. In standard mode, you might not need it explicitly, but having it ready means the agent mode can use it to apply agent-proposed fixes cleanly.  
   - If not already, introduce **LLMService port** (or ensure it covers both generation and analysis functions, maybe separate methods or one generic method with a prompt type parameter). If using an existing one, verify it’s sufficient (it might just have a `generateTests` now; consider adding `analyzeError` method, or we decide to funnel everything through one method with parameters). For now, it can remain as is; agent mode might not call it directly.  
   - Verify all changes with existing test suite (if any) or do some manual runs in standard mode to ensure nothing broke. At end of Phase 2, standard mode should still work exactly as before but the system is equipped with richer models.

3. **Phase 3: Implement Basic AgentCoordinator and Agents (Sequential Flow)**  
   *Goal:* Get a basic agent mode working in a sequential manner (no parallel or loop yet), essentially replicating the standard flow using agents step-by-step.  
   **Tasks:**  
   - Initialize integration with **Google ADK**. Add the ADK library to the project (in build.gradle or pom.xml). Ensure API keys (for the chosen model) are set (e.g., via env vars or config).  
   - Implement the `AgentCoordinator` class (application layer). It should implement the orchestrator interface. In this phase, implement it with a straightforward approach: one pass of generate → run → analyze → fix using agents, without looping. This will allow us to test each agent once in sequence.  
   - Define the **TestGenerationAgent** using ADK:
       - Likely create an instance of `LlmAgent` with a prompt instructing it to generate tests. Provide it necessary context (the class source or signature). Possibly use ADK’s ability to pass tools or context: we might give it a tool to fetch the code if needed, or we can inline the code in prompt. Start simple: include the class/method signature in the prompt.
       - Set the model (from config, e.g. GPT-4). Set any needed parameters (max tokens, etc.).  
   - Define the **Test Execution Tool** in ADK:
       - Implement a function (in Python or Java depending on ADK usage; ADK Python is the main one, but assuming our project is in Java, we need to see how to integrate. Possibly we will call Python ADK through some bridge? Or maybe there's a Java ADK? Actually, Google ADK is Python. If our project is Java, this is tricky. We might have to run a Python environment, or we consider using ADK concepts but reimplementing lightly in Java).
       - If the project is Java, one approach is to run a Python process for ADK agent, but that's complex. Alternatively, maybe treat the LLM calls as a kind of agent in a simpler Java framework. However, since ADK was explicitly mentioned, perhaps the user uses ADK in Python to coordinate and calls back into Java code.
       - For this design, let's assume we can integrate Python ADK by calling a Python script from Java or that the whole orchestrator might actually be written in Python while domain in Java (less likely). If staying in one language, maybe the project is in a polyglot environment or uses Jython or simply orchestrates via subprocess. This detail is beyond design doc scope, but we assume ADK usage is feasible.
       - For now, define conceptually: a tool `run_tests` that executes the tests via the TestRunner port and returns a result (perhaps as JSON string or a summarized text). In ADK, we register this tool for agents that need it (coordinator or a specific agent).
   - Define **ErrorAnalysisAgent** and **HealingAgent** as LLM agents with appropriate instructions. They might use the output from `run_tests` (which could be in the ADK state).
   - Orchestrate them in **Sequential order** within AgentCoordinator:
       - Possibly create a top-level `SequentialAgent` in ADK with sub_agents: [TestGenerationAgent, (FunctionTool run_tests), ErrorAnalysisAgent, HealingAgent]. Have it execute in that order.
       - Run this SequentialAgent once via ADK’s runner. This should perform one cycle.
       - After execution, gather outputs: e.g., TestGenerationAgent’s output (initial tests), and HealingAgent’s output (if any fix suggested). At this phase, we might not loop, so maybe just trust one pass. We’ll improve in next phase.
       - The expectation is that after one sequence, we have either passing tests (if we got lucky) or a single attempt fix done. It’s okay if it’s not perfect yet.
   - Validate the agent workflow on a sample: e.g., a simple class where generation should produce at least one test. See if the TestGenerationAgent output is captured. Possibly manually intervene to run tests if agent didn’t automatically do it.
   - This phase is mainly about getting the ADK integration to function and agents to communicate properly with our system. There will be adjustments (like formatting agent outputs to proper code). At the end of Phase 3, `AgentCoordinator.generateTests` should produce a test or tests and maybe attempt one fix, but it might not loop to perfect them yet.

4. **Phase 4: Implement Loop (Self-Healing) and Enhanced Coordination**  
   *Goal:* Extend AgentCoordinator to handle iterative self-healing until success, matching the standard mode’s capability, and incorporate more autonomy where beneficial.  
   **Tasks:**  
   - Utilize ADK’s **LoopAgent** to repeat the sequence from Phase 3. For example, wrap the SequentialAgent [Generate -> Run -> Analyze -> Fix] inside a LoopAgent. Define the stopping condition:
       - If using an agent to decide, create a simple agent that checks the TestResult in state and returns “continue” or “stop”. Or easier: after each loop iteration in code, check a flag in state (set by run_tests tool or by an agent) that indicates success. ADK may allow a condition function for LoopAgent as well.
       - Implement maxIterations from config to break out if exceeded. ADK’s LoopAgent supports a max_iterations parameter ([The Complete Guide to Google's Agent Development Kit (ADK) - Sid Bharath](https://www.siddharthbharath.com/the-complete-guide-to-googles-agent-development-kit-adk/#:~:text=loop_agent%20%3D%20LoopAgent%28%20name%3D,Optional%20maximum%20iterations)).
   - If not using LoopAgent, alternatively control loop in Java code: after running one sequential flow, if tests not passed, re-run the sequence. But better to use ADK’s built-in to keep it within the agent context (so agents remember previous attempts via state).
   - Ensure that in the loop, the next iteration uses the updated test code from previous fix:
       - That means the TestGenerationAgent in subsequent iterations might actually be a different action – perhaps after the first iteration, we don’t want to *generate from scratch* again, we want to use the fixed tests from last iteration. One approach: in first iteration, we only generate. In subsequent iterations, maybe skip generation and just reuse the last tests applying new fixes. This is tricky with static sequence.
       - Alternatively, treat the HealingAgent’s output as the new test version and feed it into the next run_tests directly on next loop iteration, bypassing generation agent if we maintain state of tests in memory.
       - We may configure the loop such that generation agent is only run on iteration 1, and on further iterations, it’s either no-op or replaced by something else (like a PassThroughAgent that just uses current tests).
       - A simpler design: Always call generation agent, but have it conditioned: e.g., its instruction could be "if tests exist (from previous iteration's state), just return them unchanged or incorporate the last changes." This might complicate the agent prompt. It might be easier to handle in code: after first iteration, swap out the generation agent with a dummy that just provides current tests.
       - We can finesse this by perhaps structuring the loop differently (like outside ADK logic: a loop in code that calls two ADK sequences: one for gen, one for fix...). But let's assume ADK can handle iterative improvement by sharing state.
   - Add concurrency control within ADK if possible: e.g., lock test modifications to one agent at a time in sequence flow, which is by design sequential anyway.
   - **Parallel improvements** (if time in this phase, else next phase):
       - Try using ParallelAgent for any obvious part. For example, if multiple failures, we can parallelize analysis as described. This might require dynamic creation of agents after test run (since we only know number of failures at runtime). That might be advanced; potentially skip now and handle in Phase 5.
   - Test the full loop on scenarios:
       - Simple scenario where first generation is slightly wrong but second iteration fixes it. See that it stops at correct time.
       - Scenario with an irreparable issue to see it stops at max iterations and returns failure gracefully.
       - Compare with standard mode on same input to ensure both produce comparable outputs.
   - At the end of Phase 4, Agent mode should be on par with Standard mode in functionality (perhaps slower or more verbose, but it should at least manage to produce passing tests with iterative fixes). Document any differences noticed (like if agent mode tends to produce different styles of tests).

5. **Phase 5: CLI Integration and Mode Selection**  
   *Goal:* Hook up the CLI to allow switching between orchestrators, and ensure configuration is loaded and honored.  
   **Tasks:**  
   - Implement the CLI `--mode` flag parsing. If using a library like Picocli or JCommander, add the option definition. If a custom parsing, handle it accordingly. Test that the flag is recognized and stored.
   - Implement the logic to choose orchestrator based on mode. Possibly create an `OrchestratorFactory` if not done in Phase 1. This factory will read the config default and CLI input. E.g.:
       ```java
       String mode = cliArgs.mode != null ? cliArgs.mode : config.get("orchestrator.defaultMode");
       if(mode.equalsIgnoreCase("agent")) return new AgentCoordinator(...);
       else return new TestGenerationOrchestrator(...);
       ``` 
   - Ensure the chosen orchestrator is given the necessary dependencies:
       - For `TestGenerationOrchestrator`: LLMService, TestRunner, etc (these could be singleton beans or created from config). If using Spring, autowire them; if not, instantiate with config values (like API keys).
       - For `AgentCoordinator`: It likely needs references to some of the same (TestRunner port, etc., especially to use in tools). Also pass any config like maxIterations, parallelEnabled. It may also need initialization of ADK context. Possibly the coordinator constructor will set up the ADK agents as per config.
   - Load configuration (from `application.yml`). If using Spring Boot, much is done automatically via @ConfigurationProperties. If not, use a YAML parser or simple approach to get needed values.
   - Respect the config values:
       - defaultMode as mentioned.
       - For agent: set the agent’s internal config (like writing `AgentCoordinator.maxIterations = config.agent.maxIterations`). Use these values in the logic implemented in Phase 4 (like the loop or in ADK agent definitions for tokens).
       - For agent model provider: if config says use openai GPT-4, ensure ADK is pointed to that. This might involve calling ADK’s `LiteLlm.set_default(openai, key, model)` or something similar before running agents. Implement that in AgentCoordinator initialization.
       - For parallelEnabled: if false, perhaps AgentCoordinator will not create any ParallelAgents even if code exists for it. It could simply run things sequentially. Add conditions in code for that.
   - Test CLI manually:
       - Run with `--mode=standard` and see that the standard orchestrator is invoked (maybe log which mode started for clarity).
       - Run with `--mode=agent` and see agent orchestrator invoked. Check that if ADK is not configured, it gives a graceful error. Also test without `--mode` but config default set to agent (simulate by editing config) to ensure it picks up default.
       - Ensure help text shows the mode option.
   - At end of Phase 5, the system is fully integrated. Both modes can be triggered from the CLI. Standard mode behavior should be unchanged from before (regression test it on known inputs). Agent mode should now be usable via CLI (though maybe still considered beta, we will refine further).

6. **Phase 6: Parallelization and Optimization in Agent Mode**  
   *Goal:* Enhance the agent mode with parallel execution where beneficial, and tune performance and reliability.  
   **Tasks:**  
   - Implement parallel generation for multiple classes if the use-case exists. This might involve detecting if the TestSpecification contains multiple targets (or if the CLI is invoked on a package, etc.). If so, use a ParallelAgent to create one sub-agent per class. If not needed, skip.
   - Implement parallel error analysis for multiple failures:
       - After a test run, if TestResult shows N failures and config `parallelEnabled` is true, spawn N ErrorAnalysisAgent instances in parallel (perhaps dynamically). ADK might allow creating agents on the fly or we can define a generic one and call it N times with different inputs.
       - This might require writing some code around ADK because ADK’s static graph might not natively support variable number of sub-agents. Alternatively, do parallel outside ADK: e.g., use Java streams or threads to call an LLM for each failure concurrently. But that breaks using ADK's advantages. Possibly use ADK’s ability to run the same agent multiple times with different inputs; need to research if ADK supports map-reduce style.
       - If too complex, we might compromise: feed all errors into one ErrorAnalysisAgent prompt so it analyzes them together (less ideal but simpler). Or just do sequential analysis for now, leaving parallel analysis as an optimization for later.
   - If not already done, consider using ADK’s ParallelAgent for any independent sub-tasks discovered in testing.
   - Optimize agent prompts and logic:
       - Fine-tune the prompts for each agent to improve quality. For example, ensure the generation agent knows to produce code without needing extra clarification, or limit its output length to avoid hitting token limits. Use config for any such parameters (like `maxTestMethods` or similar if we want).
       - Set timeouts for agent responses so that if an agent stalls, we break out. ADK might have a timeout setting or we implement a watchdog in AgentCoordinator.
       - Memory usage: if ADK keeps a lot of state, occasionally clear unneeded state (like after a loop ends, drop info not needed).
   - **Testing & Benchmarking:** 
       - Test agent mode on various cases: small class, larger class, edge case (like method that always throws exception). Ensure it can handle them.
       - Compare execution time of standard vs agent in those cases. Document if agent mode is slower due to overhead. See if parallelism improved any scenario.
       - If agent mode is significantly slower for trivial cases, consider shortcuts: e.g., for very simple classes, maybe skip agent and directly generate (but since user chooses mode, maybe not needed).
       - Test failure modes: what if the agent produces invalid code (syntax errors)? Possibly integrate a quick compile check after generation step and if syntax error, prompt agent to fix syntax (this could be an automatic step).
       - Also test the fallback: disable agent (agent.enabled = false) and run with `--mode=agent`, ensure it falls back or at least informs properly. 
   - At the end of Phase 6, agent mode should be robust and performance tuned. All planned parallel features implemented or consciously deferred if impractical.

7. **Phase 7: Documentation and Final Touches**  
   *Goal:* Update all documentation, and do final refactoring or cleanup.  
   **Tasks:**  
   - Update README or user guide to explain the two modes, how to enable agent mode, what the requirements are (e.g., "for agent mode you need Google ADK installed, set OPENAI_API_KEY, etc."). Include examples of using the CLI flag.
   - Document configuration options in the README’s configuration section. Provide example `application.yml` snippet as given in this design.
   - Maybe provide guidance on when to use each mode (e.g., agent mode might produce better results but requires more resources, etc.).
   - Code cleanup: remove any leftover debug prints, ensure logging is properly controlled by config (e.g., using a logger framework).
   - Double-check layering: The AgentCoordinator might import ADK classes (which are external). Ensure this is kept out of the domain layer. Possibly mark AgentCoordinator and related agent definitions as part of infrastructure or application (which is fine).
   - Merge any duplicated logic: During development, perhaps some logic ended up in both orchestrators. If so, refactor into a shared domain service. For instance, if both orchestrators use identical prompt templates for generation, put that template in a common place so it’s not duplicated.
   - Final testing pass for both modes in as real a scenario as possible (maybe integrate into a sample project to generate tests and verify they indeed compile and run).
   - After this, the feature is ready for release.

Each phase builds upon the previous, ensuring that we don’t break existing functionality while adding new capabilities. By Phase 5, we have a usable product with both modes accessible; Phase 6 and 7 then refine the agent mode to meet all goals (parallelism, config tunings, etc.). Throughout, we will maintain compliance with clean architecture (ensuring new code like AgentCoordinator doesn’t introduce undue coupling – e.g., treat ADK as an external tool integrated cleanly). 

This phased approach also allows possibly releasing the feature in stages (for example, first release might include agent mode behind an “experimental” flag after Phase 5, and a later release improves it with Phase 6 optimizations). The end result will be a consolidated JUnit Writer architecture where users can confidently choose either the straightforward deterministic approach or the powerful AI-driven agent approach, all within one cohesive codebase. 

