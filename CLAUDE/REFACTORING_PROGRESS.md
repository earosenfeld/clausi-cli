# Clausi CLI Refactoring Progress

## Summary

| Phase | Status | Priority |
|-------|--------|----------|
| Release Prep | ✅ Complete | Critical |
| Phase 1: Cleanup | ✅ Complete | High |
| Phase 2: HTTP Helpers | ⏳ Pending | Medium |
| Phase 3: Split Functions | ⏳ Pending | Medium |
| Phase 4: Logging | ⏳ Pending | Low |
| Phase 5: Exceptions | ⏳ Pending | Low |
| Phase 6: Constants | ⏳ Pending | Low |
| Phase 7: Tests | ⏳ Pending | Low |

---

## Release Prep ✅

- [x] Package builds successfully
- [x] Version 1.0.0 set
- [x] Entry point configured
- [x] README included
- [x] LICENSE included

**Ready for PyPI upload!**

---

## Phase 1: Cleanup ✅

- [x] Remove duplicate `get_openai_key()` from cli.py
- [x] Remove unused `rprint` import from cli.py
- [x] Remove deprecated `show_token_status()` from config.py
- [x] Remove test card display from payment.py
- [x] Fix hardcoded emoji to use `emoji()` function
- [x] Add native file explorer dialog (tkinter)

---

## Phase 2: HTTP Helpers ⏳

- [ ] Create `utils/http.py`
  - [ ] `build_api_headers(provider, api_key, token)`
  - [ ] `handle_api_error(response, context)`
- [ ] Rename `openai_key` → `api_key` in payment.py
  - [ ] `handle_scan_response()`
  - [ ] `retry_scan_with_token()`
  - [ ] `make_async_scan_request()`
  - [ ] `make_scan_request()`

---

## Phase 3: Split Functions ⏳

### 3.1 Split `scan()` (577 lines → ~10 functions)
- [ ] Create `core/scan_flow.py`
- [ ] Extract `validate_scan_inputs()`
- [ ] Extract `estimate_scan_cost()`
- [ ] Extract `confirm_scan_with_user()`
- [ ] Extract `execute_scan()`
- [ ] Extract `download_reports()`
- [ ] Extract `display_scan_results()`

### 3.2 Split `payment.py` (435 lines → 3 modules)
- [ ] Create `core/payment_flow.py` (payment UI)
- [ ] Create `core/scan_request.py` (API requests)
- [ ] Create `core/job_polling.py` (async jobs)

---

## Phase 4: Logging ⏳

- [ ] Create `utils/logging.py`
- [ ] Add `--verbose` flag to CLI
- [ ] Replace error `console.print` with `logger.error`
- [ ] Add debug logging for API calls

---

## Phase 5: Exceptions ⏳

- [ ] Create `exceptions.py`
  - [ ] `ClausiError` (base)
  - [ ] `PaymentRequiredError`
  - [ ] `APIError`
  - [ ] `ConfigurationError`
- [ ] Replace bare `except:` with specific exceptions
- [ ] Add proper error context

---

## Phase 6: Constants ⏳

- [ ] Create `constants.py`
  - [ ] `DEFAULT_API_URL`
  - [ ] `DEFAULT_API_TIMEOUT`
  - [ ] `DEFAULT_POLL_INTERVAL`
  - [ ] `DEFAULT_CLAUDE_MODEL`
  - [ ] `DEFAULT_OPENAI_MODEL`
  - [ ] `CACHE_TTL_SECONDS`
- [ ] Add config caching to `config.py`

---

## Phase 7: Tests ⏳

### Failing Tests (9/29)
- [ ] `test_success_response`
- [ ] `test_claude_provider_selection`
- [ ] `test_openai_provider_selection`
- [ ] `test_audit_command`
- [ ] `test_scan_with_preset`
- [ ] `test_scan_with_include`
- [ ] `test_cache_statistics_display`
- [ ] `test_cache_stats_in_scan_response`
- [ ] `test_config_set_ai_provider`

### New Tests Needed
- [ ] Path validation tests
- [ ] Error handling tests
- [ ] Native file dialog tests

---

## Files Changed

| File | Changes |
|------|---------|
| `cli.py` | Removed `rprint`, `get_openai_key` wrapper |
| `utils/config.py` | Removed `show_token_status()` |
| `core/payment.py` | Removed test card, fixed emoji |
| `tui/interactive.py` | Added native file dialog |

---

## Next Steps

1. **Release to PyPI** (no blockers)
2. Continue with Phase 2 (HTTP helpers) after release
3. Prioritize based on user feedback

---

**Last Updated:** 2025-12-24
