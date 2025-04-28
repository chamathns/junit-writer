# Getting Started with JUnit Writer

This guide will help you set up and start using JUnit Writer to generate unit tests for your Kotlin or Java project.

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.8 or higher
- Access to Google Gemini API or other supported LLM providers
- A Kotlin/Java project with a build system (Maven or Gradle)

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/junit-writer.git
   cd junit-writer
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application**

   Copy the example configuration file and edit it with your settings:

   ```bash
   cp config/application.yml.example config/application.yml
   ```

   Open `config/application.yml` in your favorite editor and update the following:
   
   - Set `repository.root_path` to the path of your Kotlin/Java project
   - Configure the LLM provider and model in the `generation` section
   - Set your API key (or use environment variables for better security)

## Verifying Your Setup

Run the verification script to ensure everything is set up correctly:

```bash
python scripts/verify_setup.py
```

This script checks:
- Python version
- Required dependencies
- Configuration file
- API key availability

## First-Time Usage

### 1. Index Your Repository

Before generating tests, you need to index your repository. This creates a database of your code that JUnit Writer uses for context:

```bash
python main.py index
```

This command:
- Scans your repository for source files
- Creates an index of files and their relationships
- Builds a vector database for RAG (Retrieval-Augmented Generation)

### 2. Generate Your First Test

Now you can generate a test for a specific file:

```bash
python main.py generate path/to/your/SourceFile.kt
```

Replace `path/to/your/SourceFile.kt` with the relative path to a source file in your repository.

### 3. Review the Generated Test

JUnit Writer will create a test file in the `generated-tests` directory (or the directory specified in your configuration). Review the test and make any necessary adjustments.

## Troubleshooting

### Common Issues

#### API Key Not Found

If you see an error about missing API key:

1. Ensure you've set the API key in your configuration file or as an environment variable
2. For Google Gemini, set `GOOGLE_API_KEY` environment variable:
   ```bash
   export GOOGLE_API_KEY=your_api_key_here
   ```

#### Repository Indexing Fails

If indexing fails:

1. Check that the repository path in your configuration is correct
2. Ensure you have read permissions for all files in the repository
3. Try running with the `--force-rescan` flag:
   ```bash
   python main.py index --force-rescan
   ```

#### Test Generation Fails

If test generation fails:

1. Check the logs for specific error messages
2. Ensure the target file exists and is a valid Kotlin or Java file
3. Verify that the repository has been indexed successfully
4. Try using a different mode:
   ```bash
   python main.py generate path/to/your/SourceFile.kt --mode=agent
   ```

## Next Steps

Now that you have JUnit Writer set up and running, you can:

- Explore different [operation modes](operation_modes.md) for test generation
- Customize the [configuration](configuration.md) for your specific needs
- Check out [usage examples](usage_examples.md) for advanced scenarios

For more information, refer to the [main documentation](../README.md).
