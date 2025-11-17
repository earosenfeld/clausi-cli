"""Clausi CLI - AI compliance auditing tool."""

import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import re
import webbrowser
import http.server
import socketserver
import threading
import urllib.parse
import secrets
import time
import site

import click
import requests
import yaml
import openai
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.markdown import Markdown
from rich import print as rprint
from dotenv import load_dotenv
try:
    import pathspec
except ImportError:
    pathspec = None

# Import our modules
from clausi import __version__
from clausi.core import payment as scan_module
from clausi.utils import config as config_module
from clausi.core import clause_selector
from clausi.core import scanner
from clausi.api import client
from clausi.utils.console import console
from clausi.utils.output import ensure_output_dir
from clausi.utils import regulations as regs_module

# Constants
DEFAULT_API_URL = "https://api.clausi.ai"
DEFAULT_API_TIMEOUT = 300
DEFAULT_API_MAX_RETRIES = 3

# Load regulations dynamically (built-in from backend + custom from local)
def get_regulations():
    """Get all available regulations (cached for performance)."""
    if not hasattr(get_regulations, '_cached'):
        built_in, custom = regs_module.get_all_regulations()
        # Merge for backward compatibility with REGULATIONS dict lookups
        get_regulations._cached = {**built_in, **{k: {'name': k, 'description': 'Custom regulation'} for k in custom}}
    return get_regulations._cached

REGULATIONS = get_regulations()  # Backward compatibility

# Report templates
REPORT_TEMPLATES = {
    "default": {
        "name": "Default Template",
        "description": "Standard compliance report with findings and recommendations",
        "sections": ["executive_summary", "findings", "recommendations", "appendix"]
    },
    "detailed": {
        "name": "Detailed Technical Report",
        "description": "Comprehensive technical report with code analysis and detailed findings",
        "sections": ["executive_summary", "methodology", "findings", "code_analysis", "recommendations", "appendix"]
    },
    "executive": {
        "name": "Executive Summary",
        "description": "High-level summary for non-technical stakeholders",
        "sections": ["executive_summary", "key_findings", "risk_assessment", "recommendations"]
    }
}

# Config paths
def create_default_config():
    """Create default config file if it doesn't exist."""
    config_path = config_module.get_config_path()
    if not config_path.exists():
        config = {
            "api_key": "",
            "ai": {
                "provider": "claude",  # Default to Claude
                "model": "claude-3-5-sonnet-20241022",  # Default model
                "fallback_provider": "openai",
                "fallback_model": "gpt-4"
            },
            "api_keys": {
                "anthropic": "",  # Will use ANTHROPIC_API_KEY env var
                "openai": ""  # Will use OPENAI_API_KEY env var
            },
            "api": {
                "url": DEFAULT_API_URL,
                "timeout": DEFAULT_API_TIMEOUT,
                "max_retries": DEFAULT_API_MAX_RETRIES
            },
            "report": {
                "format": "pdf",
                "output_dir": "clausi/reports",
                "company_name": "",
                "company_logo": "",
                "template": "default"
            },
            "regulations": {
                "selected": regs_module.get_regulation_choices()  # Default to all built-in regulations
            },
            "ui": {
                "auto_open_findings": True,  # Auto-open findings.md in editor
                "show_cache_stats": True  # Show cache statistics
            }
        }

        try:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            console.print(f"[green]✓[/green] Created default configuration file at [bold]{config_path}[/bold]")
        except Exception as e:
            console.print(f"[red]✗[/red] Error creating config file: {e}")

# Use load_config and save_config from config_module
# Note: config_module.load_config doesn't auto-create config, so we wrap it
def load_config():
    """Load configuration from file (auto-creates if missing)."""
    config_path = config_module.get_config_path()
    if not config_path.exists():
        create_default_config()
    return config_module.load_config()

save_config = config_module.save_config

def get_clausi_api_key():
    """Get Clausi API key from environment or config."""
    # First try environment variable
    api_key = os.getenv("CLAUSI_API_KEY")
    if api_key:
        return api_key
    
    # Then try config file
    config = load_config()
    if config and config.get("api_key"):
        return config["api_key"]
    
    return None

def get_openai_key() -> Optional[str]:
    """Get OpenAI API key from config file."""
    return config_module.get_openai_key()

def validate_openai_key(key: str) -> bool:
    """Validate the OpenAI API key by making a test request."""
    if not key or not isinstance(key, str) or len(key.strip()) == 0:
        return False
    
    try:
        openai.api_key = key.strip()
        # Make a simple API call to verify the key
        openai.models.list()
        return True
    except Exception as e:
        console.print(f"[yellow]Warning: OpenAI key validation failed: {str(e)}[/yellow]")
        return False

def save_audit_metadata(path: Path, metadata: Dict[str, Any]) -> None:
    """Save audit metadata to a JSON file."""
    metadata_path = path / "audit_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

def copy_template_assets(template: str, output_path: Path) -> None:
    """Copy template assets to output directory."""
    template_dir = Path(__file__).parent / "templates" / template
    if template_dir.exists():
        shutil.copytree(template_dir, output_path / "assets", dirs_exist_ok=True)

# Helper functions for scan command

def _validate_and_get_api_key(provider: str, use_claude_code: bool, openai_key: Optional[str], model: str):
    """Validate and return API key based on provider.

    Returns:
        tuple: (api_key, provider) or exits on validation failure
    """
    if use_claude_code:
        console.print(f"\n[cyan]Using Claude Code CLI (free, no API costs)[/cyan]")
        return None, "claude-code"

    console.print(f"\n[cyan]Using AI: {provider} ({model})[/cyan]")

    if provider == "claude":
        api_key = config_module.get_anthropic_key()
        if not api_key:
            console.print("\n[bold yellow]Anthropic API Key Required[/bold yellow]")
            console.print(f"\nTo use {provider}, you need to set up your Anthropic API key:")
            console.print("\n1. Set it in environment:")
            console.print("   [cyan]export ANTHROPIC_API_KEY=sk-ant-...[/cyan]")
            console.print("\n2. Or add to config:")
            console.print("   [cyan]clausi config set --anthropic-key your-key-here[/cyan]")
            console.print("\n3. Or use free Claude Code CLI:")
            console.print("   [cyan]clausi scan /path --use-claude-code[/cyan]")
            console.print("\nYou can get your Anthropic API key from: [link=https://console.anthropic.com]https://console.anthropic.com[/link]")
            sys.exit(1)
        return api_key, provider
    else:  # openai
        api_key = openai_key or get_openai_key()
        if not api_key:
            console.print("\n[bold yellow]OpenAI API Key Required[/bold yellow]")
            console.print("\nTo use OpenAI, you need to set up your OpenAI API key:")
            console.print("\n1. Using the setup wizard:")
            console.print("   [cyan]clausi setup[/cyan]")
            console.print("\n2. Or directly set the key:")
            console.print("   [cyan]clausi config set --openai-key your-key-here[/cyan]")
            console.print("\n3. Or use free Claude Code CLI:")
            console.print("   [cyan]clausi scan /path --use-claude-code[/cyan]")
            console.print("\nYou can get your OpenAI API key from: [link=https://platform.openai.com/api-keys]https://platform.openai.com/api-keys[/link]")
            sys.exit(1)

        # Validate OpenAI key
        if not validate_openai_key(api_key):
            console.print("\n[bold yellow]Invalid OpenAI API Key[/bold yellow]")
            console.print("\nThe provided OpenAI API key appears to be invalid. Please set a valid key using:")
            console.print("\n[cyan]clausi config set --openai-key your-key-here[/cyan]")
            console.print("\nYou can get your OpenAI API key from: [link=https://platform.openai.com/api-keys]https://platform.openai.com/api-keys[/link]")
            sys.exit(1)

        return api_key, provider

def _get_scan_regulations(regulation: Optional[tuple]) -> List[str]:
    """Get list of regulations to scan against.

    Returns:
        List[str]: List of regulation codes
    """
    if regulation:
        return list(regulation)
    cfg = load_config()
    return cfg.get("regulations", {}).get("selected", regs_module.get_regulation_choices())

def _setup_clause_scoping(select_clauses: bool, include_clauses: Optional[tuple],
                         exclude_clauses: Optional[tuple], preset: Optional[str],
                         regulations: List[str]):
    """Handle clause scoping based on user options.

    Returns:
        tuple: (clauses_include, clauses_exclude)
    """
    clauses_include = None
    clauses_exclude = None

    if select_clauses:
        # Interactive clause selection
        target_reg = regulations[0] if len(regulations) == 1 else None
        if not target_reg and len(regulations) > 1:
            console.print(f"\n[yellow]Multiple regulations selected. Choose one for clause scoping:[/yellow]")
            for i, reg in enumerate(regulations, 1):
                console.print(f"  {i}. {REGULATIONS[reg]['name']}")
            from rich.prompt import Prompt
            choice = Prompt.ask("[cyan]Select regulation[/cyan]", default="1")
            try:
                target_reg = regulations[int(choice) - 1]
            except (ValueError, IndexError):
                target_reg = regulations[0]

        clauses_include, clauses_exclude = clause_selector.select_clauses_interactive(target_reg)

    elif include_clauses:
        clauses_include = list(include_clauses)

    elif exclude_clauses:
        clauses_exclude = list(exclude_clauses)

    elif preset:
        target_reg = regulations[0]
        clauses_include = clause_selector.get_preset_clauses(target_reg, preset)
        if not clauses_include:
            console.print(f"[yellow]Warning: Preset '{preset}' not found for {target_reg}. Scanning all clauses.[/yellow]")
            available = clause_selector.list_available_presets(target_reg)
            if available:
                console.print(f"[cyan]Available presets:[/cyan] {', '.join(available)}")

    # Display clause scope if specified
    if clauses_include or clauses_exclude:
        clause_selector.display_clause_scope_summary(clauses_include, clauses_exclude)

    return clauses_include, clauses_exclude

def _discover_and_filter_files(abs_path: str, ignore: Optional[tuple]) -> List[dict]:
    """Discover and filter files to analyze.

    Returns:
        List[dict]: List of file dictionaries
    """
    from clausi.utils.output import create_enhanced_progress_bar

    with create_enhanced_progress_bar("Scanning project files...") as progress:
        task = progress.add_task("Scanning project files...", total=None)
        files = scanner.scan_directory(abs_path)
        progress.update(task, completed=True)

    if not files:
        console.print("[yellow]No files found to analyze![/yellow]")
        sys.exit(1)

    console.print(f"Found {len(files)} files to analyze")

    # Filter files based on .clausiignore and command-line ignore patterns
    ignore_list = list(ignore) if ignore else None
    files = scanner.filter_ignored_files(files, abs_path, ignore_list)

    if not files:
        console.print("[yellow]No files found to analyze after applying ignore patterns![/yellow]")
        sys.exit(1)

    console.print(f"Analyzing {len(files)} files after filtering")
    return files

@click.group()
@click.version_option(version=__version__, prog_name="Clausi")
def cli():
    """Clausi - AI compliance auditing CLI.

    A professional tool for auditing AI systems against regulatory requirements.

    \b
    Getting Started:
      1. Configure your API key:    clausi setup
      2. Run your first scan:       clausi scan --regulations EU-AIA
      3. Interactive config:        clausi ui config

    \b
    Quick Examples:
      clausi scan --regulations EU-AIA GDPR --format pdf
      clausi scan --preset critical-only --open-findings
      clausi models list
    """
    # Create default config on first run
    create_default_config()

@cli.group()
def config():
    """Manage Clausi CLI configuration."""
    pass

@config.command()
@click.option("--openai-key", help="Set your OpenAI API key")
@click.option("--anthropic-key", help="Set your Anthropic API key")
@click.option("--ai-provider", type=click.Choice(["claude", "openai"]), help="Set default AI provider")
@click.option("--ai-model", help="Set default AI model")
@click.option("--timeout", type=int, help="Set API timeout (seconds)")
@click.option("--max-retries", type=int, help="Set API max retries")
@click.option("--company-name", help="Set your company name for reports")
@click.option("--company-logo", type=click.Path(exists=True), help="Set your company logo for reports")
@click.option("--output-dir", type=click.Path(), help="Set default report output directory")
@click.option("--regulations", multiple=True, type=click.Choice(regs_module.get_regulation_choices()), help="Set selected regulations (can be given multiple times)")
def set(openai_key: Optional[str], anthropic_key: Optional[str], ai_provider: Optional[str], ai_model: Optional[str],
        timeout: Optional[int], max_retries: Optional[int], company_name: Optional[str],
        company_logo: Optional[str], output_dir: Optional[str], regulations: Optional[List[str]]):
    """Set configuration values."""
    config = load_config()

    if openai_key:
        # Store in new api_keys structure
        config.setdefault("api_keys", {})["openai"] = openai_key
        # Also keep legacy location for backward compatibility
        config["openai_key"] = openai_key
    if anthropic_key:
        config.setdefault("api_keys", {})["anthropic"] = anthropic_key
    if ai_provider:
        config.setdefault("ai", {})["provider"] = ai_provider
        console.print(f"[cyan]Set AI provider to: {ai_provider}[/cyan]")
    if ai_model:
        config.setdefault("ai", {})["model"] = ai_model
        console.print(f"[cyan]Set AI model to: {ai_model}[/cyan]")
    if timeout is not None:
        config.setdefault("api", {})["timeout"] = timeout
    if max_retries is not None:
        config.setdefault("api", {})["max_retries"] = max_retries
    if company_name:
        config["report"]["company_name"] = company_name
    if company_logo:
        config["report"]["company_logo"] = company_logo
    if output_dir:
        config["report"]["output_dir"] = output_dir
    if regulations:
        config.setdefault("regulations", {})["selected"] = list(regulations)

    if save_config(config):
        console.print("[green]Configuration updated successfully[/green]")

@config.command()
def show():
    """Show current configuration."""
    console.print(f"Configuration file path: [bold]{get_config_path()}[/bold]\n")
    config = load_config()
    if not config:
        return

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Add AI Provider settings
    ai_settings = config.get("ai", {})
    table.add_row("AI Provider", ai_settings.get("provider", "claude (default)"))
    table.add_row("AI Model", ai_settings.get("model", "claude-3-5-sonnet-20241022 (default)"))

    # Add API keys (masked)
    api_keys = config.get("api_keys", {})
    anthropic_key = api_keys.get("anthropic", "") or os.getenv("ANTHROPIC_API_KEY", "")
    masked_anthropic = "•" * 20 if anthropic_key else "Not set"
    table.add_row("Anthropic Key", masked_anthropic)

    openai_key = api_keys.get("openai", "") or config.get("openai_key", "") or config.get("auth", {}).get("openai_key", "")
    masked_openai = "•" * 20 if openai_key else "Not set"
    table.add_row("OpenAI Key", masked_openai)

    # Add Clausi API token
    api_token = config.get("api_token", "")
    if api_token:
        # Show first 8 and last 4 characters
        masked_token = f"{api_token[:8]}...{api_token[-4:]}"
    else:
        masked_token = "Not set"
    table.add_row("Clausi API Token", masked_token)

    # Add API settings
    api = config.get("api", {})
    
    # Show API URL with tunnel indicator
    current_api_url = get_api_url()
    tunnel_base = os.getenv('CLAUSI_TUNNEL_BASE')
    if tunnel_base:
        api_url_display = f"{current_api_url} (via CLAUSI_TUNNEL_BASE)"
    else:
        api_url_display = current_api_url
    table.add_row("API URL", api_url_display)
    
    table.add_row("API Timeout", str(api.get("timeout", DEFAULT_API_TIMEOUT)))
    table.add_row("API Max Retries", str(api.get("max_retries", DEFAULT_API_MAX_RETRIES)))
    
    # Add report settings
    report = config.get("report", {})
    table.add_row("Report Format", report.get("format", "pdf"))
    table.add_row("Output Directory", report.get("output_dir", "reports"))
    table.add_row("Company Name", report.get("company_name", "Not set"))
    table.add_row("Company Logo", report.get("company_logo", "Not set"))
    table.add_row("Report Template", report.get("template", "default"))
    
    # Add regulation settings
    regulations = config.get("regulations", {})
    selected_regs = regulations.get("selected", list(REGULATIONS.keys()))
    table.add_row("Selected Regulations", ", ".join(selected_regs))
    
    console.print(table)

@config.command()
def path():
    """Print the full path to the configuration file."""
    console.print(f"Configuration file path: [bold]{get_config_path()}[/bold]")

@cli.group()
def models():
    """Manage AI models."""
    pass

@models.command('list')
def list_models():
    """List available AI models."""
    table = Table(title="Available AI Models")
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Context", style="yellow")
    table.add_column("Cost/1M tokens", style="magenta")
    table.add_column("Speed", style="blue")
    table.add_column("Recommended", style="white")

    # Claude models
    table.add_row(
        "Claude",
        "claude-3-5-sonnet-20241022",
        "200k",
        "$3 / $15",
        "Fast",
        "Default"
    )
    table.add_row(
        "Claude",
        "claude-3-opus-20240229",
        "200k",
        "$15 / $75",
        "Medium",
        ""
    )
    table.add_row(
        "Claude",
        "claude-3-sonnet-20240229",
        "200k",
        "$3 / $15",
        "Fast",
        ""
    )

    # OpenAI models
    table.add_row(
        "OpenAI",
        "gpt-4",
        "128k",
        "$30 / $60",
        "Medium",
        ""
    )
    table.add_row(
        "OpenAI",
        "gpt-4-turbo",
        "128k",
        "$10 / $30",
        "Fast",
        ""
    )
    table.add_row(
        "OpenAI",
        "gpt-4o",
        "128k",
        "$5 / $15",
        "Fast",
        ""
    )

    console.print(table)
    console.print("\n[cyan]Tip: Claude 3.5 Sonnet is recommended (faster, cheaper, better compliance analysis)[/cyan]")
    console.print("\n[yellow]Usage:[/yellow]")
    console.print("  [cyan]clausi scan . --ai-provider claude --ai-model claude-3-5-sonnet-20241022[/cyan]")
    console.print("  [cyan]clausi scan . --ai-provider openai --ai-model gpt-4o[/cyan]")
    console.print("\n[yellow]Set default in config:[/yellow]")
    console.print("  [cyan]clausi config set --ai-provider claude[/cyan]")

@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--regulation", "--regulations", "-r", multiple=True, type=click.Choice(regs_module.get_regulation_choices()), help="Regulation(s) to check against (built-in + custom). Can be given multiple times, e.g. -r EU-AIA -r GDPR")
@click.option("--mode", type=click.Choice(["ai", "full"]), default="ai", help="Scanning mode (ai/full)")
@click.option("--output", "-o", type=click.Path(), help="Output directory for reports")
@click.option("--openai-key", help="OpenAI API key (overrides config)")
@click.option("--use-claude-code", is_flag=True, help="Use free Claude Code CLI (no API key required)")
@click.option("--ai-provider", type=click.Choice(["claude", "openai"]), help="AI provider to use (default: from config or claude)")
@click.option("--ai-model", type=str, help="Specific AI model to use")
@click.option("--select-clauses", is_flag=True, help="Interactively select clauses to scan")
@click.option("--include", "include_clauses", multiple=True, help="Include specific clauses (can be given multiple times, e.g. --include EUAIA-3.1)")
@click.option("--exclude", "exclude_clauses", multiple=True, help="Exclude specific clauses (can be given multiple times)")
@click.option("--preset", type=str, help="Use predefined clause preset (e.g., critical-only, high-priority)")
@click.option("--format", type=click.Choice(["pdf", "html", "json", "all"]), default="pdf", help="Report format (use 'all' for PDF, HTML, and JSON)")
@click.option("--template", type=click.Choice(list(REPORT_TEMPLATES.keys())), help="Report template to use")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--skip-confirmation", is_flag=True, help="Skip the confirmation prompt")
@click.option("--max-cost", type=float, help="Maximum cost in dollars (e.g., --max-cost 1.00)")
@click.option("--show-details", is_flag=True, help="Show per-file token estimates")
@click.option("--min-severity", type=click.Choice(["info", "warning", "high", "critical"]), default="info", help="Minimum severity to report")
@click.option("--ignore", multiple=True, help="Ignore files/directories (can be given multiple times)")
@click.option("--open-findings", is_flag=True, help="Auto-open findings.md in default editor after scan")
@click.option("--show-markdown", is_flag=True, help="Display markdown findings summary in terminal")
@click.option("--show-cache-stats/--no-cache-stats", default=None, help="Show/hide cache statistics (default: from config)")
def scan(path: str, regulation: Optional[List[str]], mode: str, output: Optional[str], openai_key: Optional[str],
          use_claude_code: bool, ai_provider: Optional[str], ai_model: Optional[str], select_clauses: bool, include_clauses: Optional[List[str]],
          exclude_clauses: Optional[List[str]], preset: Optional[str], format: str, template: Optional[str], verbose: bool,
          skip_confirmation: bool, max_cost: Optional[float], show_details: bool, min_severity: str, ignore: Optional[List[str]],
          open_findings: bool, show_markdown: bool, show_cache_stats: Optional[bool]):
    """Run compliance audit on your codebase (main command)."""
    # Check payment requirements before estimate (for full mode)
    # This should happen BEFORE API key validation
    if mode == "full":
        api_url = get_api_url()
        if not scan_module.check_payment_required(api_url, mode):
            return  # Exit if payment required

    # Determine AI provider
    provider = ai_provider or config_module.get_ai_provider()
    model = ai_model or config_module.get_ai_model(provider)

    # Validate and get API key
    api_key, provider = _validate_and_get_api_key(provider, use_claude_code, openai_key, model)
    # For backward compatibility, keep openai_key variable
    openai_key = api_key

    # Get regulations to scan against
    regulations = _get_scan_regulations(regulation)

    # Handle clause scoping
    clauses_include, clauses_exclude = _setup_clause_scoping(
        select_clauses, include_clauses, exclude_clauses, preset, regulations
    )

    # Set default template if not specified
    if not template:
        config = load_config()
        template = config.get("report", {}).get("template", "default")
    
    # Convert path to absolute path early
    # This ensures the backend creates output in the correct location
    abs_path = os.path.abspath(path)

    # If output not provided, fall back to config
    if not output:
        cfg = load_config()
        output = cfg.get("report", {}).get("output_dir", "clausi/reports") if cfg else "clausi/reports"
    # Create output directory
    output_path = ensure_output_dir(abs_path, output)

    # Start scanning
    console.print(f"[bold]Starting compliance scan for {abs_path}[/bold]")
    reg_names = ", ".join(REGULATIONS[r]["name"] for r in regulations)
    console.print(f"Regulations: {reg_names}")
    console.print(f"Mode: {mode}")
    console.print(f"Minimum Severity: {min_severity}")

    # Discover and filter files
    files = _discover_and_filter_files(abs_path, ignore)

    # Separate built-in and custom regulations
    custom_regs_data = regs_module.get_custom_regulations_for_scan(regulations)
    built_in_regs = [r for r in regulations if r not in [cr['code'] for cr in custom_regs_data]]

    # Prepare the initial request data for token estimation
    data = {
        "path": abs_path,  # Use absolute path
        "regulations": built_in_regs,  # Only built-in regulations
        "custom_regulations": custom_regs_data,  # Custom regulation YAML content
        "mode": mode,
        "min_severity": min_severity,
        "ai_provider": provider,  # NEW: AI provider selection
        "ai_model": model,        # NEW: AI model selection
        "clauses_include": clauses_include,  # NEW: Clause scoping (include list)
        "clauses_exclude": clauses_exclude,  # NEW: Clause scoping (exclude list)
        "metadata": {
            "path": abs_path,  # Use absolute path
            "files": files,
            "timestamp": datetime.utcnow().isoformat(),
            "format": format,
            "template": template,
            "company": {
                "name": load_config().get("report", {}).get("company_name", ""),
                "logo": load_config().get("report", {}).get("company_logo", "")
            }
        },
        "estimate_only": True  # Flag to indicate this is just for estimation
    }
    
    # Get token estimates from backend
    try:
        api_url = get_api_url()

        # Construct headers with appropriate API key header based on provider
        headers = {"Content-Type": "application/json"}
        # Only add API key header if we have one (not using Claude Code CLI)
        if openai_key:
            if provider == "claude":
                headers["X-Anthropic-Key"] = openai_key  # Note: variable name is openai_key for backward compatibility
            else:  # openai
                headers["X-OpenAI-Key"] = openai_key

        response = requests.post(
            f"{api_url}/api/clausi/estimate",
            json=data,
            headers=headers,
            timeout=300
        )
        
        if response.status_code != 200:
            console.print(f"[red]Error from backend: {response.text}[/red]")
            sys.exit(1)
        
        estimate = response.json()
        
        # Display token estimates
        console.print("\n[bold]Estimated Token Usage:[/bold]")
        console.print(f"Total Tokens: {estimate['total_tokens']:,}")
        console.print(f"- Prompt Tokens: {estimate['prompt_tokens']:,}")
        console.print(f"- Completion Tokens: {estimate['completion_tokens']:,}")
        console.print(f"Estimated Cost: ${estimate['estimated_cost']:.2f}")
        
        # Show per-regulation breakdown
        console.print("\n[bold]Per Regulation Breakdown:[/bold]")
        for reg in estimate['regulation_breakdown']:
            console.print(f"\n{REGULATIONS[reg['regulation']]['name']}:")
            console.print(f"- Total Tokens: {reg['total_tokens']:,}")
            console.print(f"- Estimated Cost: ${reg['estimated_cost']:.2f}")
        
        # Show per-file breakdown if requested
        if show_details:
            console.print("\n[bold]Per File Breakdown:[/bold]")
            for file in estimate['file_breakdown']:
                console.print(f"\n{file['path']}:")
                console.print(f"- Tokens: {file['tokens']:,}")
                console.print(f"- Estimated Cost: ${file['estimated_cost']:.2f}")
                if file.get('too_large', False):
                    console.print(f"[red]- File is too large to analyze[/red]")
        
        # Check against max cost if specified
        if max_cost is not None and estimate['estimated_cost'] > max_cost:
            console.print(f"\n[red]Error: Estimated cost (${estimate['estimated_cost']:.2f}) exceeds maximum cost (${max_cost:.2f})[/red]")
            sys.exit(1)
        
        # Check for file size limits
        for file in estimate['file_breakdown']:
            if file.get('too_large', False):
                console.print(f"\n[red]Error: File {file['path']} is too large to analyze[/red]")
                sys.exit(1)
        
        # Get user confirmation unless skipped
        if not skip_confirmation:
            if not click.confirm(f"\nProceed with analysis? Estimated cost: ${estimate['estimated_cost']:.2f}"):
                console.print("[yellow]Analysis cancelled by user[/yellow]")
                sys.exit(0)
        
        # Proceed with full analysis
        data['estimate_only'] = False  # Remove the estimation flag

        try:
            # Use async scan request (with job polling) to prevent timeouts on large scans
            result = scan_module.make_async_scan_request(get_api_url(), openai_key, provider, data)
            if not result:
                console.print("[red]Scan failed[/red]")
                sys.exit(1)

            # Handle multiple report formats
            if result.get("generated_reports"):
                console.print("[yellow]Saving reports...[/yellow]")
                for report_info in result["generated_reports"]:
                    report_format = report_info["format"]
                    report_filename = report_info["filename"]

                    try:
                        # Download report from backend
                        headers = {}
                        if openai_key:
                            headers["Authorization"] = f"Bearer {openai_key}"
                        response = requests.get(
                            f"{get_api_url()}/api/clausi/report/{report_filename}",
                            headers=headers,
                            timeout=60
                        )

                        if response.status_code == 200:
                            report_path = output_path / report_filename
                            with open(report_path, 'wb') as f:
                                f.write(response.content)
                            console.print(f"[green]{report_format.upper()} report saved to: {report_path}[/green]")
                        else:
                            console.print(f"[red]Failed to download {report_format} report: {response.status_code}[/red]")
                    except Exception as e:
                        console.print(f"[red]Error downloading {report_format} report: {str(e)}[/red]")
            else:
                # Backward compatibility - save single report
                if result.get("report_content") and result.get("report_filename"):
                    console.print("[yellow]Saving report...[/yellow]")
                    report_path = output_path / result["report_filename"]
                    with open(report_path, 'wb') as f:
                        f.write(bytes.fromhex(result["report_content"]))
                    console.print(f"[green]Report saved to: {report_path}[/green]")

            # Save metadata
            metadata = {
                "timestamp": datetime.utcnow().isoformat(),
                "path": path,
                "regulations": regulations,
                "mode": mode,
                "files_analyzed": len(files),
                "template": template,
                "format": format,
                "ai_provider": provider,  # NEW: Record AI provider used
                "ai_model": model,        # NEW: Record AI model used
                "clauses_include": clauses_include,  # NEW: Record clause scope
                "clauses_exclude": clauses_exclude,  # NEW: Record clause scope
                "findings": result.get("findings", []),
                "token_usage": result.get("token_usage", {})
            }
            save_audit_metadata(output_path, metadata)

            # Display findings
            if result.get("findings"):
                table = Table(title="Compliance Findings")
                table.add_column("Clause", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Severity", style="yellow")
                table.add_column("Location", style="blue")
                table.add_column("Description", style="white")

                for finding in result["findings"]:
                    status = "✓" if not finding.get("violation") else "✗"
                    status_style = "green" if not finding.get("violation") else "red"
                    table.add_row(
                        finding.get("clause_id", ""),
                        f"[{status_style}]{status}[/{status_style}]",
                        finding.get("severity", ""),
                        finding.get("location", ""),
                        finding.get("description", "")
                    )

                console.print(table)

            # Display actual token usage
            if "token_usage" in result:
                token_usage = result["token_usage"]
                console.print("\n[bold]Actual Token Usage:[/bold]")
                console.print(f"Total tokens used: {token_usage.get('total_tokens', 0):,}")
                console.print(f"Actual cost: ${token_usage.get('cost', 0):.2f}")

            # Display cache statistics if available and enabled
            cfg = load_config()
            # Use command-line flag if provided, otherwise fall back to config
            display_cache = show_cache_stats if show_cache_stats is not None else cfg.get("ui", {}).get("show_cache_stats", True)

            if display_cache and "cache_stats" in result:
                from clausi.utils.output import display_cache_statistics
                display_cache_statistics(result["cache_stats"])

            # Copy template assets
            copy_template_assets(template, output_path)

            # Get actual output directory from backend response
            actual_output_dir = result.get("output_dir")
            if actual_output_dir:
                console.print(f"[green]Scan completed! Reports saved to {actual_output_dir}[/green]")
            else:
                console.print(f"[green]Scan completed![/green]")

            # Handle markdown outputs
            from clausi.utils.output import (
                download_markdown_files,
                display_findings_summary,
                open_in_editor
            )

            # Check if backend provided markdown files (run_id in response)
            run_id = result.get("run_id")
            if run_id:
                console.print("\n[cyan]📄 Markdown reports available...[/cyan]")
                markdown_files = download_markdown_files(
                    api_url=get_api_url(),
                    run_id=run_id,
                    output_dir=output_path,
                    api_key=openai_key
                )

                if markdown_files:
                    console.print(f"[green]✓ Downloaded {len(markdown_files)} markdown file(s)[/green]")

                    # Find findings.md
                    findings_md = output_path / "findings.md"

                    # Display markdown summary if requested or if config says so
                    cfg = load_config()
                    auto_show = show_markdown or cfg.get("ui", {}).get("show_markdown", False)

                    if auto_show and findings_md.exists():
                        display_findings_summary(findings_md)

                    # Auto-open findings.md if requested or if config says so
                    auto_open = open_findings or cfg.get("ui", {}).get("auto_open_findings", True)

                    if auto_open and findings_md.exists():
                        open_in_editor(findings_md)

                if actual_output_dir:
                    console.print(f"\n[cyan]📁 Complete report package available at: {actual_output_dir}[/cyan]")
                    console.print(f"[dim]  • findings.md - Detailed compliance findings[/dim]")
                    console.print(f"[dim]  • compliance_report.md - Executive summary[/dim]")
                    console.print(f"[dim]  • traceability_matrix.md - Clause coverage matrix[/dim]")
                    console.print(f"[dim]  • REMEDIATION.md - AI-powered remediation guide[/dim]")
                    console.print(f"[dim]  • report.pdf - Full PDF report[/dim]")

        except requests.exceptions.RequestException as e:
            console.print(f"[red]Error connecting to backend: {str(e)}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error during analysis: {str(e)}[/red]")
            sys.exit(1)
                
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error connecting to backend: {str(e)}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error during estimation: {str(e)}[/red]")
        sys.exit(1)

@cli.command()
def tokens():
    """Show token status and remaining credits for full-mode scans."""
    config_module.show_token_status()

@cli.command()
def setup():
    """Configure API keys and settings (first-time setup)."""
    console.print(Panel.fit(
        "Welcome to Clausi CLI Setup!\n\n"
        "This wizard will help you configure Clausi CLI for first use.",
        title="Setup Wizard"
    ))
    
    # Get OpenAI API key
    openai_key = click.prompt("Enter your OpenAI API key", type=str)
    if not validate_openai_key(openai_key):
        console.print("[red]Error: Invalid OpenAI API key[/red]")
        sys.exit(1)
    
    # Get company information
    company_name = click.prompt("Enter your company name (optional)", type=str, default="")
    company_logo = click.prompt("Enter path to company logo (optional)", type=str, default="")
    
    # Get default regulation
    regulation = click.prompt(
        "Choose default regulation",
        type=click.Choice(list(REGULATIONS.keys())),
        default="EU-AIA"
    )
    
    # Get default template
    template = click.prompt(
        "Choose default report template",
        type=click.Choice(list(REPORT_TEMPLATES.keys())),
        default="default"
    )
    
    # Save configuration
    config = {
        "openai_key": openai_key,
        "report": {
            "company_name": company_name,
            "company_logo": company_logo,
            "template": template
        },
        "regulations": {
            "selected": [regulation]
        },
        "api": {
            "url": "https://api.clausi.ai",
            "timeout": 300,
            "max_retries": 3
        }
    }
    if save_config(config):
        console.print("[green]✓[/green] Setup completed successfully!")
        console.print("\nYou can now use 'clausi scan' to start scanning your projects.")

@config.command()
def edit():
    """Open the configuration file in your default editor (uses $EDITOR or Notepad)."""
    path = get_config_path()
    editor = os.getenv("EDITOR") or ("notepad" if os.name == "nt" else "vi")
    console.print(f"Opening config file: [bold]{path}[/bold] with [cyan]{editor}[/cyan]")
    try:
        os.system(f"{editor} {path}")
    except Exception as e:
        console.print(f"[red]✗[/red] Could not open editor: {e}")

@cli.group()
def ui():
    """Launch interactive mode with visual menus and forms."""
    pass

@ui.command(name="config")
def ui_config():
    """Launch interactive configuration editor."""
    try:
        from clausi.tui.app import run_tui
        console.print("[cyan]Launching interactive configuration editor...[/cyan]")
        run_tui(mode="config")
    except ImportError:
        console.print("[red]Error: Textual not installed. Run: pip install textual[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error launching TUI: {str(e)}[/red]")
        sys.exit(1)

@ui.command(name="scan")
def ui_scan():
    """Launch interactive scan builder (coming soon)."""
    console.print("[yellow]Scan builder TUI is coming soon![/yellow]")
    console.print("\nIn the meantime, use the regular scan command:")
    console.print("  [cyan]clausi scan . --preset critical-only[/cyan]")

@ui.command(name="dashboard")
def ui_dashboard():
    """Launch main TUI dashboard."""
    try:
        from clausi.tui.app import run_tui
        console.print("[cyan]Launching Clausi interactive dashboard...[/cyan]")
        run_tui(mode="main")
    except ImportError:
        console.print("[red]Error: Textual not installed. Run: pip install textual[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error launching TUI: {str(e)}[/red]")
        sys.exit(1)

@cli.command()
@click.argument("token", required=False)
@click.option("--port", default=8123, help="Port for OAuth callback server (default: 8123)")
def login(token: Optional[str], port: int):
    """Authenticate with Clausi using OAuth or API token.

    Usage:
      clausi login                    # OAuth flow (opens browser)
      clausi login <token>            # Manual token entry
    """
    from clausi.utils.config import save_api_token, get_api_token
    from clausi.utils.emoji import get as emoji

    # If token provided directly, save it
    if token:
        if save_api_token(token):
            console.print(f"\n{emoji('checkmark')} Token saved successfully!")
            console.print(f"   Token: {token[:8]}...{token[-4:]}")
            console.print(f"\n{emoji('party')} You're now authenticated! Run a scan to get started.")
        else:
            console.print(f"\n{emoji('crossmark')} Failed to save token")
            sys.exit(1)
        return

    # OAuth flow
    console.print(f"\n{emoji('key')} Starting OAuth login flow...\n")

    # Generate session code for security
    session_code = secrets.token_urlsafe(32)
    received_token = {"value": None}
    server_ready = threading.Event()

    # Create callback handler
    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if parsed.path == "/callback":
                token_param = params.get("token", [None])[0]
                session_param = params.get("session", [None])[0]

                if token_param and session_param == session_code:
                    received_token["value"] = token_param

                    # Send success page
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html><body style="font-family: system-ui; text-align: center; padding: 50px;">
                            <h1 style="color: #10b981;">Authentication Successful!</h1>
                            <p>You can close this window and return to the terminal.</p>
                        </body></html>
                    """)
                else:
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html><body style="font-family: system-ui; text-align: center; padding: 50px;">
                            <h1 style="color: #ef4444;">Authentication Failed</h1>
                            <p>Invalid session or token. Please try again.</p>
                        </body></html>
                    """)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress request logs

    # Start local server
    try:
        with socketserver.TCPServer(("127.0.0.1", port), CallbackHandler) as httpd:
            server_ready.set()

            # Get API URL
            api_url = get_api_url()

            # Construct OAuth URL
            auth_url = f"{api_url}/cli-auth?session={session_code}&port={port}"

            console.print(f"{emoji('info')} Opening browser to authenticate...")
            console.print(f"   URL: {auth_url}\n")

            # Open browser
            try:
                webbrowser.open(auth_url)
            except Exception as e:
                console.print(f"{emoji('warning')} Could not open browser automatically: {e}")
                console.print(f"\nPlease open this URL manually:\n{auth_url}\n")

            console.print(f"{emoji('hourglass')} Waiting for authentication...\n")

            # Wait for callback with timeout
            timeout_seconds = 300  # 5 minutes
            start_time = time.time()

            while not received_token["value"]:
                httpd.handle_request()
                if time.time() - start_time > timeout_seconds:
                    console.print(f"\n{emoji('crossmark')} Authentication timed out after {timeout_seconds} seconds")
                    sys.exit(1)
                if received_token["value"]:
                    break

            # Save token
            if received_token["value"]:
                if save_api_token(received_token["value"]):
                    console.print(f"\n{emoji('checkmark')} Authentication successful!")
                    console.print(f"   Token: {received_token['value'][:8]}...{received_token['value'][-4:]}")
                    console.print(f"\n{emoji('party')} You're now authenticated! Run a scan to get started.")
                else:
                    console.print(f"\n{emoji('crossmark')} Failed to save token")
                    sys.exit(1)

    except OSError as e:
        if "Address already in use" in str(e):
            console.print(f"\n{emoji('crossmark')} Port {port} is already in use")
            console.print(f"   Try a different port with: clausi login --port <PORT>")
        else:
            console.print(f"\n{emoji('crossmark')} Error starting callback server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print(f"\n\n{emoji('crossmark')} Authentication cancelled")
        sys.exit(1)

def get_api_url() -> str:
    """Get the API URL, prioritizing CLAUSI_TUNNEL_BASE environment variable."""
    # First check for tunnel base URL
    tunnel_base = os.getenv('CLAUSI_TUNNEL_BASE')
    if tunnel_base:
        return tunnel_base.rstrip('/')
    
    # Then check config file
    config = load_config()
    if config and config.get("api", {}).get("url"):
        return config["api"]["url"]
    
    # Fall back to default
    return DEFAULT_API_URL

def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main() 