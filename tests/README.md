# AgentConnect Tests

Tests have been temporarily disabled while the codebase is being actively developed.

This directory is kept for future test implementation and to maintain compatibility with CI pipelines.

## Running Tests

The `make test` command will succeed but not run any tests, as they have been disabled.

## Adding Tests

When adding tests in the future, place them in this directory with the following structure:

```
tests/
  test_*.py        # Test files (match test_*.py)
```

## CI Pipeline

The CI pipeline is configured to skip test execution if no test files are present.
