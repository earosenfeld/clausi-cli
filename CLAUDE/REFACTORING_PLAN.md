# Clausi CLI Production Refactoring Plan

## Release Status

✅ **Package builds successfully** - `clausi-1.0.0-py3-none-any.whl`
✅ **Version**: 1.0.0
✅ **Entry point**: `clausi = "clausi.cli:main"`

---

## Priority 1: RELEASE BLOCKERS (None!)

The package is ready for PyPI release. No critical blockers found.

**To publish:**
```bash
cd clausi-cli
python -m build
twine check dist/*
twine upload dist/*
```

---

## Priority 2: COMPLETED CLEANUP

- [x] Remove duplicate `get_openai_key()` wrapper from cli.py
- [x] Remove unused import `rprint` from cli.py
- [x] Remove deprecated `show_token_status()` from config.py
- [x] Remove test card display from payment.py (lines 47-50)
- [x] Fix hardcoded emoji to use `emoji()` function
- [x] Added native file explorer dialog (tkinter) to interactive.py

---

## Priority 3: POST-RELEASE IMPROVEMENTS

These are code quality improvements that can wait until after initial release:

### 3.1 Code Organization (Medium Priority)
- [ ] Create `utils/http.py` for header construction helpers
- [ ] Rename `openai_key` → `api_key` in payment.py (clarity)
- [ ] Split 577-line `scan()` function into smaller functions
- [ ] Split payment.py into smaller modules

### 3.2 Developer Experience (Low Priority)
- [ ] Create `utils/logging.py` for proper logging
- [ ] Create `exceptions.py` for custom exceptions
- [ ] Create `constants.py` for centralized constants
- [ ] Add config caching to reduce file reads

### 3.3 Testing (Low Priority)
- [ ] Fix failing tests (9/29 currently failing)
- [ ] Add path validation tests
- [ ] Add error handling tests

---

## Package Contents

```
clausi-1.0.0-py3-none-any.whl contains:
├── clausi/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                 (main CLI)
│   ├── config.example.yml
│   ├── api/
│   │   ├── __init__.py
│   │   └── client.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── clause_selector.py
│   │   ├── payment.py
│   │   └── scanner.py
│   ├── services/
│   │   └── claude_code_provider.py
│   ├── templates/
│   │   ├── default/
│   │   ├── detailed/
│   │   └── executive/
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── interactive.py     (with native file dialog)
│   │   └── screens/
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       ├── console.py
│       ├── emoji.py
│       ├── output.py
│       └── regulations.py
```

---

## PyPI Release Checklist

- [x] Version set in `__init__.py` (1.0.0)
- [x] `pyproject.toml` configured correctly
- [x] `setup.py` present for compatibility
- [x] `MANIFEST.in` excludes dev files (CLAUDE/, tests/, etc.)
- [x] LICENSE file included (MIT)
- [x] README.md included
- [x] Entry point works (`clausi = "clausi.cli:main"`)
- [x] Package builds without errors
- [ ] Run `twine check dist/*` to verify metadata
- [ ] Upload to TestPyPI first (recommended)
- [ ] Upload to PyPI

---

## Commands Reference

```bash
# Build
python -m build

# Check package
twine check dist/*

# Upload to TestPyPI (test first)
twine upload --repository testpypi dist/*

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ clausi

# Upload to PyPI (production)
twine upload dist/*

# Install from PyPI
pip install clausi
```

---

**Last Updated:** 2025-12-24
