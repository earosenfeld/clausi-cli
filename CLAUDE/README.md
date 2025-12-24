# Clausi CLI - AI Developer Documentation

> **Purpose:** Documentation hub for AI assistants working on Clausi CLI
>
> **Last Updated:** 2025-12-08
> **CLI Version:** 1.0.0

---

## 📚 Documentation Files

This directory contains **4 essential files** for AI-assisted development:

### 1. **[CLAUDE.md](CLAUDE.md)** - Main Developer Guide ⭐ START HERE

**Comprehensive technical guide for AI developers (~1,950 lines)**

**When to use:** Any time you're working on CLI development

**Contents:**
- **Part 1: Understanding the System**
  - What is Clausi CLI
  - Architecture overview
  - Directory structure
  - Key concepts (AI providers, interactive mode, custom regulations, payment flow)

- **Part 2: Key Components**
  - `cli.py` - Main orchestration
  - `payment.py` - Payment & API communication
  - `interactive.py` - Interactive mode
  - `scanner.py` - File discovery
  - `config.py` - Configuration management
  - `regulations.py` - Custom regulations

- **Part 3: Development Guide**
  - Common tasks (add AI provider, add CLI command, modify interactive mode)
  - Code patterns to follow
  - Testing guide
  - Packaging & distribution

- **Part 4: Reference**
  - Quick function reference (table with file:line numbers)
  - Important patterns
  - Gotchas & pitfalls
  - Recent changes

**Read this first for any development task.**

---

### 2. **[PRICING_STRATEGY.md](PRICING_STRATEGY.md)** - Business Pricing

**Business model and monetization strategy (~600 lines)**

**When to use:** Working on pricing, payment flow, or business decisions

**Contents:**
- Three business models (Clausi AI, Claude BYOK, OpenAI BYOK)
- Credit system and pricing tiers
- Payment flow (trial system, Stripe integration)
- Cost analysis (reveals current pricing is unsustainable!)
- Future considerations (subscriptions, enterprise, freemium)
- Recommendations and metrics to track

**Important finding:** Current Clausi AI pricing loses money on most scans. See recommendations section for fixes.

---

### 3. **[TESTING.md](TESTING.md)** - Testing Guide

**How to run and write tests**

**When to use:** Running tests or adding new tests

**Contents:**
- Test structure and organization
- Running automated tests (`pytest`)
- Manual testing checklist
- Watch mode for rapid iteration
- Test coverage details

---

### 4. **[README.md](README.md)** - This File

**Navigation and index for CLAUDE/ folder**

---

## 🚀 Quick Start for AI Developers

**New to this project?**

1. **Read CLAUDE.md** - Complete understanding of the system
2. **Check PRICING_STRATEGY.md** - If working on payment/pricing
3. **Use TESTING.md** - When running/writing tests

**Common tasks:**

| Task | File | Section |
|------|------|---------|
| Add new AI provider | CLAUDE.md | Part 3: Task 1 |
| Add new CLI command | CLAUDE.md | Part 3: Task 2 |
| Modify interactive mode | CLAUDE.md | Part 3: Task 3 |
| Understand payment flow | CLAUDE.md | Part 2: payment.py |
| Fix pricing issues | PRICING_STRATEGY.md | Cost Analysis |
| Run tests | TESTING.md | Running Tests |

---

## 📋 File Summary

```
CLAUDE/
├── CLAUDE.md              # Main developer guide (1,950 lines)
├── PRICING_STRATEGY.md    # Business pricing (600 lines)
├── TESTING.md             # Testing guide (150 lines)
└── README.md              # This file
```

**Total:** 4 files, ~2,700 lines of focused documentation

---

## 🎯 Philosophy

**Keep it simple:**
- ✅ ONE comprehensive file (CLAUDE.md) for technical development
- ✅ ONE file for business/pricing (PRICING_STRATEGY.md)
- ✅ ONE file for testing (TESTING.md)
- ✅ No redundancy, no outdated docs

**All AI developer docs in one place:**
- No need to search through 15+ files
- No confusion about which file to read
- Always up-to-date and complete

---

## 📞 Support

**Questions about:**
- **Technical development** → CLAUDE.md
- **Payment/pricing** → PRICING_STRATEGY.md
- **Testing** → TESTING.md

**Repository:** https://github.com/clausi/clausi-cli
**Documentation:** https://docs.clausi.ai

---

**Last Updated:** 2025-12-08
**Maintainer:** Clausi Development Team
