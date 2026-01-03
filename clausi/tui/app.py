"""Main Textual UI application for Clausi."""

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Button, Static
from textual.binding import Binding

from clausi.tui.screens.config import ConfigScreen


class ClausUI(App):
    """Main Clausi TUI application."""

    CSS = """
    Screen {
        align: center middle;
    }

    #main-container {
        width: 80;
        height: auto;
        border: solid $primary;
        padding: 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }

    #actions {
        width: 100%;
        height: auto;
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1 2;
        margin-top: 2;
    }

    Button {
        width: 100%;
        height: 3;
    }

    #description {
        text-align: center;
        margin-top: 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("c", "config", "Config"),
        Binding("s", "scan", "Scan"),
    ]

    TITLE = "Clausi CLI v1.0.0"
    SUB_TITLE = "AI Compliance Auditing"

    def compose(self) -> ComposeResult:
        """Compose the main UI."""
        yield Header()

        with Container(id="main-container"):
            yield Static("Clausi Interactive Mode", id="title")
            yield Static(
                "Choose an action below or press the keyboard shortcut",
                id="description"
            )

            with Vertical(id="actions"):
                yield Button("Configuration Editor [C]", id="config-button", variant="primary")
                yield Button("Scan Builder [S]", id="scan-button", variant="success")
                yield Button("View Documentation", id="docs-button")
                yield Button("Quit [Q]", id="quit-button", variant="error")

        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "config-button":
            self.action_config()
        elif button_id == "scan-button":
            self.action_scan()
        elif button_id == "docs-button":
            self.action_docs()
        elif button_id == "quit-button":
            self.action_quit()

    def action_config(self) -> None:
        """Open configuration editor."""
        self.push_screen(ConfigScreen())

    def action_scan(self) -> None:
        """Redirect to CLI scan command."""
        self.notify("Use 'clausi scan <path>' in terminal. See 'clausi scan --help'", severity="information", timeout=5)

    def action_docs(self) -> None:
        """Open documentation."""
        import webbrowser
        webbrowser.open("https://docs.clausi.ai")
        self.notify("Opened documentation in browser", severity="information", timeout=2)

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def run_tui(mode: str = "main") -> None:
    """
    Run the TUI application.

    Args:
        mode: Which screen to show ("main", "config", "scan")
    """
    app = ClausUI()

    if mode == "config":
        # Go directly to config screen
        app.push_screen(ConfigScreen())

    app.run()
