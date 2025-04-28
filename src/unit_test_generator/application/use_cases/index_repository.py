import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import dataclasses
import time

from src.unit_test_generator.domain.ports.file_system import FileSystemPort
from src.unit_test_generator.domain.ports.embedding_service import EmbeddingServicePort
from src.unit_test_generator.domain.ports.vector_db import VectorDBPort
from src.unit_test_generator.domain.models.code_artifact import (
    SourceCodeArtifact, TestCodeArtifact, ArtifactType, RepositoryStructure
)
from src.unit_test_generator.infrastructure.adapters.file_system_adapter import FileSystemAdapter

logger = logging.getLogger(__name__)

class IndexRepositoryUseCase:
    """
    Use case responsible for scanning a repository, identifying source/test files,
    linking them, persisting the index, and populating the RAG Vector DB.
    """
    # BATCH_SIZE for embedding and DB upsert
    BATCH_SIZE = 32

    def __init__(
        self,
        file_system: FileSystemPort,
        embedding_service: EmbeddingServicePort,
        vector_db: VectorDBPort,
        config: Dict[str, Any]
    ):
        self.fs = file_system
        self.embed_svc = embedding_service
        self.vector_db = vector_db
        self.config = config
        self.repo_root = Path(self.config['repository']['root_path']).resolve()
        self.index_file_path = self.config['indexing']['index_file_path']
        self.source_roots = [p.replace('/', os.sep) for p in self.config['indexing']['source_roots']]
        self.test_roots = [p.replace('/', os.sep) for p in self.config['indexing']['test_roots']]
        self.code_ext = set(self.config['indexing']['code_extensions'])
        self.ignore_patterns = self.config['indexing']['ignore_patterns']
        self.test_suffixes = self.config['indexing']['test_suffixes']
        self.test_prefixes = self.config['indexing']['test_prefixes']

        # Use the concrete adapter for JSON operations (consider refining this)
        if isinstance(self.fs, FileSystemAdapter):
             self.fs_adapter = self.fs
        else:
             logger.warning("Using a FileSystemPort implementation that might not support direct JSON operations.")
             self.fs_adapter = None

    def execute(self, force_rescan: bool = False, populate_rag: bool = True): # Default populate_rag to True
        """
        Executes the repository indexing process.

        Args:
            force_rescan: If True, ignores existing index file and rescans.
            populate_rag: If True, attempts to populate the RAG DB.
        """
        start_time = time.time()
        logger.info(f"Starting repository indexing for: {self.repo_root}")
        logger.info(f"Config - Force Rescan: {force_rescan}, Populate RAG: {populate_rag}")

        # --- Check for existing index ---
        # (Keep existing logic for loading/skipping scan if needed, but ensure we rescan if forced)
        if not force_rescan and self.fs.exists(self.index_file_path):
            logger.info(f"Index file found at {self.index_file_path}. Loading not fully implemented, proceeding with rescan.")
            # If loading was implemented:
            #   loaded_structure = self._load_index_file()
            #   if loaded_structure:
            #       if populate_rag:
            #            self._populate_rag_database(loaded_structure) # Populate RAG even if index loaded
            #       else:
            #            logger.info("Skipping RAG population as per request.")
            #       end_time = time.time()
            #       logger.info(f"Repository indexing finished (used existing index) in {end_time - start_time:.2f} seconds.")
            #       return {"status": "success_loaded", "indexed_modules": len(loaded_structure.modules)}
            #   else:
            #       logger.warning("Failed to load existing index. Performing full scan.")


        # --- Scan and Build ---
        repo_structure = RepositoryStructure(repo_root=str(self.repo_root))
        self._scan_and_build_structure(repo_structure)
        self._link_source_and_tests(repo_structure)

        # --- Save Index ---
        self._save_index_file(repo_structure)

        # --- Populate RAG ---
        if populate_rag:
             if self.embed_svc and self.vector_db:
                 self._populate_rag_database(repo_structure)
             else:
                 logger.error("Cannot populate RAG: EmbeddingService or VectorDB service not provided.")
        else:
             logger.info("Skipping RAG database population as per request.")

        end_time = time.time()
        logger.info(f"Repository indexing finished (scanned) in {end_time - start_time:.2f} seconds.")
        return {"status": "success_scanned", "indexed_modules": len(repo_structure.modules)}


    # --- Keep _scan_and_build_structure, _get_module_context, _classify_artifact, _link_source_and_tests, _infer_language as before ---
    # ... (Include the implementation of these methods from the previous response) ...
    def _scan_and_build_structure(self, repo_structure: RepositoryStructure):
        """Scans the directory and populates the initial structure based on Gradle conventions."""
        logger.debug("Scanning directories...")

        for file_path_obj in self.fs.walk_directory(str(self.repo_root), self.ignore_patterns):
            if file_path_obj.suffix not in self.code_ext:
                continue # Skip non-code files based on extension

            try:
                # Get path relative to repo root
                relative_path_str = self.fs.get_relative_path(str(file_path_obj), str(self.repo_root))
                relative_path = Path(relative_path_str)
            except ValueError:
                logger.warning(f"Could not determine relative path for {file_path_obj}. Skipping.")
                continue

            # Determine module and path relative to module
            module_name, path_in_module = self._get_module_context(relative_path)
            if not module_name or not path_in_module:
                logger.debug(f"Skipping file (not in a recognized module structure): {relative_path_str}")
                continue

            # Determine artifact type and package path
            artifact_type, package_path = self._classify_artifact(path_in_module)

            if artifact_type and package_path is not None: # package_path can be empty string for root package
                language = self._infer_language(file_path_obj.suffix)
                common_args = {
                    "relative_path": relative_path_str,
                    "absolute_path": str(file_path_obj.resolve()),
                    "module_name": module_name,
                    "language": language
                    # content is not stored here, loaded on demand
                }
                if artifact_type == ArtifactType.SOURCE:
                    artifact = SourceCodeArtifact(**common_args)
                else: # artifact_type == ArtifactType.TEST:
                     artifact = TestCodeArtifact(**common_args)

                repo_structure.add_artifact(artifact)

        logger.info(f"Initial scan complete. Found modules: {list(repo_structure.modules.keys())}")


    def _get_module_context(self, relative_path: Path) -> Tuple[Optional[str], Optional[Path]]:
        """Determines the module name and path relative to the module root."""
        if not relative_path.parts:
            return None, None

        module_name = relative_path.parts[0]
        module_root = self.repo_root / module_name

        # Basic check: does the module directory actually exist?
        if not self.fs.exists(str(module_root)):
             logger.warning(f"Detected module '{module_name}' but directory not found at {module_root}. Skipping {relative_path}")
             return None, None

        path_in_module = Path(*relative_path.parts[1:])
        return module_name, path_in_module


    def _classify_artifact(self, path_in_module: Path) -> Tuple[Optional[ArtifactType], Optional[str]]:
        """Classifies if a path within a module is source/test and extracts package path."""
        path_str = str(path_in_module).replace(os.sep, '/') # Normalize for comparison

        for src_root in self.source_roots: # e.g., "src/main/kotlin"
            # Ensure src_root ends with '/' for correct prefix check
            src_root_prefix = src_root if src_root.endswith('/') else src_root + '/'
            if path_str.startswith(src_root_prefix):
                package_path = path_str[len(src_root_prefix):] # Get the part after src/main/kotlin/
                # Return directory part as package, handle files directly in root
                return ArtifactType.SOURCE, str(Path(package_path).parent) if '/' in package_path else ""

        for test_root in self.test_roots: # e.g., "src/test/kotlin"
            test_root_prefix = test_root if test_root.endswith('/') else test_root + '/'
            if path_str.startswith(test_root_prefix):
                package_path = path_str[len(test_root_prefix):]
                return ArtifactType.TEST, str(Path(package_path).parent) if '/' in package_path else ""

        return None, None


    def _link_source_and_tests(self, repo_structure: RepositoryStructure):
        """Attempts to link source files to test files based on conventions."""
        logger.debug("Linking source and test files...")

        tests_by_module_pkg: Dict[str, Dict[str, List[TestCodeArtifact]]] = {}
        for test_file in repo_structure.get_all_test_files():
            module_name = test_file.module_name
            path_in_module = Path(*Path(test_file.relative_path).parts[1:])
            _, package_path = self._classify_artifact(path_in_module)

            if package_path is None: continue

            if module_name not in tests_by_module_pkg:
                tests_by_module_pkg[module_name] = {}
            if package_path not in tests_by_module_pkg[module_name]:
                tests_by_module_pkg[module_name][package_path] = []
            tests_by_module_pkg[module_name][package_path].append(test_file)


        for source_file in repo_structure.get_all_source_files():
            source_stem = self.fs.get_file_stem(source_file.relative_path)
            module_name = source_file.module_name

            path_in_module = Path(*Path(source_file.relative_path).parts[1:])
            _, package_path = self._classify_artifact(path_in_module)
            if package_path is None: continue

            possible_test_stems = {f"{source_stem}{suffix}" for suffix in self.test_suffixes} | \
                                  {f"{prefix}{source_stem}" for prefix in self.test_prefixes}

            candidate_tests = tests_by_module_pkg.get(module_name, {}).get(package_path, [])

            for test_file in candidate_tests:
                test_stem = self.fs.get_file_stem(test_file.relative_path)
                if test_stem in possible_test_stems:
                    source_file.linked_test_paths.append(test_file.relative_path)
                    test_file.linked_source_path = source_file.relative_path
                    logger.debug(f"Linked: {source_file.relative_path} <-> {test_file.relative_path}")

    @staticmethod
    def _infer_language(extension: str) -> Optional[str]:
        """Infers programming language from file extension."""
        ext_map = {
            ".kt": "kotlin",
            ".java": "java",
            ".py": "python",
        }
        return ext_map.get(extension.lower())

    # --- End of previously included methods ---

    def _save_index_file(self, repo_structure: RepositoryStructure):
        """Serializes the repository structure to a JSON file."""
        logger.debug(f"Saving index file to: {self.index_file_path}")
        try:
            # Ensure parent directory exists
            self.fs.make_dirs(self.index_file_path)
            # Convert RepositoryStructure object to a serializable dictionary
            index_data = dataclasses.asdict(repo_structure)
        except Exception as e:
            logger.error(f"Failed to convert repository structure to dictionary: {e}")
            return # Cannot save if conversion fails

        if self.fs_adapter:
            try:
                self.fs_adapter.write_json(self.index_file_path, index_data)
                logger.info(f"Successfully saved index file to {self.index_file_path} using FileSystemAdapter")
            except Exception as e:
                 logger.error(f"Failed to write index JSON file {self.index_file_path}: {e}")
                 # Try fallback method
                 self._save_index_file_fallback(index_data)
        else:
            logger.warning("FileSystemAdapter with JSON support not available. Using fallback method.")
            self._save_index_file_fallback(index_data)

    def _save_index_file_fallback(self, index_data: Dict):
        """Fallback method to save index file when FileSystemAdapter is not available."""
        try:
            import json
            # Convert to JSON string with proper formatting
            json_content = json.dumps(index_data, indent=2, default=str)
            # Use the standard write_file method
            self.fs.write_file(self.index_file_path, json_content)
            logger.info(f"Successfully saved index file to {self.index_file_path} using fallback method")
        except Exception as e:
            logger.error(f"Failed to save index file using fallback method: {e}")
            return


    def _populate_rag_database(self, repo_structure: RepositoryStructure):
        """Populates the Vector DB with embeddings and metadata for source files."""
        logger.info("Starting RAG database population...")
        start_time = time.time()
        source_files_to_process = repo_structure.get_all_source_files()
        total_files = len(source_files_to_process)
        processed_count = 0
        error_count = 0

        logger.info(f"Found {total_files} source files to process for RAG DB.")

        # Process in batches
        for i in range(0, total_files, self.BATCH_SIZE):
            batch_files = source_files_to_process[i:min(i + self.BATCH_SIZE, total_files)]
            batch_ids = []
            batch_contents = []
            batch_metadatas_initial = [] # Store original metadata before embedding

            logger.info(f"Processing batch {i // self.BATCH_SIZE + 1}/{(total_files + self.BATCH_SIZE - 1) // self.BATCH_SIZE} ({len(batch_files)} files)")

            # 1. Read file contents for the batch
            for source_file in batch_files:
                try:
                    content = self.fs.read_file(source_file.absolute_path)
                    if not content or content.isspace():
                        logger.warning(f"Skipping empty or whitespace-only file: {source_file.relative_path}")
                        continue

                    batch_ids.append(source_file.relative_path) # Use relative path as ID
                    batch_contents.append(content)
                    # Prepare metadata (will be associated after embedding)
                    metadata = {
                        "file_path": source_file.relative_path,
                        "module_name": source_file.module_name,
                        "language": source_file.language or "unknown",
                        "has_tests": bool(source_file.linked_test_paths),
                        # Convert list to comma-separated string for ChromaDB compatibility
                        "linked_tests": ",".join(source_file.linked_test_paths)
                    }
                    batch_metadatas_initial.append(metadata)

                except Exception as e:
                    logger.error(f"Failed to read file {source_file.relative_path}: {e}")
                    error_count += 1

            if not batch_ids: # If all files in batch failed reading
                continue

            # 2. Generate embeddings for the batch contents
            try:
                batch_embeddings = self.embed_svc.generate_embeddings(batch_contents)
                if len(batch_embeddings) != len(batch_ids):
                     logger.error(f"Mismatch between embeddings generated ({len(batch_embeddings)}) and files processed ({len(batch_ids)}) in batch.")
                     # Handle mismatch - skip batch? try individually?
                     error_count += len(batch_ids) # Count all as errors for this batch
                     continue

                # Filter out any potential empty embeddings returned on error
                # Check if embeddings are valid (not None and have values)
                valid_indices = [idx for idx, emb in enumerate(batch_embeddings) if emb is not None and len(emb) > 0]
                if len(valid_indices) < len(batch_ids):
                    logger.warning(f"{len(batch_ids) - len(valid_indices)} files failed embedding generation in this batch.")
                    error_count += (len(batch_ids) - len(valid_indices))

                final_batch_ids = [batch_ids[idx] for idx in valid_indices]
                final_batch_embeddings = [batch_embeddings[idx] for idx in valid_indices]
                final_batch_metadatas = [batch_metadatas_initial[idx] for idx in valid_indices]

            except Exception as e:
                logger.error(f"Failed to generate embeddings for batch: {e}", exc_info=True)
                error_count += len(batch_ids)
                continue # Skip this batch

            if not final_batch_ids: # If all embeddings failed
                continue

            # 3. Upsert the batch into the Vector DB
            try:
                self.vector_db.upsert_documents(
                    doc_ids=final_batch_ids,
                    embeddings=final_batch_embeddings,
                    metadatas=final_batch_metadatas
                )
                processed_count += len(final_batch_ids)
            except Exception as e:
                logger.error(f"Failed to upsert batch into Vector DB: {e}", exc_info=True)
                error_count += len(final_batch_ids) # Count as errors if upsert fails

        end_time = time.time()
        logger.info(f"Finished RAG database population in {end_time - start_time:.2f} seconds.")
        logger.info(f"Processed: {processed_count}, Errors: {error_count}, Total Source Files: {total_files}")
        try:
            db_count = self.vector_db.count()
            logger.info(f"Vector DB now contains {db_count} documents.")
        except Exception as e:
             logger.error(f"Could not get final count from Vector DB: {e}")