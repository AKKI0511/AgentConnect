"""
Telegram Agent implementation for the AgentConnect framework.

This module provides a Telegram bot interface for AgentConnect, allowing users to
interact with an AI agent through Telegram. The implementation supports both direct Telegram
user interactions and AgentConnect inter-agent collaborations.

Key components:

- **TelegramAIAgent**: Main agent class that extends AIAgent to provide Telegram integration
- **TelegramBotManager**: (Internal) Manages the Telegram bot lifecycle
- **TelegramMessageProcessor**: (Internal) Processes messages between Telegram and AgentConnect

The agent can handle:
- Direct messaging through Telegram private chats
- Group chat interactions via mentions
- Media messages (photos, documents, voice messages, etc.)
- Inter-agent collaboration requests from other agents in the AgentConnect ecosystem

Example:
    .. code-block:: python

        from agentconnect.agents.telegram import TelegramAIAgent
        from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName

        # Create the agent
        agent = TelegramAIAgent(
            agent_id="telegram_bot",
            name="My Telegram Bot",
            provider_type=ModelProvider.GOOGLE,
            model_name=ModelName.GEMINI2_FLASH,
            api_key="your_api_key",
            identity=AgentIdentity.create_key_based(),
            telegram_token="your_telegram_token"
        )

        # Run the agent
        await agent.run()
"""

from agentconnect.agents.telegram.telegram_agent import TelegramAIAgent

__all__ = ["TelegramAIAgent"]
