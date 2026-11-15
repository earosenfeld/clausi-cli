"""Singleton console instance for consistent output formatting."""

import sys

from rich.console import Console

# Windows consoles still default to a legacy code page (cp437/cp1252), which
# cannot encode the characters Rich uses to truncate table cells. Without this
# the output showed stray "?" marks mid-word ("CC3-Risk-Assess?"), which reads
# like corrupted data in a compliance tool. Reconfiguring the stream is safe on
# every platform and a no-op when the encoding is already UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Singleton console instance with UTF-8 encoding for Windows
console = Console(legacy_windows=False)

__all__ = ["console"]
