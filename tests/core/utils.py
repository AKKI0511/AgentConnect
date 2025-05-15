"""
This module contains utility functions for the tests.
"""

# Color-coded output for better visualization
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    """Print a formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")

def print_step(text):
    """Print a formatted step."""
    print(f"{Colors.BLUE}{Colors.BOLD}➤ {text}{Colors.ENDC}")

def print_success(text):
    """Print a formatted success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_warning(text):
    """Print a formatted warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")

def print_error(text):
    """Print a formatted error message."""
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_result(title, data):
    """Print formatted results."""
    print(f"{Colors.CYAN}{Colors.BOLD}{title}:{Colors.ENDC}")
    if isinstance(data, list):
        for idx, item in enumerate(data):
            if isinstance(item, tuple) and len(item) == 2:
                reg, score = item
                print(f"  {idx+1}. {Colors.BOLD}{reg.name}{Colors.ENDC} ({reg.agent_id}) - Score: {Colors.YELLOW}{score:.4f}{Colors.ENDC}")
                if hasattr(reg, 'description') and reg.description:
                    print(f"     {Colors.CYAN}Description:{Colors.ENDC} {reg.description[:100]}...") # type: ignore
            else:
                print(f"  {idx+1}. {Colors.BOLD}{item.name}{Colors.ENDC} ({item.agent_id})")
                if hasattr(item, 'description') and item.description:
                    print(f"     {Colors.CYAN}Description:{Colors.ENDC} {item.description[:100]}...") # type: ignore
    else:
        print(f"  {data}")
