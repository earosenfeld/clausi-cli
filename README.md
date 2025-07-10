# Clausi CLI

> Modern command-line interface for auditing software projects against the **EU AI Act** and **GDPR**.

---

## Table of Contents
1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick-start (End Users)](#quick-start-end-users)
4. [Configuration](#configuration)
5. [Scanning Projects](#scanning-projects)
6. [Environment Variables](#environment-variables)
7. [File Ignoring](#file-ignoring)
8. [GitHub Actions](#github-actions)
9. [API Endpoints](#api-endpoints)
10. [Development & Contribution](#development--contribution)
11. [License](#license)

---

## Overview
Clausi CLI submits source-code and metadata to the hosted Clausi platform
(`https://api.clausi.ai`) which returns a compliance report in the format of
your choice (PDF, HTML, JSON).

Supported regulatory frameworks (built-in):

| Key    | Regulation                                              |
|--------|---------------------------------------------------------|
| EU-AIA | European Union Artificial Intelligence Act (EU AI Act)  |
| GDPR   | General Data Protection Regulation                      |
| ISO-42001 | ISO/IEC 42001 AI Management System |
| HIPAA | Health Insurance Portability and Accountability Act |
| SOC2 | SOC 2 – System and Organization Controls Type 2 |

Additional frameworks can be added on the server side without requiring a
client update.

---

## Installation

| Audience           | Command                                                |
|--------------------|--------------------------------------------------------|
| **End users**      | `pip install clausi`                                   |
| **Contributors**   | `git clone https://github.com/earosenfeld/clausi-cli`<br>`cd clausi-cli`<br>`pip install -e .[dev]` |

Python ≥ 3.8 is required.

---

## Quick-start (End Users)
1. **Interactive wizard** (recommended for the first run)
   ```bash
   clausi setup
   ```
2. **Or set the OpenAI key directly**
   ```bash
   clausi config set --openai-key sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
3. **Run your first scan**
   ```bash
   clausi scan /path/to/project -r EU-AIA
   ```
   The report is saved to `./reports/` by default.

---

## Configuration
All settings live in a single YAML file:

```
Windows : %USERPROFILE%\.clausi\config.yml
macOS/Linux : ~/.clausi/config.yml
```

Typical structure:
```yaml
openai_key: "sk-..."

report:
  company_name: "ACME Corp"
  company_logo: "C:/assets/logo.png"
  template:     "default"   # default | detailed | executive

regulations:
  default: EU-AIA            # default selection for scans
```

Useful commands:
| Command                       | Purpose                                |
|--------------------------------|----------------------------------------|
| `clausi config show`           | Display current configuration          |
| `clausi config set [...]`      | Update one or more fields              |
| `clausi config edit`           | Open the YAML in `$EDITOR` / Notepad   |
| `clausi config path`           | Print the config file location         |

---

## Scanning Projects
Basic syntax:
```bash
clausi scan PATH [options]
```

Common options:
| Flag                         | Description                                              |
|------------------------------|----------------------------------------------------------|
| `-r`, `--regulation`         | Regulation key (repeat for multiple)                     |
| `--mode ai \| full`          | `ai` = lightweight analysis (default), `full` = deep scan |
| `--min-severity`             | Minimum severity to report (info, warning, high, critical) |
| `--format pdf \| html \| json \| all`| Report format (use 'all' for PDF, HTML, and JSON)     |
| `--template`                 | Report template (`default`, `detailed`, `executive`)     |
| `-o`, `--output`             | Output directory (otherwise uses config)                 |
| `--max-cost`                 | Maximum cost in dollars (e.g., --max-cost 1.00)          |
| `--skip-confirmation`        | Skip the confirmation prompt                             |
| `--show-details`             | Show per-file token estimates                            |
| `--ignore`                   | Ignore files/directories (can be given multiple times)   |

Examples:
```bash
# EU AI Act – fast scan
clausi scan . -r EU-AIA --mode ai

# GDPR deep scan, HTML report
clausi scan /srv/app -r GDPR --mode full --format html

# Scan against both regulations, use detailed template
clausi scan ~/project -r EU-AIA -r GDPR --template detailed

# Generate all report formats simultaneously
clausi scan . --format all

# Only report high and critical severity issues
clausi scan . -r EU-AIA --min-severity high

# Cost-controlled scan with confirmation skipped
clausi scan . --max-cost 5.00 --skip-confirmation

# Ignore specific files and directories
clausi scan . --ignore "tests/" --ignore "*.log" --ignore "temp/"

# Use .clausiignore file (same rules as .gitignore)
clausi scan . --min-severity warning
```

Upon completion the CLI prints a table of findings and stores:
* `audit.<pdf|html|json>` – the full report
* `audit_metadata.json` – summary of the scan session

---

## Environment Variables
| Variable           | Purpose                                   |
|--------------------|-------------------------------------------|
| `OPENAI_API_KEY`   | Overrides `openai_key` from the YAML file |
| `CLAUSI_OUTPUT_DIR`| Overrides `report.output_dir`             |
| `CLAUSI_TUNNEL_BASE`| Overrides the API base URL (e.g., for tunnel connections) |

Precedence: **CLI flag → environment variable → config file → default**.

### Using CLAUSI_TUNNEL_BASE

The `CLAUSI_TUNNEL_BASE` environment variable allows you to override the default API URL. This is useful when using tunnel connections or when the backend is hosted at a different URL.

```bash
# Use tunnel connection
CLAUSI_TUNNEL_BASE=https://api.clausi.ai clausi scan .

# Use local development server
CLAUSI_TUNNEL_BASE=http://localhost:8000 clausi scan .

# Check current configuration (shows tunnel indicator)
clausi config show
```

When `CLAUSI_TUNNEL_BASE` is set, the CLI will display it in the configuration with a tunnel indicator: `https://api.clausi.ai (via CLAUSI_TUNNEL_BASE)`.

---

## File Ignoring

Clausi CLI supports ignoring files and directories using `.clausiignore` files and command-line patterns.

### .clausiignore File

Create a `.clausiignore` file in your project root (or any parent directory) to specify files and directories to exclude from analysis. Uses the same syntax as `.gitignore`:

```bash
# Ignore test files
tests/
test_*.py

# Ignore build artifacts
build/
dist/
*.egg-info/

# Ignore logs and temporary files
*.log
temp/
tmp/

# Ignore specific files
config.local.py
secrets.json
```

### Command-line Ignoring

Use the `--ignore` flag to specify patterns directly:

```bash
# Ignore multiple patterns
clausi scan . --ignore "tests/" --ignore "*.log" --ignore "temp/"

# Ignore specific files
clausi scan . --ignore "config.local.py" --ignore "secrets.json"
```

### Ignore Rules

- **Patterns**: Use glob patterns (e.g., `*.py`, `tests/`, `**/temp/`)
- **Comments**: Lines starting with `#` are ignored
- **Search Path**: CLI searches upward from project root for `.clausiignore`
- **Combined**: Both `.clausiignore` and `--ignore` patterns are applied
- **Fallback**: If `pathspec` library is unavailable, ignore functionality is disabled

---

## GitHub Actions

[![Clausi Compliance Scan](https://github.com/earosenfeld/clausi-cli/workflows/Compliance%20Check/badge.svg)](https://github.com/earosenfeld/clausi-cli/actions)

Automate compliance checks in your CI/CD pipeline with the Clausi GitHub Action.

### Quick Setup

1. **Add the action to your workflow:**
   ```yaml
   name: Compliance Check
   
   on:
     pull_request:
       branches: [ main ]
   
   jobs:
     compliance-scan:
       runs-on: ubuntu-latest
       steps:
         - name: Run Clausi Compliance Scan
           uses: ./
           with:
             openai-key: ${{ secrets.OPENAI_API_KEY }}
   ```

2. **Set up the secret:**
   - Go to your repository Settings → Secrets and variables → Actions
   - Add `OPENAI_API_KEY` with your OpenAI API key

3. **Customize the scan:**
   ```yaml
   - name: Run Clausi Compliance Scan
     uses: ./
     with:
       path: 'src/'                    # Scan specific directory
       mode: 'full'                    # Deep analysis
       max-cost: '5.00'               # Cost limit
       regulations: 'EU-AIA,GDPR'     # Multiple regulations
       format: 'html'                 # Report format
       template: 'detailed'           # Report template
       openai-key: ${{ secrets.OPENAI_API_KEY }}
   ```

### Action Inputs

| Input | Description | Default | Required |
|-------|-------------|---------|----------|
| `path` | Path to scan | `.` | No |
| `mode` | Scan mode (`ai` or `full`) | `ai` | No |
| `min-severity` | Minimum severity to report | `info` | No |
| `max-cost` | Maximum cost in dollars | `10.00` | No |
| `regulations` | Comma-separated regulations | `EU-AIA` | No |
| `format` | Report format (`pdf`, `html`, `json`, `all`) | `html` | No |
| `template` | Report template | `default` | No |
| `ignore` | Comma-separated ignore patterns | `` | No |
| `openai-key` | OpenAI API key | - | **Yes** |
| `skip-confirmation` | Skip confirmation prompt | `true` | No |

### Example Workflows

**Basic compliance check:**
```yaml
- uses: ./
  with:
    openai-key: ${{ secrets.OPENAI_API_KEY }}
```

**Comprehensive audit:**
```yaml
- uses: ./
  with:
    mode: 'full'
    max-cost: '20.00'
    regulations: 'EU-AIA,GDPR,ISO-42001'
    format: 'pdf'
    template: 'detailed'
    openai-key: ${{ secrets.OPENAI_API_KEY }}
```

**Cost-conscious scanning:**
```yaml
- uses: ./
  with:
    mode: 'ai'
    max-cost: '2.00'
    regulations: 'EU-AIA'
    format: 'html'
    openai-key: ${{ secrets.OPENAI_API_KEY }}
```

**With ignore patterns:**
```yaml
- uses: ./
  with:
    mode: 'ai'
    min-severity: 'warning'
    ignore: 'tests/,*.log,temp/'
    openai-key: ${{ secrets.OPENAI_API_KEY }}
```

**Generate all report formats:**
```yaml
- uses: ./
  with:
    format: 'all'
    openai-key: ${{ secrets.OPENAI_API_KEY }}
```

The action will:
- Install and configure Clausi CLI
- Run the compliance scan
- Upload the report as an artifact
- Continue on error (won't fail your build)

---

## API Endpoints
The CLI communicates with the Clausi platform through two main endpoints:

### 1. `/api/clausi/estimate`
Estimates token usage and cost before running the full scan.

**Expected Response:**
```json
{
  "total_tokens": 1234,
  "prompt_tokens": 1000,
  "completion_tokens": 234,
  "estimated_cost": 0.002,
  "regulation_breakdown": [
    {
      "regulation": "EU-AIA",
      "total_tokens": 1234,
      "estimated_cost": 0.002
    }
  ],
  "file_breakdown": [
    {
      "path": "path/to/file.py",
      "tokens": 200,
      "estimated_cost": 0.0004,
      "too_large": false
    }
  ]
}
```

### 2. `/api/clausi/scan`
Performs the actual compliance analysis and generates the report.

**Expected Response:**
```json
{
  "findings": [
    {
      "clause_id": "A.1.2",
      "violation": true,
      "severity": "high",
      "location": "file.py:123",
      "description": "Description of the finding"
    }
  ],
  "token_usage": {
    "total_tokens": 1234,
    "cost": 0.002
  },
  "generated_reports": [
    {
      "format": "pdf",
      "filename": "audit.pdf"
    },
    {
      "format": "html", 
      "filename": "audit.html"
    },
    {
      "format": "json",
      "filename": "audit.json"
    }
  ]
}
```

---

## Development & Contribution
1. Install dev dependencies as shown in the installation table.
2. Run tests:
   ```bash
   pytest
   ```
3. Lint and format:
   ```bash
   ruff check .    # static analysis
   ruff format .   # auto-format (Black style)
   ```
4. Submit pull requests against `main`.

---

## License
Licensed under the MIT License – © Clausi 2025.