# Providers Module

The providers module implements various language model providers for the AgentConnect framework. It uses a factory pattern to create provider instances based on the desired model provider.

## Structure

```
providers/
├── __init__.py           # Package initialization and API exports
├── base_provider.py      # Abstract base class for all providers
├── provider_factory.py   # Factory for creating provider instances
├── openai_provider.py    # OpenAI provider implementation
├── anthropic_provider.py # Anthropic provider implementation
├── groq_provider.py      # Groq provider implementation
├── google_provider.py    # Google provider implementation
└── README.md             # This file
```

## Key Components

### BaseProvider (`base_provider.py`)

The `BaseProvider` class is an abstract base class that defines the interface for all model providers. It provides:

- **Message Formatting**: Converting dictionary messages to LangChain message objects
- **Response Generation**: Generating responses from language models
- **LangChain Integration**: Creating LangChain chat model instances

Key methods:
- `generate_response()`: Generate a response from the language model
- `get_available_models()`: Get a list of available models for the provider
- `get_langchain_llm()`: Get a LangChain chat model instance

### ProviderFactory (`provider_factory.py`)

The `ProviderFactory` class implements the factory pattern for creating provider instances. It provides:

- **Provider Creation**: Creating provider instances based on the desired model provider
- **Provider Discovery**: Getting a list of available providers and their models

Key methods:
- `create_provider()`: Create a provider instance
- `get_available_providers()`: Get all available providers and their models

### Provider Implementations

The module includes implementations for several model providers:

- **OpenAIProvider**: Provider for OpenAI models (GPT-4o, GPT-4.5, o1)
- **AnthropicProvider**: Provider for Anthropic Claude models
- **GroqProvider**: Provider for Groq-hosted models (Llama, Mixtral, Gemma)
- **GoogleProvider**: Provider for Google Gemini models

## Usage Examples

### Creating a Provider

```python
from agentconnect.core import ModelProvider
from agentconnect.providers import ProviderFactory

# Create an OpenAI provider
openai_provider = ProviderFactory.create_provider(
    provider_type=ModelProvider.OPENAI,
    api_key="your-openai-api-key"
)

# Create an Anthropic provider
anthropic_provider = ProviderFactory.create_provider(
    provider_type=ModelProvider.ANTHROPIC,
    api_key="your-anthropic-api-key"
)
```

### Generating Responses

```python
from agentconnect.core import ModelName

# Define messages
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Tell me about the solar system."}
]

# Generate a response using OpenAI
response = await openai_provider.generate_response(
    messages=messages,
    model=ModelName.GPT4O
)

# Generate a response using Anthropic
response = await anthropic_provider.generate_response(
    messages=messages,
    model=ModelName.CLAUDE_3_SONNET
)
```

### Getting Available Models

```python
# Get available OpenAI models
openai_models = openai_provider.get_available_models()

# Get available Anthropic models
anthropic_models = anthropic_provider.get_available_models()

# Get all available providers and their models
all_providers = ProviderFactory.get_available_providers()
```

## Integration with LangChain

The providers module is designed to work seamlessly with LangChain for model integration:

1. **LangChain Chat Models**: Each provider creates LangChain chat model instances
2. **Message Formatting**: Messages are formatted for LangChain compatibility
3. **Callback Support**: Callbacks are passed through to LangChain for monitoring

## Best Practices

When working with the providers module:

1. **Use the Factory**: Always use the `ProviderFactory` to create provider instances
2. **Handle Errors**: Always handle exceptions from `generate_response()`
3. **Use Environment Variables**: Store API keys in environment variables
4. **Use Type Hints**: Use type hints for better IDE support
5. **Use Absolute Imports**: Always use absolute imports for clarity
6. **Document Your Code**: Add comprehensive docstrings to all classes and methods
7. **Test with Multiple Providers**: Test your code with multiple providers for compatibility
8. **Use Default Models**: Use the default models unless you need a specific model
9. **Pass Callbacks**: Pass callbacks to `generate_response()` for monitoring
10. **Use Async**: Use async/await for better performance 