"""Clausi CLI - free, local, BYOK AI compliance auditing tool.

Everything (file discovery, AI scanning, clause matching, report
generation) runs on your machine. No Clausi account or backend is
involved - you bring your own Anthropic or OpenAI API key and pay
that provider directly.
"""

import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import click
import yaml
import openai
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Import our modules
from clausi import __version__
from clausi.utils import config as config_module
from clausi.core import clause_selector
from clausi.core import scanner
from clausi.core import compliance_analyzer
from clausi.core.ai_provider import get_ai_provider, estimate_tokens
from clausi.core.cache import LocalCache
from clausi.core.markdown_report import MarkdownGenerator
from clausi.utils.console import console
from clausi.utils.output import ensure_output_dir
from clausi.utils import regulations as regs_module
from clausi.utils.emoji import get as emoji

# Lazy-loaded regulation registry (built-in bundled + custom, all local - no network)
_REGULATIONS_CACHE = None


def get_regulations():
    """Get all available regulations (name/description), cached for performance."""
    global _REGULATIONS_CACHE
    if _REGULATIONS_CACHE is None:
        built_in, custom = regs_module.get_all_regulations()
        _REGULATIONS_CACHE = {**built_in, **{k: {'name': k, 'description': 'Custom regulation'} for k in custom}}
    return _REGULATIONS_CACHE


def create_default_config():
    """Create default config file if it doesn't exist."""
    config_path = config_module.get_config_path()
    if not config_path.exists():
        config = {
            "ai": {
                "provider": "claude",
                "model": "claude-3-5-sonnet-20241022",
            },
            "api_keys": {
                "anthropic": "",  # Prefer the ANTHROPIC_API_KEY env var
                "openai": "",     # Prefer the OPENAI_API_KEY env var
            },
            "report": {
                "output_dir": "clausi/reports",
                "company_name": "",
                "company_logo": "",
            },
            "regulations": {
                "selected": regs_module.get_regulation_choices()
            },
            "cache": {
                "enabled": True,
                "ttl_days": 30
            },
            "ui": {
                "auto_open_findings": True,
                "show_cache_stats": True
            }
        }

        try:
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            console.print(f"[green]{emoji('checkmark')}[/green] Created default configuration file at [bold]{config_path}[/bold]")
        except Exception as e:
            console.print(f"[red]{emoji('crossmark')}[/red] Error creating config file: {e}")


def load_config():
    """Load configuration from file (auto-creates if missing)."""
    config_path = config_module.get_config_path()
    if not config_path.exists():
        create_default_config()
    return config_module.load_config()


save_config = config_module.save_config


def validate_openai_key(key: str) -> bool:
    """Validate the OpenAI API key by making a test request."""
    if not key or not isinstance(key, str) or len(key.strip()) == 0:
        return False

    try:
        openai.OpenAI(api_key=key.strip()).models.list()
        return True
    except Exception as e:
        console.print(f"[yellow]Warning: OpenAI key validation failed: {str(e)}[/yellow]")
        return False


def save_audit_metadata(path: Path, metadata: Dict[str, Any]) -> None:
    """Save audit metadata to a JSON file."""
    metadata_path = path / "audit_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)


# Helper functions for scan command

def _resolve_provider_and_model(claude_model: Optional[str], openai_model: Optional[str]):
    """Resolve (provider, model) from flags, falling back to whichever API key is set.

    Priority: --claude/--openai flag > ANTHROPIC_API_KEY > OPENAI_API_KEY > error.
    """
    if claude_model is not None:
        model = claude_model if claude_model != "" else config_module.get_ai_model("claude")
        return "claude", model

    if openai_model is not None:
        model = openai_model if openai_model != "" else config_module.get_ai_model("openai")
        return "openai", model

    if config_module.get_anthropic_key():
        return "claude", config_module.get_ai_model("claude")

    if config_module.get_openai_key():
        return "openai", config_module.get_ai_model("openai")

    console.print(f"\n{emoji('crossmark')} [bold yellow]No API key found[/bold yellow]")
    console.print("\nClausi is BYOK (bring your own key) - set one of:")
    console.print("  [cyan]export ANTHROPIC_API_KEY=sk-ant-...[/cyan]   (https://console.anthropic.com)")
    console.print("  [cyan]export OPENAI_API_KEY=sk-...[/cyan]          (https://platform.openai.com/api-keys)")
    console.print("\nOr save one permanently:")
    console.print("  [cyan]clausi config set --anthropic-key sk-ant-...[/cyan]")
    console.print("  [cyan]clausi config set --openai-key sk-...[/cyan]")
    sys.exit(1)


def _validate_and_get_api_key(provider: str, model: Optional[str] = None) -> str:
    """Validate and return the API key for the given provider, or exit with guidance."""
    model_display = f" ({model})" if model else ""
    console.print(f"\n[cyan]Using {provider.title()}{model_display} with your API key[/cyan]")

    if provider == "claude":
        api_key = config_module.get_anthropic_key()
        if not api_key:
            console.print("\n[bold yellow]Anthropic API Key Required[/bold yellow]")
            console.print("\n1. Set it in environment:")
            console.print("   [cyan]export ANTHROPIC_API_KEY=sk-ant-...[/cyan]")
            console.print("\n2. Or add to config:")
            console.print("   [cyan]clausi config set --anthropic-key your-key-here[/cyan]")
            console.print("\nGet a key from: [link=https://console.anthropic.com]https://console.anthropic.com[/link]")
            sys.exit(1)
        return api_key

    api_key = config_module.get_openai_key()
    if not api_key:
        console.print("\n[bold yellow]OpenAI API Key Required[/bold yellow]")
        console.print("\n1. Set it in environment:")
        console.print("   [cyan]export OPENAI_API_KEY=sk-...[/cyan]")
        console.print("\n2. Or add to config:")
        console.print("   [cyan]clausi config set --openai-key your-key-here[/cyan]")
        console.print("\nGet a key from: [link=https://platform.openai.com/api-keys]https://platform.openai.com/api-keys[/link]")
        sys.exit(1)

    if not validate_openai_key(api_key):
        console.print("\n[bold yellow]Invalid OpenAI API Key[/bold yellow]")
        console.print("\n[cyan]clausi config set --openai-key your-key-here[/cyan]")
        sys.exit(1)
    return api_key


def launch_interactive_mode():
    """Launch interactive TUI interface."""
    try:
        from clausi.tui.interactive import ClausInteractiveTUI
        console.print("[cyan]Launching Clausi interactive mode...[/cyan]\n")
        app = ClausInteractiveTUI()
        app.run()
    except ImportError as e:
        console.print(f"[red]Error: Missing 'questionary' library[/red]")
        console.print(f"[dim]{str(e)}[/dim]")
        console.print("\nInstall with: pip install questionary")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting Clausi...[/yellow]")
        sys.exit(0)
    except Exception as e:
        error_msg = str(e)
        if "xterm-256color" in error_msg or "Windows console" in error_msg:
            console.print(f"[red]Terminal Compatibility Issue[/red]")
            console.print("\nThe interactive mode requires a proper terminal environment.")
            console.print("\n[yellow]Try one of these solutions:[/yellow]")
            console.print("  1. Run from Command Prompt (cmd.exe) instead of Git Bash/WSL")
            console.print("  2. Run from PowerShell")
            console.print("  3. Use direct commands instead: clausi scan --help")
            sys.exit(1)
        else:
            console.print(f"[red]Error launching interactive mode: {error_msg}[/red]")
            sys.exit(1)


def _get_scan_regulations(regulation: Optional[tuple]) -> List[str]:
    """Get list of regulations to scan against."""
    if regulation:
        return list(regulation)
    cfg = load_config()
    return cfg.get("regulations", {}).get("selected", regs_module.get_regulation_choices())


def _setup_clause_scoping(select_clauses: bool, include_clauses: Optional[tuple],
                         exclude_clauses: Optional[tuple], preset: Optional[str],
                         regulations: List[str]):
    """Handle clause scoping based on user options. Returns (clauses_include, clauses_exclude)."""
    clauses_include = None
    clauses_exclude = None

    if select_clauses:
        target_reg = regulations[0] if len(regulations) == 1 else None
        if not target_reg and len(regulations) > 1:
            console.print(f"\n[yellow]Multiple regulations selected. Choose one for clause scoping:[/yellow]")
            for i, reg in enumerate(regulations, 1):
                console.print(f"  {i}. {get_regulations().get(reg, {}).get('name', reg)}")
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

    if clauses_include or clauses_exclude:
        clause_selector.display_clause_scope_summary(clauses_include, clauses_exclude)

    return clauses_include, clauses_exclude


def _discover_and_filter_files(abs_path: str, ignore: Optional[tuple]) -> List[dict]:
    """Discover and filter files to analyze."""
    from clausi.utils.output import create_enhanced_progress_bar

    with create_enhanced_progress_bar("Scanning project files...") as progress:
        task = progress.add_task("Scanning project files...", total=None)
        files = scanner.scan_directory(abs_path)
        progress.update(task, completed=True)

    if not files:
        console.print("[yellow]No files found to analyze![/yellow]")
        sys.exit(1)

    console.print(f"Found {len(files)} files to analyze")

    ignore_list = list(ignore) if ignore else None
    files = scanner.filter_ignored_files(files, abs_path, ignore_list)

    if not files:
        console.print("[yellow]No files found to analyze after applying ignore patterns![/yellow]")
        sys.exit(1)

    console.print(f"Analyzing {len(files)} files after filtering")
    return files


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version=__version__, prog_name="Clausi")
def cli(ctx):
    """Clausi - free, local, BYOK AI compliance auditing CLI.

    Everything runs on your machine. Bring your own Anthropic or
    OpenAI API key - you pay that provider directly, nothing goes
    through a Clausi account.

    \b
    Getting Started:
      1. Set an API key:            export ANTHROPIC_API_KEY=sk-ant-...
      2. Just run:                  clausi
      3. Or scan directly:          clausi scan . -r EU-AIA

    \b
    Quick Examples:
      clausi                                    # Interactive mode
      clausi scan . -r EU-AIA -r GDPR          # Scan with your Anthropic/OpenAI key
      clausi scan . --claude                   # Force Claude
      clausi scan . --openai gpt-4o            # Force OpenAI
    """
    create_default_config()

    if ctx.invoked_subcommand is None:
        launch_interactive_mode()


@cli.group()
def config():
    """Manage Clausi CLI configuration."""
    pass


@config.command()
@click.option("--openai-key", help="Set your OpenAI API key")
@click.option("--anthropic-key", help="Set your Anthropic API key")
@click.option("--ai-provider", type=click.Choice(["claude", "openai"]), help="Set default AI provider")
@click.option("--ai-model", help="Set default AI model")
@click.option("--company-name", help="Set your company name for reports")
@click.option("--company-logo", type=click.Path(exists=True), help="Set your company logo for reports")
@click.option("--output-dir", type=click.Path(), help="Set default report output directory")
@click.option("--regulations", multiple=True, help="Set selected regulations (can be given multiple times)")
@click.option("--cache/--no-cache", "cache_enabled", default=None, help="Enable/disable the local scan cache")
def set(openai_key: Optional[str], anthropic_key: Optional[str], ai_provider: Optional[str], ai_model: Optional[str],
        company_name: Optional[str], company_logo: Optional[str], output_dir: Optional[str],
        regulations: Optional[List[str]], cache_enabled: Optional[bool]):
    """Set configuration values."""
    config = load_config()

    if openai_key:
        config.setdefault("api_keys", {})["openai"] = openai_key
    if anthropic_key:
        config.setdefault("api_keys", {})["anthropic"] = anthropic_key
    if ai_provider:
        config.setdefault("ai", {})["provider"] = ai_provider
        console.print(f"[cyan]Set AI provider to: {ai_provider}[/cyan]")
    if ai_model:
        config.setdefault("ai", {})["model"] = ai_model
        console.print(f"[cyan]Set AI model to: {ai_model}[/cyan]")
    if company_name:
        config.setdefault("report", {})["company_name"] = company_name
    if company_logo:
        config.setdefault("report", {})["company_logo"] = company_logo
    if output_dir:
        config.setdefault("report", {})["output_dir"] = output_dir
    if regulations:
        config.setdefault("regulations", {})["selected"] = list(regulations)
    if cache_enabled is not None:
        config.setdefault("cache", {})["enabled"] = cache_enabled

    if config_module.save_config(config):
        console.print("[green]Configuration updated successfully[/green]")


@config.command()
def show():
    """Show current configuration."""
    console.print(f"Configuration file path: [bold]{config_module.get_config_path()}[/bold]\n")
    config = config_module.load_config()
    if not config:
        return

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    ai_settings = config.get("ai", {})
    table.add_row("AI Provider", ai_settings.get("provider", "claude (default)"))
    table.add_row("AI Model", ai_settings.get("model", "claude-3-5-sonnet-20241022 (default)"))

    api_keys = config.get("api_keys", {})
    anthropic_key = api_keys.get("anthropic", "") or os.getenv("ANTHROPIC_API_KEY", "")
    masked_anthropic = "•" * 20 if anthropic_key else "Not set"
    table.add_row("Anthropic Key", masked_anthropic)

    openai_key = api_keys.get("openai", "") or os.getenv("OPENAI_API_KEY", "")
    masked_openai = "•" * 20 if openai_key else "Not set"
    table.add_row("OpenAI Key", masked_openai)

    report = config.get("report", {})
    table.add_row("Output Directory", report.get("output_dir", "clausi/reports"))
    table.add_row("Company Name", report.get("company_name", "Not set"))
    table.add_row("Company Logo", report.get("company_logo", "Not set"))

    regulations = config.get("regulations", {})
    selected_regs = regulations.get("selected", list(get_regulations().keys()))
    table.add_row("Selected Regulations", ", ".join(selected_regs))

    cache_cfg = config.get("cache", {})
    table.add_row("Local Cache", "Enabled" if cache_cfg.get("enabled", True) else "Disabled")
    table.add_row("Cache Directory", str(Path.home() / ".clausi" / "cache"))

    console.print(table)


@config.command()
def path():
    """Print the full path to the configuration file."""
    console.print(f"Configuration file path: [bold]{config_module.get_config_path()}[/bold]")


@config.command()
def edit():
    """Open the configuration file in your default editor (uses $EDITOR or Notepad)."""
    path = config_module.get_config_path()
    editor = os.getenv("EDITOR") or ("notepad" if os.name == "nt" else "vi")
    console.print(f"Opening config file: [bold]{path}[/bold] with [cyan]{editor}[/cyan]")
    try:
        os.system(f"{editor} {path}")
    except Exception as e:
        console.print(f"[red]{emoji('crossmark')}[/red] Could not open editor: {e}")


@cli.group()
def cache():
    """Manage the local scan result cache."""
    pass


@cache.command("clear")
def cache_clear():
    """Delete all cached scan results (forces a full re-scan next time)."""
    removed = LocalCache().clear()
    console.print(f"[green]{emoji('checkmark')}[/green] Removed {removed} cached result(s).")


@cache.command("stats")
def cache_stats_cmd():
    """Show local cache directory info."""
    cache_dir = Path.home() / ".clausi" / "cache"
    count = len(list(cache_dir.glob("scan_*.json"))) if cache_dir.exists() else 0
    console.print(f"Cache directory: [bold]{cache_dir}[/bold]")
    console.print(f"Cached results: [bold]{count}[/bold]")


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
    table.add_column("Recommended", style="white")

    table.add_row("Claude", "claude-3-5-sonnet-20241022", "200k", "$3 / $15", "Default")
    table.add_row("Claude", "claude-3-opus-20240229", "200k", "$15 / $75", "")
    table.add_row("Claude", "claude-3-sonnet-20240229", "200k", "$3 / $15", "")
    table.add_row("OpenAI", "gpt-4o", "128k", "$5 / $15", "Default")
    table.add_row("OpenAI", "gpt-4-turbo", "128k", "$10 / $30", "")
    table.add_row("OpenAI", "gpt-4", "128k", "$30 / $60", "")

    console.print(table)
    console.print("\n[yellow]Usage:[/yellow]")
    console.print("  [cyan]clausi scan . --claude[/cyan]                           # Default Claude model")
    console.print("  [cyan]clausi scan . --claude claude-3-5-sonnet-20241022[/cyan]  # Specify model")
    console.print("  [cyan]clausi scan . --openai gpt-4o[/cyan]                     # Use OpenAI")
    console.print("\n[yellow]Set API keys:[/yellow]")
    console.print("  [cyan]clausi config set --anthropic-key sk-ant-...[/cyan]")
    console.print("  [cyan]clausi config set --openai-key sk-...[/cyan]")


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--regulation", "--regulations", "-r", multiple=True, help="Regulation(s) to check against (built-in + custom). Can be given multiple times, e.g. -r EU-AIA -r GDPR")
@click.option("--output", "-o", type=click.Path(), help="Output directory for reports")
@click.option("--claude", "claude_model", default=None, is_flag=False, flag_value="", help="Use Claude with your API key (optionally specify model: --claude claude-3-5-sonnet-20241022)")
@click.option("--openai", "openai_model", default=None, is_flag=False, flag_value="", help="Use OpenAI with your API key (optionally specify model: --openai gpt-4o)")
@click.option("--select-clauses", is_flag=True, help="Interactively select clauses to scan")
@click.option("--include", "include_clauses", multiple=True, help="Include specific clauses (can be given multiple times, e.g. --include EUAIA-3.1)")
@click.option("--exclude", "exclude_clauses", multiple=True, help="Exclude specific clauses (can be given multiple times)")
@click.option("--preset", type=str, help="Use predefined clause preset (e.g., critical-only, high-priority)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--skip-confirmation", "-y", is_flag=True, help="Skip the confirmation prompt")
@click.option("--max-cost", type=float, help="Abort if the estimated cost exceeds this many dollars (e.g., --max-cost 1.00)")
@click.option("--show-details", is_flag=True, help="Show per-file token estimates")
@click.option("--min-severity", type=click.Choice(["info", "low", "medium", "high", "critical"]), default="info", help="Minimum severity to report")
@click.option("--ignore", multiple=True, help="Ignore files/directories (can be given multiple times)")
@click.option("--open-findings", is_flag=True, help="Auto-open findings.md in default editor after scan")
@click.option("--show-markdown", is_flag=True, help="Display markdown findings summary in terminal")
@click.option("--show-cache-stats/--no-cache-stats", default=None, help="Show/hide cache statistics (default: from config)")
@click.option("--no-cache", is_flag=True, help="Disable the local result cache for this run")
def scan(path: str, regulation: Optional[List[str]], output: Optional[str], claude_model: Optional[str],
          openai_model: Optional[str], select_clauses: bool, include_clauses: Optional[List[str]],
          exclude_clauses: Optional[List[str]], preset: Optional[str], verbose: bool,
          skip_confirmation: bool, max_cost: Optional[float], show_details: bool, min_severity: str, ignore: Optional[List[str]],
          open_findings: bool, show_markdown: bool, show_cache_stats: Optional[bool], no_cache: bool):
    """Run a compliance audit on your codebase - fully local, BYOK (main command)."""
    provider, model = _resolve_provider_and_model(claude_model, openai_model)
    api_key = _validate_and_get_api_key(provider, model)

    regulations = _get_scan_regulations(regulation)
    clauses_include, clauses_exclude = _setup_clause_scoping(
        select_clauses, include_clauses, exclude_clauses, preset, regulations
    )

    abs_path = os.path.abspath(path)

    if not output:
        cfg = load_config()
        output = cfg.get("report", {}).get("output_dir", "clausi/reports") if cfg else "clausi/reports"
    output_path = ensure_output_dir(abs_path, output)

    console.print(f"[bold]Starting compliance scan for {abs_path}[/bold]")
    reg_labels = []
    for r in regulations:
        reg_data = get_regulations().get(r, {})
        label = reg_data.get("name", r)
        version = reg_data.get("version")
        if version:
            label += f" (v{version})"
        reg_labels.append(label)
    console.print(f"Regulations: {', '.join(reg_labels)}")

    files = _discover_and_filter_files(abs_path, ignore)

    # Resolve each regulation's clauses locally (bundled YAML + project/custom)
    regulation_data = {}
    for reg_code in regulations:
        data = regs_module.get_regulation_clauses(reg_code, project_path=Path(abs_path))
        if not data:
            console.print(f"[red]Error: Unknown regulation '{reg_code}'[/red]")
            sys.exit(1)
        regulation_data[reg_code] = data

    # Rough local cost estimate (informational only - BYOK means the provider bills you directly)
    total_chars = sum(len(f["content"]) for f in files)
    est_input_tokens = estimate_tokens("x" * total_chars) * len(regulations)
    ai_provider = get_ai_provider(provider, api_key, model)
    est_cost = ai_provider.estimate_cost(est_input_tokens, est_input_tokens // 4)

    console.print("\n[bold]Rough Estimate (informational - billed directly by your provider):[/bold]")
    console.print(f"Files: {len(files)}  |  Regulations: {len(regulations)}  |  Est. cost: ${est_cost:.2f}")
    if show_details:
        for f in files:
            console.print(f"  {f['path']}: ~{estimate_tokens(f['content']):,} tokens")

    if max_cost is not None and est_cost > max_cost:
        console.print(f"\n[red]Error: Estimated cost (${est_cost:.2f}) exceeds maximum cost (${max_cost:.2f})[/red]")
        sys.exit(1)

    if not skip_confirmation:
        if not click.confirm(f"\nProceed with analysis? Estimated cost: ${est_cost:.2f}"):
            console.print("[yellow]Analysis cancelled by user[/yellow]")
            sys.exit(0)

    cfg = load_config()
    cache_cfg = cfg.get("cache", {}) if cfg else {}
    cache = LocalCache(
        enabled=(not no_cache) and cache_cfg.get("enabled", True),
        ttl=cache_cfg.get("ttl_days", 30) * 24 * 60 * 60,
    )

    all_findings: List[Dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    all_errors: List[str] = []

    for reg_code in regulations:
        reg_data = regulation_data[reg_code]
        console.print(f"\n{emoji('search')} Scanning against [bold]{reg_data['name']}[/bold]...")

        with console.status(f"Analyzing {len(files)} file(s)..."):
            result = compliance_analyzer.run_scan(
                files=files,
                regulation=reg_data["name"],
                clauses=reg_data["clauses"],
                provider=ai_provider,
                cache=cache,
                clauses_include=clauses_include,
                clauses_exclude=clauses_exclude,
                min_severity=min_severity,
            )

        for f in result["findings"]:
            f["regulation"] = reg_code
        all_findings.extend(result["findings"])
        total_prompt_tokens += result["token_usage"]["prompt_tokens"]
        total_completion_tokens += result["token_usage"]["completion_tokens"]
        total_cost += result["token_usage"]["cost"]
        all_errors.extend(result.get("errors", []))

        reg_output_dir = output_path / reg_code if len(regulations) > 1 else output_path
        audit_meta = {
            "timestamp": datetime.utcnow().isoformat(),
            "provider": provider,
            "model": model,
            "total_tokens": result["token_usage"]["total_tokens"],
            "cost": result["token_usage"]["cost"],
            "files_scanned": len(files),
        }
        MarkdownGenerator().save_all_reports(
            findings=result["findings"],
            project_name=Path(abs_path).name,
            regulation=reg_data["name"],
            audit_meta=audit_meta,
            all_clauses=reg_data["clauses"],
            output_dir=reg_output_dir,
            files_scanned=len(files),
        )
        console.print(f"[green]Reports saved to: {reg_output_dir}[/green]")

    if all_errors:
        console.print(f"\n[yellow]{emoji('warning')} {len(all_errors)} file(s) failed to analyze:[/yellow]")
        for err in all_errors[:10]:
            console.print(f"  [dim]{err}[/dim]")

    metadata = {
        "timestamp": datetime.utcnow().isoformat(),
        "path": path,
        "regulations": regulations,
        "files_analyzed": len(files),
        "ai_provider": provider,
        "ai_model": model,
        "clauses_include": clauses_include,
        "clauses_exclude": clauses_exclude,
        "findings": all_findings,
        "token_usage": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "cost": total_cost,
        }
    }
    save_audit_metadata(output_path, metadata)

    real_findings = [f for f in all_findings if f.get("clause_id") != "TOKEN-USAGE"]
    if real_findings:
        table = Table(title="Compliance Findings")
        table.add_column("Regulation", style="cyan")
        table.add_column("Clause", style="cyan")
        table.add_column("Severity", style="yellow")
        table.add_column("Location", style="blue")
        table.add_column("Description", style="white")

        for finding in real_findings:
            table.add_row(
                finding.get("regulation", ""),
                finding.get("clause_id", ""),
                finding.get("severity", ""),
                finding.get("location", ""),
                (finding.get("explanation", "") or "")[:80],
            )

        console.print(table)
    elif all_errors:
        # Never report "compliant" when files failed to analyze - an absence of
        # findings caused by errors is not evidence of compliance, and for a
        # compliance tool that mistake is worse than crashing.
        console.print(
            f"\n[red]{emoji('crossmark')} Scan incomplete: "
            f"{len(all_errors)} of {len(files)} file(s) could not be analyzed.[/red]"
        )
        console.print(
            "[yellow]No findings were produced for those files. This is NOT a "
            "clean result - re-run after resolving the errors above.[/yellow]"
        )
    else:
        console.print(f"\n[green]{emoji('checkmark')} No findings - looks compliant![/green]")

    console.print(f"\n[bold]Actual Cost:[/bold] ${total_cost:.4f}")

    display_cache = show_cache_stats if show_cache_stats is not None else (cfg.get("ui", {}).get("show_cache_stats", True) if cfg else True)
    if display_cache:
        from clausi.utils.output import display_cache_statistics
        stats = cache.stats()
        stats["cost_saved"] = 0.0  # exact $ saved is provider/model-dependent; hit-rate is the useful signal
        display_cache_statistics(stats)

    if all_errors and len(all_errors) >= len(files):
        # Every file failed: nothing was actually analyzed. Exit non-zero so CI
        # and scripts don't read a broken scan as a passing one.
        console.print(
            f"\n[red]Scan failed: no files could be analyzed. "
            f"Reports in {output_path} are empty and must not be treated as evidence.[/red]"
        )
        raise SystemExit(2)

    console.print(f"\n[green]Scan completed! Reports saved to {output_path}[/green]")

    from clausi.utils.output import display_findings_summary, open_in_editor

    findings_md = (output_path if len(regulations) == 1 else output_path / regulations[0]) / "findings.md"
    cfg = load_config()
    auto_show = show_markdown or (cfg.get("ui", {}).get("show_markdown", False) if cfg else False)
    if auto_show and findings_md.exists():
        display_findings_summary(findings_md)

    auto_open = open_findings or (cfg.get("ui", {}).get("auto_open_findings", True) if cfg else True)
    if auto_open and findings_md.exists():
        open_in_editor(findings_md)


@cli.command()
def setup():
    """Configure API keys and settings (first-time setup)."""
    console.print(Panel.fit(
        "Welcome to Clausi CLI Setup!\n\n"
        "Clausi is BYOK (bring your own key) - this wizard saves your Anthropic/OpenAI key locally.",
        title="Setup Wizard"
    ))

    provider = click.prompt("Which provider will you use?", type=click.Choice(["claude", "openai"]), default="claude")

    if provider == "claude":
        api_key = click.prompt("Enter your Anthropic API key", type=str)
    else:
        api_key = click.prompt("Enter your OpenAI API key", type=str)
        if not validate_openai_key(api_key):
            console.print("[red]Error: Invalid OpenAI API key[/red]")
            sys.exit(1)

    company_name = click.prompt("Enter your company name (optional)", type=str, default="")
    regulation = click.prompt(
        "Choose default regulation",
        type=click.Choice(list(get_regulations().keys())),
        default="EU-AIA"
    )

    config = load_config() or {}
    config.setdefault("api_keys", {})[provider if provider == "openai" else "anthropic"] = api_key
    config.setdefault("ai", {})["provider"] = provider
    config.setdefault("report", {})["company_name"] = company_name
    config.setdefault("regulations", {})["selected"] = [regulation]

    if config_module.save_config(config):
        console.print(f"[green]{emoji('checkmark')}[/green] Setup completed successfully!")
        console.print("\nYou can now use 'clausi scan' to start scanning your projects.")


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
    """Launch interactive scan wizard."""
    launch_interactive_mode()


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


# =============================================================================
# DOCS COMMAND GROUP
# =============================================================================

@cli.group()
def docs():
    """Generate AI-powered documentation for your project."""
    pass


@docs.command("generate")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory (default: {path}/clausi/docs/latest)")
@click.option("--exclude", multiple=True, help="Glob patterns to exclude (can be repeated)")
@click.option("--include", multiple=True, help="Glob patterns to include (can be repeated)")
@click.option("--claude", "claude_model", default=None, is_flag=False, flag_value="", help="Use Claude with your API key (optionally specify model)")
@click.option("--openai", "openai_model", default=None, is_flag=False, flag_value="", help="Use OpenAI with your API key (optionally specify model)")
@click.option("--skip-confirmation", "-y", is_flag=True, help="Skip cost confirmation prompt")
def docs_generate(path, output, exclude, include, claude_model, openai_model, skip_confirmation):
    """Generate AI-powered documentation for a project - fully local, BYOK.

    \b
    Examples:
        clausi docs generate                    # Auto-detects provider from env key
        clausi docs generate --claude            # Force Claude
        clausi docs generate --openai gpt-4o     # Force OpenAI
        clausi docs generate --exclude "tests/*"
    """
    from clausi.core.docs_generator import DocsGenerator

    provider, model = _resolve_provider_and_model(claude_model, openai_model)
    api_key = _validate_and_get_api_key(provider, model)

    project_path = Path(path).resolve()
    console.print(f"\n{emoji('folder')} Project: [bold]{project_path}[/bold]")

    output_dir = Path(output).resolve() if output else project_path / "clausi" / "docs" / "latest"

    generator = DocsGenerator(
        project_path=project_path,
        output_dir=output_dir,
        exclude_patterns=list(exclude),
        include_patterns=list(include),
        provider=provider,
        api_key=api_key,
        model=model,
    )

    console.print(f"\n{emoji('search')} Scanning project...")
    file_count, loc_count = generator.scan_project()
    console.print(f"   Files found: {file_count}")
    console.print(f"   Lines of code: {loc_count:,}")

    if file_count == 0:
        console.print(f"\n{emoji('warning')} No files found to document.")
        sys.exit(1)

    ai_provider = get_ai_provider(provider, api_key, model)
    est_tokens = generator.estimate_tokens()
    est_cost = ai_provider.estimate_cost(est_tokens, est_tokens // 3)
    console.print(f"\n{emoji('info')} Rough estimate (billed directly by your provider): ~${est_cost:.2f}")

    if not skip_confirmation:
        if not click.confirm("\nProceed with documentation generation?"):
            console.print("[yellow]Cancelled[/yellow]")
            sys.exit(0)

    console.print(f"\n{emoji('search')} Generating documentation...\n")

    def _progress(i, total, filename):
        console.print(f"  [{i}/{total}] {filename}...")

    try:
        docs_result = generator.generate(ai_provider, on_progress=_progress)
    except Exception as e:
        console.print(f"\n{emoji('crossmark')} [red]Documentation generation failed: {e}[/red]")
        sys.exit(1)

    generator.save_docs(docs_result)

    console.print(f"\n{emoji('checkmark')} [green]Documentation generated successfully![/green]")
    console.print(f"\n   Output: [bold]{output_dir}[/bold]")
    console.print(f"   Files:")
    for filename in docs_result:
        console.print(f"     - {filename}")


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
