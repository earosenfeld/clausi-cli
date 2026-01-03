"""Simple interactive mode for Clausi CLI - numbered menu like Claude Code planning."""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
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
        self.last_scan_path = None  # Track last scanned project for remediation

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
            elif choice == "Generate documentation":
                self.docs_wizard()
            elif choice == "View remediation guide":
                self.view_remediation_guide()
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
        """Display the main menu with arrow key navigation and number shortcuts."""
        choices = [
            questionary.Choice("Scan a project for compliance", shortcut_key="1"),
            questionary.Choice("Generate documentation", shortcut_key="2"),
            questionary.Choice("View remediation guide", shortcut_key="3"),
            questionary.Choice("View configuration", shortcut_key="4"),
            questionary.Choice("List available AI models", shortcut_key="5"),
            questionary.Choice("Run setup wizard", shortcut_key="6"),
            questionary.Choice("Show help", shortcut_key="7"),
            questionary.Choice("Exit Clausi", shortcut_key="8")
        ]
        result = questionary.select(
            "What would you like to do?",
            choices=choices,
            qmark="",
            pointer="→",
            use_shortcuts=True
        ).ask()
        return result if result else None

    def find_remediation_files(self, project_path: str = None) -> list[Path]:
        """Find all REMEDIATION.md files in a project's clausi output folder.

        Returns list of paths to remediation files found.
        """
        remediation_files = []

        if project_path:
            search_path = Path(project_path)
        else:
            search_path = Path.cwd()

        clausi_dir = search_path / "clausi"

        if not clausi_dir.exists():
            return []

        # Search for REMEDIATION.md in all regulation folders
        for reg_dir in clausi_dir.iterdir():
            if reg_dir.is_dir():
                latest_dir = reg_dir / "latest"
                if latest_dir.exists():
                    remediation_file = latest_dir / "REMEDIATION.md"
                    if remediation_file.exists():
                        remediation_files.append(remediation_file)

        return remediation_files

    def open_file(self, file_path: Path):
        """Open a file in the default system application."""
        try:
            if sys.platform == 'win32':
                os.startfile(str(file_path))
            elif sys.platform == 'darwin':
                os.system(f'open "{file_path}"')
            else:
                os.system(f'xdg-open "{file_path}"')
            console.print(f"[green]✓[/green] Opened: {file_path}")
        except Exception as e:
            console.print(f"[red]Error opening file: {e}[/red]")
            console.print(f"[dim]File location: {file_path}[/dim]")

    def view_remediation_guide(self, project_path: str = None):
        """View remediation guide for a project.

        If project_path is provided, looks there. Otherwise prompts user.
        """
        console.print("\n[bold cyan]View Remediation Guide[/bold cyan]\n")

        # If no project path, ask user to select
        if not project_path:
            # Check if we have a last scanned path
            if self.last_scan_path:
                use_last = questionary.confirm(
                    f"Use last scanned project? ({self.last_scan_path})",
                    default=True
                ).ask()
                if use_last:
                    project_path = self.last_scan_path

            if not project_path:
                project_path = self.select_path()
                if project_path is None:
                    console.print("[yellow]Cancelled[/yellow]\n")
                    return

        # Find remediation files
        remediation_files = self.find_remediation_files(project_path)

        if not remediation_files:
            console.print("[yellow]No remediation guides found.[/yellow]")
            console.print("[dim]Run a compliance scan first to generate remediation guidance.[/dim]\n")
            return

        # If multiple files, let user choose
        if len(remediation_files) == 1:
            self.open_file(remediation_files[0])
        else:
            # Build choices from file paths with number shortcuts
            # Note: questionary shortcuts only support single characters (1-9)
            def make_choice(text, shortcut_num):
                if shortcut_num <= 9:
                    return questionary.Choice(text, shortcut_key=str(shortcut_num))
                return questionary.Choice(text)

            choices = []
            file_mapping = {}
            num = 1
            for f in remediation_files:
                # Extract regulation name from path (e.g., clausi/eu-aia/latest/REMEDIATION.md -> eu-aia)
                reg_name = f.parent.parent.name.upper()
                choices.append(make_choice(reg_name, num))
                file_mapping[reg_name] = f
                num += 1
            choices.append(make_choice("Open all", num))
            choices.append(make_choice("Cancel", num + 1))

            choice = questionary.select(
                "Multiple remediation guides found. Select one:",
                choices=choices,
                qmark="",
                pointer="→",
                use_shortcuts=True
            ).ask()

            if choice is None or choice == "Cancel":
                console.print("[yellow]Cancelled[/yellow]\n")
                return

            if choice == "Open all":
                for f in remediation_files:
                    self.open_file(f)
            elif choice in file_mapping:
                self.open_file(file_mapping[choice])

        console.print()


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
            questionary.Choice("Current directory (.)", shortcut_key="1"),
            questionary.Choice("Open file explorer...", shortcut_key="2"),
            questionary.Choice("Browse in terminal...", shortcut_key="3"),
            questionary.Choice("Type path manually", shortcut_key="4")
        ]

        choice = questionary.select(
            "Select project location:",
            choices=choices,
            qmark="",
            pointer="→",
            style=custom_style,
            use_shortcuts=True
        ).ask()

        if choice is None:
            return None

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

        # Get regulation details using Rich prompts (works better on Windows)
        reg_name = Prompt.ask(
            "[cyan]Regulation name[/cyan] (e.g., 'Company Security Policy')"
        )

        if not reg_name or not reg_name.strip():
            console.print("[yellow]Cancelled[/yellow]")
            return None

        reg_name = reg_name.strip()

        reg_description = Prompt.ask(
            "[cyan]Brief description[/cyan]",
            default=f"Custom compliance requirements for {reg_name}"
        )

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
        """Interactive regulation selection - simple single-select with advanced multi-select option.

        Returns list of selected regulation codes, or None if cancelled.
        """
        # Fetch built-in and discover custom regulations
        built_in_regs = regs_module.get_regulations()
        custom_regs = regs_module.discover_custom_regulations(
            project_path=Path(project_path) if project_path else None
        )

        # Build simple choices - one regulation at a time with number shortcuts
        # Note: questionary shortcuts only support single characters (1-9)
        choices = []
        reg_mapping = {}  # Display text -> code
        num = 1

        def make_choice(text, shortcut_num):
            """Create choice with shortcut only if num <= 9"""
            if shortcut_num <= 9:
                return questionary.Choice(text, shortcut_key=str(shortcut_num))
            else:
                return questionary.Choice(text)  # No shortcut for 10+

        # Add built-in regulations with friendly names
        friendly_names = {
            "EU-AIA": "EU AI Act (EU-AIA)",
            "GDPR": "GDPR",
            "ISO-42001": "ISO 42001",
            "HIPAA": "HIPAA",
            "SOC2": "SOC 2"
        }

        for code in built_in_regs.keys():
            name = friendly_names.get(code, code)
            choices.append(make_choice(name, num))
            reg_mapping[name] = code
            num += 1

        # Add custom regulations
        if custom_regs:
            for code, path in custom_regs.items():
                reg_data = regs_module.load_custom_regulation(path)
                name = reg_data.get('name', code) if reg_data else code
                display = f"[Custom] {name}"
                choices.append(make_choice(display, num))
                reg_mapping[display] = code
                num += 1

        # Add create custom option
        create_custom_display = "Create new custom regulation"
        choices.append(make_choice(create_custom_display, num))
        num += 1

        # Add separator and advanced option
        choices.append(questionary.Separator("── Advanced ──"))
        multi_reg_display = "Scan multiple regulations"
        choices.append(make_choice(multi_reg_display, num))

        result = questionary.select(
            "Select regulation to scan against:",
            choices=choices,
            qmark="",
            pointer="→",
            style=custom_style,
            use_shortcuts=True
        ).ask()

        if result is None:
            return None

        # Handle special options
        if "Create new custom regulation" in result:
            new_code = self.create_custom_regulation(project_path)
            if new_code:
                console.print(f"\n[green]✓[/green] Custom regulation '{new_code}' created!")
                return [new_code]
            return None

        if "Scan multiple regulations" in result:
            return self._select_multiple_regulations(built_in_regs, custom_regs)

        # Return single selected regulation
        if result in reg_mapping:
            return [reg_mapping[result]]

        return None

    def _select_multiple_regulations(self, built_in_regs: dict, custom_regs: dict) -> list[str] | None:
        """Advanced multi-select for scanning multiple regulations at once."""
        # Show warning
        console.print("\n[yellow]Note:[/yellow] Multi-regulation scans generate separate reports per regulation")
        console.print("[yellow]and may increase scan time and cost.[/yellow]\n")

        # Build checkbox choices
        choices = []
        reg_mapping = {}

        friendly_names = {
            "EU-AIA": "EU AI Act",
            "GDPR": "GDPR",
            "ISO-42001": "ISO 42001",
            "HIPAA": "HIPAA",
            "SOC2": "SOC 2"
        }

        for code in built_in_regs.keys():
            display = friendly_names.get(code, code)
            choices.append(questionary.Choice(display, value=code))

        # Add custom regulations
        if custom_regs:
            for code, path in custom_regs.items():
                reg_data = regs_module.load_custom_regulation(path)
                name = reg_data.get('name', code) if reg_data else code
                choices.append(questionary.Choice(f"[Custom] {name}", value=code))

        selected = questionary.checkbox(
            "Select multiple regulations (Space to toggle, Enter to confirm):",
            choices=choices,
            qmark="",
            style=custom_style
        ).ask()

        if selected is None or len(selected) == 0:
            console.print("[yellow]No regulations selected[/yellow]")
            return None

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
            questionary.Choice("Clausi AI hosted (up to 200,000 LOC, $3.00 minimum then $0.40 per 100,000 LOC)", shortcut_key="1"),
            questionary.Choice("Claude BYOK (no size limit, $0.50 minimum then $0.10 per 100,000 LOC plus your Anthropic bill)", shortcut_key="2"),
            questionary.Choice("OpenAI BYOK (no size limit, $0.50 minimum then $0.10 per 100,000 LOC plus your OpenAI bill)", shortcut_key="3")
        ]
        provider_choice = questionary.select(
            "Select AI provider:",
            choices=provider_choices,
            qmark="",
            pointer="→",
            use_shortcuts=True
        ).ask()

        # Handle user cancellation
        if provider_choice is None:
            console.print("\n[yellow]Scan cancelled[/yellow]\n")
            return

        # Default provider flags (will be updated with model selection)
        provider_flag = ""

        # Step 2b: Model selection for BYOK providers
        if "Claude" in provider_choice:
            console.print()
            claude_models = [
                questionary.Choice("claude-sonnet-4-20250514 (Recommended - best balance)", shortcut_key="1"),
                questionary.Choice("claude-3-5-sonnet-20241022 (Previous generation)", shortcut_key="2"),
                questionary.Choice("claude-3-opus-20240229 (Most capable, slower)", shortcut_key="3"),
                questionary.Choice("claude-3-5-haiku-20241022 (Fastest, cheapest)", shortcut_key="4")
            ]
            model_choice = questionary.select(
                "Select Claude model:",
                choices=claude_models,
                qmark="",
                pointer="→",
                use_shortcuts=True
            ).ask()

            if model_choice is None:
                console.print("\n[yellow]Scan cancelled[/yellow]\n")
                return

            # Extract model name from choice
            model_name = model_choice.split(" (")[0]
            provider_flag = f"--claude {model_name}"

        elif "OpenAI" in provider_choice:
            console.print()
            openai_models = [
                questionary.Choice("gpt-4o (Recommended - best balance)", shortcut_key="1"),
                questionary.Choice("gpt-4o-mini (Faster, cheaper)", shortcut_key="2"),
                questionary.Choice("gpt-4-turbo (Previous generation)", shortcut_key="3"),
                questionary.Choice("o1-preview (Advanced reasoning, expensive)", shortcut_key="4")
            ]
            model_choice = questionary.select(
                "Select OpenAI model:",
                choices=openai_models,
                qmark="",
                pointer="→",
                use_shortcuts=True
            ).ask()

            if model_choice is None:
                console.print("\n[yellow]Scan cancelled[/yellow]\n")
                return

            # Extract model name from choice
            model_name = model_choice.split(" (")[0]
            provider_flag = f"--openai {model_name}"

        # Clausi AI uses default model, no flag needed

        # Check if BYOK provider selected and API key is missing
        from clausi.utils import config as config_module

        if "Claude" in provider_choice:
            api_key = config_module.get_anthropic_key()
            if not api_key:
                console.print("\n[yellow]Anthropic API key not found.[/yellow]")
                console.print("[dim]Opening browser to get your API key...[/dim]\n")

                # Open browser to Anthropic console
                import webbrowser
                webbrowser.open("https://console.anthropic.com/settings/keys")

                console.print("[cyan]1.[/cyan] Create a new API key in the browser")
                console.print("[cyan]2.[/cyan] Copy the key (starts with sk-ant-...)")
                console.print("[cyan]3.[/cyan] Paste it below\n")

                api_key = Prompt.ask("[cyan]Paste your Anthropic API key[/cyan]")
                if api_key and api_key.strip():
                    # Save to config
                    config = config_module.load_config() or {}
                    config.setdefault("api_keys", {})["anthropic"] = api_key.strip()
                    if config_module.save_config(config):
                        console.print("[green]✓[/green] API key saved! You won't need to enter it again.\n")
                    else:
                        console.print("[red]Failed to save API key[/red]\n")
                        return
                else:
                    console.print("[yellow]No API key provided. Scan cancelled.[/yellow]\n")
                    return

        elif "OpenAI" in provider_choice:
            api_key = config_module.get_openai_key()
            if not api_key:
                console.print("\n[yellow]OpenAI API key not found.[/yellow]")
                console.print("[dim]Opening browser to get your API key...[/dim]\n")

                # Open browser to OpenAI API keys page
                import webbrowser
                webbrowser.open("https://platform.openai.com/api-keys")

                console.print("[cyan]1.[/cyan] Create a new API key in the browser")
                console.print("[cyan]2.[/cyan] Copy the key (starts with sk-...)")
                console.print("[cyan]3.[/cyan] Paste it below\n")

                api_key = Prompt.ask("[cyan]Paste your OpenAI API key[/cyan]")
                if api_key and api_key.strip():
                    # Save to config
                    config = config_module.load_config() or {}
                    config.setdefault("api_keys", {})["openai"] = api_key.strip()
                    if config_module.save_config(config):
                        console.print("[green]✓[/green] API key saved! You won't need to enter it again.\n")
                    else:
                        console.print("[red]Failed to save API key[/red]\n")
                        return
                else:
                    console.print("[yellow]No API key provided. Scan cancelled.[/yellow]\n")
                    return

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
            questionary.Choice("Standard scan (all clauses)", shortcut_key="1"),
            questionary.Choice("Critical-only preset (faster, cheaper)", shortcut_key="2"),
            questionary.Choice("High-priority preset", shortcut_key="3")
        ]
        preset_choice = questionary.select(
            "Additional options:",
            choices=preset_choices,
            qmark="",
            pointer="→",
            use_shortcuts=True
        ).ask()

        # Handle user cancellation
        if preset_choice is None:
            console.print("\n[yellow]Scan cancelled[/yellow]\n")
            return

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
        exit_code = os.system(cmd)

        # Track the scanned path for remediation feature
        abs_path = str(Path(path).resolve())
        self.last_scan_path = abs_path

        # Handle different exit codes
        # Exit code 0 = success, 2 = payment required (insufficient balance), other = error
        if exit_code == 0:
            # Scan completed successfully - offer to view remediation guide
            remediation_files = self.find_remediation_files(abs_path)
            if remediation_files:
                console.print()
                view_remediation = questionary.confirm(
                    "View remediation guide with fix suggestions?",
                    default=True
                ).ask()
                if view_remediation:
                    self.view_remediation_guide(abs_path)
            else:
                console.print("[dim]No remediation guide generated for this scan.[/dim]")
        elif exit_code == 512:  # os.system returns exit_code * 256, so 2 * 256 = 512
            # Payment required - prompt to rescan after adding funds
            console.print()
            rescan = questionary.confirm(
                "Re-run scan after adding funds?",
                default=True
            ).ask()
            if rescan:
                console.print("\n[dim]Waiting 5 seconds for payment to process...[/dim]")
                import time
                time.sleep(5)
                console.print(f"\n[dim]Re-running: {cmd}[/dim]\n")
                os.system(cmd)
        # For other exit codes (errors), don't prompt anything

        console.print()

    def docs_wizard(self):
        """Interactive documentation generation wizard."""
        console.print("\n[bold cyan]Documentation Generator[/bold cyan]\n")
        console.print("[dim]Generate AI-powered documentation for your project.[/dim]\n")

        # Step 1: Directory selection
        path = self.select_path()

        if path is None:
            console.print("\n[yellow]Cancelled[/yellow]\n")
            return

        if not os.path.exists(path):
            console.print(f"[red]Error: Path '{path}' does not exist[/red]\n")
            return

        console.print(f"[green]Selected:[/green] {Path(path).resolve()}")

        # Step 2: AI Provider
        console.print()
        console.print("[dim]Docs generation has a 30% premium on scan pricing.[/dim]\n")

        provider_choices = [
            questionary.Choice("Clausi AI hosted (up to 200,000 LOC, $3.90 minimum then $0.52 per 100,000 LOC)", shortcut_key="1"),
            questionary.Choice("Claude BYOK (no size limit, $0.65 minimum then $0.13 per 100,000 LOC plus your Anthropic bill)", shortcut_key="2"),
            questionary.Choice("OpenAI BYOK (no size limit, $0.65 minimum then $0.13 per 100,000 LOC plus your OpenAI bill)", shortcut_key="3")
        ]
        provider_choice = questionary.select(
            "Select AI provider:",
            choices=provider_choices,
            qmark="",
            pointer="→",
            use_shortcuts=True
        ).ask()

        if provider_choice is None:
            console.print("\n[yellow]Cancelled[/yellow]\n")
            return

        provider_flag = ""
        if "Claude" in provider_choice:
            provider_flag = "--claude"
        elif "OpenAI" in provider_choice:
            provider_flag = "--openai"
        elif "Clausi AI" in provider_choice:
            provider_flag = "--clausi"

        # Check API key if BYOK
        from clausi.utils import config as config_module

        if "Claude" in provider_choice:
            api_key = config_module.get_anthropic_key()
            if not api_key:
                console.print("\n[yellow]Anthropic API key not found.[/yellow]")
                console.print("[dim]Opening browser to get your API key...[/dim]\n")

                import webbrowser
                webbrowser.open("https://console.anthropic.com/settings/keys")

                console.print("[cyan]1.[/cyan] Create a new API key in the browser")
                console.print("[cyan]2.[/cyan] Copy the key (starts with sk-ant-...)")
                console.print("[cyan]3.[/cyan] Paste it below\n")

                api_key = Prompt.ask("[cyan]Paste your Anthropic API key[/cyan]")
                if api_key and api_key.strip():
                    config = config_module.load_config() or {}
                    config.setdefault("api_keys", {})["anthropic"] = api_key.strip()
                    if config_module.save_config(config):
                        console.print("[green]✓[/green] API key saved!\n")
                    else:
                        console.print("[red]Failed to save API key[/red]\n")
                        return
                else:
                    console.print("[yellow]No API key provided. Cancelled.[/yellow]\n")
                    return

        elif "OpenAI" in provider_choice:
            api_key = config_module.get_openai_key()
            if not api_key:
                console.print("\n[yellow]OpenAI API key not found.[/yellow]")
                console.print("[dim]Opening browser to get your API key...[/dim]\n")

                import webbrowser
                webbrowser.open("https://platform.openai.com/api-keys")

                console.print("[cyan]1.[/cyan] Create a new API key in the browser")
                console.print("[cyan]2.[/cyan] Copy the key (starts with sk-...)")
                console.print("[cyan]3.[/cyan] Paste it below\n")

                api_key = Prompt.ask("[cyan]Paste your OpenAI API key[/cyan]")
                if api_key and api_key.strip():
                    config = config_module.load_config() or {}
                    config.setdefault("api_keys", {})["openai"] = api_key.strip()
                    if config_module.save_config(config):
                        console.print("[green]✓[/green] API key saved!\n")
                    else:
                        console.print("[red]Failed to save API key[/red]\n")
                        return
                else:
                    console.print("[yellow]No API key provided. Cancelled.[/yellow]\n")
                    return

        # Step 3: Output format
        console.print()
        format_choices = [
            questionary.Choice("Markdown (default)", shortcut_key="1"),
            questionary.Choice("HTML", shortcut_key="2")
        ]
        format_choice = questionary.select(
            "Output format:",
            choices=format_choices,
            qmark="",
            pointer="→",
            use_shortcuts=True
        ).ask()

        if format_choice is None:
            console.print("\n[yellow]Cancelled[/yellow]\n")
            return

        format_flag = ""
        if "HTML" in format_choice:
            format_flag = "--format html"

        # Build and run command
        cmd_parts = ["clausi", "docs", "generate"]

        if " " in path:
            cmd_parts.append(f'"{path}"')
        else:
            cmd_parts.append(path)

        if provider_flag:
            cmd_parts.append(provider_flag)
        if format_flag:
            cmd_parts.extend(format_flag.split())

        cmd = " ".join(cmd_parts)

        console.print(f"\n[dim]Running: {cmd}[/dim]\n")
        exit_code = os.system(cmd)

        if exit_code == 0:
            abs_path = Path(path).resolve()
            docs_dir = abs_path / "clausi" / "docs" / "latest"
            if docs_dir.exists():
                console.print(f"\n[green]✓[/green] Documentation generated in: {docs_dir}")

                # Offer to open the docs
                open_docs = questionary.confirm(
                    "Open documentation in browser/editor?",
                    default=True
                ).ask()
                if open_docs:
                    index_file = docs_dir / "index.md"
                    if index_file.exists():
                        self.open_file(index_file)
                    else:
                        # Open the directory
                        if sys.platform == 'win32':
                            os.startfile(str(docs_dir))
                        elif sys.platform == 'darwin':
                            os.system(f'open "{docs_dir}"')
                        else:
                            os.system(f'xdg-open "{docs_dir}"')

        console.print()


if __name__ == "__main__":
    app = ClausInteractiveTUI()
    app.run()
