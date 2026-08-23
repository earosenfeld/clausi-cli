"""
Clausi Docs Generator

Generates AI-powered documentation for codebases - fully local, BYOK
(same architecture as the compliance scanner: direct Anthropic/OpenAI
calls with the user's own key, no backend involved).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rich.console import Console

from clausi.core.ai_provider import AIProvider, AIProviderError, estimate_tokens

console = Console()

# Default patterns to exclude
DEFAULT_EXCLUDES = [
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/.git/**",
    "**/venv/**",
    "**/.venv/**",
    "**/dist/**",
    "**/build/**",
    "**/clausi/**",  # Exclude Clausi output folder (scans, docs, history)
    "**/*.pyc",
    "**/.env*",
    "**/coverage/**",
    "**/.idea/**",
    "**/.vscode/**",
    "**/*.min.js",
    "**/*.min.css",
    "**/package-lock.json",
    "**/yarn.lock",
    "**/poetry.lock",
]

# File extensions to include for analysis
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".vue", ".svelte"
}

CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"
}

DOC_EXTENSIONS = {
    ".md", ".rst", ".txt"
}

# Max total bytes of file content sent to the AI per doc-gen run.
MAX_CONTEXT_BYTES = 400_000


def strip_markdown_fence(text: str) -> str:
    """Unwrap a whole document that the model wrapped in a ```markdown fence.

    Models occasionally return the entire doc inside one fenced block, which
    renders as a literal code block instead of markdown. Only unwrap when the
    fence encloses the *whole* document - a doc that legitimately opens with a
    code sample must be left alone.
    """
    stripped = text.strip()
    if not stripped.startswith("```") or not stripped.endswith("```"):
        return text

    lines = stripped.split("\n")
    if len(lines) < 2:
        return text

    # The opening fence may carry an info string (```markdown, ```md).
    info = lines[0][3:].strip().lower()
    if info and info not in ("markdown", "md"):
        return text

    body = lines[1:-1]
    # If any inner line closes the fence, the block does not span the document.
    if any(line.strip() == "```" for line in body):
        return text

    return "\n".join(body).strip() + "\n"

SYSTEM_PROMPT = (
    "You are a senior software engineer writing clear, accurate technical "
    "documentation for a codebase. Base everything strictly on the provided "
    "project structure, README, and file excerpts - never invent features, "
    "endpoints, or files that aren't shown. Write in Markdown. Be concise "
    "and skip sections you don't have evidence for rather than padding."
)

DOC_TYPES = {
    "index.md": (
        "Write index.md: a project overview. Include what the project does, "
        "its tech stack (inferred from file extensions/config files), how to "
        "get started (install/run, if inferable), and a short annotated "
        "project structure section."
    ),
    "architecture.md": (
        "Write architecture.md: describe the system design - main modules "
        "and how they relate, data/control flow through the codebase, and "
        "any notable architectural patterns you can see evidence of. If the "
        "codebase is too small/simple for a meaningful architecture doc, say "
        "so briefly instead of inventing structure."
    ),
    "components.md": (
        "Write components.md: a walkthrough of the key files/modules and "
        "their responsibilities, based on the provided file excerpts. Group "
        "related files together. Reference actual file paths."
    ),
    "security.md": (
        "Write security.md: security-relevant observations from the code - "
        "how secrets/credentials are handled, input validation, "
        "authentication/authorization if present, and any other notable "
        "security patterns or gaps you can see evidence of. Do not guess at "
        "things not shown in the provided excerpts."
    ),
}


class DocsGenerator:
    """Generates documentation for a project using the user's own AI key."""

    def __init__(
        self,
        project_path: Path,
        output_dir: Path,
        output_format: str = "md",
        exclude_patterns: List[str] = None,
        include_patterns: List[str] = None,
        provider: str = "claude",
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.project_path = Path(project_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_format = output_format
        self.exclude_patterns = exclude_patterns or []
        self.include_patterns = include_patterns or []
        self.provider = provider
        self.api_key = api_key
        self.model = model

        # Will be populated by scan_project()
        self.files: List[Dict] = []
        self.project_structure: str = ""
        self.readme_content: str = ""
        self.package_info: Dict = {}

    def scan_project(self) -> Tuple[int, int]:
        """
        Scan the project and collect files for analysis.

        Returns:
            Tuple of (file_count, lines_of_code)
        """
        import pathspec

        # Build exclude patterns
        all_excludes = DEFAULT_EXCLUDES + self.exclude_patterns
        exclude_spec = pathspec.PathSpec.from_lines('gitwildmatch', all_excludes)

        # Honor .clausiignore the same way `clausi scan` does. Docs generation
        # sends file contents to the user's AI provider, so a path the user
        # excluded from scanning must not be shipped out here either.
        from clausi.core.scanner import find_clausiignore_file, parse_clausiignore_file

        clausiignore_spec = None
        clausiignore_file = find_clausiignore_file(str(self.project_path))
        if clausiignore_file:
            clausiignore_spec = parse_clausiignore_file(clausiignore_file)
            if clausiignore_spec:
                console.print(f"Using .clausiignore file: {clausiignore_file}")

        # Build include patterns (if specified)
        include_spec = None
        if self.include_patterns:
            include_spec = pathspec.PathSpec.from_lines('gitwildmatch', self.include_patterns)

        # Collect files
        self.files = []
        total_loc = 0

        for file_path in self.project_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Get relative path for pattern matching
            try:
                rel_path = file_path.relative_to(self.project_path)
            except ValueError:
                continue

            rel_path_str = str(rel_path).replace("\\", "/")

            # Check excludes
            if exclude_spec.match_file(rel_path_str):
                continue

            if clausiignore_spec and clausiignore_spec.match_file(rel_path_str):
                continue

            # Check includes (if specified)
            if include_spec and not include_spec.match_file(rel_path_str):
                continue

            # Check file extension
            suffix = file_path.suffix.lower()
            if suffix not in CODE_EXTENSIONS | CONFIG_EXTENSIONS | DOC_EXTENSIONS:
                continue

            # Read file content
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Skip very large files (>50KB)
                if len(content) > 50000:
                    content = content[:50000] + "\n... [TRUNCATED]"

                # Count lines of code
                lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)

                self.files.append({
                    "path": rel_path_str,
                    "content": content,
                    "extension": suffix,
                    "size": len(content),
                    "lines": lines
                })
                total_loc += lines

            except Exception:
                continue

        # Extract README if exists
        for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
            readme_path = self.project_path / readme_name
            if readme_path.exists():
                try:
                    self.readme_content = readme_path.read_text(encoding='utf-8')
                except Exception:
                    pass
                break

        # Extract package info
        self._extract_package_info()

        # Build project structure tree
        self.project_structure = self._build_tree()

        return len(self.files), total_loc

    def _extract_package_info(self):
        """Extract project name and info from package files."""
        # Try package.json
        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text())
                self.package_info = {
                    "name": data.get("name", ""),
                    "description": data.get("description", ""),
                    "version": data.get("version", ""),
                    "type": "node"
                }
                return
            except Exception:
                pass

        # Try pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib
                data = tomllib.loads(pyproject.read_text())
                project = data.get("project", data.get("tool", {}).get("poetry", {}))
                self.package_info = {
                    "name": project.get("name", ""),
                    "description": project.get("description", ""),
                    "version": project.get("version", ""),
                    "type": "python"
                }
                return
            except Exception:
                pass

        # Try setup.py
        setup_py = self.project_path / "setup.py"
        if setup_py.exists():
            self.package_info = {"type": "python"}

        # Default to folder name
        if not self.package_info:
            self.package_info = {
                "name": self.project_path.name,
                "type": "unknown"
            }

    def _build_tree(self, max_depth: int = 3) -> str:
        """Build a directory tree string."""
        lines = []

        def add_dir(path: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return

            # Get items, excluding hidden and common ignored
            items = []
            try:
                for item in sorted(path.iterdir()):
                    name = item.name
                    if name.startswith("."):
                        continue
                    if name in {"node_modules", "__pycache__", "venv", ".venv", "dist", "build"}:
                        continue
                    items.append(item)
            except PermissionError:
                return

            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "

                if item.is_dir():
                    lines.append(f"{prefix}{connector}{item.name}/")
                    extension = "    " if is_last else "│   "
                    add_dir(item, prefix + extension, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{item.name}")

        lines.append(f"{self.project_path.name}/")
        add_dir(self.project_path)

        return "\n".join(lines[:50])  # Limit to 50 lines

    def _build_context(self) -> str:
        """Build the shared project-context blob included in every doc prompt."""
        parts = [
            f"Project name: {self.package_info.get('name', self.project_path.name)}",
            f"Project type: {self.package_info.get('type', 'unknown')}",
        ]
        if self.package_info.get("description"):
            parts.append(f"Description: {self.package_info['description']}")

        parts.append("\nDirectory structure:\n" + self.project_structure)

        if self.readme_content:
            parts.append("\nREADME (excerpt):\n" + self.readme_content[:5000])

        parts.append("\nFile contents:")
        total = 0
        for f in self.files:
            entry = f"\n### {f['path']}\n```\n{f['content']}\n```\n"
            if total + len(entry) > MAX_CONTEXT_BYTES:
                parts.append(f"\n... [{len(self.files)} files total, remaining files omitted for length]")
                break
            parts.append(entry)
            total += len(entry)

        return "\n".join(parts)

    def estimate_tokens(self) -> int:
        """Rough token estimate for the shared context (informational only)."""
        return estimate_tokens(self._build_context()) * len(DOC_TYPES)

    def generate(self, ai_provider: AIProvider, on_progress=None) -> Dict[str, str]:
        """Generate all doc files locally via the given AI provider.

        Returns {"index.md": "...", "architecture.md": "...", ...}.
        Raises AIProviderError if a doc fails to generate.
        """
        context = self._build_context()
        docs: Dict[str, str] = {}

        for i, (filename, instructions) in enumerate(DOC_TYPES.items(), 1):
            if on_progress:
                on_progress(i, len(DOC_TYPES), filename)

            user_prompt = f"{instructions}\n\n---\nProject context:\n\n{context}"
            result = ai_provider.generate_text(SYSTEM_PROMPT, user_prompt)
            docs[filename] = strip_markdown_fence(result["text"])

        return docs

    def save_docs(self, docs: Dict[str, str]):
        """Save generated docs to output directory."""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Write each doc
        for filename, content in docs.items():
            filepath = self.output_dir / filename
            filepath.write_text(content, encoding='utf-8')

        # Create a simple README in the docs folder
        docs_readme = self.output_dir.parent / "README.md"
        if not docs_readme.exists():
            docs_readme.write_text(
                "# Clausi Docs\n\n"
                "Auto-generated documentation for this project.\n\n"
                "## Contents\n\n"
                "- `latest/` - Most recent documentation\n\n"
                "## Viewing\n\n"
                "Open the markdown files in your IDE or push to GitHub to view rendered.\n\n"
                "## Regenerating\n\n"
                "```bash\n"
                "clausi docs generate\n"
                "```\n",
                encoding='utf-8'
            )
