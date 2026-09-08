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
import shlex
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import click
import yaml
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
from clausi.core.pdf_report import PDFReportGenerator
from clausi.core.finding_lifecycle import (
    commit_lifecycle,
    prepare_findings,
    regulation_pack_hash,
)
from clausi.core.remediation_register import save_remediation_register
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
                "model": "claude-opus-5",
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
                "auto_open_findings": False,
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
        import openai
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

def _resolve_provider_and_model(claude_model: Optional[str], openai_model: Optional[str],
                                 claude_code: bool = False, codex: bool = False):
    """Resolve (provider, model) from flags, falling back to a key or local agent CLI.

    Priority: explicit flag > ANTHROPIC_API_KEY > OPENAI_API_KEY >
    a signed-in local agent CLI (Claude Code / Codex) > error.
    """
    if claude_code:
        return "claude-code", claude_model or ""

    if codex:
        return "codex", openai_model or ""

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

    # No API key: fall back to an agent CLI the user already has signed in.
    # This needs no key at all - it rides their existing subscription.
    from clausi.core.ai_provider import LOCAL_AGENT_PROVIDERS
    for local_name, local_cls in LOCAL_AGENT_PROVIDERS.items():
        if local_cls.is_available():
            console.print(
                f"[dim]No API key set - using your local {local_cls.friendly_name} "
                f"installation.[/dim]"
            )
            return local_name, ""

    console.print(f"\n{emoji('crossmark')} [bold yellow]No AI backend found[/bold yellow]")
    console.print("\nClausi runs locally and needs one of these. Either:")
    console.print("\n[bold]Use a coding agent you already have[/bold] (no API key needed):")
    console.print("  [cyan]claude[/cyan]  Claude Code   https://claude.com/claude-code")
    console.print("  [cyan]codex[/cyan]   Codex CLI     https://developers.openai.com/codex")
    console.print("  Install and sign in to either, then re-run clausi.")
    console.print("\n[bold]Or bring your own API key:[/bold]")
    console.print("  [cyan]export ANTHROPIC_API_KEY=sk-ant-...[/cyan]   (https://console.anthropic.com)")
    console.print("  [cyan]export OPENAI_API_KEY=sk-...[/cyan]          (https://platform.openai.com/api-keys)")
    console.print("\nOr save one permanently:")
    console.print("  [cyan]clausi config set --anthropic-key sk-ant-...[/cyan]")
    console.print("  [cyan]clausi config set --openai-key sk-...[/cyan]")
    sys.exit(1)


def _validate_and_get_api_key(provider: str, model: Optional[str] = None) -> str:
    """Validate and return the API key for the given provider, or exit with guidance."""
    model_display = f" ({model})" if model else ""

    from clausi.core.ai_provider import LOCAL_AGENT_PROVIDERS
    local_cls = LOCAL_AGENT_PROVIDERS.get(provider)
    if local_cls:
        # Agent CLIs carry their own credentials - there is no key to validate.
        if not local_cls.is_available():
            console.print(f"\n[bold yellow]{local_cls.friendly_name} not found[/bold yellow]")
            console.print(f"\n{local_cls.install_hint}")
            sys.exit(1)
        console.print(
            f"\n[cyan]Using your local {local_cls.friendly_name}{model_display} "
            f"- no API key needed[/cyan]"
        )
        return ""

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
        else:
            # A preset narrows the clause list, and a violation of an excluded
            # clause is then reported against whichever included clause fits
            # best - or not at all. Measured on a real repository, 66% of the
            # findings from a full scan landed on clauses a preset could not
            # express. That is fine for a fast triage pass and wrong as the
            # basis for a compliance claim, so say so every time.
            console.print(
                f"[yellow]Note: --preset {preset} scans "
                f"{len(clauses_include)} of the regulation's clauses. Clauses "
                "outside the preset are not assessed - this is a triage pass, "
                "not a full audit, and the report will say so.[/yellow]"
            )

    if clauses_include or clauses_exclude:
        clause_selector.display_clause_scope_summary(clauses_include, clauses_exclude)

    return clauses_include, clauses_exclude


def _reproduction_command() -> str:
    """The command a reader can actually re-run.

    sys.argv[0] is the absolute path to __main__.py when the CLI is invoked as
    `python -m clausi`, which printed a machine-specific path into the report's
    reproduction field - not a command anyone else could run.
    """
    args = sys.argv[1:]
    return shlex.join(["clausi", *args])


def _discover_and_filter_files(abs_path: str, ignore: Optional[tuple],
                                exclude_paths: Optional[List[Path]] = None) -> Tuple[List[dict], Dict[str, Any]]:
    """Discover and filter files to analyze."""
    from clausi.utils.output import create_enhanced_progress_bar

    # Resolved before the walk so ignored files are never read - see
    # scanner.build_ignore_matcher.
    ignore_list = list(ignore) if ignore else None
    ignore_matcher = scanner.build_ignore_matcher(abs_path, ignore_list)

    with create_enhanced_progress_bar("Scanning project files...") as progress:
        task = progress.add_task("Scanning project files...", total=None)
        discovered_files, coverage = scanner.scan_directory_with_coverage(
            abs_path, exclude_paths=exclude_paths, ignore_matcher=ignore_matcher
        )
        progress.update(task, completed=True)

    if not discovered_files:
        console.print("[yellow]No files found to analyze![/yellow]")
        sys.exit(1)

    console.print(f"Found {len(discovered_files)} files to analyze")

    files = discovered_files
    ignored_manifest = coverage.get("ignored", [])
    if ignored_manifest:
        console.print(f"[green]Ignored {len(ignored_manifest)} file(s) by ignore rules[/green]")

    if not files:
        console.print("[yellow]No files found to analyze after applying ignore patterns![/yellow]")
        sys.exit(1)

    console.print(f"Analyzing {len(files)} files after filtering")
    file_types: Dict[str, int] = {}
    for file_data in files:
        extension = str(file_data.get("type") or "unknown").lower()
        file_types[extension] = file_types.get(extension, 0) + 1
    ignore_file = scanner.find_clausiignore_file(abs_path)
    scope_meta = {
        "files_discovered": len(discovered_files),
        "files_analyzed": len(files),
        "files_ignored": len(discovered_files) - len(files),
        "file_types": dict(sorted(file_types.items())),
        "total_bytes": sum(int(file_data.get("size") or 0) for file_data in files),
        "ignore_patterns": list(ignore or ()),
        "clausiignore": str(ignore_file) if ignore_file else "Not present",
        "coverage": coverage,
        "ignored_files": ignored_manifest,
    }
    _print_coverage_summary(coverage, ignored_manifest)
    return files, scope_meta


def _save_scan_manifest(output_dir: Path, audit_meta: Dict[str, Any],
                        result: Dict[str, Any]) -> None:
    """Write scan_manifest.json: exactly what was and was not examined.

    A compliance report is only as meaningful as its coverage. This records the
    files that were skipped, ignored, unreadable, truncated, or failed, so a
    reader can never mistake "not looked at" for "looked at and clean".
    """
    coverage = audit_meta.get("coverage") or {}
    manifest = {
        "generated": audit_meta.get("timestamp"),
        "scan_command": audit_meta.get("scan_command"),
        "analyzed": {
            "file_count": audit_meta.get("files_analyzed"),
            "file_types": audit_meta.get("file_types"),
            "total_bytes": audit_meta.get("total_bytes"),
            "max_chars_per_file": audit_meta.get("max_file_chars", compliance_analyzer.MAX_FILE_CHARS),
        },
        "not_analyzed": {
            "unsupported_extension": coverage.get("skipped_unsupported_extension", {}),
            "unsupported_examples": coverage.get("skipped_unsupported_examples", {}),
            "excluded_directories": coverage.get("skipped_excluded_directories", {}),
            "ignored_by_rule": audit_meta.get("ignored_files", []),
            "unreadable": coverage.get("unreadable", []),
            "failed_during_analysis": result.get("errors", []),
        },
        "partially_analyzed": {
            "truncated": result.get("truncated", []),
            # Clauses the model explicitly declined to judge for a file. An
            # abstention is not a pass: it means nothing was concluded.
            "clauses_not_assessed": result.get("not_assessed", []),
        },
        "supported_extensions": coverage.get("supported_extensions", []),
        "caveat": (
            "Findings cover only the files listed under 'analyzed', and only the "
            "first max_chars_per_file characters of each. Absence of a finding for "
            "anything listed under 'not_analyzed', under "
            "'partially_analyzed.clauses_not_assessed', or beyond that limit means "
            "it was not examined, not that it is compliant."
        ),
    }
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "scan_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except OSError as e:
        console.print(f"[yellow]Warning: could not write scan manifest: {e}[/yellow]")


def _print_coverage_summary(coverage: Dict[str, Any], ignored: List[Dict[str, str]]) -> None:
    """Tell the user up front what will NOT be looked at.

    Without this, a clean report is indistinguishable from an unexamined one.
    """
    unsupported = coverage.get("skipped_unsupported_extension") or {}
    skipped_total = sum(unsupported.values())
    if skipped_total:
        top = ", ".join(f"{ext} ({n})" for ext, n in list(unsupported.items())[:5])
        console.print(
            f"[yellow]Not analyzed: {skipped_total} file(s) of unsupported types - {top}[/yellow]"
        )
    excluded_dirs = coverage.get("skipped_excluded_directories") or {}
    if excluded_dirs:
        # Named explicitly: a few of these (build, dist, target) can legitimately
        # hold real source, and the user needs to notice if theirs was skipped.
        names = ", ".join(sorted(excluded_dirs))
        console.print(f"[dim]Skipped directories: {names}[/dim]")
    if ignored:
        console.print(f"[dim]Excluded by ignore rules: {len(ignored)} file(s)[/dim]")
    unreadable = coverage.get("unreadable") or []
    if unreadable:
        console.print(f"[yellow]Unreadable: {len(unreadable)} file(s)[/yellow]")


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version=__version__, prog_name="Clausi")
def cli(ctx):
    """Clausi - free, local, BYOK AI compliance auditing CLI.

    Everything runs on your machine. Use a coding agent you already have
    signed in (Claude Code / Codex), or bring your own Anthropic or OpenAI
    API key - you pay that provider directly, nothing goes through a
    Clausi account.

    \b
    Getting Started:
      1. Have Claude Code or Codex? Nothing to set up - skip to step 2.
         Otherwise:                 export ANTHROPIC_API_KEY=sk-ant-...
      2. Just run:                  clausi
      3. Or scan directly:          clausi scan . -r EU-AIA

    \b
    Quick Examples:
      clausi                                    # Interactive mode
      clausi scan . -r EU-AIA --claude-code    # Use local Claude Code, no API key
      clausi scan . -r EU-AIA --codex          # Use local Codex CLI, no API key
      clausi scan . -r EU-AIA -r GDPR          # Auto-detect key or local agent
      clausi scan . --claude                   # Force Claude via API key
      clausi scan . --openai gpt-4o            # Force OpenAI via API key
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
    table.add_row("AI Model", ai_settings.get("model", "claude-opus-5 (default)"))

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


@cache.command("prune")
@click.option("--max-size-mb", type=float, default=None,
              help="Size ceiling in MB (default: from config, else 500)")
def cache_prune(max_size_mb: Optional[float]):
    """Drop expired entries, then the oldest ones until under the size cap."""
    cfg = load_config() or {}
    cache_cfg = cfg.get("cache", {})
    limit_mb = max_size_mb if max_size_mb is not None else cache_cfg.get("max_size_mb", 500)
    local = LocalCache(ttl=cache_cfg.get("ttl_days", 30) * 24 * 60 * 60)
    result = local.prune(max_bytes=int(limit_mb * 1024 * 1024))
    console.print(
        f"[green]{emoji('checkmark')}[/green] Removed {result['expired']} expired and "
        f"{result['evicted']} over-cap entr(ies), freeing "
        f"{result['bytes_freed'] / (1024 * 1024):.1f} MB."
    )


@cache.command("stats")
def cache_stats_cmd():
    """Show local cache directory info."""
    cache_dir = Path.home() / ".clausi" / "cache"
    count = len(list(cache_dir.glob("scan_*.json"))) if cache_dir.exists() else 0
    size_mb = LocalCache().size_bytes() / (1024 * 1024) if cache_dir.exists() else 0.0
    cfg = load_config() or {}
    limit_mb = cfg.get("cache", {}).get("max_size_mb", 500)
    console.print(f"Cache directory: [bold]{cache_dir}[/bold]")
    console.print(f"Cached results: [bold]{count}[/bold]")
    console.print(f"Size on disk: [bold]{size_mb:.1f} MB[/bold] (cap {limit_mb:.0f} MB)")


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

    table.add_row("Claude", "claude-opus-5", "1M", "$5 / $25", "Default")
    table.add_row("Claude", "claude-sonnet-5", "1M", "$3 / $15", "Cheaper")
    table.add_row("Claude", "claude-haiku-4-5", "200k", "$1 / $5", "Fastest")
    table.add_row("OpenAI", "gpt-4o", "128k", "$5 / $15", "Default")
    table.add_row("OpenAI", "gpt-4-turbo", "128k", "$10 / $30", "")
    table.add_row("OpenAI", "gpt-4", "128k", "$30 / $60", "")

    console.print(table)
    console.print("\n[yellow]Usage:[/yellow]")
    console.print("  [cyan]clausi scan . --claude[/cyan]                           # Default Claude model")
    console.print("  [cyan]clausi scan . --claude claude-sonnet-5[/cyan]            # Specify model")
    console.print("  [cyan]clausi scan . --openai gpt-4o[/cyan]                     # Use OpenAI")
    console.print("\n[yellow]Set API keys:[/yellow]")
    console.print("  [cyan]clausi config set --anthropic-key sk-ant-...[/cyan]")
    console.print("  [cyan]clausi config set --openai-key sk-...[/cyan]")


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--regulation", "--regulations", "-r", multiple=True, help="Regulation(s) to check against (built-in + custom). Can be given multiple times, e.g. -r EU-AIA -r GDPR")
@click.option("--output", "-o", type=click.Path(), help="Output directory for reports")
@click.option("--claude", "claude_model", default=None, is_flag=False, flag_value="", help="Use Claude with your API key (optionally specify model: --claude claude-sonnet-5)")
@click.option("--openai", "openai_model", default=None, is_flag=False, flag_value="", help="Use OpenAI with your API key (optionally specify model: --openai gpt-4o)")
@click.option("--claude-code", is_flag=True, help="Use your local Claude Code CLI - no API key needed")
@click.option("--codex", is_flag=True, help="Use your local Codex CLI - no API key needed")
@click.option("--select-clauses", is_flag=True, help="Interactively select clauses to scan")
@click.option("--include", "include_clauses", multiple=True, help="Include specific clauses (can be given multiple times, e.g. --include EUAIA-3.1)")
@click.option("--exclude", "exclude_clauses", multiple=True, help="Exclude specific clauses (can be given multiple times)")
@click.option("--preset", type=str, help="Use predefined clause preset (e.g., critical-only, high-priority)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--skip-confirmation", "-y", is_flag=True, help="Skip the confirmation prompt")
@click.option("--max-cost", type=float, help="Abort if the estimated cost exceeds this many dollars (e.g., --max-cost 1.00)")
@click.option("--show-details", is_flag=True, help="Show per-file token estimates")
@click.option("--passes", type=click.IntRange(1, 5), default=1,
              help="Analyze each file N times and report how often each finding "
                   "recurs. Costs N times as much; 1 pass is a sample, not a measurement.")
@click.option("--min-severity", type=click.Choice(["info", "low", "medium", "high", "critical"]), default="info", help="Minimum severity to report")
@click.option("--ignore", multiple=True, help="Ignore files/directories (can be given multiple times)")
@click.option("--open-findings/--no-open-findings", default=None,
              help="Open findings.md in your editor after the scan (default: off)")
@click.option("--show-markdown", is_flag=True, help="Display markdown findings summary in terminal")
@click.option("--show-cache-stats/--no-cache-stats", default=None, help="Show/hide cache statistics (default: from config)")
@click.option("--no-cache", is_flag=True, help="Disable the local result cache for this run")
def scan(path: str, regulation: Optional[List[str]], output: Optional[str], claude_model: Optional[str],
          openai_model: Optional[str], claude_code: bool, codex: bool,
          select_clauses: bool, include_clauses: Optional[List[str]],
          exclude_clauses: Optional[List[str]], preset: Optional[str], verbose: bool,
          skip_confirmation: bool, max_cost: Optional[float], show_details: bool, passes: int, min_severity: str, ignore: Optional[List[str]],
          open_findings: bool, show_markdown: bool, show_cache_stats: Optional[bool], no_cache: bool):
    """Run a compliance audit on your codebase - fully local (main command)."""
    provider, model = _resolve_provider_and_model(claude_model, openai_model, claude_code, codex)
    api_key = _validate_and_get_api_key(provider, model)

    regulations = _get_scan_regulations(regulation)
    clauses_include, clauses_exclude = _setup_clause_scoping(
        select_clauses, include_clauses, exclude_clauses, preset, regulations
    )

    abs_path = os.path.abspath(path)

    if output:
        # An explicit -o is relative to where the user is standing, like any
        # other CLI path argument - not to the project being scanned.
        output_path = Path(output).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        # The default lives with the project, so scanning a repo from elsewhere
        # still leaves its reports alongside the code they describe.
        cfg = load_config()
        default_dir = (cfg.get("report", {}).get("output_dir") if cfg else None) or "clausi/reports"
        output_path = ensure_output_dir(abs_path, default_dir)

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

    files, scope_meta = _discover_and_filter_files(
        abs_path, ignore,
        # Never scan our own output or state - see scanner.scan_directory_with_coverage.
        exclude_paths=[output_path, Path(abs_path) / ".clausi"],
    )

    # Resolve each regulation's clauses locally (bundled YAML + project/custom)
    regulation_data = {}
    for reg_code in regulations:
        data = regs_module.get_regulation_clauses(reg_code, project_path=Path(abs_path))
        if not data:
            console.print(f"[red]Error: Unknown regulation '{reg_code}'[/red]")
            sys.exit(1)
        regulation_data[reg_code] = data

    # Resolved before the estimate: the quote must be based on the same
    # truncation limit the scan will apply.
    _cfg = load_config()
    max_file_chars = int(
        (_cfg.get("scan", {}) if _cfg else {}).get(
            "max_file_chars", compliance_analyzer.MAX_FILE_CHARS
        )
    )

    # Local cost estimate (informational - BYOK means the provider bills you
    # directly). Counts what is actually sent: the prompt scaffold repeated for
    # every file, plus each file's text after truncation.
    ai_provider = get_ai_provider(provider, api_key, model)
    estimates = {}
    for reg_code in regulations:
        reg_data = regulation_data[reg_code]
        estimates[reg_code] = compliance_analyzer.estimate_scan(
            files,
            reg_data["name"],
            compliance_analyzer.select_clauses(
                reg_data["clauses"], clauses_include, clauses_exclude
            ),
            ai_provider,
            max_file_chars,
            passes,
        )
    est_cost = sum(e["cost"] for e in estimates.values())

    console.print("\n[bold]Estimate (informational - billed directly by your provider):[/bold]")
    console.print(f"Files: {len(files)}  |  Regulations: {len(regulations)}  |  Est. cost: ${est_cost:.2f}")
    if any(e.get("prompt_caching") for e in estimates.values()):
        console.print(
            "[dim]Assumes no local cache hits. The clause text is sent once and "
            "cached by the provider, so only the first file pays full price for "
            "it.[/dim]"
        )
    else:
        console.print(
            "[dim]Assumes no cache hits. Each file's request also carries the full "
            "clause text, which is most of the cost on small files.[/dim]"
        )
    if passes > 1:
        console.print(
            f"[dim]{passes} passes per file: each finding will carry how many "
            "passes detected it.[/dim]"
        )
    if show_details:
        for reg_code, est in estimates.items():
            console.print(
                f"  [bold]{reg_code}[/bold] - prompt overhead "
                f"~{est['prompt_overhead_tokens']:,} tokens per file"
            )
            for f in est["per_file"]:
                console.print(
                    f"    {f['path']}: ~{f['input_tokens']:,} in / "
                    f"~{f['output_tokens']:,} out  (${f['cost']:.4f})"
                )

    if max_cost is not None and est_cost > max_cost:
        console.print(f"\n[red]Error: Estimated cost (${est_cost:.2f}) exceeds maximum cost (${max_cost:.2f})[/red]")
        sys.exit(1)

    # The estimate is a guess; the ceiling has to hold against real usage too.
    budget = compliance_analyzer.CostBudget(max_cost)

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
    total_cache_read = 0
    total_cache_write = 0
    total_cost = 0.0
    all_errors: List[str] = []
    regulation_failures: List[str] = []

    for reg_code in regulations:
        reg_data = regulation_data[reg_code]
        console.print(f"\n{emoji('search')} Scanning against [bold]{reg_data['name']}[/bold]...")

        try:
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
                    budget=budget,
                    max_file_chars=max_file_chars,
                    passes=passes,
                )
        except Exception as e:  # noqa: BLE001
            # One regulation failing must not discard the regulations that
            # already scanned successfully - their reports are written inside
            # this loop and the API spend is not refundable.
            console.print(f"[red]{emoji('cross')} {reg_code} scan failed: {e}[/red]")
            regulation_failures.append(f"{reg_code}: {e}")
            continue

        for f in result["findings"]:
            f["regulation"] = reg_code
        total_prompt_tokens += result["token_usage"]["prompt_tokens"]
        total_completion_tokens += result["token_usage"]["completion_tokens"]
        total_cache_read += result["token_usage"].get("cache_read_tokens", 0)
        total_cache_write += result["token_usage"].get("cache_write_tokens", 0)
        total_cost += result["token_usage"]["cost"]
        all_errors.extend(result.get("errors", []))

        try:
            reg_output_dir = output_path / reg_code if len(regulations) > 1 else output_path
            lifecycle = prepare_findings(
                findings=result["findings"],
                regulation=reg_code,
                project_path=Path(abs_path),
                output_dir=reg_output_dir,
            )
            all_findings.extend(result["findings"])
            audit_meta = {
                "timestamp": datetime.utcnow().isoformat(),
                "provider": provider,
                # An agent CLI picks its own model and does not tell us which.
                # Recorded explicitly, because a blank field rendered as "Not
                # recorded" and read like a bug rather than a property of
                # running through someone else's CLI.
                "model": model or f"{provider} CLI default",
                "total_tokens": result["token_usage"]["total_tokens"],
                "cost": result["token_usage"]["cost"],
                "files_scanned": len(files),
                **scope_meta,
                "clauses_include": clauses_include,
                "clauses_exclude": clauses_exclude,
                "scan_command": _reproduction_command(),
                "change_summary": lifecycle["change_summary"],
                "resolved_ids": lifecycle["resolved_ids"],
                "resolved_findings": lifecycle["resolved_findings"],
                "comparison_baseline": lifecycle["is_baseline"],
                "regulation_pack_sha256": regulation_pack_hash(reg_data),
                "max_file_chars": max_file_chars,
                "passes": passes,
                "not_assessed": result.get("not_assessed", []),
                "truncated_files": result.get("truncated", []),
                # Files that errored mid-scan are part of coverage, not just
                # console noise: a report that omits them understates what was
                # never examined.
                "failed_files": result.get("errors", []),
            }
            _save_scan_manifest(reg_output_dir, audit_meta, result)
            MarkdownGenerator().save_all_reports(
                findings=result["findings"],
                project_name=Path(abs_path).name,
                regulation=reg_data["name"],
                audit_meta=audit_meta,
                all_clauses=reg_data["clauses"],
                output_dir=reg_output_dir,
                files_scanned=len(files),
            )
            PDFReportGenerator().save_report(
                findings=result["findings"],
                project_name=Path(abs_path).name,
                regulation=reg_data["name"],
                audit_meta=audit_meta,
                output_dir=reg_output_dir,
                files_scanned=len(files),
                all_clauses=reg_data["clauses"],
                project_path=Path(abs_path),
                regulation_metadata=reg_data,
            )
            save_remediation_register(result["findings"], reg_output_dir)
            commit_lifecycle(lifecycle)
            console.print(f"[green]Reports saved to: {reg_output_dir}[/green]")
        except Exception as e:  # noqa: BLE001
            # The scan succeeded and was paid for. If a report generator fails,
            # say so loudly and keep the findings that were already collected
            # rather than exiting on a traceback with nothing to show.
            console.print(
                f"[red]{emoji('cross')} {reg_code}: scan completed but report "
                f"generation failed: {type(e).__name__}: {e}[/red]"
            )
            regulation_failures.append(f"{reg_code}: report generation - {e}")

    if regulation_failures:
        console.print(f"\n[red]{emoji('cross')} {len(regulation_failures)} regulation(s) did not "
                      "produce complete reports:[/red]")
        for failure in regulation_failures:
            console.print(f"  [dim]{failure}[/dim]")

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
        "scope": scope_meta,
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
    elif regulation_failures:
        # Same reasoning as the branch above: a regulation that never completed
        # produced no findings because it did not run, not because the code is
        # clean.
        console.print(
            f"\n[red]{emoji('crossmark')} Scan incomplete: "
            f"{len(regulation_failures)} regulation(s) failed. This is NOT a clean result.[/red]"
        )
    else:
        console.print(f"\n[green]{emoji('checkmark')} No findings - looks compliant![/green]")

    console.print(f"\n[bold]Actual Cost:[/bold] ${total_cost:.4f}")

    if total_cache_read:
        # What the scaffold would have cost at full rate, minus what the cached
        # reads actually cost. Stated because an invisible optimization is one
        # nobody can check.
        saved = ai_provider.estimate_cost(total_cache_read, 0) - \
            ai_provider.estimate_cost(0, 0, total_cache_read, 0)
        console.print(
            f"[dim]Prompt caching: {total_cache_read:,} tokens served from cache "
            f"(saved ~${saved:.4f}); {total_cache_write:,} written.[/dim]"
        )

    if budget.stopped:
        # The user asked for a hard ceiling and got one. Say so explicitly -
        # a partial scan that looks complete is the dangerous outcome.
        console.print(
            f"\n[yellow]{emoji('warning')} Stopped early to stay under "
            f"--max-cost ${max_cost:.2f} (spent ${budget.spent:.4f}). Some files "
            f"were not analyzed - see the skipped files above. This is NOT a "
            f"complete scan.[/yellow]"
        )

    # Keep the cache bounded without the user having to think about it. Runs
    # after the reports are written, so a failure here can never cost a scan.
    try:
        cache.prune(max_bytes=int(cache_cfg.get("max_size_mb", 500) * 1024 * 1024))
    except Exception:  # noqa: BLE001 - housekeeping must never fail a scan
        pass

    display_cache = show_cache_stats if show_cache_stats is not None else (cfg.get("ui", {}).get("show_cache_stats", True) if cfg else True)
    if display_cache:
        from clausi.utils.output import display_cache_statistics
        stats = cache.stats()
        stats["cost_saved"] = 0.0  # exact $ saved is provider/model-dependent; hit-rate is the useful signal
        display_cache_statistics(stats)

    if regulation_failures and len(regulation_failures) >= len(regulations):
        # No regulation produced a complete report. Same contract as the
        # all-files-failed case below: never exit 0 on a scan that did not run.
        console.print(
            f"\n[red]Scan failed: no regulation completed. Reports in {output_path} "
            "are incomplete and must not be treated as evidence.[/red]"
        )
        raise SystemExit(2)

    if all_errors and len(all_errors) >= len(files):
        # Every file failed: nothing was actually analyzed. Exit non-zero so CI
        # and scripts don't read a broken scan as a passing one.
        console.print(
            f"\n[red]Scan failed: no files could be analyzed. "
            f"Reports in {output_path} are empty and must not be treated as evidence.[/red]"
        )
        raise SystemExit(2)

    if budget.stopped:
        # Exit non-zero: the reports are real but partial, and CI must not read
        # a cost-truncated scan as a clean pass.
        raise SystemExit(2)

    console.print(f"\n[green]Scan completed! Reports saved to {output_path}[/green]")

    from clausi.utils.output import display_findings_summary, open_in_editor

    findings_md = (output_path if len(regulations) == 1 else output_path / regulations[0]) / "findings.md"
    cfg = load_config()
    auto_show = show_markdown or (cfg.get("ui", {}).get("show_markdown", False) if cfg else False)
    if auto_show and findings_md.exists():
        display_findings_summary(findings_md)

    # Off unless asked for. Launching an editor on every scan hijacks the
    # user's screen on repeat runs and is simply wrong in CI; --open-findings
    # opts in, --no-open-findings always wins over the config.
    if open_findings is None:
        auto_open = bool(cfg.get("ui", {}).get("auto_open_findings", False)) if cfg else False
    else:
        auto_open = open_findings
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
@click.option("--claude-code", is_flag=True, help="Use your local Claude Code CLI (no API key needed)")
@click.option("--codex", is_flag=True, help="Use your local Codex CLI (no API key needed)")
@click.option("--skip-confirmation", "-y", is_flag=True, help="Skip cost confirmation prompt")
def docs_generate(path, output, exclude, include, claude_model, openai_model,
                  claude_code, codex, skip_confirmation):
    """Generate AI-powered documentation for a project - fully local.

    \b
    Examples:
        clausi docs generate                     # Auto-detects key or local agent
        clausi docs generate --claude-code       # Local Claude Code, no API key
        clausi docs generate --codex             # Local Codex CLI, no API key
        clausi docs generate --claude            # Force Claude via API key
        clausi docs generate --openai gpt-4o     # Force OpenAI via API key
        clausi docs generate --exclude "tests/*"
    """
    from clausi.core.docs_generator import DocsGenerator

    provider, model = _resolve_provider_and_model(claude_model, openai_model, claude_code, codex)
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
