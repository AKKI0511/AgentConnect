# Capability Discovery Tests

This directory contains comprehensive tests for the AgentConnect Capability Discovery system, including its implementation details and end-to-end functionality.

## Test Files

- **test_capability_discovery_e2e.py**: End-to-end tests for the capability discovery system, testing the main interface and API.
- **test_capability_discovery_impl.py**: Unit tests for the internal implementation components of the capability discovery system.

## Test Coverage

These tests cover the following aspects of the capability discovery system:

### Embedding Utilities
- Similarity calculation (Jaccard and cosine similarity)
- Embedding model initialization and usage
- Requirement checking for semantic search

### Qdrant Client Operations
- Client initialization and configuration
- Collection management (creation, configuration)
- Snapshot operations (save and load)
- Point operations (adding, querying, deleting)

### Search Functionality
- String-based matching for capabilities
- Semantic search with embedding-based matching
- Fallback mechanisms between search methods
- Filtering by organization and developer

### Indexing Operations
- Capability index extraction
- Embedding generation and storage for capabilities
- Updating capability embeddings for agents
- Vector store persistence

### End-to-End Workflows
- Register agents with various capabilities
- Search for agents by capability name
- Search for agents semantically by capability description
- Update agent capabilities and see changes reflected in search
- Persist and restore the vector store
- Remove agents and verify they are not returned in search results

## Prerequisites

To run these tests, you need the following dependencies installed:

```bash
pip install pytest langchain-core langchain-huggingface sentence-transformers qdrant-client
```

For full functionality, make sure you have the necessary embedding models available. The tests will use smaller models for faster execution, but they still require downloading the models.

## Running the Tests

You can run the tests using the provided test runner script:

```bash
python tests/run_capability_discovery_tests.py
```

This script will run both the implementation and end-to-end tests with colorized output for better visualization.

### Command-line Options

The test runner supports the following options:

- `--impl`: Run only the implementation tests
- `--e2e`: Run only the end-to-end tests
- `--all`: Run all tests (default if no option is specified)
- `--quiet`: Suppress test output except for errors

Examples:

```bash
# Run only implementation tests
python tests/run_capability_discovery_tests.py --impl

# Run only end-to-end tests
python tests/run_capability_discovery_tests.py --e2e

# Run all tests with minimal output
python tests/run_capability_discovery_tests.py --all --quiet
```

## Test Output

The tests provide colorized output to help visualize what's happening:

- 🟣 **Purple headers**: Test section titles and major steps
- 🔵 **Blue steps**: Individual test steps being executed
- 🟢 **Green checkmarks**: Successful test assertions
- 🟡 **Yellow warnings**: Non-critical issues or skipped tests
- 🔴 **Red errors**: Test failures or critical issues

For semantic search results, the output will show:
- Agent name and ID
- Similarity score with color coding (higher is better)
- Brief description of the agent's capabilities

## Test Skipping

Some tests automatically skip when requirements aren't met:

- Tests requiring Qdrant will be skipped if Qdrant client isn't available
- Tests requiring embedding models will be skipped if models aren't available
- Complex tests will skip dependency checks when prerequisites fail

## Notes on Test Design

1. **In-memory testing**: All Qdrant operations use in-memory databases for fast testing without external dependencies.
2. **Visual feedback**: Tests are designed to show what's happening visually to aid in understanding the system.
3. **Conditional execution**: Tests adapt to available components, allowing partial testing based on installed libraries.
4. **Cleanup**: All tests clean up after themselves to prevent contamination between test runs.

## Troubleshooting

If you encounter issues running the tests:

1. **Missing dependencies**: Ensure all required Python packages are installed
2. **Model download issues**: Check internet connectivity as models need to be downloaded
3. **Path issues**: Make sure you run the tests from the project root directory
4. **Memory issues**: For large tests, ensure you have enough system memory available 