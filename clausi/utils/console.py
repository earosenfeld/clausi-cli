"""Singleton console instance for consistent output formatting."""

from rich.console import Console

# Singleton console instance with UTF-8 encoding for Windows
console = Console(legacy_windows=False)

__all__ = ["console"]
