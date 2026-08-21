import csv
from pathlib import Path

from clausi.core.remediation_register import COLUMNS, save_remediation_register


def test_csv_register_is_customer_actionable(tmp_path: Path):
    finding = {
        "finding_id": "CL-EUAIA-CLE14-1234ABCD",
        "change_status": "new",
        "severity": "high",
        "impact_score": 4,
        "likelihood_score": 3,
        "risk_score": 12,
        "risk_rating": "High",
        "confidence": 0.9,
        "clause_id": "Article-14",
        "statement": "Human oversight",
        "file_path": "src/model.py",
        "location": "lines 10-18",
        "explanation": "No approval gate",
        "owner": "Engineering",
        "status": "Open",
    }
    output = Path(save_remediation_register([finding], tmp_path))
    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0].keys()) == COLUMNS
    assert rows[0]["Finding ID"] == finding["finding_id"]
    assert rows[0]["Risk Score"] == "12"
