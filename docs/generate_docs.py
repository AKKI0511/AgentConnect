#!/usr/bin/env python3
"""
Documentation generation script for AgentConnect.

This script automates the process of generating API documentation and building
the Sphinx documentation for the AgentConnect project.
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

# Get the absolute path to the project root
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DOCS_DIR = PROJECT_ROOT / "docs"
SOURCE_DIR = DOCS_DIR / "source"
API_DIR = SOURCE_DIR / "api"
BUILD_DIR = DOCS_DIR / "build"


def run_command(cmd, cwd=None):
    """Run a shell command and print the output."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(e.stdout)
        return False


def clean_api_docs():
    """Remove existing API documentation files."""
    print("Cleaning API documentation...")
    
    # Keep these files as they might contain manual content
    keep_files = ["index.rst"]
    
    for file in API_DIR.glob("*.rst"):
        if file.name not in keep_files:
            print(f"Removing {file}")
            file.unlink()
    
    print("API documentation cleaned.")


def generate_api_docs():
    """Generate API documentation using sphinx-apidoc."""
    print("Generating API documentation...")
    
    # Create API directory if it doesn't exist
    API_DIR.mkdir(exist_ok=True, parents=True)
    
    # Run sphinx-apidoc to generate .rst files for the Python modules
    cmd = [
        "sphinx-apidoc",
        "-f",  # Force overwriting of existing files
        "-e",  # Put documentation for each module on its own page
        "-M",  # Put module documentation before submodule documentation
        "-o", str(API_DIR),  # Output directory
        str(PROJECT_ROOT / "agentconnect"),  # Source code directory
    ]
    
    return run_command(cmd)


def build_docs(builder="html"):
    """Build the documentation using Sphinx."""
    print(f"Building {builder} documentation...")
    
    # On Windows, use make.bat
    if sys.platform.startswith("win"):
        cmd = [str(DOCS_DIR / "make.bat"), builder]
    else:
        cmd = ["make", "-C", str(DOCS_DIR), builder]
    
    success = run_command(cmd)
    
    if success and builder == "html":
        print(f"\nDocumentation built successfully. Open {BUILD_DIR / 'html' / 'index.html'} to view.")
    
    return success


def clean_build():
    """Clean the build directory."""
    print("Cleaning build directory...")
    
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
        print("Build directory cleaned.")
    else:
        print("Build directory does not exist.")


def main():
    """Main function to parse arguments and run the appropriate commands."""
    parser = argparse.ArgumentParser(description="Generate documentation for AgentConnect")
    parser.add_argument("--clean", action="store_true", help="Clean API docs and build directory before generating")
    parser.add_argument("--api-only", action="store_true", help="Only generate API documentation, don't build")
    parser.add_argument("--builder", default="html", help="Sphinx builder to use (default: html)")
    
    args = parser.parse_args()
    
    if args.clean:
        clean_api_docs()
        clean_build()
    
    if generate_api_docs() and not args.api_only:
        build_docs(args.builder)


if __name__ == "__main__":
    main() 