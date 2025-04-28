import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from unit_test_generator.domain.ports.file_system import FileSystemPort

logger = logging.getLogger(__name__)

# --- Token Estimation Helper --- (Keep this accessible)
def estimate_tokens(text: str) -> int:
    """Roughly estimates token count. Assumes ~3-4 chars per token."""
    if not text: return 0
    return (len(text) + 2) // 3

class ContextBuilderError(Exception):
    """Custom exception for context building errors."""
    pass

class ContextBuilder:
    """Builds context payload for LLM including RAG examples and dependencies."""

    def __init__(
        self,
        config: Dict[str, Any],
        repo_root: Path,
        file_system: FileSystemPort,
    ):
        """
        Initializes the ContextBuilder.

        Args:
            config: The application configuration.
            repo_root: Absolute path to the target repository root.
            file_system: Implementation of FileSystemPort to read files.
        """
        self.config = config
        self.repo_root = repo_root
        self.fs = file_system
        self.gen_config = config.get('generation', {})
        # Context building parameters
        self.similarity_threshold = self.gen_config.get('context_similarity_threshold', 0.70)
        self.max_rag_examples = self.gen_config.get('context_max_rag_examples', 2)
        self.max_dependency_files = self.gen_config.get('context_max_dependency_files', 3)
        self.max_context_tokens = self.gen_config.get('context_max_tokens', 25000)
        # Precompile DTO patterns
        dto_patterns_str = [
            r'.*\.dto\..*', r'.*DTO$', r'.*Request$', r'.*Response$',
            r'.*Model$', r'.*Entity$'
        ]
        self.dto_patterns_compiled = [re.compile(p) for p in dto_patterns_str]


    def build_llm_context(
        self,
        target_path: str,
        target_content: str,
        weighted_dependencies: List[Tuple[str, float]],
        rag_results: List[Dict[str, Any]],
        existing_test_file: Optional[Tuple[Path, str]] = None
    ) -> Dict[str, Any]:
        """
        Builds the context payload dictionary for the LLM.

        Args:
            target_path: Relative path of the target source file.
            target_content: Content of the target source file.
            weighted_dependencies: List of (relative_path, weight) for resolved dependencies.
            rag_results: List of dictionaries from VectorDBPort.find_similar.
            existing_test_file: Optional tuple of (test_file_path, test_file_content) if a test file already exists.

        Returns:
            The context payload dictionary.

        Raises:
            ContextBuilderError: If essential content cannot be read.
        """
        logger.info("Building context payload for LLM...")
        payload = {
            "target_file_path": target_path,
            "target_file_content": target_content,
            "similar_files_with_tests": [],
            "dependency_files": [],
            "language": self.gen_config.get('target_language', 'Kotlin'),
            "framework": self.gen_config.get('target_framework', 'JUnit5 with MockK'),
            "update_mode": False,
            "existing_test_file": None,
            "existing_test_content": None,
        }

        # If an existing test file was provided, add it to the context
        if existing_test_file:
            test_path, test_content = existing_test_file
            payload["update_mode"] = True
            payload["existing_test_file"] = str(test_path)
            payload["existing_test_content"] = test_content
            logger.info(f"Added existing test file to context: {test_path}")

        current_token_count = estimate_tokens(target_content)
        logger.debug(f"Initial token count (target file): {current_token_count}")

        # --- Phase 1: Add High-Confidence RAG Examples ---
        rag_examples_added = self._add_rag_examples(payload, rag_results, target_path, current_token_count)
        current_token_count += sum(estimate_tokens(ex['source_file_content']) + estimate_tokens(ex['test_file_content']) for ex in payload['similar_files_with_tests'])
        logger.debug(f"Token count after RAG phase: {current_token_count}")

        # --- Phase 2: Add Dependency Files ---
        self._add_dependency_files(payload, weighted_dependencies, target_path, current_token_count)
        final_token_count = current_token_count + sum(estimate_tokens(dep['content']) for dep in payload['dependency_files'])

        logger.debug(f"Final estimated token count for context payload: {final_token_count}")
        if final_token_count > self.max_context_tokens:
             logger.warning(f"Final context token count ({final_token_count}) EXCEEDS limit ({self.max_context_tokens}). LLM may truncate or fail.")

        logger.info(f"Context payload built: {len(payload['similar_files_with_tests'])} RAG examples, {len(payload['dependency_files'])} dependency files.")
        return payload

    def _add_rag_examples(self, payload: Dict, rag_results: List[Dict], target_path: str, current_token_count: int) -> int:
        """Adds RAG examples to the payload, respecting limits."""
        rag_examples_added = 0
        processed_rag_ids = set()
        sorted_rag_results = sorted(rag_results, key=lambda x: x.get('distance', 1.0))

        for result in sorted_rag_results:
            if rag_examples_added >= self.max_rag_examples: break

            metadata = result.get('metadata', {})
            similar_source_path = metadata.get('file_path')
            distance = result.get('distance', 1.0)
            similarity_score = 1.0 - distance

            if not similar_source_path or similar_source_path == target_path or similar_source_path in processed_rag_ids:
                continue
            processed_rag_ids.add(similar_source_path)

            if similarity_score < self.similarity_threshold:
                logger.debug(f"Skipping RAG result {similar_source_path} due to low similarity ({similarity_score:.2f} < {self.similarity_threshold:.2f})")
                continue

            linked_tests_str = metadata.get('linked_tests', '')
            test_paths = [p for p in linked_tests_str.split(',') if p]
            if not test_paths: continue
            test_file_rel_path = test_paths[0]

            try:
                similar_source_abs = self.repo_root / similar_source_path
                test_file_abs = self.repo_root / test_file_rel_path
                similar_source_content = self.fs.read_file(str(similar_source_abs))
                test_content = self.fs.read_file(str(test_file_abs))
                if not similar_source_content or not test_content: continue

                added_tokens = estimate_tokens(similar_source_content) + estimate_tokens(test_content)
                if current_token_count + added_tokens > self.max_context_tokens:
                    logger.warning(f"Context token limit ({self.max_context_tokens}) reached while adding RAG. Skipping example: {similar_source_path}")
                    break # Stop adding RAG examples

                payload['similar_files_with_tests'].append({
                    "source_file_path": similar_source_path,
                    "source_file_content": similar_source_content,
                    "test_file_path": test_file_rel_path,
                    "test_file_content": test_content,
                    "similarity_score": similarity_score
                })
                rag_examples_added += 1
                current_token_count += added_tokens # Important: Update token count locally for check
                logger.info(f"Added RAG example: {similar_source_path} (Similarity: {similarity_score:.2f})")

            except FileNotFoundError:
                logger.warning(f"Content file not found for RAG example {similar_source_path} or test {test_file_rel_path}. Skipping.")
            except Exception as e:
                 logger.warning(f"Failed to read content for RAG example {similar_source_path}: {e}")

        return rag_examples_added # Return count added

    def _add_dependency_files(self, payload: Dict, weighted_dependencies: List[Tuple[str, float]], target_path: str, current_token_count: int):
        """Adds dependency files to the payload, respecting limits and prioritizing DTOs."""
        if not weighted_dependencies: return

        logger.info(f"Adding dependency files with priority for DTOs/models...")
        dependencies_added = 0
        processed_deps = set() # Track added paths

        # --- First Pass: DTOs/Models ---
        for dep_path, weight in weighted_dependencies:
            if dependencies_added >= self.max_dependency_files: break
            if dep_path in processed_deps: continue

            is_dto = any(pattern.search(dep_path) for pattern in self.dto_patterns_compiled)
            if not is_dto: continue

            added_token_count = self._try_add_single_dependency(payload, dep_path, weight, target_path, current_token_count, is_dto=True)
            if added_token_count > 0:
                dependencies_added += 1
                current_token_count += added_token_count
                processed_deps.add(dep_path)

        # --- Second Pass: Remaining Dependencies ---
        remaining_slots = self.max_dependency_files - dependencies_added
        if remaining_slots <= 0: return

        logger.info(f"Adding up to {remaining_slots} more non-DTO dependencies...")
        for dep_path, weight in weighted_dependencies:
            if dependencies_added >= self.max_dependency_files: break
            if dep_path in processed_deps: continue # Skip already added DTOs/Models

            added_token_count = self._try_add_single_dependency(payload, dep_path, weight, target_path, current_token_count, is_dto=False)
            if added_token_count > 0:
                dependencies_added += 1
                current_token_count += added_token_count
                processed_deps.add(dep_path)


    def _try_add_single_dependency(self, payload: Dict, dep_path: str, weight: float, target_path: str, current_token_count: int, is_dto: bool) -> int:
        """Attempts to read and add a single dependency file, returning token count if added."""
        try:
            dep_abs_path = self.repo_root / dep_path
            if dep_abs_path == (self.repo_root / target_path): return 0 # Don't add target itself

            dep_content = self.fs.read_file(str(dep_abs_path))
            if not dep_content: return 0

            added_tokens = estimate_tokens(dep_content)
            if current_token_count + added_tokens > self.max_context_tokens:
                logger.warning(f"Context token limit ({self.max_context_tokens}) reached. Skipping dependency file: {dep_path}")
                return 0 # Indicate not added

            payload['dependency_files'].append({
                "dependency_path": dep_path,
                "content": dep_content,
                "is_dto": is_dto # Store this info if needed later
            })
            logger.info(f"Added {'DTO/model' if is_dto else 'dependency'} file: {dep_path} (Weight: {weight:.2f})")
            return added_tokens # Return tokens added

        except FileNotFoundError:
             logger.warning(f"Dependency file not found: {dep_path}")
             return 0
        except Exception as e:
            logger.warning(f"Failed to read content for dependency {dep_path}: {e}")
            return 0
