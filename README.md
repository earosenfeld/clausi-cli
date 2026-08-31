# Clausi CLI

> **The compliance scanner that never sees your code.**
>
> Free, local AI compliance auditing for **EU AI Act**, **GDPR**, **ISO 42001**, **HIPAA**, and **SOC 2**.

**Python:** 3.8+ | **License:** MIT

## Your code never leaves your machine to reach Clausi

Clausi runs entirely on your machine: file discovery, clause matching,
caching, and report generation all happen locally. There is no Clausi
server in the scan path, no account, no login, and no credits system.
We never receive, store, or process your source code - it is architecturally
impossible, because there's no backend for it to go to.

**What does leave your machine:** to run the AI analysis, Clausi sends
relevant code snippets to the AI provider *you* choose - either through a
coding agent already installed and signed in on your machine (Claude Code or
the Codex CLI), or through your own Anthropic (`api.anthropic.com`) or OpenAI
(`api.openai.com`) account under your own API key. Either way you're billed
by that provider, not by us. That is a materially different trust boundary
than sending your code to Clausi:
you already have a vendor relationship and a DPA with Anthropic or OpenAI,
you control the account, and you can revoke the key at any time. Clausi
itself is simply never in that data path.

**Why this matters if you're evaluating Clausi for a regulated org:** every
hosted compliance-scanning competitor requires shipping your source to a
third-party server, which typically triggers a vendor security review, a
new DPA, a data-residency assessment, and legal sign-off before anyone on
your team can run a scan. Because Clausi has no backend in the scan path,
none of that applies to Clausi itself - the only third party in scope is
the AI provider you already use.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Interactive Mode](#interactive-mode)
4. [Direct Commands](#direct-commands)
5. [AI Providers](#ai-providers)
6. [Regulation Packs](#regulation-packs)
7. [Local Caching](#local-caching)
8. [Configuration](#configuration)
9. [Custom Regulations](#custom-regulations)
10. [CLI Reference](#cli-reference)
11. [GitHub Actions](#github-actions)
12. [License](#license)

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

**Already have Claude Code or Codex installed? You need no API key at all:**

```bash
# Scan current directory against the EU AI Act using your local Claude Code
clausi scan . -r EU-AIA --claude-code

# ...or your local Codex CLI
clausi scan . -r EU-AIA --codex
```

This routes the analysis through the agent CLI already on your machine, billed
under the subscription you already pay for. Nothing extra to sign up for.

**Or bring your own API key:**

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
# or: export OPENAI_API_KEY=sk-your-key-here

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
3. **Select model** - e.g. claude-opus-5, gpt-4o
4. **Choose regulations** - one, several, or a custom regulation
5. **Select preset** (optional) - all clauses, critical-only, or high-priority

After configuration, the wizard shows the equivalent CLI command and runs the scan.

`clausi docs generate` (AI-powered docs generation) also runs fully locally,
BYOK - see [Direct Commands](#direct-commands).

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

Reduce scan time and cost by focusing on specific clauses. A narrowed scan is a
triage pass, not an audit: clauses outside the scope are never assessed, and a
violation of one of them is reported against whichever in-scope clause fits best,
or not at all. Every report states its own clause scope.

```bash
# Only critical clauses (roughly 60-85% fewer clauses scanned, regulation-dependent)
clausi scan . --preset critical-only

# Only high-priority clauses
clausi scan . --preset high-priority

# Include specific clauses
clausi scan . -r EU-AIA --include Article-9 --include Article-13

# Exclude specific clauses
clausi scan . -r EU-AIA --exclude Article-10
```

Clause IDs are matched exactly against the `id:` fields in the regulation
pack, so use the real article/clause identifiers - `Article-9` for the EU AI
Act, `Clause-4` for ISO 42001, `Security-Rule-164.308` for HIPAA. To browse
the IDs in a pack, use the interactive picker:

```bash
clausi scan . -r EU-AIA --select-clauses
```

### Output Options

```bash
# Open findings.md in your editor when the scan finishes (off by default)
clausi scan . --open-findings

# Force it off, overriding ui.auto_open_findings in your config
clausi scan . --no-open-findings

# Show summary in terminal
clausi scan . --show-markdown

# Show cache hit/miss statistics
clausi scan . --show-cache-stats

# Skip the local cache for this run
clausi scan . --no-cache
```

Every scan writes five local customer outputs:

- `report.pdf` - a stakeholder-ready decision brief, action plan, detailed
  evidence cards, and clause traceability matrix
- `findings.md` - the complete engineering findings
- `compliance_report.md` - a concise readiness summary
- `traceability_matrix.md` - clause-to-finding coverage
- `remediation_register.csv` - an operational owner, due-date, status, ticket,
  risk, and closure-evidence register for Excel, Sheets, or a GRC import

Clausi also writes `scan_snapshot.json` beside the reports and maintains
`.clausi/remediation.yml` in the scanned project. Finding IDs remain stable
across report ordering, customer-entered workflow fields survive rescans, and
the next report classifies findings as new, changed, unchanged, reopened, or
no longer detected.

PDF and register generation run locally alongside the scan; they do not use a browser,
Clausi server, or third-party rendering service.

### Documentation Generation

```bash
# Generate index.md, architecture.md, components.md, security.md locally
clausi docs generate

# No API key needed - use a local agent CLI
clausi docs generate --claude-code
clausi docs generate --codex

# Or force an API-key provider
clausi docs generate --claude
clausi docs generate --openai gpt-4o

# Output elsewhere / scope files
clausi docs generate -o ./docs --exclude "tests/*"
```

Runs the same way as `scan`: same providers, same auto-detection, your
machine, no backend. It also honors `.clausiignore`, so anything you've
excluded from scanning is not sent to your AI provider here either.

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

Clausi needs an AI model to do the analysis, and there are two ways to give it
one. Either works with every regulation, flag, and report format.

| Route | Flag | Needs an API key? | Who bills you |
|-------|------|-------------------|---------------|
| Local agent CLI | `--claude-code`, `--codex` | No | Nobody extra - it runs under the subscription you already have |
| Your own API key | `--claude`, `--openai` | Yes | Anthropic or OpenAI, per token |

### Local agent CLIs (no API key)

If you already have **Claude Code** or the **Codex CLI** installed, Clausi will
drive it directly:

```bash
# Use your local Claude Code installation
clausi scan . -r EU-AIA --claude-code

# Use your local Codex CLI
clausi scan . -r EU-AIA --codex
```

Clausi shells out to the `claude` or `codex` binary already on your `PATH` and
passes the prompt over stdin. There is no API key to configure and no
per-token charge from Clausi or from the provider's API - the work runs
under whatever plan already covers that CLI. Estimated cost is reported as
`$0.00` for these runs, because from Clausi's side it is.

Requirements:

- The relevant CLI must be installed and on your `PATH` (`claude --version`
  or `codex --version` should work in the same shell).
- You must already be signed in to that CLI.

If you pass `--claude-code` or `--codex` and the binary isn't found, Clausi
tells you which one is missing rather than silently falling back.

### Claude (Anthropic)

```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
clausi scan . --claude

# Or specify a model
clausi scan . --claude claude-sonnet-5
```

### OpenAI

```bash
export OPENAI_API_KEY=sk-your-key-here
clausi scan . --openai

# Or specify a model
clausi scan . --openai gpt-4o
```

### Auto-detection

Pass no provider flag and Clausi works out what you have, in this order:

1. `ANTHROPIC_API_KEY`
2. `OPENAI_API_KEY`
3. A local Claude Code installation
4. A local Codex CLI installation
5. Otherwise it exits, showing you both routes

So on a machine with Claude Code and no keys set, a bare `clausi scan . -r GDPR`
just works.

When you use an API key, you are billed directly by Anthropic/OpenAI for the
tokens used. Clausi itself is free either way, has no backend in the scan path,
and never sees your key or your code - only the AI provider you chose does,
under your own account.

---

## Regulation Packs

Clausi ships five built-in regulation packs, bundled as local YAML - no
network fetch, no version drift between what you scan against and what's
on disk:

| Regulation | Code | Effective date |
|------------|------|-----------------|
| EU AI Act | `EU-AIA` | 2024-08-01 |
| GDPR | `GDPR` | 2018-05-25 |
| ISO/IEC 42001:2023 | `ISO-42001` | 2023-12-18 |
| HIPAA | `HIPAA` | 2013-03-26 |
| SOC 2 | `SOC2` | 2022-01-01 |

Each pack is versioned (`version:` + `effective_date:` in the YAML) so a
scan report can always say exactly which revision of a regulation it was
checked against. `clausi scan` prints the pack version alongside each
regulation name. As frameworks are amended, packs get dated updates rather
than silent edits.

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
  model: claude-opus-5

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
| `clausi docs generate PATH` | Generate documentation (local, BYOK) |
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
| `--claude-code` | Use your local Claude Code CLI (no API key) |
| `--codex` | Use your local Codex CLI (no API key) |
| `--preset TEXT` | Use preset: `critical-only`, `high-priority` |
| `--include TEXT` | Include specific clauses (can repeat) |
| `--exclude TEXT` | Exclude specific clauses (can repeat) |
| `--open-findings` / `--no-open-findings` | Open findings.md in your editor after the scan (default: off) |
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
