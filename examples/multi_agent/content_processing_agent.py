#!/usr/bin/env python
"""
Content Processing Agent for AgentConnect Multi-Agent System

This module defines the Content Processing Agent configuration for the multi-agent system.
It handles document processing, text extraction, and format conversion.
"""

import os
import re
from typing import Dict, Any, Union

from agentconnect.agents import AIAgent
from agentconnect.utils.callbacks import ToolTracerCallbackHandler
from agentconnect.core.types import (
    AgentIdentity,
    Capability,
    ModelName,
    ModelProvider,
)

# Import document processing tools
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.document_transformers.markdownify import MarkdownifyTransformer
from langchain_core.tools import Tool
from langchain_community.document_loaders import PyPDFLoader
from pydantic import BaseModel, Field

# Define schema for PDF loading
class PDFSourceInput(BaseModel):
    """Input schema for PDF loading tool."""
    
    source: str = Field(description="URL or file path to the PDF file")

def create_content_processing_agent(provider_type: ModelProvider, model_name: ModelName, api_key: str) -> AIAgent:
    """
    Create and configure the Content Processing agent.
    
    Args:
        provider_type (ModelProvider): The type of LLM provider to use
        model_name (ModelName): The specific model to use
        api_key (str): API key for the LLM provider
        
    Returns:
        AIAgent: Configured content processing agent
    """
    # Create content processing agent with custom tools
    content_processing_identity = AgentIdentity.create_key_based()
    content_processing_capabilities = [
        Capability(
            name="content_processing",
            description="Processes and transforms content in various formats",
            input_schema={"content": "string", "process_type": "string"},
            output_schema={"processed_content": "string"},
        ),
        Capability(
            name="document_conversion",
            description="Converts documents between different formats",
            input_schema={"document": "string", "source_format": "string", "target_format": "string"},
            output_schema={"converted_document": "string"},
        ),
        Capability(
            name="text_chunking",
            description="Splits text into smaller chunks for processing",
            input_schema={"text": "string", "chunk_size": "integer", "chunk_overlap": "integer"},
            output_schema={"chunks": "list", "num_chunks": "integer"},
        ),
        Capability(
            name="html_to_markdown",
            description="Converts HTML content to markdown format for better readability",
            input_schema={"html_content": "string"},
            output_schema={"markdown": "string", "success": "boolean"},
        ),
        Capability(
            name="pdf_extraction",
            description="Extracts text and metadata from PDF files",
            input_schema={"file_path": "string"},
            output_schema={"text": "string", "num_pages": "integer", "metadata": "object"},
        ),
    ]

    # Create content processing tools
    content_processing_tools = []
    
    # Create a text splitter tool
    def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> Dict[str, Any]:
        """Split text into chunks for processing."""
        try:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size, 
                chunk_overlap=chunk_overlap
            )
            docs = text_splitter.create_documents([text])
            return {
                "chunks": [doc.page_content for doc in docs],
                "num_chunks": len(docs)
            }
        except Exception as e:
            return {"error": str(e)}
    
    # Create an HTML to markdown converter tool
    def html_to_markdown(html_content: str) -> Dict[str, str]:
        """Convert HTML content to markdown format."""
        try:
            markdown_transformer = MarkdownifyTransformer()
            docs = [Document(page_content=html_content)]
            converted_docs = markdown_transformer.transform_documents(docs)
            return {
                "markdown": converted_docs[0].page_content,
                "success": True
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    # Helper function to get the downloads directory path and ensure it exists
    def get_downloads_dir() -> str:
        """
        Get the path to the downloads directory and ensure it exists.
        
        Returns:
            str: Path to the downloads directory
        """
        # Define the downloads directory path
        downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "downloads")
        
        # Create the directory if it doesn't exist
        if not os.path.exists(downloads_dir):
            print(f"Creating downloads directory: {downloads_dir}")
            os.makedirs(downloads_dir, exist_ok=True)
        
        return downloads_dir
    
    # Create a PDF loader tool implementation
    def load_pdf_impl(source: str) -> Dict[str, Any]:
        """
        Implementation of PDF loading functionality.
        
        Args:
            source (str): URL or file path to the PDF file
            
        Returns:
            Dict with extracted text, number of pages, and metadata
        """
        try:
            temp_path = None
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Determine if the source is a URL or a file path
            if source.startswith(('http://', 'https://')):
                # It's a URL - download the PDF
                import requests
                import tempfile
                
                print(f"Downloading PDF from URL: {source}")
                response = requests.get(source)
                if response.status_code != 200:
                    return {"error": f"Failed to download PDF. Status code: {response.status_code}"}
                
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                    temp_file.write(response.content)
                    temp_path = temp_file.name
                
                is_temp_file = True
            else:
                # It's a file path - handle both absolute and relative paths
                print(f"Loading PDF from path: {source}")
                is_temp_file = False
                
                # Check possible locations
                possible_paths = [
                    # The original path exactly as provided
                    source,
                    
                    # Absolute path
                    os.path.abspath(source),
                    
                    # Relative to current directory
                    os.path.join(current_dir, source),
                    
                    # Relative to working directory
                    os.path.join(os.getcwd(), source),
                    
                    # Inside downloads directory - common case
                    os.path.join(get_downloads_dir(), os.path.basename(source)),
                    
                    # Just the filename in downloads
                    os.path.join(get_downloads_dir(), source),
                    
                    # Workspace root downloads folder
                    os.path.join(os.getcwd(), "downloads", os.path.basename(source)),
                ]
                
                # Try each possible path
                for path in possible_paths:
                    print(f"Checking path: {path}")
                    if os.path.exists(path) and os.path.isfile(path):
                        print(f"Found PDF at: {path}")
                        temp_path = path
                        break
                
                if not temp_path:
                    # Still not found - return detailed error
                    return {"error": f"File not found. Checked these paths: {', '.join(possible_paths)}"}
            
            # Check access permissions
            if not os.access(temp_path, os.R_OK):
                return {"error": f"Permission denied: Cannot read file {temp_path}"}
            
            # Check file size
            try:
                file_size = os.path.getsize(temp_path)
                print(f"PDF file size: {file_size} bytes")
                if file_size == 0:
                    return {"error": "PDF file is empty (0 bytes)"}
            except Exception as file_size_error:
                print(f"Error checking file size: {str(file_size_error)}")
            
            # Use PyPDFLoader with error handling
            try:
                print(f"Loading PDF with PyPDFLoader: {temp_path}")
                loader = PyPDFLoader(temp_path)
                docs = loader.load()
                
                if not docs:
                    return {"error": "PDF loaded but no pages were extracted"}
                
                # Clean up the temporary file if it was downloaded from a URL
                if is_temp_file:
                    try:
                        os.unlink(temp_path)
                        print(f"Temporary file removed: {temp_path}")
                    except Exception as e:
                        print(f"Warning: Could not remove temporary file: {str(e)}")
                
                # Extract metadata
                metadata = {}
                if docs and hasattr(docs[0], "metadata"):
                    metadata = docs[0].metadata
                
                # Add path information to metadata
                metadata["execution_path"] = current_dir
                metadata["working_directory"] = os.getcwd()
                metadata["file_path"] = temp_path
                
                # Return the extracted content
                print(f"Successfully extracted {len(docs)} pages from PDF")
                return {
                    "text": "\n\n".join([doc.page_content for doc in docs]),
                    "num_pages": len(docs),
                    "metadata": metadata
                }
            except Exception as e:
                print(f"Error in PyPDFLoader: {str(e)}")
                return {"error": f"Error extracting text from PDF: {str(e)}"}
                
        except Exception as e:
            print(f"Error loading PDF: {str(e)}")
            return {"error": str(e)}
        
    # Wrapper function that can handle both string inputs and PDFSourceInput
    def load_pdf(pdf_source: Union[PDFSourceInput, str, Dict[str, str]]) -> Dict[str, Any]:
        """
        Load and extract text from a PDF file.
        
        Args:
            pdf_source: Can be one of:
                - PDFSourceInput model with 'source' field
                - A string with URL or file path
                - A dictionary with 'source' key
            
        Returns:
            Dict with extracted text, number of pages, and metadata
        """
        try:
            # Get the source as a string
            source_str = ""
            
            # Handle different input types
            if isinstance(pdf_source, str):
                # Direct string input - treat as source path/URL
                print("Received string input for PDF source")
                source_str = pdf_source
            
            elif isinstance(pdf_source, dict):
                # Dictionary input - extract source field
                print("Received dictionary input for PDF source")
                if 'source' in pdf_source:
                    source_str = pdf_source['source']
                else:
                    keys = list(pdf_source.keys())
                    if len(keys) > 0:
                        # Try to use the first key value as source
                        print(f"No 'source' key found, trying first key: {keys[0]}")
                        source_str = pdf_source[keys[0]]
                    else:
                        return {"error": "No source provided in dictionary"}
            
            elif hasattr(pdf_source, 'source'):
                # Pydantic model input - use source field
                print("Received PDFSourceInput model for PDF source")
                source_str = pdf_source.source
            
            else:
                # Unknown input type
                return {"error": f"Unsupported input type: {type(pdf_source)}. Expected string, dictionary, or PDFSourceInput."}
            
            # Fix path separators for Windows paths
            if "\\" in source_str:
                # Replace backslashes with forward slashes to avoid escape sequence issues
                source_str = source_str.replace('\\', '/')
                print(f"Normalized path: {source_str}")
            
            # Check if we're dealing with a potential UUID filename in the downloads folder
            uuid_pattern = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')
            
            # If the source string contains what looks like a UUID, check the downloads folder
            if uuid_pattern.search(source_str) or ('downloads' in source_str and source_str.endswith('.pdf')):
                print("Detected potential UUID-style filename")
                
                # Get the downloads directory
                downloads_dir = get_downloads_dir()
                
                # List all PDF files in the downloads directory
                pdf_files = [f for f in os.listdir(downloads_dir) if f.endswith('.pdf')]
                print(f"Found {len(pdf_files)} PDF files in downloads directory")
                
                # If we have a basename that looks like a UUID, check if it's in the downloads folder
                basename = os.path.basename(source_str)
                
                # Special case: try to find the file by UUID pattern
                for pdf_file in pdf_files:
                    if basename in pdf_file or (uuid_pattern.search(pdf_file) and uuid_pattern.search(source_str)):
                        full_path = os.path.join(downloads_dir, pdf_file)
                        print(f"Found matching PDF file: {full_path}")
                        return load_pdf_impl(full_path)
            
            # Check if the path is in the downloads directory 
            if source_str.startswith('downloads'):
                downloads_dir = get_downloads_dir()
                if not os.path.exists(source_str):
                    potential_path = os.path.join(downloads_dir, os.path.basename(source_str))
                    print(f"Checking potential path: {potential_path}")
                    if os.path.exists(potential_path):
                        print(f"Found file in downloads directory: {potential_path}")
                        source_str = potential_path
            
            # Now process the fixed path
            return load_pdf_impl(source_str)
                
        except Exception as e:
            print(f"Error in PDF loading wrapper: {str(e)}")
            return {"error": f"PDF loading error: {str(e)}"}

    # Add the document processing tools to the agent
    content_processing_tools.append(
        Tool.from_function(
            func=split_text,
            name="split_text",
            description="Split text into smaller chunks for processing",
        )
    )
    
    content_processing_tools.append(
        Tool.from_function(
            func=html_to_markdown,
            name="html_to_markdown",
            description="Convert HTML content to markdown format",
        )
    )
    
    content_processing_tools.append(
        Tool.from_function(
            func=load_pdf,
            name="load_pdf",
            description="Load and extract text from a PDF file. You can provide either a URL or file path as a string.",
        )
    )

    # Create the content processing agent with custom tools
    content_processing_agent = AIAgent(
        agent_id="content_processing_agent",
        name="Content Processing Agent",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=content_processing_identity,
        capabilities=content_processing_capabilities,
        personality="I am a content processing specialist who excels at transforming and converting content between different formats. I can extract text from PDFs, convert HTML to markdown, and process documents for better readability. I understand how to work with relative paths from the current directory.",
        custom_tools=content_processing_tools,
        # external_callbacks=[ToolTracerCallbackHandler(agent_id="content_processing_agent", print_tool_activity=False)],
    )
    
    return content_processing_agent 