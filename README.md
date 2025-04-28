# JUnit Writer

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

JUnit Writer is an AI-powered tool that automatically generates high-quality JUnit tests for Kotlin and Java code. It uses advanced LLM techniques, including RAG (Retrieval-Augmented Generation) and multi-agent workflows, to create comprehensive test suites that follow best practices.

## 🚀 Features

- **Intelligent Test Generation**: Creates JUnit 5 tests with MockK for Kotlin and Java code
- **Multiple Operation Modes**: Choose between Standard, Agent (powered by Google's Agent Development Kit), and Commit modes
- **Self-Healing Capabilities**: Automatically fixes compilation errors and test failures
- **RAG-Enhanced Context**: Uses similar code examples to improve test quality
- **Dependency Analysis**: Includes relevant dependencies in the generation context
- **Clean Architecture**: Follows clean architecture principles for maintainability

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Operation Modes](#operation-modes)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/junit-writer.git
cd junit-writer

# Install dependencies
pip install -r requirements.txt

# Configure your API key
cp config/application.yml.example config/application.yml
# Edit config/application.yml to add your API key and repository path

# Index your repository
python main.py index

# Generate tests for a specific file
python main.py generate path/to/your/SourceFile.kt
```

## 📥 Installation

### Prerequisites

- Python 3.8 or higher
- Access to Google Gemini API or other supported LLM providers
- A Kotlin/Java project with a build system (Maven or Gradle)

For detailed installation instructions, see [Getting Started](docs/getting_started.md).

## ⚙️ Configuration

JUnit Writer uses a YAML configuration file located at `config/application.yml`. You can customize various aspects of the tool, including:

- Repository path
- LLM provider and model
- Test generation settings
- Self-healing options
- Operation mode preferences

For a complete list of configuration options, see [Configuration Guide](docs/configuration.md).

## 🔧 Usage

### Basic Commands

```bash
# Index your repository (required before generating tests)
python main.py index

# Generate tests for a specific file
python main.py generate path/to/your/SourceFile.kt

# Generate tests for files changed in a specific commit
python main.py generate abc1234
```

### Command Options

```bash
# Use agent mode for more complex test generation
python main.py generate path/to/your/SourceFile.kt --mode=agent

# Process multiple files in parallel when generating tests for a commit
python main.py generate abc1234 --parallel --max-workers=4
```

For more usage examples, see [Usage Examples](docs/usage_examples.md).

## 🔄 Operation Modes

JUnit Writer supports three primary operation modes:

- **Standard Mode**: A sequential, deterministic workflow with fixed control flow
- **Agent Mode**: An AI-driven, flexible workflow using a multi-agent approach
- **Commit Mode**: A specialized mode for processing files changed in a specific commit

For detailed information about each mode, see [Operation Modes](docs/operation_modes.md).

## 🏗️ Architecture

JUnit Writer follows clean architecture principles, with clear separation between:

- Domain layer (core business logic)
- Application layer (use cases and orchestration)
- Infrastructure layer (external interfaces and adapters)

The architecture includes interactive diagrams to help visualize the system:

![Architecture Diagram](docs/diagrams/architecture_mermaid.md#high-level-architecture)

For more details about the architecture, see [Architecture Documentation](docs/architecture.md).

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

For guidelines on contributing to this project, see [Contributing Guide](docs/contributing.md).

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.