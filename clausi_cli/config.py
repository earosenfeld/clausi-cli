"""Configuration and token management."""

import os
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import click

console = Console()

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
        # top-level key preferred
        if config.get("openai_key"):
            return config["openai_key"]
        
        # legacy location
        legacy_key = config.get("auth", {}).get("openai_key")
        if legacy_key:
            return legacy_key
    
    return None

def show_token_status():
    """Show token status and remaining credits."""
    token = get_api_token()
    if token:
        console.print(f"[green]✓[/green] API token found: {token[:8]}...")
        # TODO: Add API call to get remaining credits
        console.print("[yellow]Note: Credit status not yet implemented[/yellow]")
    else:
        console.print("[yellow]No API token found[/yellow]")
        console.print("Run a scan to get a trial token or purchase credits.") 