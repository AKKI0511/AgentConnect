Telegram Integration
===================

This guide walks you through setting up and using the Telegram agent in your AgentConnect applications.
The Telegram agent allows users to interact with your AI system through the Telegram messaging platform,
providing both direct chat interfaces and group chat capabilities.

Prerequisites
------------

Before you begin integrating the Telegram agent, ensure you have:

1. Installed AgentConnect with the required dependencies
2. A Telegram account
3. API keys for your preferred LLM provider (Google, OpenAI, Anthropic, or Groq)

Creating a Telegram Bot
-----------------------

To use the Telegram integration, you first need to create a bot through Telegram's BotFather:

1. Open Telegram and search for ``@BotFather``
2. Start a chat with BotFather and use the ``/newbot`` command
3. Follow the prompts to create your bot:
   - Provide a display name for your bot (e.g., "My AgentConnect Assistant")
   - Provide a username for your bot (must end with "bot", e.g., "my_agent_connect_bot")
4. BotFather will provide a token that looks like this: ``123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ``
5. Save this token securely - you'll need it to initialize your Telegram agent

.. warning::
   Keep your bot token secure! Anyone with this token can control your bot.
   Never commit it directly in your code. Use environment variables or secure storage.

Basic Telegram Agent Setup
--------------------------

The simplest way to set up a Telegram agent is as follows:

.. code-block:: python

    import os
    import asyncio
    from dotenv import load_dotenv
    
    from agentconnect.agents.telegram import TelegramAIAgent
    from agentconnect.core.types import AgentIdentity, ModelProvider, ModelName
    from agentconnect.core.registry import AgentRegistry
    from agentconnect.communication.hub import CommunicationHub
    
    # Load environment variables (assuming you've stored your tokens in a .env file)
    load_dotenv()
    
    async def main():
        # Create agent registry and communication hub
        registry = AgentRegistry()
        hub = CommunicationHub(registry)
        
        # Create Telegram agent
        agent = TelegramAIAgent(
            agent_id="telegram_assistant",
            name="My Telegram Assistant",
            provider_type=ModelProvider.GOOGLE,  # Or your preferred provider
            model_name=ModelName.GEMINI2_FLASH,  # Or your preferred model
            api_key=os.getenv("GOOGLE_API_KEY"),  # Your API key
            identity=AgentIdentity.create_key_based(),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN")  # Your Telegram token
        )
        
        # Register agent with the hub
        await hub.register_agent(agent)
        
        # Start the agent
        try:
            await agent.run()
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            # Clean shutdown
            await agent.stop_telegram_bot()
            await hub.unregister_agent(agent.agent_id)
    
    if __name__ == "__main__":
        asyncio.run(main())

Save this code in a file (e.g., ``telegram_bot.py``) and run it. Your bot should now be active on Telegram.

Environment Variables
--------------------

For security, store your API keys and tokens in a ``.env`` file:

.. code-block:: text

    # Telegram Bot Token
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    
    # LLM Provider API Key (choose one)
    GOOGLE_API_KEY=your_google_api_key
    # OR
    OPENAI_API_KEY=your_openai_api_key
    # OR
    ANTHROPIC_API_KEY=your_anthropic_api_key
    # OR
    GROQ_API_KEY=your_groq_api_key

Advanced Configuration
---------------------

The TelegramAIAgent supports various configuration options:

.. code-block:: python

    agent = TelegramAIAgent(
        agent_id="telegram_assistant",
        name="My Telegram Assistant",
        provider_type=ModelProvider.GOOGLE,
        model_name=ModelName.GEMINI2_FLASH,
        api_key=os.getenv("GOOGLE_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        # Additional options
        personality="helpful, friendly, and concise",
        organization_id="my_organization",
        groups_file="groups.txt",  # File to store registered group IDs
        max_tokens_per_minute=5500,  # Rate limiting
        max_tokens_per_hour=100000,  # Rate limiting
        capabilities=[...]  # Custom capabilities beyond defaults
    )

Interacting with Your Telegram Agent
------------------------------------

Once your agent is running, you can interact with it in several ways:

Private Chat
~~~~~~~~~~~

1. Open Telegram and search for your bot's username
2. Start a chat with your bot
3. Send the ``/start`` command to initialize the bot
4. Send messages directly to your bot, which will respond using the configured LLM

Group Chat
~~~~~~~~~

1. Add your bot to a Telegram group
2. Send the ``/start`` command in the group to register it
3. Mention your bot (e.g., ``@my_agent_connect_bot what's the weather today?``) to interact with it

The bot will only respond in groups when explicitly mentioned or when a message is directly replied to.

Bot Commands
~~~~~~~~~~~

The Telegram agent comes with several built-in commands:

- ``/start`` - Initialize the bot or get a welcome message
- ``/help`` - Display help information about the bot's capabilities
- ``/about`` - Show information about the bot and AgentConnect

You can customize these commands or add new ones by modifying the handler methods in your agent.

Media Handling
-------------

The Telegram agent can process various types of media:

- **Photos**: Send images to the bot for processing or description
- **Documents**: Send files for the bot to analyze (PDF, text, etc.)
- **Voice Messages**: Send voice recordings that the bot can process
- **Location Data**: Share locations with the bot

Here's an example of how the agent processes media:

1. User sends a photo to the bot
2. TelegramAIAgent downloads and processes the image
3. The agent's LLM receives context about the image
4. The agent responds with information about the image content

Integration with Other Agents
----------------------------

One of the most powerful features of the TelegramAIAgent is its ability to collaborate with other agents:

.. code-block:: python

    # Set up multiple agents
    telegram_agent = TelegramAIAgent(...)
    
    research_agent = AIAgent(
        agent_id="research_agent",
        name="Research Specialist",
        provider_type=ModelProvider.ANTHROPIC,
        model_name=ModelName.CLAUDE_3_OPUS,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        capabilities=[
            Capability(
                name="web_research",
                description="Can perform detailed web research on any topic",
                input_schema={"topic": "string"},
                output_schema={"findings": "string", "sources": "list"}
            )
        ]
    )
    
    data_visualization_agent = AIAgent(
        agent_id="viz_agent",
        name="Visualization Expert",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4_VISION,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=AgentIdentity.create_key_based(),
        capabilities=[
            Capability(
                name="data_visualization",
                description="Creates charts and visualizations from data",
                input_schema={"data": "string", "chart_type": "string"},
                output_schema={"image_path": "string", "description": "string"}
            )
        ]
    )
    
    # Register all agents
    await hub.register_agent(telegram_agent)
    await hub.register_agent(research_agent)
    await hub.register_agent(data_visualization_agent)
    
    # Start all agents
    asyncio.create_task(telegram_agent.run())
    asyncio.create_task(research_agent.run())
    asyncio.create_task(data_visualization_agent.run())

With this setup, when a user interacts with the Telegram bot, a sophisticated workflow can emerge:

1. **Request Interpretation**: The Telegram agent analyzes the user's request to determine what capabilities are needed
2. **Capability Discovery**: The agent uses the registry to find other agents with the required capabilities
3. **Collaboration Request**: The agent sends requests to the appropriate specialized agents
4. **Result Integration**: The agent combines results from multiple sources into a coherent response
5. **Content Distribution**: The agent can broadcast the finalized content to multiple groups or users

For example, when a user asks:

.. code-block::

   User: Research the latest developments in quantum computing, create a visualization 
         of the major players, and send a summary to the Tech and Science groups.

The workflow might look like this:

1. Telegram agent receives the request and identifies three required capabilities:
   - Web research
   - Data visualization
   - Group messaging

2. It discovers and collaborates with the research agent to gather information on quantum computing

3. It takes the research data and requests a visualization from the visualization agent

4. It formats all the content into a comprehensive announcement with proper formatting

5. It broadcasts the announcement to the specified groups

6. The user can later edit or update the announcement through the private chat

This multi-agent collaboration happens seamlessly behind the scenes, with the Telegram agent serving as both the user interface and the orchestration layer.

Advanced Use Cases
-----------------

Dynamic Group Announcements and Broadcasting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
   **Important:** The code examples below are provided for creating a hardcoded research-to-broadcast workflow. You do not need to implement any of this code yourself. The Telegram agent already has these capabilities built-in and will handle finding agents, requesting collaboration, and broadcasting automatically based on natural language requests.

One of the most powerful features of the Telegram agent is its ability to dynamically create and broadcast announcements to multiple groups:

.. code-block:: python

    # Example of sending an announcement to all registered groups
    await telegram_agent.send_announcement_to_groups(
        text="Important announcement: System maintenance scheduled for tomorrow.",
        media_path=None,  # Optional path to media file
        parse_mode="Markdown",  # Optional formatting (Markdown or HTML)
        groups="all"  # Or list specific group IDs
    )

This capability allows for sophisticated use cases where the Telegram agent acts as a central broadcasting system. For example, users can:

1. Ask the agent to research a topic and create announcements based on the findings
2. Request the agent to format content in a visually appealing way
3. Have the agent automatically distribute content to multiple groups
4. Edit or update previously sent announcements

Here's a complete code example demonstrating a research-to-broadcast workflow:

.. code-block:: python

    async def handle_research_and_broadcast_request(telegram_agent, message_text, user_id):
        """
        Handle a request to research a topic and broadcast findings to groups.
        
        This demonstrates the full workflow from receiving a request to broadcasting
        results across multiple channels.
        """
        # Parse the user request to identify the research topic
        # For simplicity, let's assume the topic is provided directly
        research_topic = "latest trends in artificial intelligence"
        
        # Step 1: Find a research agent that can help
        research_agents = await telegram_agent.registry.find_agents_by_capability("web_research")
        if not research_agents:
            await telegram_agent.send_message(
                chat_id=user_id,
                text="I couldn't find any research agents to help with this task."
            )
            return
        
        research_agent = research_agents[0]
        
        # Step 2: Request collaboration for research
        await telegram_agent.send_message(
            chat_id=user_id,
            text=f"Researching '{research_topic}'. This may take a moment..."
        )
        
        research_response = await telegram_agent.request_collaboration(
            target_agent_id=research_agent.agent_id,
            capability_name="web_research",
            input_data={"topic": research_topic, "depth": "comprehensive"}
        )
        
        if not research_response or not research_response.get("success"):
            await telegram_agent.send_message(
                chat_id=user_id,
                text="I encountered an issue while researching. Please try again later."
            )
            return
        
        research_findings = research_response.get("data", {}).get("findings", "No findings available")
        research_sources = research_response.get("data", {}).get("sources", [])
        
        # Step 3: Create a visualization if requested
        # Find a visualization agent
        viz_agents = await telegram_agent.registry.find_agents_by_capability("data_visualization")
        viz_path = None
        
        if viz_agents:
            viz_agent = viz_agents[0]
            viz_response = await telegram_agent.request_collaboration(
                target_agent_id=viz_agent.agent_id,
                capability_name="data_visualization",
                input_data={
                    "data": research_findings,
                    "chart_type": "infographic"
                }
            )
            
            if viz_response and viz_response.get("success"):
                viz_path = viz_response.get("data", {}).get("image_path")
        
        # Step 4: Format the announcement with markdown
        formatted_announcement = f"""
        🔍 **RESEARCH FINDINGS: {research_topic.upper()}** 🔍
        
        {research_findings}
        
        **Sources:**
        """
        
        for i, source in enumerate(research_sources[:3], 1):
            formatted_announcement += f"\n{i}. {source}"
        
        # Step 5: Send a preview to the user
        await telegram_agent.send_message(
            chat_id=user_id,
            text="Here's a preview of the announcement:",
            parse_mode="Markdown"
        )
        
        if viz_path:
            await telegram_agent.send_photo(
                chat_id=user_id,
                photo=viz_path,
                caption=formatted_announcement,
                parse_mode="Markdown"
            )
        else:
            await telegram_agent.send_message(
                chat_id=user_id,
                text=formatted_announcement,
                parse_mode="Markdown"
            )
        
        # Step 6: Ask for confirmation
        await telegram_agent.send_message(
            chat_id=user_id,
            text="Should I send this announcement to all registered groups?",
            parse_mode="Markdown"
        )
        
        # In a real implementation, you'd wait for the user's response
        # For this example, we'll assume confirmation was received
        
        # Step 7: Broadcast to all groups
        result = await telegram_agent.send_announcement_to_groups(
            text=formatted_announcement,
            media_path=viz_path,
            parse_mode="Markdown",
            groups="all"
        )
        
        # Step 8: Report back to the user
        if result.get("success"):
            groups_count = len(result.get("groups", []))
            await telegram_agent.send_message(
                chat_id=user_id,
                text=f"Announcement successfully sent to {groups_count} groups.",
                parse_mode="Markdown"
            )
        else:
            await telegram_agent.send_message(
                chat_id=user_id,
                text=f"Error sending announcement: {result.get('error')}",
                parse_mode="Markdown"
            )

Here's a practical example of how a user might interact with this feature:

.. code-block::

   User: Research the latest trends on MCP and create an announcement for all registered groups. 
         Make the announcement intense and visually appealing.
   
   Bot: I'll research MCP trends and create an announcement for all groups.
        [Agent performs research, possibly collaborating with other agents]
        
   Bot: I've prepared the announcement. Here's a preview:
        
        🔥 **BREAKING: MCP MARKET TRENDS UPDATE** 🔥
        
        Our analysis shows three major developments in the MCP space:
        - 📈 20% increase in enterprise adoption this quarter
        - 🔄 New framework version releasing next month with enhanced security
        - 🌐 Growing integration with cloud infrastructure services
        
        [Chart image showing adoption trends]
        
        Would you like me to send this to all registered groups now?
   
   User: Yes, send it.
   
   Bot: Announcement successfully sent to 5 groups.

The Telegram agent can also handle media files (images, documents, videos) as part of announcements:

.. code-block:: python

    # Sending an announcement with media
    await telegram_agent.send_announcement_to_groups(
        text="Check out our latest analysis results!",
        media_path="/path/to/chart.png",
        groups="all"
    )

Editing Messages and Announcements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Users can edit previously sent messages or announcements directly through the private chat with the bot:

.. code-block::

   User: Edit the announcement I just sent to change "20% increase" to "25% increase"
   
   Bot: I'll update the announcement. Here's the edited version:
        
        🔥 **BREAKING: MCP MARKET TRENDS UPDATE** 🔥
        
        Our analysis shows three major developments in the MCP space:
        - 📈 25% increase in enterprise adoption this quarter
        - 🔄 New framework version releasing next month with enhanced security
        - 🌐 Growing integration with cloud infrastructure services
        
        [Chart image showing adoption trends]
        
        Should I apply this edit to all groups?
   
   User: Yes
   
   Bot: Announcement successfully updated in 5 groups.

This editing capability is particularly useful for:
- Correcting information in announcements
- Updating time-sensitive information
- Refining messaging based on feedback

Super Agent Capabilities
~~~~~~~~~~~~~~~~~~~~~~

The combination of these features effectively makes the Telegram agent a "super agent" that can:

1. Act as an interface between users and specialized agents in your network
2. Perform complex tasks through multi-agent collaboration
3. Broadcast results to multiple channels/groups simultaneously
4. Manage and update previously sent content
5. Handle media and formatted text for visually appealing messaging

For example, a user could request:

.. code-block::

   User: Analyze last month's sales data, create a visualization, and send a summary to the Sales and 
         Executive groups with appropriate formatting.

The Telegram agent would:

1. Parse the request to understand the required capabilities
2. Find and collaborate with a data analysis agent in the network
3. Get the analysis results and visualizations
4. Format the content appropriately for professional presentation
5. Send specifically tailored announcements to the different groups
6. Allow the user to edit or refine the messages if needed

Group Management
~~~~~~~~~~~~~~

The Telegram agent can manage group memberships and permissions. It can add or remove users from groups, and it can control access to certain capabilities within those groups.

Customizing the Telegram Agent
-----------------------------

Extending Message Handlers
~~~~~~~~~~~~~~~~~~~~~~~~

You can customize how your bot handles messages by creating custom handlers:

.. code-block:: python

    from agentconnect.agents.telegram._handlers.base_handler import BaseHandler
    
    class CustomHandler(BaseHandler):
        async def handle_custom_message(self, message):
            # Custom message handling logic
            pass
    
    # Register the custom handler with HandlerRegistry
    handler_registry.register_handler("custom", CustomHandler())

Adding Custom Commands
~~~~~~~~~~~~~~~~~~~~

To add custom commands to your bot:

1. Create custom handler methods in your implementation
2. Register them with the HandlerRegistry
3. Update the help text to include your new commands

Troubleshooting
--------------

Common Issues
~~~~~~~~~~~

- **Bot Not Responding**: Ensure your TELEGRAM_BOT_TOKEN is correct and the bot is running
- **API Key Issues**: Verify your LLM provider's API key is valid and has sufficient quota
- **Rate Limiting**: If you hit rate limits, adjust the max_tokens parameters or switch providers
- **Message Processing Errors**: Check your logs for detailed error messages

Best Practices
-------------

1. **Token Security**: Never hardcode tokens or API keys in your source code
2. **Error Handling**: Implement proper error handling for both Telegram API operations and LLM requests
3. **Graceful Shutdown**: Always implement proper shutdown procedures to clean up resources
4. **Group Management**: Be mindful of how your bot behaves in group chats
5. **Privacy Considerations**: Inform users about data processing and storage
6. **Scaling**: For high-traffic bots, consider implementing additional rate limiting and resource management

Next Steps
---------

Now that you've set up your Telegram agent, consider:

- Adding more specialized agents to collaborate with your Telegram interface
- Implementing custom tools to enhance your bot's capabilities
- Creating a web dashboard to monitor your bot's activity
- Exploring conversation memory and context management for improved interactions

For a complete working example, see our :doc:`Telegram Agent Example </examples/telegram_example>`. 