# Clausi CLI - User Guide

**Complete guide to using Clausi CLI v1.0.0 for AI compliance auditing**

---

## 📖 **Table of Contents**

1. [Getting Started](#getting-started)
2. [Your First Scan](#your-first-scan)
3. [Understanding Results](#understanding-results)
4. [Advanced Features](#advanced-features)
5. [Common Workflows](#common-workflows)
6. [Troubleshooting](#troubleshooting)

---

## 🚀 **Getting Started**

### **Step 1: Installation**

```bash
# Install Clausi CLI
pip install clausi

# Verify installation
clausi --version
# Output: Clausi, version 1.0.0
```

### **Step 2: Get Your API Key**

Clausi uses AI to analyze your code. You'll need an API key from either:

**Option 1: Claude (Anthropic) - Recommended** ⭐
```bash
# Get your key from: https://console.anthropic.com
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Option 2: OpenAI**
```bash
# Get your key from: https://platform.openai.com/api-keys
export OPENAI_API_KEY=sk-your-key-here
```

### **Step 3: Initial Configuration**

```bash
# View available AI models
clausi models list
```

**Output:**
```
Available AI Models
+-------------------------------------------------------+
| Provider | Model                      | Cost/1M tokens |
|----------+----------------------------+----------------|
| Claude   | claude-3-5-sonnet-20241022 | $3 / $15       |
| OpenAI   | gpt-4o                     | $5 / $15       |
+-------------------------------------------------------+

Tip: Claude 3.5 Sonnet is recommended (faster, cheaper, better)
```

```bash
# Set your preferred AI provider (optional)
clausi config set --ai-provider claude

# View your configuration
clausi config show
```

**Output:**
```
Current Configuration
+-------------------------------------------------------+
| Setting              | Value                          |
|----------------------+--------------------------------|
| AI Provider          | claude                         |
| AI Model             | claude-3-5-sonnet-20241022     |
| Selected Regulations | EU-AIA, GDPR, ISO-42001, ...   |
| Output Directory     | clausi/reports                 |
+-------------------------------------------------------+
```

✅ **You're ready to scan!**

---

## 🔍 **Your First Scan**

### **Basic Scan**

```bash
# Scan current directory
clausi scan .

# Or scan specific project
clausi scan /path/to/your/project
```

### **What Happens Next**

#### **1. File Discovery**
```
Starting compliance scan for .
Scanning files...
Found 47 files to analyze
Analyzing 45 files after filtering
```

Clausi automatically:
- ✅ Finds all code files (Python, JavaScript, etc.)
- ✅ Respects `.clausiignore` (like `.gitignore`)
- ✅ Excludes common directories (`node_modules/`, `venv/`, etc.)

#### **2. Cost Estimation**
```
Estimated Token Usage:
Total Tokens: 8,500
- Prompt Tokens: 6,000
- Completion Tokens: 2,500
Estimated Cost: $0.42

Per Regulation Breakdown:

EU AI Act:
- Total Tokens: 8,500
- Estimated Cost: $0.42
```

**What this means:**
- 💰 You'll pay approximately $0.42 for this scan
- 📊 This analyzes your code against all EU AI Act clauses
- ⏱️ Scan will take approximately 30-60 seconds

#### **3. Confirmation Prompt**
```
Proceed with analysis? Estimated cost: $0.42 [y/N]:
```

Type `y` and press Enter to continue.

> **Tip:** Use `--skip-confirmation` to auto-approve scans

#### **4. Analysis Progress**
```
Analyzing compliance... ━━━━━━━━━━━━━━━━━ 100% 0:00:42

Downloading markdown reports...
✓ Downloaded findings.md
✓ Downloaded traceability.md
✓ Downloaded action_plan.md
```

#### **5. Results Display**

**Cache Statistics** (if available):
```
📊 Cache Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cache Hit Rate     80.0%
Files Cached       120 / 150
Tokens Saved       45,000
Cost Saved         $2.25
```

**What this means:**
- ♻️ 80% of your files were already analyzed before (unchanged)
- 💰 You saved $2.25 by not re-analyzing unchanged code
- ⚡ Scan was much faster due to caching

**Findings Summary:**
```
Compliance Findings
+---------------------------------------------------------------+
| Clause    | Status | Severity | Location                     |
|-----------+--------+----------+------------------------------|
| EUAIA-3.1 | ✓      | Critical | src/risk_manager.py:45       |
| EUAIA-7.2 | ✗      | High     | docs/                        |
| EUAIA-9.1 | ✓      | Medium   | src/risk_system.py:120       |
+---------------------------------------------------------------+

Actual Token Usage:
Total tokens used: 8,234
Actual cost: $0.40

Scan completed! Report saved to clausi/reports/
```

**What this means:**
- ✅ **EUAIA-3.1** - Your risk assessment is compliant
- ❌ **EUAIA-7.2** - Missing transparency documentation (HIGH priority)
- ✅ **EUAIA-9.1** - Risk management system is compliant

---

## 📋 **Understanding Results**

### **Files Generated**

After each scan, you'll find these files in `./clausi/reports/`:

```
clausi/reports/
├── findings.md              # 📄 Detailed compliance findings
├── traceability.md          # 🔗 Code-to-clause mapping
├── action_plan.md           # 📝 Step-by-step remediation plan
├── compliance_report.pdf    # 📊 Executive PDF report
└── audit_metadata.json      # 🔍 Technical metadata
```

### **findings.md** (Auto-Opens)

This is your main report. It opens automatically in your default editor.

**Structure:**
```markdown
# Compliance Findings - My AI Project

**Scan Date:** 2025-10-18
**Regulations:** EU AI Act
**Clauses Scanned:** 15
**AI Provider:** Claude 3.5 Sonnet

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
Missing transparency documentation for AI system capabilities.

**Required Actions:**
1. Create transparency documentation
2. Document AI system capabilities
3. Document known limitations
4. Provide user-facing disclosures

**Priority:** HIGH - Must be addressed before deployment
```

### **action_plan.md** - Your Next Steps

```markdown
# Remediation Action Plan

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

## Timeline

| Week | Actions |
|------|---------|
| Week 1 | Create transparency docs |
| Week 2 | Legal review |
| Week 3 | Final compliance scan |
```

### **traceability.md** - Code Mapping

Shows exactly which code files map to which compliance clauses:

```markdown
# Compliance Traceability Matrix

## EUAIA-3.1: Risk Assessment

**Files:**
- `src/risk_manager.py` (lines 45-120)
- `src/risk_types.py` (lines 10-50)
- `config/risk_config.yaml`

**Functions:**
- `assess_risk()` - Main risk assessment
- `calculate_risk_score()` - Risk scoring
```

---

## ⚡ **Advanced Features**

### **1. Clause Scoping** - Reduce Cost by 60-80%

Instead of scanning ALL clauses, focus on what matters:

```bash
# Scan only critical clauses
clausi scan . --preset critical-only

# Result: ~80% faster, ~80% cheaper
# Before: $5.00 → After: $1.00
```

**Available Presets:**

| Preset | Description | Use When |
|--------|-------------|----------|
| `critical-only` | Only critical compliance clauses | Initial assessment |
| `high-priority` | Critical + high priority | Pre-deployment check |
| `documentation` | Documentation-focused clauses | Doc review |

**Custom Clause Selection:**

```bash
# Include specific clauses
clausi scan . --include EUAIA-3.1 --include EUAIA-7.2

# Exclude certain clauses
clausi scan . --exclude EUAIA-9.1

# Interactive picker
clausi scan . --select-clauses
```

**Interactive Example:**
```
Available Clauses for EU-AIA:

 [ ] EUAIA-3.1  Risk Assessment (Critical)
 [x] EUAIA-5.2  High-Risk AI Systems (Critical)
 [x] EUAIA-7.2  Transparency Obligations (High)
 [ ] EUAIA-9.1  Risk Management System (Medium)

Select clauses to scan (space to toggle, enter to continue):
```

### **2. Multi-Model Support** - Choose Your AI

```bash
# Use Claude (default, recommended)
clausi scan . --ai-provider claude

# Use OpenAI GPT-4
clausi scan . --ai-provider openai

# Use specific model
clausi scan . --ai-provider openai --ai-model gpt-4o
```

**Model Comparison:**

| Provider | Model | Speed | Cost | Best For |
|----------|-------|-------|------|----------|
| Claude | claude-3-5-sonnet | ⚡⚡⚡ Fast | $3/$15 | **Compliance** (recommended) |
| OpenAI | gpt-4o | ⚡⚡⚡ Fast | $5/$15 | General purpose |
| OpenAI | gpt-4 | ⚡⚡ Medium | $30/$60 | Deep analysis |

### **3. Markdown-First Workflow**

```bash
# Show markdown preview in terminal
clausi scan . --show-markdown

# Auto-open findings in your editor
clausi scan . --open-findings

# Both together
clausi scan . --show-markdown --open-findings
```

**Terminal Preview:**
```
📋 FINDINGS SUMMARY
============================================================

# Compliance Findings - My Project

**Scan Date:** 2025-10-18
**Compliance Rate:** 80%

## Critical Issues

### ⚠️ EUAIA-7.2: Transparency Documentation Missing
...

(30 more lines)

💡 View full report: ./clausi/reports/findings.md
```

### **4. Multiple Regulations**

```bash
# Scan against multiple regulations
clausi scan . --regulation EU-AIA --regulation GDPR

# Result: Checks both EU AI Act AND GDPR compliance
```

Available Regulations:
- `EU-AIA` - European Union AI Act
- `GDPR` - General Data Protection Regulation
- `ISO-42001` - AI Management System
- `HIPAA` - Health Insurance Portability
- `SOC2` - System and Organization Controls

---

## 💼 **Common Workflows**

### **Workflow 1: Initial Compliance Assessment**

```bash
# 1. Quick scan with critical clauses only
clausi scan . --preset critical-only --skip-confirmation

# 2. Review findings
cat reports/findings.md

# 3. Check action plan
cat reports/action_plan.md

# 4. Fix issues

# 5. Re-scan to verify
clausi scan . --preset critical-only --skip-confirmation
```

**Timeline:** ~15 minutes
**Cost:** ~$1.00

---

### **Workflow 2: Pre-Deployment Full Audit**

```bash
# 1. Full scan with all clauses
clausi scan . \
  --regulation EU-AIA \
  --regulation GDPR \
  --open-findings \
  --show-cache-stats

# 2. Review all reports
# (findings.md auto-opens)

# 3. Check traceability
cat reports/traceability.md

# 4. Follow action plan
cat reports/action_plan.md

# 5. Fix all high-priority issues

# 6. Final verification scan
clausi scan . --skip-confirmation
```

**Timeline:** 1-2 days
**Cost:** $3-5 per scan

---

### **Workflow 3: Continuous Compliance (CI/CD)**

```bash
# In your CI/CD pipeline
export ANTHROPIC_API_KEY=$ANTHROPIC_KEY

# Fail build if critical issues found
clausi scan . \
  --preset critical-only \
  --skip-confirmation \
  --max-cost 2.00 \
  --min-severity high

# Exit code 0 = pass, 1 = fail
```

**Add to `.github/workflows/compliance.yml`:**
```yaml
- name: Compliance Scan
  run: |
    pip install clausi
    clausi scan . --preset critical-only --skip-confirmation
```

---

### **Workflow 4: Cost-Optimized Development**

```bash
# Day 1: Initial scan
clausi scan . --preset critical-only

# Days 2-5: Incremental changes
# (Only changed files analyzed due to caching)
clausi scan . --preset critical-only

# Result:
# - Day 1: $1.00 (full scan)
# - Day 2: $0.20 (80% cache hit)
# - Day 3: $0.15 (85% cache hit)
# - Day 4: $0.10 (90% cache hit)
```

**Savings:** Up to 90% on repeat scans

---

## 🎯 **Power User Tips**

### **1. Create Aliases**

```bash
# Add to ~/.bashrc or ~/.zshrc

# Quick scan
alias cscan='clausi scan . --skip-confirmation'

# Critical only
alias cscan-critical='clausi scan . --preset critical-only --skip-confirmation'

# Full audit
alias cscan-full='clausi scan . --open-findings --show-cache-stats'
```

Usage:
```bash
cscan              # Quick scan
cscan-critical     # Critical clauses only
cscan-full         # Full audit with reports
```

### **2. Ignore Files**

Create `.clausiignore` in your project root:

```
# Exclude test files
tests/
__tests__/
*.test.js
*.spec.py

# Exclude build outputs
dist/
build/
*.min.js

# Exclude dependencies
node_modules/
venv/
.venv/
```

### **3. Project-Specific Config**

Create `.clausi/config.yml` in your project:

```yaml
regulations:
  selected:
    - EU-AIA
    - GDPR

ai:
  provider: claude
  model: claude-3-5-sonnet-20241022

report:
  company_name: "My Company"
  output_dir: "compliance-reports"

ui:
  auto_open_findings: true
  show_cache_stats: true
```

### **4. Track Compliance Over Time**

```bash
# Save metadata for each scan
clausi scan . --output reports/scan-$(date +%Y%m%d)

# Compare scans
diff reports/scan-20251018/audit_metadata.json \
     reports/scan-20251025/audit_metadata.json
```

---

## 🐛 **Troubleshooting**

### **Problem: "No API key found"**

**Error:**
```
Error: ANTHROPIC_API_KEY not found
```

**Solution:**
```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Or add to config
clausi config set --anthropic-key sk-ant-your-key-here

# Verify
clausi config show
```

---

### **Problem: "Estimated cost exceeds maximum"**

**Error:**
```
Error: Estimated cost ($5.42) exceeds maximum cost ($1.00)
```

**Solution:**
```bash
# Option 1: Increase max cost
clausi scan . --max-cost 10.00

# Option 2: Use clause scoping to reduce cost
clausi scan . --preset critical-only

# Option 3: Scan fewer files
echo "tests/" >> .clausiignore
clausi scan .
```

---

### **Problem: "Unicode encoding error" (Windows)**

**Error:**
```
UnicodeEncodeError: 'charmap' codec can't encode...
```

**Solution:**
```bash
# Set UTF-8 encoding
set PYTHONIOENCODING=utf-8
clausi scan .

# Or run in PowerShell
$env:PYTHONIOENCODING="utf-8"
clausi scan .
```

---

### **Problem: Files taking too long to scan**

**Symptoms:**
- Scan stuck at "Analyzing files..."
- Very large codebases (1000+ files)

**Solution:**
```bash
# 1. Exclude unnecessary files
echo "node_modules/" >> .clausiignore
echo "venv/" >> .clausiignore

# 2. Use clause scoping
clausi scan . --preset critical-only

# 3. Scan specific directories
clausi scan ./src --ignore tests
```

---

### **Problem: Cache not working**

**Symptoms:**
- Cache hit rate always 0%
- Full analysis every time

**Solution:**

The cache is on the **backend side**, not local. Cache works when:
- ✅ Same files (same content hash)
- ✅ Same regulation
- ✅ Same clauses

If you're changing files between scans, cache won't help.

---

## 📚 **Next Steps**

### **Learn More**

- 📖 **Backend Integration:** `CLAUDE/BACKEND_INTEGRATION_GUIDE.md`
- 🔄 **What's New:** `CLAUDE/CHANGELOG_v1.0.0.md`
- 🧪 **Testing:** `TESTING.md`
- 🗺️ **Roadmap:** `CLAUDE/CLI_MODERNIZATION_PLAN.md`

### **Get Help**

```bash
# General help
clausi --help

# Command-specific help
clausi scan --help
clausi config --help
```

### **Example Projects**

Try scanning our sample project:
```bash
git clone https://github.com/clausi/examples
cd examples/sample-ai-app
clausi scan . --preset critical-only
```

---

## 🎓 **Quick Reference**

### **Essential Commands**

```bash
# Installation & setup
pip install clausi
clausi --version
clausi models list
clausi config show

# Basic scanning
clausi scan .
clausi scan /path/to/project

# Advanced scanning
clausi scan . --preset critical-only
clausi scan . --ai-provider claude
clausi scan . --open-findings --show-cache-stats

# Configuration
clausi config set --ai-provider claude
clausi config set --anthropic-key sk-ant-...
clausi config show
```

### **Common Flags**

| Flag | Description |
|------|-------------|
| `--preset <name>` | Use clause preset (critical-only, high-priority) |
| `--ai-provider <provider>` | Choose AI (claude, openai) |
| `--skip-confirmation` | Don't ask for confirmation |
| `--open-findings` | Auto-open findings.md |
| `--show-markdown` | Show markdown preview in terminal |
| `--show-cache-stats` | Display cache statistics |
| `--max-cost <amount>` | Fail if cost exceeds amount |
| `--regulation <reg>` | Scan against specific regulation |

---

**Version:** 1.0.0
**Last Updated:** 2025-10-18
**Need Help?** Check our documentation or run `clausi --help`
