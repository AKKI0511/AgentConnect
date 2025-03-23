# Communication Examples

This directory contains examples demonstrating how agents communicate with each other in the AgentConnect framework.

## Available Examples

### Basic Communication

`basic_communication.py` - Demonstrates how to:
- Set up communication between multiple agents
- Use the communication hub for message routing
- Implement different communication protocols
- Handle message verification and security

## Running Examples

To run these examples:

```bash
# Install dependencies
poetry install

# Run the basic communication example
python examples/communication/basic_communication.py
```

## Creating Your Own Communication Examples

When creating your own communication examples, consider:

1. **Communication Patterns**: Demonstrate different patterns (one-to-one, broadcast, etc.)
2. **Protocol Implementation**: Show how to implement custom communication protocols
3. **Security Measures**: Include examples of secure communication
4. **Error Handling**: Demonstrate handling of communication failures 

## Example Template

```python
import asyncio
import logging
from src.core.registry import AgentRegistry
from src.communication.hub import CommunicationHub
from src.agents.ai_agent import AIAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("YourExample")

async def main():
    # Create registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    try:
        # Create and register agents
        # ...
        
        # Your example code here
        # ...
        
    except Exception as e:
        logger.exception(f"Error in example: {str(e)}")
    finally:
        # Clean up
        # Unregister agents
        # ...
        
        logger.info("Example completed")

if __name__ == "__main__":
    asyncio.run(main()) 

```