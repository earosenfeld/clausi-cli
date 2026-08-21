"""Tests for the local stakeholder PDF report."""

from pathlib import Path

from clausi.core.pdf_report import PDFReportGenerator


def test_pdf_report_contains_complete_evidence(tmp_path: Path):
    findings = [{
        "clause_id": "Article-14",
        "severity": "critical",
        "file_path": "src/model.py",
        "location": "lines 10-18",
        "explanation": "No human review path is available for high-impact decisions.",
        "statement": "High-risk AI systems must support effective human oversight.",
        "recommended_solution": "Add an approval queue, override control, and intervention log.",
        "code_snippet": "def approve(decision):\n    return decision",
        "evidence": "The approval function returns without checking an assigned reviewer.",
        "confidence": 0.96,
        "responsible_party": "Engineering",
        "remediation_complexity": "Medium",
        "finding_certainty": "High",
    }]
    clauses = [{
        "id": "Article-14",
        "title": "Human Oversight",
    }]

    output = PDFReportGenerator().save_report(
        findings=findings,
        project_name="sample-ai-service",
        regulation="EU AI Act",
        audit_meta={
            "timestamp": "2026-08-20T12:00:00",
            "provider": "OpenAI",
            "model": "gpt-5",
        },
        output_dir=tmp_path,
        files_scanned=12,
        all_clauses=clauses,
    )

    report = Path(output)
    assert report.name == "report.pdf"
    assert report.read_bytes().startswith(b"%PDF")
    assert report.stat().st_size > 5_000
