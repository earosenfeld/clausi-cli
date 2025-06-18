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

console = Console()

# Constants
DEFAULT_API_URL = "https://api.clausi.ai"
DEFAULT_API_TIMEOUT = 300
DEFAULT_API_MAX_RETRIES = 3

# Supported regulations
# NOTE: Users can only choose from these two built-in regulations.
# If additional frameworks are added later, extend this mapping.
REGULATIONS = {
    "EU-AIA": {
        "name": "EU AI Act",
        "description": "European Union Artificial Intelligence Act",
    },
    "GDPR": {
        "name": "GDPR",
        "description": "General Data Protection Regulation",
    },
    "ISO-42001": {
        "name": "ISO 42001",
        "description": "AI Management System – ISO/IEC 42001:2023",
    },
    "HIPAA": {
        "name": "HIPAA",
        "description": "Health Insurance Portability and Accountability Act",
    },
    "SOC2": {
        "name": "SOC 2",
        "description": "System and Organization Controls Type 2",
    },
}

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
def get_config_path():
    """Get the path to the config file."""
    config_dir = Path.home() / ".clausi"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "config.yml"

def create_default_config():
    """Create default config file if it doesn't exist."""
    config_path = get_config_path()
    if not config_path.exists():
        config = {
            "api_key": "",
            "api": {
                "url": DEFAULT_API_URL,
                "timeout": DEFAULT_API_TIMEOUT,
                "max_retries": DEFAULT_API_MAX_RETRIES
            },
            "report": {
                "format": "pdf",
                "output_dir": "reports",
                "company_name": "",
                "company_logo": "",
                "template": "default"
            },
            "regulations": {
                "selected": list(REGULATIONS.keys())  # Default to all regulations
            }
        }
        
        try:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            console.print(f"[green]✓[/green] Created default configuration file at [bold]{config_path}[/bold]")
        except Exception as e:
            console.print(f"[red]✗[/red] Error creating config file: {e}")

def load_config():
    """Load configuration from file."""
    config_path = get_config_path()
    if not config_path.exists():
        create_default_config()
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]✗[/red] Error loading config: {e}")
        return None

def save_config(config):
    """Save configuration to file."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        return True
    except Exception as e:
        console.print(f"[red]✗[/red] Error saving config: {e}")
        return False

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
    config = load_config()
    if not config:
        console.print("[debug] No config file found")
        return None
    
    # top-level key preferred
    if config.get("openai_key"):
        return config["openai_key"]
    
    # legacy location
    legacy_key = config.get("auth", {}).get("openai_key")
    if legacy_key:
        return legacy_key
    
    return None

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

def scan_directory(path: str) -> List[Dict[str, str]]:
    """Scan directory for files to analyze, robustly excluding common junk folders/files and directories."""
    files_to_analyze = []
    path = Path(path)

    # File extensions to analyze
    extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.h', '.hpp', '.c', '.cs', '.go', '.rs', '.swift'}

    # Directories to exclude
    EXCLUDE_DIRS = {"venv", ".git", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
    # File patterns to exclude
    EXCLUDE_FILES = {".DS_Store", "*.egg-info", "*.pyc", "*.pyo"}

    for root, dirs, files in os.walk(path):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            file_path = Path(root) / file
            # Exclude files by name or pattern
            if file in EXCLUDE_FILES or any(file_path.match(pattern) for pattern in EXCLUDE_FILES):
                continue
            if file_path.suffix in extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    files_to_analyze.append({
                        "path": str(file_path.relative_to(path)),
                        "content": content,
                        "type": file_path.suffix[1:],  # Remove the dot
                        "size": os.path.getsize(file_path)
                    })
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not read {file_path}: {e}[/yellow]")
    return files_to_analyze

def ensure_output_dir(path: str, output_dir: Optional[str] = None) -> Path:
    """Ensure output directory exists and return its path. Default to ./reports in the current working directory."""
    if output_dir:
        output_path = Path(output_dir)
    else:
        # Default to reports directory in the current working directory
        output_path = Path.cwd() / "reports"
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path

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

@click.group()
@click.version_option(version="0.1.0", prog_name="Clausi CLI")
def cli():
    """Clausi - AI compliance auditing tool.
    
    A professional tool for auditing AI systems against regulatory requirements.
    """
    # Create default config on first run
    create_default_config()

@cli.group()
def config():
    """Manage Clausi CLI configuration."""
    pass

@config.command()
@click.option("--openai-key", help="Set your OpenAI API key")
@click.option("--timeout", type=int, help="Set API timeout (seconds)")
@click.option("--max-retries", type=int, help="Set API max retries")
@click.option("--company-name", help="Set your company name for reports")
@click.option("--company-logo", type=click.Path(exists=True), help="Set your company logo for reports")
@click.option("--output-dir", type=click.Path(), help="Set default report output directory")
@click.option("--regulations", multiple=True, type=click.Choice(list(REGULATIONS.keys())), help="Set selected regulations (can be given multiple times)")
def set(openai_key: Optional[str], timeout: Optional[int], max_retries: Optional[int],
        company_name: Optional[str], company_logo: Optional[str], output_dir: Optional[str],
        regulations: Optional[List[str]]):
    """Set configuration values."""
    config = load_config()
    
    if openai_key:
        # Store alongside clausi key for simplicity
        config["openai_key"] = openai_key
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
        console.print("[green]✓[/green] Configuration updated successfully")

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
    
    # Add OpenAI key (masked)
    openai_key = config.get("openai_key", "") or config.get("auth", {}).get("openai_key", "")
    masked_openai = "•" * len(openai_key) if openai_key else "Not set"
    table.add_row("OpenAI Key", masked_openai)
    
    # Add API settings
    api = config.get("api", {})
    table.add_row("API URL", DEFAULT_API_URL)
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

@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--regulation", "--regulations", "-r", multiple=True, type=click.Choice(list(REGULATIONS.keys())), help="Regulation(s) to check against. Can be given multiple times, e.g. -r EU-AIA -r GDPR")
@click.option("--mode", type=click.Choice(["ai", "full"]), default="ai", help="Scanning mode (ai/full)")
@click.option("--output", "-o", type=click.Path(), help="Output directory for reports")
@click.option("--openai-key", help="OpenAI API key (overrides config)")
@click.option("--format", type=click.Choice(["pdf", "html", "json"]), default="pdf", help="Report format")
@click.option("--template", type=click.Choice(list(REPORT_TEMPLATES.keys())), help="Report template to use")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--skip-confirmation", is_flag=True, help="Skip the confirmation prompt")
@click.option("--max-cost", type=float, help="Maximum cost in dollars (e.g., --max-cost 1.00)")
@click.option("--show-details", is_flag=True, help="Show per-file token estimates")
def scan(path: str, regulation: Optional[List[str]], mode: str, output: Optional[str], openai_key: Optional[str],
          format: str, template: Optional[str], verbose: bool, skip_confirmation: bool, max_cost: Optional[float],
          show_details: bool):
    """Scan a directory for compliance issues."""
    console.print("\n[debug] Checking for OpenAI key...")
    console.print(f"[debug] Command line key provided: {'Yes' if openai_key else 'No'}")
    
    # Get OpenAI key from command line or config
    if not openai_key:
        openai_key = get_openai_key()
    
    console.print(f"[debug] Final key status: {'Found' if openai_key else 'Not found'}")
    
    if not openai_key:
        console.print("\n[bold yellow]OpenAI API Key Required[/bold yellow]")
        console.print("\nTo use Clausi CLI, you need to set up your OpenAI API key. You can do this in two ways:")
        console.print("\n1. Using the setup wizard:")
        console.print("   [cyan]clausi setup[/cyan]")
        console.print("\n2. Or directly set the key:")
        console.print("   [cyan]clausi config set --openai-key your-key-here[/cyan]")
        console.print("\nYou can get your OpenAI API key from: [link=https://platform.openai.com/api-keys]https://platform.openai.com/api-keys[/link]")
        sys.exit(1)
    
    # Validate OpenAI key
    console.print("[debug] Validating OpenAI key...")
    if not validate_openai_key(openai_key):
        console.print("\n[bold yellow]Invalid OpenAI API Key[/bold yellow]")
        console.print("\nThe provided OpenAI API key appears to be invalid. Please set a valid key using:")
        console.print("\n[cyan]clausi config set --openai-key your-key-here[/cyan]")
        console.print("\nYou can get your OpenAI API key from: [link=https://platform.openai.com/api-keys]https://platform.openai.com/api-keys[/link]")
        sys.exit(1)
    
    console.print("[debug] OpenAI key validation successful")
    
    # Handle regulations (tuple -> list)
    if regulation:
        regulations = list(regulation)
    else:
        cfg = load_config()
        regulations = cfg.get("regulations", {}).get("selected", list(REGULATIONS.keys()))
    
    # Set default template if not specified
    if not template:
        config = load_config()
        template = config.get("report", {}).get("template", "default")
    
    # If output not provided, fall back to config
    if not output:
        cfg = load_config()
        output = cfg.get("report", {}).get("output_dir", "reports") if cfg else "reports"
    # Create output directory
    output_path = ensure_output_dir(path, output)
    
    # Start scanning
    console.print(f"[bold]Starting compliance scan for {path}[/bold]")
    reg_names = ", ".join(REGULATIONS[r]["name"] for r in regulations)
    console.print(f"Regulations: {reg_names}")
    console.print(f"Mode: {mode}")
    
    # Scan directory
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Scanning files...", total=None)
        files = scan_directory(path)
        progress.update(task, completed=True)
    
    if not files:
        console.print("[yellow]No files found to analyze![/yellow]")
        sys.exit(1)
    
    console.print(f"Found {len(files)} files to analyze")
    
    # Prepare the initial request data for token estimation
    data = {
        "path": path,
        "regulations": regulations,
        "mode": mode,
        "metadata": {
            "path": path,
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
        api_url = load_config().get("api", {}).get("url", DEFAULT_API_URL)
        response = requests.post(
            f"{api_url}/api/clausi/estimate",
            json=data,
            headers={
                "X-OpenAI-Key": openai_key,
                "Content-Type": "application/json"
            },
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
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("Analyzing files...", total=None)
            
            try:
                # Send request to backend
                response = requests.post(
                    f"{api_url}/api/clausi/scan",
                    json=data,
                    headers={
                        "X-OpenAI-Key": openai_key,
                        "Content-Type": "application/json"
                    },
                    timeout=300
                )
                
                if response.status_code != 200:
                    console.print(f"[red]Error from backend: {response.text}[/red]")
                    sys.exit(1)
                
                result = response.json()
                progress.update(task, completed=True)
                
                # Save the report
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
                
                # Copy template assets
                copy_template_assets(template, output_path)
                
                console.print(f"[green]Scan completed! Report saved to {output_path}[/green]")
                
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
def setup():
    """Initial setup wizard for Clausi CLI."""
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

def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main() 