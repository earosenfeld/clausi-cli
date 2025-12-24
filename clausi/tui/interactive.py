"""Simple interactive mode for Clausi CLI - numbered menu like Claude Code planning."""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
import questionary
from questionary import Style
import yaml

# Import regulations utilities
from clausi.utils import regulations as regs_module

console = Console()

# Template for new custom regulations
CUSTOM_REGULATION_TEMPLATE = '''name: "{name}"
description: "{description}"
version: "1.0"

clauses:
  - id: "{code}-001"
    title: "Example Requirement"
    description: "Description of this compliance requirement"
    requirements:
      - "First specific requirement to check"
      - "Second specific requirement to check"
    severity: "high"

  - id: "{code}-002"
    title: "Another Requirement"
    description: "Description of another compliance requirement"
    requirements:
      - "Requirement details here"
    severity: "warning"
'''


def open_native_file_dialog() -> str | None:
    """Open native OS file explorer dialog to select a folder.

    Works on Windows, macOS, and Linux.
    Returns the selected path or None if cancelled.
    """
    try:
        # Import tkinter (comes with Python)
        import tkinter as tk
        from tkinter import filedialog

        # Create a hidden root window
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Bring dialog to front

        # Open folder selection dialog
        folder_path = filedialog.askdirectory(
            title="Select Project Folder",
            initialdir=os.getcwd()
        )

        root.destroy()

        return folder_path if folder_path else None

    except ImportError:
        console.print("[yellow]Native file dialog not available (tkinter not installed)[/yellow]")
        console.print("[dim]Falling back to terminal browser...[/dim]")
        return None
    except Exception as e:
        console.print(f"[yellow]Could not open file dialog: {e}[/yellow]")
        console.print("[dim]Falling back to terminal browser...[/dim]")
        return None

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
            "2. Open file explorer...",
            "3. Browse in terminal...",
            "4. Type path manually"
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
        elif choice == "Open file explorer...":
            # Try native file dialog first
            path = open_native_file_dialog()
            if path:
                return path
            # Fall back to terminal browser if native dialog fails
            console.print("[dim]Opening terminal browser instead...[/dim]")
            return self.browse_directory()
        elif choice == "Browse in terminal...":
            return self.browse_directory()
        else:
            # Manual path entry with autocomplete
            path = questionary.path(
                "Enter path to scan:",
                only_directories=True,
                style=custom_style
            ).ask()
            return path

    def create_custom_regulation(self, project_path: str = None) -> str | None:
        """Create a new custom regulation from template.

        Returns the regulation code if created, None otherwise.
        """
        console.print("\n[bold cyan]Create Custom Regulation[/bold cyan]\n")

        # Get regulation details
        reg_name = questionary.text(
            "Regulation name (e.g., 'Company Security Policy'):",
            style=custom_style
        ).ask()

        if not reg_name:
            console.print("[yellow]Cancelled[/yellow]")
            return None

        reg_description = questionary.text(
            "Brief description:",
            default=f"Custom compliance requirements for {reg_name}",
            style=custom_style
        ).ask()

        if reg_description is None:
            console.print("[yellow]Cancelled[/yellow]")
            return None

        # Generate code from name (e.g., "Company Security Policy" -> "COMPANY-SECURITY-POLICY")
        reg_code = reg_name.upper().replace(" ", "-").replace("_", "-")
        reg_code = ''.join(c for c in reg_code if c.isalnum() or c == '-')

        # Ask where to save
        save_choices = [
            "1. Global (~/.clausi/custom_regulations/)",
            "2. Project-specific (.clausi/regulations/)"
        ]

        if project_path:
            save_choice = questionary.select(
                "Where to save?",
                choices=save_choices,
                qmark="",
                pointer="→"
            ).ask()
        else:
            save_choice = save_choices[0]  # Default to global if no project

        if save_choice is None:
            console.print("[yellow]Cancelled[/yellow]")
            return None

        # Determine save path
        if "Global" in save_choice:
            save_dir = Path.home() / ".clausi" / "custom_regulations"
        else:
            save_dir = Path(project_path) / ".clausi" / "regulations"

        save_dir.mkdir(parents=True, exist_ok=True)

        # Create filename from code
        filename = reg_code.lower() + ".yml"
        file_path = save_dir / filename

        # Check if already exists
        if file_path.exists():
            overwrite = questionary.confirm(
                f"File {filename} already exists. Overwrite?",
                default=False
            ).ask()
            if not overwrite:
                console.print("[yellow]Cancelled[/yellow]")
                return None

        # Generate content from template
        content = CUSTOM_REGULATION_TEMPLATE.format(
            name=reg_name,
            description=reg_description,
            code=reg_code
        )

        # Write file
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            console.print(f"\n[green]✓[/green] Created: {file_path}")
            console.print(f"[dim]Edit this file to add your compliance requirements.[/dim]")

            # Ask if they want to open the file
            open_file = questionary.confirm(
                "Open file in default editor?",
                default=True
            ).ask()

            if open_file:
                if sys.platform == 'win32':
                    os.startfile(str(file_path))
                elif sys.platform == 'darwin':
                    os.system(f'open "{file_path}"')
                else:
                    os.system(f'xdg-open "{file_path}"')

            return reg_code

        except Exception as e:
            console.print(f"[red]Error creating file: {e}[/red]")
            return None

    def select_regulations(self, project_path: str = None) -> list[str] | None:
        """Interactive regulation selection with checkboxes.

        Shows built-in regulations and any discovered custom regulations.
        Returns list of selected regulation codes, or None if cancelled.
        """
        # Fetch built-in and discover custom regulations
        built_in_regs = regs_module.get_regulations()
        custom_regs = regs_module.discover_custom_regulations(
            project_path=Path(project_path) if project_path else None
        )

        # Build choices list
        choices = []

        # Add built-in regulations
        for code, info in built_in_regs.items():
            name = info.get('name', code)
            desc = info.get('description', '')
            # Pre-select EU-AIA by default
            checked = code == "EU-AIA"
            choices.append(questionary.Choice(
                title=f"{code} - {name}",
                value=code,
                checked=checked
            ))

        # Add separator if there are custom regulations
        if custom_regs:
            choices.append(questionary.Separator("── Custom Regulations ──"))
            for code, path in custom_regs.items():
                # Load to get the name
                reg_data = regs_module.load_custom_regulation(path)
                name = reg_data.get('name', code) if reg_data else code
                choices.append(questionary.Choice(
                    title=f"{code} - {name} [custom]",
                    value=code,
                    checked=False
                ))

        # Add option to create new custom regulation
        choices.append(questionary.Separator("──────────────────────"))
        choices.append(questionary.Choice(
            title="➕ Create new custom regulation...",
            value="__CREATE_NEW__"
        ))

        # Show checkbox selection
        selected = questionary.checkbox(
            "Select regulations to check (use SPACE to select, ENTER to confirm):",
            choices=choices,
            qmark="",
            style=custom_style
        ).ask()

        if selected is None:
            return None

        # Handle "create new" option
        if "__CREATE_NEW__" in selected:
            selected.remove("__CREATE_NEW__")
            new_reg_code = self.create_custom_regulation(project_path)
            if new_reg_code:
                selected.append(new_reg_code)

        # Validate at least one regulation selected
        if not selected:
            console.print("[yellow]No regulations selected. Using EU-AIA as default.[/yellow]")
            return ["EU-AIA"]

        return selected

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

        # Step 3: Regulations - now with proper checkbox selection
        console.print()
        selected_regs = self.select_regulations(project_path=path)

        if selected_regs is None:
            console.print("\n[yellow]Scan cancelled[/yellow]\n")
            return

        # Build regulation flags
        reg_flags = " ".join([f"-r {r}" for r in selected_regs])

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
