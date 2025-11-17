"""Tests for the Clausi CLI."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from clausi.cli import cli
from clausi.core.scanner import scan_directory

@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()

def test_scan_directory(tmp_path):
    """Test directory scanning functionality."""
    # Create test files
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    
    # Create a Python file
    py_file = test_dir / "test.py"
    py_file.write_text("print('Hello, World!')")
    
    # Create a non-code file
    txt_file = test_dir / "test.txt"
    txt_file.write_text("This is a text file")
    
    # Scan the directory
    files = scan_directory(str(test_dir))
    
    # Check results
    assert len(files) == 1  # Only the Python file should be included
    assert files[0]["path"] == "test.py"
    assert files[0]["type"] == "py"
    assert files[0]["content"] == "print('Hello, World!')"

@patch("clausi.core.payment.requests.post")
def test_audit_command(mock_post, runner, tmp_path):
    """Test the audit command."""
    # Mock the API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "findings": [
            {
                "clause_id": "TEST-1",
                "violation": False,
                "severity": "low",
                "location": "test.py:1"
            }
        ],
        "report_path": "/path/to/report.pdf"
    }
    mock_post.return_value = mock_response
    
    # Create test project
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    (test_dir / "test.py").write_text("print('Hello, World!')")
    
    # Run the command
    result = runner.invoke(cli, ["scan", str(test_dir), "--regulation", "EU-AIA"])

    # Check the result
    assert result.exit_code == 0
    assert "TEST-1" in result.output 