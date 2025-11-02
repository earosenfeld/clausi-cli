# Clausi CLI Documentation

This directory contains documentation for the Clausi CLI modernization and backend integration.

---

## 📚 **Active Documentation** (v1.0.0)

### For Claude Developers

**[CLAUDE.md](CLAUDE.md)** (Development Guide for Claude Instances)
- 🎯 Core development philosophy (keep it simple!)
- 📁 Repository structure and folder organization
- 📝 Naming conventions (files, classes, functions)
- 🏗️ Architecture patterns and layer separation
- 🚫 What NOT to do (avoid common mistakes)
- 🔧 Common patterns used in this repo
- **Use this** when developing features or fixing bugs

### For End Users

**[USER_GUIDE.md](USER_GUIDE.md)** (Complete User Guide)
- 📖 Step-by-step installation and setup
- 🔍 Your first scan walkthrough
- 📋 Understanding compliance results
- ⚡ Advanced features (clause scoping, multi-model)
- 💼 Common workflows and use cases
- 🐛 Troubleshooting and tips
- **Use this** for learning how to use the CLI

### For Developers & Testers

**[TESTING.md](TESTING.md)** (Testing Guide)
- 🧪 Automated test system setup
- 🚀 Quick start commands
- 🔄 Watch mode for rapid iteration
- 📊 Test coverage details
- **Use this** for running and writing tests

**[TEST_RESULTS.md](TEST_RESULTS.md)** (Latest Test Results)
- ✅ Current test status
- 🐛 Known issues and fixes
- 📝 Test output examples
- **Use this** to see what's been validated

### For Backend Developers

**[BACKEND_README.md](BACKEND_README.md)** ⭐ **START HERE - Backend Team Hub**
- 🎯 Quick navigation to all backend docs
- 📚 Recommended reading order (Day 1, Day 2, Ongoing)
- 🧪 5-minute quick start guide
- 💡 Understanding the user journey
- 🔍 Common questions answered
- **Use this** as your central hub for all backend resources

**[USER_GUIDE.md](USER_GUIDE.md)** (User Experience)
- How customers actually use the CLI
- Step-by-step installation and setup
- Running scans, understanding results
- All commands and workflows
- **Use this** to understand the user experience

**[BACKEND_CLI_TESTING_GUIDE.md](BACKEND_CLI_TESTING_GUIDE.md)** (Integration Testing)
- How to install and run the CLI locally
- Testing BYOK vs Credits payment modes
- Sample curl commands for each endpoint
- Expected headers and request/response formats
- **Use this** to test CLI ↔ Backend integration

**[BACKEND_INTEGRATION_GUIDE.md](BACKEND_INTEGRATION_GUIDE.md)** (API Contract)
- Complete API specifications
- Request/response schemas
- Implementation examples
- Migration guide
- **Use this** for implementing backend changes

**[CHANGELOG_v1.0.0.md](CHANGELOG_v1.0.0.md)** (Quick Reference)
- Quick overview of what changed in v1.0.0
- Feature summaries with examples
- Comparison table (v0.3.0 vs v1.0.0)
- Testing guide
- **Use this** for a quick summary of changes

### For CLI Development

**[CLI_MODERNIZATION_PLAN.md](CLI_MODERNIZATION_PLAN.md)** (Roadmap)
- Complete 12-week modernization plan
- **Phase 1:** ✅ COMPLETE (v1.0.0 released)
- **Phase 2:** Auto-Fix Experience (upcoming)
- **Phase 3:** Developer Tools (upcoming)
- Detailed task breakdown with code examples
- **Use this** to understand the full vision and upcoming features

**[TUI_IMPLEMENTATION.md](TUI_IMPLEMENTATION.md)** (Interactive Terminal UI)
- Terminal User Interface (TUI) implementation details
- Interactive configuration editor
- Module structure and design decisions
- Usage examples and keyboard shortcuts
- **Use this** to understand the optional TUI mode

**[CLAUSI_CLI_KNOWLEDGE_TRANSFER.md](CLAUSI_CLI_KNOWLEDGE_TRANSFER.md)** (Architecture)
- Architecture overview and design decisions
- Code structure and organization
- Component interactions
- **Note:** Updated for v1.0.0 (package rename, new structure)
- **Use this** to understand how the CLI works internally

---

## 📦 **v1.0.0 Release Summary**

### New Features

1. **Multi-Model Support**
   - Claude (Anthropic) as default provider
   - OpenAI GPT-4 support
   - `clausi models list` command
   - `--ai-provider` and `--ai-model` flags

2. **Clause Scoping**
   - Interactive clause selection
   - Predefined presets (critical-only, high-priority, documentation)
   - `--include`, `--exclude`, `--preset` flags
   - 60-80% cost reduction potential

3. **Markdown-First Output**
   - Auto-generated `findings.md`, `traceability.md`, `action_plan.md`
   - Auto-open in default editor (`--open-findings`)
   - Terminal markdown display (`--show-markdown`)
   - Rich formatting with tables and syntax highlighting

4. **Enhanced Progress & Cache Statistics**
   - Detailed progress bars with time estimates
   - Cache hit/miss tracking
   - Cost savings transparency
   - `--show-cache-stats` / `--no-cache-stats` flags

### Backend Integration Required

See `BACKEND_INTEGRATION_GUIDE.md` for complete details.

**New Request Fields (all optional):**
- `ai_provider` - "claude" or "openai"
- `ai_model` - Specific model name
- `clauses_include` - Array of clause IDs to scan
- `clauses_exclude` - Array of clause IDs to skip

**New Response Fields:**
- `run_id` - For markdown file downloads
- `cache_stats` - Cache hit/miss statistics
- `token_usage.provider` - AI provider used
- `token_usage.model` - Model used

**New Endpoint:**
- `GET /api/clausi/report/{run_id}/{filename}` - Download markdown reports

---

## 📁 **Archive**

The `archive/` folder contains outdated documentation:

- `BACKEND_API_EXAMPLES.md` - Code examples (now integrated into BACKEND_INTEGRATION_GUIDE.md)
- `PAYMENT_INTEGRATION_SUMMARY.md` - Old payment flow docs (outdated file references)

---

## 🚀 **Quick Start for Backend Developers**

1. **Read:** `CHANGELOG_v1.0.0.md` (5 min)
2. **Implement:** Follow `BACKEND_INTEGRATION_GUIDE.md` (2-4 hours)
3. **Test:** Use CLI to verify integration

### Minimal Backend Changes

All new fields are **optional** and **backward compatible**:

```python
@app.post("/api/clausi/scan")
def scan(request):
    data = request.json

    # NEW: Get optional fields with defaults
    ai_provider = data.get("ai_provider", "openai")
    ai_model = data.get("ai_model", "gpt-4")
    clauses_include = data.get("clauses_include", None)
    clauses_exclude = data.get("clauses_exclude", None)

    # Your existing logic continues to work!
    result = perform_scan(data)

    # NEW: Add optional response fields
    return {
        "run_id": generate_run_id(),  # Optional
        "findings": result["findings"],
        "token_usage": {
            "total_tokens": result["tokens"],
            "cost": result["cost"],
            "provider": ai_provider,  # NEW
            "model": ai_model         # NEW
        },
        "cache_stats": {              # Optional
            "total_files": 150,
            "cache_hits": 120,
            "cache_misses": 30,
            "cache_hit_rate": 0.80,
            "tokens_saved": 45000,
            "cost_saved": 2.25
        }
    }
```

---

## 📞 **Support**

Questions? Check the documentation in this order:

1. Quick questions → `CHANGELOG_v1.0.0.md`
2. Backend integration → `BACKEND_INTEGRATION_GUIDE.md`
3. Feature planning → `CLI_MODERNIZATION_PLAN.md`
4. Architecture deep-dive → `CLAUSI_CLI_KNOWLEDGE_TRANSFER.md`

---

**Last Updated:** 2025-10-18
**CLI Version:** 1.0.0
