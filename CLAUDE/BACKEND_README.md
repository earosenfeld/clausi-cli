# Backend Team: Where to Start

## 🎯 Quick Navigation

### **"How do I test the CLI like a user would?"**

→ **[USER_GUIDE.md](USER_GUIDE.md)** - Complete user guide with step-by-step instructions

**What you'll learn:**
- ✅ Installing the CLI
- ✅ Setting up API keys
- ✅ Running your first scan
- ✅ Understanding results
- ✅ All CLI commands and flags
- ✅ Common workflows

**Start here to understand the customer experience!**

---

### **"How do I test CLI ↔ Backend integration?"**

→ **[BACKEND_CLI_TESTING_GUIDE.md](BACKEND_CLI_TESTING_GUIDE.md)** - Backend integration testing

**What you'll learn:**
- ✅ Installing CLI to test your backend
- ✅ Pointing CLI to your local backend
- ✅ Testing BYOK vs Credits payment modes
- ✅ Sample curl commands for each endpoint
- ✅ Expected headers and request/response formats
- ✅ Troubleshooting integration issues

**Use this to test your backend implementation!**

---

### **"What's the quick cheat sheet?"**

→ **[BACKEND_QUICK_REFERENCE.md](BACKEND_QUICK_REFERENCE.md)** - One-page reference

**What you'll find:**
- ⚡ 30-second install
- ⚡ 5 essential tests
- ⚡ Expected headers for each mode
- ⚡ Backend checklist

**Keep this open while developing!**

---

### **"What are the API requirements?"**

→ **[BACKEND_INTEGRATION_GUIDE.md](BACKEND_INTEGRATION_GUIDE.md)** - Complete API contract

**What you'll find:**
- 📋 All endpoint specifications
- 📋 Request/response schemas
- 📋 Migration guide
- 📋 Implementation examples

**Use this as your API reference!**

---

## 📚 Recommended Reading Order

### **Day 1: Understand the User Experience**

1. **[USER_GUIDE.md](USER_GUIDE.md)** (20 minutes)
   - Read "Getting Started" section
   - Read "Your First Scan" section
   - Try running a few scans yourself

### **Day 2: Test Integration**

2. **[BACKEND_CLI_TESTING_GUIDE.md](BACKEND_CLI_TESTING_GUIDE.md)** (1 hour)
   - Install CLI locally
   - Point it to your backend
   - Run the integration tests

3. **[BACKEND_INTEGRATION_GUIDE.md](BACKEND_INTEGRATION_GUIDE.md)** (2-4 hours)
   - Implement required endpoints
   - Test with curl commands
   - Verify responses match spec

### **Ongoing: Reference**

4. **[BACKEND_QUICK_REFERENCE.md](BACKEND_QUICK_REFERENCE.md)** (keep open)
   - Quick lookup during development

---

## 🧪 Quick Start (5 Minutes)

**Want to see the CLI in action right now?**

```bash
# 1. Install
pip install clausi

# 2. Set API key (get from https://console.anthropic.com)
export ANTHROPIC_API_KEY=sk-ant-your-key

# 3. Run a scan
cd /path/to/any/code
clausi scan . --regulations EU-AIA --skip-confirmation

# 4. View results
cat clausi/reports/findings.md
```

**That's it!** You just ran the CLI as a customer would.

---

## 💡 Understanding the User Journey

### **1. First-Time User**

```bash
# Install
pip install clausi

# Setup wizard (interactive)
clausi setup

# First scan (with prompts and confirmations)
clausi scan . --regulations EU-AIA
```

**What they see:**
- Cost estimate before scan
- Progress bars during scan
- Success message with report location
- Auto-open findings.md in editor

---

### **2. Experienced User**

```bash
# Quick scan (skip confirmations)
clausi scan . --regulations EU-AIA GDPR --skip-confirmation --open-findings

# Advanced: Clause scoping to reduce cost
clausi scan . --preset critical-only --format all

# Check token balance
clausi tokens
```

---

### **3. Power User**

```bash
# Interactive clause selection
clausi scan . --select-clauses

# Custom output location
clausi scan . --output ~/compliance/2024-10-21

# Multiple formats
clausi scan . --format all --show-cache-stats

# Interactive TUI mode
clausi ui config
```

---

## 🔍 Common Questions

### **Q: Where do reports get saved?**

**A:** Default location is `./clausi/reports/` in the current working directory

```bash
cd /home/user/my-project
clausi scan . --regulations EU-AIA

# Reports saved to:
/home/user/my-project/clausi/reports/
├── findings.md          ← Main findings
├── traceability.md      ← Compliance matrix
├── action_plan.md       ← Recommended actions
└── report.pdf           ← Professional report
```

Users can customize:
```bash
# Via flag
clausi scan . --output /path/to/custom

# Via config
clausi config set --output-dir /path/to/custom

# Via interactive TUI
clausi ui config
```

---

### **Q: What headers does the CLI send to my backend?**

**A:** Depends on payment mode:

**BYOK Mode (Customer provides API key):**
```
POST /api/clausi/scan
X-Clausi-Token: abc123...
X-Anthropic-Key: sk-ant-customer-key    ← Customer's key
Content-Type: application/json
```

**Credits Mode (Backend API key):**
```
POST /api/clausi/scan
X-Clausi-Token: abc123...
# No X-Anthropic-Key - use your backend's key
Content-Type: application/json
```

See [BACKEND_CLI_TESTING_GUIDE.md](BACKEND_CLI_TESTING_GUIDE.md) for details.

---

### **Q: How do I test both payment modes?**

**A:**

**Test BYOK:**
```bash
clausi config set --anthropic-key "sk-ant-customer-key"
clausi scan . --regulations EU-AIA
# CLI sends customer's key to backend
```

**Test Credits:**
```bash
clausi config set --anthropic-key ""  # Remove customer key
clausi scan . --regulations EU-AIA
# CLI does NOT send any AI key - backend uses its own
```

---

### **Q: What's new in v1.0.0?**

**A:** See [CHANGELOG_v1.0.0.md](CHANGELOG_v1.0.0.md)

**Key new features:**
- Multi-model support (Claude + OpenAI)
- Clause scoping (60-80% cost reduction)
- Markdown-first output (auto-generated .md files)
- Enhanced cache statistics
- Interactive TUI mode

**Backend changes required:**
- Handle `ai_provider` and `ai_model` fields
- Handle `clauses_include` / `clauses_exclude` arrays
- Return `run_id`, `cache_stats`, `provider`, `model`
- Implement markdown download endpoints

---

## 🚀 Your Action Plan

### **Step 1: Experience the CLI (30 min)**

```bash
# Install
pip install clausi

# Follow the USER_GUIDE.md "Getting Started" section
# Run a few scans
# Explore the output files
```

### **Step 2: Test Your Backend (1 hour)**

```bash
# Point CLI to your local backend
nano ~/.clausi/config.yml
# Change api.url to http://localhost:10000

# Run the automated test script
./test_backend_integration.sh

# Or follow BACKEND_CLI_TESTING_GUIDE.md manually
```

### **Step 3: Implement Missing Features (2-4 hours)**

```bash
# Follow BACKEND_INTEGRATION_GUIDE.md
# Implement required endpoints
# Test with CLI
# Verify responses
```

---

## 📞 Need Help?

**For understanding user experience:**
- Read: [USER_GUIDE.md](USER_GUIDE.md)
- Try: Install CLI and run scans yourself

**For backend integration:**
- Read: [BACKEND_CLI_TESTING_GUIDE.md](BACKEND_CLI_TESTING_GUIDE.md)
- Read: [BACKEND_INTEGRATION_GUIDE.md](BACKEND_INTEGRATION_GUIDE.md)
- Run: `./test_backend_integration.sh`

**For quick lookup:**
- Keep open: [BACKEND_QUICK_REFERENCE.md](BACKEND_QUICK_REFERENCE.md)

---

## 📁 Documentation Index

```
CLAUDE/
├── BACKEND_README.md              ← YOU ARE HERE
├── USER_GUIDE.md                  ← How users use the CLI
├── BACKEND_CLI_TESTING_GUIDE.md   ← How to test integration
├── BACKEND_QUICK_REFERENCE.md     ← One-page cheat sheet
├── BACKEND_INTEGRATION_GUIDE.md   ← API contract & specs
├── CHANGELOG_v1.0.0.md            ← What's new
├── CLAUDE.md                      ← Developer guide
└── TUI_IMPLEMENTATION.md          ← Interactive mode docs
```

**Quick links:**
- User commands → [USER_GUIDE.md](USER_GUIDE.md)
- Testing guide → [BACKEND_CLI_TESTING_GUIDE.md](BACKEND_CLI_TESTING_GUIDE.md)
- API specs → [BACKEND_INTEGRATION_GUIDE.md](BACKEND_INTEGRATION_GUIDE.md)
- What's new → [CHANGELOG_v1.0.0.md](CHANGELOG_v1.0.0.md)
