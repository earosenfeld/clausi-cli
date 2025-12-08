# CLAUDE.md - AI Developer Guide

> **Purpose:** This document helps AI assistants understand the Clausi CLI architecture and make modifications safely and effectively.

**Last Updated:** 2025-12-07
**Version:** 1.0.0
**Language:** Python 3.8+
**Framework:** Click (CLI), Rich (UI)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Directory Structure](#directory-structure)
3. [Key Components](#key-components)
4. [Request Flow](#request-flow)
5. [Configuration System](#configuration-system)
6. [Common Modifications](#common-modifications)
7. [Error Handling](#error-handling)
8. [Testing](#testing)
9. [Packaging](#packaging)
10. [Important Patterns](#important-patterns)

---

## Architecture Overview

Clausi CLI is a **command-line interface** for AI compliance auditing. It submits code to a backend API (`api.clausi.ai`) for analysis and displays results.

### High-Level Flow

```
User → Interactive Mode OR Direct Command → File Discovery → Backend API → Report Generation
                                                  ↓
                                           Token Estimation
                                                  ↓
                                         AI Provider Selection
```

### Core Responsibilities

1. **Interactive Mode** - Simple prompt-based interface for guided workflows
2. **File Discovery** - Scan directories, apply ignore patterns
3. **Cost Estimation** - Calculate token usage before scanning
4. **AI Provider Selection** - Clausi AI (default), Claude (BYOK), or OpenAI (BYOK)
5. **API Communication** - Send requests to backend with appropriate headers
6. **Report Display** - Download and display markdown/PDF reports
7. **Configuration** - Manage API keys, settings, preferences

---

## Directory Structure

```
clausi-cli/
├── clausi/                      # Main package
│   ├── __init__.py             # Package init
│   ├── __main__.py             # Entry point (python -m clausi)
│   ├── cli.py                  # Main CLI commands (Click)
│   ├── config.example.yml      # Example configuration
│   ├── create_config.py        # Config creation utility
│   │
│   ├── api/                    # API client layer
│   │   ├── __init__.py
│   │   └── client.py           # HTTP client wrapper
│   │
│   ├── core/                   # Business logic
│   │   ├── __init__.py
│   │   ├── clause_selector.py # Interactive clause selection
│   │   ├── payment.py          # Payment flow & scan requests
│   │   └── scanner.py          # File discovery & filtering
│   │
│   ├── utils/                  # Utilities
│   │   ├── __init__.py
│   │   ├── config.py           # Config file management
│   │   ├── emoji.py            # Cross-platform emoji/ASCII
│   │   └── output.py           # Output formatting
│   │
│   ├── tui/                    # Terminal UI
│   │   ├── __init__.py
│   │   ├── interactive.py      # Simple interactive mode (Rich prompts)
│   │   ├── app.py              # Legacy Textual TUI
│   │   └── screens/
│   │       ├── __init__.py
│   │       └── config.py       # Config editor screen
│   │
│   └── templates/              # Report templates
│       ├── default/
│       ├── detailed/
│       └── executive/
│
├── tests/                      # Test suite (excluded from package)
├── CLAUDE/                     # Internal docs (excluded from package)
├── .clausiignore              # Default ignore patterns
├── MANIFEST.in                # Package file inclusion rules
├── pyproject.toml             # Build configuration
├── setup.py                   # Package setup
├── README.md                  # User documentation
└── CLAUDE.md                  # This file

```

---

## Key Components

### 1. `clausi/cli.py` - Main CLI Entry Point

**Lines:** ~994 lines
**Framework:** Click
**Purpose:** Defines all CLI commands and orchestrates the scan flow

#### Key Commands

```python
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Main CLI group - launches interactive mode if no command given"""
    if ctx.invoked_subcommand is None:
        launch_interactive_mode()  # NEW: Interactive mode by default

@cli.command()
def scan(path, claude_model, openai_model, ...):
    """Main scan command"""
    # 1. Determine provider (clausi/claude/openai) from flags
    # 2. Validate API key (if needed)
    # 3. Discover files
    # 4. Get token estimate
    # 5. Get user confirmation
    # 6. Execute scan
    # 7. Download reports
    # 8. Display results

@cli.group()
def config():
    """Configuration management"""

@cli.command()
def setup():
    """First-time setup wizard"""

def launch_interactive_mode():
    """Simple prompt-based interactive mode"""
    # Menu options: scan, config, models, setup, help, quit
```

#### Important Sections

- **Lines 184-241:** API key validation (new simplified logic)
- **Lines 243-259:** Interactive mode launcher
- **Lines 578-596:** Provider determination from --claude/--openai flags
- **Lines 670-740:** Token estimation and scan execution

### 2. `clausi/core/payment.py` - Payment & Scan Requests

**Lines:** ~282 lines
**Purpose:** Handles payment flow, trial accounts, and scan API requests

#### Key Functions

```python
def make_scan_request(api_url, openai_key, provider, data):
    """
    Main scan request function.

    Responsibilities:
    - Prepare headers (X-Anthropic-Key or X-OpenAI-Key)
    - Send request to /api/clausi/scan
    - Handle response (200, 401, 402, 5xx)
    - Error handling (timeouts, connection errors)
    """

def handle_scan_response(response, api_url, openai_key, provider, data):
    """
    Response handler for different HTTP status codes.

    200: Success - return JSON
    401: Trial token created - save and retry
    402: Payment required - open browser
    524: Timeout - show helpful message
    5xx: Server error - user-friendly message
    """

def check_payment_required(api_url, mode):
    """
    Check if payment is required before scanning.
    Opens browser to payment page if needed.
    """
```

#### Modular API Key Handling (CRITICAL)

**payment.py lines 232-240:** Headers are constructed based on provider:

```python
# Only add API key header if we have one (not using Clausi hosted AI)
if api_key:
    if provider == "claude":
        headers["X-Anthropic-Key"] = api_key
    elif provider == "openai":
        headers["X-OpenAI-Key"] = api_key
# If provider == "clausi", no API key header is sent
```

**Three Provider Modes:**
1. **`clausi`** - Clausi hosted AI (default, no API key required)
2. **`claude`** - User's Anthropic API key (`sk-ant-*`)
3. **`openai`** - User's OpenAI API key (`sk-*` or `sk-proj-*`)

### 3. `clausi/core/scanner.py` - File Discovery

**Purpose:** Scan directories and apply ignore patterns

#### Key Functions

```python
def scan_directory(path, extensions=None):
    """
    Recursively scan directory for files.
    Returns list of file paths.
    """

def filter_ignored_files(files, path, ignore_patterns=None):
    """
    Apply .clausiignore and --ignore patterns.
    Uses pathspec library (gitignore-style patterns).
    """

def load_ignore_patterns(path):
    """
    Load .clausiignore from path or parent directories.
    Searches upward like .gitignore.
    """
```

### 4. `clausi/utils/config.py` - Configuration Management

**Purpose:** Read/write config file at `~/.clausi/config.yml`

#### Key Functions

```python
def get_config_path():
    """Returns Path to ~/.clausi/config.yml"""

def load_config():
    """Load YAML config file"""

def save_config(config):
    """Save config to YAML file"""

def get_anthropic_key():
    """Get Anthropic key from env or config"""

def get_openai_key():
    """Get OpenAI key from env or config"""

def get_ai_provider():
    """Get default AI provider from config"""

def get_ai_model(provider):
    """Get default model for provider"""
```

### 5. `clausi/utils/emoji.py` - Cross-Platform Emoji

**Purpose:** Provide emoji on Unix/Mac, ASCII on Windows

#### Implementation

```python
def supports_emoji():
    """Returns False on Windows, True elsewhere"""

EMOJI_MAP = {
    "check": "✓" if supports_emoji() else "[OK]",
    "crossmark": "❌" if supports_emoji() else "[ERROR]",
    "search": "🔍" if supports_emoji() else "[Search]",
    # ... etc
}

def get(name, fallback=""):
    """Get emoji by name with automatic fallback"""
```

**Usage:** `console.print(f"{emoji('check')} Success")`

### 6. `clausi/utils/output.py` - Output Formatting

**Purpose:** Display reports, cache stats, progress bars

#### Key Functions

```python
def download_markdown_files(api_url, run_id, output_dir, api_key):
    """Download findings.md, traceability.md, action_plan.md"""

def display_cache_statistics(cache_stats):
    """Display cache hit rate, tokens saved, cost saved"""

def create_enhanced_progress_bar(description):
    """Create Rich progress bar with spinner"""

def open_in_editor(file_path):
    """Open findings.md in user's default editor"""
```

### 7. `clausi/tui/interactive.py` - Simple Interactive Mode

**Purpose:** Prompt-based interactive interface for guided workflows

#### Key Class

```python
class ClausInteractiveTUI:
    """Simple interactive Clausi interface using Rich prompts"""

    def run(self):
        """Main loop - show menu and handle selections"""
        # Options: scan, config, models, setup, help, quit

    def scan_wizard(self):
        """Interactive scan setup - asks for path, provider, regulations, etc."""

    def config_menu(self):
        """Configuration management - show/set/edit"""
```

**Usage:** Automatically launched when user runs `clausi` with no arguments

---

## Request Flow

### 1. User Interaction

**Option A: Interactive Mode (Default)**
```bash
clausi
# User follows prompts to select path, provider, regulations, etc.
```

**Option B: Direct Command**
```bash
clausi scan . -r EU-AIA             # Uses Clausi AI (default)
clausi scan . -r EU-AIA --claude    # Uses Claude with user's API key
clausi scan . -r EU-AIA --openai gpt-4o  # Uses OpenAI with specific model
```

### 2. CLI Flow (`cli.py:scan()`)

```python
# Step 1: Determine provider from flags
if claude_model is not None:
    provider = "claude"
    model = claude_model if claude_model != "" else config_module.get_ai_model("claude")
elif openai_model is not None:
    provider = "openai"
    model = openai_model if openai_model != "" else config_module.get_ai_model("openai")
else:
    # Default: Clausi hosted AI (no API key needed)
    provider = "clausi"
    model = None

# Step 2: Validate API key (only if using Claude or OpenAI)
api_key = _validate_and_get_api_key(provider, model)
# Returns None for "clausi" provider, API key for "claude"/"openai"

# Step 3: Discover files
files = scanner.scan_directory(path)
files = scanner.filter_ignored_files(files, path, ignore_patterns)

# Step 4: Prepare request data
data = {
    "path": path,
    "regulations": ["EU-AIA"],
    "ai_provider": provider,  # "clausi", "claude", or "openai"
    "ai_model": model,        # Model name or None
    "files": files,
    "estimate_only": True
}

# Step 5: Get token estimate
headers = {"Content-Type": "application/json"}
if api_key:  # Only add if using Claude or OpenAI
    if provider == "claude":
        headers["X-Anthropic-Key"] = api_key
    elif provider == "openai":
        headers["X-OpenAI-Key"] = api_key

response = requests.post(f"{api_url}/api/clausi/estimate", json=data, headers=headers)
estimate = response.json()

# Step 6: Display estimate and get confirmation
console.print(f"Estimated Cost: ${estimate['estimated_cost']:.2f}")
if not click.confirm("Proceed?"):
    sys.exit(0)

# Step 7: Execute scan
data['estimate_only'] = False
result = scan_module.make_async_scan_request(api_url, api_key, provider, data)

# Step 8: Download reports
markdown_files = download_markdown_files(api_url, run_id, output_dir, api_key)

# Step 9: Display results
console.print("[green]Scan complete![/green]")
```

### 3. Simplified CLI Flags (Important!)

**Old Design (Removed):**
```bash
clausi scan . --ai-provider claude --ai-model claude-3-5-sonnet-20241022
clausi scan . --use-claude-code  # Confusing name
```

**New Design (Current):**
```bash
# Default: Clausi hosted AI (no flag needed)
clausi scan .

# Use Claude with default model
clausi scan . --claude

# Use Claude with specific model
clausi scan . --claude claude-3-5-sonnet-20241022

# Use OpenAI with specific model
clausi scan . --openai gpt-4o
```

**Key Changes:**
- ❌ Removed `--use-claude-code` (was confusing, implied local execution)
- ❌ Removed `--ai-provider` (redundant with specific flags)
- ❌ Removed `--ai-model` (model is now the value of --claude/--openai)
- ✅ Added `--claude [MODEL]` - Use Claude, optionally specify model
- ✅ Added `--openai [MODEL]` - Use OpenAI, optionally specify model
- ✅ Default behavior - Use Clausi hosted AI (no API key required)

**Flag Logic:**
- If neither `--claude` nor `--openai` is provided → `provider = "clausi"` (default)
- If `--claude` is provided → `provider = "claude"`, model is the flag value or default
- If `--openai` is provided → `provider = "openai"`, model is the flag value or default

### 4. Backend API Endpoints

#### `/api/clausi/estimate` (POST)
```json
Request:
{
  "path": "/path/to/code",
  "files": ["file1.py", "file2.py"],
  "regulations": ["EU-AIA"],
  "ai_provider": "claude",
  "ai_model": "claude-3-5-sonnet-20241022",
  "estimate_only": true
}

Response:
{
  "total_tokens": 6631,
  "prompt_tokens": 4987,
  "completion_tokens": 1644,
  "estimated_cost": 0.04,
  "regulation_breakdown": [...],
  "file_breakdown": [...]
}
```

#### `/api/clausi/scan` (POST)
```json
Request: (same as estimate but estimate_only: false)

Response:
{
  "findings": [...],
  "token_usage": {"total_tokens": 6500, "cost": 0.039},
  "run_id": "abc123",
  "cache_stats": {"cache_hit_rate": 0.8, ...}
}
```

#### `/api/clausi/report/{run_id}/findings.md` (GET)
Downloads markdown report file

---

## Configuration System

### Config File Location

- **Windows:** `%USERPROFILE%\.clausi\config.yml`
- **macOS/Linux:** `~/.clausi/config.yml`

### Config Structure

```yaml
# AI Provider Settings
ai:
  provider: claude              # claude or openai
  model: claude-3-5-sonnet-20241022
  fallback_provider: openai
  fallback_model: gpt-4

# API Keys
api_keys:
  anthropic: sk-ant-...         # Or use ANTHROPIC_API_KEY env
  openai: sk-...                # Or use OPENAI_API_KEY env

# API Settings
api:
  url: https://api.clausi.ai
  timeout: 300
  max_retries: 3

# Report Settings
report:
  format: pdf
  output_dir: clausi/reports
  company_name: Your Company
  company_logo: /path/to/logo.png
  template: default             # default | detailed | executive

# Default Regulations
regulations:
  selected:
    - EU-AIA
    - GDPR

# UI Preferences
ui:
  auto_open_findings: true      # Auto-open findings.md
  show_cache_stats: true        # Display cache statistics
```

### Configuration Precedence

1. **CLI flags** (highest priority)
2. **Environment variables** (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CLAUSI_TUNNEL_BASE`)
3. **Config file** (`~/.clausi/config.yml`)
4. **Defaults** (lowest priority)

---

## Common Modifications

### Adding a New Regulation

**File:** `clausi/cli.py`

```python
# Line ~51
REGULATIONS = {
    "EU-AIA": {
        "name": "EU AI Act",
        "description": "European Union Artificial Intelligence Act",
    },
    "GDPR": {...},
    # Add new regulation here:
    "MY-REG": {
        "name": "My Regulation",
        "description": "Description of my regulation",
    },
}
```

**File:** `setup.py` (if adding to defaults)

```python
# Line ~93 (in create_config method)
"regulations": {
    "selected": ["EU-AIA", "GDPR", "MY-REG"]  # Add here
}
```

### Adding a New AI Provider

**1. Add new CLI flag:**

`clausi/cli.py` (around line 548)
```python
@click.option("--claude", "claude_model", default=None, help="Use Claude...")
@click.option("--openai", "openai_model", default=None, help="Use OpenAI...")
@click.option("--gemini", "gemini_model", default=None, help="Use Gemini (optionally specify model)")  # NEW
```

**2. Add provider detection logic:**

`clausi/cli.py` (around line 580)
```python
if claude_model is not None:
    provider = "claude"
    model = claude_model if claude_model != "" else config_module.get_ai_model("claude")
elif openai_model is not None:
    provider = "openai"
    model = openai_model if openai_model != "" else config_module.get_ai_model("openai")
elif gemini_model is not None:  # NEW
    provider = "gemini"
    model = gemini_model if gemini_model != "" else config_module.get_ai_model("gemini")
else:
    provider = "clausi"  # Default
    model = None
```

**3. Add API key validation:**

`clausi/cli.py` in `_validate_and_get_api_key()` (around line 220)
```python
elif provider == "gemini":
    api_key = config_module.get_gemini_key()
    if not api_key:
        # Show error message with instructions
        sys.exit(1)
    return api_key
```

**4. Add API key retrieval:**

`clausi/utils/config.py`
```python
def get_gemini_key():
    """Get Gemini API key from config or environment"""
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    config = load_config()
    return config.get("api_keys", {}).get("gemini", "")
```

**5. Update header logic:**

`clausi/core/payment.py` (around line 238)
```python
if api_key:
    if provider == "claude":
        headers["X-Anthropic-Key"] = api_key
    elif provider == "openai":
        headers["X-OpenAI-Key"] = api_key
    elif provider == "gemini":  # NEW
        headers["X-Gemini-Key"] = api_key
```

**6. Update backend:** (in backend repo)
Backend's `ai_provider.py` needs to detect new provider and key prefix pattern.

### Adding a New CLI Command

```python
# In clausi/cli.py

@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output file")
def my_new_command(path, output):
    """Description of my new command."""
    console.print(f"Running my new command on {path}")

    # Your logic here

    console.print("[green]Done![/green]")
```

### Adding Error Handling for New HTTP Status

`clausi/core/payment.py:100-146` (in `handle_scan_response`)

```python
elif response.status_code == 429:  # Rate limit
    console.print(f"[yellow]Rate Limit Exceeded (Error 429)[/yellow]")
    console.print("\nYou've exceeded the API rate limit.")
    console.print("Please wait a few minutes and try again.")
```

### Customizing Output Directory Default

**File:** `clausi/cli.py:208`

```python
def ensure_output_dir(path: str, output_dir: Optional[str] = None) -> Path:
    if output_dir:
        output_path = Path(output_dir)
    else:
        # Change this line to customize default:
        output_path = Path.cwd() / "my_custom_reports"  # Was: clausi/reports
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path
```

---

## Error Handling

### Error Handling Strategy

1. **Network Errors** - Catch `requests.exceptions.*` and display user-friendly messages
2. **HTTP Errors** - Detect HTML vs JSON responses, show appropriate guidance
3. **Timeouts** - Suggest reducing file count or using presets
4. **File Errors** - Validate file existence before operations

### Key Error Handlers

**Timeout Handling:** `clausi/core/payment.py:256-266`
```python
except requests.exceptions.Timeout:
    console.print(f"\n{emoji('crossmark')} [bold red]Request Timeout[/bold red]")
    console.print("\nThe scan request timed out after 5 minutes.")
    # ... helpful suggestions
```

**HTML Error Detection:** `clausi/core/payment.py:104-146`
```python
content_type = response.headers.get('Content-Type', '')
is_html = 'text/html' in content_type or response.text.strip().startswith('<!DOCTYPE')

if response.status_code == 524 and is_html:
    # Cloudflare timeout - show helpful message instead of HTML dump
```

---

## Testing

### Test Structure

```
tests/
├── fixtures/           # Test data
├── test_cli.py        # CLI command tests
└── test_v1_features.py # Feature integration tests
```

### Running Tests

```bash
# Install dev dependencies
pip install -e .[dev]

# Run all tests
pytest tests/

# Run specific test
pytest tests/test_cli.py::test_scan_command

# Run with coverage
pytest --cov=clausi tests/
```

### Testing Checklist (After Modifications)

1. **Build Package:** `python -m build`
2. **Check Package Contents:** `tar -tzf dist/clausi-*.tar.gz`
3. **Install Locally:** `pip install dist/clausi-*.whl --force-reinstall`
4. **Test Command:** `clausi --help`, `clausi scan --help`
5. **Test Actual Scan:** `clausi scan /path/to/test/project`

---

## Packaging

### Build System

- **Build tool:** `setuptools` + `build`
- **Config files:** `pyproject.toml`, `setup.py`, `MANIFEST.in`

### Package Files Inclusion

**MANIFEST.in controls what's included:**

```
include README.md LICENSE pyproject.toml .clausiignore
recursive-include clausi *.py *.yml *.yaml *.css
recursive-exclude CLAUDE *
recursive-exclude tests *
global-exclude *.pyc __pycache__
```

### Building for PyPI

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build distributions
python -m build

# Check package
twine check dist/*

# Upload to PyPI (when ready)
twine upload dist/*
```

### Version Bumping

Update version in **3 places**:
1. `setup.py:110` - `version="1.0.0"`
2. `clausi/__init__.py` - `__version__ = "1.0.0"`
3. `clausi/cli.py:226` - `@click.version_option(version="1.0.0")`

---

## Important Patterns

### 1. Emoji Usage (Cross-Platform)

**Always use:** `from clausi.utils.emoji import get as emoji`

```python
# Good
console.print(f"{emoji('check')} Success")

# Bad - will crash on Windows
console.print("✓ Success")
```

### 2. Configuration Loading

**Always use config utilities:**

```python
# Good
from clausi.utils.config import get_anthropic_key
api_key = get_anthropic_key()  # Checks env then config

# Bad - misses environment variable
config = load_config()
api_key = config["api_keys"]["anthropic"]
```

### 3. Error Messages

**Always provide actionable guidance:**

```python
# Good
console.print(f"{emoji('crossmark')} Error: File not found")
console.print("\nPlease check:")
console.print("  1. The file path is correct")
console.print("  2. You have read permissions")

# Bad
console.print("Error: File not found")
```

### 4. Path Handling

**Always use Path objects:**

```python
# Good
from pathlib import Path
output_path = Path.cwd() / "clausi" / "reports"
output_path.mkdir(parents=True, exist_ok=True)

# Bad
import os
output_path = os.path.join(os.getcwd(), "clausi", "reports")
os.makedirs(output_path)
```

### 5. API Headers (Modular)

**Always branch on provider:**

```python
# Good
if provider == "claude":
    headers["X-Anthropic-Key"] = api_key
elif provider == "openai":
    headers["X-OpenAI-Key"] = api_key

# Bad - hardcoded
headers["X-OpenAI-Key"] = api_key  # Won't work for Claude!
```

### 6. Backward Compatibility

**When adding new features, maintain old behavior:**

```python
# Good
def scan(path, new_option=None):
    if new_option is None:
        new_option = get_default()  # Maintain old behavior
    # ...

# Bad
def scan(path, new_option):  # Breaking change - required parameter
```

---

## Quick Reference

### File Locations

| What | Where |
|------|-------|
| Main CLI | `clausi/cli.py` |
| Interactive mode | `clausi/tui/interactive.py` |
| Scan requests | `clausi/core/payment.py` |
| File discovery | `clausi/core/scanner.py` |
| Config management | `clausi/utils/config.py` |
| Emoji handling | `clausi/utils/emoji.py` |
| Output formatting | `clausi/utils/output.py` |
| API client | `clausi/api/client.py` |

### Important Functions

| What | File:Lines |
|------|-----------|
| Interactive mode launcher | `cli.py:243-259` |
| Provider determination | `cli.py:578-596` |
| API key validation | `cli.py:184-241` |
| Main scan function | `cli.py:565-900` |
| Token estimation | `cli.py:670-740` |
| Async scan request | `payment.py:216-330` |
| Header construction | `payment.py:232-240` |
| Error handling | `payment.py:various` |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `rich` | Terminal formatting and prompts |
| `requests` | HTTP client |
| `pyyaml` | Config file parsing |
| `pathspec` | .gitignore-style patterns |
| `textual` | TUI framework (legacy) |
| `openai` | OpenAI SDK (key validation) |

### Common Commands

| Command | Description |
|---------|-------------|
| `clausi` | Launch interactive mode |
| `clausi scan .` | Scan current directory (Clausi AI) |
| `clausi scan . --claude` | Scan with Claude (your API key) |
| `clausi scan . --openai gpt-4o` | Scan with OpenAI |
| `clausi scan . -r EU-AIA -r GDPR` | Multi-regulation scan |
| `clausi scan . --preset critical-only` | Scoped scan |
| `clausi config show` | View configuration |
| `clausi config set --anthropic-key <key>` | Set API key |
| `clausi models list` | List available models |

---

## Debugging Tips

### Enable Verbose Output

```bash
# Add --verbose flag to scan command
clausi scan . --verbose
```

### Check Config

```bash
# View current configuration
clausi config show

# View config file location
clausi config path

# Edit config directly
clausi config edit
```

### Test API Connection

```bash
# Use CLAUSI_TUNNEL_BASE for local testing
export CLAUSI_TUNNEL_BASE=http://localhost:10000
clausi scan .
```

### Check Package Contents

```bash
# After building
tar -tzf dist/clausi-*.tar.gz | less
```

### Test Installation

```bash
# Install from local wheel
pip install dist/clausi-*.whl --force-reinstall

# Test command
clausi --version
clausi --help
```

---

## Contact & Resources

- **Repository:** `https://github.com/clausi/clausi-cli`
- **Documentation:** `https://docs.clausi.ai`
- **Backend API:** `https://api.clausi.ai`
- **PyPI Package:** `https://pypi.org/project/clausi/`

---

**End of CLAUDE.md**

*This document should be updated whenever significant architectural changes are made to the CLI.*

---

## Recent Changes (2025-12-07)

1. **Interactive Mode** - Running `clausi` with no args now launches a simple interactive menu
2. **Simplified Flags** - Removed `--use-claude-code`, `--ai-provider`, `--ai-model`; added `--claude [MODEL]` and `--openai [MODEL]`
3. **Default Provider** - Default is now "clausi" (hosted AI, no API key required)
4. **Provider Logic** - Simplified to three modes: clausi (default), claude (BYOK), openai (BYOK)
5. **Interactive UI** - New `clausi/tui/interactive.py` with Rich-based prompts instead of Textual
