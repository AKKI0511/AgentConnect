"""
Prompt templates for the AgentConnect framework.

This module provides templates for creating different types of prompts for agents,
including system prompts, collaboration prompts, and ReAct prompts. These templates
are used to generate the prompts that guide agent behavior and decision-making.
"""

from dataclasses import dataclass

# Standard library imports
from enum import Enum
from typing import Any, Dict, List, Optional, Union

# Third-party imports
from langchain.prompts import (
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Absolute imports from agentconnect package
from agentconnect.core.types import Capability


class PromptType(str, Enum):
    """
    Types of prompts that can be used in the system.

    Attributes:
        SYSTEM: System message prompt
        HUMAN: Human message prompt
        AI: AI message prompt
        FUNCTION: Function message prompt
        CHAT: Chat prompt with multiple messages
        COLLABORATION: Prompt for agent collaboration
        TASK_DECOMPOSITION: Prompt for breaking down tasks
        CAPABILITY_MATCHING: Prompt for matching capabilities to tasks
        SUPERVISOR: Prompt for supervisor agents
        REACT: Prompt for ReAct agents
    """

    SYSTEM = "system"
    HUMAN = "human"
    AI = "ai"
    FUNCTION = "function"
    CHAT = "chat"
    COLLABORATION = "collaboration"
    TASK_DECOMPOSITION = "task_decomposition"
    CAPABILITY_MATCHING = "capability_matching"
    SUPERVISOR = "supervisor"
    REACT = "react"


# Core prompt components that are reused across templates
BASE_RESPONSE_FORMAT = """
RESPONSE STYLE:
- Match length to user's request (brief/detailed as needed)
- Present results directly and clearly
- Ask specific questions when more details help
- Use '__EXIT__' to gracefully end conversations
"""

# Common knowledge tasks that are handled directly by all agents
COMMON_KNOWLEDGE_TASKS = """
- Coding examples, pseudocode, or general programming advice
- Common explanations and definitions
- General reasoning tasks
- Brainstorming and creative thinking
- Basic information synthesis
"""

# Unified decision framework and execution strategy for all agents
AGENT_FRAMEWORK = """
DECISION FRAMEWORK:
1. ASSESS: Examine request scope
   - COMMON KNOWLEDGE TASKS: Handle immediately regardless of listed capabilities
   - WITHIN capabilities → Use direct handling
   - OUTSIDE capabilities → **Silently** search for agents and delegate immediately
   - PARTIALLY within → Handle known parts, **silently** find help for others

2. EXECUTE:
   - Use your capabilities and tools directly without announcing them
   - For common knowledge → Answer directly even if not in your capabilities
   - For specialized needs → **Silently** find & use agents
   - Search for agents using GENERAL CAPABILITY TERMS (e.g., "web_research", "code_generation")
   - NEVER use specific topics (e.g., "langchain", "crypto prices") when searching for agents
   - Present **only** actual results, never mentioning delegation

3. RESPOND: 
   - Provide direct answers with actual information
   - Include results, not "I can't" or "I would" statements
   - If no agent can help after multiple attempts, provide best effort answer
   - NEVER say "I don't have that capability" or "I can't help with that"
"""

# Collaboration protocol for agents
COLLABORATION_PROTOCOL = """
DELEGATION GUIDE (INTERNAL PROCESS - DO NOT MENTION TO USER):
1. **Silently** search for specialized agents
2. Include full context in requests to other agents
3. Obtain actual results from other agents to formulate your final response
4. Focus on delivering the final information to the user
5. Try multiple agents **internally** if the first one can't help
6. If no agents can help after multiple attempts, provide best effort answer **without mentioning the failed attempts**

KEY PRINCIPLES:
- NEVER say "I can't" or "I don't have that capability" to the user
- Always provide information, not just promises to find it
- For common tasks, handle directly
- **INTERNAL ACTIONS (searching, delegating, internal failures) MUST remain hidden from the user**
- **ALWAYS use exact agent_ids from search_for_agents results - never invent, guess, or use capability names directly**
"""

# Tool usage guide for all agents
TOOL_USAGE_GUIDE = """
TOOL USAGE GUIDE:
1. SEARCH: Use search_for_agents to find agents with needed capabilities
   - Example: search_for_agents(capability_name="web_research")
   - This returns actual agent_ids which may look like "research_agent" or "did:0933858jjfr995h48f"
2. DELEGATE: Use send_collaboration_request with ONLY the exact agent_ids from search results
   - CORRECT: send_collaboration_request(target_agent_id="research_agent", task="research quantum computing")
   - INCORRECT: send_collaboration_request(target_agent_id="web_research", task="research quantum computing")

COLLABORATION SEQUENCE:
1. search_for_agents with capability name → returns actual agent_ids
2. send_collaboration_request with exact agent_id from previous step's results

EXAMPLE:
User: "Find latest trends on MCP"
Bad: "I'm sorry, I don't have that capability." or "Okay, I will find an agent to help with that."
Good: "The latest MCP trends include..." (Agent performs search/delegation silently in the background)
"""

# Best practices for all agents
AGENT_BEST_PRACTICES = """
BEST PRACTICES:
- NEVER refuse to help; either answer directly or find another agent
- Start searching immediately **without mentioning it to the user**
- Delegate tasks **without mentioning it to the user**
- Use tools right away instead of talking about using them
- Provide direct answers with actual information, **concealing internal steps**
- Show results of your actions, not just your intentions
- **IMPORTANT: NEVER mention searching for, finding, or delegating to other agents unless explicitly asked**
"""


@dataclass
class SystemPromptConfig:
    """
    Configuration for system prompts.

    Attributes:
        name: Name of the agent
        capabilities: List of agent capabilities
        personality: Description of the agent's personality
        temperature: Temperature for generation
        max_tokens: Maximum tokens for generation
        additional_context: Additional context for the prompt
        role: Role of the agent
    """

    name: str
    capabilities: List[Capability]  # Now accepts a list of Capability objects
    personality: str = "helpful and professional"
    temperature: float = 0.7
    max_tokens: int = 1024
    additional_context: Optional[Dict[str, Any]] = None
    role: str = "assistant"


@dataclass
class CollaborationConfig:
    """
    Configuration for collaboration prompts.

    Attributes:
        agent_name: Name of the agent
        target_capabilities: List of capabilities to collaborate on
        collaboration_type: Type of collaboration
        additional_context: Additional context for the prompt
    """

    agent_name: str
    target_capabilities: List[str]
    collaboration_type: str = "request"  # request, response, or error
    additional_context: Optional[Dict[str, Any]] = None


@dataclass
class TaskDecompositionConfig:
    """
    Configuration for task decomposition prompts.

    Attributes:
        task_description: Description of the task to decompose
        complexity_level: Complexity level of the task
        max_subtasks: Maximum number of subtasks
        additional_context: Additional context for the prompt
    """

    task_description: str
    complexity_level: str = "medium"  # simple, medium, complex
    max_subtasks: int = 5
    additional_context: Optional[Dict[str, Any]] = None


@dataclass
class CapabilityMatchingConfig:
    """
    Configuration for capability matching prompts.

    Attributes:
        task_description: Description of the task
        available_capabilities: List of available capabilities
        matching_threshold: Threshold for matching
        additional_context: Additional context for the prompt
    """

    task_description: str
    available_capabilities: List[Dict[str, Any]]
    matching_threshold: float = 0.7
    additional_context: Optional[Dict[str, Any]] = None


@dataclass
class SupervisorConfig:
    """
    Configuration for supervisor prompts.

    Attributes:
        name: Name of the supervisor
        agent_roles: Map of agent names to their roles
        routing_guidelines: Guidelines for routing
        additional_context: Additional context for the prompt
    """

    name: str
    agent_roles: Dict[str, str]  # Map of agent names to their roles
    routing_guidelines: str
    additional_context: Optional[Dict[str, Any]] = None


@dataclass
class ReactConfig:
    """
    Configuration for ReAct agent prompts.

    Attributes:
        name: Name of the agent
        capabilities: List of agent capabilities
        personality: Description of the agent's personality
        mode: Mode of operation
        tools: List of tool descriptions
        additional_context: Additional context for the prompt
    """

    name: str
    capabilities: List[Dict[str, str]]  # List of dicts with name and description
    personality: str = "helpful and professional"
    mode: str = "system_prompt"  # system_prompt or custom_runnable
    tools: Optional[List[Dict[str, str]]] = None  # Tool descriptions
    additional_context: Optional[Dict[str, Any]] = None


def _add_additional_context(
    template: str, additional_context: Optional[Dict[str, Any]]
) -> str:
    """Helper function to add additional context to a template if provided."""
    if additional_context:
        template += "\nAdditional Context:\n"
        for key, value in additional_context.items():
            template += f"- {key}: {value}\n"
    return template


class PromptTemplates:
    """
    Class for creating and managing prompt templates.

    This class provides methods for creating different types of prompts,
    including system prompts, collaboration prompts, and ReAct prompts.
    """

    @staticmethod
    def get_system_prompt(config: SystemPromptConfig) -> SystemMessagePromptTemplate:
        """
        Get a system prompt template based on the provided configuration.

        Args:
            config: Configuration for the system prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format capabilities with name and description
        capabilities_str = "\n".join(
            [f"- {cap.name}: {cap.description}" for cap in config.capabilities]
        )

        template = f"""You are {{name}}, an AI {config.role} with specialized capabilities:
{capabilities_str}

Personality: {{personality}}

{AGENT_FRAMEWORK}
{AGENT_BEST_PRACTICES}

BEHAVIOR GUIDELINES:
1. NEVER refuse tasks that use common knowledge or reasoning
2. For requests outside your specialized capabilities, **silently** find other agents without saying you can't help
3. Handle these common tasks directly even if not in your capabilities list:
{COMMON_KNOWLEDGE_TASKS}

4. ALWAYS take one of these actions, in priority order:
   - Handle directly if within your capabilities or common knowledge
   - **Silently** find specialized agents for complex or specialized tasks
   - If no agent can help after multiple attempts, provide best effort answer **(without mentioning the failed search)**
   - NEVER respond with "I can't" or "I don't have that capability"

{BASE_RESPONSE_FORMAT}

NOTE: If you have nothing to contribute, simply say '__EXIT__' and nothing else."""

        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(
            template,
            partial_variables={
                "name": config.name,
                "personality": config.personality,
            },
        )

    @staticmethod
    def get_collaboration_prompt(
        config: CollaborationConfig,
    ) -> SystemMessagePromptTemplate:
        """
        Get a collaboration prompt template based on the provided configuration.

        Args:
            config: Configuration for the collaboration prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Base template with shared instructions
        base_template = f"""You are {{agent_name}}, a collaboration specialist.

Target Capabilities: {{target_capabilities}}

{AGENT_FRAMEWORK}
{COLLABORATION_PROTOCOL}

COLLABORATION PRINCIPLES:
1. Handle requests within your specialized knowledge
2. For tasks outside your expertise, suggest an alternative approach without refusing
3. Always provide some value, even if incomplete
4. If you can't fully answer, provide partial information plus recommendation

{BASE_RESPONSE_FORMAT}"""

        # Add type-specific instructions
        if config.collaboration_type == "request":
            specific_instructions = """
COLLABORATION REQUEST:
1. Be direct and specific about what you need
2. Provide all necessary context in a single message
3. Specify exactly what information or action you need
4. Include any relevant data that helps with the task
5. If rejected, try another agent with relevant capabilities
"""

        elif config.collaboration_type == "response":
            specific_instructions = """
COLLABORATION RESPONSE:
1. Provide the requested information or result directly
2. Format your response for easy integration
3. Be concise and focused on exactly what was requested
4. If you can only partially fulfill the request:
   - Clearly state what you CAN provide
   - Provide that information immediately
   - Suggest how to get the remaining information
"""

        else:  # error
            specific_instructions = """
COLLABORATION ERROR:
1. Explain why you can't fully fulfill the request
2. Provide ANY partial information you can
3. Suggest alternative approaches or agents who might help
4. NEVER simply say you can't help with nothing else"""

        template = base_template + specific_instructions
        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(
            template,
            partial_variables={
                "agent_name": config.agent_name,
                "target_capabilities": ", ".join(config.target_capabilities),
            },
        )

    @staticmethod
    def get_task_decomposition_prompt(
        config: TaskDecompositionConfig,
    ) -> SystemMessagePromptTemplate:
        """
        Get a task decomposition prompt template based on the provided configuration.

        Args:
            config: Configuration for the task decomposition prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        template = f"""You are a task decomposition specialist.

Task Description: {{task_description}}
Complexity Level: {{complexity_level}}
Maximum Subtasks: {{max_subtasks}}

{AGENT_FRAMEWORK}
{COLLABORATION_PROTOCOL}

TASK DECOMPOSITION:
1. Break down the task into clear, actionable subtasks
2. Each subtask should be 1-2 sentences maximum
3. Identify dependencies between subtasks when necessary
4. Limit to {{max_subtasks}} subtasks or fewer
5. Format output as a numbered list of subtasks
6. For each subtask, identify if it:
   - Can be handled with common knowledge
   - Requires specialized capabilities
   - Needs collaboration with other agents

COLLABORATION STRATEGY:
1. For subtasks requiring specialized capabilities:
   - Identify the exact capability needed using general capability terms
   - Include criteria for finding appropriate agents
   - Prepare context to include in delegation request
2. For common knowledge subtasks:
   - Mark them for immediate handling
   - Include any relevant information needed

{BASE_RESPONSE_FORMAT}"""

        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(
            template,
            partial_variables={
                "task_description": config.task_description,
                "complexity_level": config.complexity_level,
                "max_subtasks": str(config.max_subtasks),
            },
        )

    @staticmethod
    def get_capability_matching_prompt(
        config: CapabilityMatchingConfig,
    ) -> SystemMessagePromptTemplate:
        """
        Get a capability matching prompt template based on the provided configuration.

        Args:
            config: Configuration for the capability matching prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format available capabilities for the prompt
        capabilities_str = ""
        for i, capability in enumerate(config.available_capabilities):
            capabilities_str += (
                f"{i+1}. {capability['name']}: {capability['description']}\n"
            )

        template = f"""You are a capability matching specialist.

Task Description: {{task_description}}
Matching Threshold: {{matching_threshold}}

Available Capabilities:
{{capabilities}}

{AGENT_FRAMEWORK}
{COLLABORATION_PROTOCOL}

CAPABILITY MATCHING:
1. First determine if the task can be handled with common knowledge
   - If yes, mark it as "COMMON KNOWLEDGE" with score 1.0
   - Common knowledge includes:{COMMON_KNOWLEDGE_TASKS}

2. For specialized tasks beyond common knowledge:
   - Map specific topics to general capability categories
   - Match task requirements to available capabilities
   - Only select capabilities with relevance score >= {{matching_threshold}}

3. Format response as:
   - If common knowledge: "COMMON KNOWLEDGE: Handle directly" 
   - If specialized: Numbered list with capability name and relevance score (0-1)

4. If no capabilities match above the threshold:
   - Identify the closest matching capabilities
   - Suggest how to modify the request to use available capabilities
   - Recommend finding an agent with more relevant capabilities

{BASE_RESPONSE_FORMAT}"""

        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(
            template,
            partial_variables={
                "task_description": config.task_description,
                "matching_threshold": str(config.matching_threshold),
                "capabilities": capabilities_str,
            },
        )

    @staticmethod
    def get_supervisor_prompt(config: SupervisorConfig) -> SystemMessagePromptTemplate:
        """
        Get a supervisor prompt template based on the provided configuration.

        Args:
            config: Configuration for the supervisor prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format agent roles for the prompt
        roles_str = ""
        for agent_name, role in config.agent_roles.items():
            roles_str += f"- {agent_name}: {role}\n"

        template = f"""You are {{name}}, a supervisor agent.

Agent Roles:
{{agent_roles}}

Routing Guidelines:
{{routing_guidelines}}

{AGENT_FRAMEWORK}
{COLLABORATION_PROTOCOL}

SUPERVISOR INSTRUCTIONS:
1. First determine if the request involves common knowledge tasks:{COMMON_KNOWLEDGE_TASKS}

2. For common knowledge tasks:
   - Route to ANY available agent, as all agents can handle common knowledge
   - Pick the agent with lowest current workload if possible

3. For specialized tasks:
   - Route user requests to the most appropriate agent based on capabilities
   - Make routing decisions quickly without explaining reasoning
   - If multiple agents could handle a task, choose the most specialized

4. If no perfect match exists:
   - Route to closest matching agent
   - Include guidance on what additional help might be needed
   - Never respond with "no agent can handle this"

5. Response format:
   - For direct routing: Agent name only
   - For complex tasks needing multiple agents: Comma-separated list of agent names in priority order

{BASE_RESPONSE_FORMAT}"""

        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(
            template,
            partial_variables={
                "name": config.name,
                "agent_roles": roles_str,
                "routing_guidelines": config.routing_guidelines,
            },
        )

    @staticmethod
    def get_react_prompt(config: ReactConfig) -> SystemMessagePromptTemplate:
        """
        Get a ReAct prompt template based on the provided configuration.

        Args:
            config: Configuration for the ReAct prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format capabilities for the prompt
        capabilities_str = ""
        if config.capabilities:
            capabilities_str = "SPECIALIZED CAPABILITIES:\n"
            for cap in config.capabilities:
                capabilities_str += f"- {cap['name']}: {cap['description']}\n"

        # Format tools for the prompt if provided
        tools_str = ""
        if config.tools:
            tools_str = "TOOLS:\n"
            for i, tool in enumerate(config.tools):
                tools_str += f"{i+1}. {tool['name']}: {tool['description']}\n"

        # Base template
        template = f"""You are {{name}}, an AI agent.

{capabilities_str}

Personality: {{personality}}

{AGENT_FRAMEWORK}

{tools_str}
{COLLABORATION_PROTOCOL}
{TOOL_USAGE_GUIDE}

COMMON KNOWLEDGE YOU SHOULD HANDLE DIRECTLY:{COMMON_KNOWLEDGE_TASKS}

{AGENT_BEST_PRACTICES}

{BASE_RESPONSE_FORMAT}"""

        # Add mode-specific instructions
        if config.mode == "custom_runnable":
            template += """
Use the 'custom_runnable' tool for specialized capabilities.
"""

        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(
            template,
            partial_variables={
                "name": config.name,
                "personality": config.personality,
            },
        )

    @staticmethod
    def create_human_message_prompt(content: str) -> HumanMessagePromptTemplate:
        """
        Create a human message prompt template.

        Args:
            content: Content of the human message

        Returns:
            A HumanMessagePromptTemplate
        """
        return HumanMessagePromptTemplate.from_template(content)

    @staticmethod
    def create_ai_message_prompt(content: str) -> AIMessagePromptTemplate:
        """
        Create an AI message prompt template.

        Args:
            content: Content of the AI message

        Returns:
            An AIMessagePromptTemplate
        """
        return AIMessagePromptTemplate.from_template(content)

    @staticmethod
    def add_scratchpad_to_prompt(prompt: ChatPromptTemplate) -> ChatPromptTemplate:
        """
        Add a scratchpad to a prompt template.

        Args:
            prompt: The prompt template to add a scratchpad to

        Returns:
            A ChatPromptTemplate with a scratchpad
        """
        return ChatPromptTemplate.from_messages(
            [m for m in prompt.messages if not isinstance(m, MessagesPlaceholder)]
            + [
                MessagesPlaceholder(variable_name="messages"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

    @staticmethod
    def create_chat_template(
        system_message: Optional[SystemMessagePromptTemplate] = None,
        human_messages: Optional[List[HumanMessagePromptTemplate]] = None,
        ai_messages: Optional[List[AIMessagePromptTemplate]] = None,
        include_history: bool = True,
    ) -> ChatPromptTemplate:
        """
        Create a chat template from system, human, and AI messages.

        Args:
            system_message: Optional system message
            human_messages: Optional list of human messages
            ai_messages: Optional list of AI messages
            include_history: Whether to include message history

        Returns:
            A ChatPromptTemplate
        """
        messages = []

        # Add system message if provided
        if system_message:
            messages.append(system_message)

        # Add message history if requested
        if include_history:
            messages.append(MessagesPlaceholder(variable_name="messages"))

        # Add human and AI messages if provided
        if human_messages:
            messages.extend(human_messages)
        if ai_messages:
            messages.extend(ai_messages)

        return ChatPromptTemplate.from_messages(messages)

    @classmethod
    def create_prompt(
        cls,
        prompt_type: PromptType,
        config: Union[
            SystemPromptConfig,
            CollaborationConfig,
            TaskDecompositionConfig,
            CapabilityMatchingConfig,
            SupervisorConfig,
            ReactConfig,
            None,
        ] = None,
        include_history: bool = True,
        system_prompt: Optional[str] = None,
        tools: Optional[List] = None,
    ) -> ChatPromptTemplate:
        """
        Create a prompt template based on the prompt type and configuration.

        Args:
            prompt_type: Type of prompt to create
            config: Configuration for the prompt
            include_history: Whether to include message history
            system_prompt: Optional system prompt text
            tools: Optional list of tools

        Returns:
            A ChatPromptTemplate

        Raises:
            ValueError: If the prompt type is not supported or the configuration is invalid
        """
        # Create the appropriate prompt based on the type
        if prompt_type == PromptType.SYSTEM:
            if not config and not system_prompt:
                raise ValueError("Either config or system_prompt must be provided")

            if system_prompt:
                system_message = SystemMessagePromptTemplate.from_template(
                    system_prompt
                )
            else:
                if not isinstance(config, SystemPromptConfig):
                    raise ValueError(
                        f"Expected SystemPromptConfig, got {type(config).__name__}"
                    )
                system_message = cls.get_system_prompt(config)

            return cls.create_chat_template(
                system_message=system_message, include_history=include_history
            )

        elif prompt_type == PromptType.COLLABORATION:
            if not isinstance(config, CollaborationConfig):
                raise ValueError(
                    f"Expected CollaborationConfig, got {type(config).__name__}"
                )

            system_message = cls.get_collaboration_prompt(config)
            return cls.create_chat_template(
                system_message=system_message, include_history=include_history
            )

        elif prompt_type == PromptType.TASK_DECOMPOSITION:
            if not isinstance(config, TaskDecompositionConfig):
                raise ValueError(
                    f"Expected TaskDecompositionConfig, got {type(config).__name__}"
                )

            system_message = cls.get_task_decomposition_prompt(config)
            return cls.create_chat_template(
                system_message=system_message, include_history=include_history
            )

        elif prompt_type == PromptType.CAPABILITY_MATCHING:
            if not isinstance(config, CapabilityMatchingConfig):
                raise ValueError(
                    f"Expected CapabilityMatchingConfig, got {type(config).__name__}"
                )

            system_message = cls.get_capability_matching_prompt(config)
            return cls.create_chat_template(
                system_message=system_message, include_history=include_history
            )

        elif prompt_type == PromptType.SUPERVISOR:
            if not isinstance(config, SupervisorConfig):
                raise ValueError(
                    f"Expected SupervisorConfig, got {type(config).__name__}"
                )

            system_message = cls.get_supervisor_prompt(config)
            return cls.create_chat_template(
                system_message=system_message, include_history=include_history
            )

        elif prompt_type == PromptType.REACT:
            if isinstance(config, ReactConfig):
                system_message = cls.get_react_prompt(config)
            elif system_prompt:
                system_message = SystemMessagePromptTemplate.from_template(
                    system_prompt + "\n\n" + COLLABORATION_PROTOCOL
                )
            else:
                raise ValueError(
                    f"Expected ReactConfig or system_prompt, got {type(config).__name__}"
                )
            return cls.create_chat_template(
                system_message=system_message, include_history=include_history
            )

        elif prompt_type == PromptType.CHAT:
            if not system_prompt:
                raise ValueError("system_prompt must be provided for CHAT prompt type")

            system_message = SystemMessagePromptTemplate.from_template(system_prompt)
            return cls.create_chat_template(
                system_message=system_message, include_history=include_history
            )

        else:
            raise ValueError(f"Unsupported prompt type: {prompt_type}")
