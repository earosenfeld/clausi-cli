"""Output formatting and display utilities."""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List
from rich.markdown import Markdown
from rich.panel import Panel

from clausi.utils.emoji import get as emoji
from clausi.utils.console import console


def ensure_output_dir(path: str, output_dir: Optional[str] = None) -> Path:
    """Ensure output directory exists and return its path.

    Args:
        path: Project path (unused but kept for compatibility)
        output_dir: Optional custom output directory path

    Returns:
        Path to the output directory
    """
    if output_dir:
        output_path = Path(output_dir)
    else:
        # Default to clausi/reports directory to avoid conflicts with existing project reports/
        output_path = Path.cwd() / "clausi" / "reports"
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def open_in_editor(file_path: Path) -> bool:
    """Open a file in the user's default editor.

    Args:
        file_path: Path to the file to open

    Returns:
        True if successful, False otherwise
    """
    if not file_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return False

    try:
        # Try different methods based on platform
        if sys.platform == 'win32':
            # Windows - use start command
            os.startfile(str(file_path))
        elif sys.platform == 'darwin':
            # macOS - use open command
            subprocess.run(['open', str(file_path)], check=True)
        else:
            # Linux - try xdg-open
            subprocess.run(['xdg-open', str(file_path)], check=True)

        console.print(f"[green]{emoji('check')} Opened {file_path.name} in default editor[/green]")
        return True

    except Exception as e:
        console.print(f"[yellow]Could not auto-open {file_path.name}: {e}[/yellow]")
        console.print(f"[dim]You can manually open: {file_path}[/dim]")
        return False


def display_markdown(file_path: Path, title: Optional[str] = None) -> None:
    """Display markdown file content in the terminal.

    Args:
        file_path: Path to markdown file
        title: Optional title for the panel
    """
    if not file_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        md = Markdown(content)

        if title:
            console.print(Panel(md, title=title, border_style="cyan"))
        else:
            console.print(md)

    except Exception as e:
        console.print(f"[red]Error displaying markdown: {e}[/red]")


def display_markdown_summary(file_path: Path, max_lines: int = 20) -> None:
    """Display a summary (first N lines) of a markdown file.

    Args:
        file_path: Path to markdown file
        max_lines: Maximum number of lines to display
    """
    if not file_path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Take first N lines
        summary_lines = lines[:max_lines]
        summary_content = ''.join(summary_lines)

        if len(lines) > max_lines:
            summary_content += f"\n\n... ({len(lines) - max_lines} more lines)\n"

        md = Markdown(summary_content)
        console.print(Panel(
            md,
            title=f"📄 {file_path.name} (Preview)",
            border_style="blue"
        ))

    except Exception as e:
        console.print(f"[red]Error displaying summary: {e}[/red]")


def create_run_folder(base_output_dir: Path, project_name: str) -> Path:
    """Create a timestamped run folder for organizing scan outputs.

    Args:
        base_output_dir: Base output directory (e.g., ./reports)
        project_name: Name of the project being scanned

    Returns:
        Path to the created run folder
    """
    from datetime import datetime

    # Create timestamp-based folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder_name = f"{project_name}_{timestamp}"

    run_folder = base_output_dir / run_folder_name
    run_folder.mkdir(parents=True, exist_ok=True)

    console.print(f"[cyan]📁 Created run folder: {run_folder}[/cyan]")

    return run_folder


def download_markdown_files(
    api_url: str,
    run_id: str,
    output_dir: Path,
    api_key: str
) -> List[Path]:
    """Download markdown report files from backend.

    Args:
        api_url: Backend API URL
        run_id: Scan run ID
        output_dir: Directory to save files
        api_key: API key for authentication

    Returns:
        List of downloaded file paths
    """
    import requests

    markdown_files = [
        "findings.md",
        "traceability.md",
        "action_plan.md"
    ]

    downloaded = []

    for filename in markdown_files:
        try:
            response = requests.get(
                f"{api_url}/api/clausi/report/{run_id}/{filename}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30
            )

            if response.status_code == 200:
                file_path = output_dir / filename
                with open(file_path, 'wb') as f:
                    f.write(response.content)

                downloaded.append(file_path)
                console.print(f"[green]{emoji('check')} Downloaded {filename}[/green]")

            elif response.status_code == 404:
                console.print(f"[dim]  {filename} not available[/dim]")
            else:
                console.print(f"[yellow]⚠ Could not download {filename}: {response.status_code}[/yellow]")

        except Exception as e:
            console.print(f"[red]✗ Error downloading {filename}: {e}[/red]")

    return downloaded


def display_findings_summary(findings_file: Path) -> None:
    """Display a formatted summary of findings from markdown.

    Args:
        findings_file: Path to findings.md file
    """
    if not findings_file.exists():
        return

    console.print("\n" + "=" * 60)
    console.print("📋 FINDINGS SUMMARY")
    console.print("=" * 60 + "\n")

    display_markdown_summary(findings_file, max_lines=30)

    console.print(f"\n[cyan]💡 View full report: {findings_file}[/cyan]")
    console.print(f"[dim]   Or run: cat {findings_file}[/dim]\n")


def display_cache_statistics(cache_stats: dict) -> None:
    """Display cache hit/miss statistics in a formatted table.

    Args:
        cache_stats: Dictionary containing cache statistics from backend
                     Example: {
                         "total_files": 150,
                         "cache_hits": 120,
                         "cache_misses": 30,
                         "cache_hit_rate": 0.80,
                         "tokens_saved": 45000,
                         "cost_saved": 2.25
                     }
    """
    from rich.table import Table

    if not cache_stats:
        return

    console.print(f"\n[bold cyan]{emoji('chart')} Cache Statistics[/bold cyan]")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    # Cache hit rate
    cache_hit_rate = cache_stats.get("cache_hit_rate", 0) * 100
    table.add_row("Cache Hit Rate", f"{cache_hit_rate:.1f}%")

    # Files cached vs analyzed
    cache_hits = cache_stats.get("cache_hits", 0)
    total_files = cache_stats.get("total_files", 0)
    table.add_row("Files Cached", f"{cache_hits} / {total_files}")

    # Cost saved ($ only - hybrid approach, tokens kept internal)
    cost_saved = cache_stats.get("cost_saved", 0)
    if cost_saved > 0:
        table.add_row("Cost Saved", f"${cost_saved:.2f}")

    console.print(table)
    console.print()


def display_scan_progress(
    current_file: int,
    total_files: int,
    current_clause: int,
    total_clauses: int,
    file_name: str,
    clause_id: str,
    tokens_used: int = 0,
    estimated_cost: float = 0.0
) -> None:
    """Display detailed scan progress with file and clause information.

    Args:
        current_file: Current file number being processed
        total_files: Total number of files to process
        current_clause: Current clause number being checked
        total_clauses: Total number of clauses to check
        file_name: Name of current file being analyzed
        clause_id: ID of current clause being checked
        tokens_used: Tokens used so far (optional)
        estimated_cost: Estimated cost so far (optional)
    """
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

    # Truncate long file names
    if len(file_name) > 40:
        file_name = "..." + file_name[-37:]

    status_text = f"[cyan]File {current_file}/{total_files}:[/cyan] {file_name}\n"
    status_text += f"[yellow]Clause {current_clause}/{total_clauses}:[/yellow] {clause_id}"

    if estimated_cost > 0:
        status_text += f"\n[dim]Cost: ${estimated_cost:.2f}[/dim]"

    console.print(status_text)


def create_enhanced_progress_bar(description: str = "Processing..."):
    """Create an enhanced progress bar with more visual elements.

    Args:
        description: Description text for the progress bar

    Returns:
        Progress context manager with enhanced columns
    """
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeRemainingColumn,
        TimeElapsedColumn
    )

    return Progress(
        SpinnerColumn(spinner_name="line"),  # Use ASCII-safe spinner for Windows
        TextColumn("[bold blue]{task.description}"),
        BarColumn(complete_style="green", finished_style="bold green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    )
