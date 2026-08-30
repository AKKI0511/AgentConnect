"""
AgentConnect Examples

This package contains example applications demonstrating the capabilities
of the AgentConnect framework.

Available examples:
- Basic Chat: Interactive conversation with an AI agent
- Multi-Agent Analysis: Collaborative analysis between specialized agents
- Research Assistant: Multi-agent system for research tasks
- Data Analysis: Specialized agents for data analysis and visualization

Run these examples directly via Python scripts from the project root, for example:
    python examples/example_usage.py
    python examples/example_multi_agent.py
    python examples/research_assistant.py
    python examples/data_analysis_assistant.py
    python examples/multi_agent/multi_agent_system.py

Team Runtime examples live in examples/communication/. Start a Team from a
file with `cd examples/communication/hosted_team` then `agentconnect up`.
"""

from examples.data_analysis_assistant import run_data_analysis_assistant_demo
from examples.example_multi_agent import run_ecommerce_analysis_demo

# Export main functions for easy importing
from examples.example_usage import main as run_chat_example
from examples.research_assistant import run_research_assistant_demo

# Use the new modular multi-agent system for telegram example
from examples.multi_agent.multi_agent_system import (
    run_multi_agent_system as run_telegram_assistant,
)

__all__ = [
    "run_chat_example",
    "run_ecommerce_analysis_demo",
    "run_research_assistant_demo",
    "run_data_analysis_assistant_demo",
    "run_telegram_assistant",
]
