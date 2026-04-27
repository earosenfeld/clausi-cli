"""Cross-platform emoji support with ASCII fallbacks for Windows."""

import sys
import platform


def supports_emoji() -> bool:
    """Check if the current console supports emoji characters.

    Returns:
        bool: True if emoji is supported, False otherwise
    """
    # Check if we're on Windows
    if platform.system() == "Windows":
        # Windows 10+ with WT supports emoji, but cmd.exe doesn't
        # Safest is to disable emoji on Windows to avoid crashes
        return False

    # Check if stdout encoding supports Unicode
    if hasattr(sys.stdout, 'encoding'):
        encoding = sys.stdout.encoding or ''
        # ASCII or charmap encodings don't support emoji
        if encoding.lower() in ('ascii', 'charmap', 'cp1252'):
            return False

    return True


# Emoji map with ASCII fallbacks
EMOJI_MAP = {
    # Status indicators
    "check": "✓" if supports_emoji() else "[OK]",
    "cross": "✗" if supports_emoji() else "[X]",
    "checkmark": "✅" if supports_emoji() else "[OK]",
    "crossmark": "❌" if supports_emoji() else "[ERROR]",
    "warning": "⚠️" if supports_emoji() else "[!]",
    "info": "💡" if supports_emoji() else "[i]",

    # Status colors
    "red_circle": "🔴" if supports_emoji() else "[!]",
    "yellow_circle": "🟡" if supports_emoji() else "[*]",
    "green_circle": "🟢" if supports_emoji() else "[+]",

    # Actions
    "search": "🔍" if supports_emoji() else "[Search]",
    "folder": "📁" if supports_emoji() else "[Folder]",
    "file": "📄" if supports_emoji() else "[File]",
    "clipboard": "📋" if supports_emoji() else "[List]",
    "chart": "📊" if supports_emoji() else "[Chart]",
    "credit_card": "💳" if supports_emoji() else "[Payment]",
    "party": "🎉" if supports_emoji() else "[!]",

    # Numbers
    "one": "1️⃣" if supports_emoji() else "1.",
    "two": "2️⃣" if supports_emoji() else "2.",
    "three": "3️⃣" if supports_emoji() else "3.",
}


def get(name: str, fallback: str = "") -> str:
    """Get emoji by name with automatic fallback for unsupported terminals.

    Args:
        name: Emoji name from EMOJI_MAP
        fallback: Custom fallback if emoji name not found

    Returns:
        str: Emoji character or ASCII fallback

    Example:
        >>> from clausi.utils.emoji import get
        >>> print(f"{get('check')} Success")
        ✓ Success  # or [OK] Success on Windows
    """
    return EMOJI_MAP.get(name, fallback)


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
