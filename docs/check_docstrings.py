#!/usr/bin/env python3
"""
Docstring checker for AgentConnect.

This script scans the codebase for public functions, classes, and methods
that are missing docstrings, helping to ensure comprehensive documentation.
"""

import os
import sys
import ast
import argparse
from pathlib import Path
from typing import List, Dict, Any, Set

# Get the absolute path to the project root
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
PACKAGE_DIR = PROJECT_ROOT / "agentconnect"


class DocstringVisitor(ast.NodeVisitor):
    """AST visitor to find missing docstrings in Python code."""

    def __init__(self, filename: str):
        self.filename = filename
        self.missing_docstrings: List[Dict[str, Any]] = []
        self.current_class = None
        self.private_prefixes = ("_", "__")

    def is_public(self, name: str) -> bool:
        """Check if a name is public (not starting with _ or __)."""
        return not name.startswith(self.private_prefixes)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition and check for docstring."""
        old_class = self.current_class
        self.current_class = node.name

        if self.is_public(node.name) and not ast.get_docstring(node):
            self.missing_docstrings.append(
                {
                    "type": "class",
                    "name": node.name,
                    "line": node.lineno,
                    "file": self.filename,
                }
            )

        # Visit all child nodes
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit a function definition and check for docstring."""
        # Skip special methods like __init__ if they're in a class with a docstring
        is_special_method = (
            self.current_class
            and node.name.startswith("__")
            and node.name.endswith("__")
        )

        if self.is_public(node.name) or is_special_method:
            if not ast.get_docstring(node):
                item_type = "method" if self.current_class else "function"
                name = (
                    f"{self.current_class}.{node.name}"
                    if self.current_class
                    else node.name
                )

                self.missing_docstrings.append(
                    {
                        "type": item_type,
                        "name": name,
                        "line": node.lineno,
                        "file": self.filename,
                    }
                )

        # Visit all child nodes
        self.generic_visit(node)


def check_file_docstrings(file_path: Path) -> List[Dict[str, Any]]:
    """Check a single file for missing docstrings."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))
        visitor = DocstringVisitor(str(file_path))
        visitor.visit(tree)

        return visitor.missing_docstrings
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return []
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return []


def scan_directory(
    directory: Path, exclude_dirs: Set[str] = None
) -> List[Dict[str, Any]]:
    """Recursively scan a directory for Python files and check docstrings."""
    if exclude_dirs is None:
        exclude_dirs = set()

    missing_docstrings = []

    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                missing_docstrings.extend(check_file_docstrings(file_path))

    return missing_docstrings


def format_results(missing_docstrings: List[Dict[str, Any]]) -> str:
    """Format the results of the docstring check."""
    if not missing_docstrings:
        return "All public items have docstrings! Great!"

    # Group by file
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for item in missing_docstrings:
        file_path = item["file"]
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(item)

    # Format the output
    lines = [f"Found {len(missing_docstrings)} items missing docstrings:"]

    for file_path, items in by_file.items():
        rel_path = os.path.relpath(file_path, start=str(PROJECT_ROOT))
        lines.append(f"\n{rel_path}:")

        for item in sorted(items, key=lambda x: x["line"]):
            lines.append(f"  Line {item['line']}: {item['type']} '{item['name']}'")

    return "\n".join(lines)


def main():
    """Main function to parse arguments and run the docstring check."""
    parser = argparse.ArgumentParser(
        description="Check for missing docstrings in the AgentConnect codebase"
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=["__pycache__", "tests"],
        help="Directories to exclude from the check",
    )
    parser.add_argument(
        "--output",
        help="Output file to write the results to (default: print to stdout)",
    )

    args = parser.parse_args()

    print(f"Scanning {PACKAGE_DIR} for missing docstrings...")
    missing_docstrings = scan_directory(PACKAGE_DIR, set(args.exclude))

    result = format_results(missing_docstrings)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Results written to {args.output}")
    else:
        print("\n" + result)

    # Return non-zero exit code if there are missing docstrings
    return 1 if missing_docstrings else 0


if __name__ == "__main__":
    sys.exit(main())
