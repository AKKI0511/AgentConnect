#!/usr/bin/env python
"""
Research Agent for AgentConnect Multi-Agent System

This module defines the Research Agent configuration for the multi-agent system.
It handles web searches, retrieves information, and creates comprehensive reports.
"""

import os

from agentconnect.agents import AIAgent
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    ModelName,
    ModelProvider,
)

# Add imports for research tools
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.tools.arxiv import ArxivQueryRun
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.tools.requests.tool import RequestsGetTool, RequestsPostTool
from langchain_community.utilities import TextRequestsWrapper

def create_research_agent(provider_type: ModelProvider, model_name: ModelName, api_key: str) -> AIAgent:
    """
    Create and configure the Research agent.
    
    Args:
        provider_type (ModelProvider): The type of LLM provider to use
        model_name (ModelName): The specific model to use
        api_key (str): API key for the LLM provider
        
    Returns:
        AIAgent: Configured research agent
    """
    # Check for Tavily API key
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    
    # Create research agent with web search capabilities
    research_identity = AgentIdentity.create_key_based()
    research_capabilities = [
        Capability(
            name="web_search",
            description="Searches the web for information on various topics",
            input_schema={"query": "string", "num_results": "integer"},
            output_schema={"results": "list"},
        ),
        Capability(
            name="research_report",
            description="Creates comprehensive research reports with proper citations",
            input_schema={"topic": "string", "depth": "string"},
            output_schema={"report": "string", "citations": "list"},
        ),
        Capability(
            name="query_planning",
            description="Generates effective search queries from user questions",
            input_schema={"question": "string"},
            output_schema={"queries": "list"},
        ),
        Capability(
            name="http_request",
            description="Makes HTTP GET and POST requests to retrieve information from web APIs",
            input_schema={"url": "string", "method": "string", "data": "object"},
            output_schema={"content": "string", "status_code": "integer"},
        ),
        Capability(
            name="academic_research",
            description="Retrieves academic papers and research from ArXiv and other sources",
            input_schema={"query": "string", "max_results": "integer"},
            output_schema={"papers": "list", "abstracts": "list"},
        ),
    ]

    # Create research agent with search tools
    research_tools = []
    if tavily_api_key:
        try:
            tavily_search = TavilySearchResults(
                api_key=tavily_api_key,
                max_results=3,
                include_raw_content=True,
                include_images=False,
            )
            research_tools.append(tavily_search)
        except Exception as e:
            print(f"Error initializing Tavily search: {e}")

    research_tools.append(ArxivQueryRun())
    research_tools.append(WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper()))
    
    # Add more general search capabilities
    requests_wrapper = TextRequestsWrapper()
    research_tools.append(RequestsGetTool(requests_wrapper=requests_wrapper, allow_dangerous_requests=True))
    research_tools.append(RequestsPostTool(requests_wrapper=requests_wrapper, allow_dangerous_requests=True))

    research_agent = AIAgent(
        agent_id="research_agent",
        name="Research Agent",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=research_identity,
        capabilities=research_capabilities,
        personality="I am a research specialist who excels at finding information on various topics. I generate effective search queries, retrieve information from the web, and synthesize findings into comprehensive reports with proper citations.",
        custom_tools=research_tools,
    )
    
    return research_agent 