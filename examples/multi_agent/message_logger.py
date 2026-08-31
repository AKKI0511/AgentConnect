"""Print a labeled line for the multi-agent demo."""

from __future__ import annotations


def print_colored(message: str, color_type: str = "SYSTEM") -> None:
    """Print ``[color_type] message``. Color type is a label, not a terminal color."""
    print(f"[{color_type}] {message}")
