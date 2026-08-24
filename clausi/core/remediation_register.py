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


# Columns the customer owns. Everything else in the register is regenerated
# from the scan each run, so an edit to another column is not preserved.
CUSTOMER_COLUMNS = {
    "Owner": "owner",
    "Target Date": "target_date",
    "Status": "status",
    "Ticket": "ticket",
    "Reviewer Notes": "reviewer_notes",
    "Treatment": "treatment",
}


def read_customer_edits(output_dir: Path) -> Dict[str, Dict[str, str]]:
    """Read back workflow fields a customer edited in the register.

    The register is the artifact people actually open in Excel, so edits have to
    survive a rescan. Returns {finding_id: {field: value}} carrying only the
    customer-owned columns; a missing or malformed file yields {} rather than
    raising, because a broken register must never abort a scan.
    """
    register_path = Path(output_dir) / "remediation_register.csv"
    if not register_path.exists():
        return {}

    try:
        # utf-8-sig strips the BOM we write for Excel's benefit.
        with register_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError):
        return {}

    edits: Dict[str, Dict[str, str]] = {}
    for row in rows:
        finding_id = (row.get("Finding ID") or "").strip()
        if not finding_id:
            continue
        edits[finding_id] = {
            field: (row.get(column) or "").strip()
            for column, field in CUSTOMER_COLUMNS.items()
        }
    return edits


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
