"""
Chain factory for creating LangGraph workflows.

This module provides factory functions for creating LangGraph workflows
with different configurations and capabilities. It simplifies the process
of creating complex agent workflows by providing pre-configured templates.

Note: The ChainFactory class is deprecated. Use the workflow functions instead.
"""

# Standard library imports
import warnings
from typing import Annotated, Any, Callable, Dict, List, Optional, Sequence, TypedDict

# Third-party imports
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

# Absolute imports from agentconnect package
from agentconnect.core.registry import AgentRegistry
from agentconnect.core.types import ModelName, ModelProvider
from agentconnect.prompts.agent_prompts import AgentWorkflow, CollaborationState
from agentconnect.prompts.templates.prompt_templates import (
    PromptTemplates,
    SystemPromptConfig,
)
from agentconnect.prompts.tools import PromptTools
from agentconnect.providers.provider_factory import ProviderFactory

# Issue deprecation warning
warnings.warn(
    "chain_factory.py is deprecated. Agent workflows are now defined in prompts/agent_prompts.py",
    DeprecationWarning,
)


class State(TypedDict):
    """
    State type for basic conversation workflows.

    Attributes:
        messages: Sequence of messages in the conversation
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]


class ChainFactory:
    """
    Factory for creating conversation chains.

    Deprecated: Use the workflow functions instead.
    """

    @staticmethod
    def create_conversation_chain(
        provider_type: ModelProvider,
        model_name: ModelName,
        api_key: str,
        system_config: SystemPromptConfig,
    ) -> Runnable:
        """
        Create a conversation chain with the specified configuration.

        Args:
            provider_type: Type of model provider to use
            model_name: Name of the model to use
            api_key: API key for the provider
            system_config: Configuration for the system prompt

        Returns:
            A compiled Runnable representing the conversation chain
        """
        # Get components
        system_prompt = PromptTemplates.get_system_prompt(system_config)

        # Create prompt template with examples and instructions
        prompt_messages = [system_prompt, MessagesPlaceholder(variable_name="messages")]
        prompt = ChatPromptTemplate.from_messages(prompt_messages)

        # Get the provider
        provider = ProviderFactory.create_provider(provider_type, api_key)
        llm = provider.get_langchain_llm(
            model_name=model_name,
            temperature=system_config.temperature,
            max_tokens=system_config.max_tokens,
        )

        runnable = prompt | llm

        # Create the state graph for managing conversation flow
        workflow = StateGraph(state_schema=State)

        # Define the message processing node
        def call_model(state: State) -> Dict[str, List[BaseMessage]]:
            """Process the current state using the model."""
            response = runnable.invoke(state)
            return {"messages": [response]}

        # Add nodes to the graph
        workflow.set_entry_point("model")
        workflow.add_node("model", call_model)

        # Use memory saver for state management
        memory = MemorySaver()

        # Compile the workflow
        app = workflow.compile(checkpointer=memory)
        return app


def create_agent_workflow(
    agent_type: str,
    system_config: SystemPromptConfig,
    llm: BaseChatModel,
    agent_registry: Optional[AgentRegistry] = None,
    tools: Optional[List[BaseTool]] = None,
    prompt_templates: Optional[PromptTemplates] = None,
    agent_id: Optional[str] = None,
    custom_tools: Optional[List[BaseTool]] = None,
) -> AgentWorkflow:
    """Create a workflow for an agent.

    Args:
        agent_type: Type of agent workflow to create
        system_config: Configuration for the system prompt
        llm: Language model to use for the agent
        agent_registry: Registry of agents for collaboration
        tools: Tools for the agent to use
        prompt_templates: Templates for prompts
        agent_id: ID of the agent
        custom_tools: Custom tools for the agent

    Returns:
        An agent workflow that can be compiled and run
    """
    warnings.warn(
        "create_agent_workflow is deprecated. Use create_workflow_for_agent from agent_prompts.py instead",
        DeprecationWarning,
    )

    from agentconnect.communication import CommunicationHub
    from agentconnect.prompts.agent_prompts import create_workflow_for_agent

    # Create empty list if tools is None
    all_tools = tools or []

    # Add custom tools if provided
    if custom_tools:
        all_tools.extend(custom_tools)

    # Add agent tools if registry is provided
    if agent_registry:
        # Create the PromptTools instance
        prompt_tools = PromptTools(
            agent_registry=agent_registry,
            communication_hub=CommunicationHub(),  # Use a default hub
            llm=llm,
        )

        # If agent_id is provided, set it as the current agent
        if agent_id:
            prompt_tools.set_current_agent(agent_id)

        # Get tools for workflow
        agent_tools = prompt_tools.get_tools_for_workflow(categories=["collaboration"])
        all_tools.extend(agent_tools)

    # Create and return workflow
    return create_workflow_for_agent(
        agent_type=agent_type,
        system_config=system_config,
        llm=llm,
        tools=prompt_tools if agent_registry else None,
        prompt_templates=prompt_templates,
        agent_id=agent_id,
        custom_tools=all_tools if all_tools else None,
    )


def create_collaboration_workflow(
    llm: BaseChatModel,
    agent_registry: AgentRegistry,
    system_prompt: str,
    memory_key: str = "chat_history",
    max_iterations: int = 10,
) -> StateGraph:
    """
    Create a collaboration workflow for agent-to-agent interaction.

    Args:
        llm: Language model to use for the workflow
        agent_registry: Registry of agents for collaboration
        system_prompt: System prompt for the workflow
        memory_key: Key to use for storing chat history
        max_iterations: Maximum number of iterations for the workflow

    Returns:
        A StateGraph representing the collaboration workflow
    """
    # Create tools for agent collaboration
    # from agentconnect.communication import CommunicationHub

    # Initialize the PromptTools
    # prompt_tools = PromptTools(
    #     agent_registry=agent_registry,
    #     communication_hub=CommunicationHub(),  # Use a default hub
    #     llm=llm
    # )

    # Get tools for the workflow
    # tools = prompt_tools.get_tools_for_workflow(categories=["collaboration"])

    # Define the collaboration state
    state_type = CollaborationState

    # Create the workflow graph
    workflow = StateGraph(state_type)

    # Define the nodes in the workflow
    def agent_node(state: CollaborationState) -> CollaborationState:
        """Process the current state using the agent."""
        # Implementation would use the LLM to process the state
        return state

    def router_node(state: CollaborationState) -> str:
        """Route to the next node based on the current state."""
        if state.iterations >= max_iterations or state.final_answer:
            return "end"
        return "agent"

    # Add nodes to the workflow
    workflow.add_node("agent", agent_node)

    # Add conditional edges
    workflow.add_conditional_edges("agent", router_node, {"end": END, "agent": "agent"})

    # Set the entry point
    workflow.set_entry_point("agent")

    return workflow


def create_custom_workflow(
    llm: BaseChatModel,
    nodes: Dict[str, Callable],
    edges: Dict[str, Dict[str, str]],
    state_type: Any,
    entry_point: str,
    tools: Optional[List[BaseTool]] = None,
) -> StateGraph:
    """
    Create a custom workflow with the specified nodes and edges.

    Args:
        llm: Language model to use for the workflow
        nodes: Dictionary mapping node names to node functions
        edges: Dictionary mapping source nodes to dictionaries of condition-target pairs
        state_type: Type of state to use for the workflow
        entry_point: Name of the entry point node
        tools: Optional list of tools for the workflow

    Returns:
        A StateGraph representing the custom workflow

    Raises:
        ValueError: If the entry point is not in the nodes dictionary
    """
    if entry_point not in nodes:
        raise ValueError(f"Entry point {entry_point} not found in nodes")

    # Create the workflow graph
    workflow = StateGraph(state_type)

    # Add nodes to the workflow
    for name, func in nodes.items():
        workflow.add_node(name, func)

    # Add edges to the workflow
    for source, targets in edges.items():
        if "end" in targets and targets["end"] == "END":
            targets["end"] = END

        # Add conditional edges if there are multiple targets
        if len(targets) > 1:
            workflow.add_conditional_edges(
                source,
                lambda state, src=source: edges[src].get(state.next_step, "end"),
                targets,
            )
        # Add a simple edge if there's only one target
        elif len(targets) == 1:
            target = next(iter(targets.values()))
            workflow.add_edge(source, target)

    # Set the entry point
    workflow.set_entry_point(entry_point)

    return workflow


def compile_workflow(
    workflow: StateGraph, config: Optional[Dict[str, Any]] = None
) -> Runnable:
    """
    Compile a workflow into a runnable.

    Args:
        workflow: StateGraph to compile
        config: Optional configuration for the runnable

    Returns:
        A compiled Runnable
    """
    # Compile the workflow
    app = workflow.compile()

    # Apply configuration if provided
    if config:
        app = app.with_config(config)

    return app


def create_runnable_from_workflow(
    workflow: StateGraph, config: Optional[RunnableConfig] = None
) -> Runnable:
    """
    Create a runnable from a workflow with the specified configuration.

    Args:
        workflow: StateGraph to create a runnable from
        config: Optional configuration for the runnable

    Returns:
        A Runnable that can be used to execute the workflow
    """
    # Compile the workflow
    app = workflow.compile()

    # Apply configuration if provided
    if config:
        app = app.with_config(config)

    return app
