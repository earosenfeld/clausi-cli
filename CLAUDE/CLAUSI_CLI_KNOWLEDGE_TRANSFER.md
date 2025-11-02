# Clausi CLI - Knowledge Transfer Document

**Generated:** 2025-10-13
**Last Updated:** 2025-10-18
**Version:** 1.0.0 (updated from 0.3.0)
**Project:** Clausi AI Compliance Auditing Tool - Command-Line Interface

---

## ⚠️ **Important Update Notice - v1.0.0**

**This document was originally written for v0.3.0 and contains outdated information.**

**Key Changes in v1.0.0:**

1. **Package renamed:** `clausi_cli` → `clausi`
2. **New structure:** Industry-standard organization with `commands/`, `core/`, `api/`, `utils/`
3. **Multi-model support:** Claude (default) + OpenAI GPT-4
4. **Clause scoping:** Granular clause selection with presets
5. **Markdown-first:** Auto-generated markdown reports with auto-open
6. **Enhanced progress:** Cache statistics and detailed progress bars

**📚 For Current Documentation:**
- Architecture changes: See new structure in [Project Structure](#project-structure) section below (updated)
- Backend integration: See `BACKEND_INTEGRATION_GUIDE.md`
- What's new: See `CHANGELOG_v1.0.0.md`
- Roadmap: See `CLI_MODERNIZATION_PLAN.md`

**⚠️ Sections marked with "❌ OUTDATED" need review before use.**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Core Components](#core-components)
6. [Command-Line Interface](#command-line-interface)
7. [Configuration Management](#configuration-management)
8. [File Scanning & Filtering](#file-scanning--filtering)
9. [Backend Integration](#backend-integration)
10. [Payment & Trial System](#payment--trial-system)
11. [Report Generation](#report-generation)
12. [GitHub Actions Integration](#github-actions-integration)
13. [Development Setup](#development-setup)
14. [Testing](#testing)
15. [Distribution & Packaging](#distribution--packaging)
16. [Known Issues & Technical Debt](#known-issues--technical-debt)
17. [Future Improvements](#future-improvements)

---

## Executive Summary

Clausi CLI is a **command-line interface** for auditing software projects against regulatory frameworks including EU AI Act, GDPR, ISO 42001, HIPAA, and SOC 2. It's a Python-based tool built with Click that:

- **Scans codebases** for compliance issues using Claude (Anthropic) or OpenAI GPT-4
- **Communicates with backend API** at https://api.clausi.ai
- **Generates compliance reports** in PDF, HTML, JSON, and **Markdown** formats
- **Auto-opens findings** in default editor for immediate review
- **Manages trial system** with automatic token provisioning (20 free credits)
- **Integrates with GitHub Actions** for CI/CD compliance checks
- **Supports .clausiignore** files for excluding files from analysis
- **Clause scoping** to reduce scan time and cost by 60-80%
- **Cache statistics** for transparency into performance and cost savings

**Key User Flows:**
1. **First-time user:** `clausi setup` → Configure API keys → `clausi scan .`
2. **Scoped scan:** `clausi scan . --preset critical-only` → 80% faster, cheaper
3. **Multi-model:** `clausi scan . --ai-provider claude` → Use Claude (default) or OpenAI
4. **Markdown workflow:** Scan → `findings.md` auto-opens → Review → Fix → Commit

**Distribution:**
- Published on PyPI as `clausi`
- Installable via `pip install clausi`
- Version: **1.0.0** (released 2025-10-18)

---

## System Architecture (v1.0.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                         User's Machine                          │
│                                                                 │
│  ┌──────────────┐         ┌──────────────────┐                 │
│  │ clausi scan  │────────▶│  core/           │                 │
│  │  (CLI cmd)   │         │  - payment.py    │                 │
│  │              │         │  - scanner.py    │                 │
│  └──────────────┘         │  - clause_select │                 │
│         │                 └──────────────────┘                 │
│         ▼                          │                            │
│  ┌──────────────┐         ┌───────▼──────────┐                 │
│  │   cli.py     │────────▶│  utils/          │                 │
│  │ (orchestrate)│         │  - config.py     │                 │
│  │              │         │  - output.py     │                 │
│  └──────────────┘         └──────────────────┘                 │
│         │                          │                            │
│         │                          │                            │
└─────────┼──────────────────────────┼────────────────────────────┘
          │                          │
          │         HTTPS            │
          ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Clausi Backend API                             │
│                  https://api.clausi.ai                          │
│                                                                 │
│  POST /api/clausi/estimate         - Token estimation          │
│  POST /api/clausi/scan             - Compliance scanning       │
│  POST /api/clausi/check-payment    - Payment requirements      │
│  GET  /api/clausi/report/{run_id}/{filename} - Markdown DL     │
│  POST /api/claim                   - Token claiming            │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│              AI Providers (Multi-Model Support)                 │
│  • Anthropic Claude API (default)                              │
│  • OpenAI GPT-4 API                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Request Flow (v1.0.0):**
1. User runs `clausi scan /path/to/project`
2. CLI checks payment requirements (if full mode)
3. CLI scans directory using `core/scanner.py`
4. CLI applies `.clausiignore` patterns
5. **NEW:** User selects clauses (if `--select-clauses` or `--preset`)
6. CLI calls `/estimate` with AI provider + clause scope
7. User confirms scan (or `--skip-confirmation`)
8. CLI calls `/scan` with API keys + clause selection
9. Backend analyzes with chosen AI provider (Claude or OpenAI)
10. **NEW:** Backend returns findings + `run_id` + cache stats
11. CLI downloads reports (PDF/HTML/JSON)
12. **NEW:** CLI downloads markdown files (`findings.md`, etc.)
13. **NEW:** CLI auto-opens `findings.md` in editor
14. **NEW:** CLI displays cache statistics
15. CLI displays findings table and saves metadata

---

## Technology Stack

### Core Framework
- **Click** 8.0.0+ - Command-line interface framework
- **Python** 3.7+ - Programming language (supports 3.7-3.10)

### UI & Display
- **Rich** 10.0.0+ - Terminal formatting, tables, progress bars
- **Console** - Color output and formatting

### Data Handling
- **PyYAML** 5.4.1+ - Configuration file parsing
- **Requests** 2.26.0+ - HTTP client for API calls
- **pathspec** 0.10.0+ - .gitignore-style file matching

### AI Integration
- **OpenAI** 1.0.0+ - OpenAI API client (key validation)

### Utilities
- **python-dotenv** 0.19.0+ - Environment variable management
- **pathlib** - Path manipulation (built-in)
- **webbrowser** - Payment page opening (built-in)

---

## Project Structure (v1.0.0 - Industry Standard)

```
clausi-cli/                        # Repository root
├── clausi/                        # Main package (renamed from clausi_cli)
│   ├── __init__.py               # Package initialization (v1.0.0)
│   ├── __main__.py               # Python -m clausi support
│   │
│   ├── cli.py                    # CLI orchestrator (~950 lines)
│   │   # Main entry point, coordinates commands
│   │
│   ├── commands/                 # CLI command modules (future expansion)
│   │   # (Reserved for future subcommands)
│   │
│   ├── core/                     # Business logic
│   │   ├── scanner.py           # File scanning & filtering
│   │   ├── payment.py           # Payment flow & trials
│   │   └── clause_selector.py   # Clause scoping & presets
│   │
│   ├── api/                      # Backend API client
│   │   └── client.py            # Unified API client (future)
│   │
│   ├── utils/                    # Utility modules
│   │   ├── config.py            # Configuration management
│   │   └── output.py            # Output formatting & markdown
│   │
│   └── templates/                # Report templates
│       # (Reserved for custom templates)
│
├── tests/                        # Unit & integration tests
│   ├── test_cli_payment_flow.py
│   ├── test_payment_scenario.py
│   └── test_real_payment_flow.py
│
├── CLAUDE/                       # Documentation
│   ├── README.md                # Documentation index
│   ├── BACKEND_INTEGRATION_GUIDE.md  # Backend integration
│   ├── CHANGELOG_v1.0.0.md      # v1.0.0 release notes
│   ├── CLI_MODERNIZATION_PLAN.md    # Roadmap
│   ├── CLAUSI_CLI_KNOWLEDGE_TRANSFER.md  # This doc
│   └── archive/                 # Old docs
│
├── .github/                      # GitHub Actions workflows
│   └── workflows/
│       └── compliance.yml       # CI compliance checks
│
├── setup.py                      # Package setup (updated for v1.0.0)
├── pyproject.toml               # Modern packaging (updated)
├── action.yml                   # GitHub Action definition
├── README.md                    # User documentation
├── LICENSE                      # MIT License
├── .gitignore                   # Git ignore patterns
├── .clausiignore                # Default ignore patterns
└── requirements.txt             # Dependencies

**Key Changes from v0.3.0:**
- Package: `clausi_cli` → `clausi`
- Structure: Flat → Industry-standard (commands/, core/, api/, utils/)
- Separation: Business logic moved to `core/`, utilities to `utils/`
- Modularity: Clause selection, scanner, output now separate modules
```

---

## Core Components

### 1. Main CLI (`clausi_cli/cli.py`)

**Purpose:** Main entry point for all CLI commands

**Key Features:**
- Click-based command structure
- Configuration management
- File scanning and filtering
- Token estimation and cost calculation
- Progress bars and rich output
- Report downloading and saving

**Command Groups:**
```python
@click.group()
def cli():
    """Main CLI group"""

@cli.group()
def config():
    """Configuration subcommands"""

@cli.command()
def scan():
    """Scan command"""

@cli.command()
def setup():
    """Setup wizard"""

@cli.command()
def tokens():
    """Token status"""
```

**Key Functions:**

#### `scan_directory(path: str) -> List[Dict[str, str]]`
**Location:** `cli.py:185-218`

Scans directory for code files to analyze.

**Supported Extensions:**
```python
{'.py', '.js', '.ts', '.java', '.cpp', '.h', '.hpp',
 '.c', '.cs', '.go', '.rs', '.swift'}
```

**Excluded Directories:**
```python
{"venv", ".git", "__pycache__", "node_modules",
 ".mypy_cache", ".pytest_cache"}
```

**Returns:** List of file metadata:
```python
{
    "path": "src/main.py",
    "content": "file contents...",
    "type": "py",
    "size": 1234
}
```

#### `filter_ignored_files(files, project_path, ignore_patterns)`
**Location:** `cli.py:279-330`

Filters files based on `.clausiignore` and command-line patterns.

**Features:**
- Searches upward for `.clausiignore` file
- Parses gitignore-style patterns
- Combines file patterns with CLI patterns
- Reports ignored file count

#### `get_openai_key() -> Optional[str]`
**Location:** `cli.py:167-169`

Gets OpenAI API key from config or environment.

**Precedence:**
1. `OPENAI_API_KEY` environment variable
2. `openai_key` in config file
3. `auth.openai_key` in config file (legacy)

#### `validate_openai_key(key: str) -> bool`
**Location:** `cli.py:171-183`

Validates OpenAI API key by calling `openai.models.list()`.

**Returns:** True if valid, False otherwise

---

### 2. Scan Module (`clausi_cli/scan.py`)

**Purpose:** Payment flow handling and scan request management

**Key Functions:**

#### `check_payment_required(api_url: str, mode: str) -> bool`
**Location:** `scan.py:20-85`

Checks if payment is required before scanning.

**Flow:**
1. POST to `/api/clausi/check-payment-required`
2. Check `payment_required` in response
3. If required:
   - Open browser to Stripe checkout
   - Display payment instructions
   - Return False (exit scan)
4. If not required:
   - Return True (proceed with scan)

**Test Card Info:**
```
Card: 4242 4242 4242 4242
Date: Any future date
CVC:  Any 3 digits
Email: Any email
```

#### `make_scan_request(api_url, openai_key, data) -> Optional[Dict]`
**Location:** `scan.py:189-220`

Makes scan request with payment flow support.

**Headers:**
```python
{
    "X-OpenAI-Key": openai_key,
    "X-Clausi-Token": token,  # Optional
    "Content-Type": "application/json"
}
```

**Response Handling:**
- **200 OK:** Return scan results
- **401 Unauthorized:** Trial token created, save and retry
- **402 Payment Required:** Open payment page, exit
- **Other:** Display error, exit

#### `handle_scan_response(response, api_url, openai_key, data)`
**Location:** `scan.py:87-120`

Handles different response types from scan endpoint.

**401 Response (Trial Token):**
```json
{
  "api_token": "uuid-token",
  "credits": 20
}
```

**Actions:**
1. Display trial message
2. Save token to `~/.clausi/config.yml`
3. Retry scan with token

**402 Response (Payment Required):**
```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

**Actions:**
1. Open browser to checkout URL
2. Display payment instructions
3. Exit with status 0

#### `retry_scan_with_token(api_url, openai_key, data, token)`
**Location:** `scan.py:167-187`

Retries scan request with newly obtained token.

---

### 3. Config Module (`clausi_cli/config.py`)

**Purpose:** Configuration and token management

**Configuration Files:**
```
~/.clausi/config.yml         # Main configuration
~/.clausi/credentials.yml    # API token storage (legacy)
```

**Key Functions:**

#### `load_config() -> Optional[Dict]`
**Location:** `config.py:31-42`

Loads configuration from `~/.clausi/config.yml`.

**Returns:**
```python
{
    "openai_key": "sk-...",
    "api_token": "uuid-token",
    "api": {
        "url": "https://api.clausi.ai",
        "timeout": 300,
        "max_retries": 3
    },
    "report": {
        "format": "pdf",
        "output_dir": "reports",
        "company_name": "",
        "company_logo": "",
        "template": "default"
    },
    "regulations": {
        "selected": ["EU-AIA", "GDPR", ...]
    }
}
```

#### `save_config(config: Dict) -> bool`
**Location:** `config.py:44-53`

Saves configuration to file.

#### `get_api_token() -> Optional[str]`
**Location:** `config.py:95-100`

Gets Clausi API token from config.

#### `save_api_token(token: str) -> bool`
**Location:** `config.py:102-106`

Saves API token to config file.

**Flow:**
1. Load existing config
2. Add/update `api_token` field
3. Save config back to file

#### `get_openai_key() -> Optional[str]`
**Location:** `config.py:108-127`

Gets OpenAI API key from environment or config.

**Precedence:**
1. `OPENAI_API_KEY` environment variable
2. `openai_key` in config (top-level)
3. `auth.openai_key` in config (legacy)

#### `show_token_status()`
**Location:** `config.py:129-138`

Displays API token status.

**Output:**
```
✓ API token found: 12345678...
Note: Credit status not yet implemented
```

---

## Command-Line Interface

### Commands Overview

```
clausi                          # Main command group
├── scan PATH [options]         # Scan project for compliance
├── setup                       # Setup wizard
├── tokens                      # Show token status
└── config                      # Config management
    ├── show                    # Display configuration
    ├── set [options]           # Update configuration
    ├── path                    # Show config file path
    └── edit                    # Open config in editor
```

---

### `clausi scan PATH [OPTIONS]`

**Purpose:** Scan a directory for compliance issues

**Arguments:**
- `PATH` - Path to project directory (required)

**Options:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `-r`, `--regulation` | Multiple Choice | All | Regulation(s) to check |
| `--mode` | Choice: ai/full | `ai` | Scanning mode |
| `-o`, `--output` | Path | `./reports` | Output directory |
| `--openai-key` | String | - | OpenAI API key override |
| `--format` | Choice | `pdf` | Report format (pdf/html/json/all) |
| `--template` | Choice | `default` | Report template |
| `--min-severity` | Choice | `info` | Minimum severity level |
| `--max-cost` | Float | - | Maximum cost in dollars |
| `--skip-confirmation` | Flag | False | Skip confirmation prompt |
| `--show-details` | Flag | False | Show per-file token estimates |
| `--ignore` | Multiple | - | Ignore patterns |
| `-v`, `--verbose` | Flag | False | Verbose output |

**Regulations:**
- `EU-AIA` - EU AI Act
- `GDPR` - General Data Protection Regulation
- `ISO-42001` - ISO/IEC 42001 AI Management System
- `HIPAA` - Health Insurance Portability and Accountability Act
- `SOC2` - SOC 2 Type 2

**Report Templates:**
- `default` - Standard compliance report
- `detailed` - Comprehensive technical report
- `executive` - High-level executive summary

**Example Usage:**
```bash
# Basic scan
clausi scan . -r EU-AIA

# Multiple regulations
clausi scan /path/to/project -r EU-AIA -r GDPR

# Full mode with cost limit
clausi scan . --mode full --max-cost 5.00

# All formats with ignore patterns
clausi scan . --format all --ignore "tests/" --ignore "*.log"

# High severity only
clausi scan . --min-severity high

# Skip confirmation
clausi scan . --skip-confirmation
```

**Workflow:**
1. Check payment requirements (full mode only)
2. Validate OpenAI API key
3. Scan directory for code files
4. Apply ignore patterns from `.clausiignore` and `--ignore`
5. Request token estimate from backend
6. Display cost breakdown
7. Prompt for confirmation (unless `--skip-confirmation`)
8. Make scan request to backend
9. Download generated reports
10. Display findings table
11. Save audit metadata

---

### `clausi setup`

**Purpose:** Interactive setup wizard for first-time configuration

**Prompts:**
1. OpenAI API key (validated)
2. Company name (optional)
3. Company logo path (optional)
4. Default regulation (EU-AIA/GDPR/ISO-42001/HIPAA/SOC2)
5. Default report template (default/detailed/executive)

**Creates:**
- `~/.clausi/config.yml` with user preferences

**Example Session:**
```
Welcome to Clausi CLI Setup!

This wizard will help you configure Clausi CLI for first use.

Enter your OpenAI API key: sk-...
Enter your company name (optional): ACME Corp
Enter path to company logo (optional): /path/to/logo.png
Choose default regulation [EU-AIA]:
Choose default report template [default]:

✓ Setup completed successfully!

You can now use 'clausi scan' to start scanning your projects.
```

---

### `clausi config`

#### `clausi config show`

**Purpose:** Display current configuration

**Output:**
```
Configuration file path: /home/user/.clausi/config.yml

┌─────────────────────┬────────────────────────────────────────┐
│ Setting             │ Value                                  │
├─────────────────────┼────────────────────────────────────────┤
│ OpenAI Key          │ ••••••••••••••••••••                  │
│ API URL             │ https://api.clausi.ai                  │
│ API Timeout         │ 300                                    │
│ API Max Retries     │ 3                                      │
│ Report Format       │ pdf                                    │
│ Output Directory    │ reports                                │
│ Company Name        │ ACME Corp                              │
│ Company Logo        │ Not set                                │
│ Report Template     │ default                                │
│ Selected Regulations│ EU-AIA, GDPR                           │
└─────────────────────┴────────────────────────────────────────┘
```

**Tunnel URL Override:**
If `CLAUSI_TUNNEL_BASE` environment variable is set:
```
API URL  │ https://custom-url.com (via CLAUSI_TUNNEL_BASE)
```

#### `clausi config set [OPTIONS]`

**Purpose:** Update configuration values

**Options:**
- `--openai-key` - Set OpenAI API key
- `--timeout` - Set API timeout (seconds)
- `--max-retries` - Set API max retries
- `--company-name` - Set company name
- `--company-logo` - Set company logo path
- `--output-dir` - Set default output directory
- `--regulations` - Set selected regulations (multiple)

**Example Usage:**
```bash
# Set OpenAI key
clausi config set --openai-key sk-...

# Set company info
clausi config set --company-name "ACME Corp" --company-logo "/path/to/logo.png"

# Set multiple regulations
clausi config set --regulations EU-AIA --regulations GDPR

# Set API timeout
clausi config set --timeout 600
```

#### `clausi config path`

**Purpose:** Print configuration file path

**Output:**
```
Configuration file path: /home/user/.clausi/config.yml
```

#### `clausi config edit`

**Purpose:** Open configuration file in editor

**Editor Selection:**
1. `$EDITOR` environment variable
2. `notepad` (Windows)
3. `vi` (Unix/Linux)

**Example:**
```bash
clausi config edit
# Opens config.yml in default editor
```

---

### `clausi tokens`

**Purpose:** Show API token status and remaining credits

**Output:**
```
✓ API token found: 12345678...
Note: Credit status not yet implemented
```

**Planned Feature:**
Future versions will query backend for remaining credits:
```
✓ API token found: 12345678...
  Credits remaining: 15
  Trial user: No
```

---

## Configuration Management

### Configuration File Structure

**Location:** `~/.clausi/config.yml`

```yaml
# OpenAI API Key (required)
openai_key: "sk-..."

# Clausi API Token (auto-generated for trial users)
api_token: "uuid-token"

# API Configuration
api:
  url: "https://api.clausi.ai"
  timeout: 300
  max_retries: 3

# Report Configuration
report:
  format: "pdf"                    # pdf, html, json, all
  output_dir: "reports"            # Default output directory
  company_name: "ACME Corp"        # For report headers
  company_logo: "/path/to/logo.png"
  template: "default"              # default, detailed, executive

# Regulation Configuration
regulations:
  selected:
    - EU-AIA
    - GDPR
    - ISO-42001
    - HIPAA
    - SOC2
```

### Configuration Precedence

For each setting, the CLI follows this precedence order:

1. **Command-line flags** (highest priority)
2. **Environment variables**
3. **Configuration file**
4. **Default values** (lowest priority)

**Examples:**

#### OpenAI API Key
```
1. --openai-key flag
2. OPENAI_API_KEY environment variable
3. openai_key in config.yml
4. No default (error if not provided)
```

#### API URL
```
1. CLAUSI_TUNNEL_BASE environment variable
2. api.url in config.yml
3. Default: https://api.clausi.ai
```

#### Output Directory
```
1. --output flag
2. CLAUSI_OUTPUT_DIR environment variable
3. report.output_dir in config.yml
4. Default: ./reports
```

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `CLAUSI_OUTPUT_DIR` | Report output directory | `/path/to/reports` |
| `CLAUSI_TUNNEL_BASE` | API base URL override | `http://localhost:10000` |

**Usage:**
```bash
# Use environment variables
export OPENAI_API_KEY="sk-..."
export CLAUSI_TUNNEL_BASE="http://localhost:10000"
clausi scan .

# Or inline
OPENAI_API_KEY="sk-..." clausi scan .
```

### Config File Creation

**Automatic Creation:**
- Created on first run if not exists
- Created by `clausi setup` wizard
- Default values populated

**Manual Creation:**
```bash
mkdir -p ~/.clausi
cat > ~/.clausi/config.yml << EOF
openai_key: ""
api:
  url: https://api.clausi.ai
  timeout: 300
  max_retries: 3
report:
  format: pdf
  output_dir: reports
  company_name: ""
  company_logo: ""
  template: default
regulations:
  selected:
    - EU-AIA
    - GDPR
EOF
```

---

## File Scanning & Filtering

### Supported File Extensions

**Code Files:**
```python
{'.py', '.js', '.ts', '.java', '.cpp', '.h', '.hpp',
 '.c', '.cs', '.go', '.rs', '.swift'}
```

**Rationale:**
- Common programming languages
- Excludes markup, data files, and binaries
- Can be extended in `cli.py:191`

### Excluded Directories

**Auto-Excluded:**
```python
{"venv", ".git", "__pycache__", "node_modules",
 ".mypy_cache", ".pytest_cache"}
```

**Purpose:**
- Avoid scanning dependency folders
- Ignore build artifacts
- Exclude version control metadata

### .clausiignore File

**Purpose:** Exclude files and directories from compliance scanning

**Syntax:** Same as `.gitignore` (uses `pathspec` library)

**Location:**
- Search starts at project root
- Searches upward through parent directories
- First `.clausiignore` found is used

**Example `.clausiignore`:**
```bash
# Ignore test files
tests/
test_*.py
*_test.py

# Ignore build artifacts
build/
dist/
*.egg-info/

# Ignore logs and temp files
*.log
*.tmp
temp/
tmp/

# Ignore configuration files
config.local.py
secrets.json
.env

# Ignore documentation
docs/
*.md

# Ignore specific files
migrations/
fixtures/
```

**Pattern Types:**

| Pattern | Matches | Example |
|---------|---------|---------|
| `file.py` | Exact filename | `file.py` |
| `*.log` | Extension wildcard | `error.log`, `debug.log` |
| `tests/` | Directory | All files in `tests/` |
| `**/temp/` | Nested directory | `foo/temp/`, `bar/baz/temp/` |
| `!important.py` | Negation (keep file) | Overrides ignore |

**Command-Line Ignore:**
```bash
# Single pattern
clausi scan . --ignore "tests/"

# Multiple patterns
clausi scan . --ignore "tests/" --ignore "*.log" --ignore "temp/"

# Combines with .clausiignore
clausi scan . --ignore "*.pyc"
```

**Implementation:**
**Location:** `cli.py:242-330`

**Flow:**
1. Find `.clausiignore` by searching upward
2. Parse patterns using `pathspec.PathSpec.from_lines('gitwildmatch')`
3. Parse command-line `--ignore` patterns
4. Filter files using both specs
5. Report ignored file count

**Output:**
```
Using .clausiignore file: /path/to/project/.clausiignore
Using command-line ignore patterns: tests/, *.log
Ignoring tests/test_main.py (matches .clausiignore)
Ignoring build.log (matches command-line pattern)
Ignored 47 files based on ignore patterns
Analyzing 123 files after filtering
```

---

## Backend Integration

### API Endpoints

#### 1. `/api/clausi/estimate` (POST)

**Purpose:** Estimate token usage and cost before scanning

**Request:**
```json
{
  "path": "/path/to/project",
  "regulations": ["EU-AIA", "GDPR"],
  "mode": "full",
  "metadata": {
    "path": "/path/to/project",
    "files": [
      {
        "path": "src/main.py",
        "content": "...",
        "type": "py",
        "size": 1234
      }
    ],
    "timestamp": "2025-10-13T12:34:56.789Z",
    "format": "pdf",
    "template": "default"
  },
  "estimate_only": true
}
```

**Headers:**
```
X-OpenAI-Key: sk-...
Content-Type: application/json
```

**Response (200 OK):**
```json
{
  "total_tokens": 12345,
  "prompt_tokens": 10000,
  "completion_tokens": 2345,
  "estimated_cost": 0.42,
  "regulation_breakdown": [
    {
      "regulation": "EU-AIA",
      "total_tokens": 6000,
      "estimated_cost": 0.20
    },
    {
      "regulation": "GDPR",
      "total_tokens": 6345,
      "estimated_cost": 0.22
    }
  ],
  "file_breakdown": [
    {
      "path": "src/main.py",
      "tokens": 2000,
      "estimated_cost": 0.08,
      "too_large": false
    }
  ]
}
```

**CLI Usage:**
**Location:** `cli.py:564-623`

**Flow:**
1. Prepare request data with `estimate_only: true`
2. POST to `/api/clausi/estimate`
3. Display token estimates
4. Check against `--max-cost` if specified
5. Check for files that are too large
6. Prompt for user confirmation

---

#### 2. `/api/clausi/scan` (POST)

**Purpose:** Perform compliance scan and generate reports

**Request:**
```json
{
  "path": "/path/to/project",
  "regulations": ["EU-AIA"],
  "mode": "full",
  "min_severity": "info",
  "metadata": {
    "path": "/path/to/project",
    "files": [...],
    "timestamp": "2025-10-13T12:34:56.789Z",
    "format": "pdf",
    "template": "default",
    "company": {
      "name": "ACME Corp",
      "logo": "/path/to/logo.png"
    }
  }
}
```

**Headers:**
```
X-OpenAI-Key: sk-...
X-Clausi-Token: uuid-token    # Optional, auto-generated for trial
Content-Type: application/json
```

**Response (200 OK):**
```json
{
  "findings": [
    {
      "clause_id": "EUAIA-3.1",
      "violation": true,
      "severity": "high",
      "location": "src/main.py:42",
      "explanation": "Missing risk assessment documentation",
      "recommended_solution": "Add docstring with risk assessment"
    }
  ],
  "token_usage": {
    "total_tokens": 12500,
    "cost": 0.45
  },
  "generated_reports": [
    {
      "format": "pdf",
      "filename": "project_EU-AIA_20251013_123456.pdf"
    }
  ]
}
```

**Response (401 Unauthorized) - Trial Token Created:**
```json
{
  "api_token": "12345678-1234-1234-1234-123456789abc",
  "credits": 20
}
```

**CLI Action:**
1. Save token to `~/.clausi/config.yml`
2. Retry scan with `X-Clausi-Token` header

**Response (402 Payment Required) - Credits Exhausted:**
```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

**CLI Action:**
1. Open browser to checkout URL
2. Display payment instructions
3. Exit with status 0

---

#### 3. `/api/clausi/check-payment-required` (POST)

**Purpose:** Check if payment is required before scanning

**Request:**
```json
{
  "mode": "full"
}
```

**Headers:**
```
X-Clausi-Token: uuid-token  # Optional
Content-Type: application/json
```

**Response (200 OK) - No Payment Required:**
```json
{
  "payment_required": false,
  "reason": "Sufficient credits available",
  "credits_remaining": 15
}
```

**Response (200 OK) - Payment Required:**
```json
{
  "payment_required": true,
  "reason": "No credits remaining",
  "checkout_url": "https://checkout.stripe.com/...",
  "credits_remaining": 0
}
```

**CLI Usage:**
**Location:** `scan.py:20-85`

**Flow:**
1. Called before estimate (full mode only)
2. If payment required:
   - Open browser to checkout
   - Exit scan
3. If not required:
   - Continue to estimate

---

#### 4. `/api/clausi/report/{filename}` (GET)

**Purpose:** Download generated report file

**Request:**
```
GET /api/clausi/report/project_EU-AIA_20251013_123456.pdf
```

**Headers:**
```
Authorization: Bearer sk-...
```

**Response:**
- **200 OK** - File content (binary)
- **404 Not Found** - Report not found

**CLI Usage:**
**Location:** `cli.py:645-667`

**Flow:**
1. Loop through `generated_reports` array
2. For each report:
   - GET `/api/clausi/report/{filename}`
   - Save to output directory
   - Display success message

---

### HTTP Client Configuration

**Library:** `requests` 2.26.0+

**Timeouts:**
- Estimate: 300 seconds (5 minutes)
- Scan: 300 seconds (5 minutes)
- Report download: 60 seconds

**Retry Strategy:**
- Max retries: 3 (configured but not implemented)
- Retry-on: Connection errors

**Error Handling:**
```python
try:
    response = requests.post(url, json=data, headers=headers, timeout=300)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    console.print(f"[red]Error connecting to backend: {str(e)}[/red]")
    sys.exit(1)
```

---

## Payment & Trial System

### Trial System Flow

```
┌─────────────────────────────────────────────────────┐
│  User runs: clausi scan . --mode full               │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │  Has X-Clausi-Token in config? │
          └───────────────────────────────┘
              NO │              │ YES
                 ▼              ▼
      ┌─────────────────┐   ┌──────────────┐
      │ Check payment   │   │ Send scan    │
      │ requirements    │   │ with token   │
      └─────────────────┘   └──────────────┘
              │                    │
              ▼                    ▼
      ┌─────────────────┐   ┌──────────────┐
      │ Backend creates │   │ Backend checks│
      │ trial account   │   │ credits > 0  │
      │ with 20 credits │   └──────────────┘
      └─────────────────┘         │
              │              YES │   │ NO
              ▼                  ▼   ▼
      ┌─────────────────┐   ┌──────────────┐
      │ Return 401 with │   │ Return 402   │
      │ api_token       │   │ payment_req  │
      └─────────────────┘   └──────────────┘
              │                    │
              ▼                    ▼
      ┌─────────────────┐   ┌──────────────┐
      │ CLI saves token │   │ Open browser │
      │ Retry scan      │   │ Show payment │
      └─────────────────┘   └──────────────┘
              │
              ▼
      ┌─────────────────┐
      │ 200 OK          │
      │ Scan results    │
      └─────────────────┘
```

### Trial User Creation

**Trigger:** First full-mode scan without token

**Backend Logic:**
1. Generate `origin_hash = SHA256(IP + User-Agent)`
2. Check if origin_hash exists in database
3. If not found:
   - Create customer with `id = "trial-{uuid}"`
   - Set `credits = 20`
   - Generate API token
   - Return 401 with token
4. If found:
   - Return 402 Payment Required

**CLI Handling:**
**Location:** `scan.py:87-120`

**Response (401):**
```json
{
  "api_token": "12345678-1234-1234-1234-123456789abc",
  "credits": 20
}
```

**Actions:**
1. Display trial account message
2. Save token to config:
   ```python
   config = load_config() or {}
   config['api_token'] = api_token
   save_config(config)
   ```
3. Retry scan with token in `X-Clausi-Token` header

**Output:**
```
🎉 Trial account created!
   Credits: 20
   Token: 12345678...

   Saving token and retrying scan...
```

---

### Payment Flow

**Trigger:** Credits exhausted (trial or paid user)

**Backend Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

**CLI Handling:**
**Location:** `scan.py:122-165`

**Actions:**
1. Open browser to checkout URL:
   ```python
   webbrowser.open(checkout_url)
   ```
2. Display payment instructions:
   ```
   ═══════════════════════════════════════════════════════════
   💳 PAYMENT REQUIRED
   ═══════════════════════════════════════════════════════════

   📱 Opening payment page in your browser...

   📋 PAYMENT INSTRUCTIONS:
      💳 Use test card: 4242 4242 4242 4242
      📅 Any future date
      🔢 Any 3-digit CVC
      📧 Any email address

      ⏳ Complete your payment in the browser
      🔄 After payment, run your scan command again

   🔗 Payment URL also available at:
      https://checkout.stripe.com/...
   ═══════════════════════════════════════════════════════════
   ```
3. Wait 2 seconds for browser to open
4. Exit with status 0

**Post-Payment:**
1. User completes payment
2. Stripe webhook adds credits to account
3. User runs scan command again
4. Scan proceeds with available credits

---

### Token Storage

**File:** `~/.clausi/config.yml`

**Field:** `api_token`

**Example:**
```yaml
openai_key: "sk-..."
api_token: "12345678-1234-1234-1234-123456789abc"
api:
  url: "https://api.clausi.ai"
...
```

**Access Methods:**
```python
# Get token
token = get_api_token()

# Save token
save_api_token(token)
```

---

## Report Generation

### Report Workflow

```
┌──────────────────────────────────────────────────────┐
│  Scan completed successfully (200 OK)                │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │  Response contains:           │
          │  - findings[]                 │
          │  - token_usage{}              │
          │  - generated_reports[]        │
          └───────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │  For each generated report:   │
          │  1. Extract format & filename │
          │  2. Download from backend     │
          │  3. Save to output directory  │
          └───────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │  Save audit metadata JSON     │
          │  - timestamp                  │
          │  - regulations                │
          │  - files_analyzed             │
          │  - findings                   │
          │  - token_usage                │
          └───────────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────┐
          │  Display findings table       │
          │  Display token usage          │
          └───────────────────────────────┘
```

### Report Formats

#### PDF Report
- **Extension:** `.pdf`
- **Media Type:** `application/pdf`
- **Generated By:** Backend (WeasyPrint)
- **Download:** Binary download from `/api/clausi/report/{filename}`
- **Save:** Write binary content to file

#### HTML Report
- **Extension:** `.html`
- **Media Type:** `text/html`
- **Generated By:** Backend (Jinja2)
- **Download:** Text download from `/api/clausi/report/{filename}`
- **Save:** Write text content to file

#### JSON Report
- **Extension:** `.json`
- **Media Type:** `application/json`
- **Generated By:** Backend (Python json module)
- **Content:** Structured findings data
- **Save:** Write JSON content to file

### Report Download Logic

**Location:** `cli.py:645-667`

```python
for report_info in result["generated_reports"]:
    report_format = report_info["format"]
    report_filename = report_info["filename"]

    # Download report
    response = requests.get(
        f"{get_api_url()}/api/clausi/report/{report_filename}",
        headers={"Authorization": f"Bearer {openai_key}"},
        timeout=60
    )

    if response.status_code == 200:
        report_path = output_path / report_filename
        with open(report_path, 'wb') as f:
            f.write(response.content)
        console.print(f"[green]{report_format.upper()} report saved to: {report_path}[/green]")
```

**Output:**
```
PDF report saved to: ./reports/project_EU-AIA_20251013_123456.pdf
HTML report saved to: ./reports/project_EU-AIA_20251013_123456.html
JSON report saved to: ./reports/project_EU-AIA_20251013_123456.json
```

### Audit Metadata

**Location:** `cli.py:677-689`

**File:** `audit_metadata.json` in output directory

**Content:**
```json
{
  "timestamp": "2025-10-13T12:34:56.789Z",
  "path": "/path/to/project",
  "regulations": ["EU-AIA", "GDPR"],
  "mode": "full",
  "files_analyzed": 123,
  "template": "default",
  "format": "pdf",
  "findings": [
    {
      "clause_id": "EUAIA-3.1",
      "violation": true,
      "severity": "high",
      "location": "src/main.py:42",
      "explanation": "..."
    }
  ],
  "token_usage": {
    "total_tokens": 12500,
    "cost": 0.45
  }
}
```

**Purpose:**
- Record scan session details
- Track token usage over time
- Audit trail for compliance
- Machine-readable scan results

### Findings Table Display

**Location:** `cli.py:691-711`

**Implementation:**
```python
table = Table(title="Compliance Findings")
table.add_column("Clause", style="cyan")
table.add_column("Status", style="green")
table.add_column("Severity", style="yellow")
table.add_column("Location", style="blue")
table.add_column("Description", style="white")

for finding in result["findings"]:
    status = "✓" if not finding.get("violation") else "✗"
    status_style = "green" if not finding.get("violation") else "red"
    table.add_row(
        finding.get("clause_id", ""),
        f"[{status_style}]{status}[/{status_style}]",
        finding.get("severity", ""),
        finding.get("location", ""),
        finding.get("explanation", "")
    )

console.print(table)
```

**Output:**
```
                          Compliance Findings
┌───────────┬────────┬──────────┬─────────────────┬─────────────────┐
│ Clause    │ Status │ Severity │ Location        │ Description     │
├───────────┼────────┼──────────┼─────────────────┼─────────────────┤
│ EUAIA-3.1 │   ✗    │ high     │ src/main.py:42  │ Missing risk... │
│ GDPR-5.1  │   ✗    │ warning  │ src/data.py:15  │ No data min...  │
│ EUAIA-7.2 │   ✓    │ info     │ src/logs.py:8   │ Logging impl... │
└───────────┴────────┴──────────┴─────────────────┴─────────────────┘
```

---

## GitHub Actions Integration

### Action Definition

**File:** `action.yml`

**Purpose:** Define GitHub Action for CI/CD integration

**Inputs:**

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `path` | Path to scan | No | `.` |
| `mode` | Scan mode (ai/full) | No | `ai` |
| `min-severity` | Minimum severity | No | `info` |
| `max-cost` | Maximum cost ($) | No | `10.00` |
| `regulations` | Comma-separated regulations | No | `EU-AIA` |
| `format` | Report format | No | `html` |
| `template` | Report template | No | `default` |
| `ignore` | Comma-separated ignore patterns | No | `""` |
| `openai-key` | OpenAI API key | **Yes** | - |
| `skip-confirmation` | Skip confirmation | No | `true` |

**Outputs:**
- Report uploaded as artifact
- Summary printed to console

### Example Workflow

**File:** `.github/workflows/compliance.yml`

```yaml
name: Compliance Check

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  compliance-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Run Clausi Compliance Scan
        uses: ./
        with:
          path: 'src/'
          mode: 'ai'
          regulations: 'EU-AIA,GDPR'
          format: 'html'
          template: 'detailed'
          min-severity: 'warning'
          max-cost: '5.00'
          ignore: 'tests/,*.log,temp/'
          openai-key: ${{ secrets.OPENAI_API_KEY }}

      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: compliance-reports
          path: reports/
```

### Action Implementation

**File:** `action.yml`

```yaml
name: 'Clausi Compliance Scan'
description: 'Run AI-powered compliance checks against EU AI Act, GDPR, and more'
branding:
  icon: 'shield'
  color: 'blue'

inputs:
  path:
    description: 'Path to scan'
    required: false
    default: '.'
  mode:
    description: 'Scan mode (ai or full)'
    required: false
    default: 'ai'
  # ... (other inputs)

runs:
  using: 'composite'
  steps:
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install Clausi CLI
      run: pip install clausi-cli
      shell: bash

    - name: Configure Clausi
      run: |
        clausi config set --openai-key "${{ inputs.openai-key }}"
      shell: bash

    - name: Run compliance scan
      run: |
        clausi scan "${{ inputs.path }}" \
          --mode "${{ inputs.mode }}" \
          --regulations "${{ inputs.regulations }}" \
          --format "${{ inputs.format }}" \
          --template "${{ inputs.template }}" \
          --min-severity "${{ inputs.min-severity }}" \
          --max-cost "${{ inputs.max-cost }}" \
          --ignore "${{ inputs.ignore }}" \
          --skip-confirmation
      shell: bash
      continue-on-error: true
```

### Secrets Configuration

**GitHub Repository Settings:**
1. Go to repository Settings
2. Navigate to Secrets and variables → Actions
3. Add new secret:
   - Name: `OPENAI_API_KEY`
   - Value: `sk-...`

**Usage in Workflow:**
```yaml
openai-key: ${{ secrets.OPENAI_API_KEY }}
```

---

## Development Setup

### Prerequisites

- **Python:** 3.7+ (supports 3.7, 3.8, 3.9, 3.10)
- **pip:** Latest version
- **Virtual environment:** venv, virtualenv, or conda

### Installation Steps

#### For End Users

```bash
# Install from PyPI
pip install clausi-cli

# Verify installation
clausi --version
```

#### For Contributors

```bash
# Clone repository
git clone https://github.com/clausi/clausi-cli.git
cd clausi-cli

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e .[dev]

# Verify installation
clausi --version
```

### Development Dependencies

**File:** `setup.py:142-150`

```python
install_requires=[
    "click>=8.0.0",
    "rich>=10.0.0",
    "requests>=2.26.0",
    "pyyaml>=5.4.1",
    "python-dotenv>=0.19.0",
    "openai>=1.0.0",
    "pathspec>=0.10.0",
]
```

**Optional Dev Dependencies:**
```bash
pip install pytest pytest-cov ruff black mypy
```

### Configuration

```bash
# Run setup wizard
clausi setup

# Or manually configure
clausi config set --openai-key sk-...
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_config.py

# Run with coverage
pytest --cov=clausi_cli --cov-report=html

# Run integration tests
python test_cli_payment_flow.py
python test_payment_scenario.py
```

### Code Quality

#### Linting
```bash
# Check with ruff
ruff check .

# Fix auto-fixable issues
ruff check . --fix
```

#### Formatting
```bash
# Format with ruff
ruff format .

# Or use black
black clausi_cli/
```

#### Type Checking
```bash
# Check types with mypy
mypy clausi_cli/
```

### Project Scripts

#### Build Backend (`build_backend.py`)
**Purpose:** Build standalone backend executable

**Usage:**
```bash
python build_backend.py
```

#### Setup Dev (`setup_dev.py`)
**Purpose:** Development environment setup

**Usage:**
```bash
python setup_dev.py
```

---

## Testing

### Test Files

| File | Purpose | Location |
|------|---------|----------|
| `test_cli_payment_flow.py` | CLI payment flow integration | Root |
| `test_payment_scenario.py` | Payment scenario testing | Root |
| `test_real_payment_flow.py` | Real payment flow testing | Root |
| `tests/` | Unit tests | tests/ |

### Integration Tests

#### `test_cli_payment_flow.py`

**Purpose:** Test CLI payment flow with mock backend

**Features:**
- Mock backend server
- Trial token generation
- Payment required scenarios
- Token saving and retry

**Usage:**
```bash
python test_cli_payment_flow.py
```

#### `test_payment_scenario.py`

**Purpose:** Test specific payment scenarios

**Features:**
- First-time user (trial)
- Exhausted credits (payment)
- Valid token (scan)

**Usage:**
```bash
python test_payment_scenario.py
```

#### `test_real_payment_flow.py`

**Purpose:** Test real payment flow with live backend

**Features:**
- Real API calls
- Stripe checkout
- Credit deduction

**Usage:**
```bash
OPENAI_API_KEY=sk-... python test_real_payment_flow.py
```

### Unit Tests

**Directory:** `tests/`

**Run:**
```bash
pytest tests/
```

### Test Coverage

```bash
# Run with coverage
pytest --cov=clausi_cli --cov-report=html

# View report
open htmlcov/index.html
```

---

## Distribution & Packaging

### PyPI Package

**Package Name:** `clausi-cli`

**Installation:**
```bash
pip install clausi-cli
```

**Uninstallation:**
```bash
pip uninstall clausi-cli
```

### Package Metadata

**File:** `setup.py`

```python
name="clausi-cli"
version="0.3.0"
author="Clausi"
author_email="support@clausi.ai"
description="AI compliance auditing tool"
url="https://clausi.ai"
license="MIT"
python_requires=">=3.7"
```

**PyPI URLs:**
- **Bug Tracker:** https://github.com/clausi/clausi-cli/issues
- **Documentation:** https://docs.clausi.ai
- **Source Code:** https://github.com/clausi/clausi-cli

### Build Process

#### 1. Update Version

**File:** `setup.py`
```python
version="0.3.0"
```

**File:** `cli.py`
```python
@click.version_option(version="0.3.0", prog_name="Clausi CLI")
```

#### 2. Build Distribution

```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Output:
# dist/clausi_cli-0.3.0-py3-none-any.whl
# dist/clausi-cli-0.3.0.tar.gz
```

#### 3. Upload to PyPI

```bash
# Test upload (TestPyPI)
twine upload --repository testpypi dist/*

# Production upload
twine upload dist/*
```

### Custom Commands

#### Post-Uninstall Command

**Purpose:** Remove config directory on uninstall

**File:** `setup.py:7-26`

```python
class PostUninstallCommand(Command):
    """Post-uninstall command to remove config directory."""
    description = "Remove .clausi configuration directory"

    def run(self):
        config_dir = Path.home() / ".clausi"
        if config_dir.exists():
            shutil.rmtree(config_dir)
            print(f"Removed configuration directory: {config_dir}")
```

**Usage:**
```bash
pip uninstall clausi-cli
# Removes ~/.clausi directory
```

#### Custom Build Command

**Purpose:** Create config file during installation

**File:** `setup.py:28-108`

```python
class CustomBuildCommand(build_py):
    """Custom build command that ensures config is created."""

    def run(self):
        if not self.create_config():
            raise SystemExit("Failed to create config file. Build aborted.")
        build_py.run(self)
```

**Config Creation:**
- Creates `~/.clausi/config.yml` during build
- Populates with default values
- Runs before package installation

### Entry Points

**File:** `setup.py:151-154`

```python
entry_points={
    "console_scripts": [
        "clausi=clausi_cli.cli:main",
    ],
}
```

**Result:**
- Installs `clausi` command to PATH
- Executable on all platforms
- Calls `main()` function in `cli.py`

---

## Known Issues & Technical Debt

### Security Issues

#### 1. **OpenAI Key Stored in Plain Text**
**Location:** `~/.clausi/config.yml`

**Issue:** OpenAI API key stored unencrypted

**Risk:** Key exposure if config file is read by malicious software

**Recommendation:**
- Use system keyring for secure storage
- Encrypt config file
- Add file permissions check (600)

#### 2. **API Token Stored in Plain Text**
**Location:** `~/.clausi/config.yml`

**Issue:** Clausi API token stored unencrypted

**Recommendation:** Same as OpenAI key

#### 3. **No Request Signature Verification**

**Issue:** Backend responses not cryptographically verified

**Risk:** Man-in-the-middle attacks

**Recommendation:**
- Implement response signatures
- Validate SSL certificates
- Pin certificate for api.clausi.ai

### Architecture Issues

#### 1. **No Rate Limiting**

**Issue:** CLI makes unlimited API requests

**Risk:**
- OpenAI API rate limit exceeded
- Backend overload
- Unexpected costs

**Recommendation:**
- Implement client-side rate limiting
- Add exponential backoff
- Display rate limit warnings

#### 2. **No Request Retry Logic**

**Issue:** Network failures cause immediate failure

**Location:** All API calls lack retry logic

**Recommendation:**
- Implement retry with exponential backoff
- Configure max retries (already in config, not used)
- Handle transient errors

#### 3. **Synchronous API Calls**

**Issue:** All API calls block CLI

**Impact:** Poor user experience for slow connections

**Recommendation:**
- Use async/await for API calls
- Show progress indicators
- Allow cancellation

#### 4. **Large File Handling**

**Issue:** Entire file contents loaded into memory

**Location:** `cli.py:207-210`

**Risk:** Memory exhaustion for large codebases

**Recommendation:**
- Stream file contents
- Chunk large files
- Set file size limits

### User Experience Issues

#### 1. **No Progress for Long Scans**

**Issue:** No feedback during backend processing

**Current:** Spinner shows "Analyzing files..." indefinitely

**Recommendation:**
- WebSocket connection for progress updates
- Estimated time remaining
- File-by-file progress

#### 2. **No Scan Cancellation**

**Issue:** Cannot cancel running scan

**Recommendation:**
- Add Ctrl+C handler
- Cancel backend request
- Clean up partial results

#### 3. **Limited Error Messages**

**Issue:** Generic error messages for failures

**Example:**
```
Error connecting to backend: <error>
```

**Recommendation:**
- Categorize errors
- Provide actionable suggestions
- Add debug mode for verbose output

#### 4. **No Offline Mode**

**Issue:** Requires internet connection

**Recommendation:**
- Cache regulation YAML locally
- Support local backend URL
- Offline documentation

### Code Quality Issues

#### 1. **Large cli.py File**

**Issue:** `cli.py` is 832 lines

**Recommendation:**
- Split into modules (commands/, utils/)
- Separate concerns
- Improve maintainability

#### 2. **Duplicate Code**

**Issue:** API call logic duplicated

**Locations:**
- `cli.py:568-576` (estimate request)
- `scan.py:205-210` (scan request)

**Recommendation:**
- Create shared API client module
- DRY principle

#### 3. **Missing Type Hints**

**Issue:** Many functions lack type annotations

**Recommendation:**
- Add type hints throughout
- Use mypy for type checking
- Improve IDE support

#### 4. **Inconsistent Error Handling**

**Issue:** Mixed error handling strategies

**Examples:**
- Some functions return None
- Some raise exceptions
- Some call sys.exit()

**Recommendation:**
- Consistent error handling strategy
- Custom exception classes
- Centralized error display

---

## Future Improvements

### Short-Term (1-3 months)

#### 1. **Async API Calls**
- Migrate to `httpx` for async support
- Use `asyncio` for concurrent requests
- Improve responsiveness

#### 2. **Enhanced Progress Indicators**
- WebSocket connection to backend
- Real-time file analysis progress
- Token usage updates

#### 3. **Improved Error Messages**
- Categorize error types
- Actionable suggestions
- Context-specific help

#### 4. **Local Caching**
- Cache regulation definitions
- Cache file metadata
- Speed up subsequent scans

#### 5. **Configuration Validation**
- Validate OpenAI key on set
- Validate file paths
- Warn about invalid settings

### Mid-Term (3-6 months)

#### 1. **Offline Mode**
- Local regulation database
- Cached reports
- Offline documentation

#### 2. **Interactive Mode**
- TUI for scan results
- Navigate findings
- Fix suggestions

#### 3. **Report Customization**
- Custom report templates
- Company branding
- Template editor

#### 4. **CI/CD Enhancements**
- JUnit XML output
- SARIF format
- GitLab CI support

#### 5. **Scan History**
- Track scan results over time
- Compare scans
- Trend analysis

### Long-Term (6-12 months)

#### 1. **Language Server Protocol (LSP)**
- IDE integration
- Real-time compliance checking
- Inline suggestions

#### 2. **Git Integration**
- Scan only changed files
- Pre-commit hooks
- Blame annotations

#### 3. **Team Features**
- Shared configurations
- Team dashboards
- Collaborative reviews

#### 4. **Advanced Analytics**
- Compliance trends
- Risk scoring
- Predictive analysis

#### 5. **Plugin System**
- Custom scanners
- Custom regulations
- Extensible architecture

---

## Appendix

### Command Reference

#### All Commands

```bash
clausi --version                    # Show version
clausi --help                       # Show help

# Scanning
clausi scan PATH [options]          # Scan project
clausi scan . -r EU-AIA             # Basic scan
clausi scan . -r EU-AIA -r GDPR     # Multiple regulations
clausi scan . --mode full           # Full scan (requires credits)
clausi scan . --format all          # All report formats
clausi scan . --max-cost 5.00       # Cost limit
clausi scan . --skip-confirmation   # Skip prompt
clausi scan . --show-details        # Show per-file estimates
clausi scan . --ignore "tests/"     # Ignore patterns

# Configuration
clausi config show                  # Show config
clausi config set --openai-key sk-  # Set OpenAI key
clausi config path                  # Show config path
clausi config edit                  # Edit config file

# Setup
clausi setup                        # Setup wizard

# Tokens
clausi tokens                       # Show token status
```

### Environment Variables

```bash
# OpenAI API Key
export OPENAI_API_KEY="sk-..."

# Output directory
export CLAUSI_OUTPUT_DIR="/path/to/reports"

# API URL override
export CLAUSI_TUNNEL_BASE="http://localhost:10000"
```

### Configuration File Paths

| OS | Path |
|----|------|
| Windows | `C:\Users\<user>\.clausi\config.yml` |
| macOS | `/Users/<user>/.clausi/config.yml` |
| Linux | `/home/<user>/.clausi/config.yml` |

### Report Output Structure

```
reports/
├── project_EU-AIA_20251013_123456.pdf
├── project_EU-AIA_20251013_123456.html
├── project_EU-AIA_20251013_123456.json
└── audit_metadata.json
```

### Error Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Generic error |
| 401 | Trial token created (internal) |
| 402 | Payment required (internal) |

### Useful Links

- **GitHub:** https://github.com/clausi/clausi-cli
- **PyPI:** https://pypi.org/project/clausi-cli/
- **Documentation:** https://docs.clausi.ai
- **Support:** support@clausi.ai
- **Bug Reports:** https://github.com/clausi/clausi-cli/issues

---

**End of Knowledge Transfer Document**
