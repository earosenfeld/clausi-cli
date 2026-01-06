# Clausi CLI

> AI-powered compliance auditing for **EU AI Act**, **GDPR**, **ISO 42001**, **HIPAA**, and **SOC 2**.

**Version:** 1.0.1 | **Python:** 3.8+ | **License:** MIT

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Interactive Mode](#interactive-mode)
4. [Direct Commands](#direct-commands)
5. [AI Providers](#ai-providers)
6. [Pricing](#pricing)
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
clausi --version  # Should show: 1.0.1
```

---

## Quick Start

### Option 1: Interactive Mode (Recommended)

```bash
clausi
```

This launches a guided wizard with arrow-key navigation. Perfect for first-time users.

### Option 2: Direct Command

```bash
# Scan current directory against EU AI Act
clausi scan . -r EU-AIA

# Scan with multiple regulations
clausi scan . -r EU-AIA -r GDPR
```

---

## Interactive Mode

Run `clausi` with no arguments to launch the interactive TUI:

```
$ clausi

Clausi - AI Compliance Auditing

? What would you like to do?
→ 1. Scan a project for compliance
  2. Generate documentation
  3. View remediation guide
  4. View configuration
  5. List available AI models
  6. Run setup wizard
  7. Show help
  8. Exit Clausi
```

### Features

**Main Menu Options:**
- **Scan a project** - Full scan wizard with step-by-step guidance
- **Generate documentation** - AI-powered docs generation for your codebase
- **View remediation guide** - Open previously generated fix suggestions
- **View configuration** - Display current settings
- **List AI models** - Show available Claude and OpenAI models
- **Setup wizard** - Configure API keys and preferences

**Scan Wizard Steps:**

1. **Select project location**
   - Current directory
   - Open native file explorer (Windows/Mac/Linux)
   - Browse directories in terminal
   - Type path manually

2. **Choose AI provider**
   - Clausi AI (no API key needed)
   - Claude BYOK (your Anthropic key)
   - OpenAI BYOK (your OpenAI key)

3. **Select model** (for BYOK modes)
   - Claude: claude-sonnet-4, claude-3-5-sonnet, claude-3-5-haiku
   - OpenAI: gpt-4o, gpt-4o-mini, gpt-4-turbo

4. **Choose regulations**
   - Single regulation (quick select)
   - Multiple regulations
   - Custom regulations
   - Create new custom regulation inline

5. **Select preset** (optional)
   - Standard scan (all clauses)
   - Critical-only (faster, cheaper)
   - High-priority

After configuration, the wizard shows the equivalent CLI command and runs the scan.

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

# Show cache statistics (cost savings)
clausi scan . --show-cache-stats

# Choose report format
clausi scan . --format pdf      # Default
clausi scan . --format html
clausi scan . --format json
clausi scan . --format all      # All formats
```

### Other Commands

```bash
# Check account balance
clausi balance

# View/edit configuration
clausi config show
clausi config edit

# Setup wizard
clausi setup

# List available AI models
clausi models list

# Generate documentation
clausi docs /path/to/project

# Authenticate
clausi login
```

---

## AI Providers

Clausi supports three modes of operation:

### 1. Clausi AI (Default)

No API key required. We handle the AI calls.

```bash
clausi scan .
```

### 2. Claude BYOK (Bring Your Own Key)

Use your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
clausi scan . --claude

# Or specify a model
clausi scan . --claude claude-sonnet-4-20250514
```

### 3. OpenAI BYOK

Use your OpenAI API key:

```bash
export OPENAI_API_KEY=sk-your-key-here
clausi scan . --openai

# Or specify a model
clausi scan . --openai gpt-4o
```

---

## Pricing

### Clausi AI (Hosted)

- **Minimum:** $3.00 per scan (covers up to 100k lines of code)
- **Above 100k LOC:** +$0.40 per additional 100k lines
- **Maximum:** 200k LOC per scan (use BYOK for larger projects)

### BYOK (Bring Your Own Key)

- **Platform fee:** $0.50 minimum, +$0.10 per 100k LOC above 100k
- **No size limit** - scan projects of any size
- **You pay AI costs** directly to Anthropic/OpenAI

### Credits

- 1 credit = $0.10
- New accounts start with 20 free credits ($2.00 value)
- Purchase more at https://clausi.ai

---

## Configuration

Configuration file location:
```
Windows:     %USERPROFILE%\.clausi\config.yml
macOS/Linux: ~/.clausi/config.yml
```

Example configuration:
```yaml
api_token: "cltoken_..."          # Auto-saved after login

api_keys:
  anthropic: "sk-ant-..."         # For --claude mode
  openai: "sk-..."                # For --openai mode

api:
  url: https://api.clausi.ai
  timeout: 300

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
version: "1.0"

clauses:
  - id: "SEC-001"
    title: "Authentication Requirements"
    description: "All systems must implement proper authentication"
    requirements:
      - "Implement multi-factor authentication"
      - "Support TOTP or hardware security keys"
    severity: "critical"

  - id: "SEC-002"
    title: "Data Encryption"
    description: "Sensitive data must be encrypted"
    requirements:
      - "Encrypt data at rest using AES-256"
      - "Use TLS 1.3 for data in transit"
    severity: "high"
```

### Usage

```bash
# Use custom regulation
clausi scan . -r COMPANY-SECURITY

# Combine with built-in regulations
clausi scan . -r EU-AIA -r COMPANY-SECURITY
```

### Create via Interactive Mode

The interactive mode can create custom regulations for you:

1. Run `clausi`
2. Select "Scan a project"
3. At regulation selection, choose "Create new custom regulation"
4. Follow the prompts

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
| `clausi scan PATH` | Run compliance scan |
| `clausi docs PATH` | Generate documentation |
| `clausi balance` | Show account balance |
| `clausi login` | Authenticate with Clausi |
| `clausi setup` | First-time setup wizard |
| `clausi config show` | Display configuration |
| `clausi config edit` | Edit configuration |
| `clausi models list` | List available AI models |

### Scan Options

| Option | Description |
|--------|-------------|
| `-r, --regulation TEXT` | Regulation to scan against (can repeat) |
| `--claude [MODEL]` | Use Claude with your API key |
| `--openai [MODEL]` | Use OpenAI with your API key |
| `--preset TEXT` | Use preset: `critical-only`, `high-priority` |
| `--include TEXT` | Include specific clauses (can repeat) |
| `--exclude TEXT` | Exclude specific clauses (can repeat) |
| `--format FORMAT` | Output: `pdf`, `html`, `json`, `all` |
| `--open-findings` | Auto-open findings.md after scan |
| `--show-markdown` | Display summary in terminal |
| `--show-cache-stats` | Show cache hit/miss statistics |
| `--skip-confirmation` | Skip cost confirmation prompt |
| `--max-cost FLOAT` | Maximum cost limit in dollars |
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
          clausi scan . -r EU-AIA --claude --skip-confirmation --format html

      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: compliance-report
          path: clausi/
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key for `--claude` mode |
| `OPENAI_API_KEY` | OpenAI API key for `--openai` mode |
| `CLAUSI_TUNNEL_BASE` | Override API URL (for local dev) |

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

- **Website:** https://clausi.ai
- **Documentation:** https://docs.clausi.ai
- **GitHub:** https://github.com/earosenfeld/clausi-cli

---

## License

MIT License - © Clausi 2025
