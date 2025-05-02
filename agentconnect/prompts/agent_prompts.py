"""
Agent workflow definitions for the AgentConnect framework.

This module provides the core workflow definitions for different agent types,
using LangGraph to create stateful, multi-step workflows. These workflows
enable agents to make decisions, collaborate with other agents, and process
complex tasks.

The module implements the ReAct (Reasoning + Acting) pattern using LangGraph's
StateGraph to create workflows with multiple nodes for preprocessing, execution,
and postprocessing.
"""

# Standard library imports
import json
import logging
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

from langchain.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate

# Third-party imports
from langchain_core.runnables import chain
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agentconnect.prompts.templates.prompt_templates import (
    PromptTemplates,
    PromptType,
    ReactConfig,
    SystemPromptConfig,
)

# Absolute imports from agentconnect package
from agentconnect.prompts.tools import PromptTools

# Set up logging
logger = logging.getLogger(__name__)


class AgentMode(Enum):
    """
    Enum representing the operational modes of an agent.

    Attributes:
        CUSTOM_RUNNABLE: Agent uses a custom runnable for processing
        SYSTEM_PROMPT: Agent uses a system prompt for processing
    """

    CUSTOM_RUNNABLE = "custom_runnable"
    SYSTEM_PROMPT = "system_prompt"


class WorkflowState(Enum):
    """
    Enum for workflow states.

    Attributes:
        THINKING: Agent is thinking about the problem
        RESPONDING: Agent is generating a response
        TOOL_CALLING: Agent is calling a tool
        COLLABORATION: Agent is collaborating with another agent
        TASK_DECOMPOSITION: Agent is breaking down a task
        CAPABILITY_MATCHING: Agent is matching capabilities to tasks
        ERROR: An error occurred in the workflow
        COMPLETE: Workflow is complete
    """

    THINKING = "thinking"
    RESPONDING = "responding"
    TOOL_CALLING = "tool_calling"
    COLLABORATION = "collaboration"
    TASK_DECOMPOSITION = "task_decomposition"
    CAPABILITY_MATCHING = "capability_matching"
    ERROR = "error"
    COMPLETE = "complete"


class AgentState(TypedDict):
    """
    Base state for agent workflows.

    This TypedDict defines the structure of the state object used in agent workflows.
    It includes fields for messages, sender/receiver information, capabilities,
    and various tracking fields.

    Attributes:
        messages: Sequence of messages in the conversation
        sender: ID of the message sender
        receiver: ID of the message receiver
        mode: Optional mode of operation
        capabilities: Optional list of agent capabilities
        runnable_result: Optional result from a runnable
        collaboration_results: Optional results from collaboration
        agents_found: Optional list of agents found
        retry_count: Optional count of retries
        error: Optional error message
        context_reset: Optional flag for context reset
        topic_changed: Optional flag for topic change
        last_interaction_time: Optional timestamp of last interaction
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    sender: str
    receiver: str
    # Mode of operation
    mode: Optional[str]
    # Agent capabilities
    capabilities: Optional[List[str]]
    # Results and tracking
    runnable_result: Optional[Dict[str, Any]]
    collaboration_results: Optional[Dict[str, Any]]
    agents_found: Optional[List[Dict[str, Any]]]
    retry_count: Optional[Dict[str, int]]
    error: Optional[str]
    # Context management
    context_reset: Optional[bool]
    topic_changed: Optional[bool]
    last_interaction_time: Optional[float]


class CollaborationState(AgentState):
    """
    State for collaboration workflows.

    This TypedDict extends AgentState with additional fields specific to
    collaboration workflows.

    Attributes:
        found_agents: List of agent IDs found for collaboration
        capabilities: List of agent capabilities
        collaboration_result: Optional result from collaboration
        subtasks: List of subtasks
        current_subtask: Optional current subtask
        completed_subtasks: List of completed subtasks
        task_description: Optional task description
        action: Optional action to take
        error: Optional error message
    """

    found_agents: List[str]
    capabilities: List[Dict[str, Any]]
    collaboration_result: Optional[Dict[str, Any]]
    subtasks: List[Dict[str, Any]]
    current_subtask: Optional[Dict[str, Any]]
    completed_subtasks: List[Dict[str, Any]]
    task_description: Optional[str]
    action: Optional[str]
    error: Optional[str]


class DecisionOutput(BaseModel):
    """
    Output schema for decision nodes.

    Attributes:
        action: The action to take next
        reason: The reason for the decision
    """

    action: str = Field(description="The action to take next.")
    reason: str = Field(description="The reason for the decision.")


class TaskDecompositionOutput(BaseModel):
    """
    Output schema for task decomposition.

    Attributes:
        subtasks: List of subtasks
    """

    subtasks: List[Dict[str, Any]] = Field(description="List of subtasks.")


class AgentWorkflow:
    """
    Base class for agent workflows.

    This class provides the foundation for creating agent workflows using LangGraph.
    It handles the creation of the workflow graph, tools, and prompt templates.

    Attributes:
        agent_id: Unique identifier for the agent
        llm: Language model to use
        tools: Tools available to the agent
        prompt_templates: Prompt templates for the agent
        custom_tools: Optional list of custom LangChain tools
        workflow: The workflow graph
        mode: The agent's operational mode
    """

    def __init__(
        self,
        agent_id: str,
        llm: BaseChatModel,
        tools: PromptTools,
        prompt_templates: PromptTemplates,
        custom_tools: Optional[List[BaseTool]] = None,
        verbose: bool = False,
    ):
        """
        Initialize the agent workflow.

        Args:
            agent_id: Unique identifier for the agent
            llm: Language model to use
            tools: Tools available to the agent
            prompt_templates: Prompt templates for the agent
            custom_tools: Optional list of custom LangChain tools
            verbose: Whether to print verbose output
        """
        self.agent_id = agent_id
        self.llm = llm
        self.tools = tools
        self.prompt_templates = prompt_templates
        self.custom_tools = custom_tools or []
        self.workflow = None
        self.verbose = verbose
        # Set the mode based on whether custom tools are provided
        self.mode = AgentMode.SYSTEM_PROMPT

        # Set the LLM in tools if it doesn't already have one
        if self.tools.llm is None:
            self.tools.llm = llm

        # Build the workflow
        self.workflow = self.build_workflow()

    def _create_react_prompt(self) -> ChatPromptTemplate:
        """
        Create the prompt for the ReAct agent.

        Returns:
            A ChatPromptTemplate for the ReAct agent.
        """
        # Get system prompt information
        if hasattr(self, "system_prompt_config"):
            # Pass all system_prompt_config properties to ReactConfig
            react_config = ReactConfig(
                name=self.system_prompt_config.name,
                capabilities=[
                    {"name": cap.name, "description": cap.description}
                    for cap in self.system_prompt_config.capabilities
                ],
                personality=self.system_prompt_config.personality,
                mode=self.mode.value,
                additional_context=self.system_prompt_config.additional_context,
                enable_payments=self.system_prompt_config.enable_payments,
                payment_token_symbol=self.system_prompt_config.payment_token_symbol,
                role=self.system_prompt_config.role,
            )
        else:
            # Default configuration if system_prompt_config isn't available
            react_config = ReactConfig(
                name="AI Assistant",
                capabilities=[
                    {"name": "Conversation", "description": "general assistance"}
                ],
                personality="helpful and professional",
                mode=self.mode.value,
            )

        # Create the react prompt using the prompt templates
        react_prompt = self.prompt_templates.create_prompt(
            prompt_type=PromptType.REACT, config=react_config, include_history=True
        )

        # Don't add scratchpad here - let langgraph.prebuilt handle it
        return react_prompt

    def build_workflow(self) -> StateGraph:
        """
        Build the workflow graph for the agent.

        Returns:
            A StateGraph instance representing the agent's workflow.
        """
        # Create the base tools list
        base_tools = [
            self.tools.create_agent_search_tool(),
            self.tools.create_send_collaboration_request_tool(),
            self.tools.create_check_collaboration_result_tool(),
            # self.tools.create_task_decomposition_tool(),
        ]

        # Add custom tools if available
        if self.custom_tools:
            base_tools.extend(self.custom_tools)
            logger.debug(f"Added {len(self.custom_tools)} custom tools to the workflow")

        # Create the ReAct prompt
        react_prompt = self._create_react_prompt()

        # Create the ReAct agent - let langgraph.prebuilt handle the scratchpad
        react_agent = create_react_agent(
            model=self.llm,
            tools=base_tools,
            prompt=react_prompt,
            debug=self.verbose,
        )

        # Create the workflow graph
        workflow = StateGraph(AgentState)

        # Define nodes
        @chain
        async def preprocess(
            state: AgentState, config: RunnableConfig
        ) -> Dict[str, Any]:
            """
            Preprocess the state before the ReAct agent.

            This node initializes state properties, handles context resets,
            and manages time-based context management.

            Args:
                state: The current state
                config: The runnable configuration

            Returns:
                The updated state
            """
            import time

            # Check for long gaps between interactions (over 30 minutes)
            current_time = time.time()
            if "last_interaction_time" in state:
                time_gap = current_time - state["last_interaction_time"]
                if time_gap > 1800:  # 30 minutes in seconds
                    state["context_reset"] = True
                    logger.info(f"Context reset due to time gap of {time_gap} seconds")

            # Update last interaction time
            state["last_interaction_time"] = current_time

            return state

        @chain
        async def run_react(
            state: AgentState, config: RunnableConfig
        ) -> Dict[str, Any]:
            """
            Run the ReAct agent.

            This node executes the ReAct agent with the current state,
            handling context resets and topic changes.

            Args:
                state: The current state
                config: The runnable configuration

            Returns:
                The updated state with the ReAct agent's response
            """
            # We'll use the existing callbacks if they exist, rather than creating new ones
            # This prevents multiple traces in LangSmith

            # If context reset is needed, modify the messages to only keep the most recent
            if state.get("context_reset", False):
                messages = state.get("messages", [])
                if len(messages) > 2:  # Keep only the most recent user message
                    # Find the most recent user message
                    for i in range(len(messages) - 1, -1, -1):
                        if messages[i].type == "human":
                            state["messages"] = [messages[i]]
                            break
                    logger.info(
                        "Context reset: Keeping only the most recent user message"
                    )

            # If topic has changed, reduce context by removing older messages
            if state.get("topic_changed", False):
                messages = state.get("messages", [])
                if len(messages) > 6:  # Keep only the 3 most recent exchanges
                    state["messages"] = messages[-6:]
                    logger.info(
                        "Topic changed: Keeping only the 3 most recent exchanges"
                    )

            # Ensure callbacks are passed to the agent
            result = await react_agent.ainvoke(state, config)
            return result

        @chain
        async def postprocess(
            state: AgentState, config: RunnableConfig
        ) -> Dict[str, Any]:
            """
            Postprocess the state after the ReAct agent.

            This node extracts tool results, detects topic changes,
            and updates the state accordingly.

            Args:
                state: The current state
                config: The runnable configuration

            Returns:
                The final updated state
            """
            # Extract and store tool results for future reference
            messages = state.get("messages", [])
            if not messages:
                return state

            # Process the last message for tool calls
            last_message = messages[-1]
            tool_calls = getattr(last_message, "tool_calls", None)

            if tool_calls:
                # Process tool calls and store results
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "")

                    if tool_name == "search_for_agents":
                        # Store agents found
                        agents_found = tool_call.get("result", [])
                        if isinstance(agents_found, str):
                            try:
                                # Try to parse if it's a string representation of JSON
                                agents_found = json.loads(agents_found)
                            except Exception as e:
                                logger.warning(f"Error parsing agents found: {e}")
                                # If parsing fails, wrap in a list
                                agents_found = [
                                    {
                                        "agent_id": "unknown",
                                        "capabilities": agents_found,
                                    }
                                ]

                        state["agents_found"] = agents_found

                    elif tool_name == "send_collaboration_request":
                        # Get the tool arguments
                        tool_args = tool_call.get("args", {})
                        if isinstance(tool_args, str):
                            try:
                                tool_args = json.loads(tool_args)
                            except Exception as e:
                                logger.warning(f"Error parsing tool args: {e}")
                                tool_args = {
                                    "agent_id": "unknown",
                                    "request": tool_args,
                                }

                        agent_id = tool_args.get("agent_id", "unknown")

                        # Store the collaboration result
                        result = tool_call.get("result", "")
                        if "collaboration_results" not in state:
                            state["collaboration_results"] = {}
                        state["collaboration_results"][agent_id] = result

                        # Reset retry count for successful collaboration
                        if "retry_count" in state and agent_id in state["retry_count"]:
                            state["retry_count"][agent_id] = 0

                    elif tool_name == "decompose_task":
                        # Store task decomposition result
                        if "result" in tool_call and "subtasks" in tool_call["result"]:
                            state["subtasks"] = tool_call["result"]["subtasks"]

            # Detect topic changes based on the last few messages
            if len(messages) >= 4:
                # Simple heuristic: if the last message contains significantly different content
                # from previous messages, consider it a topic change
                try:
                    import numpy as np
                    from sklearn.feature_extraction.text import TfidfVectorizer
                    from sklearn.metrics.pairwise import cosine_similarity

                    # Extract the content from the last few messages, only if it's a string
                    recent_contents = [
                        (
                            msg.content
                            if isinstance(msg.content, str)
                            else str(msg.content)
                        )
                        for msg in messages[-4:]
                        if hasattr(msg, "content")
                    ]

                    # Filter out any empty or non-string contents
                    recent_contents = [
                        c for c in recent_contents if isinstance(c, str) and c.strip()
                    ]

                    if len(recent_contents) >= 2:
                        # Create TF-IDF vectors
                        vectorizer = TfidfVectorizer()
                        tfidf_matrix = vectorizer.fit_transform(recent_contents)

                        # Calculate similarity between the last message and previous messages
                        similarity_scores = cosine_similarity(
                            tfidf_matrix[-1:], tfidf_matrix[:-1]
                        )[0]
                        avg_similarity = np.mean(similarity_scores)

                        # If similarity is low, mark as topic change
                        if avg_similarity < 0.3:  # Threshold for topic change
                            state["topic_changed"] = True
                            logger.info(
                                f"Topic change detected with similarity score: {avg_similarity}"
                            )
                except Exception as e:
                    logger.warning(f"Error detecting topic change: {str(e)}")

            return state

        # Add nodes to the graph
        workflow.add_node("preprocess", preprocess)
        workflow.add_node("react", run_react)
        workflow.add_node("postprocess", postprocess)

        # Add edges
        workflow.set_entry_point("preprocess")
        workflow.add_edge("preprocess", "react")
        workflow.add_edge("react", "postprocess")
        workflow.add_edge("postprocess", END)

        return workflow

    def compile(self):
        """
        Compile the workflow with memory persistence.

        Returns:
            The compiled workflow with memory persistence
        """
        from langgraph.checkpoint.memory import MemorySaver

        # Create a memory saver for persistence
        memory_saver = MemorySaver()

        # Compile the workflow with the memory saver
        logger.info(f"Compiling workflow for agent {self.agent_id}")

        # Use default behavior for callbacks to avoid multiple traces in LangSmith
        return self.workflow.compile(checkpointer=memory_saver)


class AIAgentWorkflow(AgentWorkflow):
    """
    Workflow for AI agents with enhanced capabilities.

    This workflow extends the base AgentWorkflow with AI-specific
    capabilities and system prompt configuration.

    Attributes:
        system_prompt_config: Configuration for the system prompt
    """

    def __init__(
        self,
        agent_id: str,
        system_prompt_config: SystemPromptConfig,
        llm: BaseChatModel,
        tools: PromptTools,
        prompt_templates: PromptTemplates,
        custom_tools: Optional[List[BaseTool]] = None,
        verbose: bool = False,
    ):
        """
        Initialize the AI agent workflow.

        Args:
            agent_id: Unique identifier for the agent
            system_prompt_config: Configuration for the system prompt
            llm: Language model to use
            tools: Tools available to the agent
            prompt_templates: Prompt templates for the agent
            custom_tools: Optional list of custom LangChain tools
            verbose: Whether to print verbose output
        """
        self.system_prompt_config = system_prompt_config
        super().__init__(agent_id, llm, tools, prompt_templates, custom_tools, verbose)


class TaskDecompositionWorkflow(AgentWorkflow):
    """
    Workflow for decomposing tasks into subtasks.

    This workflow extends the base AgentWorkflow with task decomposition
    capabilities and system prompt configuration.

    Attributes:
        system_prompt_config: Configuration for the system prompt
    """

    def __init__(
        self,
        agent_id: str,
        system_prompt_config: SystemPromptConfig,
        llm: BaseChatModel,
        tools: PromptTools,
        prompt_templates: PromptTemplates,
        custom_tools: Optional[List[BaseTool]] = None,
        verbose: bool = False,
    ):
        """
        Initialize the task decomposition workflow.

        Args:
            agent_id: Unique identifier for the agent
            system_prompt_config: Configuration for the system prompt
            llm: Language model to use
            tools: Tools available to the agent
            prompt_templates: Prompt templates for the agent
            custom_tools: Optional list of custom LangChain tools
            verbose: Whether to print verbose output
        """
        self.system_prompt_config = system_prompt_config
        super().__init__(agent_id, llm, tools, prompt_templates, custom_tools, verbose)


class CollaborationRequestWorkflow(AgentWorkflow):
    """
    Workflow for handling collaboration requests.

    This workflow extends the base AgentWorkflow with collaboration
    capabilities and system prompt configuration.

    Attributes:
        system_prompt_config: Configuration for the system prompt
    """

    def __init__(
        self,
        agent_id: str,
        system_prompt_config: SystemPromptConfig,
        llm: BaseChatModel,
        tools: PromptTools,
        prompt_templates: PromptTemplates,
        custom_tools: Optional[List[BaseTool]] = None,
        verbose: bool = False,
    ):
        """
        Initialize the collaboration request workflow.

        Args:
            agent_id: Unique identifier for the agent
            system_prompt_config: Configuration for the system prompt
            llm: Language model to use
            tools: Tools available to the agent
            prompt_templates: Prompt templates for the agent
            custom_tools: Optional list of custom LangChain tools
            verbose: Whether to print verbose output
        """
        self.system_prompt_config = system_prompt_config
        super().__init__(agent_id, llm, tools, prompt_templates, custom_tools, verbose)


def create_workflow_for_agent(
    agent_type: str,
    system_config: SystemPromptConfig,
    llm: BaseChatModel,
    tools: PromptTools,
    prompt_templates: PromptTemplates,
    agent_id: Optional[str] = None,
    custom_tools: Optional[List[BaseTool]] = None,
    verbose: bool = False,
) -> AgentWorkflow:
    """
    Factory function to create workflows based on agent type.

    Args:
        agent_type: Type of agent workflow to create
        system_config: System prompt configuration
        llm: Language model to use
        tools: Tools available to the agent
        prompt_templates: Prompt templates for the agent
        agent_id: Optional agent ID for tool context
        custom_tools: Optional list of custom LangChain tools
        verbose: Whether to print verbose output

    Returns:
        An AgentWorkflow instance

    Raises:
        ValueError: If the agent type is unknown
    """
    # Generate a unique agent ID if not provided
    if not agent_id:
        import uuid

        agent_id = f"{agent_type}_{uuid.uuid4().hex[:8]}"

    # Note: We don't need to set the current agent ID here
    # It's now set in AIAgent._initialize_workflow before this function is called
    logger.debug(f"Creating workflow for agent: {agent_id}")

    # Check for payment capabilities in the system config
    if system_config.enable_payments:
        logger.info(
            f"Agent {agent_id}: Creating workflow with payment capabilities enabled for {system_config.payment_token_symbol}"
        )

    # Create the appropriate workflow based on agent type
    if agent_type == "ai":
        workflow = AIAgentWorkflow(
            agent_id=agent_id,
            system_prompt_config=system_config,
            llm=llm,
            tools=tools,
            prompt_templates=prompt_templates,
            custom_tools=custom_tools,
            verbose=verbose,
        )
    elif agent_type == "task_decomposition":
        workflow = TaskDecompositionWorkflow(
            agent_id=agent_id,
            system_prompt_config=system_config,
            llm=llm,
            tools=tools,
            prompt_templates=prompt_templates,
            custom_tools=custom_tools,
            verbose=verbose,
        )
    elif agent_type == "collaboration_request":
        workflow = CollaborationRequestWorkflow(
            agent_id=agent_id,
            system_prompt_config=system_config,
            llm=llm,
            tools=tools,
            prompt_templates=prompt_templates,
            custom_tools=custom_tools,
            verbose=verbose,
        )
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")

    return workflow
