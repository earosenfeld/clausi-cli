# Clausi CLI

> Free, local AI compliance auditing for **EU AI Act**, **GDPR**, **ISO 42001**, **HIPAA**, and **SOC 2**.

**Python:** 3.8+ | **License:** MIT

Clausi runs entirely on your machine. Bring your own Anthropic or OpenAI API
key - file discovery, AI scanning, clause matching, caching, and report
generation all happen locally. Nothing is uploaded to a Clausi server, and
there's no account, login, or credits system. You pay your AI provider
directly for the tokens you use.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Interactive Mode](#interactive-mode)
4. [Direct Commands](#direct-commands)
5. [AI Providers](#ai-providers)
6. [Local Caching](#local-caching)
7. [Configuration](#configuration)
8. [Custom Regulations](#custom-regulations)
9. [CLI Reference](#cli-reference)
10. [GitHub Actions](#github-actions)
11. [License](#license)

---

## Installation

```bash
pip install clausi
```

Verify installation:
```bash
clausi --version
```

---

## Quick Start

```bash
# Set an API key once
export ANTHROPIC_API_KEY=sk-ant-your-key-here
# or: export OPENAI_API_KEY=sk-your-key-here

# Scan current directory against EU AI Act
clausi scan . -r EU-AIA

# Scan with multiple regulations
clausi scan . -r EU-AIA -r GDPR
```

Or run `clausi` with no arguments for a guided interactive wizard.

---

## Interactive Mode

Run `clausi` with no arguments to launch the interactive TUI:

```
$ clausi

Clausi - AI Compliance Auditing

? What would you like to do?
→ 1. Scan a project for compliance
  2. View remediation guide
  3. View configuration
  4. List available AI models
  5. Run setup wizard
  6. Show help
  7. Exit Clausi
```

**Scan Wizard Steps:**

1. **Select project location** - current directory, file explorer, or manual path
2. **Choose AI provider** - Claude (Anthropic key) or OpenAI (OpenAI key)
3. **Select model** - e.g. claude-3-5-sonnet, gpt-4o
4. **Choose regulations** - one, several, or a custom regulation
5. **Select preset** (optional) - all clauses, critical-only, or high-priority

After configuration, the wizard shows the equivalent CLI command and runs the scan.

> `clausi docs generate` (AI-powered docs generation) previously ran through
> the hosted Clausi backend, which has been retired. A local BYOK version is
> planned but not built yet.

---

## Direct Commands

### Basic Scan

```bash
# Scan current directory
clausi scan .

# Scan specific path
clausi scan /path/to/project

# Scan with specific regulation
clausi scan . -r EU-AIA

# Multiple regulations
clausi scan . -r EU-AIA -r GDPR -r HIPAA
```

### Clause Scoping

Reduce scan time and cost by focusing on specific clauses:

```bash
# Only critical clauses (60-80% cost reduction)
clausi scan . --preset critical-only

# Only high-priority clauses
clausi scan . --preset high-priority

# Include specific clauses
clausi scan . --include EUAIA-3.1 --include EUAIA-9.1

# Exclude specific clauses
clausi scan . --exclude EUAIA-10.2
```

### Output Options

```bash
# Auto-open findings in your editor
clausi scan . --open-findings

# Show summary in terminal
clausi scan . --show-markdown

# Show cache hit/miss statistics
clausi scan . --show-cache-stats

# Skip the local cache for this run
clausi scan . --no-cache
```

Reports are always written as Markdown (`findings.md`, `compliance_report.md`,
`traceability_matrix.md`) - no PDF/HTML export yet.

### Other Commands

```bash
# View/edit configuration
clausi config show
clausi config edit

# Setup wizard (saves your API key locally)
clausi setup

# List available AI models
clausi models list

# Local cache management
clausi cache stats
clausi cache clear
```

---

## AI Providers

Clausi is BYOK-only - pick whichever provider you already have a key for:

### Claude (Anthropic)

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
clausi scan . --claude

# Or specify a model
clausi scan . --claude claude-3-5-sonnet-20241022
```

### OpenAI

```bash
export OPENAI_API_KEY=sk-your-key-here
clausi scan . --openai

# Or specify a model
clausi scan . --openai gpt-4o
```

If neither `--claude` nor `--openai` is passed, Clausi auto-detects: it uses
`ANTHROPIC_API_KEY` if set, otherwise `OPENAI_API_KEY`, otherwise it exits
with instructions for getting a key.

You are billed directly by Anthropic/OpenAI for the tokens used - Clausi
itself is free and doesn't see your key or your code.

---

## Local Caching

Clausi caches scan results on disk at `~/.clausi/cache/`, keyed by file
content hash + regulation + clause scope + provider + model. Re-running a
scan on an unchanged file serves the cached result instead of calling the AI
API again - this is the main lever for keeping repeat scans fast and cheap.

```bash
clausi cache stats     # show cache directory + entry count
clausi cache clear     # wipe the cache (forces a full re-scan)
clausi scan . --no-cache   # bypass the cache for one run
```

---

## Configuration

Configuration file location:
```
Windows:     %USERPROFILE%\.clausi\config.yml
macOS/Linux: ~/.clausi/config.yml
```

Example configuration:
```yaml
ai:
  provider: claude
  model: claude-3-5-sonnet-20241022

api_keys:
  anthropic: "sk-ant-..."         # For --claude mode
  openai: "sk-..."                # For --openai mode

report:
  output_dir: clausi/reports
  company_name: ""

cache:
  enabled: true
  ttl_days: 30

ui:
  show_markdown: true             # Show summary after scan
  auto_open_findings: true        # Auto-open findings.md
```

### Config Commands

```bash
clausi config show    # Display current config
clausi config edit    # Open in editor
clausi config path    # Print config file location
```

---

## Custom Regulations

Create your own compliance regulations with custom clauses.

### Locations

- **Global:** `~/.clausi/custom_regulations/*.yml`
- **Project-specific:** `.clausi/regulations/*.yml`

### Example

Create `~/.clausi/custom_regulations/company-security.yml`:

```yaml
name: "Company Security Policy"
description: "Internal security requirements"

clauses:
  - id: "SEC-001"
    title: "Authentication Requirements"
    description: "All systems must implement proper authentication"
    requirements:
      - "Implement multi-factor authentication"
      - "Support TOTP or hardware security keys"

  - id: "SEC-002"
    title: "Data Encryption"
    description: "Sensitive data must be encrypted"
    requirements:
      - "Encrypt data at rest using AES-256"
      - "Use TLS 1.3 for data in transit"
```

### Usage

```bash
# Use custom regulation
clausi scan . -r COMPANY-SECURITY

# Combine with built-in regulations
clausi scan . -r EU-AIA -r COMPANY-SECURITY
```

---

## CLI Reference

### Global Options

```
clausi --version    Show version
clausi --help       Show help
```

### Commands

| Command | Description |
|---------|-------------|
| `clausi` | Launch interactive mode |
| `clausi scan PATH` | Run compliance scan (local, BYOK) |
| `clausi setup` | First-time setup wizard |
| `clausi config show` | Display configuration |
| `clausi config edit` | Edit configuration |
| `clausi models list` | List available AI models |
| `clausi cache stats` | Show local cache info |
| `clausi cache clear` | Clear local cache |

### Scan Options

| Option | Description |
|--------|-------------|
| `-r, --regulation TEXT` | Regulation to scan against (can repeat) |
| `--claude [MODEL]` | Use Claude with your Anthropic API key |
| `--openai [MODEL]` | Use OpenAI with your API key |
| `--preset TEXT` | Use preset: `critical-only`, `high-priority` |
| `--include TEXT` | Include specific clauses (can repeat) |
| `--exclude TEXT` | Exclude specific clauses (can repeat) |
| `--open-findings` | Auto-open findings.md after scan |
| `--show-markdown` | Display summary in terminal |
| `--show-cache-stats` | Show cache hit/miss statistics |
| `--no-cache` | Disable the local cache for this run |
| `--skip-confirmation, -y` | Skip cost confirmation prompt |
| `--max-cost FLOAT` | Abort if the rough estimate exceeds this |
| `--ignore PATTERN` | Ignore files/dirs (can repeat) |
| `-o, --output PATH` | Output directory |
| `-v, --verbose` | Verbose output |

---

## GitHub Actions

Automate compliance checks in your CI/CD pipeline:

```yaml
name: Compliance Check

on:
  pull_request:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Clausi
        run: pip install clausi

      - name: Run Compliance Scan
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          clausi scan . -r EU-AIA --claude --skip-confirmation

      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: compliance-report
          path: clausi/reports/
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for `--claude` mode |
| `OPENAI_API_KEY` | OpenAI API key for `--openai` mode |

Precedence: CLI flag → Environment variable → Config file → Default

---

## File Ignoring

Create `.clausiignore` in your project root (same syntax as `.gitignore`):

```bash
# Ignore test files
tests/
*_test.py

# Ignore build artifacts
build/
dist/
node_modules/

# Ignore logs
*.log
```

Or use the `--ignore` flag:

```bash
clausi scan . --ignore "tests/" --ignore "*.log"
```

---

## Support

- **GitHub:** https://github.com/earosenfeld/clausi-cli

---

## License

MIT License - © Clausi 2026
