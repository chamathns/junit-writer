# JUnit Writer Usage Examples

This document provides examples of how to use JUnit Writer in various scenarios.

## Basic Usage

### Indexing Your Repository

Before generating tests, you need to index your repository:

```bash
python main.py index
```

This command scans your repository, creates an index of files, and builds a vector database for RAG.

### Generating Tests for a Single File

To generate tests for a single file:

```bash
python main.py generate path/to/your/SourceFile.kt
```

Replace `path/to/your/SourceFile.kt` with the relative path to a source file in your repository.

### Generating Tests for Files Changed in a Commit

To generate tests for files changed in a specific commit:

```bash
python main.py generate abc1234
```

Replace `abc1234` with the commit hash.

## Advanced Usage

### Using Different Operation Modes

#### Standard Mode

Standard mode is the default mode. It uses a sequential, deterministic workflow:

```bash
python main.py generate path/to/your/SourceFile.kt --mode=standard
```

#### Agent Mode

Agent mode uses a multi-agent workflow for more complex scenarios:

```bash
python main.py generate path/to/your/SourceFile.kt --mode=agent
```

### Parallel Processing

When generating tests for files changed in a commit, you can process multiple files in parallel:

```bash
python main.py generate abc1234 --parallel --max-workers=4
```

This command processes up to 4 files in parallel.

### Filtering Files by Extension

When generating tests for files changed in a commit, you can filter files by extension:

```bash
python main.py generate abc1234 --file-extensions=.kt,.java
```

This command only processes files with the specified extensions.

### Forcing a Repository Rescan

To force a complete rescan of your repository during indexing:

```bash
python main.py index --force-rescan
```

### Skipping RAG Database Population

To skip populating the RAG database during indexing:

```bash
python main.py index --no-rag
```

## Use Case Examples

### Use Case 1: Simple Service Class

For a simple service class with few dependencies:

```bash
python main.py generate src/main/kotlin/com/example/service/UserService.kt
```

Standard mode works well for this case.

### Use Case 2: Complex Domain Model

For a complex domain model with many dependencies:

```bash
python main.py generate src/main/kotlin/com/example/domain/OrderProcessing.kt --mode=agent
```

Agent mode is better suited for complex classes.

### Use Case 3: Batch Processing After a Major Refactoring

After a major refactoring with many changed files:

```bash
python main.py generate abc1234 --parallel --max-workers=8
```

This processes all changed files in parallel for faster results.

### Use Case 4: Updating Tests After API Changes

When updating tests after API changes:

```bash
python main.py generate src/main/kotlin/com/example/api/UserController.kt
```

JUnit Writer will detect the existing test file and update it accordingly.

## Tips and Best Practices

### 1. Start with Standard Mode

Start with standard mode for simple classes and switch to agent mode if needed:

```bash
python main.py generate path/to/your/SourceFile.kt
```

If the results aren't satisfactory, try agent mode:

```bash
python main.py generate path/to/your/SourceFile.kt --mode=agent
```

### 2. Use Commit Mode for Incremental Changes

For incremental changes, use commit mode to focus on changed files:

```bash
python main.py generate abc1234
```

### 3. Adjust Self-Healing Settings

If tests are failing to compile, adjust self-healing settings in your configuration:

```yaml
self_healing:
  enabled: true
  max_attempts: 5  # Increase from default
```

### 4. Optimize RAG Context

For better test generation, optimize RAG context settings:

```yaml
generation:
  context_similarity_threshold: 0.8  # Increase for more relevant examples
  context_max_rag_examples: 8        # Increase for more examples
```

### 5. Review and Refine Generated Tests

Always review generated tests and refine them as needed. JUnit Writer is a tool to assist you, not replace your judgment.

## Troubleshooting Common Issues

### Issue: Tests Fail to Compile

If generated tests fail to compile:

1. Check if self-healing is enabled:
   ```yaml
   self_healing:
     enabled: true
   ```

2. Increase the number of self-healing attempts:
   ```yaml
   self_healing:
     max_attempts: 5
   ```

3. Try agent mode:
   ```bash
   python main.py generate path/to/your/SourceFile.kt --mode=agent
   ```

### Issue: Tests Don't Cover All Methods

If generated tests don't cover all methods:

1. Adjust the context settings:
   ```yaml
   generation:
     context_max_rag_examples: 10
     context_max_dependency_files: 20
   ```

2. Try agent mode:
   ```bash
   python main.py generate path/to/your/SourceFile.kt --mode=agent
   ```

### Issue: Repository Indexing Takes Too Long

If repository indexing takes too long:

1. Adjust the exclude patterns in your configuration:
   ```yaml
   repository:
     exclude_patterns:
       - "**/.git/**"
       - "**/build/**"
       - "**/target/**"
       - "**/node_modules/**"
   ```

2. Skip RAG database population:
   ```bash
   python main.py index --no-rag
   ```

## Conclusion

JUnit Writer is a flexible tool that can be adapted to various scenarios. By understanding the different operation modes and configuration options, you can optimize it for your specific needs.

For more information, refer to the [main documentation](../README.md).
