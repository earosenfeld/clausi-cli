"""Local scan orchestration: runs files through an AI provider concurrently,
with on-disk caching, and post-processes findings for report generation.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from clausi.core.ai_provider import (
    EST_OUTPUT_TOKENS_PER_CALL,
    AIProvider,
    AIProviderError,
    analysis_fingerprint,
    estimate_tokens,
    prompt_overhead_tokens,
)
from clausi.core.cache import LocalCache

# Characters of a file actually sent for analysis. 8,000 (~2k tokens) was set
# when context windows were small and cut 25 of 86 files on a real repository -
# one at 44% coverage - which for a compliance scan means "not examined" for the
# majority of the file. 60,000 (~15k tokens) covers essentially all hand-written
# source at a cost that is still dominated by the clause text. Files past this
# are still truncated, and still disclosed as truncated in the manifest and both
# reports. Override with scan.max_file_chars in ~/.clausi/config.yml.
MAX_FILE_CHARS = 60000
MAX_WORKERS = 8

# The canonical severity ladder, low to high. Everything downstream - report
# grouping, the --min-severity filter, risk scoring - assumes a value from this
# list, so normalization happens once, at the provider boundary.
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]

# A model returns whatever word it likes. The prompt asks for lowercase
# severities but shows "High|Medium|Low" for finding_certainty a few lines
# later, so capitalized values arrive routinely. Anything unrecognized becomes
# UNKNOWN_SEVERITY rather than raising: the scan is already paid for by the
# time findings are post-processed, and one odd word must not cost the user
# the whole run.
SEVERITY_MAP = {
    "warning": "medium",
    "moderate": "medium",
    "informational": "info",
    "information": "info",
    "note": "info",
    "minor": "low",
    "major": "high",
    "severe": "critical",
    "blocker": "critical",
    "blocking": "critical",
}
UNKNOWN_SEVERITY = "medium"


def normalize_severity(raw: Any) -> str:
    """Map a provider's severity word onto SEVERITY_ORDER. Never raises."""
    if raw is None:
        return UNKNOWN_SEVERITY
    value = str(raw).strip().lower()
    value = SEVERITY_MAP.get(value, value)
    return value if value in SEVERITY_ORDER else UNKNOWN_SEVERITY


# Clause-prefix families treated as architecture/governance-level - findings
# against them get their remediation effort bumped up (never down).
ARCHITECTURE_GOVERNANCE_CLAUSES = (
    "EUAIA-9", "EUAIA-10", "EUAIA-12", "EUAIA-14",
    "GDPR-25", "GDPR-32", "GDPR-35",
    "ISO42001-4", "ISO42001-5", "ISO42001-6",
    "HIPAA-164.308", "HIPAA-164.316",
    "SOC2-CC6", "SOC2-CC7",
)

EFFORT_BUMP_KEYWORDS = (
    "risk management system", "policy program", "data retention program",
    "governance framework", "compliance framework", "audit trail",
    "documentation system",
)

EFFORT_ORDER = ["Low", "Medium", "High"]


def _confidence_to_certainty(confidence: float) -> str:
    if confidence >= 0.8:
        return "High"
    if confidence >= 0.5:
        return "Medium"
    return "Low"


def _remap_finding(raw: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Map a provider's raw JSON finding into the report-generator schema."""
    reported_severity = raw.get("severity", "medium")
    severity = normalize_severity(reported_severity)
    try:
        confidence = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    line_start = raw.get("line_start")
    line_end = raw.get("line_end")
    location = f"lines {line_start}-{line_end}" if line_start else "N/A"

    def bounded_score(value):
        try:
            score = int(value)
        except (TypeError, ValueError):
            return None
        return score if 1 <= score <= 5 else None

    return {
        "clause_id": raw.get("clause_id", ""),
        "violation": True,
        "severity": severity,
        # Kept when we had to reinterpret the model's word, so a reader can see
        # what it actually said.
        "severity_reported": (
            str(reported_severity) if str(reported_severity) != severity else ""
        ),
        "location": location,
        "explanation": raw.get("violation", ""),
        "statement": raw.get("clause_text", ""),
        "recommended_solution": raw.get("recommendation", ""),
        "code_snippet": raw.get("code_snippet", ""),
        "file_path": file_path,
        "confidence": confidence,
        "auto_fixable": bool(raw.get("auto_fixable", False)),
        "evidence": raw.get("evidence", ""),
        "finding_certainty": raw.get("finding_certainty") or _confidence_to_certainty(confidence),
        "remediation_complexity": raw.get("remediation_complexity", "Medium"),
        "responsible_party": raw.get("responsible_party", "Engineering"),
        "why_this_matters": raw.get("why_this_matters", ""),
        "business_impact": raw.get("business_impact", ""),
        "impact_score": bounded_score(raw.get("impact_score")),
        "likelihood_score": bounded_score(raw.get("likelihood_score")),
        "risk_rationale": raw.get("risk_rationale", ""),
        "verification_criteria": raw.get("verification_criteria", ""),
        "cached": False,
    }


def apply_effort_bumping(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Escalate remediation_complexity for findings that look architecturally significant."""
    counts_by_clause: Dict[str, int] = {}
    for f in findings:
        if f.get("clause_id") == "TOKEN-USAGE":
            continue
        clause_id = f.get("clause_id", "")
        counts_by_clause[clause_id] = counts_by_clause.get(clause_id, 0) + 1

    for f in findings:
        clause_id = f.get("clause_id", "")
        if clause_id == "TOKEN-USAGE":
            continue

        should_bump = False
        if counts_by_clause.get(clause_id, 0) > 3:
            should_bump = True
        if any(clause_id.startswith(prefix) for prefix in ARCHITECTURE_GOVERNANCE_CLAUSES):
            should_bump = True
        text = f"{f.get('explanation', '')} {f.get('statement', '')}".lower()
        if any(keyword in text for keyword in EFFORT_BUMP_KEYWORDS):
            should_bump = True

        if should_bump:
            current = f.get("remediation_complexity", "Medium")
            idx = EFFORT_ORDER.index(current) if current in EFFORT_ORDER else 1
            if idx < len(EFFORT_ORDER) - 1:
                f["effort_bumped"] = True
                f["effort_original"] = current
                f["remediation_complexity"] = EFFORT_ORDER[idx + 1]

    return findings


def select_clauses(clauses: List[Dict[str, Any]],
                    include: Optional[List[str]] = None,
                    exclude: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Apply --include/--exclude scoping. Shared so the estimate and the scan
    can never disagree about which clauses are in play."""
    if include:
        return [c for c in clauses if c.get("id") in include]
    if exclude:
        return [c for c in clauses if c.get("id") not in exclude]
    return clauses


VALID_ABSTENTION_REASONS = {
    "not_applicable", "not_observable_in_code", "insufficient_context",
}


def _remap_not_assessed(raw_entries: Any, file_path: str) -> List[Dict[str, Any]]:
    """Normalize the model's abstentions.

    A clause the model could not judge is not a clean clause. Silence used to be
    the only way to express that, and silence is indistinguishable from "no
    violation found" - which is exactly the false clean result a compliance
    report must never produce.
    """
    entries = []
    for raw in (raw_entries or []):
        if not isinstance(raw, dict):
            continue
        reason = str(raw.get("reason", "")).strip().lower()
        entries.append({
            "file_path": file_path,
            "clause_id": str(raw.get("clause_id", "")).strip(),
            "reason": reason if reason in VALID_ABSTENTION_REASONS else "insufficient_context",
            "explanation": str(raw.get("explanation", "")).strip(),
        })
    return entries


def scoped_content(content: str, max_file_chars: int = MAX_FILE_CHARS) -> str:
    """The text actually sent for a file - truncation included.

    Shared by the estimator and the scan so a quote can never be based on more
    content than the scan will send.
    """
    if len(content) > max_file_chars:
        return content[:max_file_chars] + "\n... [TRUNCATED] ..."
    return content


def estimate_scan(files: List[Dict[str, Any]], regulation: str,
                   clauses: List[Dict[str, Any]], provider: AIProvider,
                   max_file_chars: int = MAX_FILE_CHARS,
                   passes: int = 1) -> Dict[str, Any]:
    """Estimate one regulation's scan. Returns per-file and total figures.

    Counts what is actually sent: the prompt scaffold for every file plus the
    (possibly truncated) file text, and a flat per-call output allowance.
    """
    overhead = prompt_overhead_tokens(regulation, clauses)
    per_file = []
    for file_data in files:
        input_tokens = overhead + estimate_tokens(
            scoped_content(file_data["content"], max_file_chars)
        )
        # Every pass is a full request: N passes cost N times as much.
        input_tokens *= max(1, passes)
        output_tokens = EST_OUTPUT_TOKENS_PER_CALL * max(1, passes)
        per_file.append({
            "path": file_data["path"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": provider.estimate_cost(input_tokens, output_tokens),
        })
    return {
        "prompt_overhead_tokens": overhead,
        "per_file": per_file,
        "input_tokens": sum(f["input_tokens"] for f in per_file),
        "output_tokens": sum(f["output_tokens"] for f in per_file),
        "cost": sum(f["cost"] for f in per_file),
    }


class CostBudgetExceeded(AIProviderError):
    """Raised instead of making a call that would push spend past --max-cost."""


class CostBudget:
    """Enforces --max-cost against money actually spent, not just the quote.

    The pre-scan estimate is a guess; the provider's real usage is not. Without
    this, a --max-cost that passes the estimate places no ceiling at all on what
    a scan can charge. Cache hits cost nothing and are never counted.
    """

    def __init__(self, limit: Optional[float]):
        self.limit = limit
        self.spent = 0.0
        self.stopped = False
        self._lock = threading.Lock()

    def reserve(self, projected: float) -> None:
        """Claim room for one call, or raise if it would break the ceiling.

        The claim is added to `spent` immediately, before the call is made.
        MAX_WORKERS files are in flight at once, so a check that only read the
        balance would let every worker pass the ceiling together and blow
        through the limit by up to a full batch of calls.
        """
        if self.limit is None:
            return
        with self._lock:
            if self.spent + projected > self.limit:
                self.stopped = True
                raise CostBudgetExceeded(
                    f"skipped to stay under --max-cost ${self.limit:.2f} "
                    f"(committed ${self.spent:.2f}, this file ~${projected:.2f})"
                )
            self.spent += projected

    def record(self, projected: float, actual: float) -> None:
        """Settle a completed call: swap its reservation for what it really cost."""
        if self.limit is None:
            return
        with self._lock:
            self.spent += actual - projected


def analyze_file(provider: AIProvider, cache: LocalCache, regulation: str,
                  clauses: List[Dict[str, Any]], clause_ids: Optional[List[str]],
                  file_data: Dict[str, Any], budget: Optional["CostBudget"] = None,
                  projected_cost: float = 0.0, max_file_chars: int = MAX_FILE_CHARS,
                  passes: int = 1):
    """Analyze a single file, using the cache when possible.

    Returns (findings, prompt_tokens, completion_tokens, cost).
    """
    file_path = file_data["path"]
    content = file_data["content"]
    if len(content) > max_file_chars:
        # Record the loss. A truncated file yields findings for only the first
        # max_file_chars, so "no finding" past the cut means "not examined".
        file_data["truncated_from"] = len(content)
    content = scoped_content(content, max_file_chars)

    cache_key = cache.generate_cache_key(
        content, regulation, clauses=clause_ids, provider=provider.name,
        model=provider.model, analysis_fingerprint=analysis_fingerprint(clauses),
        # A 3-pass consensus result is not interchangeable with a 1-pass one.
        passes=passes,
    )

    def _from_cache(entry):
        findings = entry["findings"]
        for f in findings:
            f["file_path"] = file_path
            f["cached"] = True
        # Entries written before abstention shipped have no not_assessed key.
        return findings, 0, 0, 0.0, entry.get("not_assessed") or []

    cached = cache.get(cache_key)
    if cached is not None:
        return _from_cache(cached)

    # Identical content scanned concurrently shares one cache key. Serialize on
    # it so only the first worker pays for the API call and the rest reuse the
    # result - which also keeps duplicate files from getting different findings
    # out of a non-deterministic model.
    with cache.key_lock(cache_key):
        cached = cache.peek(cache_key)
        if cached is not None:
            return _from_cache(cached)

        # Checked here, inside the miss path: a cache hit costs nothing and
        # must never be refused for budget reasons.
        if budget is not None:
            budget.reserve(projected_cost)

        try:
            findings, prompt_tokens, completion_tokens, cost, not_assessed = _analyze_uncached(
                provider, cache, regulation, clauses, file_path, content, cache_key,
                passes=passes,
            )
        except Exception:
            # Release the reservation. A failed call produced no findings, and
            # holding its projection would shrink the ceiling for the files
            # that can still succeed.
            if budget is not None:
                budget.record(projected_cost, 0.0)
            raise
        if budget is not None:
            budget.record(projected_cost, cost)
        return findings, prompt_tokens, completion_tokens, cost, not_assessed


def merge_passes(pass_findings: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Merge repeated analyses of one file into findings with a detection rate.

    Measured 2026-09-01 over 10 identical runs of one fixture file: the number
    of findings was stable (3 in 9 runs, 0 in one) but which clauses were
    flagged was not - Article-12 in 90% of runs, Article-13 70%, Article-14
    60%, Article-9 50%. A single pass is therefore a sample, not a
    measurement, and reporting it as a measurement is the problem. Merging by
    clause keeps every clause any pass flagged and records how often it was
    seen, so a reader can tell a consistent finding from a coin flip.
    """
    total = len(pass_findings)
    best: Dict[str, Dict[str, Any]] = {}
    seen: Dict[str, int] = {}

    for findings in pass_findings:
        for clause in {f.get("clause_id", "") for f in findings}:
            seen[clause] = seen.get(clause, 0) + 1
        for finding in findings:
            clause = finding.get("clause_id", "")
            current = best.get(clause)
            # Keep the most confident rendering of each clause; the others say
            # the same thing less well.
            if current is None or _confidence(finding) > _confidence(current):
                best[clause] = finding

    merged = []
    for clause, finding in best.items():
        finding["detection_passes"] = total
        finding["detection_count"] = seen.get(clause, 0)
        finding["detection_rate"] = round(seen.get(clause, 0) / total, 2) if total else 0.0
        merged.append(finding)
    return merged


def _confidence(finding: Dict[str, Any]) -> float:
    try:
        return float(finding.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _analyze_uncached(provider, cache, regulation, clauses, file_path, content,
                       cache_key, passes: int = 1):
    """Call the provider and cache the result. Caller holds the key lock."""
    pass_findings = []
    not_assessed: List[Dict[str, Any]] = []
    prompt_total = completion_total = 0
    cost_total = 0.0

    for _ in range(max(1, passes)):
        result = provider.analyze_code(regulation, clauses, file_path, content)
        pass_findings.append([_remap_finding(raw, file_path) for raw in result["findings"]])
        # Abstentions from the last pass: they describe the same file, and
        # merging them across passes would double-count the same clause.
        not_assessed = _remap_not_assessed(result.get("not_assessed"), file_path)
        prompt_total += result.get("prompt_tokens", 0)
        completion_total += result.get("completion_tokens", 0)
        cost_total += provider.estimate_cost(
            result.get("prompt_tokens", 0), result.get("completion_tokens", 0)
        )

    findings = merge_passes(pass_findings)

    prompt_tokens = prompt_total
    completion_tokens = completion_total
    cost = cost_total
    for f in findings:
        f["prompt_tokens"] = prompt_tokens
        f["completion_tokens"] = completion_tokens
        f["total_tokens"] = prompt_tokens + completion_tokens
        f["model"] = provider.model
        f["provider"] = provider.name

    cache.set(cache_key, {"findings": findings, "not_assessed": not_assessed})
    return findings, prompt_tokens, completion_tokens, cost, not_assessed


def run_scan(files: List[Dict[str, Any]], regulation: str, clauses: List[Dict[str, Any]],
             provider: AIProvider, cache: LocalCache,
             clauses_include: Optional[List[str]] = None,
             clauses_exclude: Optional[List[str]] = None,
             min_severity: str = "info",
             budget: Optional["CostBudget"] = None,
             max_file_chars: int = MAX_FILE_CHARS,
             passes: int = 1,
             on_progress=None) -> Dict[str, Any]:
    """Scan all files against one regulation's clauses. Returns
    {"findings": [...], "token_usage": {...}, "cache_stats": {...}}."""
    scoped_clauses = select_clauses(clauses, clauses_include, clauses_exclude)

    clause_ids = [c["id"] for c in scoped_clauses] if (clauses_include or clauses_exclude) else None

    all_findings: List[Dict[str, Any]] = []
    all_not_assessed: List[Dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    errors: List[str] = []

    estimate = estimate_scan(files, regulation, scoped_clauses, provider,
                              max_file_chars, passes)
    projected = {f["path"]: f["cost"] for f in estimate["per_file"]}

    def _work(file_data):
        return analyze_file(
            provider, cache, regulation, scoped_clauses, clause_ids, file_data,
            budget=budget, projected_cost=projected.get(file_data["path"], 0.0),
            max_file_chars=max_file_chars, passes=passes,
        )

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(files)))) as executor:
        future_to_file = {executor.submit(_work, fd): fd for fd in files}
        completed = 0
        for future in as_completed(future_to_file):
            file_data = future_to_file[future]
            completed += 1
            try:
                findings, prompt_tokens, completion_tokens, cost, not_assessed = future.result()
                all_findings.extend(findings)
                all_not_assessed.extend(not_assessed)
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                total_cost += cost
            except AIProviderError as e:
                errors.append(f"{file_data['path']}: {e}")
            except Exception as e:  # noqa: BLE001 - see below
                # Every API call in this scan is already paid for by the time a
                # worker raises. An unanticipated error on one file must cost
                # that file, not the user's entire run and every other file's
                # findings with it.
                errors.append(
                    f"{file_data['path']}: unexpected {type(e).__name__}: {e}"
                )
            if on_progress:
                on_progress(completed, len(files), file_data["path"])

    try:
        all_findings = apply_effort_bumping(all_findings)
    except Exception as e:  # noqa: BLE001
        # Effort bumping is an enhancement, not the result. Losing it is a
        # degraded report; raising here would lose the report entirely.
        errors.append(f"remediation-effort scoring skipped: {type(e).__name__}: {e}")

    if min_severity in SEVERITY_ORDER:
        min_idx = SEVERITY_ORDER.index(min_severity)

        def _rank(finding):
            return SEVERITY_ORDER.index(normalize_severity(finding.get("severity")))

        all_findings = [f for f in all_findings if _rank(f) >= min_idx]

    token_usage = {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "cost": total_cost,
        "provider": provider.name,
        "model": provider.model,
    }

    truncated = [
        {
            "path": fd["path"],
            "original_chars": fd["truncated_from"],
            "analyzed_chars": max_file_chars,
        }
        for fd in files
        if fd.get("truncated_from")
    ]

    return {
        "findings": all_findings,
        "token_usage": token_usage,
        "cache_stats": cache.stats(),
        "errors": errors,
        "truncated": truncated,
        "not_assessed": all_not_assessed,
    }
