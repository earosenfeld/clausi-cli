"""Portable remediation-register export for customer follow-through."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable


COLUMNS = (
    "Finding ID",
    "Change",
    "Severity",
    "Impact Score",
    "Likelihood Score",
    "Risk Score",
    "Risk Rating",
    "Confidence",
    "Clause",
    "Requirement",
    "File",
    "Location",
    "Observed Condition",
    "Business Impact",
    "Treatment",
    "Closure Evidence",
    "Owner",
    "Target Date",
    "Status",
    "Ticket",
    "Reviewer Notes",
)


def _row(finding: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "Finding ID": finding.get("finding_id", ""),
        "Change": finding.get("change_status", ""),
        "Severity": finding.get("severity", ""),
        "Impact Score": finding.get("impact_score", ""),
        "Likelihood Score": finding.get("likelihood_score") or "",
        "Risk Score": finding.get("risk_score") or "",
        "Risk Rating": finding.get("risk_rating", ""),
        "Confidence": finding.get("confidence", ""),
        "Clause": finding.get("clause_id", ""),
        "Requirement": finding.get("statement", ""),
        "File": finding.get("file_path", ""),
        "Location": finding.get("location", ""),
        "Observed Condition": finding.get("explanation", ""),
        "Business Impact": finding.get("business_impact") or finding.get("why_this_matters", ""),
        "Treatment": finding.get("treatment") or finding.get("recommended_solution", ""),
        "Closure Evidence": finding.get("verification_criteria", ""),
        "Owner": finding.get("owner") or finding.get("responsible_party", ""),
        "Target Date": finding.get("target_date", ""),
        "Status": finding.get("status", "Open"),
        "Ticket": finding.get("ticket", ""),
        "Reviewer Notes": finding.get("reviewer_notes", ""),
    }


def save_remediation_register(findings: Iterable[Dict[str, Any]], output_dir: Path) -> str:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "remediation_register.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for finding in findings:
            if finding.get("clause_id") != "TOKEN-USAGE":
                writer.writerow(_row(finding))
    return str(output_path.resolve())
