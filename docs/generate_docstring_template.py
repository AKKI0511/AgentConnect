#!/usr/bin/env python3
"""
Docstring template generator for AgentConnect.

This script generates docstring templates for functions and classes
to help developers add missing docstrings.
"""

import os
import sys
import ast
import inspect
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Get the absolute path to the project root
PROJECT_ROOT = Path(__file__).parent.parent.absolute()


def get_function_signature(node: ast.FunctionDef) -> Tuple[List[str], Optional[str]]:
    """Extract parameter names and return annotation from a function definition."""
    args = []
    
    # Get positional arguments
    for arg in node.args.args:
        arg_name = arg.arg
        arg_type = ""
        if arg.annotation:
            if isinstance(arg.annotation, ast.Name):
                arg_type = arg.annotation.id
            elif isinstance(arg.annotation, ast.Subscript):
                if isinstance(arg.annotation.value, ast.Name):
                    arg_type = arg.annotation.value.id
                    # Try to get the subscript
                    if isinstance(arg.annotation.slice, ast.Index):
                        if isinstance(arg.annotation.slice.value, ast.Name):
                            arg_type += f"[{arg.annotation.slice.value.id}]"
                    elif hasattr(arg.annotation.slice, 'id'):
                        arg_type += f"[{arg.annotation.slice.id}]"
            
        args.append((arg_name, arg_type))
    
    # Get *args if present
    if node.args.vararg:
        args.append((f"*{node.args.vararg.arg}", ""))
    
    # Get keyword-only arguments
    for arg in node.args.kwonlyargs:
        arg_name = arg.arg
        arg_type = ""
        if arg.annotation:
            if isinstance(arg.annotation, ast.Name):
                arg_type = arg.annotation.id
        args.append((arg_name, arg_type))
    
    # Get **kwargs if present
    if node.args.kwarg:
        args.append((f"**{node.args.kwarg.arg}", ""))
    
    # Get return type
    return_type = None
    if node.returns:
        if isinstance(node.returns, ast.Name):
            return_type = node.returns.id
        elif isinstance(node.returns, ast.Subscript):
            if isinstance(node.returns.value, ast.Name):
                return_type = node.returns.value.id
                # Try to get the subscript
                if isinstance(node.returns.slice, ast.Index):
                    if isinstance(node.returns.slice.value, ast.Name):
                        return_type += f"[{node.returns.slice.value.id}]"
                elif hasattr(node.returns.slice, 'id'):
                    return_type += f"[{node.returns.slice.id}]"
    
    return args, return_type


def generate_function_docstring(node: ast.FunctionDef, class_name: Optional[str] = None) -> str:
    """Generate a docstring template for a function."""
    args, return_type = get_function_signature(node)
    
    # Start with a basic description
    if class_name:
        docstring = f'"""{node.name} method.\n\n'
    else:
        docstring = f'"""{node.name} function.\n\n'
    
    docstring += "TODO: Add a description of what this function does.\n"
    
    # Add Args section if there are arguments
    if args:
        docstring += "\nArgs:\n"
        for arg_name, arg_type in args:
            # Skip self for methods
            if class_name and arg_name == "self":
                continue
            
            # Format the type hint
            type_hint = f" ({arg_type})" if arg_type else ""
            
            # Handle special cases for *args and **kwargs
            if arg_name.startswith("*"):
                docstring += f"    {arg_name}: TODO: Describe variable arguments\n"
            else:
                docstring += f"    {arg_name}{type_hint}: TODO: Describe parameter\n"
    
    # Add Returns section if there's a return type
    if return_type and return_type != "None":
        docstring += "\nReturns:\n"
        docstring += f"    {return_type}: TODO: Describe return value\n"
    
    # Add Raises section as a placeholder
    docstring += "\nRaises:\n"
    docstring += "    Exception: TODO: Document exceptions raised\n"
    
    # Add Examples section
    docstring += "\nExamples:\n"
    docstring += "    TODO: Add usage examples\n"
    
    docstring += '"""'
    return docstring


def generate_class_docstring(node: ast.ClassDef) -> str:
    """Generate a docstring template for a class."""
    # Get base classes
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
    
    # Start with a basic description
    docstring = f'"""{node.name} class.\n\n'
    docstring += "TODO: Add a description of what this class does.\n"
    
    # Add information about inheritance
    if bases:
        docstring += f"\nInherits from: {', '.join(bases)}\n"
    
    # Add Attributes section
    docstring += "\nAttributes:\n"
    docstring += "    TODO: List and describe class attributes\n"
    
    # Add Examples section
    docstring += "\nExamples:\n"
    docstring += "    TODO: Add usage examples\n"
    
    docstring += '"""'
    return docstring


def process_file(file_path: Path, missing_items: List[Dict[str, Any]]) -> Dict[str, str]:
    """Process a file and generate docstring templates for missing items."""
    templates = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        # Find all classes and functions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if this class is in the missing items list
                for item in missing_items:
                    if (item['file'] == str(file_path) and 
                        item['type'] == 'class' and 
                        item['name'] == node.name):
                        templates[f"class:{node.name}"] = generate_class_docstring(node)
            
            elif isinstance(node, ast.FunctionDef):
                # Find the parent class if any
                parent_class = None
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef):
                        for child in ast.iter_child_nodes(parent):
                            if child is node:
                                parent_class = parent.name
                                break
                        if parent_class:
                            break
                
                # Check if this function is in the missing items list
                for item in missing_items:
                    if item['file'] == str(file_path) and item['type'] in ('function', 'method'):
                        if parent_class:
                            if item['name'] == f"{parent_class}.{node.name}":
                                templates[f"method:{parent_class}.{node.name}"] = generate_function_docstring(node, parent_class)
                        else:
                            if item['name'] == node.name:
                                templates[f"function:{node.name}"] = generate_function_docstring(node)
        
        return templates
    
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return {}


def main():
    """Main function to parse arguments and generate docstring templates."""
    parser = argparse.ArgumentParser(
        description="Generate docstring templates for missing docstrings"
    )
    parser.add_argument(
        "missing_docstrings_file",
        help="File containing the output of check_docstrings.py"
    )
    parser.add_argument(
        "--output",
        help="Output file to write the templates to (default: docstring_templates.txt)"
    )
    
    args = parser.parse_args()
    
    # Parse the missing docstrings file
    missing_items = []
    current_file = None
    
    try:
        with open(args.missing_docstrings_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("Found "):
                    continue
                
                if line.endswith(":"):
                    # This is a file path
                    current_file = os.path.join(PROJECT_ROOT, line[:-1])
                elif line.startswith("  Line "):
                    # This is an item
                    parts = line.split(":")
                    line_part = parts[0].strip()
                    item_part = parts[1].strip()
                    
                    line_num = int(line_part.split()[1])
                    item_type, item_name = item_part.split("'")[0].strip(), item_part.split("'")[1].strip()
                    
                    missing_items.append({
                        'file': current_file,
                        'line': line_num,
                        'type': item_type,
                        'name': item_name
                    })
    except Exception as e:
        print(f"Error parsing missing docstrings file: {e}")
        return 1
    
    if not missing_items:
        print("No missing docstrings found.")
        return 0
    
    # Group missing items by file
    by_file = {}
    for item in missing_items:
        file_path = item['file']
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(item)
    
    # Process each file and generate templates
    all_templates = {}
    for file_path, items in by_file.items():
        templates = process_file(Path(file_path), items)
        all_templates.update(templates)
    
    # Write the templates to a file
    output_file = args.output or "docstring_templates.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Docstring Templates\n\n")
        f.write("This file contains templates for missing docstrings in the codebase.\n")
        f.write("Copy and paste these templates into the appropriate locations in your code.\n\n")
        
        for key, template in all_templates.items():
            item_type, item_name = key.split(":", 1)
            f.write(f"## {item_type.capitalize()}: {item_name}\n\n")
            f.write("```python\n")
            f.write(template)
            f.write("\n```\n\n")
    
    print(f"Generated {len(all_templates)} docstring templates in {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 