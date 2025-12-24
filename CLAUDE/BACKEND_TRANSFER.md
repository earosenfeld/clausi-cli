# Backend Integration Update - Add "clausi" Provider Support

> **Date:** 2025-12-08
> **Priority:** HIGH - Blocking payment flow testing
> **Affected:** Backend API (`app/services/ai_provider.py`)

---

## Problem

**CLI is sending `provider = "clausi"` but backend doesn't recognize it.**

### Current Error

```
ValueError: Unknown provider: clausi. Supported: claude, openai, claude-code-cli, claude-code
```

### What's Happening

When users run:
```bash
clausi scan .
```

The CLI sends:
```json
{
  "ai_provider": "clausi",
  "files": [...],
  "regulations": ["EU-AIA"]
}
```

Backend responds with 500 error because "clausi" is not in the supported providers list.

---

## Solution

**Add "clausi" as a valid provider name for the credit-based hosted AI mode.**

"clausi" should work the same as "claude-code-cli" (backend's hosted AI), just with better branding/naming.

---

## Code Changes Required

### File: `app/services/ai_provider.py`

**Location:** Line ~887 (in `get_ai_provider()` function)

#### Change 1: Update Error Message

```python
# BEFORE:
raise ValueError(f"Unknown provider: {provider_name}. Supported: claude, openai, claude-code-cli, claude-code")

# AFTER:
raise ValueError(f"Unknown provider: {provider_name}. Supported: claude, openai, claude-code-cli, claude-code, clausi")
```

#### Change 2: Add "clausi" Provider Handler

Add this before the error is raised:

```python
# NEW: Add support for "clausi" provider (credit-based hosted AI)
elif provider_name == "clausi":
    # "clausi" is an alias for "claude-code-cli" (better branding)
    # Uses backend's AI, charges via credit system
    logger.info("Using Clausi hosted AI (credit-based, no customer API key required)")
    return ClaudeCodeCLIProvider(api_key=None)
```

**Complete example:**

```python
def get_ai_provider(api_key: Optional[str] = None, provider_name: str = "claude") -> BaseProvider:
    """Get AI provider instance based on provider name."""

    if provider_name == "claude":
        return ClaudeProvider(api_key=api_key)

    elif provider_name == "openai":
        return OpenAIProvider(api_key=api_key)

    elif provider_name == "claude-code-cli":
        logger.info("No API key provided - using Claude Code CLI (free, no API costs)")
        return ClaudeCodeCLIProvider(api_key=None)

    elif provider_name == "claude-code":
        return ClaudeCodeProvider(api_key=api_key)

    # NEW: Add "clausi" as alias for hosted AI mode
    elif provider_name == "clausi":
        logger.info("Using Clausi hosted AI (credit-based, no customer API key required)")
        return ClaudeCodeCLIProvider(api_key=None)

    else:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: claude, openai, claude-code-cli, claude-code, clausi")
```

---

## What "clausi" Provider Should Do

**Behavior:** Same as "claude-code-cli"

1. ✅ Use backend's AI keys (not customer's)
2. ✅ Charge via credit/token system
3. ✅ Check customer credits before scan
4. ✅ Deduct credits after scan
5. ✅ Return 402 Payment Required if insufficient credits
6. ✅ Support account creation (20 starting credits)

**Pricing:**
- Minimum: 20 credits ($2.00)
- Plus: 8 credits per 100k tokens ($0.80 per 100k)
- New users: 20 credits ($2.00 starting balance)

---

## Additional Backend Issues Found

### Issue 2: Trial Credits Parameter Error

**Error in logs:**
```
ERROR:app.middleware.credits_guard:Error in credits guard:
CustomerService.create_trial_customer() got an unexpected keyword argument 'trial_credits'
```

**Fix:** Update `CustomerService.create_trial_customer()` to accept `trial_credits` parameter:

```python
# In CustomerService
def create_trial_customer(self, ..., trial_credits: int = 20):
    """Create trial customer with specified credits."""
    # ... existing code
    customer.credits = trial_credits  # Use parameter instead of hardcoded value
    # ... rest of code
```

---

## Testing Instructions

### Test 1: Verify "clausi" Provider Works

**Request:**
```bash
curl -X POST http://localhost:8000/api/clausi/scan/async \
  -H "Content-Type: application/json" \
  -H "X-Clausi-Token: clau_test123" \
  -d '{
    "ai_provider": "clausi",
    "regulations": ["EU-AIA"],
    "files": ["test.py"],
    "file_contents": {"test.py": "print(\"hello\")"}
  }'
```

**Expected Response:**
```json
{
  "job_id": "uuid-here",
  "status": "processing"
}
```

**NOT:**
```json
{
  "error": "Unknown provider: clausi"
}
```

### Test 2: Verify Trial Account Creation

**Request (no token):**
```bash
curl -X POST http://localhost:8000/api/clausi/scan/async \
  -H "Content-Type: application/json" \
  -d '{
    "ai_provider": "clausi",
    "regulations": ["EU-AIA"],
    "files": ["test.py"],
    "file_contents": {"test.py": "print(\"hello\")"}
  }'
```

**Expected Response (401):**
```json
{
  "api_token": "clau_generated_token",
  "credits": 20,
  "message": "Trial account created"
}
```

### Test 3: Verify Payment Required Flow

**Setup:** Set user credits to 0 in database

**Request:**
```bash
curl -X POST http://localhost:8000/api/clausi/scan/async \
  -H "Content-Type: application/json" \
  -H "X-Clausi-Token: clau_test123" \
  -d '{
    "ai_provider": "clausi",
    "regulations": ["EU-AIA"],
    "files": ["test.py"],
    "file_contents": {"test.py": "print(\"hello\")"}
  }'
```

**Expected Response (402):**
```json
{
  "payment_required": true,
  "checkout_url": "https://checkout.stripe.com/...",
  "credits_needed": 25,
  "credits_available": 0
}
```

---

## Provider Matrix (for Reference)

| Provider | API Key Source | CLI Flag | Cost Model |
|----------|---------------|----------|------------|
| **clausi** | Backend's keys | (default) | Credit-based: 25 tokens min + usage |
| **claude** | Customer's key | `--claude` | $0.50 platform fee (5 tokens) |
| **openai** | Customer's key | `--openai` | $0.50 platform fee (5 tokens) |
| **claude-code-cli** | Backend's keys | N/A (internal) | Same as "clausi" |

---

## Migration Notes

**Backward Compatibility:**
- ✅ All existing providers still work (claude, openai, claude-code-cli)
- ✅ Just adding "clausi" as a new option
- ✅ No breaking changes

**Rollout:**
- Deploy backend changes first
- CLI already sends "clausi" (v1.0.0)
- Once deployed, payment flow testing can proceed

---

## Checklist

Backend developer should complete:

- [ ] Add "clausi" to supported providers list
- [ ] Add "clausi" handler in `get_ai_provider()`
- [ ] Fix `create_trial_customer()` to accept `trial_credits` parameter
- [ ] Test with curl (see Testing Instructions above)
- [ ] Verify logs show "Using Clausi hosted AI" (not "Claude Code CLI")
- [ ] Deploy to staging/production
- [ ] Notify CLI team that backend is ready

---

## Questions?

**Contact:** CLI Development Team

**Related Files:**
- CLI: `clausi/cli.py` line 638 (sets `provider = "clausi"`)
- CLI: `clausi/core/payment.py` (handles 401/402 responses)
- Backend: `app/services/ai_provider.py` line ~887 (needs update)

---

**Priority:** HIGH - Blocking payment flow testing and production launch

**Estimated Time:** 15-30 minutes

---

**Last Updated:** 2025-12-08
