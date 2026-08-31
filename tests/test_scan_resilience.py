"""A paid scan must survive bad provider output, transient errors, and stale caches.

Every test here corresponds to a way a completed, already-billed scan could
previously be lost or silently misreported.
"""

import contextlib
import os
import time

import pytest

from clausi.core import compliance_analyzer
from clausi.core.ai_provider import (
    AIProviderError,
    analysis_fingerprint,
    call_with_retries,
    is_retryable,
)
from clausi.core import scanner
from clausi.core.cache import DEFAULT_TTL_SECONDS, LocalCache
from clausi.core.compliance_analyzer import normalize_severity, run_scan
from clausi.core.markdown_report import MarkdownGenerator
from clausi.core.pdf_report import PDFReportGenerator


class _NullCache:
    """A cache that never stores anything, so tests exercise the live path."""

    enabled = False

    def generate_cache_key(self, *args, **kwargs):
        return "test-key"

    def get(self, key):
        return None

    def peek(self, key):
        return None

    def key_lock(self, key):
        return contextlib.nullcontext()

    def set(self, key, result):
        pass

    def stats(self):
        return {}


class _StubProvider:
    name = "stub"
    model = "stub-model"

    def __init__(self, findings=None, raises=None):
        self._findings = findings or []
        self._raises = raises

    def analyze_code(self, regulation, clauses, file_path, code):
        if self._raises:
            raise self._raises
        return {"findings": self._findings, "prompt_tokens": 10, "completion_tokens": 5}

    def estimate_cost(self, input_tokens, output_tokens):
        return 0.0


FILES = [{"path": "a.py", "content": "print('x')"}]


# --- severity normalization ------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Medium", "medium"),
    ("HIGH", "high"),
    ("  Critical  ", "critical"),
    ("warning", "medium"),
    ("moderate", "medium"),
    ("blocker", "critical"),
    ("minor", "low"),
    ("informational", "info"),
    ("nonsense", "medium"),
    (None, "medium"),
    (3, "medium"),
])
def test_normalize_severity_maps_every_input_onto_the_ladder(raw, expected):
    assert normalize_severity(raw) == expected


def test_capitalized_severity_does_not_destroy_the_scan():
    """Regression: severity_order.index("Medium") raised ValueError during
    post-processing, discarding every finding in an already-billed scan."""
    provider = _StubProvider([{"clause_id": "Article-9", "severity": "Medium", "confidence": 0.9}])
    result = run_scan(FILES, "EU AI Act", [], provider, _NullCache(), min_severity="low")

    assert len(result["findings"]) == 1
    assert result["findings"][0]["severity"] == "medium"
    assert result["findings"][0]["severity_reported"] == "Medium"


def test_min_severity_filter_uses_normalized_values():
    provider = _StubProvider([
        {"clause_id": "Article-9", "severity": "LOW"},
        {"clause_id": "Article-12", "severity": "Critical"},
    ])
    result = run_scan(FILES, "EU AI Act", [], provider, _NullCache(), min_severity="high")

    assert [f["severity"] for f in result["findings"]] == ["critical"]


def test_unparseable_confidence_does_not_raise():
    provider = _StubProvider([{"clause_id": "Article-9", "confidence": "very sure"}])
    result = run_scan(FILES, "EU AI Act", [], provider, _NullCache())

    assert result["findings"][0]["confidence"] == 0.5


# --- worker isolation ------------------------------------------------------

def test_unexpected_worker_error_costs_one_file_not_the_run():
    files = [{"path": "a.py", "content": "a"}, {"path": "b.py", "content": "b"}]

    class _Flaky(_StubProvider):
        def analyze_code(self, regulation, clauses, file_path, code):
            if file_path == "a.py":
                raise KeyError("some unanticipated shape")
            return {"findings": [{"clause_id": "Article-9", "severity": "high"}],
                    "prompt_tokens": 1, "completion_tokens": 1}

    result = run_scan(files, "EU AI Act", [], _Flaky(), _NullCache())

    assert len(result["findings"]) == 1
    assert any("a.py" in e and "KeyError" in e for e in result["errors"])


def test_provider_error_is_reported_per_file():
    result = run_scan(
        FILES, "EU AI Act", [], _StubProvider(raises=AIProviderError("429 rate limited")),
        _NullCache(),
    )

    assert result["findings"] == []
    assert result["errors"] and "a.py" in result["errors"][0]


# --- retries ---------------------------------------------------------------

class _RateLimited(Exception):
    status_code = 429


class _Fatal(Exception):
    status_code = 400


def test_retries_transient_failures_then_succeeds():
    attempts = []

    def operation():
        attempts.append(1)
        if len(attempts) < 3:
            raise _RateLimited("slow down")
        return "ok"

    assert call_with_retries(operation, "test", sleep=lambda _: None) == "ok"
    assert len(attempts) == 3


def test_does_not_retry_a_client_error():
    attempts = []

    def operation():
        attempts.append(1)
        raise _Fatal("bad request")

    with pytest.raises(AIProviderError):
        call_with_retries(operation, "test", sleep=lambda _: None)
    assert len(attempts) == 1


def test_gives_up_after_max_attempts():
    attempts = []

    def operation():
        attempts.append(1)
        raise _RateLimited("still limited")

    with pytest.raises(AIProviderError):
        call_with_retries(operation, "test", sleep=lambda _: None)
    assert len(attempts) == compliance_analyzer_max_attempts()


def compliance_analyzer_max_attempts():
    from clausi.core.ai_provider import MAX_ATTEMPTS
    return MAX_ATTEMPTS


def test_recognizes_retryable_errors_by_class_name():
    class RateLimitError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    assert is_retryable(RateLimitError("x"))
    assert is_retryable(APIConnectionError("x"))
    assert not is_retryable(ValueError("x"))


# --- cache invalidation ----------------------------------------------------

def test_cache_key_changes_when_clause_text_changes(tmp_path):
    """A regulation pack that revises a clause must not serve the old finding."""
    cache = LocalCache(cache_dir=tmp_path)
    old = [{"id": "Article-9", "title": "Risk management", "description": "Original wording."}]
    new = [{"id": "Article-9", "title": "Risk management", "description": "Revised wording."}]

    key_old = cache.generate_cache_key(
        "code", "EU AI Act", provider="claude", model="m",
        analysis_fingerprint=analysis_fingerprint(old))
    key_new = cache.generate_cache_key(
        "code", "EU AI Act", provider="claude", model="m",
        analysis_fingerprint=analysis_fingerprint(new))

    assert key_old != key_new


def test_cache_key_is_stable_for_identical_clauses(tmp_path):
    cache = LocalCache(cache_dir=tmp_path)
    clauses = [{"id": "Article-9", "title": "Risk management"}]
    args = dict(provider="claude", model="m", analysis_fingerprint=analysis_fingerprint(clauses))

    assert (cache.generate_cache_key("code", "EU AI Act", **args)
            == cache.generate_cache_key("code", "EU AI Act", **args))


def test_fingerprint_ignores_clause_ordering():
    a = [{"id": "Article-9"}, {"id": "Article-12"}]
    assert analysis_fingerprint(a) == analysis_fingerprint(list(reversed(a)))


# --- coverage disclosure ---------------------------------------------------

AUDIT_META_WITH_GAPS = {
    "timestamp": "2026-08-31T12:00:00",
    "provider": "claude",
    "model": "claude-opus-5",
    "failed_files": ["src/router.py: 429 rate limited"],
    "truncated_files": [{"path": "src/big.py", "original_chars": 18251, "analyzed_chars": 8000}],
    "coverage": {
        "skipped_unsupported_extension": {".md": 4},
        "skipped_excluded_directories": {"node_modules": 1},
        "unreadable": [{"path": "src/bad.py", "reason": "decode error"}],
    },
    "ignored_files": [{"path": "src/gen.py", "rule": ".clausiignore"}],
}


def test_markdown_coverage_reports_files_that_failed_analysis():
    md = MarkdownGenerator().generate_findings_md(
        findings=[], project_name="p", regulation="EU AI Act",
        audit_meta=AUDIT_META_WITH_GAPS, files_scanned=3,
    )

    assert "Coverage and Limits" in md
    assert "Failed during analysis" in md
    assert "src/router.py" in md


def test_pdf_discloses_scan_coverage(tmp_path):
    """The PDF is the deliverable an assessor reads; exclusions must appear in it."""
    block = PDFReportGenerator()._scan_coverage_block(AUDIT_META_WITH_GAPS)
    assert block, "expected a coverage section when files were skipped or failed"

    output = PDFReportGenerator().save_report(
        findings=[], project_name="p", regulation="EU AI Act",
        audit_meta=AUDIT_META_WITH_GAPS, output_dir=tmp_path, files_scanned=3,
        all_clauses=[{"id": "Article-9", "title": "Risk management"}],
    )
    assert open(output, "rb").read().startswith(b"%PDF")


def test_pdf_coverage_section_omitted_when_nothing_was_skipped():
    assert PDFReportGenerator()._scan_coverage_block({"coverage": {}}) == []


# --- local agent CLI -------------------------------------------------------

def test_local_agent_retries_a_garbled_response_once():
    """Observed live: both files of a two-file scan came back as prose, then
    succeeded unchanged on re-run. Retrying is free on a subscription plan."""
    from clausi.core.ai_provider import ClaudeCodeProvider

    provider = ClaudeCodeProvider()
    responses = iter(["I'll analyze that for you.", '{"findings": []}'])
    provider._run = lambda prompt: next(responses)

    assert provider.analyze_code("EU AI Act", [], "a.py", "code")["findings"] == []


def test_local_agent_gives_up_after_repeated_garbled_responses():
    from clausi.core.ai_provider import ClaudeCodeProvider

    provider = ClaudeCodeProvider()
    provider._run = lambda prompt: "still not JSON"

    with pytest.raises(AIProviderError, match="attempt"):
        provider.analyze_code("EU AI Act", [], "a.py", "code")


# --- cost estimate and the --max-cost ceiling ------------------------------
#
# The estimate used to count file bytes only, ignoring that every request also
# carries the full clause text - understating a real scan by more than 2x. And
# --max-cost only ever gated the estimate, so a wrong estimate meant no ceiling
# at all on what a scan could actually charge.

class _PricedProvider(_StubProvider):
    """Charges a flat amount per call, so budget arithmetic is exact."""

    def __init__(self, cost_per_call=0.10, **kwargs):
        super().__init__(**kwargs)
        self._cost_per_call = cost_per_call
        self.calls = []

    def analyze_code(self, regulation, clauses, file_path, code):
        self.calls.append(file_path)
        return super().analyze_code(regulation, clauses, file_path, code)

    def estimate_cost(self, input_tokens, output_tokens):
        return self._cost_per_call


CLAUSES = [
    {"id": "X-1", "title": "A clause", "description": "d" * 400,
     "requirements": ["r" * 200]},
]


def test_estimate_includes_prompt_overhead():
    overhead = compliance_analyzer.prompt_overhead_tokens("Reg", CLAUSES)
    assert overhead > 100

    files = [{"path": "a.py", "content": "print('x')"}]
    est = compliance_analyzer.estimate_scan(files, "Reg", CLAUSES, _StubProvider())

    assert est["prompt_overhead_tokens"] == overhead
    # The file itself is a rounding error next to the clause text.
    assert est["input_tokens"] >= overhead


def test_estimate_counts_truncated_content_only():
    """A quote must never be based on more text than the scan will send."""
    huge = "x" * (compliance_analyzer.MAX_FILE_CHARS * 10)
    est = compliance_analyzer.estimate_scan(
        [{"path": "big.py", "content": huge}], "Reg", CLAUSES, _StubProvider()
    )
    ceiling = (
        compliance_analyzer.prompt_overhead_tokens("Reg", CLAUSES)
        + compliance_analyzer.MAX_FILE_CHARS // 4
        + 100
    )
    assert est["input_tokens"] < ceiling


def test_max_cost_stops_a_running_scan():
    files = [{"path": f"f{i}.py", "content": "print('x')"} for i in range(6)]
    provider = _PricedProvider(cost_per_call=0.10)
    budget = compliance_analyzer.CostBudget(limit=0.25)

    result = run_scan(
        files=files, regulation="Reg", clauses=CLAUSES,
        provider=provider, cache=_NullCache(), budget=budget,
    )

    assert budget.stopped
    assert len(provider.calls) < len(files)
    assert budget.spent <= 0.25
    assert result["errors"]
    assert any("--max-cost" in e for e in result["errors"])


def test_no_max_cost_never_stops():
    files = [{"path": f"f{i}.py", "content": "print('x')"} for i in range(4)]
    provider = _PricedProvider(cost_per_call=100.0)
    budget = compliance_analyzer.CostBudget(limit=None)

    run_scan(files=files, regulation="Reg", clauses=CLAUSES,
             provider=provider, cache=_NullCache(), budget=budget)

    assert not budget.stopped
    assert len(provider.calls) == len(files)


def test_budget_never_refuses_a_cache_hit():
    """Cache hits cost nothing, so an exhausted budget must not block them."""

    class _HitCache(_NullCache):
        def get(self, key):
            return {"findings": []}

    provider = _PricedProvider(cost_per_call=0.10)
    budget = compliance_analyzer.CostBudget(limit=0.0)

    result = run_scan(
        files=[{"path": "a.py", "content": "print('x')"}], regulation="Reg",
        clauses=CLAUSES, provider=provider, cache=_HitCache(), budget=budget,
    )

    assert not budget.stopped
    assert provider.calls == []
    assert not result["errors"]


# --- cache eviction --------------------------------------------------------
#
# The cache only ever grew. Content hash, prompt text and pack contents are all
# in the key, so every file edit and every pack update orphans an entry that is
# unreachable but never removed.

def test_prune_removes_expired_and_over_cap_entries(tmp_path):
    cache = LocalCache(ttl=60, cache_dir=tmp_path)
    for i in range(5):
        cache.set(f"scan_{i}", {"findings": [{"pad": "x" * 500}]})

    stale = tmp_path / "scan_0.json"
    os.utime(stale, (time.time() - 3600, time.time() - 3600))

    result = cache.prune(max_bytes=2 * max(
        p.stat().st_size for p in tmp_path.glob("scan_*.json")
    ))

    assert result["expired"] == 1
    assert not stale.exists()
    assert result["evicted"] >= 1
    assert cache.size_bytes() > 0


def test_prune_is_a_no_op_when_under_the_cap(tmp_path):
    cache = LocalCache(ttl=DEFAULT_TTL_SECONDS, cache_dir=tmp_path)
    cache.set("scan_keep", {"findings": []})

    result = cache.prune(max_bytes=10 * 1024 * 1024)

    assert result == {"expired": 0, "evicted": 0, "bytes_freed": 0}
    assert (tmp_path / "scan_keep.json").exists()


# --- coverage: our own output, and clauses the model declined to judge ------

def test_scan_skips_clausi_own_output(tmp_path):
    """A repeat scan used to discover the previous run's reports and list our
    own PDF and CSV as unsupported files in every manifest after the first."""
    (tmp_path / "app.py").write_text("print('x')", encoding="utf-8")
    reports = tmp_path / "clausi" / "reports"
    reports.mkdir(parents=True)
    (reports / "report.pdf").write_text("pdf", encoding="utf-8")
    (reports / "findings.md").write_text("md", encoding="utf-8")

    files, coverage = scanner.scan_directory_with_coverage(
        str(tmp_path), exclude_paths=[reports]
    )

    assert [f["path"] for f in files] == ["app.py"]
    assert not coverage.get("skipped_unsupported_extension")


def test_abstentions_are_normalized_and_returned():
    provider = _StubProvider()
    provider._not_assessed = [
        {"clause_id": "X-1", "reason": "NOT_APPLICABLE", "explanation": "n/a here"},
        {"clause_id": "X-2", "reason": "made up", "explanation": ""},
        "garbage",
    ]

    def analyze(regulation, clauses, file_path, code):
        return {"findings": [], "not_assessed": provider._not_assessed,
                "prompt_tokens": 1, "completion_tokens": 1}

    provider.analyze_code = analyze

    result = run_scan(files=FILES, regulation="Reg", clauses=CLAUSES,
                      provider=provider, cache=_NullCache())

    entries = result["not_assessed"]
    assert len(entries) == 2  # the non-dict is dropped
    assert entries[0]["reason"] == "not_applicable"
    # An unrecognised reason must not become a silent pass.
    assert entries[1]["reason"] == "insufficient_context"
    assert all(e["file_path"] == "a.py" for e in entries)


def test_coverage_section_reports_abstentions():
    md = MarkdownGenerator()._coverage_section({
        "not_assessed": [
            {"file_path": "a.py", "clause_id": "X-1",
             "reason": "not_applicable", "explanation": "no data handling"},
        ],
    })
    text = "\n".join(md)
    assert "Clauses not assessed" in text
    assert "abstention is not a pass" in text
    assert "X-1" in text
