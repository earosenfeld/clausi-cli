# Clausi CLI

**Positioning (2026-08-20, Eric + CEO decision): "The compliance scanner
that never sees your code."** Free, local, BYOK command-line tool for AI
compliance auditing against regulatory frameworks. There is no hosted
backend in the scan path — everything (file discovery, AI calls, caching,
report generation) runs on the user's machine. Be precise in any copy: code
content is sent to the user's own chosen AI provider (`api.anthropic.com`
or `api.openai.com`) under the user's own key — that is NOT the same claim
as "nothing leaves your machine." Never overclaim zero egress; the accurate
claim is "Clausi never sees your code; your code goes only to the AI
provider you choose, under your own key."

Business model (not yet built — do not add pricing/paywall copy or code):
CLI stays free forever; future monetization is a subscription to
maintained regulation packs (versioned, dated clause definitions). This is
why `clausi/data/regulations/*.yml` carry `version`/`effective_date`/
`last_updated` fields — the legal-content schema needs to support dated
updates now, even though nothing is sold yet.

## Related Projects

- **Backend:** `../../clausi/.Codex/AGENTS.md` (no longer used by this CLI's scan flow)
- **Frontend:** `../../clausi-frontend/.Codex/AGENTS.md`

## Detailed Documentation

Legacy deep-dive docs (from the hosted-backend era) are archived at `../archive/Codex/`. Read on demand only — never @-import them; treat pricing/backend-flow content there as historical, not current.

Area-specific rules live in `.Codex/rules/` (provider/local-scan patterns, testing + packaging) and load automatically when you touch matching files.

---

## Quick Reference

```bash
# Interactive mode (default)
clausi

# Direct scan commands (BYOK - set ANTHROPIC_API_KEY or OPENAI_API_KEY first)
clausi scan . -r EU-AIA                    # Auto-detects provider from env key
clausi scan . -r EU-AIA --Codex           # Force Codex
clausi scan . -r EU-AIA --openai gpt-4o    # Force OpenAI

# Other commands
clausi config show                          # View configuration
clausi cache stats / clausi cache clear     # Local scan-result cache
```

## Tech Stack

- **Framework:** Click (CLI), Rich (UI), Questionary (Interactive)
- **Language:** Python 3.8+
- **Config:** YAML (~/.clausi/config.yml)
- **AI SDKs:** `anthropic`, `openai` (called directly with the user's key)

## Project Structure

```
clausi/
├── cli.py                      # Main CLI commands & orchestration
├── core/
│   ├── scanner.py               # File discovery & filtering
│   ├── clause_selector.py       # Preset/clause scoping
│   ├── ai_provider.py           # Codex/OpenAI BYOK calls + prompt template
│   ├── cache.py                 # Local on-disk scan-result cache
│   ├── compliance_analyzer.py   # Concurrent scan orchestration + effort bumping
│   ├── markdown_report.py       # Local Markdown report generation
│   ├── pdf_report.py            # Local branded stakeholder PDF generation
│   └── docs_generator.py        # Local AI docs generation (index/architecture/components/security.md)
├── data/
│   └── regulations/             # Bundled built-in regulation YAML (EU-AIA, GDPR, ...) — each has version/effective_date/last_updated
├── utils/
│   ├── config.py                # Config + BYOK key management
│   ├── emoji.py                 # Cross-platform emoji
│   └── regulations.py           # Built-in + custom regulation loading (local, no network)
└── tui/
    └── interactive.py           # Interactive mode (questionary)
```

## Key Files

| File | Purpose |
|------|---------|
| `cli.py: _resolve_provider_and_model` | Provider detection (Codex/openai, no hosted mode) |
| `cli.py: scan` | Main scan command — local flow, no backend calls |
| `core/ai_provider.py` | Direct Anthropic/OpenAI SDK calls, prompt template |
| `core/compliance_analyzer.py` | Bounded-concurrency per-file scan + effort bumping |
| `core/cache.py` | Content-hash-keyed disk cache (`~/.clausi/cache/`) |
| `core/clause_selector.py: CLAUSE_PRESETS` | Preset clause-ID lists — IDs are matched by exact string equality against `data/regulations/*.yml` `id:` fields, not fuzzy-matched. A stale/typo'd ID silently scans zero clauses (found+fixed 2026-08-20 — presets had been referencing IDs like `EUAIA-3.1` that never existed; real IDs are `Article-9`, `Clause-4`, `Security-Rule-164.308`, etc). Verify preset IDs actually exist in the regulation YAML when editing either file. |
| `core/markdown_report.py` | findings.md / compliance_report.md / traceability_matrix.md |
| `core/pdf_report.py` | report.pdf decision brief, evidence cards, and traceability matrix |
| `interactive.py` | Arrow-key menu navigation |
| `config.py` | ~/.clausi/config.yml management |

## AI Provider Modes (BYOK only)

| Mode | Flag | API Key | Cost |
|------|------|---------|------|
| Codex | `--Codex` | ANTHROPIC_API_KEY | Paid directly to Anthropic |
| OpenAI | `--openai` | OPENAI_API_KEY | Paid directly to OpenAI |

No flag → auto-detect: ANTHROPIC_API_KEY, then OPENAI_API_KEY, else exit with setup instructions. `clausi docs generate` also runs fully locally now (`core/docs_generator.py`, via `AIProvider.generate_text`) — same BYOK model as `scan`.

## Hard rule — always use the emoji helper (Windows compatibility)

```python
from clausi.utils.emoji import get as emoji
console.print(f"{emoji('checkmark')} Success")   # never hardcode ✓/emoji literals
```

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...     # For --Codex
OPENAI_API_KEY=sk-...            # For --openai
```

## Common Tasks

| Task | How |
|------|-----|
| Add new CLI flag | Add `@click.option()` in `cli.py` |
| Add provider | Update `core/ai_provider.py` + detection + config (see `.Codex/rules/providers.md`) |
| Test locally | `export ANTHROPIC_API_KEY=... && clausi scan tests/fixtures -r EU-AIA` |
| Build package | `python -m build` |

Testing + packaging commands: `.Codex/rules/testing.md` (auto-loads when touching `tests/` or build config), or `pytest tests/` directly.

## Keeping This File Updated

Update the matching section when adding commands, modules, flags, or env vars. Keep it a quick reference; deep detail goes in `.Codex/rules/` or code.

---

## Worker session role (clausi-ceo MCP)

You are the **cli** worker for Clausi (PyPI `clausi` tool; free, local, BYOK — no backend dependency in the scan path as of 2026-08-20). Don't edit `clausi/` or `clausi-frontend/` — those have their own workers. You report to the CEO session at the repo root; Eric is the founder — route through the CEO.

Loop: hooks auto-surface directives (act on them first, `acknowledge_directive(id, note)` each); backlog = `list_priorities()` → `start_priority(id)` → build → `verify` GREEN → `complete_priority(id, note-with-verify-keywords)`. A bare `tick` = watchdog wake — reply "ok".

Full protocol (directive verbs, hook mechanics, CEO comms): `/mnt/c/Users/Eric/dev/systems/mcp/PATTERN.md`.
