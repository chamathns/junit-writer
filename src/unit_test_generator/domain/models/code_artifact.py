from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum, auto


class ArtifactType(Enum):
    SOURCE = auto()
    TEST = auto()


@dataclass
class CodeArtifact:
    """Represents a single source or test file."""
    relative_path: str
    absolute_path: str
    module_name: str
    artifact_type: ArtifactType
    language: Optional[str] = None  # e.g., 'kotlin', 'java', inferred from extension
    content: Optional[str] = None  # Content might be loaded lazily


@dataclass
class SourceCodeArtifact(CodeArtifact):
    """Specialized artifact for source code."""
    artifact_type: ArtifactType = ArtifactType.SOURCE
    linked_test_paths: List[str] = field(default_factory=list)  # Relative paths of corresponding tests


@dataclass
class TestCodeArtifact(CodeArtifact):
    """Specialized artifact for test code."""
    artifact_type: ArtifactType = ArtifactType.TEST
    linked_source_path: Optional[str] = None  # Relative path of corresponding source


@dataclass
class RepositoryStructure:
    """Holds the structured information about the scanned repository."""
    repo_root: str
    modules: dict[str, dict[str, list[CodeArtifact]]] = field(default_factory=dict)

    # Example: modules['my_module']['source_files'] = [SourceCodeArtifact(...)]
    #          modules['my_module']['test_files'] = [TestCodeArtifact(...)]

    def add_artifact(self, artifact: CodeArtifact):
        """Adds a code artifact to the structure."""
        if artifact.module_name not in self.modules:
            self.modules[artifact.module_name] = {"source_files": [], "test_files": []}

        if artifact.artifact_type == ArtifactType.SOURCE:
            self.modules[artifact.module_name]["source_files"].append(artifact)
        elif artifact.artifact_type == ArtifactType.TEST:
            self.modules[artifact.module_name]["test_files"].append(artifact)

    def get_all_source_files(self) -> List[SourceCodeArtifact]:
        all_sources = []
        for module_data in self.modules.values():
            all_sources.extend(module_data.get("source_files", []))
        return all_sources

    def get_all_test_files(self) -> List[TestCodeArtifact]:
        all_tests = []
        for module_data in self.modules.values():
            all_tests.extend(module_data.get("test_files", []))
        return all_tests

    def find_source_by_relative_path(self, rel_path: str) -> Optional[SourceCodeArtifact]:
        for source_file in self.get_all_source_files():
            if source_file.relative_path == rel_path:
                return source_file
        return None