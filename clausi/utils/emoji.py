"""Console glyphs, with plain-text fallbacks for terminals that cannot draw them."""

import os
import platform
import sys

# Environment variables set by Windows terminals that render emoji: Windows
# Terminal (WT_SESSION), VS Code and other modern emulators (TERM_PROGRAM),
# and Git Bash / MSYS (TERM). The legacy console host - a bare cmd.exe or
# PowerShell window - sets none of them and draws emoji as empty boxes even
# when stdout is UTF-8, so on Windows emoji are opted into per terminal
# rather than assumed.
_WINDOWS_EMOJI_ENV = ("WT_SESSION", "TERM_PROGRAM", "TERM")


def supports_emoji() -> bool:
    """Whether the current terminal can be trusted to draw emoji."""
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    if encoding and "utf" not in encoding:
        return False
    if platform.system() == "Windows":
        return any(os.environ.get(name) for name in _WINDOWS_EMOJI_ENV)
    return True


# name -> (glyph, fallback). Status glyphs keep a short ASCII fallback because
# they carry meaning (this passed, this failed). Decorative glyphs fall back to
# nothing: a heading reads better bare than behind a "[Chart]" placeholder.
_GLYPHS = {
    # Status indicators
    "check": ("\u2713", "[OK]"),
    "cross": ("\u2717", "[X]"),
    "checkmark": ("\u2705", "[OK]"),
    "crossmark": ("\u274c", "[ERROR]"),
    "warning": ("\u26a0\ufe0f", "[!]"),
    "red_circle": ("\U0001f534", "[!]"),
    "yellow_circle": ("\U0001f7e1", "[*]"),
    "green_circle": ("\U0001f7e2", "[+]"),

    # Decorative
    "info": ("\U0001f4a1", ""),
    "search": ("\U0001f50d", ""),
    "folder": ("\U0001f4c1", ""),
    "file": ("\U0001f4c4", ""),
    "clipboard": ("\U0001f4cb", ""),
    "chart": ("\U0001f4ca", ""),
    "credit_card": ("\U0001f4b3", ""),
    "party": ("\U0001f389", ""),

    # Numbers
    "one": ("1\ufe0f\u20e3", "1."),
    "two": ("2\ufe0f\u20e3", "2."),
    "three": ("3\ufe0f\u20e3", "3."),
}


def get(name: str, fallback: str = "") -> str:
    """Glyph for `name`, or its plain-text fallback on terminals without emoji.

    Use this for status marks that sit inside a sentence. For a glyph that
    opens a line, use `lead()` so the fallback does not leave a stray space.
    """
    glyph = _GLYPHS.get(name)
    if glyph is None:
        return fallback
    return glyph[0] if supports_emoji() else glyph[1]


def lead(name: str) -> str:
    """Glyph for `name` followed by a space, or nothing if it has no fallback.

    Example:
        >>> print(f"{lead('search')}Scanning project...")
        (emoji) Scanning project...   # or just "Scanning project..."
    """
    glyph = get(name)
    return f"{glyph} " if glyph else ""


def strip_emoji(text: str) -> str:
    """Remove all emoji characters from text (fallback safety).

    Args:
        text: Input text potentially containing emoji

    Returns:
        str: Text with emoji removed
    """
    if supports_emoji():
        return text

    # Simple emoji removal for safety
    # This catches most common emoji ranges
    import re
    # Unicode emoji ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)
