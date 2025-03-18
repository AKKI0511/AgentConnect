# Developer Guidelines for AgentConnect

As a developer working on the AgentConnect project, here's what you need to keep in mind when making code changes to ensure everything stays in sync and documentation remains up-to-date:

## Documentation Workflow

When you modify code in the AgentConnect project, follow these steps to maintain proper documentation:

### 1. Add Proper Docstrings

Always add Google-style docstrings to any new classes, methods, or functions you create. This is crucial because:

- The automated documentation system extracts these docstrings to generate the API reference
- The docstring checker will flag missing docstrings
- Well-documented code is easier for other developers to understand and use

Example of a good docstring:

```python
def connect_agents(agent1, agent2, protocol=None):
    """Connect two agents to enable communication between them.
    
    This function establishes a communication channel between two agents
    using the specified protocol or a default protocol if none is provided.
    
    Args:
        agent1 (Agent): The first agent to connect
        agent2 (Agent): The second agent to connect
        protocol (Protocol, optional): Communication protocol to use
        
    Returns:
        Connection: A connection object representing the established channel
        
    Raises:
        ConnectionError: If the connection cannot be established
    """
```

### 2. Run the Documentation Tools

After making changes, run the documentation tools to ensure everything is up-to-date:

```bash
# Using Make commands (recommended)
make docs-clean      # Clean existing documentation
make docs            # Generate documentation
make docs-coverage   # Generate documentation coverage report

# Or run individual Python scripts directly
poetry run python docs/check_docstrings.py
poetry run python docs/doc_coverage.py
poetry run python docs/generate_docs.py
```

This will:
- Check for missing docstrings
- Create a documentation coverage report
- Rebuild the documentation

### 3. Fix Missing Docstrings

If the docstring checker finds missing docstrings:

1. Review the `missing_docstrings.txt` file
2. Use the `generate_docstring_template.py` script to create templates:
   ```bash
   poetry run python docs/generate_docstring_template.py missing_docstrings.txt --output docstring_templates.txt
   ```
3. Add the missing docstrings to your code
4. Run the documentation tools again to verify all docstrings are now present

### 4. Review Documentation Coverage

Check the documentation coverage report (`coverage/doc_coverage_report.html`) to ensure your changes maintain or improve the documentation coverage. Pay special attention to:

- Overall coverage percentage
- Coverage for specific modules you've modified
- Any undocumented items in your code

### 5. Test the Generated Documentation

After rebuilding the documentation, open the HTML documentation in your browser to ensure:

- Your changes appear correctly in the API reference
- Cross-references work properly
- Examples are clear and accurate

## Git Workflow

The project includes Git hooks to help maintain documentation quality:

1. When you commit changes, the pre-commit hook will check if you've modified Python files
2. If you have, it will remind you to update the documentation
3. You can choose to continue with the commit or abort to update the documentation first

For best results:

- Install the Git hooks using `make install-hooks`
- Update documentation before committing code changes
- Include documentation updates in the same commit as code changes when possible

## Continuous Integration

Remember that the GitHub Actions workflow will:

1. Build the documentation automatically when changes are pushed to the main branch
2. Deploy the documentation to GitHub Pages
3. Fail if there are errors in the documentation build process

To avoid CI failures:
- Always run the documentation tools locally before pushing changes
- Fix any documentation issues before pushing to the main branch

## Best Practices

1. **Document as you code**: Write docstrings while implementing features, not after
2. **Be comprehensive**: Document all parameters, return values, and exceptions
3. **Include examples**: Practical examples help users understand how to use your code
4. **Keep docstrings updated**: When you change function signatures or behavior, update the docstrings
5. **Run the full documentation workflow regularly**: This ensures you catch any issues early

By following these guidelines, you'll help maintain high-quality documentation for the AgentConnect project, making it more accessible and easier to use for everyone.


# Visually Checking Your Documentation Before Committing

You have several options to visually check your documentation before committing changes to ensure everything looks correct:

## Option 1: Use Make Commands

The simplest approach is to use the Make commands we've created:

```bash
# Clean and generate documentation
make docs-clean
make docs
```

Then open the generated documentation in your browser:
```bash
# On Windows
start docs\build\html\index.html

# On macOS
open docs/build/html/index.html

# On Linux
xdg-open docs/build/html/index.html
```

## Option 2: Build and Open Manually

If you prefer more control over the process:

1. Build the documentation:
   ```bash
   # From the project root
   poetry run python docs/generate_docs.py
   ```

2. Open the generated HTML in your browser:
   ```bash
   # On Windows
   start docs\build\html\index.html
   
   # On macOS
   open docs/build/html/index.html
   
   # On Linux
   xdg-open docs/build/html/index.html
   ```

## Option 3: Check Documentation Coverage First

Before building the full documentation, you might want to check the documentation coverage:

1. Generate a documentation coverage report:
   ```bash
   make docs-coverage
   # or
   poetry run python docs/doc_coverage.py
   ```

2. Open the coverage report to see which parts of your code need better documentation:
   ```bash
   # On Windows
   start coverage/doc_coverage_report.html
   
   # On macOS
   open coverage/doc_coverage_report.html
   
   # On Linux
   xdg-open coverage/doc_coverage_report.html
   ```

3. After addressing any issues, build and check the full documentation

## What to Look For When Reviewing Documentation

When visually inspecting your documentation, check for:

1. **Completeness**: Are all your modules, classes, and functions properly documented?
2. **Formatting**: Do code examples, parameter lists, and return values display correctly?
3. **Navigation**: Can you easily navigate between related components?
4. **Cross-references**: Do links to other parts of the documentation work?
5. **Examples**: Are the examples clear and do they demonstrate proper usage?
6. **Type hints**: Are parameter and return types displayed correctly?

## Checking Specific Changes

If you've only modified a specific part of the codebase, you can focus your review on those sections:

1. Build the documentation:
   ```bash
   make docs
   # or
   poetry run python docs/generate_docs.py
   ```

2. Navigate directly to the relevant module in the HTML documentation:
   ```
   docs/build/html/api/agentconnect.<your_module>.html
   ```

## Checking Documentation Before Pushing to GitHub

Remember that GitHub Actions will automatically build and deploy your documentation when you push to the main branch. To preview how it will look on GitHub Pages:

1. Run the full documentation workflow:
   ```bash
   make docs-clean
   make docs
   make docs-coverage
   ```

2. Check the HTML output in `docs/build/html/` to ensure it will display correctly when deployed

By visually checking your documentation before committing, you can catch and fix issues early, ensuring that the published documentation is always accurate and helpful.
