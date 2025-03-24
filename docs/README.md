# AgentConnect Documentation

This directory contains the documentation for the AgentConnect project. The documentation is built using [Sphinx](https://www.sphinx-doc.org/), which automatically generates API documentation from docstrings in the code.

## Documentation Structure

- `source/`: Contains the source files for the documentation
  - `api/`: Auto-generated API documentation
  - `guides/`: User guides
  - `examples/`: Example code and usage
  - `conf.py`: Sphinx configuration
  - `index.rst`: Main index file
- `build/`: Contains the built documentation (generated)
- `generate_docs.py`: Script to automate documentation generation
- `check_docstrings.py`: Script to check for missing docstrings
- `generate_docstring_template.py`: Script to generate templates for missing docstrings
- `doc_coverage.py`: Script to generate documentation coverage reports
- `Makefile` and `make.bat`: Standard Sphinx build scripts

## Getting Started

### Installation

Before using the documentation tools, you need to install the required Python packages using Poetry:

```bash
# Install documentation dependencies
poetry install --with docs
# or
make install-docs
```

## Automated Documentation Generation

We've set up several tools to automate the documentation process:

### Using Make

The simplest way to build the documentation is using Make:

```bash
# Generate HTML documentation
make docs
# or
make docs-html

# Clean existing docs before generating
make docs-clean

# Check docstring coverage
make docs-coverage
```

### Python Scripts

For more fine-grained control, you can use the Python scripts directly:

```bash
# Generate API docs and build HTML documentation
poetry run python docs/generate_docs.py

# Check for missing docstrings
poetry run python docs/check_docstrings.py

# Generate templates for missing docstrings
poetry run python docs/generate_docstring_template.py missing_docstrings.txt --output docstring_templates.txt

# Generate documentation coverage report
poetry run python docs/doc_coverage.py
```

### Pre-commit Hooks

We use pre-commit hooks to ensure documentation quality:

1. The `check-docstrings` hook checks that all public functions, classes, and methods have docstrings.
2. The `check-docs` hook ensures that the documentation builds successfully.

These hooks are automatically installed when you run:

```bash
poetry run pre-commit install
# or
make install-hooks
```

### GitHub Actions

Documentation is automatically built and deployed to GitHub Pages when changes are pushed to the main branch. You can view the latest documentation at: `https://akki0511.github.io/AgentConnect/`

## Writing Documentation

### Code Documentation

Document your code using Google-style docstrings:

```python
def my_function(param1, param2):
    """Short description of the function.
    
    Longer description explaining what the function does, its behavior,
    and any important details.
    
    Args:
        param1 (type): Description of param1
        param2 (type): Description of param2
        
    Returns:
        return_type: Description of the return value
        
    Raises:
        ExceptionType: When and why this exception is raised
        
    Examples:
        >>> my_function(1, 2)
        3
    """
    return param1 + param2
```

### Adding New Pages

1. Create a new `.rst` or `.md` file in the appropriate directory
2. Add the file to the appropriate toctree in `index.rst` or another parent document

## Building Documentation Manually

If you prefer to use the standard Sphinx commands:

```bash
# On Linux/macOS
cd docs
make html

# On Windows
cd docs
.\make.bat html
``` 