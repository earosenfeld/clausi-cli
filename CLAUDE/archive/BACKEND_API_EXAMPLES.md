# Backend API Examples - Quick Reference

**For:** Backend developers integrating CLI v1.0.0 features
**Last Updated:** 2025-10-18

---

## Quick Start

### Minimal Backend Changes (Backward Compatible)

```python
@app.post("/api/clausi/scan")
def scan_endpoint(request: ScanRequest):
    data = request.json

    # NEW: Get optional fields with defaults
    ai_provider = data.get("ai_provider", "openai")
    ai_model = data.get("ai_model", "gpt-4")
    clauses_include = data.get("clauses_include", None)
    clauses_exclude = data.get("clauses_exclude", None)

    # Existing logic works unchanged
    result = perform_scan(data)

    # NEW: Add optional fields to response
    return {
        "run_id": generate_run_id(),  # NEW but optional
        "findings": result["findings"],
        "token_usage": {
            "total_tokens": result["tokens"],
            "cost": result["cost"],
            "provider": ai_provider,  # NEW
            "model": ai_model         # NEW
        }
    }
```

**That's it!** CLI will work with this minimal change.

---

## Example 1: Multi-Model Support

### Request Handler

```python
from anthropic import Anthropic
import openai

def get_ai_client(provider: str, api_key: str):
    """Get AI client based on provider."""
    if provider == "claude":
        return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    else:  # openai
        openai.api_key = api_key
        return openai

def analyze_with_ai(files, clauses, provider, model):
    """Run compliance analysis with specified AI."""

    if provider == "claude":
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Build prompt
        prompt = build_compliance_prompt(files, clauses)

        # Call Claude
        response = client.messages.create(
            model=model or "claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        return parse_claude_response(response.content[0].text)

    else:  # openai
        # Call OpenAI (existing logic)
        response = openai.chat.completions.create(
            model=model or "gpt-4",
            messages=[{
                "role": "user",
                "content": build_compliance_prompt(files, clauses)
            }]
        )

        return parse_openai_response(response.choices[0].message.content)
```

### Token Estimation

```python
def estimate_tokens(files, clauses, provider, model):
    """Estimate token usage based on provider."""

    # Count input tokens
    total_chars = sum(len(f["content"]) for f in files)
    clause_count = len(clauses)

    if provider == "claude":
        # Claude: ~4 chars per token
        input_tokens = total_chars // 4
        # Add tokens for clause analysis
        output_tokens = clause_count * 500
        tokens_per_million_input = 3.0
        tokens_per_million_output = 15.0

    else:  # openai
        # OpenAI: ~4 chars per token
        input_tokens = total_chars // 4
        output_tokens = clause_count * 400
        tokens_per_million_input = 30.0
        tokens_per_million_output = 60.0

    total_tokens = input_tokens + output_tokens
    cost = (input_tokens / 1_000_000 * tokens_per_million_input +
            output_tokens / 1_000_000 * tokens_per_million_output)

    return {
        "estimated_tokens": total_tokens,
        "estimated_cost": cost,
        "provider": provider,
        "model": model
    }
```

---

## Example 2: Clause Scoping

### Clause Filtering

```python
# Define all available clauses
EU_AIA_CLAUSES = {
    "EUAIA-3.1": {
        "title": "Risk Assessment",
        "priority": "critical",
        "description": "Risk assessment and classification"
    },
    "EUAIA-5.2": {
        "title": "High-Risk AI Systems",
        "priority": "critical",
        "description": "Requirements for high-risk systems"
    },
    "EUAIA-7.2": {
        "title": "Transparency",
        "priority": "high",
        "description": "Transparency obligations"
    },
    # ... more clauses
}

def filter_clauses(regulation_id, clauses_include, clauses_exclude):
    """Filter clauses based on include/exclude lists."""

    # Get all clauses for regulation
    if regulation_id == "EU-AIA":
        all_clauses = EU_AIA_CLAUSES
    elif regulation_id == "GDPR":
        all_clauses = GDPR_CLAUSES
    # ... etc

    # Apply filtering
    if clauses_include:
        # Only include specified clauses
        return {
            cid: clause
            for cid, clause in all_clauses.items()
            if cid in clauses_include
        }

    if clauses_exclude:
        # Exclude specified clauses
        return {
            cid: clause
            for cid, clause in all_clauses.items()
            if cid not in clauses_exclude
        }

    # No filtering - return all
    return all_clauses


def scan_with_clause_filter(data):
    """Perform scan with clause filtering."""

    clauses_include = data.get("clauses_include")
    clauses_exclude = data.get("clauses_exclude")
    regulation_id = data["regulations"][0]

    # Filter clauses
    clauses_to_scan = filter_clauses(
        regulation_id,
        clauses_include,
        clauses_exclude
    )

    print(f"Scanning {len(clauses_to_scan)} clauses")

    # Perform scan only on filtered clauses
    results = []
    for clause_id, clause_info in clauses_to_scan.items():
        result = analyze_clause(
            files=data["metadata"]["files"],
            clause_id=clause_id,
            clause_info=clause_info
        )
        results.append(result)

    return {
        "findings": results,
        "clauses_scanned": len(clauses_to_scan),
        "clauses_include": clauses_include,
        "clauses_exclude": clauses_exclude
    }
```

---

## Example 3: Markdown Generation

### Generate findings.md

```python
def generate_findings_markdown(scan_result, project_name):
    """Generate findings.md from scan results."""

    findings = scan_result["findings"]
    metadata = scan_result["metadata"]

    # Count stats
    total = len(findings)
    compliant = sum(1 for f in findings if f["status"] == "compliant")
    non_compliant = total - compliant
    critical = sum(1 for f in findings if f["severity"] == "critical")

    md = f"""# Compliance Findings - {project_name}

**Scan Date:** {metadata['timestamp']}
**Regulations:** {', '.join(metadata['regulations'])}
**Clauses Scanned:** {total}
**AI Provider:** {metadata.get('ai_provider', 'OpenAI')} {metadata.get('ai_model', 'GPT-4')}

---

## Executive Summary

Out of {total} clauses analyzed:
- ✅ **{compliant} compliant** ({compliant/total*100:.1f}%)
- ❌ **{non_compliant} non-compliant** ({non_compliant/total*100:.1f}%)
- 🚨 **{critical} critical issues**

---

## Findings by Clause

"""

    # Add each finding
    for finding in findings:
        status_icon = "✅" if finding["status"] == "compliant" else "❌"
        severity_badge = f"**{finding['severity'].upper()}**"

        md += f"""
### {status_icon} {finding['clause_id']}: {finding.get('title', 'Clause')}

**Status:** {finding['status'].upper()}
**Severity:** {severity_badge}
**Files Checked:** {finding.get('files_checked', 0)}

{finding['description']}

"""

        # Add evidence if compliant
        if finding['status'] == 'compliant' and 'evidence' in finding:
            md += "**Evidence:**\n"
            for evidence in finding['evidence']:
                md += f"- `{evidence['file']}:{evidence['line']}` - {evidence['note']}\n"
            md += "\n"

        # Add recommendations if non-compliant
        if finding['status'] != 'compliant' and 'recommendations' in finding:
            md += "**Recommendations:**\n"
            for i, rec in enumerate(finding['recommendations'], 1):
                md += f"{i}. {rec}\n"
            md += "\n"

        md += "---\n\n"

    # Add summary table
    md += f"""
## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Clauses | {total} |
| Compliant | {compliant} |
| Non-Compliant | {non_compliant} |
| Critical Issues | {critical} |

---

*Generated by Clausi v1.0.0*
"""

    return md
```

### Generate traceability.md

```python
def generate_traceability_markdown(scan_result):
    """Generate traceability matrix."""

    findings = scan_result["findings"]

    md = """# Traceability Matrix

**Project:** My Project
**Scan Date:** 2025-10-18

---

## Code to Clause Mapping

| File | Lines | Clause | Status | Note |
|------|-------|--------|--------|------|
"""

    # Build mapping from files to clauses
    for finding in findings:
        if 'evidence' in finding:
            for evidence in finding['evidence']:
                status = "✅" if finding['status'] == 'compliant' else "❌"
                md += f"| {evidence['file']} | {evidence['line']} | {finding['clause_id']} | {status} | {evidence['note']} |\n"

    md += "\n---\n\n## Clause Coverage\n\n"

    # Add coverage details per clause
    for finding in findings:
        status = "✅ Covered" if finding['status'] == 'compliant' else "❌ Not Covered"
        md += f"""
### {finding['clause_id']}: {finding.get('title', 'Clause')}
- **Status:** {status}
"""
        if finding['status'] == 'compliant' and 'evidence' in finding:
            md += "- **Files:**\n"
            for evidence in finding['evidence']:
                md += f"  - `{evidence['file']}:{evidence['line']}`\n"
        else:
            md += f"- **Gap:** {finding.get('gap_description', 'Not implemented')}\n"

        md += f"- **Priority:** {finding['severity']}\n\n"

    return md
```

### File Storage

```python
import os
from pathlib import Path

def save_markdown_reports(run_id, findings_md, traceability_md, action_plan_md):
    """Save all markdown files to run folder."""

    # Create run folder
    run_folder = Path(f"runs/{run_id}")
    run_folder.mkdir(parents=True, exist_ok=True)

    # Save files
    (run_folder / "findings.md").write_text(findings_md, encoding='utf-8')
    (run_folder / "traceability.md").write_text(traceability_md, encoding='utf-8')
    (run_folder / "action_plan.md").write_text(action_plan_md, encoding='utf-8')

    print(f"Saved markdown reports to {run_folder}")
    return run_folder


def download_markdown_endpoint(run_id: str, filename: str):
    """Endpoint to download markdown files."""

    allowed_files = ["findings.md", "traceability.md", "action_plan.md"]

    if filename not in allowed_files:
        return {"error": "Invalid filename"}, 400

    file_path = Path(f"runs/{run_id}/{filename}")

    if not file_path.exists():
        return {"error": "File not found"}, 404

    content = file_path.read_text(encoding='utf-8')

    return Response(
        content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
```

---

## Example 4: Complete Flow

### Full Scan Endpoint Implementation

```python
from fastapi import FastAPI, HTTPException
from datetime import datetime
import uuid

app = FastAPI()

@app.post("/api/clausi/scan")
async def scan_endpoint(data: dict):
    """Complete scan endpoint with all new features."""

    # 1. Extract parameters
    ai_provider = data.get("ai_provider", "openai")
    ai_model = data.get("ai_model", "gpt-4")
    clauses_include = data.get("clauses_include")
    clauses_exclude = data.get("clauses_exclude")
    files = data["metadata"]["files"]
    regulation_id = data["regulations"][0]

    # 2. Filter clauses
    clauses_to_scan = filter_clauses(
        regulation_id,
        clauses_include,
        clauses_exclude
    )

    # 3. Run AI analysis
    findings = analyze_with_ai(
        files=files,
        clauses=clauses_to_scan,
        provider=ai_provider,
        model=ai_model
    )

    # 4. Generate reports
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{regulation_id.lower()}"

    # PDF report (existing)
    pdf_path = generate_pdf_report(findings, data["metadata"])

    # Markdown reports (new)
    findings_md = generate_findings_markdown(
        {"findings": findings, "metadata": data["metadata"]},
        project_name=Path(data["path"]).name
    )
    traceability_md = generate_traceability_markdown(
        {"findings": findings}
    )
    action_plan_md = generate_action_plan_markdown(findings)

    save_markdown_reports(run_id, findings_md, traceability_md, action_plan_md)

    # 5. Calculate costs
    token_usage = calculate_token_usage(findings, ai_provider, ai_model)

    # 6. Return response
    return {
        "run_id": run_id,  # NEW: For markdown downloads
        "findings": findings,
        "report_filename": pdf_path.name,
        "token_usage": {
            "total_tokens": token_usage["total"],
            "cost": token_usage["cost"],
            "provider": ai_provider,  # NEW
            "model": ai_model         # NEW
        }
    }


@app.get("/api/clausi/report/{run_id}/{filename}")
async def download_report(run_id: str, filename: str):
    """Download markdown report."""
    return download_markdown_endpoint(run_id, filename)
```

---

## Testing Examples

### Test Multi-Model

```python
def test_multi_model():
    # Test Claude
    response = client.post("/api/clausi/scan", json={
        "path": "./test-project",
        "regulations": ["EU-AIA"],
        "ai_provider": "claude",
        "ai_model": "claude-3-5-sonnet-20241022",
        "metadata": {"files": []}
    })

    assert response.status_code == 200
    assert response.json()["token_usage"]["provider"] == "claude"

    # Test OpenAI
    response = client.post("/api/clausi/scan", json={
        "path": "./test-project",
        "regulations": ["EU-AIA"],
        "ai_provider": "openai",
        "ai_model": "gpt-4",
        "metadata": {"files": []}
    })

    assert response.status_code == 200
    assert response.json()["token_usage"]["provider"] == "openai"
```

### Test Clause Scoping

```python
def test_clause_scoping():
    # Test include
    response = client.post("/api/clausi/scan", json={
        "path": "./test-project",
        "regulations": ["EU-AIA"],
        "clauses_include": ["EUAIA-3.1", "EUAIA-7.2"],
        "metadata": {"files": []}
    })

    findings = response.json()["findings"]
    clause_ids = [f["clause_id"] for f in findings]

    assert "EUAIA-3.1" in clause_ids
    assert "EUAIA-7.2" in clause_ids
    assert "EUAIA-9.1" not in clause_ids  # Not included
```

### Test Markdown Download

```python
def test_markdown_download():
    # First, do a scan
    scan_response = client.post("/api/clausi/scan", json={
        "path": "./test-project",
        "regulations": ["EU-AIA"],
        "metadata": {"files": []}
    })

    run_id = scan_response.json()["run_id"]

    # Download findings
    md_response = client.get(f"/api/clausi/report/{run_id}/findings.md")

    assert md_response.status_code == 200
    assert md_response.headers["content-type"] == "text/markdown"
    assert "# Compliance Findings" in md_response.text
```

---

## Common Patterns

### Pattern 1: Graceful Degradation

```python
# Always provide defaults for optional features
ai_provider = data.get("ai_provider", "openai")  # Default to OpenAI

# Check if feature is enabled
if RUN_MARKDOWN_GENERATION:
    run_id = generate_markdown_reports(findings)
else:
    run_id = None  # CLI handles gracefully
```

### Pattern 2: Feature Flags

```python
FEATURES = {
    "multi_model": os.getenv("ENABLE_MULTI_MODEL", "true") == "true",
    "clause_scoping": os.getenv("ENABLE_CLAUSE_SCOPING", "true") == "true",
    "markdown_output": os.getenv("ENABLE_MARKDOWN", "false") == "true"
}

if not FEATURES["multi_model"]:
    ai_provider = "openai"  # Force OpenAI if feature disabled
```

---

## Error Handling

```python
@app.post("/api/clausi/scan")
async def scan_endpoint(data: dict):
    try:
        ai_provider = data.get("ai_provider", "openai")

        # Validate provider
        if ai_provider not in ["claude", "openai"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported AI provider: {ai_provider}"
            )

        # Validate clauses
        if data.get("clauses_include"):
            valid_clauses = get_valid_clause_ids(data["regulations"][0])
            invalid = [c for c in data["clauses_include"] if c not in valid_clauses]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid clause IDs: {invalid}"
                )

        # Perform scan
        result = perform_scan(data)
        return result

    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Summary

**Minimal changes for backward compatibility:**
1. Accept new optional fields
2. Return defaults if not implemented

**Full implementation:**
1. Multi-model routing (30 min)
2. Clause filtering (1 hour)
3. Markdown generation (2-3 hours)

**Total implementation time:** ~4-5 hours for full feature set.

---

For more details, see `BACKEND_INTEGRATION_GUIDE.md`
