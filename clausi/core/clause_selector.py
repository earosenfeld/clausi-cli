"""Clause selection and scoping utilities."""

from typing import List, Optional, Tuple
from rich.table import Table
from rich.prompt import Prompt
from clausi.utils.console import console

# Predefined clause presets for quick scoping.
# IDs here must match the "id:" field in clausi/data/regulations/*.yml exactly -
# they're matched by simple string equality (clausi/core/compliance_analyzer.py),
# not fuzzy-matched, so a typo or stale ID here silently scans zero clauses.
CLAUSE_PRESETS = {
    "EU-AIA": {
        "critical-only": [
            "Article-9",   # Risk Management System
            "Article-13",  # Transparency and Information to Users
            "Article-14",  # Human Oversight
        ],
        "high-priority": [
            "Article-9",
            "Article-10",  # Data and Data Governance
            "Article-13",
            "Article-14",
            "Article-15",  # Accuracy, Robustness and Cybersecurity
        ],
        "documentation": [
            "Article-11",  # Technical Documentation
            "Article-12",  # Record-Keeping and Logging
            "Article-13",
        ]
    },
    "GDPR": {
        "critical-only": [
            "Article-5",     # Principles Relating to Processing of Personal Data
            "Article-32",    # Security of Processing
            "Article-33-34", # Personal Data Breach Notification
        ],
        "high-priority": [
            "Article-5",
            "Article-6",   # Lawfulness of Processing
            "Article-25",  # Data Protection by Design and by Default
            "Article-32",
            "Article-35",  # Data Protection Impact Assessment (DPIA)
        ],
        "data-handling": [
            "Article-5",
            "Article-6",
            "Article-7",      # Conditions for Consent
            "Article-15-22",  # Data Subject Rights
        ]
    },
    "ISO-42001": {
        "critical-only": [
            "Clause-4",  # Context of the Organization
            "Clause-5",  # Leadership and Organizational Commitment
            "Clause-6",  # Planning and Risk Assessment
        ],
        "high-priority": [
            "Clause-4",
            "Clause-5",
            "Clause-6",
            "Clause-8.1",  # Operational Planning and Control
            "Clause-8.2",  # AI System Lifecycle Management
        ]
    },
    "HIPAA": {
        "critical-only": [
            "Security-Rule-164.308",  # Administrative Safeguards
            "Security-Rule-164.310",  # Physical Safeguards
            "Security-Rule-164.312",  # Technical Safeguards
        ],
        "high-priority": [
            "Security-Rule-164.308",
            "Security-Rule-164.310",
            "Security-Rule-164.312",
            "Security-Rule-164.316",   # Policies, Procedures and Documentation
            "Breach-Notification-164.404",  # Breach Notification to Individuals
        ]
    },
    "SOC2": {
        "critical-only": [
            "CC6-Logical-Access",     # Logical and Physical Access Controls
            "CC7-System-Operations",  # System Operations
            "CC8-Change-Management",  # Change Management
        ],
        "high-priority": [
            "CC6-Logical-Access",
            "CC7-System-Operations",
            "CC8-Change-Management",
            "CC9-Risk-Mitigation",  # Risk Mitigation
            "CC3-Risk-Assessment",  # Risk Assessment Process
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
