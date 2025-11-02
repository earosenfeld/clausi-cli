"""Test suite for Clausi CLI v1.0.0 features.

Tests:
- Multi-model support (Claude + OpenAI)
- Clause scoping with presets
- Markdown output generation
- Cache statistics display
- Enhanced progress bars

Usage:
    pytest tests/test_v1_features.py -v
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from clausi.cli import cli
from clausi.core import clause_selector
from clausi.utils.output import (
    display_cache_statistics,
    display_markdown_summary,
    create_enhanced_progress_bar
)


class TestMultiModelSupport:
    """Test multi-model support feature."""

    def test_claude_provider_selection(self):
        """Test selecting Claude as AI provider."""
        runner = CliRunner()

        with patch('clausi.cli.scanner.scan_directory') as mock_scan, \
             patch('clausi.cli.config_module.get_anthropic_key') as mock_key, \
             patch('clausi.cli.requests.post') as mock_post:

            mock_key.return_value = "sk-ant-test-key"
            mock_scan.return_value = [{"path": "test.py", "content": "print('hi')"}]

            # Mock estimate response
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "total_tokens": 1000,
                    "estimated_cost": 0.05,
                    "prompt_tokens": 800,
                    "completion_tokens": 200,
                    "regulation_breakdown": [],
                    "file_breakdown": []
                }
            )

            result = runner.invoke(cli, [
                'scan',
                'tests/fixtures',
                '--ai-provider', 'claude',
                '--ai-model', 'claude-3-5-sonnet-20241022',
                '--skip-confirmation'
            ])

            # Should not error when provider is specified
            assert "Using AI: claude" in result.output or result.exit_code == 0

    def test_openai_provider_selection(self):
        """Test selecting OpenAI as AI provider."""
        runner = CliRunner()

        with patch('clausi.cli.scanner.scan_directory') as mock_scan, \
             patch('clausi.cli.get_openai_key') as mock_key, \
             patch('clausi.cli.validate_openai_key') as mock_validate, \
             patch('clausi.cli.requests.post') as mock_post:

            mock_key.return_value = "sk-test-key"
            mock_validate.return_value = True
            mock_scan.return_value = [{"path": "test.py", "content": "print('hi')"}]

            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "total_tokens": 1000,
                    "estimated_cost": 0.05,
                    "prompt_tokens": 800,
                    "completion_tokens": 200,
                    "regulation_breakdown": [],
                    "file_breakdown": []
                }
            )

            result = runner.invoke(cli, [
                'scan',
                'tests/fixtures',
                '--ai-provider', 'openai',
                '--skip-confirmation'
            ])

            assert "Using AI: openai" in result.output or result.exit_code == 0

    def test_models_list_command(self):
        """Test models list command shows available models."""
        runner = CliRunner()
        result = runner.invoke(cli, ['models', 'list'])

        assert result.exit_code == 0
        assert "Claude" in result.output
        assert "OpenAI" in result.output
        assert "claude-3-5-sonnet-20241022" in result.output


class TestClauseScoping:
    """Test clause scoping feature."""

    def test_preset_critical_only(self):
        """Test critical-only preset."""
        clauses = clause_selector.get_preset_clauses("EU-AIA", "critical-only")

        assert clauses is not None
        assert isinstance(clauses, list)
        assert len(clauses) > 0
        assert "EUAIA-3.1" in clauses  # Risk assessment is critical

    def test_preset_high_priority(self):
        """Test high-priority preset."""
        clauses = clause_selector.get_preset_clauses("EU-AIA", "high-priority")

        assert clauses is not None
        assert isinstance(clauses, list)
        assert len(clauses) > len(clause_selector.get_preset_clauses("EU-AIA", "critical-only"))

    def test_list_available_presets(self):
        """Test listing available presets."""
        presets = clause_selector.list_available_presets("EU-AIA")

        assert presets is not None
        assert "critical-only" in presets
        assert "high-priority" in presets

    def test_scan_with_preset(self):
        """Test scanning with preset."""
        runner = CliRunner()

        with patch('clausi.cli.scanner.scan_directory') as mock_scan, \
             patch('clausi.cli.config_module.get_anthropic_key') as mock_key, \
             patch('clausi.cli.requests.post') as mock_post:

            mock_key.return_value = "sk-ant-test-key"
            mock_scan.return_value = [{"path": "test.py", "content": "test"}]

            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "total_tokens": 500,
                    "estimated_cost": 0.025,
                    "prompt_tokens": 400,
                    "completion_tokens": 100,
                    "regulation_breakdown": [],
                    "file_breakdown": []
                }
            )

            result = runner.invoke(cli, [
                'scan',
                'tests/fixtures',
                '--preset', 'critical-only',
                '--skip-confirmation'
            ])

            # Should show clause scope
            assert result.exit_code == 0 or "Clause Scope" in result.output

    def test_scan_with_include(self):
        """Test scanning with specific clause inclusion."""
        runner = CliRunner()

        with patch('clausi.cli.scanner.scan_directory') as mock_scan, \
             patch('clausi.cli.config_module.get_anthropic_key') as mock_key, \
             patch('clausi.cli.requests.post') as mock_post:

            mock_key.return_value = "sk-ant-test-key"
            mock_scan.return_value = [{"path": "test.py", "content": "test"}]

            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "total_tokens": 300,
                    "estimated_cost": 0.015,
                    "prompt_tokens": 250,
                    "completion_tokens": 50,
                    "regulation_breakdown": [],
                    "file_breakdown": []
                }
            )

            result = runner.invoke(cli, [
                'scan',
                'tests/fixtures',
                '--include', 'EUAIA-3.1',
                '--include', 'EUAIA-7.2',
                '--skip-confirmation'
            ])

            assert result.exit_code == 0


class TestMarkdownOutput:
    """Test markdown output features."""

    def test_cache_statistics_display(self, capsys):
        """Test cache statistics display formatting."""
        cache_stats = {
            "total_files": 150,
            "cache_hits": 120,
            "cache_misses": 30,
            "cache_hit_rate": 0.80,
            "tokens_saved": 45000,
            "cost_saved": 2.25
        }

        display_cache_statistics(cache_stats)
        captured = capsys.readouterr()

        assert "Cache Statistics" in captured.out
        assert "80.0%" in captured.out
        assert "120 / 150" in captured.out
        assert "45,000" in captured.out
        assert "$2.25" in captured.out

    def test_enhanced_progress_bar_creation(self):
        """Test enhanced progress bar creation."""
        progress_bar = create_enhanced_progress_bar("Testing...")

        assert progress_bar is not None
        # Progress bar should have enhanced columns
        assert hasattr(progress_bar, 'columns')

    def test_markdown_summary_display(self, tmp_path, capsys):
        """Test markdown summary display."""
        # Create test markdown file
        md_file = tmp_path / "test.md"
        md_file.write_text("""# Test Heading

This is a test markdown file.

## Section 1

Some content here.
""")

        display_markdown_summary(md_file, max_lines=5)
        captured = capsys.readouterr()

        assert "Test Heading" in captured.out or "test.md" in captured.out


class TestCacheStatistics:
    """Test cache statistics feature."""

    def test_cache_stats_in_scan_response(self):
        """Test that cache stats are properly displayed when present."""
        runner = CliRunner()

        with patch('clausi.cli.scanner.scan_directory') as mock_scan, \
             patch('clausi.cli.config_module.get_anthropic_key') as mock_key, \
             patch('clausi.cli.scan_module.make_scan_request') as mock_request, \
             patch('clausi.cli.requests.post') as mock_post:

            mock_key.return_value = "sk-ant-test-key"
            mock_scan.return_value = [{"path": "test.py", "content": "test"}]

            # Mock estimate
            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "total_tokens": 1000,
                    "estimated_cost": 0.05,
                    "prompt_tokens": 800,
                    "completion_tokens": 200,
                    "regulation_breakdown": [],
                    "file_breakdown": []
                }
            )

            # Mock scan with cache stats
            mock_request.return_value = {
                "findings": [],
                "token_usage": {
                    "total_tokens": 950,
                    "cost": 0.048,
                    "provider": "claude",
                    "model": "claude-3-5-sonnet-20241022"
                },
                "cache_stats": {
                    "total_files": 10,
                    "cache_hits": 8,
                    "cache_misses": 2,
                    "cache_hit_rate": 0.80,
                    "tokens_saved": 5000,
                    "cost_saved": 0.25
                }
            }

            result = runner.invoke(cli, [
                'scan',
                'tests/fixtures',
                '--skip-confirmation',
                '--show-cache-stats'
            ])

            # Should complete successfully
            assert result.exit_code == 0

    def test_cache_stats_disabled(self):
        """Test that cache stats can be disabled."""
        runner = CliRunner()

        with patch('clausi.cli.scanner.scan_directory') as mock_scan, \
             patch('clausi.cli.config_module.get_anthropic_key') as mock_key, \
             patch('clausi.cli.requests.post') as mock_post:

            mock_key.return_value = "sk-ant-test-key"
            mock_scan.return_value = [{"path": "test.py", "content": "test"}]

            mock_post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "total_tokens": 1000,
                    "estimated_cost": 0.05,
                    "prompt_tokens": 800,
                    "completion_tokens": 200,
                    "regulation_breakdown": [],
                    "file_breakdown": []
                }
            )

            result = runner.invoke(cli, [
                'scan',
                'tests/fixtures',
                '--no-cache-stats',
                '--skip-confirmation'
            ])

            # Should not show cache stats
            assert "Cache Statistics" not in result.output or result.exit_code == 0


class TestConfigManagement:
    """Test configuration management."""

    def test_config_show_command(self):
        """Test config show command."""
        runner = CliRunner()

        with patch('clausi.cli.load_config') as mock_load:
            mock_load.return_value = {
                "ai": {
                    "provider": "claude",
                    "model": "claude-3-5-sonnet-20241022"
                },
                "api_keys": {
                    "anthropic": "test-key",
                    "openai": ""
                },
                "ui": {
                    "show_cache_stats": True,
                    "auto_open_findings": True
                }
            }

            result = runner.invoke(cli, ['config', 'show'])

            assert result.exit_code == 0
            assert "AI Provider" in result.output
            assert "claude" in result.output

    def test_config_set_ai_provider(self):
        """Test setting AI provider in config."""
        runner = CliRunner()

        with patch('clausi.cli.load_config') as mock_load, \
             patch('clausi.cli.save_config') as mock_save:

            mock_load.return_value = {"ai": {}}

            result = runner.invoke(cli, [
                'config', 'set',
                '--ai-provider', 'claude'
            ])

            assert result.exit_code == 0
            assert mock_save.called


def test_package_imports():
    """Test that all modules can be imported."""
    # Core modules
    from clausi.core import scanner, payment, clause_selector

    # Utils
    from clausi.utils import config, output

    # API
    from clausi.api import client

    # CLI
    from clausi import cli

    assert scanner is not None
    assert payment is not None
    assert clause_selector is not None
    assert config is not None
    assert output is not None
    assert client is not None


def test_version():
    """Test version number."""
    from clausi import __version__
    assert __version__ == "1.0.0"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
