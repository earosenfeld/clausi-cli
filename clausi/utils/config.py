"""Configuration and token management."""

import os
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from rich.table import Table
from rich.panel import Panel
import click
from clausi.utils.console import console

# Constants
CONFIG = Path.home() / ".clausi" / "credentials.yml"

def get_config_path() -> Path:
    """Get the path to the config file."""
    config_dir = Path.home() / ".clausi"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "config.yml"

def get_credentials_path() -> Path:
    """Get the path to the credentials file."""
    config_dir = Path.home() / ".clausi"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "credentials.yml"

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

def save_token(token: str) -> bool:
    """Save token to credentials file."""
    try:
        CONFIG.parent.mkdir(exist_ok=True)
        with CONFIG.open("w") as f:
            yaml.safe_dump({"api_token": token}, f)
        return True
    except Exception as e:
        console.print(f"[red]Error saving token: {e}[/red]")
        return False

def load_token() -> Optional[str]:
    """Load token from credentials file."""
    try:
        if CONFIG.exists():
            return yaml.safe_load(CONFIG.read_text()).get("api_token")
        return None
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load credentials: {e}[/yellow]")
        return None

def check_token_status(token: str, api_url: str) -> Optional[Dict[str, Any]]:
    """Check token status and remaining credits."""
    try:
        response = requests.get(
            f"{api_url}/api/clausi/token/status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[red]Error checking token status: {response.status_code}[/red]")
            return None
            
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error connecting to server: {e}[/red]")
        return None

def get_api_token():
    """Get API token from config file."""
    config = load_config()
    if config:
        return config.get('api_token')
    return None

def save_api_token(token: str):
    """Save API token to config file."""
    config = load_config() or {}
    config['api_token'] = token
    return save_config(config)

def get_openai_key() -> Optional[str]:
    """Get OpenAI API key from environment or config."""
    # First try environment variable
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key:
        return openai_key

    # Then try config file
    config = load_config()
    if config:
        # Check new api_keys structure
        if config.get("api_keys", {}).get("openai"):
            return config["api_keys"]["openai"]

        # top-level key preferred (legacy)
        if config.get("openai_key"):
            return config["openai_key"]

        # legacy location
        legacy_key = config.get("auth", {}).get("openai_key")
        if legacy_key:
            return legacy_key

    return None

def get_anthropic_key() -> Optional[str]:
    """Get Anthropic API key from environment or config."""
    # First try environment variable
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    if anthropic_key:
        return anthropic_key

    # Then try config file
    config = load_config()
    if config:
        # Check new api_keys structure
        if config.get("api_keys", {}).get("anthropic"):
            return config["api_keys"]["anthropic"]

    return None

def get_ai_provider() -> str:
    """Get AI provider from config (defaults to claude)."""
    config = load_config()
    if config:
        provider = config.get("ai", {}).get("provider", "claude")
        return provider
    return "claude"

def get_ai_model(provider: str = None) -> str:
    """Get AI model for given provider from config."""
    if not provider:
        provider = get_ai_provider()

    config = load_config()
    if config:
        # Check for provider-specific model in config
        model = config.get("ai", {}).get("model")
        if model:
            return model

    # Default models
    if provider == "claude":
        return "claude-3-5-sonnet-20241022"
    else:  # openai
        return "gpt-4"

def show_balance_status():
    """Show account balance status."""
    import requests
    token = get_api_token()
    if token:
        console.print(f"[green]✓[/green] Account connected: {token[:8]}...")

        # Fetch balance from API
        try:
            api_url = os.environ.get("CLAUSI_TUNNEL_BASE", "https://api.clausi.ai")
            response = requests.get(
                f"{api_url}/api/users/me",
                headers={"X-Clausi-Key": token},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                credits = data.get("credits", data.get("tokens", 0))
                balance_usd = credits * 0.10
                console.print(f"   Balance: [bold]${balance_usd:.2f}[/bold] ({credits} credits)")
            elif response.status_code == 401:
                console.print("[yellow]Session expired. Run 'clausi login' to re-authenticate.[/yellow]")
            else:
                console.print(f"[dim]Could not fetch balance (HTTP {response.status_code})[/dim]")
        except requests.exceptions.RequestException:
            console.print("[dim]Could not connect to server[/dim]")

        console.print("\nManage account: https://clausi.ai/dashboard")
    else:
        console.print("[yellow]No account found[/yellow]")
        console.print("Run 'clausi login' to create an account.") 