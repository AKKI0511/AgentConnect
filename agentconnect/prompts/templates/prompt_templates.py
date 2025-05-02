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
NOTE: During a collaboration with another agent, simply say '__EXIT__' and nothing else if you have nothing to contribute.
"""

# Core agent prompt template that serves as the foundation for all prompts
# This contains the common elements that should be present in all agent prompts
CORE_AGENT_PROMPT = """
You are {name}, an autonomous AI agent operating in a decentralized network of independent agents.

Personality: {personality}

Your primary goal is to accomplish tasks efficiently, either by using your own capabilities or by collaborating with other agents in the network.

- If you cannot fulfill a request directly, **immediately and silently use the `search_for_agents` tool** to find other agents with the required capabilities and delegate tasks to them as needed. **Do not ask for permission before searching.**
- Directly handle tasks solvable with your core language model capabilities (e.g., text generation, summarization, general knowledge questions) whenever possible.
- Communicate and collaborate with other agents to achieve the best possible outcome for each request.
- Always analyze tool responses and decide the next best action based on the information available.
- Avoid sending collaboration requests to yourself or to human agents.
- Be concise, professional, and helpful in all interactions.
"""


# Helper function to build payment info string
def get_payment_info(enable_payments: bool, payment_token_symbol: Optional[str]) -> str:
    """Generate payment info string if payments are enabled."""
    if enable_payments and payment_token_symbol:
        return f"\nPayment enabled. Token: {payment_token_symbol}"
    return ""


def _add_additional_context(
    template: str, additional_context: Optional[Dict[str, Any]]
) -> str:
    """Helper function to add additional context to a template if provided."""
    if additional_context:
        template += "\nAdditional Context:\n"
        for key, value in additional_context.items():
            template += f"- {key}: {value}\n"
    return template


@dataclass
class SystemPromptConfig:
    """
    Configuration for system prompts.

    Attributes:
        name: Name of the agent
        capabilities: List of agent capabilities
        personality: Description of the agent's personality
        additional_context: Additional context for the prompt
        role: Role of the agent
        enable_payments: Whether payment capabilities are enabled
        payment_token_symbol: Symbol of the token used for payments
    """

    name: str
    capabilities: List[Capability]  # Now accepts a list of Capability objects
    personality: str = "helpful and professional"
    additional_context: Optional[Dict[str, Any]] = None
    role: str = "assistant"
    enable_payments: bool = False
    payment_token_symbol: Optional[str] = None


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
        enable_payments: Whether payment capabilities are enabled
        payment_token_symbol: Symbol of the token used for payments (e.g., "ETH", "USDC")
        role: Role of the agent
        additional_context: Additional context for the prompt
    """

    name: str
    capabilities: List[Dict[str, str]]  # List of dicts with name and description
    personality: str = "helpful and professional"
    mode: str = "system_prompt"  # system_prompt or custom_runnable
    role: str = "agent"
    enable_payments: bool = False
    payment_token_symbol: Optional[str] = None
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
        Generates a system prompt for a standard agent.
        Uses the core agent prompt structure.

        Args:
            config: Configuration for the system prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format capabilities with name and description
        capabilities_str = "\n".join(
            [
                f"- **{cap.name.replace('_', ' ').title()}:** You can: {cap.description}"
                for cap in config.capabilities
            ]
        )
        if not capabilities_str:
            capabilities_str = "No specific capabilities listed. Handle tasks using inherent knowledge or delegate."

        # Add payment info if enabled
        payment_info = get_payment_info(
            config.enable_payments, config.payment_token_symbol
        )

        # Construct the prompt using the core template
        template = CORE_AGENT_PROMPT.format(
            name=config.name,
            personality=config.personality,
        )

        # Add capabilities and payment info
        template += f"\nUnique Capabilities you can perform using your internal reasoning:\n{capabilities_str}"
        template += payment_info

        # Add response format
        template += f"\n{BASE_RESPONSE_FORMAT}"

        # Add any additional context
        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(template)

    @staticmethod
    def get_collaboration_prompt(
        config: CollaborationConfig,
    ) -> SystemMessagePromptTemplate:
        """
        Get a collaboration prompt template based on the provided configuration.
        Uses the core agent prompt structure with collaboration-specific instructions.

        Args:
            config: Configuration for the collaboration prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format capabilities for collaboration
        capabilities_str = f"- **Collaboration:** You can: specialize in {', '.join(config.target_capabilities)}"

        # Construct the prompt using the core template
        template = CORE_AGENT_PROMPT.format(
            name=config.agent_name,
            personality="helpful and collaborative",
        )

        # Add capabilities
        template += f"\nUnique Capabilities you can perform using your internal reasoning:\n{capabilities_str}"

        # Add collaboration-specific instructions based on type
        if config.collaboration_type == "request":
            template += """
\nCOLLABORATION REQUEST INSTRUCTIONS:
1. Be direct and specific about what you need
2. Provide all necessary context in a single message
3. Specify exactly what information or action you need
4. Include any relevant data that helps with the task
5. If rejected, try another agent with relevant capabilities
"""
        elif config.collaboration_type == "response":
            template += """
\nCOLLABORATION RESPONSE INSTRUCTIONS:
1. Provide the requested information or result directly
2. Format your response for easy integration
3. Be concise and focused on exactly what was requested
4. If you can only partially fulfill the request:
   - Clearly state what you CAN provide
   - Provide that information immediately
   - Suggest how to get the remaining information
"""
        else:  # error
            template += """
\nCOLLABORATION ERROR INSTRUCTIONS:
1. Explain why you can't fully fulfill the request
2. Provide ANY partial information you can
3. Suggest alternative approaches or agents who might help
4. NEVER simply say you can't help with nothing else
"""

        # Add response format
        template += f"\n{BASE_RESPONSE_FORMAT}"

        # Add any additional context
        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(template)

    @staticmethod
    def get_task_decomposition_prompt(
        config: TaskDecompositionConfig,
    ) -> SystemMessagePromptTemplate:
        """
        Get a task decomposition prompt template based on the provided configuration.
        Uses the core agent prompt structure with task decomposition-specific instructions.

        Args:
            config: Configuration for the task decomposition prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Construct the prompt using the core template
        template = CORE_AGENT_PROMPT.format(
            name="Task Decomposition Agent",
            personality="analytical and methodical",
        )

        # Add capabilities
        template += (
            "\nUnique Capabilities you can perform using your internal reasoning:"
        )
        template += "\n- **Task Decomposition:** You can: break down complex tasks into manageable subtasks"

        # Add task-specific context
        template += f"\n\nTask Description: {config.task_description}"
        template += f"\nComplexity Level: {config.complexity_level}"
        template += f"\nMaximum Subtasks: {config.max_subtasks}"

        # Add task decomposition-specific instructions
        template += """
\nTASK DECOMPOSITION INSTRUCTIONS:
1. Break down the task into clear, actionable subtasks
2. Each subtask should be 1-2 sentences maximum
3. Identify dependencies between subtasks when necessary
4. Limit subtasks to the maximum number specified or fewer
5. Format output as a numbered list of subtasks
6. For each subtask, identify if it:
   - Can be handled with your inherent knowledge
   - Requires specialized capabilities/tools
   - Needs collaboration with other agents
"""

        # Add response format
        template += f"\n{BASE_RESPONSE_FORMAT}"

        # Add any additional context
        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(template)

    @staticmethod
    def get_capability_matching_prompt(
        config: CapabilityMatchingConfig,
    ) -> SystemMessagePromptTemplate:
        """
        Get a capability matching prompt template based on the provided configuration.
        Uses the core agent prompt structure with capability matching-specific instructions.

        Args:
            config: Configuration for the capability matching prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format available capabilities for context
        available_capabilities = "\n".join(
            [
                f"- {cap['name']}: {cap['description']}"
                for cap in config.available_capabilities
            ]
        )

        # Construct the prompt using the core template
        template = CORE_AGENT_PROMPT.format(
            name="Capability Matching Agent",
            personality="analytical and precise",
        )

        # Add capabilities
        template += (
            "\nUnique Capabilities you can perform using your internal reasoning:"
        )
        template += "\n- **Capability Matching:** You can: match tasks to appropriate capabilities and tools"

        # Add task-specific context
        template += f"\n\nTask Description: {config.task_description}"
        template += f"\nMatching Threshold: {config.matching_threshold}"
        template += f"\n\nAvailable Capabilities/Tools:\n{available_capabilities}"

        # Add capability matching-specific instructions
        template += f"""
\nCAPABILITY MATCHING INSTRUCTIONS:
1. First determine if the task can be handled using general reasoning and inherent knowledge (without specific listed tools).
   - If yes, mark it as "INHERENT KNOWLEDGE" with score 1.0

2. For specialized tasks requiring specific tools:
   - Match task requirements to the available capabilities/tools listed above.
   - Only select capabilities with relevance score >= {config.matching_threshold}

3. Format response as:
   - If inherent knowledge: "INHERENT KNOWLEDGE: Handle directly"
   - If specialized tool needed: Numbered list with capability/tool name and relevance score (0-1)

4. If no capabilities/tools match above the threshold and it's not inherent knowledge:
   - Identify the closest matching capabilities/tools.
   - Suggest how to modify the request to use available tools.
   - Recommend finding an agent via delegation with more relevant capabilities.
"""

        # Add response format
        template += f"\n{BASE_RESPONSE_FORMAT}"

        # Add any additional context
        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(template)

    @staticmethod
    def get_supervisor_prompt(config: SupervisorConfig) -> SystemMessagePromptTemplate:
        """
        Get a supervisor prompt template based on the provided configuration.
        Uses the core agent prompt structure with supervisor-specific instructions.

        Args:
            config: Configuration for the supervisor prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format agent roles for context
        agent_roles = "\n".join(
            [
                f"- {agent_name}: {role}"
                for agent_name, role in config.agent_roles.items()
            ]
        )

        # Construct the prompt using the core template
        template = CORE_AGENT_PROMPT.format(
            name=config.name,
            personality="decisive and authoritative",
        )

        # Add capabilities
        template += (
            "\nUnique Capabilities you can perform using your internal reasoning:"
        )
        template += "\n- **Supervision:** You can: route tasks to appropriate agents based on their capabilities"

        # Add supervisor-specific context
        template += f"\n\nAgent Roles:\n{agent_roles}"
        template += f"\n\nRouting Guidelines:\n{config.routing_guidelines}"

        # Add supervisor-specific instructions
        template += """
\nSUPERVISOR INSTRUCTIONS:
1. Determine if the request can likely be handled by an agent using its inherent knowledge/general reasoning.

2. If yes (inherent knowledge task):
   - Route to ANY available agent, as all agents possess base LLM capabilities.
   - Pick the agent with lowest current workload if possible.

3. If no (requires specialized tools/capabilities):
   - Route user requests to the agent whose listed capabilities/tools best match the task.
   - Make routing decisions quickly without explaining reasoning.
   - If multiple agents could handle a task, choose the most specialized.

4. If no agent has matching specialized tools and it's not an inherent knowledge task:
   - Route to the agent whose capabilities are closest.
   - Include guidance on what additional help might be needed (potentially via delegation by the receiving agent).
   - Never respond with "no agent can handle this".

5. Response format:
   - For direct routing: Agent name only
   - For complex tasks needing multiple agents: Comma-separated list of agent names in priority order
"""

        # Add response format
        template += f"\n{BASE_RESPONSE_FORMAT}"

        # Add any additional context
        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(template)

    @staticmethod
    def get_react_prompt(config: ReactConfig) -> SystemMessagePromptTemplate:
        """
        Generates a system prompt for a ReAct agent.
        This is the canonical template that other prompts should follow structurally.
        """
        capabilities_list = config.capabilities or []
        formatted_capabilities = []
        for cap in capabilities_list:
            name = cap.get("name", "N/A")
            description = cap.get("description", "N/A")
            # Format name: split by '_', capitalize each part, join with space
            formatted_name = (
                " ".join(word.capitalize() for word in name.split("_"))
                if name != "N/A"
                else "N/A"
            )
            # Add prefix to description
            prefixed_description = f"You can: {description}"
            formatted_capabilities.append(
                f"- **{formatted_name}:** {prefixed_description}"
            )

        capabilities_str = "\n".join(formatted_capabilities)
        if not capabilities_str:
            capabilities_str = "No specific capabilities listed. Handle tasks using inherent knowledge or delegate."

        # Add payment info if enabled
        payment_info = get_payment_info(
            config.enable_payments, config.payment_token_symbol
        )

        # This is the canonical template that should be followed structurally
        template = f"""
You are {config.name}, an autonomous AI agent operating in a decentralized network of independent agents.

Personality: {config.personality}

Your primary goal is to accomplish tasks efficiently, either by using your own capabilities or by collaborating with other agents in the network.

- If you cannot fulfill a request directly, **immediately and silently use the `search_for_agents` tool** to find other agents with the required capabilities and delegate tasks to them as needed. **Do not ask for permission before searching.**
- Directly handle tasks solvable with your core language model capabilities (e.g., text generation, summarization, general knowledge questions) whenever possible.
- Communicate and collaborate with other agents to achieve the best possible outcome for each request.
- Always analyze tool responses and decide the next best action based on the information available.
- Avoid sending collaboration requests to yourself or to human agents.
- Be concise, professional, and helpful in all interactions.

Unique Capabilities you can perform using your internal reasoning:
{capabilities_str}
{payment_info}
"""

        # Add any additional context
        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(template)

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
    ) -> ChatPromptTemplate:
        """
        Create a prompt template based on the prompt type and configuration.

        Args:
            prompt_type: Type of prompt to create
            config: Configuration for the prompt
            include_history: Whether to include message history
            system_prompt: Optional system prompt text

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
                    system_prompt
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
