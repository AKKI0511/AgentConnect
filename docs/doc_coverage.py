#!/usr/bin/env python3
"""
Documentation coverage checker for AgentConnect.

This script analyzes the codebase and generates a report on documentation coverage,
including statistics on how well the code is documented.
"""

import os
import sys
import ast
import argparse
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from datetime import datetime

# Get the absolute path to the project root
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
PACKAGE_DIR = PROJECT_ROOT / "agentconnect"


class DocCoverageVisitor(ast.NodeVisitor):
    """AST visitor to analyze documentation coverage in Python code."""

    def __init__(self, filename: str):
        self.filename = filename
        self.stats = {
            'total_classes': 0,
            'documented_classes': 0,
            'total_functions': 0,
            'documented_functions': 0,
            'total_methods': 0,
            'documented_methods': 0,
        }
        self.current_class = None
        self.private_prefixes = ('_', '__')
        self.items = []

    def is_public(self, name: str) -> bool:
        """Check if a name is public (not starting with _ or __)."""
        return not name.startswith(self.private_prefixes)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class definition and check for docstring."""
        old_class = self.current_class
        self.current_class = node.name

        if self.is_public(node.name):
            self.stats['total_classes'] += 1
            has_docstring = bool(ast.get_docstring(node))
            if has_docstring:
                self.stats['documented_classes'] += 1
            
            self.items.append({
                'type': 'class',
                'name': node.name,
                'line': node.lineno,
                'file': self.filename,
                'documented': has_docstring
            })

        # Visit all child nodes
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit a function definition and check for docstring."""
        if self.is_public(node.name) or (self.current_class and node.name == '__init__'):
            has_docstring = bool(ast.get_docstring(node))
            
            if self.current_class:
                self.stats['total_methods'] += 1
                if has_docstring:
                    self.stats['documented_methods'] += 1
                
                self.items.append({
                    'type': 'method',
                    'name': f"{self.current_class}.{node.name}",
                    'line': node.lineno,
                    'file': self.filename,
                    'documented': has_docstring
                })
            else:
                self.stats['total_functions'] += 1
                if has_docstring:
                    self.stats['documented_functions'] += 1
                
                self.items.append({
                    'type': 'function',
                    'name': node.name,
                    'line': node.lineno,
                    'file': self.filename,
                    'documented': has_docstring
                })
        
        # Visit all child nodes
        self.generic_visit(node)


def analyze_file(file_path: Path) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """Analyze a single file for documentation coverage."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        visitor = DocCoverageVisitor(str(file_path))
        visitor.visit(tree)
        
        return visitor.stats, visitor.items
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return {}, []
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return {}, []


def scan_directory(directory: Path, exclude_dirs: Set[str] = None) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """Recursively scan a directory for Python files and analyze documentation coverage."""
    if exclude_dirs is None:
        exclude_dirs = set()
    
    total_stats = {
        'total_classes': 0,
        'documented_classes': 0,
        'total_functions': 0,
        'documented_functions': 0,
        'total_methods': 0,
        'documented_methods': 0,
    }
    all_items = []
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                file_stats, file_items = analyze_file(file_path)
                
                # Update total stats
                for key in total_stats:
                    total_stats[key] += file_stats.get(key, 0)
                
                all_items.extend(file_items)
    
    return total_stats, all_items


def calculate_coverage(stats: Dict[str, int]) -> Dict[str, float]:
    """Calculate coverage percentages from statistics."""
    coverage = {}
    
    if stats['total_classes'] > 0:
        coverage['class_coverage'] = (stats['documented_classes'] / stats['total_classes']) * 100
    else:
        coverage['class_coverage'] = 100.0
    
    if stats['total_functions'] > 0:
        coverage['function_coverage'] = (stats['documented_functions'] / stats['total_functions']) * 100
    else:
        coverage['function_coverage'] = 100.0
    
    if stats['total_methods'] > 0:
        coverage['method_coverage'] = (stats['documented_methods'] / stats['total_methods']) * 100
    else:
        coverage['method_coverage'] = 100.0
    
    total_items = stats['total_classes'] + stats['total_functions'] + stats['total_methods']
    documented_items = stats['documented_classes'] + stats['documented_functions'] + stats['documented_methods']
    
    if total_items > 0:
        coverage['overall_coverage'] = (documented_items / total_items) * 100
    else:
        coverage['overall_coverage'] = 100.0
    
    return coverage


def generate_coverage_chart(stats: Dict[str, int], coverage: Dict[str, float], output_file: str):
    """Generate a bar chart showing documentation coverage."""
    try:
        import matplotlib.pyplot as plt
        
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Data for the chart
        categories = ['Classes', 'Functions', 'Methods', 'Overall']
        values = [
            coverage['class_coverage'],
            coverage['function_coverage'],
            coverage['method_coverage'],
            coverage['overall_coverage']
        ]
        
        # Create the bar chart
        bars = ax.bar(categories, values, color=['#3498db', '#2ecc71', '#e74c3c', '#f39c12'])
        
        # Add values on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{height:.1f}%', ha='center', va='bottom')
        
        # Add counts as text below the bars
        ax.text(0, -5, f"{stats['documented_classes']}/{stats['total_classes']}", ha='center')
        ax.text(1, -5, f"{stats['documented_functions']}/{stats['total_functions']}", ha='center')
        ax.text(2, -5, f"{stats['documented_methods']}/{stats['total_methods']}", ha='center')
        
        total_items = stats['total_classes'] + stats['total_functions'] + stats['total_methods']
        documented_items = stats['documented_classes'] + stats['documented_functions'] + stats['documented_methods']
        ax.text(3, -5, f"{documented_items}/{total_items}", ha='center')
        
        # Customize the chart
        ax.set_ylim(0, 105)  # Set y-axis limit to 0-105 to leave room for text
        ax.set_ylabel('Coverage (%)')
        ax.set_title('Documentation Coverage Report')
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plt.figtext(0.5, 0.01, f"Generated on {timestamp}", ha='center', fontsize=8)
        
        # Save the chart
        plt.tight_layout(pad=2.0)
        plt.savefig(output_file)
        print(f"Coverage chart saved to {output_file}")
        
    except ImportError:
        print("Matplotlib is not installed. Skipping chart generation.")
        print("Install matplotlib with: pip install matplotlib")


def generate_html_report(stats: Dict[str, int], coverage: Dict[str, float], items: List[Dict[str, Any]], output_file: str):
    """Generate an HTML report of documentation coverage."""
    # Group items by file
    by_file = {}
    for item in items:
        file_path = item['file']
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(item)
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentConnect Documentation Coverage Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #e0e0e0; background-color: #1e1e1e; }}
        h1, h2, h3 {{ color: #61afef; }}
        .summary {{ background-color: #252526; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .progress-container {{ width: 100%; background-color: #333333; border-radius: 5px; margin-bottom: 10px; }}
        .progress-bar {{ height: 20px; border-radius: 5px; text-align: center; color: white; font-weight: bold; }}
        .good {{ background-color: #2ecc71; }}
        .warning {{ background-color: #f39c12; }}
        .poor {{ background-color: #e74c3c; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #444444; }}
        th {{ background-color: #2d2d2d; }}
        tr:hover {{ background-color: #333333; }}
        .documented {{ color: #2ecc71; }}
        .undocumented {{ color: #e74c3c; }}
        .file-header {{ cursor: pointer; padding: 10px; background-color: #2d2d2d; margin-top: 10px; border-radius: 5px; }}
        .file-content {{ display: none; padding: 10px; border: 1px solid #444444; border-radius: 0 0 5px 5px; }}
        .timestamp {{ color: #7f8c8d; font-size: 0.8em; margin-top: 30px; text-align: center; }}
    </style>
</head>
<body>
    <h1>AgentConnect Documentation Coverage Report</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Overall documentation coverage: {coverage['overall_coverage']:.1f}%</p>
        
        <h3>Classes</h3>
        <div class="progress-container">
            <div class="progress-bar {'good' if coverage['class_coverage'] >= 80 else 'warning' if coverage['class_coverage'] >= 50 else 'poor'}" 
                 style="width: {min(100, coverage['class_coverage'])}%">
                {coverage['class_coverage']:.1f}%
            </div>
        </div>
        <p>{stats['documented_classes']}/{stats['total_classes']} classes documented</p>
        
        <h3>Functions</h3>
        <div class="progress-container">
            <div class="progress-bar {'good' if coverage['function_coverage'] >= 80 else 'warning' if coverage['function_coverage'] >= 50 else 'poor'}" 
                 style="width: {min(100, coverage['function_coverage'])}%">
                {coverage['function_coverage']:.1f}%
            </div>
        </div>
        <p>{stats['documented_functions']}/{stats['total_functions']} functions documented</p>
        
        <h3>Methods</h3>
        <div class="progress-container">
            <div class="progress-bar {'good' if coverage['method_coverage'] >= 80 else 'warning' if coverage['method_coverage'] >= 50 else 'poor'}" 
                 style="width: {min(100, coverage['method_coverage'])}%">
                {coverage['method_coverage']:.1f}%
            </div>
        </div>
        <p>{stats['documented_methods']}/{stats['total_methods']} methods documented</p>
    </div>
    
    <h2>Detailed Report</h2>
"""
    
    # Add file details
    for file_path, file_items in by_file.items():
        rel_path = os.path.relpath(file_path, start=str(PROJECT_ROOT))
        
        # Calculate file statistics
        file_total = len(file_items)
        file_documented = sum(1 for item in file_items if item['documented'])
        file_coverage = (file_documented / file_total * 100) if file_total > 0 else 100
        
        html += f"""
    <div class="file-section">
        <div class="file-header" onclick="toggleFile('{rel_path.replace('/', '_')}')">
            {rel_path} - {file_coverage:.1f}% ({file_documented}/{file_total})
        </div>
        <div id="{rel_path.replace('/', '_')}" class="file-content">
            <table>
                <tr>
                    <th>Type</th>
                    <th>Name</th>
                    <th>Line</th>
                    <th>Status</th>
                </tr>
"""
        
        # Sort items by line number
        for item in sorted(file_items, key=lambda x: x['line']):
            status_class = "documented" if item['documented'] else "undocumented"
            status_text = "Documented" if item['documented'] else "Missing Docstring"
            
            html += f"""
                <tr>
                    <td>{item['type'].capitalize()}</td>
                    <td>{item['name']}</td>
                    <td>{item['line']}</td>
                    <td class="{status_class}">{status_text}</td>
                </tr>
"""
        
        html += """
            </table>
        </div>
    </div>
"""
    
    # Add timestamp and JavaScript
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html += f"""
    <div class="timestamp">
        Generated on {timestamp}
    </div>
    
    <script>
        function toggleFile(id) {{
            var content = document.getElementById(id);
            if (content.style.display === "block") {{
                content.style.display = "none";
            }} else {{
                content.style.display = "block";
            }}
        }}
    </script>
</body>
</html>
"""
    
    # Write HTML to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"HTML report saved to {output_file}")


def main():
    """Main function to parse arguments and run the documentation coverage analysis."""
    parser = argparse.ArgumentParser(
        description="Check documentation coverage in the AgentConnect codebase"
    )
    parser.add_argument(
        "--exclude", 
        nargs="+", 
        default=["__pycache__", "tests"],
        help="Directories to exclude from the check"
    )
    parser.add_argument(
        "--html", 
        help="Output HTML report file (default: doc_coverage_report.html)"
    )
    parser.add_argument(
        "--chart", 
        help="Output chart file (default: doc_coverage_chart.png)"
    )
    parser.add_argument(
        "--json", 
        help="Output JSON data file"
    )
    
    args = parser.parse_args()
    
    print(f"Analyzing documentation coverage in {PACKAGE_DIR}...")
    stats, items = scan_directory(PACKAGE_DIR, set(args.exclude))
    
    # Calculate coverage percentages
    coverage = calculate_coverage(stats)
    
    # Print summary to console
    print("\nDocumentation Coverage Summary:")
    print(f"Classes:   {coverage['class_coverage']:.1f}% ({stats['documented_classes']}/{stats['total_classes']})")
    print(f"Functions: {coverage['function_coverage']:.1f}% ({stats['documented_functions']}/{stats['total_functions']})")
    print(f"Methods:   {coverage['method_coverage']:.1f}% ({stats['documented_methods']}/{stats['total_methods']})")
    print(f"Overall:   {coverage['overall_coverage']:.1f}%")
    
    # Ensure coverage directory exists
    coverage_dir = os.path.join(PROJECT_ROOT, "docs", "coverage")
    if not os.path.exists(coverage_dir):
        os.makedirs(coverage_dir)
        print(f"Created directory: {coverage_dir}")
    
    # Generate HTML report
    html_file = args.html or os.path.join(coverage_dir, "doc_coverage_report.html")
    generate_html_report(stats, coverage, items, html_file)
    
    # Generate chart
    if args.chart or not args.html:
        chart_file = args.chart or os.path.join(coverage_dir, "doc_coverage_chart.png")
        generate_coverage_chart(stats, coverage, chart_file)
    
    # Save JSON data if requested
    if args.json:
        json_data = {
            'stats': stats,
            'coverage': coverage,
            'timestamp': datetime.now().isoformat()
        }
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2)
        print(f"JSON data saved to {args.json}")
    
    # Return success
    return 0


if __name__ == "__main__":
    sys.exit(main()) 