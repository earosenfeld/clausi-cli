# Clausi CLI Test Suite

Test infrastructure for Clausi CLI v1.0.0.

---

## 📁 **Structure**

```
tests/
├── README.md                    # This file
├── mock_backend.py              # Mock API server for offline testing
├── test_v1_features.py          # Unit tests for v1.0.0 features
├── test_cli_payment_flow.py     # Payment flow tests
├── test_payment_scenario.py     # Payment scenarios
├── test_real_payment_flow.py    # Real backend integration tests
└── fixtures/                    # Sample files for testing
    ├── main.py                  # Sample AI application
    └── utils.py                 # Sample utilities
```

---

## 🚀 **Quick Start**

### Run All Tests (Real Backend)

```bash
# From project root
python dev_test.py
```

### Run Specific Tests

```bash
# Test multi-model support
python dev_test.py --test multi-model

# Test clause scoping
python dev_test.py --test preset

# Test markdown output
python dev_test.py --test markdown
```

### Watch Mode

```bash
# Auto re-run on file changes
python dev_test.py --watch
```

---

## 🧪 **Test Types**

### 1. Integration Tests (`dev_test.py`)

Tests against **real backend API**:
- Multi-model support (Claude + OpenAI)
- Clause scoping with presets
- Markdown output generation
- Cache statistics display
- Full feature integration

**Usage:**
```bash
python dev_test.py              # Run all
python dev_test.py --test full  # Full feature test
python dev_test.py --watch      # Watch mode
```

### 2. Unit Tests (`test_v1_features.py`)

Tests individual modules with mocks:
- Clause selector presets
- Output formatting
- Cache statistics display
- Config management

**Usage:**
```bash
pytest tests/test_v1_features.py -v
```

### 3. Mock Backend (`mock_backend.py`)

Standalone Flask server for offline testing:
- Returns realistic mock responses
- No real API calls
- Fast iteration

**Usage:**
```bash
# Terminal 1: Start mock server
python tests/mock_backend.py

# Terminal 2: Run tests against mock
export CLAUSI_TUNNEL_BASE=http://localhost:5555
python dev_test.py
```

---

## 📝 **Test Fixtures**

Sample files in `fixtures/` used for testing:

- `main.py` - Sample AI model with risk assessment
- `utils.py` - Sample utility functions

**Add more fixtures:**
```bash
# Create new test file
echo "def test_function(): pass" > tests/fixtures/example.py

# Tests will automatically include it
python dev_test.py --test full
```

---

## 🎯 **Testing Workflow**

### Development Iteration

```bash
# 1. Start watch mode
python dev_test.py --watch

# 2. Edit code (changes auto-detected)
vim clausi/core/clause_selector.py

# 3. Tests re-run automatically
# (observe results in terminal)
```

### Before Committing

```bash
# 1. Run all integration tests
python dev_test.py

# 2. Run unit tests
pytest tests/test_v1_features.py -v

# 3. Syntax check
python -m py_compile clausi/**/*.py

# 4. Manual smoke test
clausi scan tests/fixtures --skip-confirmation
```

---

## 🔧 **Mock Backend Endpoints**

When running `tests/mock_backend.py`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/clausi/estimate` | POST | Token estimation |
| `/api/clausi/scan` | POST | Compliance scan |
| `/api/clausi/check-payment-required` | POST | Payment check |
| `/api/clausi/report/{run_id}/{filename}` | GET | Download markdown |
| `/health` | GET | Health check |

**Mock Features:**
- Adjusts estimates based on clause scoping
- Returns realistic findings
- Generates markdown content
- Simulates cache statistics

---

## 📊 **Expected Test Results**

All tests should pass:

```
============================================================
Test Results Summary
============================================================

 #  Test                                Status      Time
────────────────────────────────────────────────────────
 1  Test 1: Multi-Model - Claude...    ✓ PASS     3.45s
 2  Test 2: Clause Scoping...          ✓ PASS     2.10s
 3  Test 3: Markdown Output...         ✓ PASS     3.22s
 4  Test 4: Cache Statistics...        ✓ PASS     2.88s
 5  Test 5: Full Feature Test...       ✓ PASS     4.15s

Total: 5 tests
Passed: 5
Failed: 0
Total Time: 15.80s

✓ All tests passed!
```

---

## 🐛 **Troubleshooting**

### Tests Fail: "Module not found"

```bash
pip install -e .
```

### Tests Fail: "No API key"

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Mock Server Won't Start

```bash
# Check if port 5555 is in use
lsof -i :5555

# Kill existing process
kill -9 <PID>

# Restart
python tests/mock_backend.py
```

### Watch Mode Not Working

Make sure you're editing files in `clausi/` directory - only `*.py` files in `clausi/` are watched.

---

## 📚 **Related Documentation**

- **Testing Guide:** `../TESTING.md` (detailed guide)
- **Backend Integration:** `../CLAUDE/BACKEND_INTEGRATION_GUIDE.md`
- **Changelog:** `../CLAUDE/CHANGELOG_v1.0.0.md`

---

**Last Updated:** 2025-10-18
**CLI Version:** 1.0.0
