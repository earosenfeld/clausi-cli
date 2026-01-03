"""Configuration editor screen for TUI."""

import os
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static, Select
from textual.binding import Binding

from clausi.utils.config import load_config, save_config, get_config_path


class ConfigScreen(Screen):
    """Interactive configuration editor."""

    CSS = """
    ConfigScreen {
        align: center middle;
    }

    #config-container {
        width: 90;
        height: auto;
        max-height: 40;
        border: solid $primary;
        padding: 2;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }

    .config-row {
        height: auto;
        width: 100%;
        margin-bottom: 1;
    }

    .config-label {
        width: 25;
        padding-right: 2;
    }

    .config-input {
        width: 1fr;
    }

    #button-bar {
        height: 3;
        margin-top: 2;
        align: center middle;
    }

    #button-bar Button {
        margin: 0 1;
    }

    .hint {
        color: $text-muted;
        text-style: italic;
        margin-left: 25;
        margin-bottom: 1;
    }

    .status-message {
        text-align: center;
        margin-top: 1;
        padding: 1;
    }

    .success {
        color: $success;
        text-style: bold;
    }

    .error {
        color: $error;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self):
        """Initialize the config screen."""
        super().__init__()
        self.config = load_config() or {}
        self.status_message = ""

    def compose(self) -> ComposeResult:
        """Compose the configuration UI."""
        with ScrollableContainer(id="config-container"):
            yield Static("Configuration Editor", classes="section-title")
            yield Static("Press Ctrl+S to save, Esc to cancel", classes="hint")

            # API Keys section
            yield Static("API Keys", classes="section-title")

            with Horizontal(classes="config-row"):
                yield Label("Anthropic API Key:", classes="config-label")
                anthropic_key = self.config.get("api_keys", {}).get("anthropic", "")
                yield Input(
                    value=anthropic_key,
                    placeholder="sk-ant-...",
                    password=True,
                    id="anthropic-key",
                    classes="config-input"
                )

            yield Static("Get your key from: https://console.anthropic.com", classes="hint")

            with Horizontal(classes="config-row"):
                yield Label("OpenAI API Key:", classes="config-label")
                openai_key = self.config.get("api_keys", {}).get("openai", "") or self.config.get("openai_key", "")
                yield Input(
                    value=openai_key,
                    placeholder="sk-...",
                    password=True,
                    id="openai-key",
                    classes="config-input"
                )

            yield Static("Get your key from: https://platform.openai.com/api-keys", classes="hint")

            # AI Provider section
            yield Static("AI Provider Settings", classes="section-title")

            with Horizontal(classes="config-row"):
                yield Label("Default Provider:", classes="config-label")
                provider = self.config.get("ai", {}).get("provider", "claude")
                yield Select(
                    [("Claude (Anthropic)", "claude"), ("OpenAI", "openai")],
                    value=provider,
                    id="ai-provider",
                    classes="config-input"
                )

            # Report Settings section
            yield Static("Report Settings", classes="section-title")

            with Horizontal(classes="config-row"):
                yield Label("Output Directory:", classes="config-label")
                output_dir = self.config.get("report", {}).get("output_dir", "reports")
                yield Input(
                    value=output_dir,
                    placeholder="reports",
                    id="output-dir",
                    classes="config-input"
                )

            with Horizontal(classes="config-row"):
                yield Label("Report Format:", classes="config-label")
                report_format = self.config.get("report", {}).get("format", "pdf")
                yield Select(
                    [("PDF", "pdf"), ("HTML", "html"), ("JSON", "json"), ("All Formats", "all")],
                    value=report_format,
                    id="report-format",
                    classes="config-input"
                )

            with Horizontal(classes="config-row"):
                yield Label("Company Name:", classes="config-label")
                company_name = self.config.get("report", {}).get("company_name", "")
                yield Input(
                    value=company_name,
                    placeholder="ACME Corp",
                    id="company-name",
                    classes="config-input"
                )

            # Status message
            yield Static("", id="status", classes="status-message")

            # Action buttons
            with Horizontal(id="button-bar"):
                yield Button("Save [Ctrl+S]", variant="primary", id="save-button")
                yield Button("Test Connection", variant="success", id="test-button")
                yield Button("Cancel [Esc]", variant="error", id="cancel-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "save-button":
            self.action_save()
        elif button_id == "test-button":
            self.action_test()
        elif button_id == "cancel-button":
            self.action_cancel()

    def action_save(self) -> None:
        """Save the configuration."""
        try:
            # Get values from inputs
            anthropic_key = self.query_one("#anthropic-key", Input).value.strip()
            openai_key = self.query_one("#openai-key", Input).value.strip()
            ai_provider = self.query_one("#ai-provider", Select).value
            output_dir = self.query_one("#output-dir", Input).value.strip()
            report_format = self.query_one("#report-format", Select).value
            company_name = self.query_one("#company-name", Input).value.strip()

            # Update config
            if "api_keys" not in self.config:
                self.config["api_keys"] = {}

            if anthropic_key:
                self.config["api_keys"]["anthropic"] = anthropic_key

            if openai_key:
                self.config["api_keys"]["openai"] = openai_key

            if "ai" not in self.config:
                self.config["ai"] = {}
            self.config["ai"]["provider"] = ai_provider

            if "report" not in self.config:
                self.config["report"] = {}

            self.config["report"]["output_dir"] = output_dir or "reports"
            self.config["report"]["format"] = report_format
            self.config["report"]["company_name"] = company_name

            # Save to file
            if save_config(self.config):
                status = self.query_one("#status", Static)
                status.update("Configuration saved successfully!")
                status.add_class("success")
                status.remove_class("error")

                self.notify("Configuration saved!", severity="information", timeout=3)

                # Show equivalent CLI command
                cli_cmds = []
                if anthropic_key:
                    cli_cmds.append("clausi config set --anthropic-key YOUR_KEY")
                if ai_provider:
                    cli_cmds.append(f"clausi config set --ai-provider {ai_provider}")

                if cli_cmds:
                    self.notify(
                        f"Equivalent CLI: {'; '.join(cli_cmds)}",
                        severity="information",
                        timeout=5
                    )
            else:
                raise Exception("Failed to save configuration file")

        except Exception as e:
            status = self.query_one("#status", Static)
            status.update(f"Error: {str(e)}")
            status.add_class("error")
            status.remove_class("success")
            self.notify(f"Failed to save: {str(e)}", severity="error", timeout=5)

    def action_test(self) -> None:
        """Test the API connection."""
        anthropic_key = self.query_one("#anthropic-key", Input).value.strip()
        openai_key = self.query_one("#openai-key", Input).value.strip()
        ai_provider = self.query_one("#ai-provider", Select).value

        if ai_provider == "claude":
            if not anthropic_key:
                self.notify("Please enter Anthropic API key first", severity="warning", timeout=3)
                return

            self.notify("Testing Anthropic API connection...", severity="information", timeout=2)

            try:
                # Test Anthropic API
                from anthropic import Anthropic
                client = Anthropic(api_key=anthropic_key)
                # Make a minimal API call to test
                # (This will raise an error if the key is invalid)
                client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}]
                )

                status = self.query_one("#status", Static)
                status.update("Anthropic API key is valid!")
                status.add_class("success")
                status.remove_class("error")
                self.notify("Connection successful!", severity="information", timeout=3)

            except Exception as e:
                status = self.query_one("#status", Static)
                status.update(f"API test failed: {str(e)}")
                status.add_class("error")
                status.remove_class("success")
                self.notify(f"Connection failed: {str(e)}", severity="error", timeout=5)

        elif ai_provider == "openai":
            if not openai_key:
                self.notify("Please enter OpenAI API key first", severity="warning", timeout=3)
                return

            self.notify("Testing OpenAI API connection...", severity="information", timeout=2)

            try:
                # Test OpenAI API
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                # Make a minimal API call to test
                client.models.list()

                status = self.query_one("#status", Static)
                status.update("OpenAI API key is valid!")
                status.add_class("success")
                status.remove_class("error")
                self.notify("Connection successful!", severity="information", timeout=3)

            except Exception as e:
                status = self.query_one("#status", Static)
                status.update(f"API test failed: {str(e)}")
                status.add_class("error")
                status.remove_class("success")
                self.notify(f"Connection failed: {str(e)}", severity="error", timeout=5)

    def action_cancel(self) -> None:
        """Cancel and go back."""
        self.dismiss()


if __name__ == "__main__":
    """Allow running this screen standalone for testing."""
    from textual.app import App

    class TestApp(App):
        def on_mount(self):
            self.push_screen(ConfigScreen())

    app = TestApp()
    app.run()
