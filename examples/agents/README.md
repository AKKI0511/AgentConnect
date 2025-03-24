# Agent Examples

This directory contains examples demonstrating how to create and use different types of agents in the AgentConnect framework.

## Available Examples

### Basic Agent Usage

`basic_agent_usage.py` - Demonstrates how to:
- Create an AI agent with different providers (OpenAI, Anthropic, etc.)
- Send messages to an agent and receive responses
- Configure agent parameters
- Handle agent state and memory

## Running Examples

To run these examples:

```bash
# Install dependencies
poetry install

# Run the basic agent example
python examples/agents/basic_agent_usage.py
```

## Creating Your Own Agent Examples

When creating your own agent examples, consider:

1. **Provider Configuration**: Show how to configure different AI providers
2. **Agent Capabilities**: Demonstrate specific agent capabilities
3. **Error Handling**: Include proper error handling for API calls
4. **Environment Variables**: Use environment variables for API keys

## Example Template

```python
import asyncio
import logging
import os
from dotenv import load_dotenv

from src.agents.ai_agent import AIAgent
from src.core.types import ModelProvider, ModelName, AgentIdentity

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("YourExample")

async def main():
    try:
        # Create your agents
        # ...

        # Your example code here
        # ...

    except Exception as e:
        logger.exception(f"Error in example: {str(e)}")
    finally:
        # Clean up
        # ...

        logger.info("Example completed")

if __name__ == "__main__":
    asyncio.run(main())

```
