#!/usr/bin/env python
"""
Message Logger for AgentConnect Multi-Agent System

This module provides message logging functionality to visualize agent interactions
in a multi-agent system.
"""

from colorama import init, Fore, Style
from agentconnect.core.message import Message

# Initialize colorama for cross-platform colored output
init()

# Define colors for different message types
COLORS = {
    "SYSTEM": Fore.YELLOW,
    "USER": Fore.GREEN,
    "ASSISTANT": Fore.CYAN,
    "ERROR": Fore.RED,
    "INFO": Fore.MAGENTA,
    "RESEARCH": Fore.BLUE,
    "TELEGRAM": Fore.LIGHTBLUE_EX,
    "CONTENT": Fore.WHITE,
    "DATA": Fore.LIGHTGREEN_EX,
    "WARNING": Fore.LIGHTYELLOW_EX,
    "PROCESS": Fore.LIGHTMAGENTA_EX,
    "COMMAND": Fore.LIGHTYELLOW_EX,
    "QUERY": Fore.LIGHTCYAN_EX,
    "PDF": Fore.LIGHTRED_EX,
}

def print_colored(message: str, color_type: str = "SYSTEM") -> None:
    """
    Print a message with specified color.

    Args:
        message (str): The message to print
        color_type (str): The type of color to use (SYSTEM, USER, AI, etc.)
    """
    color = COLORS.get(color_type, Fore.WHITE)
    print(f"{color}{message}{Style.RESET_ALL}")

async def agent_message_logger(message: Message) -> None:
    """
    Global message handler for logging agent collaboration flow.
    
    This handler inspects messages routed through the hub and logs specific interactions
    between agents in the system, visualizing how they collaborate.
    
    Args:
        message (Message): The message being routed through the hub
    """
    # Skip logging messages to/from human agents
    if "human" in message.receiver_id.lower() or "human" in message.sender_id.lower():
        return
    
    # Determine color based on sender agent
    color_type = "SYSTEM"
    if "telegram" in message.sender_id:
        color_type = "TELEGRAM"
    elif "research" in message.sender_id:
        color_type = "RESEARCH"
    elif "content" in message.sender_id:
        color_type = "CONTENT"
    elif "data" in message.sender_id:
        color_type = "DATA"
    
    # Log the message flow with truncated content
    shortened_content = message.content[:50] + ("..." if len(message.content) > 50 else "")
    print_colored(f"🔄 {message.sender_id} → {message.receiver_id}: {shortened_content}", color_type) 