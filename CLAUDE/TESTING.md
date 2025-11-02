# Clausi CLI Testing Guide

Quick guide for testing v1.0.0 features.

---

## 🚀 **Quick Start**

### Run All Tests (Against Real Backend)

```bash
python dev_test.py
```

### Run Specific Test

```bash
# Test multi-model support
python dev_test.py --test multi-model

# Test clause scoping
python dev_test.py --test preset

# Test markdown output
python dev_test.py --test markdown

# Test cache statistics
python dev_test.py --test cache

# Full feature test
python dev_test.py --test full
```

### Watch Mode (Auto Re-run on Changes)

```bash
python dev_test.py --watch
```

This will automatically re-run tests whenever you modify files in `clausi/`.

---

## 🔧 **Prerequisites**

### 1. Install CLI in Development Mode

```bash
pip install -e .
```

### 2. Set API Keys

```bash
# For Claude tests
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# For OpenAI tests (optional)
export OPENAI_API_KEY=sk-your-key-here
```

### 3. Verify Installation

```bash
clausi --version  # Should show 1.0.0
```

---

## 📋 **Available Tests**

| Test | Command | Description |
|------|---------|-------------|
| **Multi-Model (Claude)** | `--test multi-model` | Test Claude AI provider |
| **Multi-Model (OpenAI)** | `--test openai` | Test OpenAI provider |
| **Clause Preset** | `--test preset` | Test clause scoping with presets |
| **Clause Include** | `--test include` | Test specific clause inclusion |
| **Markdown Output** | `--test markdown` | Test markdown generation |
| **Cache Statistics** | `--test cache` | Test cache stats display |
| **Models List** | `--test models` | Test models list command |
| **Config Show** | `--test config` | Test config display |
| **Full Feature** | `--test full` | Test all features together |

---

## 🧪 **Testing Against Mock Backend** (Optional)

If you want to test without hitting the real API:

### 1. Start Mock Server

```bash
python tests/mock_backend.py
```

The mock server will run on `http://localhost:5555`

### 2. Run Tests Against Mock

```bash
python dev_test.py --mock
```

---

## 🔄 **Development Workflow**

### Rapid Iteration

```bash
# Terminal 1: Watch mode
python dev_test.py --watch

# Terminal 2: Edit code
# Changes are detected automatically and tests re-run
```

### Test Specific Feature

```bash
# Make changes to clause selector
vim clausi/core/clause_selector.py

# Test just that feature
python dev_test.py --test preset
```

### Manual CLI Testing

```bash
# Test with actual backend
clausi scan tests/fixtures \
  --ai-provider claude \
  --preset critical-only \
  --show-markdown \
  --show-cache-stats

# Check generated reports
ls -l reports/
cat reports/findings.md
```

---

## 📊 **Test Coverage**

### v1.0.0 Features Tested

- ✅ Multi-Model Support
  - Claude (Anthropic) provider
  - OpenAI provider
  - Model selection
  - `clausi models list` command

- ✅ Clause Scoping
  - Presets (critical-only, high-priority)
  - Include specific clauses
  - Exclude specific clauses
  - Cost reduction verification

- ✅ Markdown Output
  - findings.md generation
  - traceability.md generation
  - action_plan.md generation
  - Terminal markdown display
  - Auto-open in editor

- ✅ Cache Statistics
  - Cache hit/miss tracking
  - Token savings calculation
  - Cost savings display
  - Enable/disable via flag

- ✅ Enhanced Progress
  - Detailed progress bars
  - Time estimates
  - Real-time updates

---

## 🎯 **Testing Checklist**

Before releasing changes:

- [ ] All tests pass: `python dev_test.py`
- [ ] Syntax check: `python -m py_compile clausi/**/*.py`
- [ ] Manual smoke test: `clausi scan tests/fixtures`
- [ ] Config commands work: `clausi config show`
- [ ] Models list works: `clausi models list`
- [ ] Markdown files generated in `reports/`
- [ ] Cache stats displayed (if available)
- [ ] No errors in terminal output

---

## 🐛 **Troubleshooting**

### Tests Fail with "Module not found"

```bash
# Reinstall in development mode
pip install -e .
```

### "No API key found"

```bash
# Set your API key
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Or add to config
clausi config set --anthropic-key sk-ant-your-key-here
```

### "Backend connection error"

```bash
# Check if backend is running
curl https://api.clausi.ai/health

# Or use mock backend
python tests/mock_backend.py  # Terminal 1
python dev_test.py --mock     # Terminal 2
```

### Watch Mode Not Detecting Changes

```bash
# Make sure you're editing files in clausi/ directory
# Watch only monitors *.py files in clausi/
```

---

## 📝 **Example Test Output**

```
╭─────────────────────────────────────────╮
│ Clausi CLI v1.0.0 - Feature Test Suite │
│ Backend: https://api.clausi.ai          │
│ Fixtures: tests/fixtures                │
╰─────────────────────────────────────────╯

============================================================
Test 1/9
============================================================

▶ Test 1: Multi-Model - Claude Provider
Command: clausi scan tests/fixtures --ai-provider claude --skip-confirmation

Using AI: claude (claude-3-5-sonnet-20241022)
Starting compliance scan for tests/fixtures
Found 2 files to analyze

Estimated Token Usage:
Total Tokens: 1,500
Estimated Cost: $0.08

Analyzing files...
✓ PASS (3.45s)

[... more tests ...]

============================================================
Test Results Summary
============================================================

 #  Test                                Status      Time
────────────────────────────────────────────────────────
 1  Test 1: Multi-Model - Claude...    ✓ PASS     3.45s
 2  Test 2: Clause Scoping...          ✓ PASS     2.10s
 3  Test 3: Markdown Output...         ✓ PASS     3.22s
 ...

Total: 9 tests
Passed: 9
Failed: 0
Total Time: 25.43s

✓ All tests passed!
```

---

## 🔗 **Related Documentation**

- **Backend Integration:** `CLAUDE/BACKEND_INTEGRATION_GUIDE.md`
- **Changelog:** `CLAUDE/CHANGELOG_v1.0.0.md`
- **CLI Features:** `CLAUDE/CLI_MODERNIZATION_PLAN.md`

---

**Last Updated:** 2025-10-18
**CLI Version:** 1.0.0
