"""Local Markdown compliance report generation (findings, executive summary,
traceability matrix) - ported from the (now-retired) hosted backend so
reports are produced entirely on-device.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from clausi import __version__ as REPORT_VERSION

RISK_THEME_LABELS = {
    "EUAIA-6": "Risk Classification", "EUAIA-9": "Risk Management",
    "EUAIA-10": "Data Governance", "EUAIA-11": "Technical Documentation",
    "EUAIA-12": "Record Keeping", "EUAIA-13": "Transparency",
    "EUAIA-14": "Human Oversight", "EUAIA-15": "Accuracy & Robustness",
    "GDPR-5": "Data Processing Principles", "GDPR-6": "Lawfulness of Processing",
    "GDPR-7": "Consent", "GDPR-12": "Transparent Information",
    "GDPR-32": "Security of Processing", "ISO42001": "AI Management System",
}

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "warning": 2, "low": 3, "info": 4}
CERTAINTY_RANK = {"High": 0, "Medium": 1, "Low": 2}


def _real_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [f for f in findings if f.get("clause_id") != "TOKEN-USAGE"]


def _apply_back_compat_defaults(findings: List[Dict[str, Any]]) -> None:
    for f in findings:
        if f.get("clause_id") == "TOKEN-USAGE":
            continue
        f["responsible_party"] = f.get("responsible_party") or f.get("owner_suggested") or "Engineering"
        f["remediation_complexity"] = f.get("remediation_complexity") or f.get("effort_bucket") or "Medium"
        if not f.get("finding_certainty"):
            confidence = f.get("confidence", 0.5)
            f["finding_certainty"] = "High" if confidence >= 0.8 else ("Medium" if confidence >= 0.5 else "Low")


def _calculate_audit_readiness(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    real = _real_findings(findings)
    critical = sum(1 for f in real if f.get("severity") == "critical")
    high = sum(1 for f in real if f.get("severity") == "high")
    level = "not_ready" if critical else ("partial" if high else "ready")
    return {"level": level, "critical_count": critical, "high_count": high, "blocking_count": critical}


def _calculate_remediation_effort(findings: List[Dict[str, Any]]) -> str:
    real = _real_findings(findings)
    critical = sum(1 for f in real if f.get("severity") == "critical")
    non_trivial = sum(1 for f in real if f.get("remediation_complexity") in ("Medium", "High"))
    if critical or non_trivial > 10:
        return "Significant"
    if non_trivial >= 4:
        return "Moderate"
    return "Minimal"


def _calculate_top_risk_themes(findings: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    real = _real_findings(findings)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for f in real:
        prefix = f.get("clause_id", "").split(".")[0]
        groups.setdefault(prefix, []).append(f)

    themes = []
    for prefix, group in groups.items():
        high_or_critical = sum(1 for f in group if f.get("severity") in ("critical", "high"))
        themes.append({
            "name": RISK_THEME_LABELS.get(prefix, prefix),
            "count": len(group),
            "high_or_critical_count": high_or_critical,
            "severity": "high" if high_or_critical else "medium",
        })
    themes.sort(key=lambda t: (-t["count"], -t["high_or_critical_count"]))
    return themes[:limit]


def _get_priority_remediation_items(findings: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    real = _real_findings(findings)
    candidates = [
        f for f in real
        if f.get("remediation_complexity") == "Low"
        and f.get("severity") in ("critical", "high", "medium", "warning")
    ]
    candidates.sort(key=lambda f: (
        SEVERITY_RANK.get(f.get("severity", "medium"), 2),
        CERTAINTY_RANK.get(f.get("finding_certainty", "Medium"), 1),
    ))
    return candidates[:limit]


def _file_importance_score(file_path: str) -> int:
    lowered = file_path.lower()
    if any(k in lowered for k in ("main", "app", "index", "server", "api")):
        return 3
    if any(k in lowered for k in ("test", "spec", "util", "helper")):
        return 1
    return 2


def calculate_impact_score(finding: Dict[str, Any]) -> float:
    severity_score = {"critical": 10, "high": 7, "warning": 4, "medium": 4, "low": 2, "info": 1}
    score = severity_score.get(finding.get("severity", "low"), 2)
    score += finding.get("confidence", 0.5) * 5
    score += _file_importance_score(finding.get("file_path", ""))
    return score


class MarkdownGenerator:
    """Builds findings.md, compliance_report.md, and traceability_matrix.md locally."""

    def save_all_reports(self, findings: List[Dict[str, Any]], project_name: str,
                          regulation: str, audit_meta: Dict[str, Any],
                          all_clauses: List[Dict[str, Any]], output_dir: Path,
                          files_scanned: int = 0) -> Dict[str, str]:
        _apply_back_compat_defaults(findings)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = {}
        findings_md = self.generate_findings_md(findings, project_name, regulation, audit_meta, files_scanned)
        (output_dir / "findings.md").write_text(findings_md, encoding="utf-8")
        paths["findings"] = str(output_dir / "findings.md")

        compliance_md = self.generate_compliance_report_md(findings, project_name, regulation, audit_meta, files_scanned)
        (output_dir / "compliance_report.md").write_text(compliance_md, encoding="utf-8")
        paths["compliance_report"] = str(output_dir / "compliance_report.md")

        traceability_md = self.generate_traceability_matrix_md(findings, all_clauses, regulation, project_name)
        (output_dir / "traceability_matrix.md").write_text(traceability_md, encoding="utf-8")
        paths["traceability_matrix"] = str(output_dir / "traceability_matrix.md")

        return paths

    def _footer(self) -> str:
        # Precise wording: analysis is sent to the user's own AI provider, so
        # "no data leaves your machine" would be false. Clausi never sees it.
        return (f"\n---\n*Generated by Clausi v{REPORT_VERSION} on "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')} - analysis ran on this machine "
                f"via your own AI provider; Clausi never received your code.*\n")

    def generate_findings_md(self, findings, project_name, regulation, audit_meta, files_scanned=0) -> str:
        real = _real_findings(findings)
        readiness = _calculate_audit_readiness(findings)
        effort = _calculate_remediation_effort(findings)
        themes = _calculate_top_risk_themes(findings)
        priority_items = _get_priority_remediation_items(findings)

        readiness_labels = {"ready": "READY", "partial": "PARTIALLY READY", "not_ready": "NOT READY"}
        lines = [f"# Compliance Findings: {project_name}", "", f"**Regulation:** {regulation}  ",
                 f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

        lines += ["## Audit Readiness", "",
                  f"**Status:** {readiness_labels.get(readiness['level'], readiness['level'])}  ",
                  f"**Blocking issues:** {readiness['blocking_count']}  ",
                  f"**High-risk gaps:** {readiness['high_count']}", ""]

        lines += ["## Executive Summary", "", "| Metric | Value |", "|---|---|",
                  f"| Files Scanned | {files_scanned} |",
                  f"| Total Findings | {len(real)} |",
                  f"| Blocking Issues | {readiness['blocking_count']} |",
                  f"| High-Risk Gaps | {readiness['high_count']} |",
                  f"| Remediation Effort | {effort} |",
                  f"| Cost | ${audit_meta.get('cost', 0):.4f} |", ""]

        changes = audit_meta.get("change_summary") or {}
        if changes:
            lines += ["## Change Since Prior Assessment", "", "| New | Changed | Reopened | No Longer Detected | Unchanged |", "|---:|---:|---:|---:|---:|",
                      f"| {changes.get('new', 0)} | {changes.get('changed', 0)} | {changes.get('reopened', 0)} | {changes.get('resolved', 0)} | {changes.get('unchanged', 0)} |", ""]

        resolved = audit_meta.get("resolved_findings") or []
        if resolved:
            lines += ["## Resolved Since Prior Assessment", "",
                      f"{len(resolved)} finding(s) previously reported are no longer detected. "
                      "Confirm each was genuinely remediated rather than moved, renamed, or "
                      "excluded from this scan's scope before treating it as closed.", "",
                      "| Finding ID | Clause | Severity | File | Last Recorded Status |",
                      "|---|---|---|---|---|"]
            for r in resolved:
                lines.append(
                    f"| `{r.get('finding_id', '')}` | {r.get('clause_id', '')} | "
                    f"{r.get('severity', '')} | `{r.get('file_path', '')}` | "
                    f"{r.get('last_status', '')} |"
                )
            lines.append("")

        if themes:
            lines += ["## Top Risk Themes", ""]
            for t in themes:
                lines.append(f"- **{t['name']}** ({t['severity']}) - {t['count']} finding(s)")
            lines.append("")

        if priority_items:
            lines += ["## Priority Remediation Items (Quick Wins)", ""]
            for f in priority_items:
                lines.append(f"- `{f.get('clause_id')}` [{f.get('severity')}] {f.get('explanation', '')[:100]}")
            lines.append("")

        severity_counts: Dict[str, int] = {}
        for f in real:
            severity_counts[f.get("severity", "info")] = severity_counts.get(f.get("severity", "info"), 0) + 1
        lines += ["## Summary by Severity", ""]
        for sev in ("critical", "high", "medium", "low", "info"):
            if severity_counts.get(sev):
                lines.append(f"- **{sev.title()}:** {severity_counts[sev]}")
        lines.append("")

        lines += ["## Detailed Findings", ""]
        sorted_findings = sorted(real, key=calculate_impact_score, reverse=True)
        for i, f in enumerate(sorted_findings, 1):
            lines.append(f"### {i}. `{f.get('finding_id', f'F-{i:03d}')}` - `{f.get('clause_id')}` - {f.get('severity', '').upper()}")
            lines.append("")
            lines.append(f"**File:** `{f.get('file_path')}` ({f.get('location', 'N/A')})  ")
            lines.append(f"**Certainty:** {f.get('finding_certainty')} | "
                          f"**Effort:** {f.get('remediation_complexity')} | "
                          f"**Owner:** {f.get('owner') or f.get('responsible_party')} | "
                          f"**Status:** {f.get('status', 'Open')} | "
                          f"**Change:** {f.get('change_status', 'new')}")
            lines.append(f"**Risk:** impact {f.get('impact_score', 'not recorded')}/5, "
                         f"likelihood {f.get('likelihood_score') or 'not assessed'}/5, "
                         f"rating {f.get('risk_rating', 'Not scored')}")
            lines.append("")
            if f.get("statement"):
                lines.append(f"**Clause:** {f['statement']}")
                lines.append("")
            if f.get("why_this_matters"):
                lines.append(f"**Why this matters:** {f['why_this_matters']}")
                lines.append("")
            if f.get("business_impact"):
                lines.append(f"**Business impact:** {f['business_impact']}")
                lines.append("")
            lines.append(f"**Issue:** {f.get('explanation', '')}")
            lines.append("")
            if f.get("code_snippet"):
                lines.append("```")
                lines.append(f["code_snippet"])
                lines.append("```")
                lines.append("")
            if f.get("evidence"):
                lines.append(f"**Evidence:** {f['evidence']}")
                lines.append("")
            lines.append(f"**Recommendation:** {f.get('recommended_solution', '')}")
            lines.append("")

        lines += ["## Scan Metadata", "",
                   f"- Provider: {audit_meta.get('provider')}",
                   f"- Model: {audit_meta.get('model')}",
                   f"- Total tokens: {audit_meta.get('total_tokens', 0):,}",
                   f"- Cost: ${audit_meta.get('cost', 0):.4f}"]

        lines.append(self._footer())
        return "\n".join(lines)

    def generate_compliance_report_md(self, findings, project_name, regulation, audit_meta, files_scanned=0) -> str:
        real = _real_findings(findings)
        readiness = _calculate_audit_readiness(findings)
        priority_items = _get_priority_remediation_items(findings)
        readiness_labels = {"ready": "READY", "partial": "PARTIALLY READY", "not_ready": "NOT READY"}

        lines = [f"# Executive Compliance Report: {project_name}", "", f"**Regulation:** {regulation}  ",
                 f"**Status:** {readiness_labels.get(readiness['level'], readiness['level'])}", ""]

        lines += ["## Summary", "", "| Metric | Value |", "|---|---|",
                  f"| Files Scanned | {files_scanned} |",
                  f"| Total Findings | {len(real)} |",
                  f"| Blocking Issues | {readiness['blocking_count']} |", ""]

        severity_counts: Dict[str, int] = {}
        for f in real:
            severity_counts[f.get("severity", "info")] = severity_counts.get(f.get("severity", "info"), 0) + 1
        lines += ["## Findings by Severity", "", "| Severity | Count |", "|---|---|"]
        for sev in ("critical", "high", "medium", "low", "info"):
            if severity_counts.get(sev):
                lines.append(f"| {sev.title()} | {severity_counts[sev]} |")
        lines.append("")

        if priority_items:
            lines += ["## Priority Items", ""]
            for f in priority_items:
                lines.append(f"- `{f.get('clause_id')}` {f.get('explanation', '')[:100]}")
            lines.append("")

        top_actions = sorted(real, key=calculate_impact_score, reverse=True)[:5]
        if top_actions:
            lines += ["## Recommended Actions", ""]
            for f in top_actions:
                lines.append(f"- **{f.get('clause_id')}**: {f.get('explanation', '')[:100]}")
            lines.append("")

        lines += ["## Next Steps", "",
                   "- [ ] Review all critical and high-severity findings",
                   "- [ ] Assign owners to priority remediation items",
                   "- [ ] Re-run `clausi scan` after fixes to confirm resolution", ""]

        lines.append(self._footer())
        return "\n".join(lines)

    def generate_traceability_matrix_md(self, findings, all_clauses, regulation, project_name) -> str:
        real = _real_findings(findings)
        by_clause: Dict[str, List[Dict[str, Any]]] = {}
        for i, f in enumerate(real, 1):
            f["_finding_ref"] = f"F-{i:03d}"
            by_clause.setdefault(f.get("clause_id", ""), []).append(f)

        lines = [f"# Traceability Matrix: {project_name}", "", f"**Regulation:** {regulation}", "",
                 "| Clause | Title | Findings | Status | IDs |", "|---|---|---|---|---|"]

        for clause in all_clauses:
            clause_id = clause.get("id", "")
            title = clause.get("title", "")
            clause_findings = by_clause.get(clause_id, [])
            count = len(clause_findings)

            if count == 0:
                status = "✅ compliant"
            else:
                max_sev = min((SEVERITY_RANK.get(f.get("severity", "medium"), 2) for f in clause_findings), default=2)
                status = {0: "\U0001F534 critical", 1: "\U0001F7E0 important"}.get(max_sev, "\U0001F7E1 minor")

            ids = ", ".join(f["_finding_ref"] for f in clause_findings[:5])
            if count > 5:
                ids += f" (+{count - 5} more)"

            lines.append(f"| {clause_id} | {title} | {count} | {status} | {ids} |")

        lines.append("")
        lines.append(self._footer())
        return "\n".join(lines)
