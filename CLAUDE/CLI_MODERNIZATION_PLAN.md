# Clausi CLI Modernization Plan

**Created:** 2025-10-18
**Last Updated:** 2025-10-18
**Goal:** Transform CLI into enterprise-grade developer tool
**Timeline:** 12 weeks (aligned with backend development)
**Version:** 0.3.0 → **1.0.0** ✅ RELEASED

---

## 🎉 **Status Update - Phase 1 COMPLETE**

**✅ COMPLETED (Released as v1.0.0):**
- ✅ Task 1.1: Multi-Model Support (Claude + OpenAI)
- ✅ Task 1.2: Clause Scoping with Presets
- ✅ Task 1.3: Markdown-First Output
- ✅ Task 1.4: Enhanced Progress & Cache Stats
- ✅ Package reorganization to industry standards
- ✅ Backend integration documentation

**📋 IN PROGRESS:**
- Task 1.5: Git Integration - Basic (pending)

**🔜 UPCOMING:**
- Phase 2: Auto-Fix Experience (Weeks 5-8)
- Phase 3: Developer Tools (Weeks 9-12)

**📚 Documentation:**
- See `CHANGELOG_v1.0.0.md` for release notes
- See `BACKEND_INTEGRATION_GUIDE.md` for backend integration

---

## **Executive Summary**

This plan modernizes the Clausi CLI to support the new backend features while dramatically improving developer experience. The focus is on **markdown-first workflows**, **git integration**, **auto-fix capabilities**, and **real-time feedback**.

### **Key Improvements:**

| Feature | Before (v0.3.0) | After (v1.0.0) |
|---------|-----------------|----------------|
| **AI Model** | GPT-4 only | Claude (default) + GPT-4 |
| **Scan Speed** | 15 min full scan | 2 sec (cached), 30 sec (incremental) |
| **Output** | PDF only | Markdown + PDF + HTML + JSON |
| **Cost** | $5.00 per scan | $0.50 per scan (90% savings) |
| **Fixes** | Manual | Auto-generated with review |
| **Git Integration** | None | Native (pre-commit, watch, compare) |
| **Progress** | Silent wait | Real-time with cache stats |
| **Workflow** | CLI → Report | CLI → findings.md → Git → Auto-fix |

---

## **Table of Contents**

1. [Phase 1: Foundation (Weeks 1-4)](#phase-1-foundation-weeks-1-4)
2. [Phase 2: Auto-Fix Experience (Weeks 5-8)](#phase-2-auto-fix-experience-weeks-5-8)
3. [Phase 3: Developer Tools (Weeks 9-12)](#phase-3-developer-tools-weeks-9-12)
4. [API Contract with Backend](#api-contract-with-backend)
5. [File Structure & Configuration](#file-structure--configuration)
6. [User Experience Flows](#user-experience-flows)
7. [Testing Strategy](#testing-strategy)
8. [Migration Guide](#migration-guide)

---

## **Phase 1: Foundation (Weeks 1-4)**

**Goal:** Support new backend features (Claude, caching, markdown, clause scoping)

### **Task 1.1: Multi-Model Support**

#### **What to Build:**

Add support for Claude (default) and OpenAI with user override.

#### **Configuration Changes:**

```yaml
# ~/.clausi/config.yml

# NEW: AI Provider settings
ai:
  provider: claude  # claude or openai
  model: claude-3-5-sonnet-20241022
  fallback_provider: openai
  fallback_model: gpt-4

# NEW: API Keys
api_keys:
  anthropic: ${ANTHROPIC_API_KEY}  # From environment
  openai: ${OPENAI_API_KEY}
```

#### **CLI Usage:**

```bash
# Use default (Claude)
clausi scan .

# Override to use OpenAI
clausi scan . --ai-provider openai

# Override model
clausi scan . --ai-model claude-3-opus-20240229

# Show available models
clausi models list
```

#### **Implementation:**

**File:** `clausi_cli/cli.py`

```python
# Add to scan command
@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--ai-provider',
              type=click.Choice(['claude', 'openai']),
              default=None,
              help='AI provider to use (default: from config)')
@click.option('--ai-model',
              type=str,
              default=None,
              help='Specific AI model to use')
def scan(path, ai_provider, ai_model, **kwargs):
    """Scan project for compliance issues."""

    # Get provider from config or flag
    provider = ai_provider or get_config_value('ai.provider', 'claude')
    model = ai_model or get_config_value('ai.model', 'claude-3-5-sonnet-20241022')

    # Get appropriate API key
    if provider == 'claude':
        api_key = os.getenv('ANTHROPIC_API_KEY') or get_config_value('api_keys.anthropic')
        if not api_key:
            console.print("[red]Error: ANTHROPIC_API_KEY not found[/red]")
            console.print("Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
            sys.exit(1)
    else:
        api_key = get_openai_key()

    # Pass to backend in scan request
    scan_data = {
        "path": path,
        "regulations": regulations,
        "mode": mode,
        "ai_provider": provider,  # NEW
        "ai_model": model,        # NEW
        "metadata": {
            ...
        }
    }

    console.print(f"[cyan]Using AI: {provider} ({model})[/cyan]")

    # Make scan request...
```

#### **New Command: Models**

```python
@cli.group()
def models():
    """Manage AI models."""
    pass

@models.command('list')
def list_models():
    """List available AI models."""
    from rich.table import Table

    table = Table(title="Available AI Models")
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Context", style="yellow")
    table.add_column("Cost/1M", style="magenta")
    table.add_column("Speed", style="blue")

    table.add_row("Claude", "claude-3-5-sonnet-20241022", "200k", "$3/$15", "⚡⚡⚡")
    table.add_row("Claude", "claude-3-opus-20240229", "200k", "$15/$75", "⚡⚡")
    table.add_row("OpenAI", "gpt-4", "128k", "$30/$60", "⚡⚡")
    table.add_row("OpenAI", "gpt-4-turbo", "128k", "$10/$30", "⚡⚡⚡")

    console.print(table)
    console.print("\n[cyan]💡 Tip: Claude 3.5 Sonnet is recommended (faster, cheaper, better)[/cyan]")
```

---

### **Task 1.2: Clause Scoping**

#### **What to Build:**

Let users select specific clauses to scan (saves time and money).

#### **CLI Usage:**

```bash
# Interactive clause selection
clausi scan . --select-clauses

# Specify clauses directly
clausi scan . --include EUAIA-3.1 --include EUAIA-7.2

# Exclude specific clauses
clausi scan . --exclude EUAIA-2.1 --exclude GDPR-5.1

# Scan only high-priority clauses (predefined)
clausi scan . --preset critical-only
```

#### **Implementation:**

**Interactive Selection:**

```python
# File: clausi_cli/clause_selector.py

from rich.prompt import Prompt, Confirm
from rich.table import Table

def select_clauses_interactive(regulation: str) -> tuple:
    """Interactive clause selection."""

    # Load available clauses for regulation
    clauses = load_regulation_clauses(regulation)

    console.print(f"\n[cyan]Select clauses to scan for {regulation}[/cyan]")
    console.print("Press Enter to select all, or choose specific clauses:\n")

    # Display clauses table
    table = Table()
    table.add_column("#", style="cyan")
    table.add_column("Clause ID", style="green")
    table.add_column("Title", style="yellow")
    table.add_column("Priority", style="magenta")

    for i, clause in enumerate(clauses, 1):
        priority = clause.get('priority', 'medium')
        table.add_row(
            str(i),
            clause['id'],
            clause['title'][:50],
            priority.upper()
        )

    console.print(table)

    # Get user selection
    selection = Prompt.ask(
        "\n[cyan]Enter clause numbers (comma-separated) or 'all'[/cyan]",
        default="all"
    )

    if selection.lower() == 'all':
        return None, None  # Scan all clauses

    # Parse selection
    selected_indices = [int(x.strip()) - 1 for x in selection.split(',')]
    selected_clauses = [clauses[i]['id'] for i in selected_indices]

    console.print(f"\n[green]✓ Selected {len(selected_clauses)} clauses[/green]")
    return selected_clauses, None

# Add to scan command
@cli.command()
@click.option('--select-clauses', is_flag=True, help='Interactively select clauses')
@click.option('--include', multiple=True, help='Include specific clauses')
@click.option('--exclude', multiple=True, help='Exclude specific clauses')
@click.option('--preset', type=click.Choice(['critical-only', 'high-priority']),
              help='Use predefined clause preset')
def scan(path, select_clauses, include, exclude, preset, **kwargs):
    """Scan with clause selection."""

    clauses_include = None
    clauses_exclude = None

    if select_clauses:
        clauses_include, clauses_exclude = select_clauses_interactive(regulation)
    elif include:
        clauses_include = list(include)
    elif exclude:
        clauses_exclude = list(exclude)
    elif preset:
        clauses_include = get_preset_clauses(regulation, preset)

    # Add to scan request
    scan_data = {
        ...
        "clauses_include": clauses_include,  # NEW
        "clauses_exclude": clauses_exclude,  # NEW
    }
```

**Presets:**

```python
# File: clausi_cli/presets.py

CLAUSE_PRESETS = {
    "EU-AIA": {
        "critical-only": ["EUAIA-3.1", "EUAIA-5.2", "EUAIA-7.2", "EUAIA-9.1"],
        "high-priority": ["EUAIA-3.1", "EUAIA-5.2", "EUAIA-7.2", "EUAIA-9.1",
                         "EUAIA-10.2", "EUAIA-12.1"]
    },
    "GDPR": {
        "critical-only": ["GDPR-5.1", "GDPR-32.1", "GDPR-33.1"],
        "high-priority": ["GDPR-5.1", "GDPR-6.1", "GDPR-25.1", "GDPR-32.1"]
    }
}
```

---

### **Task 1.3: Markdown-First Output**

#### **What to Build:**

Generate markdown files by default, auto-open findings.md in editor.

#### **Output Structure:**

```
compliance-reports/
└── project_EUAIA_20251018_143022/
    ├── findings.md              # ← Main file (auto-opens)
    ├── compliance_report.md     # Executive summary
    ├── traceability_matrix.md   # Clause coverage matrix
    ├── report.pdf              # Traditional report
    ├── report.html             # Web report
    └── audit_meta.json         # Machine-readable metadata
```

#### **Implementation:**

```python
# File: clausi_cli/scan.py

def handle_scan_results(result, output_path):
    """Handle scan results with markdown-first approach."""

    run_folder = result.get("run_folder")
    markdown_files = result.get("markdown_files", {})

    # Download all reports
    for report in result.get("generated_reports", []):
        download_report(report, run_folder)

    # Download markdown files
    findings_md_path = None
    for name, filename in markdown_files.items():
        local_path = download_markdown_file(filename, run_folder)
        if name == "findings":
            findings_md_path = local_path

    # Display summary
    console.print(f"\n[green]✓ Scan complete![/green]\n")
    console.print(f"[cyan]📁 Reports saved to:[/cyan] {run_folder}")

    # List generated files
    from rich.tree import Tree
    tree = Tree("📂 Generated Files")
    tree.add(f"📝 [yellow]findings.md[/yellow] - Main findings (auto-opening)")
    tree.add(f"📊 [blue]compliance_report.md[/blue] - Executive summary")
    tree.add(f"🔍 [magenta]traceability_matrix.md[/magenta] - Clause coverage")
    tree.add(f"📄 report.pdf - Traditional report")
    tree.add(f"🌐 report.html - Web report")
    console.print(tree)

    # Show quick stats
    findings_count = len(result.get("findings", []))
    violations = sum(1 for f in result["findings"] if f.get("violation"))

    console.print(f"\n[cyan]📊 Summary:[/cyan]")
    console.print(f"  • Total findings: {findings_count}")
    console.print(f"  • Violations: {violations}")
    console.print(f"  • Compliance score: {result.get('compliance_score', 'N/A')}")
    console.print(f"  • Cost: ${result['audit_meta']['cost']:.2f}")
    console.print(f"  • Cache hits: {result['audit_meta'].get('cache_hits', 0)}")

    # Auto-open findings.md
    if findings_md_path and should_auto_open():
        console.print(f"\n[cyan]Opening findings.md in editor...[/cyan]")
        open_in_editor(findings_md_path)
    else:
        # Show quick actions
        show_quick_actions(findings_md_path, run_folder)

def should_auto_open() -> bool:
    """Check if should auto-open findings.md."""
    config_value = get_config_value('ui.auto_open_findings', True)
    return config_value and os.getenv('EDITOR') is not None

def open_in_editor(file_path: str):
    """Open file in configured editor."""
    editor = os.getenv('EDITOR', 'vim')

    try:
        subprocess.run([editor, file_path])
    except Exception as e:
        console.print(f"[yellow]Could not open editor: {e}[/yellow]")
        console.print(f"[cyan]File location:[/cyan] {file_path}")

def show_quick_actions(findings_path, run_folder):
    """Show quick action menu."""
    from rich.panel import Panel

    actions = """
[cyan]Quick actions:[/cyan]
  [v] View findings.md
  [f] Generate fixes (clausi fix)
  [c] Commit to git
  [o] Open folder
  [q] Quit
"""

    console.print(Panel(actions, title="What's next?", border_style="cyan"))

    action = Prompt.ask("Choose action", choices=['v', 'f', 'c', 'o', 'q'], default='v')

    if action == 'v':
        open_in_editor(findings_path)
    elif action == 'f':
        console.print("\n[cyan]Run:[/cyan] clausi fix findings.md")
    elif action == 'c':
        commit_reports(run_folder)
    elif action == 'o':
        import webbrowser
        webbrowser.open(f"file://{run_folder}")
```

---

### **Task 1.4: Enhanced Progress & Cache Stats**

#### **What to Build:**

Real-time progress with cache hit/miss stats, cost savings display.

#### **Implementation:**

```python
# File: clausi_cli/progress.py

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from rich.panel import Panel

class ScanProgress:
    """Enhanced progress display for scans."""

    def __init__(self, total_files: int):
        self.total_files = total_files
        self.cache_hits = 0
        self.cache_misses = 0
        self.current_file = None

    def create_progress_display(self):
        """Create rich progress display."""

        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("• Cache: {task.fields[cache_hits]}/{task.fields[total]}"),
            TextColumn("• Cost: ${task.fields[cost]:.2f}"),
        )

    def scan_with_progress(self, files, scan_function):
        """Scan files with progress display."""

        with self.create_progress_display() as progress:
            task = progress.add_task(
                "Scanning files...",
                total=self.total_files,
                cache_hits=0,
                cost=0.0
            )

            results = []
            total_cost = 0.0

            for i, file in enumerate(files):
                # Check cache first (simulated - actual logic in backend)
                progress.update(
                    task,
                    description=f"Scanning {file['path']}...",
                    advance=1,
                    cache_hits=self.cache_hits,
                    cost=total_cost
                )

                # Simulate cache check
                cached = check_cache(file)  # This would be from backend response

                if cached:
                    self.cache_hits += 1
                    results.append(cached)
                else:
                    self.cache_misses += 1
                    result = scan_function(file)
                    total_cost += result.get('cost', 0)
                    results.append(result)

            progress.update(task, description="✓ Scan complete!")

        # Show final stats
        self.show_final_stats(total_cost)

        return results

    def show_final_stats(self, total_cost):
        """Show final scan statistics."""

        cache_rate = (self.cache_hits / self.total_files * 100) if self.total_files > 0 else 0

        # Calculate savings
        estimated_full_cost = self.total_files * 0.05  # $0.05 per file average
        savings = estimated_full_cost - total_cost

        stats = f"""
[cyan]📊 Scan Statistics:[/cyan]

  Files scanned: {self.total_files}
  Cache hits: {self.cache_hits} ({cache_rate:.1f}%)
  Cache misses: {self.cache_misses}

  Cost: ${total_cost:.2f}
  Estimated without cache: ${estimated_full_cost:.2f}
  Savings: ${savings:.2f} ({savings/estimated_full_cost*100:.1f}%)
"""

        console.print(Panel(stats, title="✓ Complete", border_style="green"))
```

**Usage in scan command:**

```python
@cli.command()
def scan(path, **kwargs):
    # ... setup code ...

    # Scan with progress
    progress = ScanProgress(total_files=len(files))
    results = progress.scan_with_progress(files, lambda f: scan_file_api(f))
```

---

### **Task 1.5: Git Integration - Basic**

#### **What to Build:**

Detect git repos, track compliance reports, basic commit support.

#### **Implementation:**

```python
# File: clausi_cli/git_utils.py

import git
from pathlib import Path

class GitIntegration:
    """Git integration utilities."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        try:
            self.repo = git.Repo(project_path, search_parent_directories=True)
            self.enabled = True
        except git.InvalidGitRepositoryError:
            self.repo = None
            self.enabled = False

    def is_git_repo(self) -> bool:
        """Check if project is a git repository."""
        return self.enabled

    def get_current_branch(self) -> str:
        """Get current git branch."""
        if not self.enabled:
            return None
        return self.repo.active_branch.name

    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        if not self.enabled:
            return False
        return self.repo.is_dirty()

    def commit_reports(self, reports_folder: str, message: str = None):
        """Commit compliance reports to git."""
        if not self.enabled:
            console.print("[yellow]Not a git repository. Skipping commit.[/yellow]")
            return

        # Add reports folder
        self.repo.index.add([reports_folder])

        # Generate commit message
        if not message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            message = f"chore: update compliance reports [{timestamp}] [skip ci]"

        # Commit
        self.repo.index.commit(message)
        console.print(f"[green]✓ Committed reports to git[/green]")
        console.print(f"[cyan]Message:[/cyan] {message}")

# New command: commit-reports
@cli.command('commit-reports')
@click.argument('reports_folder', type=click.Path(exists=True))
@click.option('--message', '-m', help='Commit message')
def commit_reports_cmd(reports_folder, message):
    """Commit compliance reports to git."""

    git_integration = GitIntegration(os.getcwd())

    if not git_integration.is_git_repo():
        console.print("[red]Error: Not a git repository[/red]")
        sys.exit(1)

    git_integration.commit_reports(reports_folder, message)
```

---

## **Phase 2: Auto-Fix Experience (Weeks 5-8)**

**Goal:** Implement auto-fix generation and application

### **Task 2.1: Fix Generation Command**

#### **What to Build:**

Parse findings.md, call backend to generate fixes, present for review.

#### **CLI Usage:**

```bash
# Generate fixes from findings.md
clausi fix findings.md

# Auto-apply all safe fixes (batch mode)
clausi fix findings.md --batch

# Fix specific finding by ID
clausi fix findings.md --finding-id EUAIA-3.1

# Preview fixes without applying
clausi fix findings.md --dry-run
```

#### **Implementation:**

```python
# File: clausi_cli/fix.py

from pathlib import Path
import difflib
from rich.syntax import Syntax
from rich.prompt import Confirm

class FixApplicator:
    """Apply auto-generated fixes to code."""

    def __init__(self, findings_md_path: str):
        self.findings_path = Path(findings_md_path)
        self.findings = self.parse_findings_md()

    def parse_findings_md(self) -> list:
        """Parse findings from markdown file."""
        # TODO: Implement markdown parser
        # Extract findings with metadata
        pass

    def generate_fix(self, finding: dict, api_key: str) -> dict:
        """Call backend to generate fix."""

        # Read file content
        file_path = finding['file_path']
        with open(file_path, 'r') as f:
            file_content = f.read()

        # Call backend /api/clausi/fix
        response = requests.post(
            f"{get_api_url()}/api/clausi/fix",
            headers={"X-OpenAI-Key": api_key},
            json={
                "finding": finding,
                "file_content": file_content,
                "file_path": file_path
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": response.text}

    def show_fix_preview(self, fix_result: dict):
        """Show fix preview with diff."""

        console.print(f"\n[cyan]{'='*60}[/cyan]")
        console.print(f"[yellow]Finding: {fix_result['finding_id']}[/yellow]")
        console.print(f"[cyan]{'='*60}[/cyan]\n")

        # Show explanation
        console.print(f"[green]Explanation:[/green]")
        console.print(fix_result['explanation'])

        # Show diff with syntax highlighting
        console.print(f"\n[green]Proposed changes:[/green]")
        diff = fix_result['diff']

        # Syntax highlight diff
        syntax = Syntax(diff, "diff", theme="monokai", line_numbers=True)
        console.print(syntax)

        # Show warnings
        if fix_result.get('warnings'):
            console.print(f"\n[yellow]⚠️  Warnings:[/yellow]")
            for warning in fix_result['warnings']:
                console.print(f"  • {warning}")

    def apply_fix(self, file_path: str, fixed_code: str):
        """Apply fix to file."""

        # Backup original
        backup_path = f"{file_path}.backup"
        shutil.copy(file_path, backup_path)

        # Write fixed code
        with open(file_path, 'w') as f:
            f.write(fixed_code)

        console.print(f"[green]✓ Applied fix to {file_path}[/green]")
        console.print(f"[cyan]  Backup saved: {backup_path}[/cyan]")

    def interactive_fix(self, dry_run: bool = False):
        """Interactive fix application."""

        fixable = [f for f in self.findings if f.get('can_auto_fix')]

        console.print(f"\n[cyan]Found {len(fixable)} fixable findings[/cyan]")
        console.print(f"[yellow]Generating fixes with Claude...[/yellow]\n")

        api_key = get_openai_key()

        for i, finding in enumerate(fixable, 1):
            console.print(f"\n[cyan]{'='*60}[/cyan]")
            console.print(f"[yellow]Finding {i}/{len(fixable)}[/yellow]")
            console.print(f"[cyan]{'='*60}[/cyan]")

            # Generate fix
            with console.status(f"Generating fix for {finding['clause_id']}..."):
                fix_result = self.generate_fix(finding, api_key)

            if not fix_result.get('success'):
                console.print(f"[red]✗ Failed to generate fix: {fix_result.get('error')}[/red]")
                continue

            # Show preview
            self.show_fix_preview(fix_result)

            if dry_run:
                console.print("\n[cyan](Dry run - not applying)[/cyan]")
                continue

            # Prompt for action
            console.print("\n[cyan]Apply this fix?[/cyan]")
            action = Prompt.ask(
                "Choose",
                choices=['y', 'n', 'e', 's', 'q'],
                default='n'
            )

            if action == 'y':
                self.apply_fix(finding['file_path'], fix_result['fixed_code'])
            elif action == 'e':
                # Open in editor for manual editing
                self.edit_and_apply(finding['file_path'], fix_result['fixed_code'])
            elif action == 's':
                # Skip this fix
                console.print("[yellow]Skipped[/yellow]")
            elif action == 'q':
                console.print("[yellow]Quit fixing[/yellow]")
                break
            else:
                console.print("[yellow]Skipped[/yellow]")

        console.print("\n[green]✓ Fix session complete[/green]")

    def batch_fix(self):
        """Apply all safe fixes automatically."""

        fixable = [f for f in self.findings if f.get('can_auto_fix')]
        api_key = get_openai_key()

        applied = 0
        failed = 0

        with console.status("Applying fixes..."):
            for finding in fixable:
                fix_result = self.generate_fix(finding, api_key)

                if fix_result.get('success'):
                    self.apply_fix(finding['file_path'], fix_result['fixed_code'])
                    applied += 1
                else:
                    failed += 1

        console.print(f"\n[green]✓ Applied {applied} fixes[/green]")
        if failed > 0:
            console.print(f"[yellow]⚠️  {failed} fixes failed[/yellow]")

# Add command
@cli.command('fix')
@click.argument('findings_md', type=click.Path(exists=True))
@click.option('--batch', is_flag=True, help='Auto-apply all safe fixes')
@click.option('--dry-run', is_flag=True, help='Preview without applying')
@click.option('--finding-id', help='Fix specific finding only')
def fix_cmd(findings_md, batch, dry_run, finding_id):
    """Generate and apply code fixes from findings.md."""

    applicator = FixApplicator(findings_md)

    if batch:
        applicator.batch_fix()
    else:
        applicator.interactive_fix(dry_run=dry_run)
```

---

### **Task 2.2: Verify Fixes Command**

#### **What to Build:**

Re-scan after applying fixes to verify they worked.

#### **CLI Usage:**

```bash
# Apply fixes then re-scan
clausi fix findings.md --verify

# Or manually verify
clausi scan --verify-fixes ./compliance-reports/previous_scan/
```

#### **Implementation:**

```python
@cli.command('verify-fixes')
@click.argument('previous_scan_folder', type=click.Path(exists=True))
def verify_fixes(previous_scan_folder):
    """Re-scan to verify applied fixes."""

    # Load previous findings
    previous_findings = load_findings_from_folder(previous_scan_folder)

    console.print(f"[cyan]Verifying {len(previous_findings)} fixes...[/cyan]")

    # Run new scan
    new_results = run_scan(...)

    # Compare results
    fixed = []
    still_failing = []

    for old_finding in previous_findings:
        # Check if finding still exists in new scan
        still_present = any(
            f['clause_id'] == old_finding['clause_id'] and
            f['file_path'] == old_finding['file_path']
            for f in new_results['findings']
        )

        if still_present:
            still_failing.append(old_finding)
        else:
            fixed.append(old_finding)

    # Display results
    console.print(f"\n[green]✓ Fixed: {len(fixed)}[/green]")
    console.print(f"[yellow]⚠️  Still failing: {len(still_failing)}[/yellow]")

    if still_failing:
        console.print("\n[yellow]Findings still present:[/yellow]")
        for finding in still_failing:
            console.print(f"  • {finding['clause_id']} ({finding['file_path']})")
```

---

## **Phase 3: Developer Tools (Weeks 9-12)**

**Goal:** Watch mode, pre-commit hooks, scan comparison

### **Task 3.1: Watch Mode**

#### **What to Build:**

Real-time scanning as files change during development.

#### **CLI Usage:**

```bash
# Watch current directory
clausi watch

# Watch specific path
clausi watch ./src

# Watch with specific clauses
clausi watch --include EUAIA-3.1
```

#### **Implementation:**

```python
# File: clausi_cli/watch.py

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

class ComplianceWatcher(FileSystemEventHandler):
    """Watch for file changes and scan."""

    def __init__(self, regulation, clauses_include=None):
        self.regulation = regulation
        self.clauses_include = clauses_include
        self.pending_scans = set()
        self.scan_debounce = 2  # seconds

    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return

        # Filter to code files
        if not self.is_code_file(event.src_path):
            return

        # Add to pending scans
        self.pending_scans.add(event.src_path)

        # Debounce: wait for changes to settle
        time.sleep(self.scan_debounce)

        # Scan changed files
        self.scan_pending_files()

    def is_code_file(self, path: str) -> bool:
        """Check if file should be scanned."""
        extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.go', '.rs'}
        return Path(path).suffix in extensions

    def scan_pending_files(self):
        """Scan all pending files."""
        if not self.pending_scans:
            return

        files = list(self.pending_scans)
        self.pending_scans.clear()

        console.print(f"\n[cyan][{time.strftime('%H:%M:%S')}] ✏️  {len(files)} file(s) changed[/cyan]")

        # Quick scan (incremental)
        results = quick_scan(files, self.regulation, self.clauses_include)

        # Display results
        if results['new_findings']:
            console.print(f"[yellow]⚠️  {len(results['new_findings'])} new finding(s):[/yellow]")
            for finding in results['new_findings']:
                console.print(f"  • {finding['clause_id']}: {finding['explanation'][:60]}...")
        else:
            console.print(f"[green]✅ No new issues![/green]")

@cli.command('watch')
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--include', multiple=True, help='Include specific clauses')
def watch_cmd(path, include):
    """Watch for file changes and scan in real-time."""

    console.print(f"[cyan]👀 Watching for changes in: {path}[/cyan]")
    console.print(f"[cyan]Press Ctrl+C to stop[/cyan]\n")

    event_handler = ComplianceWatcher(
        regulation="EU-AIA",  # TODO: from config
        clauses_include=list(include) if include else None
    )

    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[yellow]Stopped watching[/yellow]")

    observer.join()
```

---

### **Task 3.2: Pre-Commit Hook**

#### **What to Build:**

Install git pre-commit hook to scan staged files.

#### **CLI Usage:**

```bash
# Install pre-commit hook
clausi init --git-hooks

# Manual hook management
clausi hooks install
clausi hooks uninstall
clausi hooks test
```

#### **Implementation:**

```python
# File: clausi_cli/hooks.py

PRE_COMMIT_TEMPLATE = """#!/bin/bash
# Clausi compliance pre-commit hook
# Generated by clausi-cli

echo "🔍 Running compliance check..."

# Get staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\\.py$|\\.js$|\\.ts$')

if [ -z "$STAGED_FILES" ]; then
    echo "✓ No code files staged"
    exit 0
fi

# Run clausi scan on staged files only
clausi scan --staged --critical-only --no-cache

# Check exit code
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Compliance check failed!"
    echo "   Fix critical issues or use 'git commit --no-verify' to skip"
    exit 1
fi

echo "✓ Compliance check passed"
exit 0
"""

class HookManager:
    """Manage git hooks."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.hooks_dir = self.repo_path / '.git' / 'hooks'
        self.pre_commit_path = self.hooks_dir / 'pre-commit'

    def install_pre_commit(self):
        """Install pre-commit hook."""

        if not self.hooks_dir.exists():
            console.print("[red]Not a git repository[/red]")
            return False

        # Backup existing hook
        if self.pre_commit_path.exists():
            backup_path = self.pre_commit_path.with_suffix('.backup')
            shutil.copy(self.pre_commit_path, backup_path)
            console.print(f"[yellow]Backed up existing hook to {backup_path}[/yellow]")

        # Write hook
        self.pre_commit_path.write_text(PRE_COMMIT_TEMPLATE)
        self.pre_commit_path.chmod(0o755)  # Make executable

        console.print("[green]✓ Installed pre-commit hook[/green]")
        console.print(f"[cyan]Location:[/cyan] {self.pre_commit_path}")
        return True

@cli.group('hooks')
def hooks():
    """Manage git hooks."""
    pass

@hooks.command('install')
def install_hooks():
    """Install git pre-commit hook."""
    manager = HookManager(os.getcwd())
    manager.install_pre_commit()
```

---

### **Task 3.3: Compare Scans**

#### **What to Build:**

Compare compliance over time, show trends.

#### **CLI Usage:**

```bash
# Compare with previous scan
clausi compare ./compliance-reports/latest ./compliance-reports/previous

# Compare with main branch
clausi compare --base main

# Show trend over last N scans
clausi trends --last 10
```

#### **Implementation:**

```python
@cli.command('compare')
@click.argument('base_scan', type=click.Path(exists=True))
@click.argument('current_scan', type=click.Path(exists=True))
def compare_scans(base_scan, current_scan):
    """Compare two compliance scans."""

    base_findings = load_findings_from_folder(base_scan)
    current_findings = load_findings_from_folder(current_scan)

    # Calculate changes
    fixed = []
    new = []
    unchanged = []

    base_ids = {f"{f['clause_id']}:{f['file_path']}" for f in base_findings}
    current_ids = {f"{f['clause_id']}:{f['file_path']}" for f in current_findings}

    fixed_ids = base_ids - current_ids
    new_ids = current_ids - base_ids
    unchanged_ids = base_ids & current_ids

    # Display comparison
    console.print("\n[cyan]📊 Scan Comparison[/cyan]\n")

    from rich.table import Table
    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Base", style="yellow")
    table.add_column("Current", style="green")
    table.add_column("Change", style="magenta")

    table.add_row(
        "Total Findings",
        str(len(base_findings)),
        str(len(current_findings)),
        f"{len(current_findings) - len(base_findings):+d}"
    )
    table.add_row("Fixed", "-", str(len(fixed_ids)), f"+{len(fixed_ids)}")
    table.add_row("New", "-", str(len(new_ids)), f"{len(new_ids):+d}")

    console.print(table)

    # Show details
    if fixed_ids:
        console.print("\n[green]✅ Fixed findings:[/green]")
        for finding_id in list(fixed_ids)[:10]:
            console.print(f"  • {finding_id}")

    if new_ids:
        console.print("\n[yellow]⚠️  New findings:[/yellow]")
        for finding_id in list(new_ids)[:10]:
            console.print(f"  • {finding_id}")
```

---

## **API Contract with Backend**

### **Endpoint: POST /api/clausi/scan**

**Request:**
```json
{
  "path": "/project",
  "regulations": ["EU-AIA"],
  "mode": "full",
  "ai_provider": "claude",
  "ai_model": "claude-3-5-sonnet-20241022",
  "clauses_include": ["EUAIA-3.1", "EUAIA-7.2"],
  "clauses_exclude": [],
  "metadata": {
    "incremental": true,
    "git_base_branch": "main",
    "format": "markdown",
    "files": [...]
  }
}
```

**Response:**
```json
{
  "findings": [...],
  "run_folder": "./compliance-reports/project_EUAIA_20251018_143022/",
  "markdown_files": {
    "findings": "findings.md",
    "report": "compliance_report.md",
    "matrix": "traceability_matrix.md"
  },
  "generated_reports": [
    {"format": "pdf", "filename": "report.pdf"},
    {"format": "html", "filename": "report.html"}
  ],
  "audit_meta": {
    "model": "claude-3-5-sonnet-20241022",
    "provider": "claude",
    "total_tokens": 12500,
    "cost": 0.42,
    "cache_hits": 245,
    "cache_misses": 2,
    "clauses_scanned": ["EUAIA-3.1", "EUAIA-7.2"],
    "prompt_hash": "sha256:abc123..."
  },
  "compliance_score": 87.5
}
```

### **Endpoint: POST /api/clausi/fix**

**Request:**
```json
{
  "finding": {
    "clause_id": "EUAIA-3.1",
    "severity": "high",
    "location": "line 42",
    "explanation": "Missing risk assessment...",
    "file_path": "src/recommender.py"
  },
  "file_content": "def process_user_data(data):\n    ...",
  "file_path": "src/recommender.py"
}
```

**Response:**
```json
{
  "success": true,
  "finding_id": "EUAIA-3.1",
  "original_code": "...",
  "fixed_code": "...",
  "diff": "--- original\n+++ fixed\n...",
  "explanation": "Added risk assessment docstring with required fields",
  "warnings": ["Review generated docstring for accuracy"],
  "can_auto_apply": true
}
```

---

## **File Structure & Configuration**

### **Project Structure After Init:**

```
project/
├── .clausi/
│   ├── config.yml              # User configuration
│   └── cache.db                # Optional local cache
├── .clausiignore               # Files to skip
├── .git/
│   └── hooks/
│       └── pre-commit          # Auto-generated
└── compliance-reports/         # Git-tracked
    ├── project_EUAIA_20251015_120000/
    │   ├── findings.md
    │   ├── compliance_report.md
    │   ├── traceability_matrix.md
    │   ├── report.pdf
    │   └── audit_meta.json
    └── project_EUAIA_20251018_143022/
        └── ...
```

### **Enhanced Config (.clausi/config.yml):**

```yaml
# AI Configuration
ai:
  provider: claude               # claude or openai
  model: claude-3-5-sonnet-20241022
  fallback_provider: openai
  fallback_model: gpt-4

# API Keys (prefer environment variables)
api_keys:
  anthropic: ${ANTHROPIC_API_KEY}
  openai: ${OPENAI_API_KEY}

# Scan Defaults
defaults:
  regulations: [EU-AIA]
  mode: full
  output_format: markdown
  enable_caching: true
  incremental_scans: true

# UI Preferences
ui:
  auto_open_findings: true
  editor: ${EDITOR}               # Falls back to vim
  theme: monokai
  show_cache_stats: true

# Git Integration
git:
  auto_commit: false
  commit_message_template: "chore: update compliance reports [{timestamp}] [skip ci]"
  track_in_git: true

# Clause Presets
presets:
  critical-only: [EUAIA-3.1, EUAIA-5.2, EUAIA-7.2, EUAIA-9.1]
  high-priority: [EUAIA-3.1, EUAIA-5.2, EUAIA-7.2, EUAIA-9.1, EUAIA-10.2]

# Auto-Fix
auto_fix:
  require_confirmation: true      # Prompt before applying
  create_backups: true
  max_batch_fixes: 20
```

---

## **User Experience Flows**

### **Flow 1: First-Time User**

```bash
$ clausi init

Welcome to Clausi CLI! 🚀

Setting up your compliance environment...

✓ Created .clausi/config.yml
✓ Created .clausiignore
✓ Detected git repository
  Install pre-commit hook? [Y/n]: y
✓ Installed pre-commit hook

Configuration:
  AI Provider: Claude (recommended)
  Model: claude-3-5-sonnet-20241022

  Need API key? Get one at: https://console.anthropic.com

Set your API key:
  export ANTHROPIC_API_KEY=sk-ant-...

Ready to scan! Try:
  clausi scan .
```

### **Flow 2: Daily Developer Workflow**

```bash
# Start watch mode in morning
$ clausi watch ./src

👀 Watching for changes in: ./src
Press Ctrl+C to stop

[09:15:32] ✏️  src/recommender.py changed
           🔍 Scanning... (1 file, cached: 246)
           ✅ No new issues!

[09:42:18] ✏️  src/auth.py changed
           🔍 Scanning... (1 file, cached: 246)
           ⚠️  1 new finding:
           - GDPR-32: Missing encryption (line 78)
           📝 Updated findings.md

# At end of day, fix issues
$ clausi fix compliance-reports/latest/findings.md

📝 Found 3 fixable findings
🤖 Generating fixes with Claude...

Finding 1/3: GDPR-32 (src/auth.py:78)
  Issue: Missing encryption for PII
  [Shows diff]
  Apply? [y/N/e/s/q]: y
  ✓ Applied

Finding 2/3: EUAIA-3.1 (src/recommender.py:42)
  Issue: Missing risk assessment
  [Shows diff]
  Apply? [y/N/e/s/q]: y
  ✓ Applied

✓ Applied 2/3 fixes
⚠️  1 fix requires manual review

# Verify fixes worked
$ clausi scan --verify

✓ Scanning to verify fixes...
✓ Fixed: 2
⚠️  Still failing: 0

# Commit everything
$ git add .
$ git commit -m "fix: compliance issues from scan"
[pre-commit hook runs]
✓ Compliance check passed
```

### **Flow 3: CI/CD Integration**

```yaml
# .github/workflows/compliance.yml
name: Compliance Check

on: [pull_request]

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Clausi Scan
        run: |
          pip install clausi-cli
          clausi scan . \
            --ai-provider claude \
            --critical-only \
            --format markdown \
            --output ./compliance-reports
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Upload Reports
        uses: actions/upload-artifact@v3
        with:
          name: compliance-reports
          path: ./compliance-reports

      - name: Comment PR
        uses: actions/github-script@v6
        with:
          script: |
            // Read findings.md and post as comment
            const fs = require('fs');
            const findings = fs.readFileSync('./compliance-reports/latest/findings.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: findings
            });
```

---

## **Testing Strategy**

### **Unit Tests**

```python
# tests/test_fix_applicator.py

import pytest
from clausi_cli.fix import FixApplicator

def test_parse_findings_md():
    """Test parsing findings from markdown."""
    applicator = FixApplicator('test_findings.md')
    findings = applicator.parse_findings_md()

    assert len(findings) > 0
    assert 'clause_id' in findings[0]
    assert 'file_path' in findings[0]

def test_diff_generation():
    """Test diff generation."""
    original = "def foo():\n    pass"
    fixed = "def foo():\n    '''Docstring'''\n    pass"

    diff = generate_diff(original, fixed)
    assert '+++' in diff
    assert 'Docstring' in diff

# tests/test_git_integration.py

def test_detect_git_repo():
    """Test git repository detection."""
    git_int = GitIntegration('/path/to/repo')
    assert git_int.is_git_repo()

def test_commit_reports():
    """Test committing reports."""
    git_int = GitIntegration('/path/to/repo')
    git_int.commit_reports('./reports', 'test commit')

    # Verify commit exists
    assert 'test commit' in git_int.repo.head.commit.message
```

### **Integration Tests**

```python
# tests/test_scan_flow.py

@pytest.mark.integration
def test_full_scan_flow():
    """Test complete scan workflow."""

    # Run scan
    result = subprocess.run(
        ['clausi', 'scan', '.', '--ai-provider', 'claude'],
        capture_output=True
    )

    assert result.returncode == 0

    # Verify markdown files created
    assert Path('./compliance-reports/latest/findings.md').exists()
    assert Path('./compliance-reports/latest/compliance_report.md').exists()

@pytest.mark.integration
def test_fix_application():
    """Test fix generation and application."""

    # Generate fix
    result = subprocess.run(
        ['clausi', 'fix', 'findings.md', '--dry-run'],
        capture_output=True
    )

    assert result.returncode == 0
    assert 'Generated fix' in result.stdout.decode()
```

---

## **Migration Guide**

### **From v0.3.0 to v1.0.0**

#### **Breaking Changes:**

1. **Default AI provider changed to Claude**
   - Migration: Add `ai.provider: openai` to config if you want to keep using GPT-4

2. **Output format changed to markdown by default**
   - Migration: Use `--format pdf` to get old behavior

3. **Reports now saved in dated folders**
   - Migration: Old reports stay in `./reports/`, new ones go to `./compliance-reports/project_REG_DATE/`

#### **New Environment Variables:**

```bash
# Add to your .env or .bashrc
export ANTHROPIC_API_KEY=sk-ant-...  # Required for Claude

# Optional: Keep using OpenAI
export CLAUSI_AI_PROVIDER=openai
```

#### **Config Migration:**

**Old config (.clausi/config.yml):**
```yaml
openai_key: sk-...
api_token: uuid-token
report:
  format: pdf
```

**New config (.clausi/config.yml):**
```yaml
# AI configuration (NEW)
ai:
  provider: claude
  model: claude-3-5-sonnet-20241022

# API keys
api_keys:
  anthropic: ${ANTHROPIC_API_KEY}
  openai: ${OPENAI_API_KEY}  # Migrated from openai_key

# Token (unchanged)
api_token: uuid-token

# Report defaults (NEW structure)
defaults:
  output_format: markdown  # Changed from 'pdf'
  enable_caching: true
```

**Auto-migration script:**

```bash
clausi migrate-config
```

This will:
- Backup old config to `.clausi/config.yml.v0.3.0`
- Convert to new format
- Prompt for missing values (like ANTHROPIC_API_KEY)

---

## **Success Criteria**

### **Phase 1 (Weeks 1-4):**
- ✅ Claude integration works seamlessly
- ✅ 80%+ of users use cached scans on second run
- ✅ Markdown files auto-open in editor
- ✅ Clause scoping saves 50%+ scan time
- ✅ Average scan cost: $0.50 (down from $5.00)

### **Phase 2 (Weeks 5-8):**
- ✅ Auto-fix success rate: 70%+ for documentation issues
- ✅ 90%+ of users try auto-fix feature
- ✅ Fix verification shows 0 regressions
- ✅ Average time to fix 10 issues: <30 min (down from 5 hours)

### **Phase 3 (Weeks 9-12):**
- ✅ Watch mode used by 50%+ of daily active users
- ✅ Pre-commit hook installed in 70%+ of projects
- ✅ Scan comparison used for sprint reviews
- ✅ Developer satisfaction: 8/10 or higher

---

## **Next Steps**

### **Week 1-2:**
1. Set up development environment
2. Implement multi-model support (Claude + OpenAI)
3. Add clause scoping UI
4. Test with backend API

### **Week 3-4:**
5. Implement markdown file handling
6. Add enhanced progress bars
7. Basic git integration
8. Polish UX based on feedback

### **Review Checkpoint (Week 4):**
- Demo to stakeholders
- Gather user feedback
- Adjust Phase 2 priorities

---

## **Appendix**

### **A. Commands Reference**

```bash
# Scanning
clausi scan PATH                        # Basic scan
clausi scan . --ai-provider claude      # Use Claude
clausi scan . --select-clauses          # Interactive clause selection
clausi scan . --include EUAIA-3.1       # Specific clauses
clausi scan . --watch                   # Watch mode

# Fixing
clausi fix findings.md                  # Interactive fix
clausi fix findings.md --batch          # Auto-apply all
clausi fix findings.md --dry-run        # Preview only
clausi scan --verify-fixes ./prev       # Verify fixes

# Git Integration
clausi init --git-hooks                 # Setup with hooks
clausi commit-reports ./reports         # Commit reports
clausi compare base/ current/           # Compare scans
clausi hooks install                    # Install hooks

# Configuration
clausi config show                      # Show config
clausi config set --ai-provider claude  # Set provider
clausi models list                      # List AI models

# Developer Tools
clausi watch ./src                      # Watch for changes
clausi trends --last 10                 # Show trend
```

### **B. Keyboard Shortcuts**

When applying fixes interactively:
- `y` - Yes, apply this fix
- `n` - No, skip this fix
- `e` - Edit in $EDITOR before applying
- `s` - Show full diff
- `q` - Quit fixing session
- `a` - Apply all remaining (batch mode)

### **C. Troubleshooting**

**Issue: "ANTHROPIC_API_KEY not found"**
```bash
# Solution:
export ANTHROPIC_API_KEY=sk-ant-...
# Or add to ~/.bashrc for persistence
```

**Issue: "findings.md not opening in editor"**
```bash
# Solution:
export EDITOR=code  # VSCode
# or
export EDITOR=vim   # Vim
```

**Issue: "Pre-commit hook failing"**
```bash
# Bypass for emergency commits:
git commit --no-verify

# Or fix the issue:
clausi scan --critical-only
clausi fix findings.md
```

---

**End of CLI Modernization Plan**

For backend coordination, see: `backend/IMPLEMENTATION_PLAN.md`

**Questions?** Contact backend team or file an issue.
