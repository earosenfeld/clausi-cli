# Backend Team: CLI Testing Guide

## Quick Start (5 minutes)

### 1. Install the CLI

```bash
# Clone the repository
git clone https://github.com/your-org/clausi-cli.git
cd clausi-cli

# Install in development mode
pip install -e .

# Verify installation
clausi --version
# Should show: clausi, version 1.0.0
```

### 2. Configure API Endpoint

The CLI needs to point to your backend. Set this in the config:

```bash
# Open config file
nano ~/.clausi/config.yml

# Or use interactive TUI
clausi ui config
```

**Config file structure:**
```yaml
api_key: ""  # Clausi token (for Credits mode)
api_keys:
  anthropic: "sk-ant-..."  # For BYOK mode with Claude
  openai: "sk-..."         # For BYOK mode with OpenAI

api:
  url: "http://localhost:10000"  # ← Point to your backend
  timeout: 300
  max_retries: 3

ai:
  provider: "claude"  # or "openai"
  model: "claude-3-5-sonnet-20241022"

report:
  format: "pdf"
  output_dir: "clausi/reports"  # Default: ./clausi/reports (avoids conflicts)
  company_name: ""
```

### 3. Quick Test

```bash
# Simple test scan
clausi scan . --regulations EU-AIA --skip-confirmation
```

---

## Testing Payment Modes

The CLI supports two payment models that your backend needs to handle:

### Mode 1: BYOK (Bring Your Own Key)

**Customer provides their AI API key, pays 1 Clausi token flat rate**

```bash
# Set customer's AI key
clausi config set --anthropic-key "sk-ant-customer-key-here"

# Run scan - CLI sends X-Clausi-Token + X-Anthropic-Key headers
clausi scan . --regulations EU-AIA --ai-provider claude
```

**Backend should receive:**
```
Headers:
  X-Clausi-Token: abc123...
  X-Anthropic-Key: sk-ant-customer-key-here
  Content-Type: application/json

Body:
{
  "path": "/path/to/code",
  "regulations": ["EU-AIA"],
  "ai_provider": "claude",
  "ai_model": "claude-3-5-sonnet-20241022",
  ...
}
```

**Backend should:**
- Use customer's `sk-ant-customer-key-here` to call Anthropic API
- Charge exactly 1 Clausi token (flat rate)
- Return results

---

### Mode 2: Credits Mode

**Customer uses backend's AI key, pays variable cost based on usage**

```bash
# Remove customer AI key (simulate Credits mode)
clausi config set --anthropic-key ""

# Get a Clausi token from your backend first
# (You'll need to implement token generation endpoint)

# Run scan - CLI sends only X-Clausi-Token header
clausi scan . --regulations EU-AIA --ai-provider claude
```

**Backend should receive:**
```
Headers:
  X-Clausi-Token: abc123...
  Content-Type: application/json
  # Note: NO X-Anthropic-Key or X-OpenAI-Key header

Body:
{
  "path": "/path/to/code",
  "regulations": ["EU-AIA"],
  "ai_provider": "claude",
  "ai_model": "claude-3-5-sonnet-20241022",
  ...
}
```

**Backend should:**
- Detect no AI key in headers
- Use backend's own API key from `.env`
- Charge based on actual token usage
- Return results with cost breakdown

---

## Key Endpoints to Implement

### 1. Health Check (Optional but Recommended)

```bash
curl http://localhost:10000/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### 2. Check Payment Required

**CLI calls this BEFORE showing cost estimate**

```bash
curl -X POST http://localhost:10000/api/clausi/check-payment-required \
  -H "Content-Type: application/json" \
  -d '{"mode": "full"}'
```

**Expected Response (No Payment Required):**
```json
{
  "payment_required": false,
  "reason": "User has active subscription"
}
```

**Expected Response (Payment Required):**
```json
{
  "payment_required": true,
  "reason": "No active subscription",
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

If `payment_required: true`, CLI will:
1. Open the `checkout_url` in user's browser
2. Show payment instructions
3. Exit and tell user to retry after payment

---

### 3. Main Scan Endpoint

**This is the primary endpoint the CLI uses**

```bash
# Test with BYOK mode
curl -X POST http://localhost:10000/api/clausi/scan \
  -H "Content-Type: application/json" \
  -H "X-Clausi-Token: test-token-123" \
  -H "X-Anthropic-Key: sk-ant-test-key" \
  -d '{
    "path": "/path/to/code",
    "regulations": ["EU-AIA"],
    "mode": "full",
    "ai_provider": "claude",
    "ai_model": "claude-3-5-sonnet-20241022",
    "format": "pdf"
  }'
```

**Request Body Fields:**

**Required:**
- `path` - Directory to scan
- `regulations` - Array of regulation IDs (e.g., ["EU-AIA", "GDPR"])

**Optional (v1.0.0 new features):**
- `ai_provider` - "claude" or "openai" (default: "claude")
- `ai_model` - Specific model name
- `clauses_include` - Array of clause IDs to scan only (e.g., ["EUAIA-3.1", "EUAIA-3.2"])
- `clauses_exclude` - Array of clause IDs to skip
- `mode` - "ai" or "full" (default: "ai")
- `format` - "pdf", "html", "json", or "all"
- `output_dir` - Where to save reports

**Expected Response:**
```json
{
  "run_id": "run_2024-10-21_abc123",
  "status": "completed",
  "findings": [
    {
      "regulation": "EU-AIA",
      "clause_id": "EUAIA-3.1",
      "title": "Risk Management System",
      "severity": "high",
      "finding": "No risk management system detected",
      "file": "src/model.py",
      "line": 42,
      "recommendation": "Implement risk management system..."
    }
  ],
  "token_usage": {
    "total_tokens": 125000,
    "prompt_tokens": 100000,
    "completion_tokens": 25000,
    "cost": 6.25,
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
  "report_files": {
    "pdf": "/path/to/report.pdf",
    "html": "/path/to/report.html",
    "findings_md": "/path/to/findings.md"
  }
}
```

**Important Response Fields:**
- `run_id` - Used to download markdown files later
- `cache_stats` - NEW in v1.0.0, shows cache performance
- `token_usage.provider` - NEW, which AI was used
- `token_usage.model` - NEW, which model was used

---

### 4. Download Markdown Reports (NEW in v1.0.0)

**CLI downloads markdown files after scan completes**

```bash
# Download findings.md
curl http://localhost:10000/api/clausi/report/run_2024-10-21_abc123/findings.md

# Download traceability.md
curl http://localhost:10000/api/clausi/report/run_2024-10-21_abc123/traceability.md

# Download action_plan.md
curl http://localhost:10000/api/clausi/report/run_2024-10-21_abc123/action_plan.md
```

**Expected Response:**
```
Content-Type: text/markdown

# Compliance Findings Report

## EU AI Act (EU-AIA)

### 🔴 High Severity Issues (3)

...
```

---

## Testing Clause Scoping (NEW in v1.0.0)

**Feature:** Users can select specific clauses to scan, reducing cost by 60-80%

### Test 1: Include Specific Clauses

```bash
clausi scan . --regulations EU-AIA \
  --include EUAIA-3.1 \
  --include EUAIA-3.2 \
  --skip-confirmation
```

**Backend receives:**
```json
{
  "regulations": ["EU-AIA"],
  "clauses_include": ["EUAIA-3.1", "EUAIA-3.2"]
}
```

**Backend should:** Only analyze those 2 clauses instead of all ~50 EU-AIA clauses

---

### Test 2: Exclude Specific Clauses

```bash
clausi scan . --regulations EU-AIA \
  --exclude EUAIA-9.1 \
  --exclude EUAIA-9.2 \
  --skip-confirmation
```

**Backend receives:**
```json
{
  "regulations": ["EU-AIA"],
  "clauses_exclude": ["EUAIA-9.1", "EUAIA-9.2"]
}
```

**Backend should:** Analyze all clauses EXCEPT those 2

---

### Test 3: Use Preset

```bash
clausi scan . --regulations EU-AIA \
  --preset critical-only \
  --skip-confirmation
```

**Backend receives:**
```json
{
  "regulations": ["EU-AIA"],
  "clauses_include": ["EUAIA-3.1", "EUAIA-6.1", "EUAIA-9.2", ...]
  // Pre-filtered list of critical clauses
}
```

---

## Testing Multi-Model Support (NEW in v1.0.0)

### Test Claude (Anthropic)

```bash
clausi scan . \
  --regulations EU-AIA \
  --ai-provider claude \
  --ai-model claude-3-5-sonnet-20241022 \
  --skip-confirmation
```

**Backend receives:**
```json
{
  "ai_provider": "claude",
  "ai_model": "claude-3-5-sonnet-20241022"
}
```

**Headers (BYOK mode):**
```
X-Anthropic-Key: sk-ant-customer-key
```

---

### Test OpenAI

```bash
clausi scan . \
  --regulations EU-AIA \
  --ai-provider openai \
  --ai-model gpt-4o \
  --skip-confirmation
```

**Backend receives:**
```json
{
  "ai_provider": "openai",
  "ai_model": "gpt-4o"
}
```

**Headers (BYOK mode):**
```
X-OpenAI-Key: sk-customer-openai-key
```

---

## Common CLI Commands for Testing

### 1. Quick Scan (Skip Confirmation)

```bash
clausi scan . --regulations EU-AIA --skip-confirmation
```

### 2. Scan with Multiple Regulations

```bash
clausi scan . --regulations EU-AIA GDPR HIPAA --skip-confirmation
```

### 3. Scan with Custom Output

```bash
clausi scan . --regulations EU-AIA --output ./my-reports --format all
```

### 4. Interactive Clause Selection

```bash
clausi scan . --regulations EU-AIA --select-clauses
# CLI shows interactive menu to pick clauses
```

### 5. View Cache Statistics

```bash
clausi scan . --regulations EU-AIA --show-cache-stats
```

### 6. Open Findings After Scan

```bash
clausi scan . --regulations EU-AIA --open-findings
# Auto-opens findings.md in default editor
```

---

## Testing the Interactive TUI

### Test Configuration Editor

```bash
clausi ui config
```

**Should show:**
- Interactive form to edit API keys
- Dropdowns for provider/format selection
- "Test Connection" button
- Save/Cancel buttons
- Keyboard shortcuts (Ctrl+S, Esc)

**Test the connection tester:**
1. Enter a valid Anthropic API key
2. Click "Test Connection"
3. Should make a real API call to validate the key

---

## Debugging CLI → Backend Communication

### Enable Verbose Output

```bash
clausi scan . --regulations EU-AIA --verbose
```

### Check Config

```bash
clausi config show
```

**Should display:**
```yaml
api_key: ""
api_keys:
  anthropic: "sk-ant-***idden"
  openai: ""
api:
  url: "http://localhost:10000"
  timeout: 300
  max_retries: 3
ai:
  provider: "claude"
  model: "claude-3-5-sonnet-20241022"
```

### Check Token Status

```bash
clausi tokens
```

**Should show:**
```
Token Status:
  Status: Active
  Credits: 100 tokens remaining
  Type: Trial Account
```

---

## Expected HTTP Headers

The CLI always sends these headers:

### BYOK Mode (Customer API Key)
```
POST /api/clausi/scan
Content-Type: application/json
X-Clausi-Token: abc123...
X-Anthropic-Key: sk-ant-customer-key  ← Customer's key
```

### Credits Mode (Backend API Key)
```
POST /api/clausi/scan
Content-Type: application/json
X-Clausi-Token: abc123...
# No X-Anthropic-Key header - use backend's key
```

### OpenAI BYOK Mode
```
POST /api/clausi/scan
Content-Type: application/json
X-Clausi-Token: abc123...
X-OpenAI-Key: sk-customer-openai-key  ← Customer's OpenAI key
```

---

## Testing Error Handling

### Test 1: Invalid API Key

```bash
# Set invalid key
clausi config set --anthropic-key "invalid-key"

# Try to scan
clausi scan . --regulations EU-AIA
```

**Expected:** CLI validates key locally and shows error before hitting backend

---

### Test 2: Backend Returns 402 Payment Required

**Backend response:**
```json
HTTP 402 Payment Required
{
  "payment_required": true,
  "checkout_url": "https://checkout.stripe.com/..."
}
```

**CLI should:**
1. Open checkout URL in browser
2. Show payment instructions
3. Exit gracefully

---

### Test 3: Backend Returns 500 Error

**Backend response:**
```json
HTTP 500 Internal Server Error
{
  "error": "Database connection failed"
}
```

**CLI should:**
1. Display error message
2. Exit with non-zero status code

---

## Quick Reference: Backend Checklist

- [ ] `/health` endpoint responding
- [ ] `/api/clausi/check-payment-required` endpoint working
- [ ] `/api/clausi/scan` endpoint accepting requests
- [ ] Reads `X-Clausi-Token` header
- [ ] Reads `X-Anthropic-Key` header (BYOK mode)
- [ ] Reads `X-OpenAI-Key` header (OpenAI BYOK mode)
- [ ] Uses backend API key when no customer key provided (Credits mode)
- [ ] Handles `ai_provider` field (claude/openai)
- [ ] Handles `ai_model` field
- [ ] Handles `clauses_include` array
- [ ] Handles `clauses_exclude` array
- [ ] Returns `run_id` in response
- [ ] Returns `cache_stats` in response
- [ ] Returns `token_usage.provider` and `token_usage.model`
- [ ] Markdown download endpoints working
- [ ] `/api/clausi/report/{run_id}/findings.md`
- [ ] `/api/clausi/report/{run_id}/traceability.md`
- [ ] `/api/clausi/report/{run_id}/action_plan.md`

---

## Sample Backend Test Script

```bash
#!/bin/bash
# test_backend.sh - Quick backend integration test

API_URL="http://localhost:10000"
TOKEN="test-token-123"
ANTHROPIC_KEY="sk-ant-test-key"

echo "1. Testing health check..."
curl -s $API_URL/health | jq .

echo -e "\n2. Testing payment check..."
curl -s -X POST $API_URL/api/clausi/check-payment-required \
  -H "Content-Type: application/json" \
  -d '{"mode":"full"}' | jq .

echo -e "\n3. Testing scan endpoint (BYOK mode)..."
curl -s -X POST $API_URL/api/clausi/scan \
  -H "Content-Type: application/json" \
  -H "X-Clausi-Token: $TOKEN" \
  -H "X-Anthropic-Key: $ANTHROPIC_KEY" \
  -d '{
    "path": ".",
    "regulations": ["EU-AIA"],
    "ai_provider": "claude",
    "ai_model": "claude-3-5-sonnet-20241022",
    "clauses_include": ["EUAIA-3.1"]
  }' | jq .

echo -e "\n4. Testing markdown download..."
RUN_ID="run_2024-10-21_test"
curl -s $API_URL/api/clausi/report/$RUN_ID/findings.md | head -10
```

---

## Contact & Support

**For CLI issues:**
- Check `CLAUDE/USER_GUIDE.md` for user documentation
- Check `CLAUDE/BACKEND_INTEGRATION_GUIDE.md` for API contract

**For backend integration questions:**
- See `CLAUDE/BACKEND_INTEGRATION_GUIDE.md` for complete API specs
- See `CLAUDE/CHANGELOG_v1.0.0.md` for what's new in v1.0.0

**Quick help:**
```bash
clausi --help                 # Main help
clausi scan --help            # Scan command help
clausi config --help          # Config management
clausi ui --help              # Interactive mode help
```
