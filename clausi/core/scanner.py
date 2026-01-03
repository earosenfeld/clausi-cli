"""File scanning and filtering logic."""

import os
from pathlib import Path
from typing import List, Dict, Optional, Any

try:
    import pathspec
except ImportError:
    pathspec = None

from clausi.utils.console import console


def scan_directory(path: str) -> List[Dict[str, str]]:
    """Scan directory for files to analyze, robustly excluding common junk folders/files and directories."""
    files_to_analyze = []
    path = Path(path)

    # File extensions to analyze
    extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.h', '.hpp', '.c', '.cs', '.go', '.rs', '.swift'}

    # Directories to exclude
    EXCLUDE_DIRS = {"venv", ".git", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
    # File patterns to exclude
    EXCLUDE_FILES = {".DS_Store", "*.egg-info", "*.pyc", "*.pyo"}

    for root, dirs, files in os.walk(path):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            file_path = Path(root) / file
            # Exclude files by name or pattern
            if file in EXCLUDE_FILES or any(file_path.match(pattern) for pattern in EXCLUDE_FILES):
                continue
            if file_path.suffix in extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    files_to_analyze.append({
                        "path": str(file_path.relative_to(path)),
                        "content": content,
                        "type": file_path.suffix[1:],  # Remove the dot
                        "size": os.path.getsize(file_path)
                    })
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not read {file_path}: {e}[/yellow]")
    return files_to_analyze


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


def filter_ignored_files(files: List[Dict[str, str]], project_path: str, ignore_patterns: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Filter out files that match ignore patterns."""
    if not files:
        return files

    # Find .clausiignore file
    clausiignore_path = find_clausiignore_file(project_path)
    ignore_spec = None

    if clausiignore_path:
        ignore_spec = parse_clausiignore_file(clausiignore_path)
        if ignore_spec:
            console.print(f"[green]Using .clausiignore file: {clausiignore_path}[/green]")

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
        return files

    project_path_obj = Path(project_path).resolve()
    filtered_files = []

    for file_info in files:
        file_path = Path(file_info["path"])
        full_path = project_path_obj / file_path

        # Check if file should be ignored
        should_ignore = False

        if ignore_spec and ignore_spec.match_file(str(file_path)):
            should_ignore = True
            console.print(f"[dim]Ignoring {file_path} (matches .clausiignore)[/dim]")

        if cmd_ignore_spec and cmd_ignore_spec.match_file(str(file_path)):
            should_ignore = True
            console.print(f"[dim]Ignoring {file_path} (matches command-line pattern)[/dim]")

        if not should_ignore:
            filtered_files.append(file_info)

    ignored_count = len(files) - len(filtered_files)
    if ignored_count > 0:
        console.print(f"[green]Ignored {ignored_count} files based on .clausiignore patterns[/green]")

    return filtered_files
