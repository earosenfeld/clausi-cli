"""Local scan orchestration: runs files through an AI provider concurrently,
with on-disk caching, and post-processes findings for report generation.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from clausi.core.ai_provider import AIProvider, AIProviderError
from clausi.core.cache import LocalCache

MAX_FILE_CHARS = 8000
MAX_WORKERS = 8

SEVERITY_MAP = {"warning": "medium"}

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
    severity = raw.get("severity", "medium")
    severity = SEVERITY_MAP.get(severity, severity)
    confidence = float(raw.get("confidence", 0.5))
    line_start = raw.get("line_start")
    line_end = raw.get("line_end")
    location = f"lines {line_start}-{line_end}" if line_start else "N/A"

    return {
        "clause_id": raw.get("clause_id", ""),
        "violation": True,
        "severity": severity,
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
        "cached": False,
    }


def apply_effort_bumping(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Escalate remediation_complexity for findings that look architecturally significant."""
    counts_by_clause: Dict[str, int] = {}
    for f in findings:
        if f.get("clause_id") == "TOKEN-USAGE":
            continue
        counts_by_clause[f["clause_id"]] = counts_by_clause.get(f["clause_id"], 0) + 1

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


def analyze_file(provider: AIProvider, cache: LocalCache, regulation: str,
                  clauses: List[Dict[str, Any]], clause_ids: Optional[List[str]],
                  file_data: Dict[str, Any]):
    """Analyze a single file, using the cache when possible.

    Returns (findings, prompt_tokens, completion_tokens, cost).
    """
    file_path = file_data["path"]
    content = file_data["content"]
    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n... [TRUNCATED] ..."

    cache_key = cache.generate_cache_key(
        content, regulation, clauses=clause_ids, provider=provider.name, model=provider.model
    )
    cached = cache.get(cache_key)
    if cached is not None:
        findings = cached["findings"]
        for f in findings:
            f["file_path"] = file_path
            f["cached"] = True
        return findings, 0, 0, 0.0

    result = provider.analyze_code(regulation, clauses, file_path, content)
    findings = [_remap_finding(raw, file_path) for raw in result["findings"]]

    prompt_tokens = result.get("prompt_tokens", 0)
    completion_tokens = result.get("completion_tokens", 0)
    cost = provider.estimate_cost(prompt_tokens, completion_tokens)
    for f in findings:
        f["prompt_tokens"] = prompt_tokens
        f["completion_tokens"] = completion_tokens
        f["total_tokens"] = prompt_tokens + completion_tokens
        f["model"] = provider.model
        f["provider"] = provider.name

    cache.set(cache_key, {"findings": findings})
    return findings, prompt_tokens, completion_tokens, cost


def run_scan(files: List[Dict[str, Any]], regulation: str, clauses: List[Dict[str, Any]],
             provider: AIProvider, cache: LocalCache,
             clauses_include: Optional[List[str]] = None,
             clauses_exclude: Optional[List[str]] = None,
             min_severity: str = "info",
             on_progress=None) -> Dict[str, Any]:
    """Scan all files against one regulation's clauses. Returns
    {"findings": [...], "token_usage": {...}, "cache_stats": {...}}."""
    scoped_clauses = clauses
    if clauses_include:
        scoped_clauses = [c for c in clauses if c.get("id") in clauses_include]
    elif clauses_exclude:
        scoped_clauses = [c for c in clauses if c.get("id") not in clauses_exclude]

    clause_ids = [c["id"] for c in scoped_clauses] if (clauses_include or clauses_exclude) else None

    all_findings: List[Dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    errors: List[str] = []

    def _work(file_data):
        return analyze_file(provider, cache, regulation, scoped_clauses, clause_ids, file_data)

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(files)))) as executor:
        future_to_file = {executor.submit(_work, fd): fd for fd in files}
        completed = 0
        for future in as_completed(future_to_file):
            file_data = future_to_file[future]
            completed += 1
            try:
                findings, prompt_tokens, completion_tokens, cost = future.result()
                all_findings.extend(findings)
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                total_cost += cost
            except AIProviderError as e:
                errors.append(f"{file_data['path']}: {e}")
            if on_progress:
                on_progress(completed, len(files), file_data["path"])

    all_findings = apply_effort_bumping(all_findings)

    severity_order = ["info", "low", "medium", "warning", "high", "critical"]
    if min_severity in severity_order:
        min_idx = severity_order.index(min_severity)
        all_findings = [
            f for f in all_findings
            if severity_order.index(f.get("severity", "info")) >= min_idx
        ]

    token_usage = {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "cost": total_cost,
        "provider": provider.name,
        "model": provider.model,
    }

    return {
        "findings": all_findings,
        "token_usage": token_usage,
        "cache_stats": cache.stats(),
        "errors": errors,
    }
