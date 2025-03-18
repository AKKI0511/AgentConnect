Multi-Agent Example
=================

.. _multi_agent_example:

Working with Multiple Agents
---------------------------

This example demonstrates how to set up and manage multiple agents in a collaborative environment.

Setting Up Multiple Agents
-------------------------

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.communication import CommunicationHub
    from agentconnect.providers import OpenAIProvider, AnthropicProvider, GoogleProvider

    # Create different providers
    openai_provider = OpenAIProvider(model="gpt-4")
    anthropic_provider = AnthropicProvider(model="claude-3-opus")
    google_provider = GoogleProvider(model="gemini-pro")

    # Create agents with different capabilities
    researcher = AIAgent(name="Researcher", provider=openai_provider)
    analyst = AIAgent(name="Analyst", provider=anthropic_provider)
    writer = AIAgent(name="Writer", provider=google_provider)

    # Create a communication hub
    hub = CommunicationHub()

    # Connect all agents
    hub.connect_all([researcher, analyst, writer])

Collaborative Problem Solving
----------------------------

Once the agents are connected, you can have them collaborate on a task:

.. code-block:: python

    # Start with a research task
    research_results = researcher.send_message(
        "Research the latest advancements in quantum computing.", 
        to=hub.get_all_agents()
    )

    # Analyst processes the research
    analysis = analyst.send_message(
        f"Analyze these research findings: {research_results}",
        to=writer
    )

    # Writer creates the final report
    final_report = writer.send_message(
        f"Create a comprehensive report based on this analysis: {analysis}",
        to=hub.get_agent("Researcher")  # Send back to researcher for verification
    )

    print(f"Final Report: {final_report}")

Agent Specialization
------------------

You can also create specialized agents for specific tasks:

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.prompts import PromptTemplates

    # Create a specialized agent for code review
    code_reviewer = AIAgent(
        name="CodeReviewer",
        provider=openai_provider,
        system_prompt=PromptTemplates.get_template("code_review")
    )

    # Add to the hub
    hub.connect(code_reviewer, [researcher, analyst, writer])

    # Use for code review
    code_review = code_reviewer.send_message(
        "Please review this Python code: ```python\ndef factorial(n):\n    if n == 0:\n        return 1\n    else:\n        return n * factorial(n-1)\n```",
        to=analyst
    )

    print(f"Code Review: {code_review}") 