# AgentConnect Tests

## Running Tests

Use `make test` to run all tests.

## Adding Tests

When adding tests, place them in this directory with the following structure:

```
tests/
  test_*.py        # Test files (match test_*.py)
```

## Tests available

- Refer to [Registry Tests](./core/registry/README.md) for tests related to the registry and Qdrant vector database.
- To understand the system prompt for an `AIAgent`, run `python tests/check_react_prompt.py`
- To test the `HumanAgent` and `AIAgent` usage, run tests from `tests/agents/`