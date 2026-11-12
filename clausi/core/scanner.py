"""File scanning and filtering logic."""

import contextlib
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import pathspec
except ImportError:
    pathspec = None

from clausi.utils.console import console


# File extensions Clausi can currently analyze. Anything else is reported as
# skipped rather than silently dropped - a reader must be able to tell the
# difference between "inspected and clean" and "never looked at".
SUPPORTED_EXTENSIONS = {
    '.py', '.js', '.ts', '.java', '.cpp', '.h', '.hpp', '.c', '.cs', '.go',
    '.rs', '.swift',
}

# Directories that hold dependencies, build output, or tool caches rather than
# the project's own source. Scanning them bills the user to audit third-party
# code and attributes other people's findings to their project.
#
# Every exclusion here is reported in the scan manifest, so a user who keeps
# real source in one of these can see that it was skipped.
EXCLUDE_DIRS = {
    # Version control and editors
    ".git", ".hg", ".svn", ".idea", ".vscode",
    # Python environments, caches, and packaging
    "venv", ".venv", "site-packages", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".tox", ".nox", ".eggs", "htmlcov",
    # JavaScript dependencies and framework build output
    "node_modules", "bower_components", ".next", ".nuxt", ".svelte-kit",
    # Vendored dependencies (Go, PHP/Composer)
    "vendor",
    # Build output
    "dist", "build", "target", ".gradle", ".terraform",
}
# Clausi's own control files are not project code; listing them as "unsupported"
# is noise in the coverage manifest.
EXCLUDE_FILES = {".DS_Store", "*.egg-info", "*.pyc", "*.pyo", ".clausiignore"}

# Cap on how many example paths to keep per skip reason, so the manifest stays
# readable on a large repository while still being concrete.
MAX_MANIFEST_EXAMPLES = 10


def scan_directory_with_coverage(
    path: str, exclude_paths: Optional[Iterable[Path]] = None,
    ignore_matcher=None,
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """Discover analyzable files and record everything that was not analyzed.

    Returns (files, coverage). Coverage exists so a scan can state its own
    limits: silently ignoring a file class makes a clean report indistinguishable
    from an unexamined one.
    """
    files_to_analyze: List[Dict[str, str]] = []
    unsupported: Dict[str, int] = {}
    unsupported_examples: Dict[str, List[str]] = {}
    excluded_dirs: Dict[str, int] = {}
    unreadable: List[Dict[str, str]] = []
    ignored: List[Dict[str, str]] = []
    root_path = Path(path)

    # Clausi's own output and state directories. A repeat scan would otherwise
    # discover the reports from the previous run and list our own PDF and CSV
    # as "unsupported files" in the coverage manifest of every scan after the
    # first. Passed in rather than hardcoded because the output directory is
    # configurable and can sit anywhere.
    skip_roots = set()
    for candidate in (exclude_paths or []):
        with contextlib.suppress(OSError):
            skip_roots.add(Path(candidate).resolve())

    def _is_skipped(directory: Path) -> bool:
        if not skip_roots:
            return False
        try:
            resolved = directory.resolve()
        except OSError:
            return False
        return any(
            resolved == skip or skip in resolved.parents for skip in skip_roots
        )

    for root, dirs, files in os.walk(root_path):
        pruned = [d for d in dirs if d in EXCLUDE_DIRS]
        for d in pruned:
            excluded_dirs[d] = excluded_dirs.get(d, 0) + 1
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        own_output = [d for d in dirs if _is_skipped(Path(root) / d)]
        for d in own_output:
            excluded_dirs[f"{d} (Clausi output)"] = (
                excluded_dirs.get(f"{d} (Clausi output)", 0) + 1
            )
        dirs[:] = [d for d in dirs if d not in own_output]

        for file in files:
            file_path = Path(root) / file
            if file in EXCLUDE_FILES or any(file_path.match(pattern) for pattern in EXCLUDE_FILES):
                continue

            try:
                rel_path = str(file_path.relative_to(root_path))
            except ValueError:
                rel_path = str(file_path)

            if file_path.suffix not in SUPPORTED_EXTENSIONS:
                ext = file_path.suffix or "(no extension)"
                unsupported[ext] = unsupported.get(ext, 0) + 1
                examples = unsupported_examples.setdefault(ext, [])
                if len(examples) < MAX_MANIFEST_EXAMPLES:
                    examples.append(rel_path)
                continue

            # Checked before the read, not after.
            rule = ignore_matcher(rel_path) if ignore_matcher else None
            if rule:
                ignored.append({"path": rel_path, "rule": rule})
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                files_to_analyze.append({
                    "path": rel_path,
                    "content": content,
                    "type": file_path.suffix[1:],
                    "size": os.path.getsize(file_path)
                })
            except Exception as e:
                unreadable.append({"path": rel_path, "reason": str(e)})
                console.print(f"[yellow]Warning: Could not read {file_path}: {e}[/yellow]")

    coverage = {
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "discovered": len(files_to_analyze),
        "skipped_unsupported_extension": dict(sorted(unsupported.items(), key=lambda kv: -kv[1])),
        "skipped_unsupported_examples": unsupported_examples,
        "skipped_excluded_directories": dict(sorted(excluded_dirs.items(), key=lambda kv: -kv[1])),
        "unreadable": unreadable,
        "ignored": ignored,
    }
    return files_to_analyze, coverage


def scan_directory(path: str) -> List[Dict[str, str]]:
    """Scan directory for files to analyze, excluding common junk folders/files."""
    files, _ = scan_directory_with_coverage(path)
    return files


def find_clausiignore_file(project_path: str) -> Optional[Path]:
    """Find .clausiignore file by searching upward from project root."""
    if pathspec is None:
        console.print("[yellow]Warning: pathspec library not available. .clausiignore functionality disabled.[/yellow]")
        return None

    current_path = Path(project_path).resolve()

    # Search upward from project root
    while current_path != current_path.parent:
        clausiignore_path = current_path / ".clausiignore"
        if clausiignore_path.exists():
            return clausiignore_path
        current_path = current_path.parent

    return None


def parse_clausiignore_file(clausiignore_path: Path) -> Optional[Any]:
    """Parse .clausiignore file and return a PathSpec object."""
    if pathspec is None:
        return None

    try:
        with open(clausiignore_path, 'r', encoding='utf-8') as f:
            patterns = f.readlines()

        # Remove empty lines and comments
        patterns = [line.strip() for line in patterns if line.strip() and not line.startswith('#')]

        if not patterns:
            return None

        return pathspec.PathSpec.from_lines('gitwildmatch', patterns)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not parse .clausiignore file: {e}[/yellow]")
        return None


def build_ignore_matcher(project_path: str,
                          ignore_patterns: Optional[List[str]] = None):
    """Return a callable(rel_path) -> rule name or None.

    Pulled out of filter_ignored_files_with_manifest so the walk can consult
    the ignore rules *before* reading a file. Reading first and discarding
    after meant a repo whose .clausiignore excludes vendored or generated
    trees still paid the full read for every one of those files, and held them
    all in memory at once.
    """
    ignore_spec = None
    clausiignore_path = find_clausiignore_file(project_path)
    if clausiignore_path:
        ignore_spec = parse_clausiignore_file(clausiignore_path)
        if ignore_spec:
            console.print(f"[green]Using .clausiignore:[/green] {clausiignore_path}", highlight=False)

    cmd_ignore_spec = None
    if ignore_patterns and pathspec:
        try:
            cmd_ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns)
            console.print(
                f"[green]Using command-line ignore patterns: {', '.join(ignore_patterns)}[/green]"
            )
        except Exception as e:  # noqa: BLE001 - a bad pattern must not end the scan
            console.print(f"[yellow]Warning: Could not parse command-line ignore patterns: {e}[/yellow]")

    if not ignore_spec and not cmd_ignore_spec:
        return None

    def _match(rel_path: str) -> Optional[str]:
        if ignore_spec and ignore_spec.match_file(rel_path):
            return ".clausiignore"
        if cmd_ignore_spec and cmd_ignore_spec.match_file(rel_path):
            return "--ignore pattern"
        return None

    return _match


def filter_ignored_files_with_manifest(
    files: List[Dict[str, str]], project_path: str,
    ignore_patterns: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Filter ignored files, also returning what was ignored and by which rule."""
    ignored_manifest: List[Dict[str, str]] = []
    if not files:
        return files, ignored_manifest

    # Find .clausiignore file
    clausiignore_path = find_clausiignore_file(project_path)
    ignore_spec = None

    if clausiignore_path:
        ignore_spec = parse_clausiignore_file(clausiignore_path)
        if ignore_spec:
            console.print(f"[green]Using .clausiignore:[/green] {clausiignore_path}", highlight=False)

    # Parse command-line ignore patterns
    cmd_ignore_spec = None
    if ignore_patterns:
        try:
            if pathspec:
                cmd_ignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', ignore_patterns)
                console.print(f"[green]Using command-line ignore patterns: {', '.join(ignore_patterns)}[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not parse command-line ignore patterns: {e}[/yellow]")

    if not ignore_spec and not cmd_ignore_spec:
        return files, ignored_manifest

    project_path_obj = Path(project_path).resolve()
    filtered_files = []

    for file_info in files:
        file_path = Path(file_info["path"])
        full_path = project_path_obj / file_path

        # Check if file should be ignored
        should_ignore = False

        if ignore_spec and ignore_spec.match_file(str(file_path)):
            should_ignore = True
            ignored_manifest.append({"path": str(file_path), "rule": ".clausiignore"})
            console.print(f"[dim]Ignoring {file_path} (matches .clausiignore)[/dim]")

        if cmd_ignore_spec and cmd_ignore_spec.match_file(str(file_path)):
            should_ignore = True
            ignored_manifest.append({"path": str(file_path), "rule": "--ignore pattern"})
            console.print(f"[dim]Ignoring {file_path} (matches command-line pattern)[/dim]")

        if not should_ignore:
            filtered_files.append(file_info)

    ignored_count = len(files) - len(filtered_files)
    if ignored_count > 0:
        console.print(f"[green]Ignored {ignored_count} files based on .clausiignore patterns[/green]")

    return filtered_files, ignored_manifest


def filter_ignored_files(files: List[Dict[str, str]], project_path: str,
                         ignore_patterns: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Filter out files that match ignore patterns."""
    filtered, _ = filter_ignored_files_with_manifest(files, project_path, ignore_patterns)
    return filtered
