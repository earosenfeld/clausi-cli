"""Configuration management for the local, BYOK-only CLI."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from clausi.utils.console import console


def get_config_path() -> Path:
    """Get the path to the config file."""
    config_dir = Path.home() / ".clausi"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "config.yml"


def load_config() -> Optional[Dict[str, Any]]:
    """Load configuration from file."""
    config_path = get_config_path()
    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return None


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        return True
    except Exception as e:
        console.print(f"[red]Error saving config: {e}[/red]")
        return False


def get_openai_key() -> Optional[str]:
    """Get OpenAI API key from environment or config."""
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key:
        return openai_key

    config = load_config()
    if config:
        if config.get("api_keys", {}).get("openai"):
            return config["api_keys"]["openai"]
        if config.get("openai_key"):
            return config["openai_key"]

    return None


def get_anthropic_key() -> Optional[str]:
    """Get Anthropic API key from environment or config."""
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    if anthropic_key:
        return anthropic_key

    config = load_config()
    if config and config.get("api_keys", {}).get("anthropic"):
        return config["api_keys"]["anthropic"]

    return None


def get_ai_provider() -> str:
    """Get AI provider from config (defaults to claude if a key is available)."""
    config = load_config()
    if config:
        provider = config.get("ai", {}).get("provider")
        if provider:
            return provider
    return "claude" if get_anthropic_key() else "openai"


DEFAULT_MODELS = {
    "claude": "claude-3-5-sonnet-20241022",
    "openai": "gpt-4o",
}


def _model_belongs_to(model: str, provider: str) -> bool:
    """Whether a configured model name is plausibly for the given provider.

    `ai.model` is a single shared config key, so a user who configured Claude
    and then ran --openai used to send a Claude model name to OpenAI and get a
    confusing 404. Claude model IDs are the only ones we can identify by name,
    so gate on that and let anything else through to OpenAI.
    """
    is_claude_name = model.startswith("claude")
    return is_claude_name if provider == "claude" else not is_claude_name


def get_ai_model(provider: Optional[str] = None) -> str:
    """Get AI model for given provider from config."""
    if not provider:
        provider = get_ai_provider()

    config = load_config() or {}
    ai_config = config.get("ai", {}) or {}

    # Per-provider config wins: ai.models.{provider}
    per_provider = (ai_config.get("models") or {}).get(provider)
    if per_provider:
        return per_provider

    # Legacy shared key, honoured only when it matches the requested provider.
    model = ai_config.get("model")
    if model and _model_belongs_to(model, provider):
        return model

    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openai"])
