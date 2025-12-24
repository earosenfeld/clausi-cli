# Frontend Dashboard Implementation - CLI Purchase Flow (Hybrid Approach)

> **Date:** 2025-12-08
> **Approach:** Hybrid (show dollars, tokens internal)
> **Priority:** Medium-High

---

## Overview

When users run out of balance in the CLI, they'll be redirected to the dashboard with their token in the URL for auto-authentication and seamless purchase flow.

**Key Principle: Show dollars first, tokens second (for transparency)**

---

## URL Parameters to Handle

The dashboard will receive URLs like:
```
https://www.clausi.ai/dashboard?from=cli&action=purchase&token=clau_abc123xyz
```

**Parameters:**
- `from=cli` - User came from CLI
- `action=purchase` - They need to add funds
- `token=clau_abc123xyz` - Their API token for auto-authentication

---

## Implementation Steps

### 1. Detect CLI Redirect

```javascript
// In your dashboard page component (useEffect or componentDidMount)
const urlParams = new URLSearchParams(window.location.search);
const fromCLI = urlParams.get('from') === 'cli';
const action = urlParams.get('action');
const token = urlParams.get('token');

if (fromCLI && action === 'purchase' && token) {
  handleCLIPurchaseFlow(token);
}
```

### 2. Auto-Authenticate with Token

```javascript
async function handleCLIPurchaseFlow(token) {
  try {
    // Step 1: Authenticate user with the token
    await authenticateWithToken(token);

    // Step 2: Fetch current balance (in tokens)
    const tokenBalance = await fetchTokenBalance(token);

    // Step 3: Convert to dollars for display
    const dollarBalance = tokenBalance * 0.10;

    // Step 4: Show purchase UI
    showAddFundsModal({
      tokenBalance: tokenBalance,      // Backend uses tokens
      dollarBalance: dollarBalance,    // Frontend shows dollars
      source: 'cli',
      highlightMessage: true
    });

  } catch (error) {
    console.error('CLI auth failed:', error);
    // Fallback: show regular purchase UI
    showAddFundsModal({
      tokenBalance: 0,
      dollarBalance: 0,
      source: 'cli',
      error: 'Please log in to add funds'
    });
  }
}
```

### 3. Add Funds Modal/UI (Dollar-First Display)

**Show dollars prominently, tokens as secondary info:**

```jsx
// Example React component
<AddFundsModal>
  <Banner type="info">
    ℹ️ You're here from the CLI - add funds to continue scanning
  </Banner>

  <CurrentBalance>
    <h2>Balance: ${dollarBalance.toFixed(2)}</h2>
    <small>{tokenBalance} credits</small>
  </CurrentBalance>

  <PricingPackages>
    <Package>
      <h3>$10</h3>
      <p>100 credits</p>
      <Badge>Popular ⭐</Badge>
    </Package>

    <Package>
      <h3>$50</h3>
      <p>500 credits</p>
    </Package>

    <Package>
      <h3>$100</h3>
      <p>1000 credits</p>
    </Package>
  </PricingPackages>

  <AfterPurchaseInstructions>
    <strong>After completing your purchase:</strong>
    <ol>
      <li>Return to your terminal</li>
      <li>Re-run your scan: <code>clausi scan .</code></li>
    </ol>
  </AfterPurchaseInstructions>
</AddFundsModal>
```

### 4. After Purchase Confirmation

```javascript
// After Stripe payment succeeds
function onPurchaseComplete(tokensAdded) {
  const dollarsAdded = tokensAdded * 0.10;
  const newTokenBalance = oldTokenBalance + tokensAdded;
  const newDollarBalance = newTokenBalance * 0.10;

  showSuccessMessage({
    title: 'Funds Added! ✅',
    message: `$${dollarsAdded.toFixed(2)} added to your account`,
    details: `New balance: $${newDollarBalance.toFixed(2)} (${newTokenBalance} credits)`,
    cliInstructions: 'Return to your terminal and re-run your scan command'
  });

  // Don't auto-close modal so user can see the message
}
```

---

## User Flow Diagram

```
User runs: clausi scan .
    ↓
CLI: "Insufficient balance: $0.00"
    ↓
Browser opens:
  https://www.clausi.ai/dashboard?from=cli&action=purchase&token=clau_xyz
    ↓
Dashboard auto-authenticates
    ↓
Shows: "Balance: $0.00 (0 credits)"
    ↓
User selects "$10 (100 credits)"
    ↓
Stripe checkout
    ↓
Payment succeeds
    ↓
Shows: "✅ $10.00 added! New balance: $10.00 (100 credits)"
    ↓
User closes browser
    ↓
User re-runs: clausi scan .
    ↓
Works! ✅
```

---

## API Endpoints Needed

### 1. Token Authentication

```javascript
async function authenticateWithToken(token) {
  const response = await fetch('https://api.clausi.ai/api/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token })
  });

  const data = await response.json();

  if (data.authenticated) {
    localStorage.setItem('clausi_token', token);
    return data.user;
  }

  throw new Error('Invalid token');
}
```

### 2. Fetch Balance

```javascript
async function fetchTokenBalance(token) {
  const response = await fetch('https://api.clausi.ai/api/customers/balance', {
    headers: { 'X-Clausi-Token': token }
  });

  const data = await response.json();
  return data.credits; // Returns number (backend uses tokens internally)
}
```

---

## Display Guidelines (Hybrid Approach)

### ✅ Public Pages (Website, Pricing)
**Show ONLY dollars:**
```
Free: $2.00 credit included
Usage: $2.00 minimum + $0.80 per 100k tokens
```

### ✅ Dashboard (Logged In)
**Show BOTH (dollars primary, tokens secondary):**
```
Balance: $4.80
48 credits
```

### ✅ CLI Messages
**Show ONLY dollars:**
```
Balance remaining: $0.00
Estimated scan cost: $4.80
```

### ✅ Purchase Packages
**Show dollars prominently:**
```
$10
100 credits
```

**NOT:**
```
100 credits
$10
```

---

## Testing Instructions

### Test Case 1: User with $0 Balance
```
1. Visit: http://localhost:3000/dashboard?from=cli&action=purchase&token=clau_test123
2. Should auto-login (if token valid)
3. Should show "Balance: $0.00 (0 credits)"
4. Should show purchase modal automatically
```

### Test Case 2: Invalid Token
```
1. Visit: http://localhost:3000/dashboard?from=cli&action=purchase&token=invalid
2. Should gracefully handle error
3. Should show login prompt or error message
```

### Test Case 3: Normal Dashboard Visit
```
1. Visit: http://localhost:3000/dashboard
2. Should work normally (no auto-purchase modal)
```

---

## Edge Cases to Handle

1. **Token expired/invalid:** Show error, ask user to login normally
2. **Already logged in:** If user already has session, verify token matches
3. **Multiple tabs:** Handle if user has dashboard already open
4. **URL cleanup:** After processing, remove query params (optional)

```javascript
// Clean URL after processing (optional for cleaner UX)
if (fromCLI && action === 'purchase') {
  window.history.replaceState({}, document.title, '/dashboard');
}
```

---

## Language/Copy Guidelines

### ✅ Use These Terms:
- "Balance" (not "tokens remaining")
- "Add funds" (not "buy tokens")
- "Purchase" or "Add credits" (not "purchase tokens")
- "$10.00 (100 credits)" (dollars first!)

### ❌ Avoid These Terms:
- "Buy tokens"
- "Token purchase"
- "100 tokens ($10)" (wrong order)

**Exception:** Dashboard can show "credits" as secondary info for power users who want to see the internal accounting.

---

## Minimal Implementation (Quick Start)

```javascript
// dashboard.js or dashboard page component
useEffect(() => {
  const params = new URLSearchParams(window.location.search);

  if (params.get('from') === 'cli' && params.get('action') === 'purchase') {
    const token = params.get('token');
    const urlParams = new URLSearchParams(window.location.search);

    // Show banner or modal
    showNotification({
      type: 'info',
      message: `Welcome from CLI! Add funds to continue scanning.`,
      action: 'Add Funds'
    });

    // Authenticate with token
    if (token) {
      authenticateWithToken(token);
    }
  }
}, []);
```

---

## Summary Checklist

**What to implement:**
- [x] Detect URL parameters (from, action, token)
- [x] Auto-authenticate user with the token
- [x] Fetch current balance (returns tokens from backend)
- [x] **Convert tokens → dollars for display**
- [x] Auto-open/highlight "Add Funds" UI
- [x] Show CLI-specific messaging
- [x] Display balance as "$X.XX (Y credits)"
- [x] Handle success with clear instructions

**Backend endpoints needed:**
- `POST /api/auth/token` - Authenticate with CLI token
- `GET /api/customers/balance` - Get balance (returns tokens)

**Key Difference from Backend's Guide:**
- ✅ Show dollars first, tokens second (hybrid approach)
- ✅ Use "balance" and "add funds" language (not "tokens")
- ✅ Tokens are implementation detail, dollars are user-facing

---

## Conversion Formula

**Always use:**
```javascript
const TOKEN_PRICE = 0.10; // $0.10 per token/credit
const dollarBalance = tokenBalance * TOKEN_PRICE;
```

**Examples:**
```
0 tokens = $0.00
20 tokens = $2.00
100 tokens = $10.00
500 tokens = $50.00
```

---

**Priority:** Medium-High
**Estimated Time:** 2-4 hours
**Dependencies:** Backend endpoints must support token authentication

---

**Last Updated:** 2025-12-08
