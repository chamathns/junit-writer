# Contributing to JUnit Writer

Thank you for your interest in contributing to JUnit Writer! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)

## Code of Conduct

Please be respectful and considerate of others when contributing to this project. We aim to foster an inclusive and welcoming community.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up your development environment
4. Create a new branch for your feature or bug fix
5. Make your changes
6. Test your changes
7. Submit a pull request

## Development Environment

### Prerequisites

- Python 3.8 or higher
- Access to Google Gemini API or other supported LLM providers
- A Kotlin/Java project for testing

### Setup

1. Clone your fork of the repository:
   ```bash
   git clone https://github.com/yourusername/junit-writer.git
   cd junit-writer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

3. Configure the application:
   ```bash
   cp config/application.yml.example config/application.yml
   ```
   Edit `config/application.yml` with your settings.

4. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Coding Standards

We follow PEP 8 style guide for Python code. Please ensure your code adheres to these standards.

### Code Style

- Use 4 spaces for indentation
- Use snake_case for variable and function names
- Use CamelCase for class names
- Keep line length to a maximum of 100 characters
- Add docstrings to all functions, classes, and modules
- Use type hints where appropriate

### Project Structure

The project follows clean architecture principles:

- `src/unit_test_generator/domain/`: Domain layer (core business logic)
- `src/unit_test_generator/application/`: Application layer (use cases)
- `src/unit_test_generator/infrastructure/`: Infrastructure layer (adapters)
- `src/unit_test_generator/cli/`: Command-line interface
- `tests/`: Test files

## Pull Request Process

1. Create a new branch for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
   or
   ```bash
   git checkout -b fix/your-bug-fix
   ```

2. Make your changes and commit them with clear, descriptive commit messages:
   ```bash
   git commit -m "Add feature: your feature description"
   ```

3. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

4. Submit a pull request to the main repository.

5. Update the README.md or documentation with details of changes if appropriate.

6. The pull request will be reviewed by maintainers. Address any requested changes.

7. Once approved, your pull request will be merged.

## Testing

Please ensure that your code includes appropriate tests:

1. Write unit tests for new features or bug fixes
2. Ensure all tests pass before submitting a pull request
3. Run tests using pytest:
   ```bash
   pytest
   ```

4. Aim for high test coverage:
   ```bash
   pytest --cov=src
   ```

## Documentation

Good documentation is essential:

1. Update the README.md if you change functionality
2. Add or update docstrings for all functions, classes, and modules
3. Update or add documentation in the `/docs` directory as needed
4. Use clear, concise language in documentation

## Issue Reporting

If you find a bug or have a feature request:

1. Check if the issue already exists in the GitHub issues
2. If not, create a new issue with a clear description
3. For bugs, include:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment details (OS, Python version, etc.)
4. For feature requests, include:
   - Clear description of the feature
   - Rationale for adding the feature
   - Potential implementation approach (if you have ideas)

## Adding New Features

When adding new features, consider the following:

### New LLM Providers

To add support for a new LLM provider:

1. Create a new adapter in `src/unit_test_generator/infrastructure/adapters/llm/`
2. Implement the `LLMServicePort` interface
3. Update the factory in `src/unit_test_generator/cli/adapter_factory.py`
4. Add configuration options in `config/application.yml.example`
5. Update documentation

### New Operation Modes

To add a new operation mode:

1. Create a new orchestrator in `src/unit_test_generator/application/orchestrators/`
2. Update the `ModeSelector` in `src/unit_test_generator/application/services/mode_selector.py`
3. Add the mode to the CLI argument parser
4. Update configuration options
5. Update documentation

## Thank You

Your contributions are greatly appreciated! By following these guidelines, you help maintain the quality and consistency of the project.
