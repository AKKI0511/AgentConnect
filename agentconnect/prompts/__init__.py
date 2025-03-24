"""
Prompt templates and tools for the AgentConnect framework.

This module provides the core logic for agent workflows, including prompt templates,
tools for agent collaboration, and workflow definitions. It serves as the "brain"
of the AgentConnect framework, enabling agents to make decisions, collaborate with
other agents, and process complex tasks.

Key components:

- **Tools**: Utilities for agent search, collaboration, and task decomposition
- **Workflows**: LangGraph-based workflows for different agent types
- **Templates**: Prompt templates for various agent interactions
- **Chain Factory**: Utilities for creating LangChain chains
"""

# Re-export only the most important workflow classes
from agentconnect.prompts.agent_prompts import (
    AgentWorkflow,
    AIAgentWorkflow,
    create_workflow_for_agent,
)

# Re-export only the chain factory function that most users will need
from agentconnect.prompts.chain_factory import create_agent_workflow

# Re-export only the top-level prompt management class
from agentconnect.prompts.templates.prompt_templates import PromptTemplates

# Re-export only the top-level tool class
from agentconnect.prompts.tools import PromptTools

__all__ = [
    # Only most commonly used components
    "AgentWorkflow",
    "AIAgentWorkflow",
    "create_workflow_for_agent",
    "PromptTemplates",
    "PromptTools",
    "create_agent_workflow",
]
