#!/usr/bin/env python
"""
Telegram Agent for AgentConnect Multi-Agent System

This module defines the TelegramAIAgent configuration for the multi-agent system.
It handles Telegram user interactions and integration with the Telegram API.
"""

import os

from agentconnect.agents.telegram.telegram_agent import TelegramAIAgent
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    ModelName,
    ModelProvider,
)

def create_telegram_agent(provider_type: ModelProvider, model_name: ModelName, api_key: str) -> TelegramAIAgent:
    """
    Create and configure the Telegram agent.
    
    Args:
        provider_type (ModelProvider): The type of LLM provider to use
        model_name (ModelName): The specific model to use
        api_key (str): API key for the LLM provider
        
    Returns:
        TelegramAIAgent: Configured telegram agent
    """
    # Check for required API keys
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN not found. Please set it in your environment or .env file."
        )
    
    # Create Telegram agent
    telegram_identity = AgentIdentity.create_key_based()
    telegram_capabilities = [
        Capability(
            name="telegram_interface",
            description="Provides interface for Telegram users, handling messages and commands",
            input_schema={"message": "string", "chat_id": "string"},
            output_schema={"response": "string", "success": "boolean"},
        ),
        Capability(
            name="document_handling",
            description="Processes documents uploaded by users including PDF files",
            input_schema={"file_id": "string", "file_type": "string", "chat_id": "string"},
            output_schema={"processed_content": "string", "success": "boolean"},
        ),
        Capability(
            name="pdf_processing",
            description="Extracts and analyzes content from PDF files uploaded by users",
            input_schema={"file_path": "string"},
            output_schema={"text": "string", "summary": "string", "num_pages": "integer"},
        ),
    ]

    telegram_agent = TelegramAIAgent(
        agent_id="telegram_agent",
        name="Telegram Assistant",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=telegram_identity,
        capabilities=telegram_capabilities,
        personality="I am a helpful and friendly Telegram assistant. I can answer questions, provide information, and collaborate with other specialized agents to solve complex problems. I can also process PDF documents that you upload, including files from local paths like 'examples/data.pdf' or absolute paths.",
        telegram_token=telegram_token
    )
    
    return telegram_agent 