import argparse

def parse_arguments() -> argparse.Namespace:
    """
    Configures and parses command line arguments for the application.

    Returns:
        argparse.Namespace: An object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Agentic Unit Test Generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Optional: Improves help message
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Available commands"
    )

    # --- Index Command Arguments ---
    parser_index = subparsers.add_parser(
        "index",
        help="Scan repository, build index, and populate RAG DB.",
        description="Scans the target repository based on configuration, creates a file index, "
                    "links source and test files, and optionally populates a vector database (RAG) "
                    "with source file embeddings."
    )
    parser_index.add_argument(
        "--force-rescan",
        action="store_true",
        help="Ignore existing index file and perform a full rescan."
    )
    parser_index.add_argument(
        "--no-rag",
        action="store_true",
        help="Skip populating the RAG vector database during indexing."
    )

    # --- Generate Command Arguments ---
    parser_generate = subparsers.add_parser(
        "generate",
        help="Generate unit tests for a specific file or files changed in a commit.",
        description="Generates unit tests for a specified source file or files changed in a commit. "
                    "It uses the RAG database to find similar, already tested files for context "
                    "and prompts an LLM to write the new tests."
    )
    parser_generate.add_argument(
        "target",
        help="Either a relative path to a source file (e.g., app/src/main/kotlin/com/example/MyClass.kt) "
             "or a commit hash (e.g., abc1234) to generate tests for files changed in that commit."
    )
    parser_generate.add_argument(
        "--parallel",
        action="store_true",
        help="Process multiple files in parallel when generating tests for a commit."
    )
    parser_generate.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of parallel workers when using --parallel (default: 4)."
    )
    parser_generate.add_argument(
        "--file-extensions",
        type=str,
        default=".kt,.java",
        help="Comma-separated list of file extensions to filter by when generating tests for a commit (default: .kt,.java)."
    )
    parser_generate.add_argument(
        "--mode",
        type=str,
        choices=["standard", "agent"],
        help="Execution mode: 'standard' for sequential generation, 'agent' for ADK multi-agent generation. If not specified, uses the value from config."
    )

    return parser.parse_args()
