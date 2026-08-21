"""Test suite for Clausi CLI local/BYOK features.

Tests:
- Multi-model support (Claude + OpenAI) via BYOK
- Clause scoping with presets
- Local cache
- Cache statistics display
- Enhanced progress bars

Usage:
    pytest tests/test_v1_features.py -v
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from clausi.cli import cli
from clausi.core import clause_selector
from clausi.core.cache import LocalCache
from clausi.utils.regulations import get_regulation_clauses
from clausi.utils.output import (
    display_cache_statistics,
    display_markdown_summary,
    create_enhanced_progress_bar,
)


def _fake_provider(findings=None):
    provider = MagicMock()
    provider.name = "claude"
    provider.model = "claude-3-5-sonnet-20241022"
    provider.analyze_code.return_value = {
        "findings": findings or [],
        "prompt_tokens": 100,
        "completion_tokens": 50,
    }
    provider.estimate_cost.return_value = 0.01
    return provider


class TestMultiModelSupport:
    """Test multi-model support feature."""

    def test_claude_provider_selection(self, tmp_path):
        runner = CliRunner()
        test_dir = tmp_path / "proj"
        test_dir.mkdir()
        (test_dir / "test.py").write_text("print('hi')")

        with patch("clausi.cli.get_ai_provider", return_value=_fake_provider()) as mock_get_provider, \
             patch("clausi.utils.config.get_anthropic_key", return_value="sk-ant-test-key"):
            result = runner.invoke(cli, [
                "scan", str(test_dir), "-r", "EU-AIA", "--claude", "--skip-confirmation",
            ])

        assert result.exit_code == 0, result.output
        assert mock_get_provider.call_args[0][0] == "claude"

    def test_openai_provider_selection(self, tmp_path):
        runner = CliRunner()
        test_dir = tmp_path / "proj"
        test_dir.mkdir()
        (test_dir / "test.py").write_text("print('hi')")

        with patch("clausi.cli.get_ai_provider", return_value=_fake_provider()) as mock_get_provider, \
             patch("clausi.cli.validate_openai_key", return_value=True), \
             patch("clausi.utils.config.get_openai_key", return_value="sk-test-key"):
            result = runner.invoke(cli, [
                "scan", str(test_dir), "-r", "EU-AIA", "--openai", "--skip-confirmation",
            ])

        assert result.exit_code == 0, result.output
        assert mock_get_provider.call_args[0][0] == "openai"

    def test_models_list_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["models", "list"])

        assert result.exit_code == 0
        assert "Claude" in result.output
        assert "OpenAI" in result.output
        assert "claude-3-5-sonnet-20241022" in result.output


class TestClauseScoping:
    """Test clause scoping feature."""

    def test_preset_critical_only(self):
        clauses = clause_selector.get_preset_clauses("EU-AIA", "critical-only")

        assert clauses is not None
        assert isinstance(clauses, list)
        assert len(clauses) > 0
        assert "Article-9" in clauses

    def test_preset_high_priority(self):
        clauses = clause_selector.get_preset_clauses("EU-AIA", "high-priority")

        assert clauses is not None
        assert len(clauses) > len(clause_selector.get_preset_clauses("EU-AIA", "critical-only"))

    def test_list_available_presets(self):
        presets = clause_selector.list_available_presets("EU-AIA")

        assert "critical-only" in presets
        assert "high-priority" in presets

    def test_every_preset_id_resolves_to_a_real_clause(self):
        """Every preset clause ID must exist in its regulation's YAML.

        Clause matching is exact string equality, so a stale or mistyped ID
        silently scans zero clauses and reports a clean result. That shipped
        broken in v1.0.1 across all five regulations, and no other test caught
        it because the rest only assert presets are non-empty.
        """
        broken = []
        for reg_code, presets in clause_selector.CLAUSE_PRESETS.items():
            regulation = get_regulation_clauses(reg_code)
            assert regulation is not None, f"preset regulation {reg_code} has no YAML"

            real_ids = {str(c["id"]) for c in regulation["clauses"] if c.get("id")}
            for preset_name, clause_ids in presets.items():
                missing = [cid for cid in clause_ids if cid not in real_ids]
                if missing:
                    broken.append(f"{reg_code}/{preset_name}: {missing}")

        assert not broken, "preset IDs not present in regulation YAML: " + "; ".join(broken)

    def test_scan_with_preset(self, tmp_path):
        runner = CliRunner()
        test_dir = tmp_path / "proj"
        test_dir.mkdir()
        (test_dir / "test.py").write_text("test")

        with patch("clausi.cli.get_ai_provider", return_value=_fake_provider()), \
             patch("clausi.utils.config.get_anthropic_key", return_value="sk-ant-test-key"):
            result = runner.invoke(cli, [
                "scan", str(test_dir), "-r", "EU-AIA", "--preset", "critical-only", "--skip-confirmation",
            ])

        assert result.exit_code == 0, result.output

    def test_scan_with_include(self, tmp_path):
        runner = CliRunner()
        test_dir = tmp_path / "proj"
        test_dir.mkdir()
        (test_dir / "test.py").write_text("test")

        with patch("clausi.cli.get_ai_provider", return_value=_fake_provider()), \
             patch("clausi.utils.config.get_anthropic_key", return_value="sk-ant-test-key"):
            result = runner.invoke(cli, [
                "scan", str(test_dir), "-r", "EU-AIA",
                "--include", "EUAIA-3.1", "--include", "EUAIA-7.2", "--skip-confirmation",
            ])

        assert result.exit_code == 0, result.output


class TestLocalCache:
    """Test the on-disk scan cache."""

    def test_cache_key_deterministic(self, tmp_path):
        cache = LocalCache(cache_dir=tmp_path)
        key1 = cache.generate_cache_key("content", "EU-AIA", provider="claude", model="m1")
        key2 = cache.generate_cache_key("content", "EU-AIA", provider="claude", model="m1")
        assert key1 == key2

    def test_cache_key_changes_with_content(self, tmp_path):
        cache = LocalCache(cache_dir=tmp_path)
        key1 = cache.generate_cache_key("content-a", "EU-AIA", provider="claude", model="m1")
        key2 = cache.generate_cache_key("content-b", "EU-AIA", provider="claude", model="m1")
        assert key1 != key2

    def test_cache_hit_after_set(self, tmp_path):
        cache = LocalCache(cache_dir=tmp_path)
        key = cache.generate_cache_key("content", "EU-AIA", provider="claude", model="m1")

        assert cache.get(key) is None  # miss
        cache.set(key, {"findings": []})
        result = cache.get(key)  # hit

        assert result is not None
        assert result["cached"] is True
        assert cache.stats()["cache_hits"] == 1
        assert cache.stats()["cache_misses"] == 1

    def test_cache_disabled_never_hits(self, tmp_path):
        cache = LocalCache(enabled=False, cache_dir=tmp_path)
        key = cache.generate_cache_key("content", "EU-AIA", provider="claude", model="m1")
        cache.set(key, {"findings": []})
        assert cache.get(key) is None


class TestMarkdownOutput:
    """Test markdown output features."""

    def test_cache_statistics_display(self, capsys):
        cache_stats = {
            "total_files": 150,
            "cache_hits": 120,
            "cache_misses": 30,
            "cache_hit_rate": 0.80,
            "cost_saved": 2.25,
        }

        display_cache_statistics(cache_stats)
        captured = capsys.readouterr()

        assert "Cache Statistics" in captured.out
        assert "80.0%" in captured.out
        assert "120 / 150" in captured.out
        assert "$2.25" in captured.out

    def test_enhanced_progress_bar_creation(self):
        progress_bar = create_enhanced_progress_bar("Testing...")
        assert progress_bar is not None
        assert hasattr(progress_bar, 'columns')

    def test_markdown_summary_display(self, tmp_path, capsys):
        md_file = tmp_path / "test.md"
        md_file.write_text("""# Test Heading

This is a test markdown file.

## Section 1

Some content here.
""")

        display_markdown_summary(md_file, max_lines=5)
        captured = capsys.readouterr()

        assert "Test Heading" in captured.out or "test.md" in captured.out


class TestConfigManagement:
    """Test configuration management."""

    def test_config_show_command(self):
        runner = CliRunner()

        with patch('clausi.cli.config_module.load_config') as mock_load:
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
        runner = CliRunner()

        with patch('clausi.cli.load_config') as mock_load, \
             patch('clausi.cli.config_module.save_config') as mock_save:

            mock_load.return_value = {"ai": {}}

            result = runner.invoke(cli, [
                'config', 'set',
                '--ai-provider', 'claude'
            ])

            assert result.exit_code == 0
            assert mock_save.called


def test_package_imports():
    """Test that all modules can be imported."""
    from clausi.core import scanner, clause_selector, ai_provider, cache, compliance_analyzer, markdown_report
    from clausi.utils import config, output, regulations
    from clausi import cli

    assert scanner is not None
    assert clause_selector is not None
    assert ai_provider is not None
    assert cache is not None
    assert compliance_analyzer is not None
    assert markdown_report is not None
    assert config is not None
    assert output is not None
    assert regulations is not None
    assert cli is not None


def test_version():
    """Test version number."""
    from clausi import __version__
    assert __version__


class TestShippedRegressions:
    """Bugs that shipped in 1.0.x and must not come back."""

    def test_claude_call_sends_no_sampling_params(self):
        """The Anthropic SDK removed temperature/top_p/top_k from messages.create.

        Passing them raised TypeError on SDK 1.x, so every file failed to
        analyze while the CLI still reported a clean scan.
        """
        from clausi.core.ai_provider import ClaudeProvider

        provider = ClaudeProvider.__new__(ClaudeProvider)
        provider.model = "claude-3-5-sonnet-20241022"
        captured = {}

        class _FakeMessages:
            def create(self, **kwargs):
                captured.update(kwargs)
                return MagicMock(
                    content=[MagicMock(text='{"findings": []}')],
                    usage=MagicMock(input_tokens=1, output_tokens=1),
                )

        provider._client = MagicMock(messages=_FakeMessages())
        provider.analyze_code("EU-AIA", [], "f.py", "code")

        for banned in ("temperature", "top_p", "top_k"):
            assert banned not in captured, f"{banned} was sent to messages.create"

    def test_openai_never_gets_a_claude_model(self, tmp_path, monkeypatch):
        """A shared ai.model config key must not leak across providers.

        Configuring Claude and then running --openai sent a Claude model name
        to OpenAI, which 404s with a confusing model_not_found.
        """
        from clausi.utils import config as config_module

        monkeypatch.setattr(
            config_module, "load_config",
            lambda: {"ai": {"model": "claude-3-5-sonnet-20241022"}},
        )
        assert config_module.get_ai_model("claude") == "claude-3-5-sonnet-20241022"
        assert not config_module.get_ai_model("openai").startswith("claude")

    def test_relative_output_dir_resolves_against_scanned_project(self, tmp_path):
        """Reports belong to the project scanned, not the current directory."""
        from clausi.utils.output import ensure_output_dir

        project = tmp_path / "someproject"
        project.mkdir()
        elsewhere = tmp_path / "cwd"
        elsewhere.mkdir()

        cwd = os.getcwd()
        os.chdir(elsewhere)
        try:
            out = ensure_output_dir(str(project), "clausi/reports")
        finally:
            os.chdir(cwd)

        assert project.resolve() in out.resolve().parents
        assert elsewhere.resolve() not in out.resolve().parents


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
