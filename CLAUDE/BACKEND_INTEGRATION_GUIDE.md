# Backend Integration Guide - CLI v1.0.0

**Document Version:** 1.0.0
**CLI Version:** 1.0.0
**Last Updated:** 2025-10-18

This document describes the changes made to the Clausi CLI and the corresponding backend integration requirements.

---

## Table of Contents

1. [Overview of Changes](#overview-of-changes)
2. [Package Restructuring](#package-restructuring)
3. [Multi-Model Support Integration](#multi-model-support-integration)
4. [Clause Scoping Integration](#clause-scoping-integration)
5. [Markdown Output Integration](#markdown-output-integration)
6. [Enhanced Progress & Cache Statistics](#enhanced-progress--cache-statistics-v100)
7. [API Contract Changes](#api-contract-changes)
8. [Example Workflows](#example-workflows)
9. [Migration Guide](#migration-guide)

---

## Overview of Changes

The CLI has been modernized with four major feature additions:

1. **Multi-Model Support** - Support for Claude (Anthropic) and OpenAI GPT-4
2. **Clause Scoping** - Granular clause selection with presets
3. **Markdown-First Output** - Rich markdown reports with auto-open functionality
4. **Enhanced Progress & Cache Statistics** - Improved visibility with cache hit/miss tracking

All changes are **backward compatible**. Existing backend implementations will continue to work.

---

## Package Restructuring

### Old Structure
```
clausi-cli/
└── clausi_cli/
    ├── cli.py
    ├── scan.py
    ├── config.py
    └── ...
```

### New Structure
```
clausi-cli/
└── clausi/              # Renamed from clausi_cli
    ├── cli.py           # Thin orchestrator
    ├── commands/        # CLI commands (future expansion)
    ├── core/            # Business logic
    │   ├── scanner.py
    │   ├── payment.py
    │   └── clause_selector.py
    ├── api/             # API client
    │   └── client.py
    └── utils/           # Utilities
        ├── config.py
        └── output.py
```

**Backend Impact:** None - Package internal restructuring only.

---

## Multi-Model Support Integration

### Feature Overview

Users can now choose between Claude (Anthropic) or OpenAI GPT-4 for compliance analysis.

### CLI Usage

```bash
# Use Claude (default)
clausi scan . --ai-provider claude --ai-model claude-3-5-sonnet-20241022

# Use OpenAI
clausi scan . --ai-provider openai --ai-model gpt-4o

# Set default provider
clausi config set --ai-provider claude
```

### Request Changes

**New fields added to `/api/clausi/estimate` and `/api/clausi/scan`:**

```json
{
  "path": ".",
  "regulations": ["EU-AIA"],
  "mode": "full",
  "ai_provider": "claude",           // NEW: "claude" or "openai"
  "ai_model": "claude-3-5-sonnet-20241022",  // NEW: specific model
  "metadata": { ... }
}
```

### Backend Implementation Requirements

#### 1. Accept New Fields

```python
# In your scan/estimate endpoint
data = request.json
ai_provider = data.get("ai_provider", "openai")  # Default to openai for backward compat
ai_model = data.get("ai_model", None)
```

#### 2. Route to Appropriate AI Provider

```python
if ai_provider == "claude":
    # Use Anthropic API
    import anthropic
    client = anthropic.Anthropic(api_key=anthropic_key)
    response = client.messages.create(
        model=ai_model or "claude-3-5-sonnet-20241022",
        ...
    )

elif ai_provider == "openai":
    # Use OpenAI API (existing logic)
    import openai
    response = openai.chat.completions.create(
        model=ai_model or "gpt-4",
        ...
    )
```

#### 3. Handle API Keys

**CLI sends API keys via headers:**
- OpenAI: `X-OpenAI-Key: sk-...`
- Claude: Backend should use its own Anthropic key OR accept from CLI (design decision)

**Recommended approach:**
```python
# Backend uses its own keys for both providers
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = request.headers.get("X-OpenAI-Key")  # From user
```

#### 4. Token Estimation

```python
def estimate_tokens(files, ai_provider, ai_model):
    if ai_provider == "claude":
        # Claude token counting
        # Anthropic models: ~200k context window
        return estimate_claude_tokens(files, ai_model)
    else:
        # OpenAI token counting (existing)
        return estimate_openai_tokens(files, ai_model)
```

#### 5. Response Metadata

Include AI provider info in response:

```json
{
  "findings": [...],
  "token_usage": {
    "total_tokens": 15000,
    "cost": 0.75,
    "provider": "claude",           // NEW
    "model": "claude-3-5-sonnet-20241022"  // NEW
  }
}
```

---

## Clause Scoping Integration

### Feature Overview

Users can now select specific clauses to scan, reducing scan time and cost.

### CLI Usage

```bash
# Interactive selection
clausi scan . --select-clauses

# Use preset
clausi scan . --preset critical-only

# Manual inclusion
clausi scan . --include EUAIA-3.1 --include EUAIA-7.2

# Manual exclusion
clausi scan . --exclude GDPR-5.1
```

### Request Changes

**New fields added to `/api/clausi/estimate` and `/api/clausi/scan`:**

```json
{
  "path": ".",
  "regulations": ["EU-AIA"],
  "clauses_include": ["EUAIA-3.1", "EUAIA-7.2"],  // NEW: Include only these
  "clauses_exclude": ["EUAIA-9.1"],                // NEW: Exclude these
  "metadata": { ... }
}
```

**Rules:**
- If `clauses_include` is provided, ONLY scan those clauses
- If `clauses_exclude` is provided, scan all clauses EXCEPT those
- If neither provided, scan all clauses (default behavior)
- `clauses_include` takes precedence over `clauses_exclude`

### Backend Implementation Requirements

#### 1. Filter Clauses

```python
def get_clauses_to_scan(regulation_id, clauses_include, clauses_exclude):
    all_clauses = get_all_clauses_for_regulation(regulation_id)

    if clauses_include:
        # Only scan included clauses
        return [c for c in all_clauses if c.id in clauses_include]

    if clauses_exclude:
        # Scan all except excluded
        return [c for c in all_clauses if c.id not in clauses_exclude]

    # Default: scan all
    return all_clauses
```

#### 2. Update Token Estimation

```python
def estimate_scan_cost(data):
    clauses_include = data.get("clauses_include")
    clauses_exclude = data.get("clauses_exclude")

    clauses_to_scan = get_clauses_to_scan(
        regulation_id=data["regulations"][0],
        clauses_include=clauses_include,
        clauses_exclude=clauses_exclude
    )

    # Estimate based on filtered clauses
    estimated_tokens = len(clauses_to_scan) * TOKENS_PER_CLAUSE
    return {
        "estimated_tokens": estimated_tokens,
        "clauses_scanned": len(clauses_to_scan),
        "clauses_included": clauses_include,
        "clauses_excluded": clauses_exclude
    }
```

#### 3. Response Updates

Include clause scope in metadata:

```json
{
  "findings": [...],
  "metadata": {
    "clauses_scanned": 7,
    "clauses_include": ["EUAIA-3.1", "EUAIA-7.2"],
    "clauses_exclude": null
  }
}
```

### Available Presets (CLI handles these - backend doesn't need them)

**EU-AIA:**
- `critical-only`: EUAIA-3.1, EUAIA-5.2, EUAIA-7.2, EUAIA-9.1
- `high-priority`: Above + EUAIA-10.2, EUAIA-12.1, EUAIA-13.1
- `documentation`: EUAIA-7.2, EUAIA-11.1, EUAIA-12.1, EUAIA-13.3

**GDPR:**
- `critical-only`: GDPR-5.1, GDPR-32.1, GDPR-33.1
- `high-priority`: Above + GDPR-6.1, GDPR-25.1, GDPR-35.1
- `data-handling`: GDPR-5.1, GDPR-6.1, GDPR-7.1, GDPR-15.1, GDPR-17.1

---

## Markdown Output Integration

### Feature Overview

CLI now supports rich markdown reports that auto-open in the user's editor.

### CLI Usage

```bash
# Auto-open findings.md after scan
clausi scan . --open-findings

# Display markdown summary in terminal
clausi scan . --show-markdown
```

### Expected Files

Backend should generate **3 markdown files** per scan:

1. **`findings.md`** - Compliance findings with detailed explanations
2. **`traceability.md`** - Traceability matrix linking code to clauses
3. **`action_plan.md`** - Recommended remediation actions

### Response Changes

**Add `run_id` to scan response:**

```json
{
  "run_id": "20251018_143022_euaia",  // NEW: Unique run identifier
  "findings": [...],
  "report_filename": "compliance_report.pdf",
  "token_usage": { ... }
}
```

### Backend Implementation Requirements

#### 1. Generate Markdown Files

```python
def generate_markdown_reports(scan_result, run_id):
    """Generate 3 markdown files from scan results."""

    # 1. findings.md
    findings_md = generate_findings_markdown(scan_result)
    save_file(f"runs/{run_id}/findings.md", findings_md)

    # 2. traceability.md
    traceability_md = generate_traceability_markdown(scan_result)
    save_file(f"runs/{run_id}/traceability.md", traceability_md)

    # 3. action_plan.md
    action_plan_md = generate_action_plan_markdown(scan_result)
    save_file(f"runs/{run_id}/action_plan.md", action_plan_md)

    return run_id
```

#### 2. New Download Endpoint

**Endpoint:** `GET /api/clausi/report/{run_id}/{filename}`

```python
@app.get("/api/clausi/report/{run_id}/{filename}")
def download_markdown_report(run_id: str, filename: str):
    """Download a markdown report file.

    Args:
        run_id: Scan run identifier
        filename: One of: findings.md, traceability.md, action_plan.md

    Returns:
        Markdown file content
    """
    allowed_files = ["findings.md", "traceability.md", "action_plan.md"]

    if filename not in allowed_files:
        return {"error": "Invalid filename"}, 400

    file_path = f"runs/{run_id}/{filename}"

    if not os.path.exists(file_path):
        return {"error": "File not found"}, 404

    with open(file_path, 'rb') as f:
        content = f.read()

    return Response(
        content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
```

#### 3. Markdown Templates

**findings.md structure:**

```markdown
# Compliance Findings - [Project Name]

**Scan Date:** 2025-10-18
**Regulations:** EU AI Act
**Clauses Scanned:** 15
**AI Provider:** Claude 3.5 Sonnet

---

## Executive Summary

[High-level overview of compliance status]

---

## Findings by Clause

### ✅ EUAIA-3.1: Risk Assessment

**Status:** COMPLIANT
**Severity:** Critical
**Files Checked:** 12

[Detailed explanation]

**Evidence:**
- `src/risk_manager.py:45-67` - Risk assessment implementation found
- `docs/risk_assessment.md` - Documentation present

---

### ❌ EUAIA-7.2: Transparency Obligations

**Status:** NON-COMPLIANT
**Severity:** High
**Files Checked:** 8

[Detailed explanation]

**Missing:**
- User notification system not implemented
- Transparency logs not found

**Recommendations:**
1. Implement user notification in `src/ui/notifications.py`
2. Add transparency logging to audit trail

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Clauses | 15 |
| Compliant | 12 |
| Non-Compliant | 3 |
| Critical Issues | 1 |
| High Priority | 2 |

---

Generated by Clausi v1.0.0 using Claude 3.5 Sonnet
```

**traceability.md structure:**

```markdown
# Traceability Matrix

**Project:** [Name]
**Scan Date:** 2025-10-18
**Regulation:** EU AI Act

---

## Code to Clause Mapping

| File | Lines | Clause | Status | Note |
|------|-------|--------|--------|------|
| src/risk_manager.py | 45-67 | EUAIA-3.1 | ✅ | Risk assessment impl |
| src/risk_manager.py | 120-145 | EUAIA-9.1 | ✅ | Risk management system |
| src/data/processor.py | 30-55 | EUAIA-10.2 | ✅ | Data governance |
| src/ui/notifications.py | - | EUAIA-7.2 | ❌ | Missing |

---

## Clause Coverage

### EUAIA-3.1: Risk Assessment
- **Status:** ✅ Covered
- **Files:**
  - `src/risk_manager.py:45-67`
  - `tests/test_risk.py:10-25`
- **Confidence:** High

### EUAIA-7.2: Transparency
- **Status:** ❌ Not Covered
- **Gap:** No user notification system found
- **Priority:** High
```

**action_plan.md structure:**

```markdown
# Remediation Action Plan

**Generated:** 2025-10-18
**Priority:** Address 3 critical/high issues

---

## Immediate Actions (Critical)

### 1. Implement User Notification System
- **Clause:** EUAIA-7.2
- **Severity:** High
- **Effort:** 2-3 days
- **Files to modify:**
  - Create `src/ui/notifications.py`
  - Update `src/main.py` to integrate notifications

**Code snippet:**
\`\`\`python
class TransparencyNotifier:
    def notify_user(self, event_type, details):
        # Log transparency event
        self.audit_log.record(event_type, details)
        # Notify user via UI
        self.ui.show_notification(details)
\`\`\`

---

## Next Steps (High Priority)

### 2. Add Transparency Logging
- **Clause:** EUAIA-7.2
- **Severity:** High
- **Effort:** 1 day

### 3. Enhance Risk Documentation
- **Clause:** EUAIA-3.1
- **Severity:** Medium
- **Effort:** 4 hours

---

## Enhanced Progress & Cache Statistics (v1.0.0+)

### Feature Overview

The CLI now displays enhanced progress indicators and cache statistics during scans to provide better visibility into scan performance and cost savings.

### CLI Usage

```bash
# Cache stats shown by default (can be disabled)
clausi scan .

# Explicitly disable cache stats
clausi scan . --no-cache-stats

# Set in config
clausi config set --show-cache-stats true
```

### Backend Implementation Requirements

#### 1. Track Cache Hits/Misses

When analyzing files, track which files have been cached from previous scans:

```python
def analyze_files_with_cache(files, regulation, clauses):
    """Analyze files with caching support."""
    cache_hits = 0
    cache_misses = 0
    tokens_saved = 0
    cost_saved = 0.0

    for file in files:
        # Check if file is in cache (based on content hash + regulation + clauses)
        cache_key = generate_cache_key(file, regulation, clauses)

        if cache_exists(cache_key):
            # Use cached result
            result = get_cached_result(cache_key)
            cache_hits += 1

            # Calculate tokens that would have been used
            file_tokens = estimate_file_tokens(file)
            tokens_saved += file_tokens
            cost_saved += calculate_cost(file_tokens, ai_provider, ai_model)
        else:
            # Analyze file and cache result
            result = analyze_file(file, regulation, clauses)
            store_in_cache(cache_key, result)
            cache_misses += 1

    return {
        "results": results,
        "cache_stats": {
            "total_files": len(files),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": cache_hits / len(files) if files else 0,
            "tokens_saved": tokens_saved,
            "cost_saved": round(cost_saved, 2)
        }
    }
```

#### 2. Cache Key Generation

Recommended cache key format:

```python
import hashlib

def generate_cache_key(file, regulation, clauses):
    """Generate cache key based on file content, regulation, and clauses."""
    # Hash file content
    file_hash = hashlib.sha256(file['content'].encode()).hexdigest()

    # Include regulation and clauses in key
    clauses_str = ",".join(sorted(clauses)) if clauses else "all"

    cache_key = f"{regulation}:{clauses_str}:{file_hash}"
    return cache_key
```

#### 3. Response Format

Include `cache_stats` in scan response:

```json
{
  "findings": [...],
  "token_usage": { ... },
  "cache_stats": {
    "total_files": 150,        // Total files analyzed
    "cache_hits": 120,          // Files served from cache
    "cache_misses": 30,         // Files analyzed fresh
    "cache_hit_rate": 0.80,     // Hit rate (0.0 - 1.0)
    "tokens_saved": 45000,      // Tokens saved by caching
    "cost_saved": 2.25          // Cost saved in USD
  }
}
```

#### 4. Cache Storage Recommendations

**Storage Options:**
- Redis (recommended for production)
- In-memory dict (for development)
- SQLite (for persistence without Redis)

**Cache Expiration:**
- Recommended: 7-30 days
- Invalidate on file content change
- Invalidate on regulation/clause change

**Example with Redis:**

```python
import redis
import json

cache = redis.Redis(host='localhost', port=6379, db=0)
CACHE_TTL = 7 * 24 * 60 * 60  # 7 days

def get_cached_result(cache_key):
    """Get result from Redis cache."""
    data = cache.get(cache_key)
    return json.loads(data) if data else None

def store_in_cache(cache_key, result):
    """Store result in Redis cache with TTL."""
    cache.setex(
        cache_key,
        CACHE_TTL,
        json.dumps(result)
    )
```

### CLI Display

When cache stats are provided, the CLI displays:

```
📊 Cache Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cache Hit Rate     80.0%
Files Cached       120 / 150
Tokens Saved       45,000
Cost Saved         $2.25
```

### Configuration

Cache statistics display can be controlled via:

1. **Command-line flag:**
   ```bash
   clausi scan . --show-cache-stats    # Show (default)
   clausi scan . --no-cache-stats      # Hide
   ```

2. **Config file:**
   ```yaml
   ui:
     show_cache_stats: true  # Show by default
   ```

---

## Long-term Improvements

[...]
```

---

## API Contract Changes

### Summary of All Changes

| Endpoint | Method | New Fields (Request) | New Fields (Response) |
|----------|--------|---------------------|----------------------|
| `/api/clausi/estimate` | POST | `ai_provider`, `ai_model`, `clauses_include`, `clauses_exclude` | `provider`, `model` in token_usage |
| `/api/clausi/scan` | POST | `ai_provider`, `ai_model`, `clauses_include`, `clauses_exclude` | `run_id`, `provider`, `model`, `cache_stats` |
| `/api/clausi/report/{run_id}/{filename}` | GET | N/A (new endpoint) | Markdown file content |

### Backward Compatibility

**All new fields are optional.** Existing backend implementations will work without changes.

**Defaults:**
- `ai_provider`: defaults to `"openai"`
- `ai_model`: defaults to `"gpt-4"` (openai) or `"claude-3-5-sonnet-20241022"` (claude)
- `clauses_include`: defaults to `null` (scan all)
- `clauses_exclude`: defaults to `null` (exclude none)
- `run_id`: If not provided, markdown features are skipped (backward compatible)

---

## Example Workflows

### Example 1: Full-Featured Scan with Claude

**CLI Command:**
```bash
clausi scan ./my-project \
  --ai-provider claude \
  --ai-model claude-3-5-sonnet-20241022 \
  --preset critical-only \
  --open-findings
```

**Request to Backend:**
```json
POST /api/clausi/scan
{
  "path": "./my-project",
  "regulations": ["EU-AIA"],
  "mode": "full",
  "ai_provider": "claude",
  "ai_model": "claude-3-5-sonnet-20241022",
  "clauses_include": ["EUAIA-3.1", "EUAIA-5.2", "EUAIA-7.2", "EUAIA-9.1"],
  "clauses_exclude": null,
  "metadata": {
    "files": [{"path": "src/main.py", "content": "..."}],
    "timestamp": "2025-10-18T14:30:22Z"
  }
}
```

**Response from Backend:**
```json
{
  "run_id": "20251018_143022_euaia_critical",
  "findings": [
    {
      "clause_id": "EUAIA-3.1",
      "status": "compliant",
      "severity": "critical",
      "description": "Risk assessment system implemented",
      "location": "src/risk_manager.py:45"
    }
  ],
  "report_filename": "compliance_report_20251018.pdf",
  "token_usage": {
    "total_tokens": 8500,
    "cost": 0.42,
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
  }
}
```

**Subsequent Markdown Downloads:**
```
GET /api/clausi/report/20251018_143022_euaia_critical/findings.md
GET /api/clausi/report/20251018_143022_euaia_critical/traceability.md
GET /api/clausi/report/20251018_143022_euaia_critical/action_plan.md
```

---

### Example 2: Simple OpenAI Scan (Backward Compatible)

**CLI Command:**
```bash
clausi scan ./my-project
```

**Request to Backend:**
```json
POST /api/clausi/scan
{
  "path": "./my-project",
  "regulations": ["EU-AIA", "GDPR"],
  "mode": "full",
  "metadata": {
    "files": [...]
  }
}
```

**Response from Backend (Legacy Format Still Works):**
```json
{
  "findings": [...],
  "report_filename": "compliance_report.pdf",
  "token_usage": {
    "total_tokens": 15000,
    "cost": 0.75
  }
}
```

---

## Migration Guide

### Phase 1: Non-Breaking Changes (Immediate)

1. **Accept new fields** in `/api/clausi/estimate` and `/api/clausi/scan`
2. **Return defaults** if backend doesn't support multi-model yet:
   ```json
   {
     "token_usage": {
       "provider": "openai",  // Always return openai for now
       "model": "gpt-4"
     }
   }
   ```

### Phase 2: Add Claude Support (Week 1)

1. Add Anthropic SDK: `pip install anthropic`
2. Set `ANTHROPIC_API_KEY` environment variable
3. Implement provider routing logic
4. Test with CLI: `clausi scan . --ai-provider claude`

### Phase 3: Add Clause Scoping (Week 1-2)

1. Implement clause filtering in scan logic
2. Update token estimation to account for clause count
3. Test with: `clausi scan . --preset critical-only`

### Phase 4: Add Markdown Generation (Week 2-3)

1. Create markdown generation functions
2. Implement `runs/` folder structure
3. Add new `/api/clausi/report/{run_id}/{filename}` endpoint
4. Test with: `clausi scan . --open-findings`

---

## Testing Checklist

### Multi-Model Support
- [ ] Scan with `--ai-provider claude` completes successfully
- [ ] Scan with `--ai-provider openai` completes successfully
- [ ] Token usage includes `provider` and `model` fields
- [ ] Cost calculation is correct for both providers

### Clause Scoping
- [ ] `clauses_include` filters clauses correctly
- [ ] `clauses_exclude` filters clauses correctly
- [ ] Token estimate reflects clause count
- [ ] Scan results only include requested clauses

### Markdown Output
- [ ] Scan response includes `run_id`
- [ ] All 3 markdown files can be downloaded
- [ ] Markdown files have correct structure
- [ ] Files are saved in `runs/{run_id}/` folder

### Backward Compatibility
- [ ] Old CLI versions (without new fields) still work
- [ ] Scan without `ai_provider` defaults to OpenAI
- [ ] Scan without `clauses_include/exclude` scans all clauses
- [ ] Scan without `run_id` in response works (no markdown)

---

## Support & Questions

For backend integration support, contact:
- **CLI Maintainer:** [Your Team]
- **Backend Team:** [Backend Team]
- **Documentation:** See `CLAUSI_CLI_KNOWLEDGE_TRANSFER.md` for full CLI architecture

---

**Document Changelog:**
- 2025-10-18: Initial version documenting v1.0.0 changes
