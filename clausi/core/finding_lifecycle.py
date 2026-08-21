"""Stable finding identity, scan comparison, and local remediation state."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


REMEDIATION_STATUSES = (
    "Open",
    "In progress",
    "Risk accepted",
    "False positive",
    "Remediated",
    "Verified",
    "Reopened",
)

_SEVERITY_IMPACT = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "warning": 3,
    "low": 2,
    "info": 1,
}


def _normalize(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text.strip().lower())


def _path_key(value: Any) -> str:
    return _normalize(value).replace("\\", "/")


def _bounded_score(value: Any) -> Optional[int]:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return score if 1 <= score <= 5 else None


def _risk_rating(score: Optional[int]) -> str:
    if score is None:
        return "Not scored"
    if score >= 20:
        return "Critical"
    if score >= 12:
        return "High"
    if score >= 6:
        return "Medium"
    return "Low"


def stable_finding_id(finding: Dict[str, Any], regulation: str) -> str:
    """Return a deterministic ID that survives report ordering and repeat scans."""
    identity = "|".join(
        (
            _normalize(regulation),
            _normalize(finding.get("clause_id")),
            _path_key(finding.get("file_path")),
            _normalize(finding.get("location")),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8].upper()
    regulation_key = re.sub(r"[^A-Z0-9]", "", regulation.upper())[:8] or "GEN"
    clause_key = re.sub(r"[^A-Z0-9]", "", str(finding.get("clause_id", "" )).upper())[-6:] or "CLAUSE"
    return f"CL-{regulation_key}-{clause_key}-{digest}"


def finding_content_hash(finding: Dict[str, Any]) -> str:
    """Hash the material assessment content, excluding workflow-only fields."""
    fields = (
        "severity",
        "explanation",
        "statement",
        "recommended_solution",
        "evidence",
        "business_impact",
        "impact_score",
        "likelihood_score",
        "risk_rationale",
        "verification_criteria",
    )
    payload = {field: _normalize(finding.get(field)) for field in fields}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def regulation_pack_hash(regulation_metadata: Dict[str, Any]) -> str:
    payload = json.dumps(
        regulation_metadata or {}, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"version": 1, "findings": {}}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {"version": 1, "findings": {}}
    if not isinstance(loaded, dict):
        return {"version": 1, "findings": {}}
    if not isinstance(loaded.get("findings"), dict):
        loaded["findings"] = {}
    loaded.setdefault("version", 1)
    return loaded


def _load_snapshot(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"findings": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"findings": {}}
    return loaded if isinstance(loaded, dict) else {"findings": {}}


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def prepare_findings(
    findings: List[Dict[str, Any]],
    regulation: str,
    project_path: Path,
    output_dir: Path,
    scanned_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Enrich findings and prepare, but do not yet persist, lifecycle state."""
    scanned_at = scanned_at or datetime.now(timezone.utc).isoformat()
    output_dir = Path(output_dir)
    remediation_path = Path(project_path) / ".clausi" / "remediation.yml"
    snapshot_path = output_dir / "scan_snapshot.json"
    store = _load_yaml(remediation_path)
    previous = _load_snapshot(snapshot_path)
    previous_findings = previous.get("findings", {})
    if not isinstance(previous_findings, dict):
        previous_findings = {}

    current_snapshot: Dict[str, Any] = {}
    current_ids = set()
    changes = {"new": 0, "unchanged": 0, "changed": 0, "reopened": 0, "resolved": 0}

    for finding in findings:
        if finding.get("clause_id") == "TOKEN-USAGE":
            continue
        finding_id = stable_finding_id(finding, regulation)
        current_ids.add(finding_id)
        prior_snapshot = previous_findings.get(finding_id, {})
        entry = store["findings"].get(finding_id, {})
        if not isinstance(entry, dict):
            entry = {}

        prior_status = _normalize(entry.get("status"))
        content_hash = finding_content_hash(finding)
        if prior_status in {"remediated", "verified"}:
            change_status = "reopened"
            workflow_status = "Reopened"
        elif not prior_snapshot:
            change_status = "new"
            workflow_status = entry.get("status") or finding.get("status") or "Open"
        elif prior_snapshot.get("content_hash") == content_hash:
            change_status = "unchanged"
            workflow_status = entry.get("status") or finding.get("status") or "Open"
        else:
            change_status = "changed"
            workflow_status = entry.get("status") or finding.get("status") or "Open"

        impact_score = _bounded_score(finding.get("impact_score"))
        if impact_score is None:
            impact_score = _SEVERITY_IMPACT.get(_normalize(finding.get("severity")), 3)
            impact_basis = "Severity-derived proxy; validate during human review"
        else:
            impact_basis = "AI-assessed; validate during human review"
        likelihood_score = _bounded_score(finding.get("likelihood_score"))
        risk_score = impact_score * likelihood_score if likelihood_score else None
        risk_rationale = finding.get("risk_rationale")
        if not risk_rationale and likelihood_score is None:
            risk_rationale = (
                "Likelihood was not independently assessed; no numeric residual risk score "
                "is reported until a reviewer supplies it."
            )

        owner = entry.get("owner") or finding.get("owner") or finding.get("responsible_party") or "Unassigned"
        finding.update(
            {
                "finding_id": finding_id,
                "change_status": change_status,
                "owner": owner,
                "responsible_party": owner,
                "status": workflow_status,
                "target_date": entry.get("target_date") or finding.get("target_date") or "",
                "ticket": entry.get("ticket") or finding.get("ticket") or "",
                "treatment": entry.get("treatment") or finding.get("treatment") or finding.get("recommended_solution") or "",
                "reviewer_notes": entry.get("reviewer_notes") or finding.get("reviewer_notes") or "",
                "impact_score": impact_score,
                "impact_score_basis": impact_basis,
                "likelihood_score": likelihood_score,
                "risk_score": risk_score,
                "risk_rating": _risk_rating(risk_score),
                "risk_rationale": risk_rationale or "Human calibration required.",
            }
        )
        changes[change_status] += 1

        store["findings"][finding_id] = {
            **entry,
            "owner": owner,
            "status": workflow_status,
            "target_date": finding.get("target_date") or "",
            "ticket": finding.get("ticket") or "",
            "treatment": finding.get("treatment") or "",
            "reviewer_notes": finding.get("reviewer_notes") or "",
            "regulation": regulation,
            "clause_id": finding.get("clause_id") or "",
            "file_path": finding.get("file_path") or "",
            "last_seen": scanned_at,
        }
        current_snapshot[finding_id] = {
            "content_hash": content_hash,
            "severity": finding.get("severity"),
            "clause_id": finding.get("clause_id"),
            "file_path": finding.get("file_path"),
            "status": workflow_status,
        }

    resolved_ids = sorted(set(previous_findings) - current_ids)
    changes["resolved"] = len(resolved_ids)
    store["updated_at"] = scanned_at
    snapshot = {
        "version": 1,
        "scanned_at": scanned_at,
        "regulation": regulation,
        "findings": current_snapshot,
        "resolved_since_prior_scan": resolved_ids,
    }
    return {
        "findings": findings,
        "change_summary": changes,
        "resolved_ids": resolved_ids,
        "is_baseline": not bool(previous_findings),
        "remediation_path": remediation_path,
        "snapshot_path": snapshot_path,
        "remediation_store": store,
        "snapshot": snapshot,
    }


def commit_lifecycle(prepared: Dict[str, Any]) -> None:
    """Persist remediation state and the current comparison snapshot atomically."""
    remediation_path = Path(prepared["remediation_path"])
    snapshot_path = Path(prepared["snapshot_path"])
    yaml_text = yaml.safe_dump(
        prepared["remediation_store"], sort_keys=False, allow_unicode=True
    )
    json_text = json.dumps(prepared["snapshot"], indent=2, sort_keys=True)
    _atomic_text(remediation_path, yaml_text)
    _atomic_text(snapshot_path, json_text + "\n")


def status_options() -> Iterable[str]:
    return REMEDIATION_STATUSES
