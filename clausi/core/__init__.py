"""Core business logic."""

from clausi.core.scanner import scan_directory, filter_ignored_files
from clausi.core.payment import check_payment_required, handle_scan_response
from clausi.core.clause_selector import (
    select_clauses_interactive,
    get_preset_clauses,
    display_clause_scope_summary,
)

__all__ = [
    "scan_directory",
    "filter_ignored_files",
    "check_payment_required",
    "handle_scan_response",
    "select_clauses_interactive",
    "get_preset_clauses",
    "display_clause_scope_summary",
]
