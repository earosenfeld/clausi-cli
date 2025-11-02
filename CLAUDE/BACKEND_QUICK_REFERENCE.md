# Backend Quick Reference Card

## 📥 Install CLI (30 seconds)

```bash
git clone <repo-url> && cd clausi-cli
pip install -e .
clausi --version  # Should show: 1.0.0
```

## ⚙️ Point to Your Backend

```bash
# Edit config file
nano ~/.clausi/config.yml

# Set this:
api:
  url: "http://localhost:10000"  # ← Your backend URL
```

## 🧪 Quick Tests

### Test 1: Health Check
```bash
curl http://localhost:10000/health
```

### Test 2: BYOK Mode (Customer API Key)
```bash
# Set customer's API key
clausi config set --anthropic-key "sk-ant-customer-key"

# Run scan
clausi scan . --regulations EU-AIA --skip-confirmation

# Backend receives:
# Header: X-Anthropic-Key: sk-ant-customer-key
# Backend should: Use customer's key, charge 1 token flat
```

### Test 3: Credits Mode (Backend API Key)
```bash
# Remove customer key
clausi config set --anthropic-key ""

# Run scan
clausi scan . --regulations EU-AIA --skip-confirmation

# Backend receives:
# Header: (no X-Anthropic-Key)
# Backend should: Use own key from .env, charge based on usage
```

### Test 4: Clause Scoping (Cost Reduction)
```bash
clausi scan . --regulations EU-AIA --preset critical-only

# Backend receives:
# Body: { "clauses_include": ["EUAIA-3.1", "EUAIA-6.1", ...] }
# Backend should: Only analyze specified clauses
```

### Test 5: Multi-Model
```bash
clausi scan . --ai-provider openai --ai-model gpt-4o

# Backend receives:
# Body: { "ai_provider": "openai", "ai_model": "gpt-4o" }
# Header: X-OpenAI-Key: sk-customer-key (BYOK mode)
```

## 📋 Expected Headers

### BYOK Mode (Customer Key)
```
POST /api/clausi/scan
X-Clausi-Token: abc123
X-Anthropic-Key: sk-ant-customer-key  ← Use this key
Content-Type: application/json
```

### Credits Mode (Your Key)
```
POST /api/clausi/scan
X-Clausi-Token: abc123
# No X-Anthropic-Key ← Use backend's key from .env
Content-Type: application/json
```

## 📤 Expected Response

```json
{
  "run_id": "run_2024-10-21_abc123",
  "findings": [...],
  "token_usage": {
    "total_tokens": 125000,
    "cost": 6.25,
    "provider": "claude",  ← NEW
    "model": "claude-3-5-sonnet-20241022"  ← NEW
  },
  "cache_stats": {  ← NEW (optional)
    "cache_hits": 120,
    "cache_misses": 30,
    "tokens_saved": 45000
  }
}
```

## 🔍 Debug Commands

```bash
clausi config show          # View config
clausi tokens              # Check token status
clausi --help              # Full help
clausi scan --help         # Scan options
```

## ✅ Backend Checklist

- [ ] `/health` endpoint
- [ ] `/api/clausi/check-payment-required` endpoint
- [ ] `/api/clausi/scan` endpoint
- [ ] Reads `X-Clausi-Token` header
- [ ] Reads `X-Anthropic-Key` header (BYOK)
- [ ] Reads `X-OpenAI-Key` header (OpenAI BYOK)
- [ ] Uses backend key when no customer key (Credits mode)
- [ ] Returns `run_id`, `cache_stats`, `provider`, `model`
- [ ] Markdown download endpoints:
  - [ ] `/api/clausi/report/{run_id}/findings.md`
  - [ ] `/api/clausi/report/{run_id}/traceability.md`
  - [ ] `/api/clausi/report/{run_id}/action_plan.md`

## 📖 Full Documentation

- **Setup & Testing:** `BACKEND_CLI_TESTING_GUIDE.md`
- **API Contract:** `BACKEND_INTEGRATION_GUIDE.md`
- **What's New:** `CHANGELOG_v1.0.0.md`
