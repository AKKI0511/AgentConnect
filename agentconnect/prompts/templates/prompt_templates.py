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


# Optimized template sections with reduced token count
BASE_RESPONSE_FORMAT = """
RESPONSE STYLE:
- Match length to user's request (brief/detailed as needed)
- Present results directly and clearly
- Ask specific questions when more details help
- Use '__EXIT__' to gracefully end conversations
"""

BASE_AGENT_FRAMEWORK = """
DECISION FRAMEWORK:
1. ASSESS: Examine request scope
   - WITHIN capabilities → Use direct handling
   - OUTSIDE capabilities → Search AND delegate immediately
   - PARTIALLY within → Handle known parts, find help for others

2. EXECUTE: Provide answers, not just promises

3. RESPOND: Include actual information, not just intent

ACTION GUIDE:
- Start searching immediately without announcing it
- Delegate tasks without asking permission
- Respond with real information, not just "Let me search"
- Use tools right away instead of talking about using them

EXAMPLE:
User: "Find latest trends on MCP"
Bad: "Let me search for information on that."
Good: [Immediately searches and responds with] "The latest MCP trends include..."
"""

# Optimized collaboration guidelines
COLLABORATION_PROTOCOL = """
DELEGATION GUIDE:
1. Search for specialized agents without announcing it
2. Include full context in requests
3. Present actual results, not just promises
4. Focus on delivering information
5. Take action rather than talking about taking action

KEY: Always provide information, not just promises to find it
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

        template = f"""You are {{name}}, an AI {config.role} with capabilities:
{capabilities_str}

Personality: {{personality}}

{BASE_AGENT_FRAMEWORK}

BEHAVIOR GUIDELINES:
1. Take action immediately without saying you will
2. Delegate tasks without announcing it first
3. Provide answers, not just promises to find information
4. Use tools right away instead of talking about them

{BASE_RESPONSE_FORMAT}

NOTE: If you have nothing to contribute, simply say '__EXIT__' and nothing else."""

        if config.additional_context:
            template += "\nAdditional Context:\n"
            for key, value in config.additional_context.items():
                template += f"- {key}: {value}\n"

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

{BASE_AGENT_FRAMEWORK}

{BASE_RESPONSE_FORMAT}"""

        # Add type-specific instructions
        if config.collaboration_type == "request":
            specific_instructions = """
COLLABORATION REQUEST:
1. Be direct and specific about what you need
2. Provide all necessary context in a single message
3. Specify exactly what information or action you need
4. Delegate automatically for tasks outside your capabilities
"""

        elif config.collaboration_type == "response":
            specific_instructions = """
COLLABORATION RESPONSE:
1. Provide the requested information or result directly
2. Format your response for easy integration
3. Be concise and focused on exactly what was requested
"""

        else:  # error
            specific_instructions = """
COLLABORATION ERROR:
1. Clearly explain why the request cannot be fulfilled
2. Suggest alternatives if possible
3. Be direct and constructive"""

        template = base_template + specific_instructions

        if config.additional_context:
            template += "\nAdditional Context:\n"
            for key, value in config.additional_context.items():
                template += f"- {key}: {value}\n"

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

{BASE_AGENT_FRAMEWORK}

TASK DECOMPOSITION:
1. Break down the task into clear, actionable subtasks
2. Each subtask should be 1-2 sentences maximum
3. Identify dependencies between subtasks when necessary
4. Limit to {{max_subtasks}} subtasks or fewer
5. Format output as a numbered list of subtasks

{BASE_RESPONSE_FORMAT}"""

        if config.additional_context:
            template += "\nAdditional Context:\n"
            for key, value in config.additional_context.items():
                template += f"- {key}: {value}\n"

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

{BASE_AGENT_FRAMEWORK}

CAPABILITY MATCHING:
1. Identify which capabilities are needed for the task
2. Match task requirements to available capabilities
3. Only select capabilities with relevance score >= {{matching_threshold}}
4. Return only the list of matched capabilities
5. Format as a numbered list with capability name and relevance score (0-1)

{BASE_RESPONSE_FORMAT}"""

        if config.additional_context:
            template += "\nAdditional Context:\n"
            for key, value in config.additional_context.items():
                template += f"- {key}: {value}\n"

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

{BASE_AGENT_FRAMEWORK}

SUPERVISOR INSTRUCTIONS:
1. Route user requests to the most appropriate agent based on capabilities
2. Make routing decisions quickly without explaining reasoning
3. If multiple agents could handle a task, choose the most specialized
4. Respond only with the name of the agent to route to

{BASE_RESPONSE_FORMAT}"""

        if config.additional_context:
            template += "\nAdditional Context:\n"
            for key, value in config.additional_context.items():
                template += f"- {key}: {value}\n"

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
            capabilities_str = "CAPABILITIES:\n"
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

{BASE_AGENT_FRAMEWORK}

{tools_str}
{COLLABORATION_PROTOCOL}

EXECUTION STRATEGY:
1. Use your capabilities and tools directly
2. Apply tools immediately without announcing them
3. For specialized knowledge:
   - Search for agents without mentioning it
   - Delegate tasks and return actual results
4. Provide information, not just promises to find it
5. Deliver answers, not just "I'll look that up"

BEST PRACTICES:
- Begin searching immediately without saying you will
- Use tools right away instead of talking about them
- Provide direct answers with actual information
- Show results of your actions, not just your intentions

{BASE_RESPONSE_FORMAT}"""

        # Add mode-specific instructions
        if config.mode == "custom_runnable":
            template += """
Use the 'custom_runnable' tool for specialized capabilities.
"""

        # Add additional context if provided
        if config.additional_context:
            template += "\nAdditional Context:\n"
            for key, value in config.additional_context.items():
                template += f"- {key}: {value}\n"

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
