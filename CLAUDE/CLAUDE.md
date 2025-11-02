# Claude Developer Guide

**For Future Claude Instances Working on Clausi**

> Last Updated: 2025-10-18
> Repository: clausi-cli (CLI) + clausi (Backend)

---

## 🎯 Core Philosophy

### Keep It Simple
- **Prefer clarity over cleverness** - Write code that's easy to understand
- **One file, one purpose** - Don't create multi-purpose utility files
- **Explicit over implicit** - Clear function names, obvious parameter names
- **No premature optimization** - Make it work first, optimize later if needed

### Consistency Matters
- Follow existing patterns in the codebase
- Match naming conventions already in use
- Don't introduce new paradigms without discussion
- If you see a pattern used 3+ times, follow it

---

## 📁 Repository Structure

### CLI Repository (`clausi-cli/`)

```
clausi-cli/
├── clausi/                      # Main package (NOT clausi_cli!)
│   ├── __init__.py
│   ├── cli.py                   # Main CLI entry point with Click commands
│   ├── api/                     # API client code
│   │   └── client.py            # Backend API communication
│   ├── commands/                # CLI command implementations (if separated)
│   ├── core/                    # Core business logic
│   │   └── payment.py           # Payment flow handling
│   ├── utils/                   # Utility functions
│   │   ├── config.py            # Configuration management
│   │   └── output.py            # Terminal output formatting
│   └── [feature]/               # Feature-specific modules
│
├── tests/                       # All test files
│   ├── fixtures/                # Test data and sample files
│   ├── unit/                    # Unit tests
│   └── integration/             # Integration tests
│
├── CLAUDE/                      # Documentation for Claude instances
│   ├── README.md                # Index of all documentation
│   ├── CLAUDE.md                # This file - development guide
│   ├── USER_GUIDE.md            # End-user documentation
│   ├── TESTING.md               # Testing guide
│   ├── BACKEND_INTEGRATION_GUIDE.md
│   └── [feature]_GUIDE.md       # Feature-specific docs
│
├── README.md                    # Main project README
├── dev_test.py                  # Test runner
├── setup.py                     # Package configuration
└── .clausiignore                # Files to ignore in scans
```

### Backend Repository (`clausi/backend/`)

```
clausi/backend/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── routes/                  # API endpoints
│   │   ├── clausi.py            # Main scan/estimate endpoints
│   │   ├── stripe_webhook.py   # Payment webhooks
│   │   └── claim.py             # Customer claims
│   │
│   ├── services/                # Business logic (NO database access here)
│   │   ├── ai_provider.py       # AI provider abstraction (Claude/OpenAI)
│   │   ├── compliance_analyzer.py  # Core analysis logic
│   │   ├── pdf_report.py        # Report generation
│   │   ├── markdown_report.py   # Markdown reports
│   │   └── [feature]_service.py
│   │
│   ├── core/                    # Core configuration
│   │   └── config.py            # Settings and environment variables
│   │
│   ├── db/                      # Database layer
│   │   ├── base.py              # Database connection
│   │   └── models/              # SQLModel models
│   │
│   └── middleware/              # Request/response middleware
│       └── credits_guard.py     # Token deduction
│
├── regulations/                 # Regulation YAML files
│   ├── eu_aia.yml
│   ├── gdpr.yml
│   └── iso_42001.yml
│
├── CLAUDE/                      # Backend documentation
└── .env                         # Environment variables
```

---

## 📝 Naming Conventions

### Files

**DO:**
- `ai_provider.py` - Lowercase with underscores (snake_case)
- `compliance_analyzer.py` - Descriptive, clear purpose
- `markdown_report.py` - Noun-based names for modules

**DON'T:**
- `utils.py` - Too generic, what utils?
- `helpers.py` - What does it help with?
- `AIProvider.py` - No CamelCase for file names
- `ai-provider.py` - No hyphens in Python files

### Directories

**DO:**
- `services/` - Plural for collection of related files
- `utils/` - When it contains MULTIPLE specific utilities
- `core/` - Central, foundational code

**DON'T:**
- `misc/` - Too vague
- `stuff/` - Not descriptive
- `helpers/` - What are they helping?

### Classes

```python
# DO: Clear, specific names
class ClaudeProvider(AIProvider):
    """Anthropic Claude AI provider implementation."""

class ComplianceAnalyzer:
    """Analyzes code for regulatory compliance."""

# DON'T: Vague or overly generic
class Helper:
class Manager:
class Handler:
```

### Functions

```python
# DO: Verb-based, action-oriented
def get_anthropic_key() -> Optional[str]:
    """Get Anthropic API key from environment or config."""

def create_run_folder(project_name: str, regulation: str) -> Path:
    """Create timestamped output folder for scan results."""

# DON'T: Unclear purpose
def process():
def handle():
def do_stuff():
```

---

## 🏗️ Architecture Patterns

### Layer Separation

**CLI → API Client → Backend**

```python
# ✅ GOOD: Clear separation
# cli.py
result = api_client.estimate(data, api_key)

# api/client.py
def estimate(self, data: Dict, api_key: str) -> Optional[Dict]:
    response = requests.post(f"{self.api_url}/api/clausi/estimate", ...)
    return response.json()

# ❌ BAD: CLI directly calling requests
# cli.py
response = requests.post("https://api.clausi.ai/estimate", ...)
```

### Service Layer (Backend)

**Routes → Services → Database**

```python
# ✅ GOOD: Route delegates to service
# routes/clausi.py
@router.post("/scan")
async def run_audit(request: Request, session: AsyncSession):
    mapper = GPTMapper(regulation=reg, api_key=api_key)
    findings = mapper.map_to_regulations(metadata)

# services/compliance_analyzer.py
class GPTMapper:
    def map_to_regulations(self, metadata: Dict) -> List[Dict]:
        # Business logic here

# ❌ BAD: Route contains business logic
@router.post("/scan")
async def run_audit(...):
    # 200 lines of compliance analysis logic
```

### Configuration Access

```python
# ✅ GOOD: Centralized config
from app.core.config import settings

api_key = settings.ANTHROPIC_API_KEY
provider = settings.AI_PROVIDER

# ❌ BAD: Direct os.getenv everywhere
import os
api_key = os.getenv("ANTHROPIC_API_KEY")
```

---

## 🧪 Testing Philosophy

### Test Structure

```
tests/
├── unit/                        # Fast, isolated tests
│   ├── test_config.py
│   └── test_output.py
├── integration/                 # Tests with external dependencies
│   ├── test_api_client.py
│   └── test_backend_scan.py
└── fixtures/                    # Sample data
    ├── main.py                  # Sample code to scan
    └── utils.py
```

### Test Naming

```python
# ✅ GOOD: Descriptive test names
def test_get_anthropic_key_from_config():
    """Test retrieving Anthropic key from config file."""

def test_scan_with_clause_scoping():
    """Test scan endpoint with clause inclusion filters."""

# ❌ BAD: Generic test names
def test_config():
def test_scan():
```

### Test Runner

We use `dev_test.py` for CLI integration tests:
- Tests run against REAL backend (not mocked)
- Supports watch mode for rapid iteration
- Use `--test <name>` for individual tests

```bash
# Run all tests
python dev_test.py

# Run specific test
python dev_test.py --test models

# Watch mode (auto re-run on changes)
python dev_test.py --watch
```

---

## 📚 Documentation Standards

### CLAUDE/ Directory

All documentation for Claude instances goes in `CLAUDE/`:

- **`README.md`** - Index/table of contents
- **`CLAUDE.md`** - This file (development guide)
- **`USER_GUIDE.md`** - End-user facing documentation
- **`TESTING.md`** - How to run and write tests
- **`[FEATURE]_GUIDE.md`** - Feature-specific implementation docs

### Documentation Format

```markdown
# Clear Title

**Last Updated:** YYYY-MM-DD
**Status:** Active | Deprecated | In Progress

---

## Overview

Brief description of what this covers.

## Key Concepts

- **Concept 1**: Explanation
- **Concept 2**: Explanation

## Implementation

Step-by-step guide with code examples.

## Common Issues

FAQ and troubleshooting.
```

### Code Comments

```python
# ✅ GOOD: Explain WHY, not WHAT
# Use customer's key if provided (BYOK mode), otherwise backend's key (Credits mode)
api_key_to_use = customer_api_key or settings.ANTHROPIC_API_KEY

# ❌ BAD: Obvious comments
# Set api key to customer key or settings key
api_key_to_use = customer_api_key or settings.ANTHROPIC_API_KEY

# ✅ GOOD: Docstrings for public APIs
def get_anthropic_key() -> Optional[str]:
    """
    Get Anthropic API key from environment or config.

    Checks in order:
    1. ANTHROPIC_API_KEY environment variable
    2. api_keys.anthropic in config file

    Returns:
        API key string or None if not found
    """
```

---

## 🚫 What NOT to Do

### Don't Create Generic Utility Files

```python
# ❌ BAD: utils.py with random functions
def format_date(d):
    ...
def send_email(to, subject):
    ...
def parse_json(s):
    ...

# ✅ GOOD: Specific, focused modules
# utils/date_formatter.py
def format_iso_date(date: datetime) -> str:
    ...

# utils/email_sender.py
def send_notification_email(to: str, subject: str, body: str):
    ...
```

### Don't Use Abbreviations

```python
# ❌ BAD: Cryptic names
def proc_rsp(r):
    ...

# ✅ GOOD: Clear, full names
def process_scan_response(response: Dict) -> ScanResult:
    ...
```

### Don't Create Deeply Nested Structures

```python
# ❌ BAD: Too deep
app/services/compliance/analyzers/ai/providers/claude/implementations/

# ✅ GOOD: Flat and clear
app/services/ai_provider.py
app/services/compliance_analyzer.py
```

### Don't Mix Responsibilities

```python
# ❌ BAD: Class doing too much
class ScanManager:
    def validate_input(self): ...
    def call_ai_api(self): ...
    def save_to_database(self): ...
    def send_email(self): ...
    def generate_pdf(self): ...

# ✅ GOOD: Single responsibility
class InputValidator:
    def validate_scan_request(self): ...

class AIProvider:
    def analyze_code(self): ...

class ReportGenerator:
    def generate_pdf(self): ...
```

---

## 🔧 Common Patterns in This Repo

### 1. Configuration Pattern

```python
# Always use the config module
from clausi.utils.config import get_anthropic_key, load_config

api_key = get_anthropic_key()  # Checks env → config → None
config = load_config()
```

### 2. API Client Pattern

```python
# API calls go through client.py
from clausi.api.client import APIClient

client = APIClient(api_url="https://api.clausi.ai")
result = client.estimate(data, api_key)
```

### 3. Rich Console Output

```python
from rich.console import Console

console = Console()
console.print("[green]Success![/green]")
console.print("[red]Error occurred[/red]")
```

### 4. Provider Abstraction Pattern

```python
# Backend uses factory pattern for AI providers
from app.services.ai_provider import get_ai_provider

provider = get_ai_provider(api_key=customer_key)  # Returns ClaudeProvider or OpenAIProvider
result = await provider.analyze_code(code, regulation)
```

### 5. Two Payment Modes

```python
# BYOK (Bring Your Own Key)
if customer_api_key:
    provider = get_ai_provider(api_key=customer_api_key)  # Use customer's key
    cost = 1  # Flat rate: 1 token

# Credits Mode
else:
    provider = get_ai_provider()  # Use backend's key from settings
    cost = calculate_token_cost(ai_tokens_used)  # Variable based on usage
```

---

## 🎨 Code Style

### Python Style

- **PEP 8** compliant
- **Type hints** for function signatures
- **Docstrings** for public APIs
- **Line length**: Aim for 100 chars, max 120

```python
def create_run_folder(
    project_name: str,
    regulation: str,
    timestamp: datetime
) -> Path:
    """
    Create timestamped output folder for scan results.

    Args:
        project_name: Name of the project being scanned
        regulation: Regulation being checked (e.g., "EU-AIA")
        timestamp: Scan start time

    Returns:
        Path to created output folder
    """
    folder_name = f"{project_name}_{regulation}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    output_path = Path("outputs") / folder_name
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path
```

### Import Organization

```python
# Standard library
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Third-party
import click
import requests
from rich.console import Console

# Local
from clausi.api.client import APIClient
from clausi.utils.config import load_config
```

---

## 🔍 Debugging Tips

### Enable Debug Mode

```python
# CLI: Use --debug flag (if implemented)
clausi scan . --debug

# Backend: Check logs
logger.info(f"Processing regulation: {reg}")
logger.error(f"Failed to initialize: {e}")
```

### Test Against Real Backend

```bash
# Make sure tunnel is running
cloudflared tunnel run changeus

# Run tests
python dev_test.py
```

### Check API Keys

```python
# Verify keys are loaded
from clausi.utils.config import get_anthropic_key
print(get_anthropic_key())  # Should show key or None

# Backend
from app.core.config import settings
print(f"Anthropic: {settings.ANTHROPIC_API_KEY[:10]}...")
```

---

## 📦 Package Management

### CLI Installation

```bash
# Development mode (editable install)
cd clausi-cli
pip install -e .

# This allows you to edit code and test without reinstalling
```

### Backend Dependencies

```bash
# Install all dependencies
cd clausi/backend
pip install -r requirements.txt

# Run backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 10000 --reload
```

---

## 🚀 Development Workflow

### 1. Understand the Request
- Read user's request carefully
- Check existing documentation in `CLAUDE/`
- Review similar code in the repo

### 2. Plan the Changes
- Use TodoWrite to track tasks
- Break down into small steps
- Identify which files need changes

### 3. Make Changes
- Follow existing patterns
- Keep changes minimal and focused
- Add/update tests as needed

### 4. Test Changes
- Run relevant tests
- Test manually if needed
- Check for Unicode issues on Windows

### 5. Document
- Update relevant docs in `CLAUDE/`
- Add code comments for complex logic
- Update CHANGELOG if applicable

---

## ⚠️ Platform-Specific Issues

### Windows Console Unicode

**Problem:** Emoji and special characters cause `UnicodeEncodeError` on Windows

**Solution:** Use ASCII-safe alternatives

```python
# ❌ BAD: Unicode characters
console.print("✅ Success!")
console.print("⚡⚡⚡ Fast")

# ✅ GOOD: ASCII-safe
console.print("[green]Success![/green]")
console.print("Fast")
```

**Where this matters:**
- `cli.py` - All terminal output
- `dev_test.py` - Test output
- `output.py` - Progress bars and tables

### Path Handling

```python
# ✅ GOOD: Use pathlib.Path for cross-platform
from pathlib import Path

config_path = Path.home() / ".clausi" / "config.yml"

# ❌ BAD: Hardcoded path separators
config_path = "C:\\Users\\...\\config.yml"
```

---

## 📞 Getting Help

### Check Documentation First

1. `CLAUDE/README.md` - Index of all docs
2. `CLAUDE/USER_GUIDE.md` - How features work
3. `CLAUDE/TESTING.md` - Testing guide
4. `CLAUDE/BACKEND_INTEGRATION_GUIDE.md` - Backend API

### Understanding the Codebase

```bash
# Find where a function is defined
grep -r "def get_anthropic_key" clausi/

# Find where it's used
grep -r "get_anthropic_key()" clausi/

# Check recent changes
git log --oneline -10
```

---

## 🎯 Quick Reference

### File Placement Decision Tree

```
Need to add code?
│
├─ CLI-related?
│  ├─ API communication → clausi/api/
│  ├─ CLI commands → clausi/cli.py
│  ├─ Configuration → clausi/utils/config.py
│  ├─ Terminal output → clausi/utils/output.py
│  └─ Core logic → clausi/core/
│
├─ Backend-related?
│  ├─ API endpoint → backend/app/routes/
│  ├─ Business logic → backend/app/services/
│  ├─ Database → backend/app/db/
│  └─ Config → backend/app/core/config.py
│
├─ Documentation?
│  ├─ For Claude → CLAUDE/
│  ├─ For users → README.md or CLAUDE/USER_GUIDE.md
│  └─ API docs → CLAUDE/BACKEND_INTEGRATION_GUIDE.md
│
└─ Tests?
   ├─ Unit tests → tests/unit/
   ├─ Integration → tests/integration/
   └─ Fixtures → tests/fixtures/
```

---

## 🌟 Best Practices Checklist

Before submitting changes, ask yourself:

- [ ] Did I follow existing naming conventions?
- [ ] Did I put files in the right directories?
- [ ] Did I add type hints to function signatures?
- [ ] Did I write/update tests?
- [ ] Did I update documentation?
- [ ] Did I test on Windows (check for Unicode issues)?
- [ ] Did I keep changes focused and minimal?
- [ ] Did I use existing patterns from the codebase?
- [ ] Did I avoid creating generic utility files?
- [ ] Did I write clear, descriptive names?

---

**Remember:** When in doubt, look at how similar code is already written in the repository. Consistency is more important than any individual preference.

**End of Guide** | Last Updated: 2025-10-18
