"""Simple interactive mode for Clausi CLI - numbered menu like Claude Code planning."""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
import questionary

console = Console()


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


    def scan_wizard(self):
        """Interactive scan wizard with numbered steps."""
        console.print("\n[bold cyan]Scan Wizard[/bold cyan]\n")

        # Step 1: Directory
        path = Prompt.ask("Path to scan", default=".")
        if not os.path.exists(path):
            console.print(f"[red]Error: Path '{path}' does not exist[/red]\n")
            return

        # Step 2: AI Provider
        console.print()
        provider_choices = [
            "1. Clausi AI (free, no API key required)",
            "2. Claude (requires Anthropic API key)",
            "3. OpenAI (requires OpenAI API key)"
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
            "Clausi AI (free, no API key required)": "",
            "Claude (requires Anthropic API key)": "--claude",
            "OpenAI (requires OpenAI API key)": "--openai gpt-4o"
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
