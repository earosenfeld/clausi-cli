# CLAUDE.md - Clausi CLI Developer Guide

> **Purpose:** Comprehensive guide for AI assistants working on Clausi CLI development
>
> **Last Updated:** 2025-12-24
> **Version:** 1.0.0
> **Language:** Python 3.8+
> **Framework:** Click (CLI), Rich (UI), Questionary (Interactive)

---

## Table of Contents

**PART 1: UNDERSTANDING THE SYSTEM**
1. [What is Clausi CLI](#what-is-clausi-cli)
2. [Architecture Overview](#architecture-overview)
3. [Directory Structure](#directory-structure)
4. [Key Concepts](#key-concepts)

**PART 2: KEY COMPONENTS**
5. [cli.py - Main Orchestration](#clipy---main-orchestration)
6. [payment.py - Payment & API Communication](#paymentpy---payment--api-communication)
7. [interactive.py - Interactive Mode](#interactivepy---interactive-mode)
8. [scanner.py - File Discovery](#scannerpy---file-discovery)
9. [config.py - Configuration Management](#configpy---configuration-management)
10. [regulations.py - Custom Regulations](#regulationspy---custom-regulations)

**PART 3: DEVELOPMENT GUIDE**
11. [Common Development Tasks](#common-development-tasks)
12. [Code Patterns to Follow](#code-patterns-to-follow)
13. [Testing Guide](#testing-guide)
14. [Packaging & Distribution](#packaging--distribution)

**PART 4: REFERENCE**
15. [Quick Function Reference](#quick-function-reference)
16. [Important Patterns](#important-patterns)
17. [Gotchas & Pitfalls](#gotchas--pitfalls)
18. [Recent Changes](#recent-changes)

---

## PART 1: UNDERSTANDING THE SYSTEM

### What is Clausi CLI

**Purpose:** Command-line tool for AI compliance auditing against regulatory frameworks (EU AI Act, GDPR, ISO 42001, HIPAA, SOC2).

**Key Users:**
- Developers checking compliance during development
- Security teams running audits
- DevOps teams in CI/CD pipelines

**Core Workflows:**

1. **Interactive Mode** (Beginner-friendly)
   ```bash
   clausi
   # Guided wizard with arrow key navigation
   ```

2. **Direct Commands** (Power users)
   ```bash
   clausi scan . -r EU-AIA --claude --preset critical-only --open-findings
   ```

3. **CI/CD Integration**
   ```yaml
   # GitHub Actions
   - uses: clausi/clausi-cli@v1
     with:
       openai-key: ${{ secrets.OPENAI_API_KEY }}
   ```

**Three AI Provider Modes:**

| Mode | CLI Flag | API Key Required | Backend Behavior | Cost |
|------|----------|------------------|------------------|------|
| Clausi AI (default) | None | ❌ No | Uses backend's AI | $2 min via credits |
| Claude (BYOK) | `--claude [MODEL]` | ✅ Yes (Anthropic) | Uses customer's key | $0.50 platform fee |
| OpenAI (BYOK) | `--openai [MODEL]` | ✅ Yes (OpenAI) | Uses customer's key | $0.50 platform fee |

---

### Architecture Overview

#### High-Level Flow

```
User Command
    ↓
Interactive Mode OR Direct Command
    ↓
Provider Detection (clausi/claude/openai)
    ↓
API Key Validation (if needed)
    ↓
File Discovery & Filtering (.clausiignore)
    ↓
Token Estimation (GET /api/clausi/estimate)
    ↓
User Confirmation
    ↓
Scan Execution (POST /api/clausi/scan/async)
    ↓
Report Download & Display
```

#### System Components

```
┌─────────────────────────────────────────────────────────┐
│                    User's Machine                        │
│                                                          │
│  ┌──────────────┐         ┌──────────────────┐          │
│  │ clausi       │────────▶│  Interactive      │          │
│  │ (entry)      │         │  Mode (TUI)       │          │
│  └──────────────┘         └──────────────────┘          │
│         │                          │                     │
│         ▼                          ▼                     │
│  ┌──────────────────────────────────────────┐           │
│  │           cli.py (orchestrator)          │           │
│  │  - Command routing                       │           │
│  │  - Provider detection                    │           │
│  │  - API key validation                    │           │
│  └──────────────────────────────────────────┘           │
│         │                          │                     │
│    ┌────┴────┐              ┌─────┴──────┐              │
│    ▼         ▼              ▼            ▼              │
│  ┌────┐  ┌────────┐    ┌────────┐  ┌─────────┐         │
│  │core│  │ utils  │    │  api   │  │   tui   │         │
│  │────│  │────────│    │────────│  │─────────│         │
│  │pay │  │config  │    │client  │  │interact │         │
│  │scan│  │emoji   │    │        │  │app      │         │
│  │sel │  │output  │    │        │  │         │         │
│  │    │  │regs    │    │        │  │         │         │
│  └────┘  └────────┘    └────────┘  └─────────┘         │
│     │          │            │                            │
└─────┼──────────┼────────────┼────────────────────────────┘
      │          │            │
      └──────────┴────────────┘
                 │
                 ▼
      ┌──────────────────────┐
      │  Backend API         │
      │  api.clausi.ai       │
      │                      │
      │  /estimate           │
      │  /scan/async         │
      │  /jobs/{id}/status   │
      │  /jobs/{id}/result   │
      └──────────────────────┘
```

---

### Directory Structure

```
clausi-cli/
├── clausi/                          # Main package
│   ├── __init__.py                 # Version: __version__ = "1.0.0"
│   ├── __main__.py                 # Entry: python -m clausi
│   ├── cli.py                      # ★ CRITICAL: Main CLI commands
│   ├── config.example.yml          # Example config
│   │
│   ├── api/                        # Backend communication
│   │   ├── __init__.py
│   │   └── client.py               # HTTP client wrapper
│   │
│   ├── core/                       # Business logic
│   │   ├── __init__.py
│   │   ├── payment.py              # ★ CRITICAL: Payment & scan requests
│   │   ├── scanner.py              # File discovery & filtering
│   │   └── clause_selector.py     # Interactive clause selection
│   │
│   ├── utils/                      # Utilities
│   │   ├── __init__.py
│   │   ├── config.py               # Config file management
│   │   ├── emoji.py                # Cross-platform emoji/ASCII
│   │   ├── output.py               # Output formatting
│   │   ├── regulations.py          # Custom regulations
│   │   ├── console.py              # Rich console instance
│   │   └── custom_regulations_README.md
│   │
│   ├── tui/                        # Terminal UI
│   │   ├── __init__.py
│   │   ├── interactive.py          # ★ NEW: Interactive mode (questionary)
│   │   ├── app.py                  # Legacy Textual TUI
│   │   └── screens/
│   │       ├── __init__.py
│   │       └── config.py           # Config editor screen
│   │
│   └── templates/                  # Report templates
│       ├── default/
│       ├── detailed/
│       └── executive/
│
├── tests/                          # Test suite
│   ├── test_cli.py
│   └── test_v1_features.py
│
├── CLAUDE/                         # AI developer documentation
│   ├── CLAUDE.md                   # ★ THIS FILE
│   ├── PRICING_STRATEGY.md         # Business pricing decisions
│   └── TESTING.md                  # Testing details
│
├── .clausiignore                   # Default ignore patterns
├── MANIFEST.in                     # Package inclusion rules
├── pyproject.toml                  # Modern build config
├── setup.py                        # Package setup
├── README.md                       # User documentation
└── LICENSE                         # MIT License
```

---

### Key Concepts

#### 1. AI Providers

**Three modes of operation:**

```python
# Mode 1: Clausi AI (default) - No API key needed
provider = "clausi"
api_key = None
# Backend uses its own AI, charges via credit system

# Mode 2: Claude (BYOK) - User's Anthropic key
provider = "claude"
api_key = "sk-ant-..."
# Backend uses customer's key, charges $0.50 platform fee

# Mode 3: OpenAI (BYOK) - User's OpenAI key
provider = "openai"
api_key = "sk-..."
# Backend uses customer's key, charges $0.50 platform fee
```

**How CLI determines provider:**

```python
# cli.py:578-596
if claude_model is not None:
    provider = "claude"
    model = claude_model if claude_model != "" else "claude-3-5-sonnet-20241022"
elif openai_model is not None:
    provider = "openai"
    model = openai_model if openai_model != "" else "gpt-4o"
else:
    provider = "clausi"  # Default
    model = None
```

**Critical pattern: Headers must match provider**

```python
# payment.py:232-240
headers = {"Content-Type": "application/json"}

if api_key:  # Only if BYOK mode
    if provider == "claude":
        headers["X-Anthropic-Key"] = api_key
    elif provider == "openai":
        headers["X-OpenAI-Key"] = api_key
# For "clausi" provider, no API key header is added
```

#### 2. Interactive Mode

**When:** User runs `clausi` with no arguments
**How:** Questionary library (arrow key navigation)
**Why:** Make CLI approachable for beginners

**Menu structure:**
```
1. Scan a project for compliance
2. View configuration
3. List available AI models
4. Run setup wizard
5. Show help
6. Exit Clausi
```

**Key features:**
- Arrow key navigation (↑/↓)
- Number shortcuts (type 1-6)
- Graceful cancellation (ESC/Ctrl+C)
- Shows equivalent CLI command

#### 3. Custom Regulations

**Locations:**
- Global: `~/.clausi/custom_regulations/*.yml`
- Project: `{project}/.clausi/regulations/*.yml`

**Format:**
```yaml
name: "Company Security Policy"
description: "Internal security requirements"
version: "1.0"

clauses:
  - id: "SEC-001"
    title: "Authentication Requirements"
    requirements:
      - "Implement multi-factor authentication"
      - "Support TOTP or hardware keys"
    severity: "critical"
```

**Usage:**
```bash
clausi scan . -r COMPANY-SECURITY
```

**Backend integration:**
```python
# Custom regulations sent in request payload
"custom_regulations": [
    {
        "code": "COMPANY-SECURITY",
        "content": { ... }  # YAML content
    }
]
```

#### 4. Payment Flow

**Trial System:**
- First scan without API key triggers trial creation
- Backend returns 401 with token + 20 free credits
- CLI saves token to `~/.clausi/config.yml`
- Subsequent scans use saved token

**Credit System:**
- When credits exhausted, backend returns 402
- CLI opens Stripe checkout in browser
- User completes payment
- User re-runs scan command

**BYOK (Bring Your Own Key):**
- User provides API key via `--claude` or `--openai`
- Backend uses customer's key
- Platform fee charged: $0.50 per scan
- No trial/credits involved

---

## PART 2: KEY COMPONENTS

### cli.py - Main Orchestration

**File:** `clausi/cli.py`
**Lines:** ~1200
**Framework:** Click
**Purpose:** Define CLI commands, orchestrate scan flow

#### Key Functions

**1. Main CLI Group (Lines 536-550)**
```python
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Main entry point - launches interactive mode if no command given"""
    if ctx.invoked_subcommand is None:
        # No command provided, launch interactive mode
        launch_interactive_mode()
```

**2. Scan Command (Lines 548-900)**
```python
@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("-r", "--regulation", multiple=True)
@click.option("--claude", "claude_model", default=None)
@click.option("--openai", "openai_model", default=None)
@click.option("--preset", type=click.Choice(["critical-only", "high-priority"]))
@click.option("--open-findings", is_flag=True)
def scan(path, regulation, claude_model, openai_model, preset, open_findings, ...):
    """Main scan command"""

    # Step 1: Provider detection from flags
    if claude_model is not None:
        provider = "claude"
        model = claude_model if claude_model != "" else config_module.get_ai_model("claude")
    elif openai_model is not None:
        provider = "openai"
        model = openai_model if openai_model != "" else config_module.get_ai_model("openai")
    else:
        provider = "clausi"
        model = None

    # Step 2: API key validation (only if BYOK)
    api_key = _validate_and_get_api_key(provider, model)

    # Step 3: File discovery
    files = scanner.scan_directory(path)
    files = scanner.filter_ignored_files(files, path, ignore_patterns)

    # Step 4: Custom regulations
    custom_regs = regs_module.get_custom_regulations_for_scan(regulations, path)

    # Step 5: Token estimation
    data = {"files": files, "regulations": regulations, "custom_regulations": custom_regs}
    estimate = get_estimate(api_url, api_key, provider, data)

    # Step 6: User confirmation
    console.print(f"Estimated Cost: ${estimate['estimated_cost']:.2f}")
    if not skip_confirmation and not click.confirm("Proceed?"):
        sys.exit(0)

    # Step 7: Execute scan
    result = scan_module.make_async_scan_request(api_url, api_key, provider, data)

    # Step 8: Display results
    display_scan_results(result)
```

**3. Config Commands (Lines 460-520)**
```python
@cli.group()
def config():
    """Configuration management"""

@config.command()
def show():
    """Display current configuration"""

@config.command()
@click.option("--anthropic-key")
@click.option("--openai-key")
def set(**kwargs):
    """Update configuration values"""
```

**4. Interactive Mode Launcher (Lines 243-271)**
```python
def launch_interactive_mode():
    """Launch interactive TUI with error handling"""
    try:
        from clausi.tui.interactive import ClausInteractiveTUI
        tui = ClausInteractiveTUI()
        tui.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
    except Exception as e:
        # Handle terminal compatibility issues
        if "xterm-256color" in str(e) or "Windows console" in str(e):
            console.print("[red]Terminal Compatibility Issue[/red]")
            console.print("\nTry:")
            console.print("  1. Run from Command Prompt (cmd.exe)")
            console.print("  2. Use direct commands: clausi scan --help")
        else:
            console.print(f"[red]Error: {e}[/red]")
```

**5. API Key Validation (Lines 184-241)**
```python
def _validate_and_get_api_key(provider: str, model: str) -> Optional[str]:
    """Validate and retrieve API key based on provider"""

    if provider == "clausi":
        # No API key needed for Clausi hosted AI
        return None

    elif provider == "claude":
        api_key = config_module.get_anthropic_key()
        if not api_key:
            console.print(f"{emoji('crossmark')} [bold red]Anthropic API Key Required[/bold red]")
            console.print("\nTo use Claude, you need an Anthropic API key.")
            console.print("\nOptions:")
            console.print("  1. Set environment variable: export ANTHROPIC_API_KEY=sk-ant-...")
            console.print("  2. Add to config: clausi config set --anthropic-key sk-ant-...")
            console.print("  3. Use Clausi AI instead (no flag needed)")
            sys.exit(1)
        return api_key

    elif provider == "openai":
        api_key = config_module.get_openai_key()
        if not api_key:
            console.print(f"{emoji('crossmark')} [bold red]OpenAI API Key Required[/bold red]")
            console.print("\nTo use OpenAI, you need an OpenAI API key.")
            console.print("\nOptions:")
            console.print("  1. Set environment variable: export OPENAI_API_KEY=sk-...")
            console.print("  2. Add to config: clausi config set --openai-key sk-...")
            console.print("  3. Use Clausi AI instead (no flag needed)")
            sys.exit(1)
        return api_key

    return None
```

#### Important Sections

| What | Lines | Purpose |
|------|-------|---------|
| CLI group & interactive launcher | 536-550 | Entry point, route to interactive or command |
| API key validation | 184-241 | Validate keys based on provider |
| Provider detection | 578-596 | Determine provider from CLI flags |
| Main scan orchestration | 670-900 | Full scan flow |
| Config management | 460-520 | Config CRUD operations |

---

### payment.py - Payment & API Communication

**File:** `clausi/core/payment.py`
**Lines:** ~403
**Purpose:** Handle payment flow, trial system, scan requests

#### Key Functions

**1. Async Scan Request (Lines 216-336)**

```python
def make_async_scan_request(api_url: str, openai_key: str, provider: str, data: Dict) -> Optional[Dict]:
    """
    Make async scan request with job polling (prevents timeouts on large scans).

    Flow:
    1. POST /api/clausi/scan/async → get job_id
    2. Poll GET /api/clausi/jobs/{job_id}/status every 2s
    3. GET /api/clausi/jobs/{job_id}/result when complete
    """

    # Prepare headers based on provider
    headers = {"Content-Type": "application/json"}

    if openai_key:  # Only if BYOK mode
        if provider == "claude":
            headers["X-Anthropic-Key"] = openai_key
        elif provider == "openai":
            headers["X-OpenAI-Key"] = openai_key

    # Add token if available (trial/credits)
    token = get_api_token()
    if token:
        headers["X-Clausi-Token"] = token

    # Start async job
    response = requests.post(
        f"{api_url}/api/clausi/scan/async",
        json=data,
        headers=headers,
        timeout=30
    )
    job_id = response.json()["job_id"]

    # Poll for completion
    with Progress(...) as progress:
        while True:
            status_response = requests.get(
                f"{api_url}/api/clausi/jobs/{job_id}/status",
                timeout=10
            )
            status = status_response.json()["status"]

            if status == "completed":
                break
            elif status == "failed":
                return None

            time.sleep(2)  # Poll every 2 seconds

    # Get final result
    result_response = requests.get(
        f"{api_url}/api/clausi/jobs/{job_id}/result",
        timeout=10
    )

    return result_response.json()
```

**2. Response Handler (Lines 69-144)**

```python
def handle_scan_response(response: requests.Response, api_url: str,
                        openai_key: str, provider: str, data: Dict) -> Optional[Dict]:
    """Handle different response types from scan endpoint"""

    if response.status_code == 200:
        # Success
        return response.json()

    elif response.status_code == 401:
        # Trial token created - save and retry
        response_data = response.json()
        api_token = response_data["api_token"]
        credits = response_data["credits"]

        console.print(f"{emoji('party')} Trial account created!")
        console.print(f"   Credits: {credits}")

        # Save token
        save_api_token(api_token)

        # Retry scan with new token
        return retry_scan_with_token(api_url, openai_key, provider, data, api_token)

    elif response.status_code == 402:
        # Payment required
        handle_payment_required(response)
        return None

    elif response.status_code == 524:
        # Cloudflare timeout
        console.print("[yellow]Server Timeout (Error 524)[/yellow]")
        console.print("\nTry:")
        console.print("  1. Reduce files (use --ignore)")
        console.print("  2. Use --preset critical-only")
        sys.exit(1)

    elif response.status_code >= 500:
        # Server error
        console.print("[yellow]Server Error[/yellow]")
        console.print("Please try again in a few minutes.")
        sys.exit(1)

    else:
        # Other errors
        console.print(f"[red]HTTP Error {response.status_code}[/red]")
        sys.exit(1)
```

**3. Payment Required Handler (Lines 146-189)**

```python
def handle_payment_required(response: requests.Response):
    """Handle 402 Payment Required response"""

    payment_data = response.json()
    checkout_url = payment_data.get("checkout_url")

    console.print("\n" + "=" * 60)
    console.print(f"{emoji('credit_card')} PAYMENT REQUIRED")
    console.print("=" * 60)

    console.print(f"\n{emoji('info')} Opening payment page in your browser...")

    # Open browser
    try:
        webbrowser.open(checkout_url)
    except Exception as e:
        console.print(f"[red]Could not open browser: {e}[/red]")

    console.print(f"\n{emoji('clipboard')} PAYMENT INSTRUCTIONS:")
    console.print(f"   {emoji('credit_card')} Use test card: 4242 4242 4242 4242")
    console.print("   Any future date")
    console.print("   Any 3-digit CVC")
    console.print("\n   Complete payment in browser")
    console.print("   After payment, run scan command again")

    console.print(f"\n🔗 Payment URL:")
    console.print(f"   {checkout_url}")
    console.print("\n" + "=" * 60)

    sys.exit(0)  # Graceful exit
```

**4. Check Payment Required (Lines 19-67)**

```python
def check_payment_required(api_url: str, mode: str = "full") -> bool:
    """Check if payment required before scan"""

    try:
        response = requests.post(
            f"{api_url}/api/clausi/check-payment-required",
            headers={"Content-Type": "application/json"},
            json={"mode": mode},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            if data.get("payment_required"):
                checkout_url = data.get("checkout_url")

                # Open browser and show instructions
                webbrowser.open(checkout_url)
                console.print("Payment required - see browser")

                return False  # Payment required, don't proceed

        return True  # OK to proceed

    except Exception as e:
        console.print(f"Error checking payment: {e}")
        return True  # Proceed anyway
```

#### Payment Flow Diagram

```
User runs scan
    ↓
Check for saved token
    ↓
    ├─→ No token → Auto-start login flow
    │       ↓
    │   clausi login (OAuth)
    │       ↓
    │   Token saved → Continue
    │
    └─→ Token exists → Continue
            ↓
        make_async_scan_request()
            ↓
        POST /scan/async
            ↓
            ├─→ 200: Success → Return result
            ├─→ 401: Token expired → Prompt re-login → Exit
            ├─→ 402: Payment required → Open checkout → Exit
            ├─→ 524: Timeout → Show helpful message → Exit
            └─→ 5xx: Server error → Show error → Exit
```

---

### interactive.py - Interactive Mode

**File:** `clausi/tui/interactive.py`
**Lines:** ~300
**Library:** Questionary (arrow key navigation), tkinter (native file dialog)
**Purpose:** Beginner-friendly guided workflow

#### Key Features

1. **Native File Explorer** - Opens OS file picker (Windows/Mac/Linux)
2. **Terminal Directory Browser** - Arrow-key navigation through folders
3. **Path Autocomplete** - Type path with tab completion
4. **Graceful Fallbacks** - If native dialog fails, falls back to terminal

#### Path Selection Flow

```python
def select_path(self) -> str | None:
    """Let user choose how to specify the path to scan."""
    choices = [
        "1. Current directory (.)",
        "2. Open file explorer...",      # Native OS dialog (tkinter)
        "3. Browse in terminal...",       # Arrow-key directory browser
        "4. Type path manually"           # Text input with autocomplete
    ]
    # ...
```

#### Native File Dialog

```python
def open_native_file_dialog() -> str | None:
    """Open native OS file explorer dialog to select a folder."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()  # Hide the main window
    root.attributes('-topmost', True)  # Bring dialog to front

    folder_path = filedialog.askdirectory(
        title="Select Project Folder",
        initialdir=os.getcwd()
    )
    root.destroy()
    return folder_path if folder_path else None
```

#### Terminal Directory Browser

```python
def browse_directory(self, start_path: str = ".") -> str | None:
    """Interactive directory browser with arrow keys."""
    # Shows:
    # - .. (parent directory)
    # - [Select this folder: current_name]
    # - subdirectory1/
    # - subdirectory2/
    # Navigate with arrows, Enter to select
```

#### AI Provider Selection

```python
provider_choices = [
    "1. Clausi AI (no API key needed, pay per scan)",
    "2. Claude (bring your own Anthropic API key + $0.50 fee)",
    "3. OpenAI (bring your own OpenAI API key + $0.50 fee)"
]
provider_choice = questionary.select(
    "Select AI provider:",
    choices=provider_choices,
    qmark="",
    pointer="→"
).ask()

if provider_choice is None:
    return

# Strip number prefix and map to provider flag
provider_choice = provider_choice.split(". ", 1)[1]
provider_flags = {
    "Clausi AI (no API key needed, pay per scan)": "",
    "Claude (bring your own Anthropic API key + $0.50 fee)": "--claude",
    "OpenAI (bring your own OpenAI API key + $0.50 fee)": "--openai gpt-4o"
}
provider_flag = provider_flags[provider_choice]

# Step 3: Select regulations
reg_choice = questionary.select(
    "Select regulations:",
    choices=[
        "1. EU AI Act only",
        "2. EU AI Act + GDPR",
        "3. All regulations (EU-AIA, GDPR, ISO-42001, HIPAA, SOC2)",
        "4. Custom selection"
    ],
    qmark="",
    pointer="→"
).ask()

if reg_choice is None:
    return

# Strip prefix and map to -r flags
reg_choice = reg_choice.split(". ", 1)[1]
if reg_choice == "EU AI Act only":
    reg_flags = "-r EU-AIA"
elif reg_choice == "EU AI Act + GDPR":
    reg_flags = "-r EU-AIA -r GDPR"
elif "All regulations" in reg_choice:
    reg_flags = "-r EU-AIA -r GDPR -r ISO-42001 -r HIPAA -r SOC2"
# ... etc

# Step 4: Preset selection
preset_choice = questionary.select(
    "Additional options:",
    choices=[
        "1. Standard scan (all clauses)",
        "2. Critical-only preset (faster, cheaper)",
        "3. High-priority preset"
    ],
    qmark="",
    pointer="→"
).ask()

if preset_choice is None:
    return

# Strip prefix and map to --preset flag
preset_choice = preset_choice.split(". ", 1)[1]
if "Critical-only" in preset_choice:
    preset_flag = "--preset critical-only"
elif "High-priority" in preset_choice:
    preset_flag = "--preset high-priority"
else:
    preset_flag = ""

# Build command
cmd_parts = ["clausi", "scan"]

# Quote path if it contains spaces
if " " in path:
    cmd_parts.append(f'"{path}"')
else:
    cmd_parts.append(path)

cmd_parts.extend(reg_flags.split())
if provider_flag:
    cmd_parts.extend(provider_flag.split())
if preset_flag:
    cmd_parts.extend(preset_flag.split())
cmd_parts.append("--open-findings")

cmd = " ".join(cmd_parts)

# Show command and execute
console.print(f"\n[dim]Running: {cmd}[/dim]\n")
os.system(cmd)
```

#### Features

| Feature | Implementation |
|---------|----------------|
| Arrow key navigation | Questionary's `select()` |
| Number shortcuts | User can type 1-6 directly |
| Cancellation | Returns None, gracefully handled |
| Path with spaces | Quoted properly in command building |
| Equivalent command | Shown before execution |

---

### scanner.py - File Discovery

**File:** `clausi/core/scanner.py`
**Lines:** ~200
**Purpose:** Discover files, apply ignore patterns

#### Key Functions

```python
def scan_directory(path: str, extensions: List[str] = None) -> List[str]:
    """
    Recursively scan directory for files.

    Returns:
        List of relative file paths
    """
    files = []
    path = Path(path)

    for file_path in path.rglob("*"):
        if file_path.is_file():
            if extensions:
                if file_path.suffix in extensions:
                    files.append(str(file_path.relative_to(path)))
            else:
                files.append(str(file_path.relative_to(path)))

    return files


def filter_ignored_files(files: List[str], project_path: str,
                        ignore_patterns: List[str] = None) -> List[str]:
    """
    Apply .clausiignore and --ignore patterns.

    Uses pathspec library (gitignore-style matching).
    """
    # Load .clausiignore if exists
    clausiignore_patterns = load_ignore_patterns(project_path)

    # Combine with CLI --ignore patterns
    all_patterns = clausiignore_patterns + (ignore_patterns or [])

    if not all_patterns:
        return files

    # Create pathspec matcher
    spec = pathspec.PathSpec.from_lines('gitwildmatch', all_patterns)

    # Filter files
    filtered = []
    for file in files:
        if not spec.match_file(file):
            filtered.append(file)

    return filtered


def load_ignore_patterns(path: str) -> List[str]:
    """
    Load .clausiignore from path or parent directories.

    Searches upward like .gitignore.
    """
    path = Path(path)

    # Search upward for .clausiignore
    current = path
    while current != current.parent:
        clausiignore = current / ".clausiignore"
        if clausiignore.exists():
            return clausiignore.read_text().splitlines()
        current = current.parent

    return []
```

---

### config.py - Configuration Management

**File:** `clausi/utils/config.py`
**Lines:** ~182
**Purpose:** Read/write config file at `~/.clausi/config.yml`

#### Key Functions

```python
def get_config_path() -> Path:
    """Returns Path to ~/.clausi/config.yml"""
    config_dir = Path.home() / ".clausi"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "config.yml"


def load_config() -> Optional[Dict[str, Any]]:
    """Load YAML config file"""
    config_path = get_config_path()
    if not config_path.exists():
        return None

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def save_config(config: Dict[str, Any]) -> bool:
    """Save config to YAML file"""
    config_path = get_config_path()
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    return True


def get_anthropic_key() -> Optional[str]:
    """Get Anthropic API key from environment or config"""
    # Environment variable takes precedence
    key = os.getenv('ANTHROPIC_API_KEY')
    if key:
        return key

    # Check config file
    config = load_config()
    if config:
        return config.get("api_keys", {}).get("anthropic")

    return None


def get_openai_key() -> Optional[str]:
    """Get OpenAI API key from environment or config"""
    # Environment variable takes precedence
    key = os.getenv('OPENAI_API_KEY')
    if key:
        return key

    # Check config file
    config = load_config()
    if config:
        # Check new structure
        if config.get("api_keys", {}).get("openai"):
            return config["api_keys"]["openai"]

        # Legacy location
        if config.get("openai_key"):
            return config["openai_key"]

    return None


def get_api_token() -> Optional[str]:
    """Get API token (for trial/credits)"""
    config = load_config()
    if config:
        return config.get('api_token')
    return None


def save_api_token(token: str) -> bool:
    """Save API token to config"""
    config = load_config() or {}
    config['api_token'] = token
    return save_config(config)
```

#### Configuration Precedence

```
CLI Flag
   ↓ (if not provided)
Environment Variable
   ↓ (if not set)
Config File
   ↓ (if not exists)
Default Value
```

---

### regulations.py - Custom Regulations

**File:** `clausi/utils/regulations.py`
**Lines:** ~280
**Purpose:** Discover and load custom regulation YAML files

#### Key Functions

```python
def discover_custom_regulations(project_path: Optional[Path] = None) -> Dict[str, Path]:
    """
    Discover custom regulation YAML files.

    Searches:
    1. Global: ~/.clausi/custom_regulations/
    2. Project: {project}/.clausi/regulations/

    Returns:
        Dict mapping regulation code to YAML file path
        Example: {"COMPANY-SECURITY": Path("~/.clausi/custom_regulations/company-security.yml")}
    """
    regulations = {}

    # Global regulations
    global_dir = Path.home() / ".clausi" / "custom_regulations"
    if global_dir.exists():
        for yaml_file in global_dir.glob("*.yml"):
            code = yaml_file.stem.upper().replace("-", "_")
            regulations[code] = yaml_file

    # Project-specific regulations (override global)
    if project_path:
        project_dir = Path(project_path) / ".clausi" / "regulations"
        if project_dir.exists():
            for yaml_file in project_dir.glob("*.yml"):
                code = yaml_file.stem.upper().replace("-", "_")
                regulations[code] = yaml_file

    return regulations


def load_custom_regulation(yaml_path: Path) -> Optional[Dict[str, Any]]:
    """Load a custom regulation YAML file"""
    try:
        with open(yaml_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Error loading {yaml_path}: {e}[/red]")
        return None


def get_custom_regulations_for_scan(
    selected_regulations: List[str],
    project_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Prepare custom regulations to send to backend.

    Returns:
        List of dicts with code and content for each custom regulation
    """
    custom_regs = []
    discovered = discover_custom_regulations(project_path)

    for reg_code in selected_regulations:
        if reg_code in discovered:
            content = load_custom_regulation(discovered[reg_code])
            if content:
                custom_regs.append({
                    "code": reg_code,
                    "content": content
                })

    return custom_regs
```

---

## PART 3: DEVELOPMENT GUIDE

### Common Development Tasks

#### Task 1: Add a New AI Provider

**Example: Adding Google Gemini support**

**Step 1: Add CLI flag** (`cli.py`)

```python
# Around line 548
@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--claude", "claude_model", default=None)
@click.option("--openai", "openai_model", default=None)
@click.option("--gemini", "gemini_model", default=None)  # NEW
def scan(...):
```

**Step 2: Add provider detection** (`cli.py`)

```python
# Around line 580
if claude_model is not None:
    provider = "claude"
    model = claude_model if claude_model != "" else "claude-3-5-sonnet-20241022"
elif openai_model is not None:
    provider = "openai"
    model = openai_model if openai_model != "" else "gpt-4o"
elif gemini_model is not None:  # NEW
    provider = "gemini"
    model = gemini_model if gemini_model != "" else "gemini-pro"
else:
    provider = "clausi"
    model = None
```

**Step 3: Add API key validation** (`cli.py`)

```python
# In _validate_and_get_api_key() around line 220
elif provider == "gemini":
    api_key = config_module.get_gemini_key()
    if not api_key:
        console.print(f"{emoji('crossmark')} [bold red]Gemini API Key Required[/bold red]")
        console.print("\nOptions:")
        console.print("  1. Set environment: export GEMINI_API_KEY=...")
        console.print("  2. Add to config: clausi config set --gemini-key ...")
        sys.exit(1)
    return api_key
```

**Step 4: Add config function** (`utils/config.py`)

```python
def get_gemini_key() -> Optional[str]:
    """Get Gemini API key from environment or config"""
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key

    config = load_config()
    if config:
        return config.get("api_keys", {}).get("gemini")

    return None
```

**Step 5: Add header logic** (`core/payment.py`)

```python
# Around line 238
if api_key:
    if provider == "claude":
        headers["X-Anthropic-Key"] = api_key
    elif provider == "openai":
        headers["X-OpenAI-Key"] = api_key
    elif provider == "gemini":  # NEW
        headers["X-Gemini-Key"] = api_key
```

**Step 6: Update interactive mode** (`tui/interactive.py`)

```python
# In scan_wizard()
provider_choices = [
    "1. Clausi AI (no API key needed, pay per scan)",
    "2. Claude (bring your own Anthropic API key + $0.50 fee)",
    "3. OpenAI (bring your own OpenAI API key + $0.50 fee)",
    "4. Gemini (bring your own Google API key + $0.50 fee)"  # NEW
]
provider_choice = questionary.select(
    "Select AI provider:",
    choices=provider_choices,
    qmark="",
    pointer="→"
).ask()

# Add mapping in provider_flags dict
provider_flags = {
    # ... existing mappings ...
    "Gemini (bring your own Google API key + $0.50 fee)": "--gemini"  # NEW
}
```

**Step 7: Test**

```bash
# Build and install
python -m build
pip install dist/clausi-*.whl --force-reinstall

# Test command
clausi scan . --gemini gemini-pro

# Test interactive mode
clausi
# Select option 4 (Gemini)
```

---

#### Task 2: Add a New CLI Command

**Example: Adding a `validate` command to check custom regulations**

```python
# In cli.py

@cli.command()
@click.argument("regulation_file", type=click.Path(exists=True))
def validate(regulation_file):
    """Validate a custom regulation YAML file"""

    console.print(f"Validating {regulation_file}...")

    # Load YAML
    try:
        with open(regulation_file, 'r') as f:
            content = yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Invalid YAML: {e}[/red]")
        sys.exit(1)

    # Check required fields
    required = ["name", "description", "version", "clauses"]
    missing = [f for f in required if f not in content]

    if missing:
        console.print(f"[red]Missing required fields: {', '.join(missing)}[/red]")
        sys.exit(1)

    # Validate clauses
    for clause in content.get("clauses", []):
        if "id" not in clause:
            console.print(f"[red]Clause missing 'id' field[/red]")
            sys.exit(1)
        if "severity" not in clause:
            console.print(f"[yellow]Warning: Clause {clause['id']} missing 'severity'[/yellow]")

    console.print(f"[green]{emoji('checkmark')} Valid regulation file![/green]")
    console.print(f"\nRegulation: {content['name']}")
    console.print(f"Version: {content['version']}")
    console.print(f"Clauses: {len(content.get('clauses', []))}")
```

**Usage:**
```bash
clausi validate ~/.clausi/custom_regulations/my-reg.yml
```

---

#### Task 3: Modify Interactive Mode Menu

**Example: Add a "Check Status" option**

```python
# In tui/interactive.py

def show_main_menu(self):
    return questionary.select(
        "What would you like to do?",
        choices=[
            "1. Scan a project for compliance",
            "2. View configuration",
            "3. List available AI models",
            "4. Run setup wizard",
            "5. Check account status",  # NEW
            "6. Show help",
            "7. Exit Clausi"  # Updated number
        ],
        qmark="",
        pointer="→"
    ).ask()

def run(self):
    while True:
        choice = self.show_main_menu()

        # ... existing handlers ...

        elif "Check account status" in choice:  # NEW
            self.check_status()

def check_status(self):
    """Check API token status and remaining credits"""
    from clausi.utils.config import get_api_token

    token = get_api_token()

    if token:
        self.console.print(f"[green]API Token: {token[:8]}...[/green]")
        # TODO: Call backend to get actual credits
        self.console.print("[yellow]Credit check not yet implemented[/yellow]")
    else:
        self.console.print("[yellow]No API token found[/yellow]")
        self.console.print("Run a scan to create a trial account.")

    input("\nPress Enter to continue...")
```

---

#### Task 4: Add a New Built-in Regulation

**Step 1: Add to REGULATIONS dict** (`cli.py` around line 51)

```python
REGULATIONS = {
    "EU-AIA": {
        "name": "EU AI Act",
        "description": "European Union Artificial Intelligence Act",
    },
    "GDPR": {
        "name": "GDPR",
        "description": "General Data Protection Regulation",
    },
    # ... existing regulations ...
    "PCI-DSS": {  # NEW
        "name": "PCI DSS",
        "description": "Payment Card Industry Data Security Standard",
    }
}
```

**Step 2: Update default config** (`setup.py` around line 82)

```python
"regulations": {
    "selected": ["EU-AIA", "GDPR", "PCI-DSS"]  # Add to defaults
}
```

**Step 3: Update interactive mode** (`tui/interactive.py`)

```python
reg_choice = questionary.select(
    "Select regulations:",
    choices=[
        "1. EU AI Act only",
        "2. EU AI Act + GDPR",
        "3. All regulations",  # Will include PCI-DSS automatically
        "4. PCI DSS only",  # NEW option
        "5. Custom selection"
    ]
).ask()

# Add mapping
elif "PCI DSS only" in reg_choice:
    reg_flags = "-r PCI-DSS"
```

**Step 4: Backend must support the new regulation**

---

### Code Patterns to Follow

#### Pattern 1: Always Use emoji() Helper

```python
# ✅ GOOD
from clausi.utils.emoji import get as emoji
console.print(f"{emoji('checkmark')} Success")

# ❌ BAD - Will crash on Windows
console.print("✓ Success")
```

#### Pattern 2: Always Check Provider Before Setting Headers

```python
# ✅ GOOD
if api_key:
    if provider == "claude":
        headers["X-Anthropic-Key"] = api_key
    elif provider == "openai":
        headers["X-OpenAI-Key"] = api_key

# ❌ BAD - Hardcoded, won't work for all providers
headers["X-OpenAI-Key"] = api_key
```

#### Pattern 3: Graceful Cancellation in Interactive Mode

```python
# ✅ GOOD
choice = questionary.select(...).ask()
if choice is None:  # User pressed ESC
    console.print("\n[yellow]Cancelled[/yellow]")
    return

# ❌ BAD - Will crash on ESC
choice = questionary.select(...).ask()
# Assume choice is always a string
```

#### Pattern 4: Use Path Objects for File Operations

```python
# ✅ GOOD
from pathlib import Path
config_path = Path.home() / ".clausi" / "config.yml"
config_path.parent.mkdir(exist_ok=True)

# ❌ BAD - String manipulation, not cross-platform
import os
config_path = os.path.join(os.path.expanduser("~"), ".clausi", "config.yml")
```

#### Pattern 5: Provide Actionable Error Messages

```python
# ✅ GOOD
console.print(f"{emoji('crossmark')} [red]File not found: {path}[/red]")
console.print("\nPlease check:")
console.print("  1. The file path is correct")
console.print("  2. You have read permissions")
console.print(f"\nCurrent directory: {os.getcwd()}")

# ❌ BAD - Unhelpful
console.print("Error: File not found")
```

#### Pattern 6: Configuration Precedence

```python
# ✅ GOOD - Check in order: CLI → Env → Config → Default
def get_api_url():
    # CLI flag would be checked by Click before this
    # Check environment
    url = os.getenv('CLAUSI_TUNNEL_BASE')
    if url:
        return url
    # Check config
    config = load_config()
    if config and config.get('api', {}).get('url'):
        return config['api']['url']
    # Default
    return "https://api.clausi.ai"

# ❌ BAD - Ignores environment variable
def get_api_url():
    config = load_config()
    return config.get('api', {}).get('url', 'https://api.clausi.ai')
```

---

### Testing Guide

#### Test Structure

```
tests/
├── fixtures/              # Test data
│   └── sample_project/
├── test_cli.py           # CLI command tests
└── test_v1_features.py   # Feature integration tests
```

#### Running Tests

```bash
# Install dev dependencies
pip install -e .[dev]

# Run all tests
pytest tests/

# Run specific test
pytest tests/test_cli.py::test_scan_command

# Run with coverage
pytest --cov=clausi tests/

# Run in verbose mode
pytest -v tests/
```

#### Manual Testing Checklist

**After making changes:**

1. **Build package**
   ```bash
   rm -rf dist/ build/ *.egg-info/
   python -m build
   ```

2. **Check package contents**
   ```bash
   tar -tzf dist/clausi-*.tar.gz | grep -E "(interactive|payment|cli)"
   ```

3. **Install locally**
   ```bash
   pip install dist/clausi-*.whl --force-reinstall
   ```

4. **Test commands**
   ```bash
   clausi --version
   clausi --help
   clausi scan --help
   ```

5. **Test interactive mode**
   ```bash
   clausi
   # Navigate with arrows
   # Test cancellation (ESC)
   # Test number shortcuts (1-6)
   ```

6. **Test actual scan**
   ```bash
   # Create test project
   mkdir test_project
   echo "print('hello')" > test_project/main.py

   # Run scan
   clausi scan test_project -r EU-AIA
   ```

7. **Test with local backend**
   ```bash
   export CLAUSI_TUNNEL_BASE=http://localhost:10000
   clausi scan test_project -r EU-AIA
   ```

---

### Packaging & Distribution

#### Build System

- **Build tool:** `setuptools` + `build`
- **Config files:** `pyproject.toml`, `setup.py`, `MANIFEST.in`

#### Version Management

**Single source of truth:** `clausi/__init__.py`

```python
__version__ = "1.0.0"
```

All other files read from this via `pyproject.toml`:

```toml
[tool.setuptools.dynamic]
version = {attr = "clausi.__version__"}
```

#### Package Inclusion Rules

**MANIFEST.in** controls what's included:

```
# Include
include README.md LICENSE pyproject.toml .clausiignore
recursive-include clausi *.py *.yml *.yaml *.css *.md

# Exclude
recursive-exclude CLAUDE *
recursive-exclude tests *
global-exclude *.pyc __pycache__
```

#### Building for PyPI

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build distributions (.tar.gz and .whl)
python -m build

# Check package
twine check dist/*

# Upload to Test PyPI (recommended first)
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

#### Pre-Upload Checklist

1. ✅ Version bumped in `clausi/__init__.py`
2. ✅ CHANGELOG updated
3. ✅ README.md reflects latest features
4. ✅ All tests pass: `pytest tests/`
5. ✅ Package builds: `python -m build`
6. ✅ Twine check passes: `twine check dist/*`
7. ✅ Local install works: `pip install dist/*.whl --force-reinstall`
8. ✅ Manual smoke test: `clausi --help`, `clausi scan test_project`

---

## PART 4: REFERENCE

### Quick Function Reference

| What | File | Lines | Function |
|------|------|-------|----------|
| **CLI Entry Point** |
| Main CLI group | cli.py | 536-550 | `cli()` |
| Scan command | cli.py | 548-900 | `scan()` |
| Interactive launcher | cli.py | 243-271 | `launch_interactive_mode()` |
| **Provider & API Keys** |
| Provider detection | cli.py | 578-596 | Inside `scan()` |
| API key validation | cli.py | 184-241 | `_validate_and_get_api_key()` |
| Get Anthropic key | config.py | 131-145 | `get_anthropic_key()` |
| Get OpenAI key | config.py | 106-129 | `get_openai_key()` |
| **Payment & Scanning** |
| Async scan request | payment.py | 216-336 | `make_async_scan_request()` |
| Sync scan request | payment.py | 339-403 | `make_scan_request()` |
| Response handler | payment.py | 69-144 | `handle_scan_response()` |
| Payment required | payment.py | 146-189 | `handle_payment_required()` |
| Check payment | payment.py | 19-67 | `check_payment_required()` |
| **Interactive Mode** |
| Main TUI class | interactive.py | 15-250 | `ClausInteractiveTUI` |
| Main menu | interactive.py | 40-55 | `show_main_menu()` |
| Scan wizard | interactive.py | 85-180 | `scan_wizard()` |
| **File Discovery** |
| Scan directory | scanner.py | 15-35 | `scan_directory()` |
| Filter ignored | scanner.py | 38-65 | `filter_ignored_files()` |
| Load .clausiignore | scanner.py | 68-85 | `load_ignore_patterns()` |
| **Configuration** |
| Load config | config.py | 29-40 | `load_config()` |
| Save config | config.py | 42-51 | `save_config()` |
| Get API token | config.py | 93-98 | `get_api_token()` |
| Save API token | config.py | 100-104 | `save_api_token()` |
| **Custom Regulations** |
| Discover regulations | regulations.py | 128-157 | `discover_custom_regulations()` |
| Load regulation YAML | regulations.py | 160-170 | `load_custom_regulation()` |
| Get for scan | regulations.py | 225-254 | `get_custom_regulations_for_scan()` |

---

### Important Patterns

#### Error Handling

**Network Errors:**
```python
try:
    response = requests.post(...)
except requests.exceptions.Timeout:
    console.print(f"{emoji('crossmark')} Request timed out")
    console.print("\nTry:")
    console.print("  1. Reduce files with --ignore")
    console.print("  2. Use --preset critical-only")
    sys.exit(1)
except requests.exceptions.ConnectionError:
    console.print(f"{emoji('crossmark')} Connection error")
    console.print("\nCheck your internet connection")
    sys.exit(1)
```

**HTML vs JSON Response Detection:**
```python
content_type = response.headers.get('Content-Type', '')
is_html = 'text/html' in content_type or response.text.startswith('<!DOCTYPE')

if is_html:
    console.print("Received HTML error page (likely Cloudflare)")
else:
    error_data = response.json()
    console.print(error_data.get('detail', 'Unknown error'))
```

#### Cross-Platform Compatibility

**Emoji:**
```python
from clausi.utils.emoji import get as emoji
# Automatically uses ASCII on Windows, emoji elsewhere
console.print(f"{emoji('checkmark')} Done")
```

**Paths:**
```python
from pathlib import Path
# Works on Windows, Mac, Linux
config_path = Path.home() / ".clausi" / "config.yml"
```

**Commands:**
```python
# Quote paths with spaces
if " " in path:
    cmd_parts.append(f'"{path}"')
else:
    cmd_parts.append(path)
```

---

### Gotchas & Pitfalls

#### Gotcha 1: Provider String Must Match Header Logic

**Problem:**
```python
# In cli.py, you set provider="anthropic"
provider = "anthropic"

# But in payment.py, you check for "claude"
if provider == "claude":
    headers["X-Anthropic-Key"] = api_key
# MISMATCH! Header won't be set
```

**Solution:** Use consistent provider strings: `"clausi"`, `"claude"`, `"openai"`

---

#### Gotcha 2: Interactive Mode Cancellation

**Problem:**
```python
choice = questionary.select(...).ask()
# Assume choice is always a string
option = choice.split(". ")[1]  # CRASH if choice is None
```

**Solution:** Always check for None
```python
choice = questionary.select(...).ask()
if choice is None:  # User pressed ESC
    return
option = choice.split(". ")[1]  # Safe now
```

---

#### Gotcha 3: Environment Variables Not Checked

**Problem:**
```python
def get_api_key():
    config = load_config()
    return config.get("api_key")  # Misses OPENAI_API_KEY env var
```

**Solution:** Check environment first
```python
def get_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    config = load_config()
    return config.get("api_key")
```

---

#### Gotcha 4: Hardcoded API URL

**Problem:**
```python
response = requests.post("https://api.clausi.ai/api/clausi/scan", ...)
# Won't work with CLAUSI_TUNNEL_BASE for local testing
```

**Solution:** Always use get_api_url()
```python
from clausi.cli import get_api_url
api_url = get_api_url()  # Checks CLAUSI_TUNNEL_BASE
response = requests.post(f"{api_url}/api/clausi/scan", ...)
```

---

#### Gotcha 5: Emoji on Windows

**Problem:**
```python
console.print("✓ Success")  # Displays � on Windows
```

**Solution:** Use emoji helper
```python
from clausi.utils.emoji import get as emoji
console.print(f"{emoji('checkmark')} Success")  # Shows [OK] on Windows
```

---

#### Gotcha 6: Package Not Including New Files

**Problem:** Added new file `clausi/utils/new_feature.py` but it's not in package

**Solution:** Check MANIFEST.in
```
recursive-include clausi *.py  # Should include all .py files
```

Then rebuild:
```bash
rm -rf dist/ build/ *.egg-info/
python -m build
tar -tzf dist/clausi-*.tar.gz | grep new_feature  # Verify it's there
```

---

### Recent Changes

#### 2025-12-24 - Production Ready Release

**Interactive Mode Enhancements:**
- Added native file explorer dialog (tkinter) for folder selection
- Added terminal-based directory browser as fallback
- Path selection now offers 4 options:
  1. Current directory (.)
  2. Open file explorer...
  3. Browse in terminal...
  4. Type path manually

**Payment Flow Updates:**
- Added auto-login flow when no token found
- Removed test card display (was showing Stripe test card 4242...)
- Improved session expiry handling with clear re-login prompts

**Pricing Messaging (Hybrid Approach):**
- CLI now shows $ amounts only (no tokens/credits visible to users)
- Updated provider labels: "Clausi AI (no API key needed, pay per scan)"
- BYOK options show platform fee: "+ $0.50 fee"
- Renamed `clausi tokens` command to `clausi balance`

**Code Cleanup:**
- Removed duplicate `get_openai_key()` wrapper from cli.py
- Removed unused `rprint` import
- Removed deprecated `show_token_status()` function
- Fixed hardcoded emoji to use `emoji()` function

**New Files:**
- `CLAUDE/REFACTORING_PLAN.md` - Production refactoring roadmap
- `CLAUDE/REFACTORING_PROGRESS.md` - Progress tracker

---

#### 2025-12-08 - Documentation Consolidation

**Changes:**
- Consolidated all AI developer docs into this file
- Created separate PRICING_STRATEGY.md for business pricing
- Cleaned up redundant markdown files

#### 2025-12-07 - Interactive Mode & CLI Simplification

**Interactive Mode:**
- Added `clausi/tui/interactive.py` with questionary
- Arrow key navigation like Claude Code planning mode
- Numbered menu (1-6) with direct shortcuts
- Step-by-step scan wizard
- Graceful cancellation (ESC/Ctrl+C)

**CLI Flag Simplification:**
- ❌ Removed `--use-claude-code`, `--ai-provider`, `--ai-model`
- ✅ Added `--claude [MODEL]` and `--openai [MODEL]`
- ✅ Default is now "clausi" provider (no API key needed)

**Custom Regulations:**
- Verified feature is fully implemented
- Added documentation to README
- Included `custom_regulations_README.md` in package

**Package Updates:**
- Fixed license format in `pyproject.toml`
- Fixed package discovery for all subpackages
- Added `questionary>=2.0.0` dependency

#### 2025-10-18 - v1.0.0 Release

**Major Features:**
1. Multi-model support (Claude, OpenAI)
2. Clause scoping (presets, include/exclude)
3. Markdown-first output (findings.md auto-open)
4. Cache statistics display
5. Enhanced progress bars

---

## For AI Assistants

**When working on this codebase:**

1. **Read before editing** - Always read files before modifying
2. **Test changes** - Build, install, and manually test after modifications
3. **Update docs** - Update this file for significant architectural changes
4. **Follow patterns** - See [Code Patterns to Follow](#code-patterns-to-follow)
5. **Check compatibility** - Test on Windows/Mac/Linux if possible
6. **Verify packaging** - Ensure new files are included in package

**Critical files (modify with caution):**
- `clausi/cli.py` - Main orchestration, affects all users
- `clausi/core/payment.py` - Payment flow, API communication
- `clausi/tui/interactive.py` - Interactive mode
- `pyproject.toml` - Build configuration
- `setup.py` - Package setup

**Safe files (low risk):**
- `clausi/utils/output.py` - Output formatting
- `clausi/utils/emoji.py` - Emoji mappings
- `clausi/templates/` - Report templates
- Tests and documentation

**Tool preferences:**
- Use Read/Edit/Write for files (not Bash cat/sed/echo)
- Use Grep for code search (not bash grep)
- Use Glob for file patterns (not bash find)
- Use TodoWrite for task tracking
- Use AskUserQuestion for clarification

---

## Contact & Resources

- **Repository:** https://github.com/clausi/clausi-cli
- **Documentation:** https://docs.clausi.ai
- **Backend API:** https://api.clausi.ai
- **PyPI Package:** https://pypi.org/project/clausi/

---

**Last Updated:** 2025-12-24
**Maintainer:** Clausi Development Team
**CLI Version:** 1.0.0
