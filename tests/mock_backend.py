"""Mock backend server for testing CLI features without hitting real API.

Usage:
    python tests/mock_backend.py

Then in another terminal:
    export CLAUSI_TUNNEL_BASE=http://localhost:5555
    clausi scan ./tests/fixtures
"""

from flask import Flask, request, jsonify, Response
import json
from datetime import datetime

app = Flask(__name__)

# Mock data
MOCK_RUN_ID = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_euaia"

MOCK_ESTIMATE_RESPONSE = {
    "total_tokens": 8500,
    "prompt_tokens": 6000,
    "completion_tokens": 2500,
    "estimated_cost": 0.42,
    "regulation_breakdown": [
        {
            "regulation": "EU-AIA",
            "total_tokens": 8500,
            "estimated_cost": 0.42,
            "clauses": 15
        }
    ],
    "file_breakdown": [
        {
            "path": "main.py",
            "tokens": 2000,
            "estimated_cost": 0.10,
            "too_large": False
        },
        {
            "path": "utils.py",
            "tokens": 1500,
            "estimated_cost": 0.08,
            "too_large": False
        }
    ]
}

MOCK_SCAN_RESPONSE = {
    "run_id": MOCK_RUN_ID,
    "findings": [
        {
            "clause_id": "EUAIA-3.1",
            "status": "compliant",
            "severity": "critical",
            "description": "Risk assessment system properly implemented",
            "location": "src/risk_manager.py:45",
            "violation": False
        },
        {
            "clause_id": "EUAIA-7.2",
            "status": "non-compliant",
            "severity": "high",
            "description": "Missing transparency documentation",
            "location": "docs/",
            "violation": True
        },
        {
            "clause_id": "EUAIA-9.1",
            "status": "compliant",
            "severity": "medium",
            "description": "Risk management system in place",
            "location": "src/risk_system.py:120",
            "violation": False
        }
    ],
    "token_usage": {
        "total_tokens": 8234,
        "cost": 0.40,
        "provider": "claude",
        "model": "claude-3-5-sonnet-20241022"
    },
    "cache_stats": {
        "total_files": 150,
        "cache_hits": 120,
        "cache_misses": 30,
        "cache_hit_rate": 0.80,
        "tokens_saved": 45000,
        "cost_saved": 2.25
    },
    "report_filename": f"compliance_report_{datetime.now().strftime('%Y%m%d')}.pdf",
    "generated_reports": [
        {
            "format": "pdf",
            "filename": f"compliance_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        }
    ]
}

MOCK_MARKDOWN_FILES = {
    "findings.md": """# Compliance Findings - Test Project

**Scan Date:** {date}
**Regulations:** EU AI Act
**AI Provider:** Claude 3.5 Sonnet
**Clauses Scanned:** 15

---

## Executive Summary

✅ **12 of 15 clauses compliant** (80% compliance rate)
⚠️ **3 clauses need attention**

**Risk Level:** MEDIUM

---

## Findings by Clause

### ✅ EUAIA-3.1: Risk Assessment

**Status:** Compliant
**Severity:** Critical
**Location:** `src/risk_manager.py:45`

**Finding:**
Risk assessment system properly implemented with comprehensive coverage.

**Details:**
- Risk categories defined
- Assessment methodology documented
- Automated risk scoring in place

---

### ⚠️ EUAIA-7.2: Transparency Obligations

**Status:** Non-Compliant
**Severity:** High
**Location:** `docs/`

**Finding:**
Missing transparency documentation for AI system capabilities and limitations.

**Required Actions:**
1. Create transparency documentation
2. Document AI system capabilities
3. Document known limitations
4. Provide user-facing disclosures

**Priority:** HIGH - Must be addressed before deployment

---

### ✅ EUAIA-9.1: Risk Management System

**Status:** Compliant
**Severity:** Medium
**Location:** `src/risk_system.py:120`

**Finding:**
Risk management system in place with monitoring capabilities.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Clauses | 15 |
| Compliant | 12 |
| Non-Compliant | 3 |
| Compliance Rate | 80% |
| Critical Issues | 0 |
| High Priority | 1 |

---

*Generated with Claude Code - AI Compliance Analysis*
""".format(date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

    "traceability.md": """# Compliance Traceability Matrix

**Project:** Test Project
**Scan Date:** {date}

---

## Code-to-Clause Mapping

### EUAIA-3.1: Risk Assessment

**Files:**
- `src/risk_manager.py` (lines 45-120)
- `src/risk_types.py` (lines 10-50)
- `config/risk_config.yaml`

**Functions:**
- `assess_risk()` - Main risk assessment
- `calculate_risk_score()` - Risk scoring
- `categorize_risk()` - Risk categorization

---

### EUAIA-7.2: Transparency Obligations

**Files:**
- ❌ Missing: `docs/transparency.md`
- ❌ Missing: `docs/ai_capabilities.md`

**Required:**
- Transparency documentation
- AI capabilities document
- Limitations disclosure

---

### EUAIA-9.1: Risk Management System

**Files:**
- `src/risk_system.py` (lines 120-300)
- `src/monitoring.py` (lines 50-100)

**Functions:**
- `monitor_risks()` - Continuous monitoring
- `update_risk_assessment()` - Risk updates
- `generate_risk_report()` - Reporting

---

*Generated with Claude Code - AI Compliance Analysis*
""".format(date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),

    "action_plan.md": """# Remediation Action Plan

**Project:** Test Project
**Generated:** {date}

---

## Priority 1: HIGH (Must Fix Before Deployment)

### Action 1: Create Transparency Documentation

**Clause:** EUAIA-7.2
**Severity:** High
**Effort:** 4 hours
**Owner:** Compliance Team

**Steps:**
1. Create `docs/transparency.md`
2. Document AI system capabilities
3. Document known limitations
4. Add user-facing disclosures
5. Review with legal team

**Acceptance Criteria:**
- [ ] Documentation created
- [ ] All capabilities listed
- [ ] Limitations documented
- [ ] Legal review complete

---

## Priority 2: MEDIUM (Recommended Improvements)

### Action 2: Enhance Risk Monitoring

**Clause:** EUAIA-9.1
**Severity:** Medium
**Effort:** 8 hours
**Owner:** Engineering Team

**Steps:**
1. Add real-time monitoring dashboard
2. Implement automated alerts
3. Create risk trending reports

**Acceptance Criteria:**
- [ ] Dashboard implemented
- [ ] Alerts configured
- [ ] Reports automated

---

## Timeline

| Week | Actions |
|------|---------|
| Week 1 | Action 1: Transparency docs |
| Week 2 | Action 2: Risk monitoring |
| Week 3 | Review and validation |
| Week 4 | Final compliance scan |

---

## Estimated Costs

- Development effort: 12 hours
- Review cycles: 4 hours
- Testing: 2 hours

**Total:** ~18 hours / 2-3 days

---

*Generated with Claude Code - AI Compliance Analysis*
""".format(date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
}


@app.route('/api/clausi/estimate', methods=['POST'])
def estimate():
    """Mock token estimation endpoint."""
    data = request.json

    # Adjust estimate based on clause scoping
    response = MOCK_ESTIMATE_RESPONSE.copy()

    if data.get('clauses_include'):
        # Reduce tokens if using clause scoping
        clause_count = len(data['clauses_include'])
        reduction_factor = clause_count / 15  # Assume 15 total clauses
        response['total_tokens'] = int(response['total_tokens'] * reduction_factor)
        response['estimated_cost'] = round(response['estimated_cost'] * reduction_factor, 2)

    print(f"✓ Estimate requested: {response['estimated_cost']} USD, {response['total_tokens']} tokens")
    return jsonify(response)


@app.route('/api/clausi/scan', methods=['POST'])
def scan():
    """Mock scan endpoint."""
    data = request.json

    response = MOCK_SCAN_RESPONSE.copy()

    # Update based on request parameters
    ai_provider = data.get('ai_provider', 'openai')
    ai_model = data.get('ai_model', 'gpt-4')

    response['token_usage']['provider'] = ai_provider
    response['token_usage']['model'] = ai_model

    # Filter findings if clause scoping used
    if data.get('clauses_include'):
        included_clauses = data['clauses_include']
        response['findings'] = [
            f for f in response['findings']
            if f['clause_id'] in included_clauses
        ]

    print(f"✓ Scan completed: {len(response['findings'])} findings")
    print(f"  Provider: {ai_provider}, Model: {ai_model}")

    return jsonify(response)


@app.route('/api/clausi/check-payment-required', methods=['POST'])
def check_payment():
    """Mock payment check endpoint."""
    print("✓ Payment check: OK (no payment required)")
    return jsonify({"payment_required": False})


@app.route('/api/clausi/report/<run_id>/<filename>', methods=['GET'])
def download_report(run_id, filename):
    """Mock markdown report download."""
    if filename in MOCK_MARKDOWN_FILES:
        print(f"✓ Downloading: {filename}")
        return Response(
            MOCK_MARKDOWN_FILES[filename],
            mimetype='text/markdown',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )

    return jsonify({"error": "File not found"}), 404


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "Clausi Mock Backend",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    })


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Clausi Mock Backend Server")
    print("=" * 60)
    print()
    print("Server running at: http://localhost:5555")
    print()
    print("To use with CLI:")
    print("  export CLAUSI_TUNNEL_BASE=http://localhost:5555")
    print("  clausi scan ./tests/fixtures")
    print()
    print("Available endpoints:")
    print("  POST /api/clausi/estimate")
    print("  POST /api/clausi/scan")
    print("  POST /api/clausi/check-payment-required")
    print("  GET  /api/clausi/report/{run_id}/{filename}")
    print("  GET  /health")
    print()
    print("=" * 60)
    print()

    app.run(host='0.0.0.0', port=5555, debug=True)
