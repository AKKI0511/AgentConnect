# Contributing to AgentConnect

Thank you for your interest in contributing to AgentConnect! We aim to make this project a welcoming space for collaboration and improvement.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
  - [Development Environment](#development-environment)
  - [First Time Setup](#first-time-setup)
- [Development Workflow](#development-workflow)
  - [Creating a Feature](#creating-a-feature)
  - [CI/CD Workflows](#ci-cd-workflows)
  - [Code Style](#code-style)
  - [Testing](#testing)
  - [Documentation](#documentation)
  - [Git Hooks](#git-hooks)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Development Environment

Required tools:
- Python 3.11 or higher
- Poetry (Python package manager)
- Git
- A code editor (VS Code recommended)
- Make (optional, for using Makefile commands)

### First Time Setup

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/AKKI0511/AgentConnect.git
   cd AgentConnect
   ```

3. Set up your development environment:
   ```bash
   # Install Poetry if you haven't already
   curl -sSL https://install.python-poetry.org | python3 -

   # Install dependencies
   poetry install --with dev,demo

   # Install pre-commit hooks
   poetry run pre-commit install
   # or
   make install-hooks
   ```

4. Create a branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Creating a Feature

1. Update your main branch:
   ```bash
   git checkout main
   git pull upstream main
   ```

2. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. Make your changes:
   - Write tests for new functionality
   - Update documentation as needed
   - Follow the code style guidelines

4. Commit your changes:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

### CI/CD Workflows

AgentConnect uses GitHub Actions for continuous integration and deployment:

1. **CI Workflow (`main.yml`)**:
   - Triggered on pushes to main and pull requests
   - Runs on Ubuntu with Python 3.11 and 3.12
   - Sets up Redis for testing
   - Installs dependencies using Poetry
   - Runs linting with flake8
   - Checks code formatting with black
   - Runs tests with pytest
   - Fails fast if any step fails

2. **Documentation Workflow (`docs.yml`)**:
   - Triggered on pushes to main and pull requests that modify documentation
   - Builds documentation using Sphinx
   - Deploys to GitHub Pages when merged to main
   - Documentation is available at: https://akki0511.github.io/AgentConnect/

When you submit a pull request, these workflows will automatically run to verify your changes. Make sure all checks pass before requesting a review.

### Code Style

We use several tools to maintain code quality:

1. Recommended: Use the Makefile for common development tasks:
   ```powershell
   # Format code, run linting, and tests
   make all

   # Run only linting
   make lint

   # Format code
   make format

   # Run tests
   make test

   # Run tests with coverage
   make coverage
   ```

2. Black for code formatting:
   ```powershell
   poetry run black .
   ```

3. Flake8 for style guide enforcement:
   ```powershell
   poetry run flake8
   ```

4. Pylint for code analysis:
   ```powershell
   poetry run pylint agentconnect/ tests/ demos/
   ```

5. Type hints are required for all functions:
   ```python
   def example_function(param1: str, param2: int) -> bool:
       return True
   ```

### Git Hooks

We use pre-commit to automate code quality checks before each commit. The hooks will:

- Format code with Black
- Sort imports with isort
- Check for common issues with flake8
- Ensure documentation is up-to-date

To install the hooks:

```bash
# Install pre-commit hooks
poetry run pre-commit install
# or
make install-hooks
```

To manually run all hooks on all files:

```bash
poetry run pre-commit run --all-files
# or
make hooks
```

> **Note**: The `demos/` directory is excluded from pre-commit checks as it contains standalone demo applications that follow different coding standards.

### Testing

1. Write tests for your changes:
   ```python
   # tests/test_your_feature.py
   def test_your_feature():
       result = your_feature()
       assert result == expected_value
   ```

2. Run the test suite:
   ```bash
   poetry run pytest
   ```

### Documentation

1. Update docstrings for any new code:
   ```python
   def your_function(param1: str, param2: int) -> bool:
       """
       Brief description of function.

       Args:
           param1: Description of param1
           param2: Description of param2

       Returns:
           bool: Description of return value

       Raises:
           ValueError: Description of when this error occurs
       """
       return True
   ```

2. Update README.md if you've added new features
3. Add examples to the examples/ directory
4. Update API documentation if needed

## Pull Request Process

1. Update the README.md with details of major changes
2. Update the CHANGELOG.md following the Keep a Changelog format
3. Ensure all tests pass and code style checks succeed
4. Submit the PR with a clear title and description
5. Wait for review and address any feedback

Example PR description:
```markdown
## Description
Brief description of your changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe how you tested your changes

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Code follows style guidelines
- [ ] CHANGELOG.md updated
```

## Community

- Join our [Discord server](https://discord.gg/agentconnect)
- Follow us on [Twitter](https://twitter.com/agentconnect)
- Subscribe to our [newsletter](https://agentconnect.dev/newsletter)

## Additional Resources

- [Python Style Guide (PEP 8)](https://peps.python.org/pep-0008/)
- [Type Hints Guide (PEP 484)](https://peps.python.org/pep-0484/)
- [Git Commit Message Guidelines](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)

Thank you for contributing to AgentConnect!
