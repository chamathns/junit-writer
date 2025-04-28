import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
import time

# Domain Ports
from unit_test_generator.domain.ports.file_system import FileSystemPort
from unit_test_generator.domain.ports.embedding_service import EmbeddingServicePort
from unit_test_generator.domain.ports.vector_db import VectorDBPort
from unit_test_generator.domain.ports.llm_service import LLMServicePort
from unit_test_generator.domain.ports.code_parser import CodeParserPort
from unit_test_generator.domain.ports.build_system import BuildSystemPort
from unit_test_generator.domain.ports.error_parser import ErrorParserPort
# Application Services
from unit_test_generator.application.services.dependency_resolver import DependencyResolverService
from unit_test_generator.application.services.context_builder import ContextBuilder, ContextBuilderError
from unit_test_generator.application.services.test_output_path_resolver import TestOutputPathResolver
# ADK and Agent related (assuming ADKRunnerAdapter is the interface)
from unit_test_generator.infrastructure.adk_tools.runner import ADKRunnerAdapter, SimplifiedADKRunner # Use appropriate runner type
# Helper
from unit_test_generator.application.utils.code_block_parser import parse_llm_code_block

logger = logging.getLogger(__name__)

class TestGenerationError(Exception):
    """Custom exception for orchestration errors."""
    def __init__(self, message, status="error"):
        self.message = message
        self.status = status
        super().__init__(message)

class TestGenerationOrchestrator:
    """Orchestrates the entire test generation process including self-healing."""

    def __init__(
        self,
        # --- Ports ---
        file_system: FileSystemPort,
        embedding_service: EmbeddingServicePort,
        vector_db: VectorDBPort,
        llm_service: LLMServicePort,
        code_parser: CodeParserPort,
        # --- Services ---
        dependency_resolver: DependencyResolverService,
        context_builder: ContextBuilder,
        path_resolver: TestOutputPathResolver,
        # --- Optional ADK Components ---
        adk_runner: Optional[Union[ADKRunnerAdapter, SimplifiedADKRunner]],
        # --- Config ---
        config: Dict[str, Any],
        repo_root: Path,
    ):
        self.fs = file_system
        self.embed_svc = embedding_service
        self.vector_db = vector_db
        self.llm_service = llm_service
        self.code_parser = code_parser
        self.dependency_resolver = dependency_resolver
        self.context_builder = context_builder
        self.path_resolver = path_resolver
        self.path_resolver.set_file_system(file_system)  # Set file system in path resolver
        self.adk_runner = adk_runner
        self.config = config
        self.repo_root = repo_root
        self.gen_config = config.get('generation', {})
        self.healing_config = config.get('self_healing', {})

    def run(self, target_file_rel_path: str) -> Dict[str, Any]:
        """
        Executes the test generation and optional self-healing process.

        Returns:
            Dictionary with 'status' and 'output_path' or 'message'.
        """
        start_time = time.time()
        logger.info(f"Orchestrator starting process for: {target_file_rel_path}")

        try:
            # 1. Initial Setup (Read, Embed, Parse)
            target_content, target_embedding, imports, usage_weights = self._initial_setup(target_file_rel_path)

            # 2. Resolve Dependencies
            weighted_dependencies = self._resolve_dependencies(target_file_rel_path, imports, usage_weights)

            # 3. RAG Search
            rag_results = self._perform_rag_search(target_embedding)

            # 4. Check for existing test file
            existing_test_file = self.path_resolver.find_existing_test_file(target_file_rel_path)
            update_mode = existing_test_file is not None

            # 5. Build Context
            context_payload = self.context_builder.build_llm_context(
                target_file_rel_path, target_content, weighted_dependencies, rag_results,
                existing_test_file=existing_test_file
            )

            # 6. Initial LLM Generation (or update if existing test file found)
            if update_mode:
                logger.info(f"Generating updated test code for existing test file")
                initial_generated_code = self._generate_updated_code(context_payload)
            else:
                logger.info(f"Generating new test code")
                initial_generated_code = self._generate_initial_code(context_payload)

            # 7. Determine & Write Initial File
            output_test_abs_path = self.path_resolver.resolve(target_file_rel_path)
            self._write_test_file(output_test_abs_path, initial_generated_code, "Initial")

            # 7. Self-Healing (via ADK if enabled)
            final_status = self._run_self_healing_if_enabled(
                target_file_rel_path, target_content, output_test_abs_path, initial_generated_code
            )

            # 8. Final Result
            end_time = time.time()
            logger.info(f"Orchestration for {target_file_rel_path} completed in {end_time - start_time:.2f} seconds.")
            return {"status": final_status, "output_path": str(output_test_abs_path)}

        except TestGenerationError as e:
            logger.error(f"Orchestration failed: {e.message}", exc_info=False) # Log only message for known errors
            return {"status": e.status, "message": e.message}
        except Exception as e:
            logger.critical(f"Unexpected error during orchestration: {e}", exc_info=True)
            return {"status": "error", "message": f"Unexpected orchestration error: {e}"}


    def _initial_setup(self, target_file_rel_path: str) -> Tuple[str, List[float], List[str], Dict[str, float]]:
        """Handles reading target, embedding, and parsing."""
        logger.info("Step 1: Initial Setup (Read, Embed, Parse)")
        target_file_abs_path = self.repo_root / target_file_rel_path
        try:
            if not self.fs.exists(str(target_file_abs_path)):
                raise FileNotFoundError(f"Target source file not found: {target_file_abs_path}")
            target_content = self.fs.read_file(str(target_file_abs_path))
            if not target_content or target_content.isspace():
                 raise ValueError("Target file is empty or whitespace-only")

            target_embedding = self.embed_svc.generate_embedding(target_content)
            if not target_embedding: raise ValueError("Embedding service returned empty result.")

            imports, usage_weights = self.code_parser.parse(target_content, target_file_rel_path)
            return target_content, target_embedding, imports, usage_weights

        except (FileNotFoundError, ValueError) as e:
            raise TestGenerationError(str(e)) from e
        except Exception as e:
            raise TestGenerationError(f"Initial setup failed: {e}") from e

    def _resolve_dependencies(self, target_file_rel_path: str, imports: List[str], usage_weights: Dict[str, float]) -> List[Tuple[str, float]]:
        """Resolves dependencies using the injected service."""
        logger.info("Step 2: Resolving Dependencies")
        if not imports: return []
        try:
            target_module = Path(target_file_rel_path).parts[0] if Path(target_file_rel_path).parts else "unknown"
            return self.dependency_resolver.resolve_dependencies(imports, usage_weights, target_module)
        except Exception as e:
            logger.warning(f"Dependency resolution failed: {e}. Proceeding without dependency context.", exc_info=True)
            return [] # Continue without dependencies if resolution fails

    def _perform_rag_search(self, target_embedding: List[float]) -> List[Dict[str, Any]]:
        """Performs RAG search using the Vector DB."""
        logger.info("Step 3: Performing RAG Search")
        try:
            # Fetch more to allow filtering by threshold later
            num_to_fetch = self.gen_config.get('context_max_rag_examples', 2) * 2 + 5
            results = self.vector_db.find_similar(
                embedding=target_embedding,
                n_results=num_to_fetch,
                filter_metadata={"has_tests": True}
            )
            logger.info(f"RAG search returned {len(results)} potential candidates.")
            return results
        except Exception as e:
            logger.warning(f"RAG search failed: {e}. Proceeding without RAG examples.", exc_info=True)
            return []

    def _generate_initial_code(self, context_payload: Dict[str, Any]) -> str:
        """Generates the initial test code using the LLM."""
        logger.info("Step 4: Generating Initial Test Code via LLM")
        try:
            initial_generated_code_raw = self.llm_service.generate_tests(context_payload)
            initial_generated_code = parse_llm_code_block(
                initial_generated_code_raw,
                context_payload.get("language", "kotlin")
            )
            if not initial_generated_code:
                 raise TestGenerationError("LLM failed to generate initial test code or returned invalid format.", status="error_llm_generation")
            logger.info("Successfully received initial generated test code.")
            return initial_generated_code
        except Exception as e:
            raise TestGenerationError(f"Initial LLM interaction error: {e}", status="error_llm_generation") from e

    def _generate_updated_code(self, context_payload: Dict[str, Any]) -> str:
        """Generates updated test code for an existing test file using the LLM."""
        logger.info("Step 4: Generating Updated Test Code via LLM")
        try:
            # Add specific instructions for updating existing test
            update_context = context_payload.copy()
            update_context["instruction"] = (
                "Update the existing test file to align with the changes in the source file. "
                "Preserve existing test methods and functionality where possible. "
                "Add new tests only for new or modified functionality in the source file. "
                "Ensure the updated test file maintains the same structure and style as the existing one. "
                "Do not remove existing tests unless they are no longer applicable."
            )

            updated_code_raw = self.llm_service.generate_tests(update_context)
            updated_code = parse_llm_code_block(
                updated_code_raw,
                context_payload.get("language", "kotlin")
            )
            if not updated_code:
                 raise TestGenerationError("LLM failed to generate updated test code or returned invalid format.", status="error_llm_generation")
            logger.info("Successfully received updated test code.")
            return updated_code
        except Exception as e:
            logger.error(f"Error generating updated test code: {e}", exc_info=True)
            # Fallback to existing test code if update fails
            if context_payload.get("existing_test_content"):
                logger.warning("Falling back to existing test code due to update failure")
                return context_payload["existing_test_content"]
            # If no fallback available, raise the error
            raise TestGenerationError(f"Test update LLM interaction error: {e}", status="error_llm_generation") from e

    def _write_test_file(self, path: Path, content: str, stage: str = "Unknown"):
        """Writes content to the specified test file path."""
        logger.info(f"Step 5: Writing {stage} Test File to {path}")
        try:
            self.fs.write_file(str(path), content)
            logger.info(f"{stage} generated tests written successfully.")
        except Exception as e:
            raise TestGenerationError(f"Failed to write {stage} test file {path}: {e}", status="error_file_write") from e

    def _run_self_healing_if_enabled(
        self,
        target_file_rel_path: str,
        target_content: str,
        output_test_abs_path: Path,
        initial_generated_code: str
    ) -> str:
        """Runs the ADK self-healing process if configured."""
        if not self.healing_config.get('enabled', False):
            logger.info("Self-healing disabled. Skipping.")
            return "success_generated_only"

        if not self.gen_config.get('write_to_repo', False):
            logger.warning("Self-healing requires 'generation.write_to_repo=true'. Skipping.")
            return "success_generated_only"

        if self.adk_runner is None:
            logger.error("Self-healing enabled but ADK Runner/Engine not provided to Use Case. Skipping.")
            return "error_config_adk_missing" # Indicate config issue

        # Log that we're using the improved self-healing process
        logger.info("Using improved self-healing process with hybrid error parsing.")

        logger.info("Step 6: Starting Self-Healing Cycle via ADK")
        try:
            # Prepare initial state for ADK reasoning engine with enhanced diagnostics
            initial_state = {
                "target_file_path": target_file_rel_path,
                "target_file_content": target_content,
                "test_file_abs_path": str(output_test_abs_path), # Pass absolute path
                "test_file_rel_path": str(output_test_abs_path.relative_to(self.repo_root)), # Relative for tools/prompts
                "current_test_code": initial_generated_code,
                "attempt_count": 0,
                "max_attempts": self.healing_config.get('max_attempts', 3),
                "language": self.gen_config.get('target_language', 'Kotlin'),
                "framework": self.gen_config.get('target_framework', 'JUnit5 with MockK'),
                "last_errors": None,
                "success": False,
                "diagnostic_mode": True,  # Enable detailed diagnostics
                "incremental_fixes": True,  # Fix one error at a time if possible
                "validation_enabled": True,  # Validate fixes before applying
                "error_categories": [],  # Track error categories for better diagnostics
                "fix_history": []  # Track fix attempts and their results
            }

            # Define the goal for the reasoning engine with more specific instructions
            goal = (
                f"Verify and fix the unit test file at '{initial_state['test_file_rel_path']}' "
                f"for the source file '{target_file_rel_path}' until it compiles and passes execution. "
                f"Follow these steps:\n"
                f"1. Read the current test file\n"
                f"2. Run the test to identify errors\n"
                f"3. Parse errors carefully using the parse_errors tool\n"
                f"4. For each error, generate a targeted fix using the generate_fix tool\n"
                f"5. Apply fixes incrementally, focusing on one error category at a time\n"
                f"6. Validate each fix by running the test again\n"
                f"7. If a fix doesn't work, try a different approach\n"
                f"8. Continue until the test passes or max attempts ({initial_state['max_attempts']}) is reached.\n"
                f"9. Prioritize fixing import errors, then MockK setup issues, then assertions."
                # Add more detail about using other tools if needed by the specific ADK engine/prompt
            )

            # Run the ADK agent
            logger.info("Invoking ADK runner...")
            # Adapt based on whether runner is sync or async
            if isinstance(self.adk_runner, SimplifiedADKRunner):
                import asyncio
                final_state = asyncio.run(self.adk_runner.run(goal=goal, initial_state=initial_state))
            else: # Assuming ADKRunnerAdapter or similar sync interface
                final_state = self.adk_runner.run(goal=goal, initial_state=initial_state)

            logger.info("ADK runner finished.")
            logger.debug(f"Final ADK State: {final_state}")

            # Process the final state
            if final_state.get("success", False):
                # Optional: Verify final code exists and write it one last time?
                # final_code = final_state.get("current_test_code")
                # if final_code: self._write_test_file(output_test_abs_path, final_code, "Final Healed")
                return "success_healed"
            else:
                logger.error(f"Self-healing failed or hit max attempts. Last attempted code remains at: {output_test_abs_path}")
                # Optionally write the last known code state from final_state if different
                last_code = final_state.get("current_test_code")
                if last_code and last_code != initial_generated_code:
                     try:
                         self._write_test_file(output_test_abs_path, last_code, "Last Failed Attempt")
                     except Exception: pass # Ignore write error here, already logged failure
                return "error_healing_failed"

        except Exception as e:
            logger.error(f"Error during ADK self-healing cycle: {e}", exc_info=True)
            raise TestGenerationError(f"Self-healing cycle failed: {e}", status="error_healing_exception") from e
