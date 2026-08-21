from pathlib import Path

import yaml

from clausi.core.finding_lifecycle import commit_lifecycle, prepare_findings


def _finding(explanation="Missing review gate", severity="high"):
    return {
        "clause_id": "Article-14",
        "file_path": "src/model.py",
        "location": "lines 10-18",
        "severity": severity,
        "explanation": explanation,
        "statement": "Provide effective human oversight",
        "recommended_solution": "Add an approval gate",
        "confidence": 0.92,
    }


def test_stable_id_and_scan_comparison(tmp_path: Path):
    project = tmp_path / "project"
    output = project / "clausi" / "reports"
    project.mkdir()

    first_findings = [_finding()]
    first = prepare_findings(first_findings, "EU-AIA", project, output)
    first_id = first_findings[0]["finding_id"]
    assert first["is_baseline"] is True
    assert first_findings[0]["change_status"] == "new"
    assert first_findings[0]["risk_score"] is None
    commit_lifecycle(first)

    second_findings = [_finding()]
    second = prepare_findings(second_findings, "EU-AIA", project, output)
    assert second_findings[0]["finding_id"] == first_id
    assert second_findings[0]["change_status"] == "unchanged"
    commit_lifecycle(second)

    changed_findings = [_finding(explanation="Review gate can be bypassed")]
    changed = prepare_findings(changed_findings, "EU-AIA", project, output)
    assert changed_findings[0]["finding_id"] == first_id
    assert changed_findings[0]["change_status"] == "changed"


def test_customer_workflow_state_is_preserved_and_reopened(tmp_path: Path):
    project = tmp_path / "project"
    output = project / "clausi" / "reports"
    project.mkdir()
    first = prepare_findings([_finding()], "EU-AIA", project, output)
    finding_id = first["findings"][0]["finding_id"]
    commit_lifecycle(first)

    remediation_path = project / ".clausi" / "remediation.yml"
    remediation = yaml.safe_load(remediation_path.read_text(encoding="utf-8"))
    remediation["findings"][finding_id].update({
        "owner": "Privacy",
        "status": "Verified",
        "target_date": "2026-09-30",
        "ticket": "GRC-42",
    })
    remediation_path.write_text(yaml.safe_dump(remediation, sort_keys=False), encoding="utf-8")

    current_findings = [_finding()]
    current = prepare_findings(current_findings, "EU-AIA", project, output)
    finding = current_findings[0]
    assert finding["change_status"] == "reopened"
    assert finding["status"] == "Reopened"
    assert finding["owner"] == "Privacy"
    assert finding["target_date"] == "2026-09-30"
    assert finding["ticket"] == "GRC-42"


def test_resolved_count_tracks_missing_prior_finding(tmp_path: Path):
    project = tmp_path / "project"
    output = project / "clausi" / "reports"
    project.mkdir()
    first = prepare_findings([_finding()], "EU-AIA", project, output)
    commit_lifecycle(first)

    current = prepare_findings([], "EU-AIA", project, output)
    assert current["change_summary"]["resolved"] == 1
    assert len(current["resolved_ids"]) == 1
