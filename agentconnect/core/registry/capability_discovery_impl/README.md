# AgentConnect Capability Discovery System

## Overview

The Capability Discovery System enables intelligent discovery of agents within AgentConnect based on natural language descriptions of desired capabilities. The system uses semantic search with vector embeddings to match queries against agent profiles, capabilities, and skills.

## Key Features

- **Semantic Search**: Find agents based on natural language queries, not just exact capability names
- **Filtering**: Apply metadata filters to narrow search results (tags, I/O modes, auth schemes, etc.)
- **Fallback Mechanisms**: Graceful degradation to simpler search methods when advanced features unavailable
- **Performance Optimizations**: Efficient indexing, batched operations, and vector storage optimizations
- **Robustness**: Extensive error handling and fallback mechanisms throughout

## Architecture

### Core Components

1. **Embedding Generation** (`embedding_utils.py`)
   - Transforms text into vector representations using pre-trained language models
   - Provides fallback similarity calculations when embedding models unavailable
   - Multiple initialization paths for embedding models with progressive fallbacks

2. **Vector Storage** (`qdrant_client.py`)
   - Manages Qdrant vector database connections (in-memory, local file, or remote)
   - Configures optimized vector collections with HNSW indexing and quantization
   - Handles efficient point deletion and payload indexing

3. **Indexing Logic** (`indexing.py`)
   - Processes agent registrations into rich text representations
   - Creates embeddings for agent profiles, capabilities, and skills
   - Implements batched updates for performance optimization
   - Uses deterministic hashing for consistent ID generation

4. **Search Functionality** (`search.py`)
   - Provides hybrid search combining vector similarity with metadata filtering
   - Supports both simple string-based capability lookup and semantic search
   - Implements fallback search methods when vector search unavailable
   - Handles result deduplication and scoring

## Data Flow

1. **Registration**: Agent registrations are processed to extract textual descriptions
2. **Embedding**: Text descriptions are converted to vector embeddings
3. **Indexing**: Embeddings and metadata are stored in Qdrant with optimized structure
4. **Query Processing**: Search queries are embedded and matched against stored vectors
5. **Result Filtering**: Optional metadata filters are applied to narrow results
6. **Scoring & Ranking**: Results are scored by similarity and returned in ranked order

## Implementation Details

### Embedding Process

For each registered agent, the system generates and indexes multiple vector embeddings:

1. **Agent Profile**: Combined embedding of name, summary, description, capabilities, skills, tags, etc.
2. **Individual Capabilities**: Separate embeddings for each capability (name + description)
3. **Individual Skills**: Separate embeddings for each skill (name + description)

This multi-vector approach allows queries to match relevant information whether it appears in the overall profile, a specific capability, or a skill description.

### Payload Structure

Each indexed point includes a rich payload with metadata for filtering:

```python
# Example agent profile payload
{
    "agent_id": "agent123",
    "name": "Translation Agent",
    "summary": "Translates between multiple languages",
    "organization": "LangTech Inc",
    "developer": "John Smith",
    "tags": ["translation", "nlp"],
    "auth_schemes": ["OAuth2"],
    "default_input_modes": ["text"],
    "default_output_modes": ["text"],
    "payment_address": "0x1234...",
    "doc_id": "agent123_profile",
    "doc_type": "agent_profile"
}
```

### Search Implementation

The system supports multiple search approaches:

1. **Exact Capability Name Matching**: Direct lookup by capability name
2. **Semantic Vector Search**: Finding semantically similar capabilities via vector embeddings
3. **Hybrid Search**: Combining vector similarity with metadata filters
4. **Fallback Text Search**: Using Jaccard similarity when vector search unavailable

### Qdrant Configuration

The vector database is optimized for both performance and efficiency:

- **Vector Quantization**: INT8 scalar quantization for 4x storage reduction
- **HNSW Index**: Optimized for search speed with tunable accuracy parameters
- **Payload Indexing**: Dedicated indexes for frequently filtered fields
- **Multiple Deployment Options**: In-memory, local file-based, or remote server

## Usage

### Basic Usage via Service

The main entry point is the `CapabilityDiscoveryService` class in [Capability Discovery](../capability_discovery.py):

```python
# Example usage
discovery_service = CapabilityDiscoveryService()
matching_agents = await discovery_service.find_by_capability_semantic(
    capability_description="translate English to French",
    limit=5,
    filters={"tags": ["translation"], "default_input_modes": ["text"]}
)
```

### Advanced Configuration

The system can be configured with custom embedding models and Qdrant parameters through a flat configuration dictionary:

```python
config = {
    # Embedding model configuration
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",  # Default: all-mpnet-base-v2
    "cache_folder": "./.cache/huggingface/embeddings",
    
    # Qdrant connection options (choose one)
    "in_memory": True,
    # "path": "./local_qdrant",  # Local file-based storage
    # "url": "http://qdrant.example.com",  # Remote server
    # "host": "localhost",  # Alternative to URL
    # "port": 6333,
    # "api_key": "your-api-key",
    
    # Qdrant collection options
    "use_quantization": True,  # Use INT8 quantization (4x storage reduction)
    "vectors_on_disk": False,  # Keep vectors in memory for speed
    "index_on_disk": False,    # Keep index in memory for speed
    "batch_size": 100          # Batch size for indexing operations
}

discovery_service = CapabilityDiscoveryService(vector_store_config=config)
```

## Performance Optimization Techniques

1. **Payload Compression**: Scalar quantization reduces storage by 4x with <1% accuracy loss
2. **Batched Updates**: Uses configurable batch sizes (default 100) for faster indexing
3. **Optimized HNSW Index**: Configured for speed while maintaining accuracy
4. **Payload Indexes**: Created on frequently filtered fields for faster queries
5. **Deterministic IDs**: Generating consistent IDs enables efficient updates

## Dependencies

The system has several dependencies with graceful degradation:

- **Basic Requirements**: `langchain-core`, `numpy`
- **Embedding Model**: `langchain-huggingface`, `sentence-transformers`
- **Vector Store**: `qdrant-client`

The system will automatically detect available dependencies and adjust functionality accordingly.

## Development and Testing

Each module includes self-contained test functions that can be run directly:

```python
# Example test for indexing
python -c "from agentconnect.core.registry.capability_discovery_impl.indexing import main; import asyncio; asyncio.run(main())"
```

## Future Enhancements

Potential areas for future improvement:

1. **Cross-lingual Search**: Support for matching capabilities across languages
2. **Dynamic Reranking**: Additional post-search reranking based on relevance signals
3. **Contextual Search**: Incorporating conversational context into search queries
4. **Result Diversification**: Ensuring diverse results for broader queries 