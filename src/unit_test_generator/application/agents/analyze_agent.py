"""
Agent for analyzing source code.
"""
import logging
from pathlib import Path
from typing import Dict, Any, List

from unit_test_generator.domain.models.agent_models import Agent, AgentState

logger = logging.getLogger(__name__)


class AnalyzeAgent(Agent):
    """
    Agent for analyzing source code.
    """

    def _observe(self, state: AgentState) -> Dict[str, Any]:
        """
        Gather information about the source code.

        Args:
            state: The current state

        Returns:
            Observations about the source code
        """
        target_file_rel_path = state.data.get("target_file_rel_path")
        file_content = state.data.get("file_content")

        logger.info(f"Analyzing source file: {target_file_rel_path}")

        # Parse the code to extract classes, methods, etc.
        code_parser = self.tools.get("code_parser")
        imports, usage_weights = code_parser.parse(file_content, target_file_rel_path)

        # Generate embedding for the source file
        embedding_service = self.tools.get("embedding")
        embedding = embedding_service.generate_embedding(file_content)

        # Perform RAG search to find similar code
        vector_db = self.tools.get("vector_db")
        num_to_fetch = self.config.get('generation', {}).get('context_max_rag_examples', 2) * 2 + 5
        rag_results = vector_db.find_similar(
            embedding=embedding,
            n_results=num_to_fetch,
            filter_metadata={"has_tests": True}
        )

        logger.info(f"RAG search returned {len(rag_results)} potential candidates")

        # Resolve dependencies
        repo_root = state.data.get("repo_root")
        target_module = Path(target_file_rel_path).parts[0] if Path(target_file_rel_path).parts else "unknown"

        # We need to get the dependency resolver from the tools
        # For now, we'll just log the imports and usage weights
        logger.info(f"Found {len(imports)} imports with {len(usage_weights)} usage weights")

        return {
            "file_path": target_file_rel_path,
            "imports": imports,
            "usage_weights": usage_weights,
            "embedding": embedding,
            "rag_results": rag_results,
            "update_mode": state.data.get("update_mode", False),
            "existing_test_file": state.data.get("existing_test_file")
        }

    def _think(self, observations: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """
        Reason about the source code.

        Args:
            observations: Observations about the source code
            state: The current state

        Returns:
            Thoughts about the source code
        """
        file_path = observations.get("file_path")
        imports = observations.get("imports", [])
        rag_results = observations.get("rag_results", [])
        update_mode = observations.get("update_mode", False)

        # Analyze the complexity of the code based on imports and RAG results
        complexity = "medium"
        if len(imports) > 10:
            complexity = "high"
        elif len(imports) < 3:
            complexity = "low"

        # Determine the approach based on the analysis
        approach = "standard"
        if complexity == "high":
            approach = "incremental"

        # Determine if we have good examples from RAG
        has_good_examples = len(rag_results) > 0

        logger.info(f"Analysis complete for {file_path}. Complexity: {complexity}, Approach: {approach}")

        return {
            "complexity": complexity,
            "approach": approach,
            "has_good_examples": has_good_examples,
            "update_mode": update_mode,
            "analysis_complete": True
        }

    def _decide_actions(self, thoughts: Dict[str, Any], state: AgentState) -> List[Dict[str, Any]]:
        """
        Decide on actions to take.

        Args:
            thoughts: Thoughts about the source code
            state: The current state

        Returns:
            List of actions to take
        """
        # No external actions needed for analysis, as we've already done the work in observe and think
        return []

    def _execute_actions(self, actions: List[Dict[str, Any]], state: AgentState) -> List[Dict[str, Any]]:
        """
        Execute the actions.

        Args:
            actions: List of actions to take
            state: The current state

        Returns:
            Results of the actions
        """
        # No actions to execute
        return []

    def _update_state(self, state: AgentState, results: List[Dict[str, Any]]) -> AgentState:
        """
        Update the state based on action results.

        Args:
            state: The current state
            results: Results of the actions

        Returns:
            Updated state
        """
        # Get the analysis results from the thoughts
        thoughts = state.thoughts[-1] if state.thoughts else {}

        # Update the state with the analysis results
        return state.update({
            "analysis_complete": True,
            "complexity": thoughts.get("complexity", "medium"),
            "approach": thoughts.get("approach", "standard"),
            "has_good_examples": thoughts.get("has_good_examples", False),
            "update_mode": thoughts.get("update_mode", False)
        })

    def _is_success(self, state: AgentState) -> bool:
        """
        Determine if the analysis is complete.

        Args:
            state: The current state

        Returns:
            True if the analysis is complete, False otherwise
        """
        # Analysis is successful if it's complete
        return state.data.get("analysis_complete", False)
