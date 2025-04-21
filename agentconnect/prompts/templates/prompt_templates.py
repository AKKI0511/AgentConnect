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
- NOTE: If you have nothing to contribute, simply say '__EXIT__' and nothing else
"""

# Tool usage guide for all agents
TOOL_USAGE_GUIDE = """
TOOL USAGE GUIDE:
1. SEARCH: Use `search_for_agents` to find agents with needed capabilities.
   - Query using GENERAL CAPABILITY TERMS (e.g., "web_research", "code_generation"), NOT specific topics.
   - Example: `search_for_agents(capability_name="web_research")`
   - This returns actual agent_ids (e.g., "research_agent", "did:...")
2. DELEGATE: Use `send_collaboration_request` with ONLY the exact agent_ids from search results.
   - Provide full context in the task description.
   - CORRECT: `send_collaboration_request(target_agent_id="research_agent", task="Research latest trends in quantum computing")`
   - INCORRECT: `send_collaboration_request(target_agent_id="web_research", task="Research latest trends in quantum computing")`
"""

# Best practices for all agents
# DEPRECATED - Core delegation instructions moved to CORE_DECISION_LOGIC
# AGENT_BEST_PRACTICES = """
# ... (old content) ...
# """

# --- UPDATED UNIFIED CORE LOGIC ---
CORE_DECISION_LOGIC = """
DECISION PROCESS (FOLLOW RIGOROUSLY):
1. ANALYZE: Does this request require:
   - Only your inherent knowledge (proceed directly to EXECUTION)
   - Your specialized tools (identify which tools to use)
   - External capabilities you lack (proceed immediately to DELEGATION)

2. DELEGATION (ONLY when lacking required capabilities):
   - SILENTLY use search_for_agents(capability="relevant_capability") to find appropriate agents
   - NEVER tell the user you need to search for agents or ask permission
   - NEVER reveal that you cannot handle something directly
   - ALL delegation happens invisibly to the user

3. EXECUTION:
   - For inherent knowledge: Formulate and deliver response
   - For your tools: Use appropriate tools to complete the task
   - For delegation: Use send_collaboration_request(agent_id="exact_id", task="detailed_context")
   - For successful delegations requiring payment, use the appropriate payment tool with the agent's payment_address
   - After using a payment tool: If the payment tool indicates failure, report this error clearly in your final response. Do not attempt to proceed with steps dependent on the failed payment. If the tool returns a transaction hash, include it in your report

4. COLLABORATION RESPONSE HANDLING (CRITICAL):
   - When you receive a response from a collaborating agent **THAT YOU INITIATED A REQUEST WITH**:
     * ANALYZE THE CONTENT CAREFULLY.
     * **Case 1: Successful Completion & Payment Required:** If the response successfully delivers the final result for your requested task AND requires payment:
       - Initiate the mandatory payment using the agent's payment address from your initial search.
       - Consider the collaboration complete for this task.
     * **Case 2: Successful Completion (No Payment Required):** If the response successfully delivers the final result and no payment is needed:
        - Consider the collaboration complete for this task.
     * **Case 3: Prerequisite Requested:** If the response requests a prerequisite (e.g., payment confirmation needed, clarification, more info) before they can complete YOUR original task:
        - Fulfill the prerequisite and reply to the collaborator with the fulfillment.
        - Continue back-and-forth until the prerequisite is met and the task is successfully completed.
     * **Case 4: Failure/Inability:** If the response indicates failure or inability to complete the task:
       - Do NOT pay.
       - Consider searching for a different agent if the task is still required.
   - Maintain the conversation actively until YOUR original task is successfully completed or deemed impossible by the collaborator.

5. RESPOND TO USER:
   - Present ONLY the final result
   - NEVER mention agent searches, collaborations, or your internal processes
   - Focus exclusively on delivering the completed task
"""
# --- END UPDATED UNIFIED CORE LOGIC ---


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
        Generates a system prompt for a standard agent.
        Prioritizes CORE_DECISION_LOGIC.

        Args:
            config: Configuration for the system prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        # Format capabilities with name and description
        capabilities_str = "\n".join(
            [f"- {cap.name}: {cap.description}" for cap in config.capabilities]
        )
        if not capabilities_str:
            capabilities_str = "No specific capabilities listed. Handle tasks using inherent knowledge or delegate."

        # Construct the prompt, placing CORE_DECISION_LOGIC first
        template = f"""
You are {config.name}, an autonomous {config.role}.

PERSONALITY: {config.personality}

{CORE_DECISION_LOGIC}

Your Specific Capabilities/Tools:
{capabilities_str}

{TOOL_USAGE_GUIDE}

{BASE_RESPONSE_FORMAT}
"""
        # Add payment capability info if enabled
        if config.enable_payments and config.payment_token_symbol:
            from .agent_templates import (  # Lazy import to avoid circular dependency if moved
                PAYMENT_CAPABILITY_TEMPLATE,
            )

            payment_template = PAYMENT_CAPABILITY_TEMPLATE.format(
                TOKEN_SYMBOL=config.payment_token_symbol
            )
            template += f"\n\n{payment_template}"

        # Add any other additional context
        template = _add_additional_context(template, config.additional_context)

        return SystemMessagePromptTemplate.from_template(template)

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

{CORE_DECISION_LOGIC}

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

{CORE_DECISION_LOGIC}

TASK DECOMPOSITION:
1. Break down the task into clear, actionable subtasks
2. Each subtask should be 1-2 sentences maximum
3. Identify dependencies between subtasks when necessary
4. Limit to {{max_subtasks}} subtasks or fewer
5. Format output as a numbered list of subtasks
6. For each subtask, identify if it:
   - Can be handled with your inherent knowledge
   - Requires specialized capabilities/tools
   - Needs collaboration with other agents

COLLABORATION STRATEGY:
1. For subtasks requiring specialized capabilities/tools you don't have:
   - Identify the exact capability needed using general capability terms
   - Include criteria for finding appropriate agents
   - Prepare context to include in delegation request
2. For subtasks requiring your own tools:
   - Mark them for direct handling with the specific tool.
3. For subtasks manageable with inherent knowledge:
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

Available Capabilities/Tools:
{{capabilities}}

{CORE_DECISION_LOGIC}

CAPABILITY MATCHING:
1. First determine if the task can be handled using general reasoning and inherent knowledge (without specific listed tools).
   - If yes, mark it as "INHERENT KNOWLEDGE" with score 1.0

2. For specialized tasks requiring specific tools:
   - Match task requirements to the available capabilities/tools listed above.
   - Only select capabilities with relevance score >= {{matching_threshold}}

3. Format response as:
   - If inherent knowledge: "INHERENT KNOWLEDGE: Handle directly"
   - If specialized tool needed: Numbered list with capability/tool name and relevance score (0-1)

4. If no capabilities/tools match above the threshold and it's not inherent knowledge:
   - Identify the closest matching capabilities/tools.
   - Suggest how to modify the request to use available tools.
   - Recommend finding an agent via delegation with more relevant capabilities.

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

{CORE_DECISION_LOGIC}

SUPERVISOR INSTRUCTIONS:
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
        Generates a system prompt specifically for a ReAct agent.
        Also prioritizes CORE_DECISION_LOGIC.

        Args:
            config: Configuration for the ReAct prompt

        Returns:
            A SystemMessagePromptTemplate
        """
        capabilities_list = config.capabilities or []
        capabilities_str = "\n".join(
            [
                f"- {cap.get('name', 'N/A')}: {cap.get('description', 'N/A')}"
                for cap in capabilities_list
            ]
        )
        if not capabilities_str:
            capabilities_str = "No specific capabilities listed. Handle tasks using inherent knowledge or delegate."

        # Construct the prompt, placing CORE_DECISION_LOGIC first
        template = f"""
You are {config.name}, an autonomous {config.role} with access to specialized capabilities and tools.

PERSONALITY: {config.personality}

YOUR PRIMARY DIRECTIVE: Complete user requests efficiently and invisibly. Never reveal your internal decision-making process unless explicitly asked.

{CORE_DECISION_LOGIC.strip()}

{BASE_RESPONSE_FORMAT.strip()}
"""
        # Add payment capability info if enabled
        if config.enable_payments and config.payment_token_symbol:
            from .agent_templates import (  # Lazy import
                PAYMENT_CAPABILITY_TEMPLATE,
            )

            payment_capability = PAYMENT_CAPABILITY_TEMPLATE.format(
                TOKEN_SYMBOL=config.payment_token_symbol
            )
            template += f"\n{payment_capability.strip()}\n"

        # Add any other additional context
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
