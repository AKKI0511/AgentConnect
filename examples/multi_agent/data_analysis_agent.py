#!/usr/bin/env python
"""
Data Analysis Agent for AgentConnect Multi-Agent System

This module defines the Data Analysis Agent configuration for the multi-agent system.
It handles data processing, visualization, and insights generation.
"""

import os
import io
import json
from typing import Dict
from pydantic import BaseModel, Field

from agentconnect.agents import AIAgent
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    ModelName,
    ModelProvider,
)
from agentconnect.prompts.tools import PromptTools
from agentconnect.core.registry import AgentRegistry
from agentconnect.communication import CommunicationHub

# Import for data analysis
import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Define schema for data analysis
class DataAnalysisInput(BaseModel):
    """Input schema for data analysis tool."""

    data: str = Field(description="The data to analyze in CSV or JSON format.")
    analysis_type: str = Field(
        default="summary",
        description="The type of analysis to perform (summary, correlation, visualization).",
    )

def create_data_analysis_agent(
    provider_type: ModelProvider, 
    model_name: ModelName, 
    api_key: str,
    registry: AgentRegistry,
    hub: CommunicationHub
) -> AIAgent:
    """
    Create and configure the Data Analysis agent.
    
    Args:
        provider_type (ModelProvider): The type of LLM provider to use
        model_name (ModelName): The specific model to use
        api_key (str): API key for the LLM provider
        registry (AgentRegistry): The agent registry for tool creation
        hub (CommunicationHub): The communication hub for tool creation
        
    Returns:
        AIAgent: Configured data analysis agent
    """
    # Create data analysis agent with visualization capabilities
    data_analysis_identity = AgentIdentity.create_key_based()
    data_analysis_capabilities = [
        Capability(
            name="data_analysis",
            description="Analyzes provided data (structured or textual) to provide insights, identify trends, assess impacts (e.g., economic), and generate summaries.",
            input_schema={"data": "string", "analysis_type": "string"},
            output_schema={"result": "string", "visualization_path": "string"},
        ),
        Capability(
            name="data_visualization",
            description="Creates visualizations from provided data",
            input_schema={"data": "string", "chart_type": "string"},
            output_schema={"visualization_path": "string", "description": "string"},
        ),
    ]

    # Function for data analysis tool
    def analyze_data(data: str, analysis_type: str = "summary") -> Dict[str, str]:
        """
        Analyze data and generate visualizations.

        Args:
            data (str): Data in CSV or JSON format
            analysis_type (str): Type of analysis to perform

        Returns:
            Dict[str, str]: Results of analysis and path to any visualizations
        """
        print(f"Performing {analysis_type} analysis on data")

        # Create a directory for visualizations if it doesn't exist
        viz_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "visualizations"
        )
        if not os.path.exists(viz_dir):
            os.makedirs(viz_dir)

        try:
            # Load data
            if data.startswith("{") or data.startswith("["):
                # Try to parse as JSON
                data_dict = json.loads(data)
                df = pd.DataFrame(data_dict)
            else:
                # Try to parse as CSV
                df = pd.read_csv(io.StringIO(data))

            # Get basic stats
            num_rows, num_cols = df.shape
            column_types = df.dtypes.to_dict()
            numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
            categorical_columns = df.select_dtypes(include=["object"]).columns.tolist()

            summary = f"Dataset has {num_rows} rows and {num_cols} columns.\n\n"

            if analysis_type == "summary":
                # Basic summary statistics
                summary += "## Summary Statistics\n\n"
                for col in numeric_columns:
                    summary += f"### {col}\n"
                    summary += f"- Mean: {df[col].mean():.2f}\n"
                    summary += f"- Median: {df[col].median():.2f}\n"
                    summary += f"- Min: {df[col].min():.2f}\n"
                    summary += f"- Max: {df[col].max():.2f}\n"
                    summary += f"- Standard Deviation: {df[col].std():.2f}\n\n"

                for col in categorical_columns:
                    summary += f"### {col}\n"
                    summary += f"- Unique values: {df[col].nunique()}\n"
                    summary += f"- Top value: {df[col].value_counts().index[0]}\n\n"

            elif analysis_type == "correlation" and len(numeric_columns) > 1:
                # Correlation analysis
                corr = df[numeric_columns].corr()

                # Create correlation heatmap
                plt.figure(figsize=(10, 8))
                plt.matshow(corr, fignum=1)
                plt.title("Correlation Matrix")
                plt.colorbar()

                # Add correlation values
                for i in range(len(corr.columns)):
                    for j in range(len(corr.columns)):
                        plt.text(
                            i, j, f"{corr.iloc[i, j]:.2f}", va="center", ha="center"
                        )

                # Save visualization
                viz_path = os.path.join(viz_dir, "correlation_matrix.png")
                plt.savefig(viz_path)
                plt.close()

                # Add correlation summary to results
                summary += "## Correlation Analysis\n\n"
                summary += "The correlation matrix between numeric variables has been saved as an image.\n\n"

                # Find strongest correlations
                corr_values = corr.unstack().sort_values(ascending=False)
                # Remove self-correlations (which are always 1.0)
                corr_values = corr_values[corr_values < 0.999]

                summary += "### Strongest correlations:\n"
                for i, (idx, val) in enumerate(corr_values.items()):
                    if i >= 5:  # Top 5 correlations
                        break
                    summary += f"- {idx[0]} vs {idx[1]}: {val:.2f}\n"

                return {"result": summary, "visualization_path": viz_path}

            elif analysis_type == "visualization":
                # Create multiple visualizations for numeric columns
                viz_paths = []
                viz_summary = ""

                # Create a histogram for each numeric column
                for col in numeric_columns[:3]:  # Limit to first 3 columns
                    plt.figure(figsize=(8, 6))
                    plt.hist(df[col].dropna(), bins=20, alpha=0.7)
                    plt.title(f"Histogram of {col}")
                    plt.xlabel(col)
                    plt.ylabel("Frequency")
                    viz_path = os.path.join(
                        viz_dir, f"histogram_{col}.png".replace("/", "_")
                    )
                    plt.savefig(viz_path)
                    plt.close()
                    viz_paths.append(viz_path)
                    viz_summary += f"- Histogram of {col}\n"

                # Create a pie chart for a categorical column if available
                if categorical_columns:
                    col = categorical_columns[0]
                    plt.figure(figsize=(8, 8))
                    value_counts = df[col].value_counts()
                    # Limit to top 5 categories for readability
                    if len(value_counts) > 5:
                        other_count = value_counts[5:].sum()
                        value_counts = value_counts[:5]
                        value_counts["Other"] = other_count
                    plt.pie(value_counts, labels=value_counts.index, autopct="%1.1f%%")
                    plt.title(f"Distribution of {col}")
                    viz_path = os.path.join(
                        viz_dir, f"pie_chart_{col}.png".replace("/", "_")
                    )
                    plt.savefig(viz_path)
                    plt.close()
                    viz_paths.append(viz_path)
                    viz_summary += f"- Pie chart of {col} distribution\n"

                summary += "## Visualizations Created\n\n"
                summary += viz_summary
                summary += f"\nVisualizations saved to {viz_dir}\n"

                return {"result": summary, "visualization_path": ",".join(viz_paths)}

            # Default return for summary
            return {"result": summary, "visualization_path": ""}

        except Exception as e:
            error_msg = f"Error analyzing data: {str(e)}"
            print(error_msg)
            return {
                "result": f"Error analyzing data: {str(e)}",
                "visualization_path": "",
            }

    # Create the tools for the data analysis agent
    data_analysis_agent_tools = PromptTools(registry, hub)
    data_analysis_tool = data_analysis_agent_tools.create_tool_from_function(
        func=analyze_data,
        name="analyze_data",
        description="Analyze data and generate visualizations",
        args_schema=DataAnalysisInput,
        category="data_analysis",
    )

    # Create the data analysis agent with custom tools
    data_analysis_agent = AIAgent(
        agent_id="data_analysis_agent",
        name="Data Analysis Agent",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=data_analysis_identity,
        capabilities=data_analysis_capabilities,
        personality=(
            "I am a data analysis specialist. I excel at processing structured data (like CSV/JSON) for statistical analysis and visualization. "
            "I can also analyze textual information to identify key trends, assess potential impacts (including economic consequences), and generate insightful summaries based on the provided context."
        ),
        custom_tools=[data_analysis_tool],
    )
    
    return data_analysis_agent 