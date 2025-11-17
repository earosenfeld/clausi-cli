"""Clause selection and scoping utilities."""

from typing import List, Optional, Tuple
from rich.table import Table
from rich.prompt import Prompt
from clausi.utils.console import console

# Predefined clause presets for quick scoping
CLAUSE_PRESETS = {
    "EU-AIA": {
        "critical-only": [
            "EUAIA-3.1",  # Risk assessment
            "EUAIA-5.2",  # High-risk AI system requirements
            "EUAIA-7.2",  # Transparency obligations
            "EUAIA-9.1",  # Risk management system
        ],
        "high-priority": [
            "EUAIA-3.1",
            "EUAIA-5.2",
            "EUAIA-7.2",
            "EUAIA-9.1",
            "EUAIA-10.2",  # Data governance
            "EUAIA-12.1",  # Record keeping
            "EUAIA-13.1",  # Human oversight
        ],
        "documentation": [
            "EUAIA-7.2",   # Transparency
            "EUAIA-11.1",  # Technical documentation
            "EUAIA-12.1",  # Record keeping
            "EUAIA-13.3",  # Instructions for use
        ]
    },
    "GDPR": {
        "critical-only": [
            "GDPR-5.1",    # Data minimization
            "GDPR-32.1",   # Security of processing
            "GDPR-33.1",   # Breach notification
        ],
        "high-priority": [
            "GDPR-5.1",
            "GDPR-6.1",    # Lawfulness of processing
            "GDPR-25.1",   # Data protection by design
            "GDPR-32.1",
            "GDPR-35.1",   # Data protection impact assessment
        ],
        "data-handling": [
            "GDPR-5.1",
            "GDPR-6.1",
            "GDPR-7.1",    # Consent
            "GDPR-15.1",   # Right of access
            "GDPR-17.1",   # Right to erasure
        ]
    },
    "ISO-42001": {
        "critical-only": [
            "ISO42001-4.1",   # Context of organization
            "ISO42001-5.1",   # Leadership
            "ISO42001-6.1",   # Planning
        ],
        "high-priority": [
            "ISO42001-4.1",
            "ISO42001-5.1",
            "ISO42001-6.1",
            "ISO42001-7.1",   # Support
            "ISO42001-8.1",   # Operation
        ]
    },
    "HIPAA": {
        "critical-only": [
            "HIPAA-164.308", # Administrative safeguards
            "HIPAA-164.310", # Physical safeguards
            "HIPAA-164.312", # Technical safeguards
        ],
        "high-priority": [
            "HIPAA-164.308",
            "HIPAA-164.310",
            "HIPAA-164.312",
            "HIPAA-164.314", # Organizational requirements
            "HIPAA-164.316", # Policies and procedures
        ]
    },
    "SOC2": {
        "critical-only": [
            "SOC2-CC6.1",  # Logical and physical access
            "SOC2-CC7.1",  # System operations
            "SOC2-CC7.2",  # Change management
        ],
        "high-priority": [
            "SOC2-CC6.1",
            "SOC2-CC6.6",  # Encryption
            "SOC2-CC7.1",
            "SOC2-CC7.2",
            "SOC2-CC8.1",  # Risk assessment
        ]
    }
}


def get_preset_clauses(regulation: str, preset: str) -> Optional[List[str]]:
    """Get clause IDs for a given preset.

    Args:
        regulation: Regulation ID (e.g., "EU-AIA")
        preset: Preset name (e.g., "critical-only")

    Returns:
        List of clause IDs or None if preset not found
    """
    return CLAUSE_PRESETS.get(regulation, {}).get(preset)


def list_available_presets(regulation: str) -> List[str]:
    """List available presets for a regulation.

    Args:
        regulation: Regulation ID

    Returns:
        List of preset names
    """
    return list(CLAUSE_PRESETS.get(regulation, {}).keys())


def select_clauses_interactive(regulation: str, all_clauses: Optional[List[dict]] = None) -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """Interactive clause selection.

    Args:
        regulation: Regulation ID
        all_clauses: List of clause dictionaries with 'id', 'title', 'priority' keys
                     If None, will use preset-based selection only

    Returns:
        Tuple of (include_list, exclude_list)
    """
    console.print(f"\n[cyan]📋 Clause Selection for {regulation}[/cyan]\n")

    # Show available presets
    presets = list_available_presets(regulation)
    if presets:
        console.print("[yellow]Available presets:[/yellow]")
        for i, preset in enumerate(presets, 1):
            preset_clauses = get_preset_clauses(regulation, preset)
            console.print(f"  {i}. [cyan]{preset}[/cyan] ({len(preset_clauses)} clauses)")
        console.print(f"  {len(presets) + 1}. [cyan]custom[/cyan] (select manually)")
        console.print(f"  {len(presets) + 2}. [cyan]all[/cyan] (scan all clauses)")

        choice = Prompt.ask(
            "\n[cyan]Choose an option[/cyan]",
            default=str(len(presets) + 2)
        )

        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(presets):
                # User selected a preset
                preset_name = presets[choice_idx]
                selected = get_preset_clauses(regulation, preset_name)
                console.print(f"\n[green]✓ Selected preset '{preset_name}' with {len(selected)} clauses[/green]")
                return selected, None
            elif choice_idx == len(presets) + 1:
                # User wants all clauses
                console.print("\n[green]✓ Scanning all clauses[/green]")
                return None, None
        except (ValueError, IndexError):
            pass

    # If we have clause metadata, allow manual selection
    if all_clauses:
        return select_clauses_manual(all_clauses)

    # Fallback: scan all
    console.print("\n[yellow]No clause metadata available. Scanning all clauses.[/yellow]")
    return None, None


def select_clauses_manual(all_clauses: List[dict]) -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """Manual clause selection from list.

    Args:
        all_clauses: List of clause dictionaries

    Returns:
        Tuple of (include_list, exclude_list)
    """
    console.print("\n[cyan]Manual Clause Selection[/cyan]\n")

    # Display clauses in a table
    table = Table()
    table.add_column("#", style="cyan", width=4)
    table.add_column("Clause ID", style="green", width=15)
    table.add_column("Title", style="yellow")
    table.add_column("Priority", style="magenta", width=10)

    for i, clause in enumerate(all_clauses, 1):
        priority = clause.get('priority', 'medium')
        title = clause.get('title', 'No title')
        # Truncate long titles
        if len(title) > 60:
            title = title[:57] + "..."

        table.add_row(
            str(i),
            clause['id'],
            title,
            priority.upper()
        )

    console.print(table)

    console.print("\n[yellow]Selection options:[/yellow]")
    console.print("  • Enter clause numbers (comma-separated): [cyan]1,3,5,7[/cyan]")
    console.print("  • Enter ranges: [cyan]1-5,8,10-12[/cyan]")
    console.print("  • Enter 'all' to scan all clauses")
    console.print("  • Enter 'high' to scan only high-priority clauses")
    console.print("  • Enter 'critical' to scan only critical clauses")

    selection = Prompt.ask(
        "\n[cyan]Your selection[/cyan]",
        default="all"
    )

    # Parse selection
    if selection.lower() == 'all':
        return None, None

    if selection.lower() == 'high':
        selected = [c['id'] for c in all_clauses if c.get('priority') in ['high', 'critical']]
        console.print(f"\n[green]✓ Selected {len(selected)} high-priority clauses[/green]")
        return selected, None

    if selection.lower() == 'critical':
        selected = [c['id'] for c in all_clauses if c.get('priority') == 'critical']
        console.print(f"\n[green]✓ Selected {len(selected)} critical clauses[/green]")
        return selected, None

    # Parse comma-separated numbers and ranges
    try:
        indices = parse_selection_string(selection)
        selected = [all_clauses[i - 1]['id'] for i in indices if 0 < i <= len(all_clauses)]
        console.print(f"\n[green]✓ Selected {len(selected)} clauses[/green]")
        return selected, None
    except (ValueError, IndexError) as e:
        console.print(f"[red]Invalid selection: {e}[/red]")
        return None, None


def parse_selection_string(selection: str) -> List[int]:
    """Parse selection string like '1,3,5-7,10' into list of integers.

    Args:
        selection: Selection string

    Returns:
        List of selected indices

    Raises:
        ValueError: If selection string is invalid
    """
    indices = []
    parts = selection.split(',')

    for part in parts:
        part = part.strip()
        if '-' in part:
            # Range
            start, end = part.split('-', 1)
            start_idx = int(start.strip())
            end_idx = int(end.strip())
            indices.extend(range(start_idx, end_idx + 1))
        else:
            # Single number
            indices.append(int(part))

    return sorted(set(indices))  # Remove duplicates and sort


def display_clause_scope_summary(include: Optional[List[str]], exclude: Optional[List[str]]):
    """Display summary of clause scope.

    Args:
        include: List of included clause IDs (None = all)
        exclude: List of excluded clause IDs (None = none)
    """
    if not include and not exclude:
        console.print("[cyan]Scanning:[/cyan] All clauses")
        return

    if include:
        console.print(f"[cyan]Scanning:[/cyan] {len(include)} specific clauses")
        if len(include) <= 10:
            console.print(f"  [dim]{', '.join(include)}[/dim]")
        else:
            console.print(f"  [dim]{', '.join(include[:10])}... (+{len(include) - 10} more)[/dim]")

    if exclude:
        console.print(f"[cyan]Excluding:[/cyan] {len(exclude)} clauses")
        if len(exclude) <= 10:
            console.print(f"  [dim]{', '.join(exclude)}[/dim]")
        else:
            console.print(f"  [dim]{', '.join(exclude[:10])}... (+{len(exclude) - 10} more)[/dim]")
