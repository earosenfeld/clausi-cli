# Clausi CLI - Pricing Strategy

> **Purpose:** Business pricing model, payment flows, and monetization strategy
>
> **Last Updated:** 2025-12-24
> **Version:** 1.0.0
> **For:** Product, pricing, and business strategy decisions

---

## Table of Contents

1. [Pricing Overview](#pricing-overview)
2. [Three Business Models](#three-business-models)
3. [Credit System](#credit-system)
4. [Payment Flow](#payment-flow)
5. [Stripe Integration](#stripe-integration)
6. [Trial System](#trial-system)
7. [Pricing Tiers](#pricing-tiers)
8. [Cost Analysis](#cost-analysis)
9. [Future Considerations](#future-considerations)

---

## Pricing Overview

### Core Philosophy

**Balance accessibility with sustainability:**
- **Free trial** for first-time users (20 credits = ~2-5 scans)
- **Low barrier to entry** ($2 minimum credit purchase)
- **BYOK option** for cost-conscious power users
- **Platform fee** that's fair and transparent

### Revenue Sources

| Source | Description | Revenue per Scan |
|--------|-------------|------------------|
| **Clausi AI credits** | User pays for AI usage via our backend | Variable ($0.50 - $5.00) |
| **Platform fees (BYOK)** | Fixed fee when user provides their own API key | $0.50 per scan |
| **Credit packages** | Bulk credit purchases (discounts at higher tiers) | Varies by package |

---

## Three Business Models

### 1. Clausi AI (Default) - Credit-Based

**What:**
- User doesn't provide API key
- Backend uses its own Claude/OpenAI instances
- User pays via credit system

**Pricing:**
- **Minimum purchase:** $2 (20 credits)
- **Cost per scan:** Variable based on project size
  - Small project (<100 files): ~2-5 credits ($0.20-$0.50)
  - Medium project (100-500 files): ~10-20 credits ($1.00-$2.00)
  - Large project (>500 files): ~30-50 credits ($3.00-$5.00)

**Revenue Model:**
```
User Payment: $2 minimum
↓
Backend AI Cost: ~40-60% of revenue
↓
Gross Margin: 40-60%
```

**Advantages:**
- ✅ Easiest for users (no API key setup)
- ✅ Highest revenue per scan
- ✅ We control AI quality/model selection
- ✅ Can optimize costs via caching

**Disadvantages:**
- ❌ Higher support burden (payment issues, refunds)
- ❌ Need to front AI costs
- ❌ Responsible for rate limits

---

### 2. Claude BYOK (Bring Your Own Key)

**What:**
- User provides their Anthropic API key
- Backend uses customer's key for AI calls
- We charge platform fee only

**Pricing:**
- **Platform fee:** $0.50 per scan
- **User's AI cost:** Direct Anthropic charges (they pay separately)
  - Claude Sonnet: ~$3 per 1M input tokens, ~$15 per 1M output tokens
  - Typical scan: $0.10 - $2.00 in AI costs (user pays Anthropic directly)

**Revenue Model:**
```
Platform Fee: $0.50 per scan
↓
Our Costs: Minimal (server, bandwidth)
↓
Gross Margin: ~90%
```

**Advantages:**
- ✅ Predictable revenue ($0.50 per scan)
- ✅ No AI cost risk
- ✅ Users appreciate transparency
- ✅ Appeals to cost-conscious developers

**Disadvantages:**
- ❌ Lower revenue per scan
- ❌ More complex for users (need Anthropic account)
- ❌ Less control over AI quality

---

### 3. OpenAI BYOK

**What:**
- User provides their OpenAI API key
- Backend uses customer's key for AI calls
- We charge platform fee only

**Pricing:**
- **Platform fee:** $0.50 per scan
- **User's AI cost:** Direct OpenAI charges
  - GPT-4: ~$10 per 1M input tokens, ~$30 per 1M output tokens
  - Typical scan: $0.20 - $3.00 in AI costs (user pays OpenAI directly)

**Revenue Model:**
- Same as Claude BYOK above

---

## Credit System

### Credit Pricing Packages

| Package | Price | Credits | Cost per Credit | Discount | Best For |
|---------|-------|---------|-----------------|----------|----------|
| **Starter** | $2 | 20 | $0.10 | 0% | Trial, small projects |
| **Basic** | $5 | 60 | $0.083 | 17% | Individual developers |
| **Pro** | $10 | 150 | $0.067 | 33% | Small teams |
| **Team** | $25 | 400 | $0.063 | 37% | Larger teams |
| **Enterprise** | Custom | Custom | Custom | 40%+ | Organizations |

### Credit Usage Examples

**Small Python Project (50 files, 5K LOC):**
- Token estimate: ~200K tokens
- Credits: 3-5 credits
- Cost: $0.30-$0.50

**Medium Web App (200 files, 20K LOC):**
- Token estimate: ~800K tokens
- Credits: 15-20 credits
- Cost: $1.50-$2.00

**Large Monorepo (1000 files, 100K LOC):**
- Token estimate: ~4M tokens
- Credits: 40-50 credits
- Cost: $4.00-$5.00

**With --preset critical-only (60-80% reduction):**
- Small project: 1-2 credits ($0.10-$0.20)
- Medium project: 5-8 credits ($0.50-$0.80)
- Large project: 15-20 credits ($1.50-$2.00)

---

## Payment Flow

### User Journey: Clausi AI (Default)

```
1. User runs: clausi scan .
   ↓
2. CLI checks: Do they have an API token?
   ├─→ No token → Backend creates trial account (401 response)
   │                ↓
   │              CLI saves token, user gets 20 free credits
   │                ↓
   │              Scan proceeds automatically
   │
   └─→ Has token → Continue to step 3

3. Backend checks: Do they have enough credits?
   ├─→ Yes → Run scan, deduct credits
   │           ↓
   │         Scan completes, show results
   │
   └─→ No → Return 402 Payment Required
             ↓
           CLI opens Stripe checkout in browser
             ↓
           User completes payment
             ↓
           User re-runs: clausi scan .
             ↓
           Scan proceeds with purchased credits
```

### User Journey: BYOK (Claude/OpenAI)

```
1. User runs: clausi scan . --claude
   ↓
2. CLI checks: Do they have Anthropic API key?
   ├─→ No → Show error with instructions
   │           ↓
   │         Exit
   │
   └─→ Yes → Continue

3. CLI sends request with X-Anthropic-Key header
   ↓
4. Backend checks: Valid key?
   ├─→ Invalid → Return 401 Unauthorized
   │               ↓
   │             CLI shows error
   │
   └─→ Valid → Use customer's key for AI calls
                 ↓
               Charge $0.50 platform fee
                 ↓
               Return scan results
```

---

## Stripe Integration

### Checkout Flow

**1. Backend creates checkout session:**
```python
checkout_session = stripe.checkout.Session.create(
    payment_method_types=['card'],
    line_items=[{
        'price_data': {
            'currency': 'usd',
            'product_data': {
                'name': 'Clausi Credits',
                'description': '60 credits for compliance scanning'
            },
            'unit_amount': 500,  # $5.00 in cents
        },
        'quantity': 1,
    }],
    mode='payment',
    success_url='https://clausi.ai/payment/success?session_id={CHECKOUT_SESSION_ID}',
    cancel_url='https://clausi.ai/payment/cancel',
    client_reference_id=user_token,  # Link payment to user
)

return {
    "payment_required": True,
    "checkout_url": checkout_session.url
}
```

**2. CLI receives 402 response:**
```python
{
    "payment_required": True,
    "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

**3. CLI opens browser:**
```python
import webbrowser
webbrowser.open(checkout_url)

console.print("Payment required - see browser")
console.print("After payment, re-run your scan command")
```

**4. User completes payment in Stripe:**
- Stripe test card: 4242 4242 4242 4242
- Any future expiry date
- Any 3-digit CVC

**5. Stripe webhook notifies backend:**
```python
@app.post("/webhooks/stripe")
def stripe_webhook(request):
    event = stripe.Webhook.construct_event(
        payload=request.body,
        sig_header=request.headers['Stripe-Signature'],
        secret=STRIPE_WEBHOOK_SECRET
    )

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_token = session['client_reference_id']
        amount = session['amount_total']  # in cents

        # Credit user's account
        credits = amount / 10  # $0.10 per credit
        add_credits_to_user(user_token, credits)

    return {"status": "success"}
```

**6. User re-runs scan:**
```bash
clausi scan .
# Now has credits, scan proceeds
```

---

## Trial System

### Trial Account Creation

**When:** First scan without API key

**Backend behavior (401 response):**
```python
# User has no token, create trial
trial_token = generate_token()
trial_credits = 20  # 20 free credits

create_user_account(
    token=trial_token,
    credits=trial_credits,
    created_at=datetime.now(),
    trial=True
)

return Response(
    status_code=401,
    json={
        "api_token": trial_token,
        "credits": trial_credits,
        "message": "Trial account created"
    }
)
```

**CLI behavior:**
```python
if response.status_code == 401:
    data = response.json()
    token = data["api_token"]
    credits = data["credits"]

    console.print(f"Trial account created!")
    console.print(f"Credits: {credits}")

    # Save token for future scans
    save_api_token(token)

    # Retry scan with new token
    return retry_scan_with_token(api_url, api_key, provider, data, token)
```

**Trial limitations:**
- ✅ Full feature access (all regulations, AI models)
- ✅ 20 credits (~2-5 scans depending on project size)
- ✅ No credit card required
- ✅ No time limit
- ❌ Cannot get more free credits (must purchase)

---

## Pricing Tiers

### Current Tiers (v1.0.0)

**1. Free Trial**
- Cost: $0
- Credits: 20
- Perfect for: Evaluating Clausi, small projects

**2. Starter ($2)**
- Credits: 20
- Cost per credit: $0.10
- Perfect for: Individual developers, occasional scans

**3. Basic ($5)**
- Credits: 60
- Cost per credit: $0.083
- Discount: 17%
- Perfect for: Regular users, small teams

**4. Pro ($10)**
- Credits: 150
- Cost per credit: $0.067
- Discount: 33%
- Perfect for: Power users, weekly scans

**5. Team ($25)**
- Credits: 400
- Cost per credit: $0.063
- Discount: 37%
- Perfect for: Teams, CI/CD integration

**6. Enterprise (Custom)**
- Credits: Custom
- Cost per credit: Negotiated (targeting ~$0.06)
- Discount: 40%+
- Perfect for: Organizations, high-volume usage
- Includes: Dedicated support, SLA, custom regulations

---

## Cost Analysis

### Backend Costs (Clausi AI Mode)

**Per-scan AI costs (using Claude Sonnet):**

```
Small project (200K tokens):
  Input:  200K tokens × $3/1M  = $0.60
  Output: 10K tokens × $15/1M  = $0.15
  Total AI cost: ~$0.75
  User pays: 3-5 credits ($0.30-$0.50)
  Loss: -$0.25 to -$0.45 per scan

Medium project (800K tokens):
  Input:  800K tokens × $3/1M  = $2.40
  Output: 40K tokens × $15/1M  = $0.60
  Total AI cost: ~$3.00
  User pays: 15-20 credits ($1.50-$2.00)
  Loss: -$1.00 to -$1.50 per scan

Large project (4M tokens):
  Input:  4M tokens × $3/1M    = $12.00
  Output: 200K tokens × $15/1M = $3.00
  Total AI cost: ~$15.00
  User pays: 40-50 credits ($4.00-$5.00)
  Loss: -$10.00 to -$11.00 per scan
```

**⚠️ ISSUE: Current pricing is not sustainable!**

### Sustainable Pricing Analysis

**Option 1: Increase credit cost**
```
Current: $0.10 per credit
Needed: $0.25-$0.30 per credit (2.5-3x increase)

New pricing:
  Starter: $5 for 20 credits
  Basic: $15 for 60 credits
  Pro: $30 for 150 credits
```

**Option 2: Increase credits per scan**
```
Current: Small = 3-5 credits, Medium = 15-20, Large = 40-50
Needed: Small = 10-15 credits, Medium = 40-60, Large = 200-300

Maintains $0.10/credit but uses more credits per scan
```

**Option 3: Hybrid - Adjust both**
```
Credits: $0.15 per credit
Usage: Increase by 1.5-2x

New pricing:
  Starter: $3 for 20 credits
  Small scan: 5-8 credits ($0.75-$1.20)
  Medium scan: 25-35 credits ($3.75-$5.25)
  Large scan: 80-120 credits ($12-$18)
```

**Option 4: Usage-based pricing**
```
Charge per 100K tokens:
  $0.40 per 100K tokens

Small (200K): $0.80
Medium (800K): $3.20
Large (4M): $16.00

Transparent and fair, scales with actual usage
```

### BYOK Costs (Platform Fee Model)

**Per-scan costs:**
```
Revenue: $0.50 platform fee
Backend costs:
  - Server/compute: $0.02
  - Bandwidth: $0.01
  - Database: $0.01
  - Support/overhead: $0.05
  Total cost: ~$0.09

Gross profit: $0.41 per scan
Gross margin: 82%
```

**BYOK is highly profitable but lower total revenue**

---

## Future Considerations

### Subscription Model

**Monthly subscriptions instead of credits:**

```
Tier 1: $9/month
  - 10 scans/month
  - All regulations
  - Standard support

Tier 2: $29/month
  - Unlimited scans
  - All regulations
  - Priority support
  - Custom regulations

Tier 3: $99/month (Team)
  - Unlimited scans
  - 5 user seats
  - All features
  - Dedicated support
  - SLA
```

**Advantages:**
- Predictable revenue
- Higher customer lifetime value
- Easier for teams to budget

**Disadvantages:**
- May not suit occasional users
- Need to estimate "unlimited" usage

---

### Freemium Model

**Always-free tier:**
```
Free forever:
  - 5 scans/month
  - EU-AIA only
  - Community support

Paid tiers unlock:
  - Unlimited scans
  - All regulations
  - Custom regulations
  - Priority support
```

**Advantages:**
- Lower barrier to entry
- Viral growth potential
- Builds community

**Disadvantages:**
- High free user count may not convert
- Support burden for free users

---

### Enterprise Features

**Custom pricing for large organizations:**

1. **Self-hosted option** - Run Clausi backend on-premises
   - One-time: $10,000 setup
   - Annual: $5,000 license
   - Unlimited scans

2. **API access** - Programmatic scanning
   - $500/month base
   - $0.50 per scan via API

3. **Dedicated instance** - Isolated cloud deployment
   - $1,000/month
   - Guaranteed SLA
   - Custom regulations included

4. **White-label** - Rebrand Clausi for internal use
   - $5,000/month minimum
   - Custom branding
   - Dedicated support

---

### Promotional Pricing

**Launch promotion ideas:**

1. **Early adopter discount**
   - 50% off first purchase
   - Valid through Q1 2025

2. **Referral program**
   - Give 10 credits, Get 10 credits
   - Both referrer and referred get bonus

3. **Open source discount**
   - 30% off for OSS projects
   - Verification via GitHub

4. **Student/academic pricing**
   - Free credits for .edu emails
   - 50% off all packages

5. **Non-profit pricing**
   - 70% off all packages
   - Verification required

---

## Recommendations

### Immediate (Q1 2025)

1. **Fix pricing model** - Current Clausi AI pricing is unsustainable
   - **Recommendation:** Move to usage-based ($0.40 per 100K tokens)
   - Or: Increase credit cost to $0.25/credit and adjust usage estimates

2. **Promote BYOK** - Higher margins, lower risk
   - Add prominent "Save money with BYOK" messaging
   - Tutorial video on setting up API keys

3. **Trial improvements**
   - Reduce trial credits from 20 to 10 (still 1-2 scans)
   - Add "20% off first purchase" for trial users

### Medium-term (Q2 2025)

4. **Add subscription option**
   - Test $9/month tier (10 scans)
   - Gauge interest in "unlimited" tiers

5. **Implement caching**
   - Cache AI responses for unchanged files
   - Reduce AI costs by 40-60%
   - Pass savings to users (lower credit usage)

6. **Volume discounts**
   - Discount for 100+ scans/month
   - Enterprise tier with negotiated pricing

### Long-term (Q3+ 2025)

7. **Self-hosted option**
   - For enterprise customers
   - Higher revenue per customer

8. **API access**
   - Programmatic scanning
   - Monthly + per-scan pricing

9. **White-label**
   - For consulting firms, large enterprises
   - High-touch sales, high revenue

---

## Pricing Decision Framework

**When considering pricing changes, evaluate:**

1. **Customer value** - How much value does Clausi provide?
   - Prevents compliance violations (priceless)
   - Saves manual audit time (hours → minutes)
   - Typical benchmark: Customers pay 10% of value

2. **Competitive pricing** - What do alternatives cost?
   - Manual audits: $5,000-$50,000
   - Automated tools: $100-$1,000/month
   - Our position: **Significantly cheaper than both**

3. **Cost to serve** - What does it cost us?
   - AI costs: $0.75-$15.00 per scan (current)
   - Infrastructure: $0.05-$0.10 per scan
   - Support: ~$0.50 per active user/month

4. **Customer willingness to pay** - Market research
   - Survey users after trial
   - A/B test pricing tiers
   - Monitor conversion rates

5. **Strategic goals** - Growth vs profitability
   - Early stage: Optimize for growth (lower prices)
   - Growth stage: Balance growth + profitability
   - Mature: Optimize for profitability (raise prices)

---

## Key Metrics to Track

### Financial Metrics

- **MRR (Monthly Recurring Revenue)** - For subscription model
- **ARPU (Average Revenue Per User)** - Credits purchased per month
- **CAC (Customer Acquisition Cost)** - Marketing + sales costs
- **LTV (Lifetime Value)** - Total revenue per customer
- **LTV:CAC Ratio** - Should be >3:1

### Usage Metrics

- **Scans per user** - Average monthly scans
- **Credits per scan** - Average credits consumed
- **Free → Paid conversion rate** - % of trial users who purchase
- **Churn rate** - % of users who stop using
- **Credit package mix** - Which tiers are most popular

### Product Metrics

- **Trial completion rate** - % who complete first scan
- **BYOK adoption** - % using own API keys vs Clausi AI
- **Preset usage** - % using --preset critical-only
- **Average project size** - Files/tokens per scan

---

## Conclusion

**Current state:** Unsustainable Clausi AI pricing, profitable BYOK model

**Priority actions:**
1. Fix Clausi AI pricing (move to usage-based or increase credit cost)
2. Promote BYOK to improve margins
3. Reduce trial credits to 10
4. Implement caching to reduce AI costs

**Long-term vision:**
- Hybrid model: Freemium + Paid + Enterprise
- Subscription option for predictable revenue
- Self-hosted for large enterprises

**Success metrics:**
- LTV:CAC > 3:1
- Gross margin > 60%
- <5% monthly churn
- 20%+ trial → paid conversion

---

**Last Updated:** 2025-12-24
**Next Review:** Q1 2025 (after analyzing initial user data)
