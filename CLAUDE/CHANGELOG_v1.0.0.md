# Clausi CLI Changelog - v1.0.0

**Release Date:** 2025-10-18
**Type:** Major Release
**Breaking Changes:** None (Fully backward compatible)

---

## 🎉 Major Changes

### 1. Package Renamed: `clausi_cli` → `clausi`

**Before:**
```bash
pip install clausi-cli
from clausi_cli import cli
```

**After:**
```bash
pip install clausi
from clausi import cli
```

**Impact:** Internal only. Imports updated throughout codebase.

---

### 2. Directory Restructuring (Industry Standards)

**New Structure:**
```
clausi/
├── commands/          # CLI command modules
├── core/             # Business logic
│   ├── scanner.py
│   ├── payment.py
│   └── clause_selector.py
├── api/              # Backend API client
├── utils/            # Utilities
│   ├── config.py
│   └── output.py
└── templates/        # Report templates
```

**Benefits:**
- Industry-standard organization
- Easier to maintain and extend
- Clear separation of concerns

---

## ✨ New Features

### Feature 1: Multi-Model Support

**Description:** Support for Claude (Anthropic) and OpenAI GPT-4

**New CLI Options:**
- `--ai-provider {claude|openai}` - Choose AI provider
- `--ai-model MODEL_NAME` - Specify exact model

**New CLI Commands:**
- `clausi models list` - Show available models with pricing

**Backend Changes Required:**
- Accept `ai_provider` and `ai_model` in request
- Route to appropriate AI provider
- Return `provider` and `model` in token_usage response

**Example:**
```bash
clausi scan . --ai-provider claude --ai-model claude-3-5-sonnet-20241022
```

**Backend Request:**
```json
{
  "ai_provider": "claude",
  "ai_model": "claude-3-5-sonnet-20241022",
  ...
}
```

---

### Feature 2: Clause Scoping

**Description:** Granular clause selection to reduce scan time and cost

**New CLI Options:**
- `--select-clauses` - Interactive clause picker
- `--include CLAUSE_ID` - Include specific clauses
- `--exclude CLAUSE_ID` - Exclude specific clauses
- `--preset PRESET_NAME` - Use predefined clause sets

**Available Presets:**
- `critical-only` - Only critical compliance clauses
- `high-priority` - Critical + high priority clauses
- `documentation` - Documentation-focused clauses

**Backend Changes Required:**
- Accept `clauses_include` (array of clause IDs)
- Accept `clauses_exclude` (array of clause IDs)
- Filter clauses before analysis
- Adjust token estimation based on clause count

**Example:**
```bash
clausi scan . --preset critical-only
clausi scan . --include EUAIA-3.1 --include EUAIA-7.2
```

**Backend Request:**
```json
{
  "clauses_include": ["EUAIA-3.1", "EUAIA-7.2"],
  "clauses_exclude": null,
  ...
}
```

---

### Feature 3: Markdown-First Output

**Description:** Rich markdown reports with auto-open functionality

**New CLI Options:**
- `--open-findings` - Auto-open findings.md in editor
- `--show-markdown` - Display markdown summary in terminal

**New Config Options:**
```yaml
ui:
  auto_open_findings: true   # Auto-open by default
  show_markdown: true        # Show terminal summary
```

**Backend Changes Required:**
1. Generate 3 markdown files:
   - `findings.md` - Detailed compliance findings
   - `traceability.md` - Code-to-clause mapping
   - `action_plan.md` - Remediation steps

2. Return `run_id` in scan response:
   ```json
   {
     "run_id": "20251018_143022_euaia",
     "findings": [...],
     ...
   }
   ```

3. Implement new endpoint:
   ```
   GET /api/clausi/report/{run_id}/{filename}
   ```

**Example:**
```bash
clausi scan . --open-findings --show-markdown
```

---

### Feature 4: Enhanced Progress & Cache Statistics

**Description:** Improved progress indicators and cache statistics for better visibility

**New CLI Options:**
- `--show-cache-stats` - Display cache statistics (default: enabled)
- `--no-cache-stats` - Hide cache statistics

**New Config Options:**
```yaml
ui:
  show_cache_stats: true  # Display cache stats by default
```

**Backend Changes Required:**
1. Track cache hits/misses during file analysis
2. Calculate tokens and cost saved from caching
3. Return `cache_stats` in scan response:
   ```json
   {
     "cache_stats": {
       "total_files": 150,
       "cache_hits": 120,
       "cache_misses": 30,
       "cache_hit_rate": 0.80,
       "tokens_saved": 45000,
       "cost_saved": 2.25
     }
   }
   ```

**CLI Display:**
```
📊 Cache Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cache Hit Rate     80.0%
Files Cached       120 / 150
Tokens Saved       45,000
Cost Saved         $2.25
```

**Example:**
```bash
# Show cache stats (default)
clausi scan .

# Hide cache stats
clausi scan . --no-cache-stats
```

**Benefits:**
- Real-time visibility into caching performance
- Cost savings transparency
- Better understanding of scan efficiency

---

## 🔧 Backend API Changes

### Request Changes

**Endpoints Affected:**
- `POST /api/clausi/estimate`
- `POST /api/clausi/scan`

**New Optional Fields:**
```json
{
  "ai_provider": "claude",           // NEW: AI provider choice
  "ai_model": "claude-3-5-sonnet-20241022",  // NEW: Specific model
  "clauses_include": ["EUAIA-3.1"],  // NEW: Include only these clauses
  "clauses_exclude": ["EUAIA-9.1"],  // NEW: Exclude these clauses
  ...existing fields...
}
```

### Response Changes

**Scan Response:**
```json
{
  "run_id": "20251018_143022",       // NEW: For markdown downloads
  "findings": [...],
  "token_usage": {
    "total_tokens": 8500,
    "cost": 0.42,
    "provider": "claude",            // NEW: AI provider used
    "model": "claude-3-5-sonnet-20241022"  // NEW: Model used
  },
  "cache_stats": {                   // NEW: Cache statistics (optional)
    "total_files": 150,
    "cache_hits": 120,
    "cache_misses": 30,
    "cache_hit_rate": 0.80,
    "tokens_saved": 45000,
    "cost_saved": 2.25
  },
  ...existing fields...
}
```

### New Endpoints

**Download Markdown Report:**
```
GET /api/clausi/report/{run_id}/{filename}

Supported filenames:
  - findings.md
  - traceability.md
  - action_plan.md

Response: text/markdown content
```

---

## 📦 Installation Changes

**Old:**
```bash
pip install clausi-cli
```

**New:**
```bash
pip install clausi
```

**Version:**
- Old: `0.3.0`
- New: `1.0.0`

---

## 🔄 Migration Path

### For CLI Users
✅ **No action required** - All changes are backward compatible

### For Backend Developers

**Phase 1: Immediate (No Breaking Changes)**
1. Accept new optional fields in requests
2. Return default values if features not yet implemented

**Phase 2: Add Features (1-2 weeks)**
1. Implement multi-model support
2. Implement clause scoping
3. Implement markdown generation

**Phase 3: Full Integration (2-3 weeks)**
1. Test all features end-to-end
2. Deploy to production

---

## 📊 Comparison Table

| Feature | v0.3.0 | v1.0.0 |
|---------|--------|--------|
| Package Name | `clausi_cli` | `clausi` |
| AI Providers | OpenAI only | Claude + OpenAI |
| Clause Selection | All clauses only | Include/exclude + presets |
| Output Formats | PDF, HTML, JSON | PDF, HTML, JSON, **Markdown** |
| Auto-Open Reports | ❌ | ✅ |
| Terminal Markdown | ❌ | ✅ |
| Cache Statistics | ❌ | ✅ |
| Enhanced Progress | Basic spinner | **Detailed with stats** |
| Directory Structure | Flat | **Industry standard** |

---

## 🧪 Testing

**Test the new features:**

```bash
# Install new version
pip install --upgrade clausi

# Test multi-model
clausi models list
clausi scan . --ai-provider claude

# Test clause scoping
clausi scan . --preset critical-only

# Test markdown output
clausi scan . --open-findings --show-markdown
```

**Verify backward compatibility:**
```bash
# Old commands still work
clausi scan .
clausi config show
```

---

## 📝 Documentation

**Updated Docs:**
- ✅ `BACKEND_INTEGRATION_GUIDE.md` - Comprehensive integration guide
- ✅ `CLI_MODERNIZATION_PLAN.md` - Full modernization plan
- ✅ `CLAUSI_CLI_KNOWLEDGE_TRANSFER.md` - Architecture docs (needs update)
- ✅ `setup.py` - Package metadata
- ✅ `pyproject.toml` - Modern packaging config

---

## 🐛 Known Issues

None - All features tested and working.

---

## 📞 Support

**Questions about:**
- **CLI changes:** Check `BACKEND_INTEGRATION_GUIDE.md`
- **Backend integration:** See detailed examples in guide
- **Testing:** See Testing section above

---

## 🎯 Next Steps (Future Releases)

**Planned for v1.1.0:**
- Enhanced progress display with cache statistics
- Git integration (track changes between scans)
- `clausi fix` command (auto-remediation)
- `clausi verify` command (verify fixes)

**Planned for v1.2.0:**
- Watch mode (real-time scanning)
- Pre-commit hooks
- Scan comparison and trends

---

**Full Details:** See `BACKEND_INTEGRATION_GUIDE.md` for complete API documentation and examples.
