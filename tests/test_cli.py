"""Tests for the Clausi CLI (local, BYOK)."""

from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from clausi.cli import cli
from clausi.core.scanner import scan_directory


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


def test_scan_directory(tmp_path):
    """Test directory scanning functionality."""
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()

    py_file = test_dir / "test.py"
    py_file.write_text("print('Hello, World!')")

    txt_file = test_dir / "test.txt"
    txt_file.write_text("This is a text file")

    files = scan_directory(str(test_dir))

    assert len(files) == 1  # Only the Python file should be included
    assert files[0]["path"] == "test.py"
    assert files[0]["type"] == "py"
    assert files[0]["content"] == "print('Hello, World!')"


def _fake_provider(findings):
    provider = MagicMock()
    provider.name = "claude"
    provider.model = "claude-3-5-sonnet-20241022"
    provider.analyze_code.return_value = {
        "findings": findings,
        "prompt_tokens": 100,
        "completion_tokens": 50,
    }
    provider.estimate_cost.return_value = 0.01
    return provider


def test_scan_command_local_flow(runner, tmp_path):
    """A scan runs entirely locally: no HTTP calls, findings come from the mocked AI provider."""
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    (test_dir / "test.py").write_text("print('Hello, World!')")

    findings = [{
        "clause_id": "Article-9",
        "clause_text": "Risk management",
        "violation": "No risk assessment found",
        "severity": "low",
        "confidence": 0.6,
        "line_start": 1,
        "line_end": 1,
        "code_snippet": "print('Hello, World!')",
        "recommendation": "Add a risk assessment",
        "auto_fixable": False,
        "evidence": "Missing risk management code",
    }]

    reports_dir = tmp_path / "reports"
    with patch("clausi.cli.get_ai_provider", return_value=_fake_provider(findings)), \
         patch("clausi.utils.config.get_anthropic_key", return_value="sk-ant-test-key"):
        result = runner.invoke(cli, [
            "scan", str(test_dir), "-r", "EU-AIA", "--claude", "--skip-confirmation",
            "-o", str(reports_dir),
        ])

    assert result.exit_code == 0, result.output
    assert "Article-9" in result.output
    assert (reports_dir / "findings.md").exists()
    assert (reports_dir / "report.pdf").exists()
    assert (reports_dir / "report.pdf").stat().st_size > 5_000


def test_scan_needs_a_key_or_a_local_agent(runner, tmp_path):
    """With no key AND no agent CLI installed, scan exits with guidance.

    It must never fall through to a hosted backend - there isn't one.
    """
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    (test_dir / "test.py").write_text("print('hi')")

    with patch("clausi.utils.config.get_anthropic_key", return_value=None), \
         patch("clausi.utils.config.get_openai_key", return_value=None), \
         patch("clausi.core.ai_provider.shutil.which", return_value=None):
        result = runner.invoke(cli, ["scan", str(test_dir), "-r", "EU-AIA"])

    assert result.exit_code != 0
    assert "No AI backend found" in result.output
    # Both routes out of the error should be offered.
    assert "Claude Code" in result.output
    assert "ANTHROPIC_API_KEY" in result.output


def test_scan_falls_back_to_local_agent_when_no_key(runner, tmp_path):
    """An installed, signed-in agent CLI means no API key is needed at all."""
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    (test_dir / "test.py").write_text("print('hi')")

    with patch("clausi.utils.config.get_anthropic_key", return_value=None), \
         patch("clausi.utils.config.get_openai_key", return_value=None), \
         patch("clausi.core.ai_provider.shutil.which", return_value="/usr/bin/claude"), \
         patch("clausi.core.ai_provider.subprocess.run",
               return_value=MagicMock(returncode=0, stdout='{"findings": []}', stderr="")):
        result = runner.invoke(cli, [
            "scan", str(test_dir), "-r", "EU-AIA", "--skip-confirmation",
        ])

    assert result.exit_code == 0, result.output
    assert "no API key needed" in result.output


def _fake_docs_provider():
    provider = MagicMock()
    provider.name = "claude"
    provider.model = "claude-3-5-sonnet-20241022"
    provider.generate_text.return_value = {
        "text": "# Doc\n\nGenerated content.",
        "prompt_tokens": 500,
        "completion_tokens": 200,
    }
    provider.estimate_cost.return_value = 0.05
    return provider


def test_docs_generate_local_flow(runner, tmp_path):
    """docs generate runs entirely locally and writes all four doc files."""
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    (test_dir / "app.py").write_text("def main():\n    pass\n")

    out_dir = tmp_path / "docs_out"
    provider = _fake_docs_provider()
    with patch("clausi.cli.get_ai_provider", return_value=provider), \
         patch("clausi.utils.config.get_anthropic_key", return_value="sk-ant-test-key"):
        result = runner.invoke(cli, [
            "docs", "generate", str(test_dir), "--claude", "--skip-confirmation",
            "-o", str(out_dir),
        ])

    assert result.exit_code == 0, result.output
    assert provider.generate_text.call_count == 4
    for filename in ("index.md", "architecture.md", "components.md", "security.md"):
        assert (out_dir / filename).exists()
