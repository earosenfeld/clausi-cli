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

import json
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
    provider.model = "claude-opus-5"
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
        assert "claude-opus-5" in result.output


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
                    "model": "claude-opus-5"
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


class TestLocalAgentProviders:
    """Scanning through a locally installed Claude Code / Codex CLI."""

    def test_prompt_goes_on_stdin_not_argv(self):
        """Prompts embed whole source files.

        Windows caps a command line near 32KB, so a large file passed as an
        argument would fail; keeping it on stdin also means no shell ever
        parses user code.
        """
        from clausi.core.ai_provider import ClaudeCodeProvider

        provider = ClaudeCodeProvider()
        big_code = "x = 1\n" * 20000
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["input"] = kwargs.get("input")
            return MagicMock(returncode=0, stdout='{"findings": []}', stderr="")

        with patch("clausi.core.ai_provider.shutil.which", return_value="/usr/bin/claude"), \
             patch("clausi.core.ai_provider.subprocess.run", side_effect=fake_run):
            provider.analyze_code("EU-AIA", [], "big.py", big_code)

        assert big_code in captured["input"], "prompt was not sent on stdin"
        assert not any(big_code in str(part) for part in captured["cmd"]), \
            "source code leaked onto the command line"

    def test_uses_resolved_path_for_windows_cmd_shims(self):
        """On Windows these CLIs are .CMD shims that a bare name cannot exec."""
        from clausi.core.ai_provider import ClaudeCodeProvider

        resolved = r"C:\Users\x\AppData\Roaming\npm\claude.CMD"
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return MagicMock(returncode=0, stdout='{"findings": []}', stderr="")

        with patch("clausi.core.ai_provider.shutil.which", return_value=resolved), \
             patch("clausi.core.ai_provider.subprocess.run", side_effect=fake_run):
            ClaudeCodeProvider().analyze_code("EU-AIA", [], "f.py", "code")

        assert captured["cmd"][0] == resolved

    def test_missing_cli_gives_install_guidance(self):
        from clausi.core.ai_provider import AIProviderError, CodexProvider

        with patch("clausi.core.ai_provider.shutil.which", return_value=None):
            with pytest.raises(AIProviderError) as exc:
                CodexProvider().analyze_code("GDPR", [], "f.py", "code")

        assert "not found" in str(exc.value).lower()

    def test_nonzero_exit_is_an_error_not_an_empty_result(self):
        """A crashed CLI must never look like a clean scan."""
        from clausi.core.ai_provider import AIProviderError, ClaudeCodeProvider

        with patch("clausi.core.ai_provider.shutil.which", return_value="/usr/bin/claude"), \
             patch("clausi.core.ai_provider.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="", stderr="not logged in")):
            with pytest.raises(AIProviderError) as exc:
                ClaudeCodeProvider().analyze_code("EU-AIA", [], "f.py", "code")

        assert "not logged in" in str(exc.value)

    def test_local_agents_report_zero_cost(self):
        from clausi.core.ai_provider import ClaudeCodeProvider

        assert ClaudeCodeProvider().estimate_cost(10_000, 5_000) == 0.0


class TestShippedRegressions:
    """Bugs that shipped in 1.0.x and must not come back."""

    def test_claude_call_sends_no_sampling_params(self):
        """The Anthropic SDK removed temperature/top_p/top_k from messages.create.

        Passing them raised TypeError on SDK 1.x, so every file failed to
        analyze while the CLI still reported a clean scan.
        """
        from clausi.core.ai_provider import ClaudeProvider

        provider = ClaudeProvider.__new__(ClaudeProvider)
        provider.model = "claude-opus-5"
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

    @pytest.mark.parametrize("wrapper,label", [
        ("{body}", "bare json"),
        ("```json\n{body}\n```", "fenced with language tag"),
        ("```\n{body}\n```", "fenced without tag"),
        ("Here is the analysis:\n\n{body}\n\nLet me know if you need more.", "prose-wrapped"),
    ])
    def test_claude_response_parses_into_findings(self, wrapper, label):
        """Claude has no json_object mode, so it wraps JSON in fences or prose.

        OpenAI is called with response_format=json_object and always returns
        bare JSON, so the OpenAI path never exercised this. Parsing Claude's
        text directly turned every wrapped response into an analysis failure.
        """
        from clausi.core.ai_provider import ClaudeProvider

        body = json.dumps({"findings": [{
            "clause_id": "Article-14",
            "severity": "critical",
            "explanation": "No human oversight mechanism.",
            "line_start": 10,
            "line_end": 15,
        }]})

        provider = ClaudeProvider.__new__(ClaudeProvider)
        provider.model = "claude-opus-5"
        provider._client = MagicMock(messages=MagicMock(create=MagicMock(
            return_value=MagicMock(
                content=[MagicMock(text=wrapper.format(body=body))],
                usage=MagicMock(input_tokens=10, output_tokens=20),
            )
        )))

        result = provider.analyze_code("EU-AIA", [], "model_service.py", "code")

        assert len(result["findings"]) == 1, f"failed for {label}"
        assert result["findings"][0]["clause_id"] == "Article-14"
        assert result["findings"][0]["severity"] == "critical"

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

    def test_default_output_dir_resolves_against_scanned_project(self, tmp_path):
        """The default report location belongs to the project scanned.

        Scanning a repo from elsewhere used to dump reports into whatever
        directory the user happened to be standing in.
        """
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

    def test_scan_does_not_launch_an_editor_by_default(self, tmp_path):
        """Opening an editor on every scan hijacks the screen and breaks CI.

        There was previously an --open-findings opt-in but no way to opt out,
        and the config defaulted to on.
        """
        project = tmp_path / "proj"
        project.mkdir()
        (project / "a.py").write_text("print('x')")

        runner = CliRunner()
        with patch("clausi.cli.get_ai_provider", return_value=_fake_provider()), \
             patch("clausi.utils.config.get_anthropic_key", return_value="sk-ant-test-key"), \
             patch("clausi.utils.output.open_in_editor") as opener:
            result = runner.invoke(cli, [
                "scan", str(project), "-r", "EU-AIA", "--claude",
                "--skip-confirmation", "-o", str(tmp_path / "out"),
            ])

        assert result.exit_code == 0, result.output
        opener.assert_not_called()

    def test_no_open_findings_overrides_config(self, tmp_path):
        """--no-open-findings must win even when the config enables opening."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / "a.py").write_text("print('x')")

        runner = CliRunner()
        with patch("clausi.cli.get_ai_provider", return_value=_fake_provider()), \
             patch("clausi.utils.config.get_anthropic_key", return_value="sk-ant-test-key"), \
             patch("clausi.cli.load_config", return_value={"ui": {"auto_open_findings": True}}), \
             patch("clausi.utils.output.open_in_editor") as opener:
            result = runner.invoke(cli, [
                "scan", str(project), "-r", "EU-AIA", "--claude", "--skip-confirmation",
                "--no-open-findings", "-o", str(tmp_path / "out2"),
            ])

        assert result.exit_code == 0, result.output
        opener.assert_not_called()

    def test_explicit_output_flag_is_relative_to_cwd(self, tmp_path):
        """-o is a path the user typed, so it anchors where they are standing.

        Anchoring it to the scanned project instead buried reports inside the
        tree being audited, which is not what anyone types `-o out` expecting.
        """
        project = tmp_path / "someproject"
        project.mkdir()
        (project / "a.py").write_text("print('x')")
        elsewhere = tmp_path / "cwd"
        elsewhere.mkdir()

        runner = CliRunner()
        cwd = os.getcwd()
        os.chdir(elsewhere)
        try:
            with patch("clausi.cli.get_ai_provider", return_value=_fake_provider()), \
                 patch("clausi.utils.config.get_anthropic_key", return_value="sk-ant-test-key"):
                result = runner.invoke(cli, [
                    "scan", str(project), "-r", "EU-AIA", "--claude",
                    "--skip-confirmation", "-o", "myreports",
                ])
        finally:
            os.chdir(cwd)

        assert result.exit_code == 0, result.output
        assert (elsewhere / "myreports").exists(), "explicit -o did not land in cwd"
        assert not (project / "myreports").exists(), "explicit -o leaked into scanned project"


class TestDocsGeneration:
    """`clausi docs generate` - verified end to end for the first time 2026-08-23."""

    def test_whole_document_markdown_fence_is_unwrapped(self):
        from clausi.core.docs_generator import strip_markdown_fence

        wrapped = "```markdown\n# Title\n\nSome prose.\n```"
        assert strip_markdown_fence(wrapped) == "# Title\n\nSome prose.\n"

    def test_document_opening_with_a_code_sample_is_left_alone(self):
        from clausi.core.docs_generator import strip_markdown_fence

        # Starts and ends with a fence, but they are two separate blocks.
        doc = "```bash\nclausi scan .\n```\n\nProse.\n\n```python\nx = 1\n```"
        assert strip_markdown_fence(doc) == doc

        # A real code block, not a document wrapper.
        py = "```python\nx = 1\n```"
        assert strip_markdown_fence(py) == py

    def test_docs_generation_honors_clausiignore(self, tmp_path):
        """A path excluded from scanning must not be shipped to the AI provider here either."""
        from clausi.core.docs_generator import DocsGenerator

        (tmp_path / "keep.py").write_text("def f():\n    return 1\n")
        secret = tmp_path / "secret"
        secret.mkdir()
        (secret / "keys.py").write_text("TOKEN = 'sk-live-do-not-send'\n")
        (tmp_path / ".clausiignore").write_text("secret/\n")

        generator = DocsGenerator(str(tmp_path), str(tmp_path / "out"))
        generator.scan_project()

        paths = {f["path"].replace("\\", "/") for f in generator.files}
        assert "keep.py" in paths
        assert not any(p.startswith("secret/") for p in paths), (
            f"docs generate leaked a .clausiignore'd path: {paths}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


class TestModelPricing:
    """The default model must be priced, or cost estimates silently under-quote."""

    def test_default_claude_model_has_a_pricing_entry(self):
        from clausi.core.ai_provider import ClaudeProvider
        assert ClaudeProvider.DEFAULT_MODEL in ClaudeProvider.PRICING

    def test_default_openai_model_has_a_pricing_entry(self):
        from clausi.core.ai_provider import OpenAIProvider
        assert OpenAIProvider.DEFAULT_MODEL in OpenAIProvider.PRICING

    def test_configured_default_model_matches_provider_default(self):
        """config.DEFAULT_MODELS and the provider classes must not drift apart."""
        from clausi.core.ai_provider import ClaudeProvider, OpenAIProvider
        from clausi.utils.config import DEFAULT_MODELS
        assert DEFAULT_MODELS["claude"] == ClaudeProvider.DEFAULT_MODEL
        assert DEFAULT_MODELS["openai"] == OpenAIProvider.DEFAULT_MODEL
