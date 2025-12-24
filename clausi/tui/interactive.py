"""Simple interactive mode for Clausi CLI - numbered menu like Claude Code planning."""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
import questionary
from questionary import Style

console = Console()

# Custom style for questionary prompts
custom_style = Style([
    ('qmark', 'fg:cyan bold'),
    ('question', 'bold'),
    ('answer', 'fg:cyan'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:cyan bold'),
    ('selected', 'fg:cyan'),
])


class ClausInteractiveTUI:
    """Simple interactive Clausi interface with numbered menu."""

    def __init__(self):
        self.running = True

    def run(self):
        """Run the interactive session."""
        console.print("\n[bold cyan]Clausi[/bold cyan] - AI Compliance Auditing\n")

        while self.running:
            choice = self.show_main_menu()

            # Handle user cancellation (Ctrl+C or ESC)
            if choice is None:
                console.print("\n[dim]Goodbye![/dim]\n")
                break

            if choice == "Scan a project for compliance":
                self.scan_wizard()
            elif choice == "View configuration":
                os.system("clausi config show")
                console.print()
            elif choice == "List available AI models":
                os.system("clausi models list")
                console.print()
            elif choice == "Run setup wizard":
                os.system("clausi setup")
                console.print()
            elif choice == "Show help":
                os.system("clausi --help")
                console.print()
            elif choice == "Exit Clausi":
                console.print("\n[dim]Goodbye![/dim]\n")
                self.running = False

    def show_main_menu(self):
        """Display the main menu with arrow key navigation."""
        choices = [
            "1. Scan a project for compliance",
            "2. View configuration",
            "3. List available AI models",
            "4. Run setup wizard",
            "5. Show help",
            "6. Exit Clausi"
        ]
        result = questionary.select(
            "What would you like to do?",
            choices=choices,
            qmark="",
            pointer="→"
        ).ask()
        # Strip the number prefix for comparison
        return result.split(". ", 1)[1] if result else None


    def browse_directory(self, start_path: str = ".") -> str | None:
        """Interactive directory browser similar to Claude Code.

        Returns the selected path or None if cancelled.
        """
        current_path = Path(start_path).resolve()

        while True:
            # Build directory choices
            choices = []

            # Add parent directory option (unless at root)
            if current_path.parent != current_path:
                choices.append(".. (parent directory)")

            # Add current directory selection option
            choices.append(f"[Select this folder: {current_path.name or current_path}]")

            # Add subdirectories
            try:
                subdirs = sorted([
                    d.name + "/" for d in current_path.iterdir()
                    if d.is_dir() and not d.name.startswith('.')
                ])
                choices.extend(subdirs)
            except PermissionError:
                console.print("[yellow]Permission denied for some directories[/yellow]")

            # Show current location
            console.print(f"\n[dim]Current: {current_path}[/dim]")

            selection = questionary.select(
                "Select a directory:",
                choices=choices,
                qmark="",
                pointer="→",
                style=custom_style
            ).ask()

            if selection is None:
                return None

            if selection == ".. (parent directory)":
                current_path = current_path.parent
            elif selection.startswith("[Select this folder:"):
                return str(current_path)
            else:
                # Navigate into selected subdirectory (remove trailing /)
                current_path = current_path / selection.rstrip("/")

    def select_path(self) -> str | None:
        """Let user choose how to specify the path to scan.

        Returns the selected path or None if cancelled.
        """
        choices = [
            "1. Current directory (.)",
            "2. Browse for folder...",
            "3. Type path manually"
        ]

        choice = questionary.select(
            "Select project location:",
            choices=choices,
            qmark="",
            pointer="→",
            style=custom_style
        ).ask()

        if choice is None:
            return None

        choice = choice.split(". ", 1)[1]

        if choice == "Current directory (.)":
            return "."
        elif choice == "Browse for folder...":
            return self.browse_directory()
        else:
            # Manual path entry with autocomplete
            path = questionary.path(
                "Enter path to scan:",
                only_directories=True,
                style=custom_style
            ).ask()
            return path

    def scan_wizard(self):
        """Interactive scan wizard with numbered steps."""
        console.print("\n[bold cyan]Scan Wizard[/bold cyan]\n")

        # Step 1: Directory selection with browser
        path = self.select_path()

        if path is None:
            console.print("\n[yellow]Scan cancelled[/yellow]\n")
            return

        if not os.path.exists(path):
            console.print(f"[red]Error: Path '{path}' does not exist[/red]\n")
            return

        console.print(f"[green]Selected:[/green] {Path(path).resolve()}")

        # Step 2: AI Provider
        console.print()
        provider_choices = [
            "1. Clausi AI (no API key needed, pay per scan)",
            "2. Claude (bring your own Anthropic API key + $0.50 fee)",
            "3. OpenAI (bring your own OpenAI API key + $0.50 fee)"
        ]
        provider_choice = questionary.select(
            "Select AI provider:",
            choices=provider_choices,
            qmark="",
            pointer="→"
        ).ask()

        # Handle user cancellation
        if provider_choice is None:
            console.print("\n[yellow]Scan cancelled[/yellow]\n")
            return

        # Strip number prefix
        provider_choice = provider_choice.split(". ", 1)[1]

        provider_flags = {
            "Clausi AI (no API key needed, pay per scan)": "",
            "Claude (bring your own Anthropic API key + $0.50 fee)": "--claude",
            "OpenAI (bring your own OpenAI API key + $0.50 fee)": "--openai gpt-4o"
        }
        provider_flag = provider_flags[provider_choice]

        # Step 3: Regulations
        console.print()
        reg_choices = [
            "1. EU AI Act only",
            "2. EU AI Act + GDPR",
            "3. All regulations (EU-AIA, GDPR, ISO-42001, HIPAA, SOC2)",
            "4. Custom selection"
        ]
        reg_choice = questionary.select(
            "Select regulations:",
            choices=reg_choices,
            qmark="",
            pointer="→"
        ).ask()

        # Handle user cancellation
        if reg_choice is None:
            console.print("\n[yellow]Scan cancelled[/yellow]\n")
            return

        # Strip number prefix
        reg_choice = reg_choice.split(". ", 1)[1]

        if reg_choice == "EU AI Act only":
            reg_flags = "-r EU-AIA"
        elif reg_choice == "EU AI Act + GDPR":
            reg_flags = "-r EU-AIA -r GDPR"
        elif reg_choice == "All regulations (EU-AIA, GDPR, ISO-42001, HIPAA, SOC2)":
            reg_flags = "-r EU-AIA -r GDPR -r ISO-42001 -r HIPAA -r SOC2"
        else:
            regs = Prompt.ask("Enter regulations (comma-separated)", default="EU-AIA")
            reg_flags = " ".join([f"-r {r.strip()}" for r in regs.split(",")])

        # Step 4: Additional options
        console.print()
        preset_choices = [
            "1. Standard scan (all clauses)",
            "2. Critical-only preset (faster, cheaper)",
            "3. High-priority preset"
        ]
        preset_choice = questionary.select(
            "Additional options:",
            choices=preset_choices,
            qmark="",
            pointer="→"
        ).ask()

        # Handle user cancellation
        if preset_choice is None:
            console.print("\n[yellow]Scan cancelled[/yellow]\n")
            return

        # Strip number prefix
        preset_choice = preset_choice.split(". ", 1)[1]

        preset_flag = ""
        if preset_choice == "Critical-only preset (faster, cheaper)":
            preset_flag = "--preset critical-only"
        elif preset_choice == "High-priority preset":
            preset_flag = "--preset high-priority"

        # Build and run command
        cmd_parts = ["clausi", "scan"]

        # Quote path if it contains spaces
        if " " in path:
            cmd_parts.append(f'"{path}"')
        else:
            cmd_parts.append(path)

        cmd_parts.extend(reg_flags.split())
        if provider_flag:
            cmd_parts.extend(provider_flag.split())
        if preset_flag:
            cmd_parts.extend(preset_flag.split())
        cmd_parts.append("--open-findings")

        cmd = " ".join(cmd_parts)

        console.print(f"\n[dim]Running: {cmd}[/dim]\n")
        os.system(cmd)
        console.print()


if __name__ == "__main__":
    app = ClausInteractiveTUI()
    app.run()
