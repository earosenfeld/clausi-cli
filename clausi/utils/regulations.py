"""Local regulation loading (built-in bundled YAML + user custom regulations).

No network calls - built-in regulations ship inside the clausi package
(clausi/data/regulations/); custom regulations live in
~/.clausi/custom_regulations/ and <project>/.clausi/regulations/.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from clausi.utils.console import console

logger = logging.getLogger(__name__)

BUILT_IN_REGULATIONS_DIR = Path(__file__).parent.parent / "data" / "regulations"
CUSTOM_REGULATIONS_DIR = Path.home() / ".clausi" / "custom_regulations"

# Maps regulation YAML filename stem -> canonical regulation code.
_FILENAME_TO_CODE = {
    "eu_aia": "EU-AIA",
    "gdpr": "GDPR",
    "iso_42001": "ISO-42001",
    "hipaa": "HIPAA",
    "soc2": "SOC2",
}

_BUILT_IN_CACHE: Optional[Dict[str, Any]] = None


def _regulation_code_for(yaml_path: Path) -> str:
    stem = yaml_path.stem
    return _FILENAME_TO_CODE.get(stem, stem.upper().replace("_", "-"))


def _load_regulation_file(yaml_path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        console.print(f"[yellow]Warning: Could not load regulation {yaml_path.name}: {e}[/yellow]")
        return None


def get_regulations() -> Dict[str, Any]:
    """Get built-in regulations bundled with the CLI (name/description/clauses)."""
    global _BUILT_IN_CACHE
    if _BUILT_IN_CACHE is not None:
        return _BUILT_IN_CACHE

    regulations: Dict[str, Any] = {}
    if BUILT_IN_REGULATIONS_DIR.exists():
        for yaml_path in sorted(BUILT_IN_REGULATIONS_DIR.glob("*.yml")):
            data = _load_regulation_file(yaml_path)
            if not data:
                continue
            code = _regulation_code_for(yaml_path)
            regulations[code] = {
                "name": data.get("name", code),
                "description": data.get("description", ""),
                "version": data.get("version", ""),
                "effective_date": data.get("effective_date", ""),
                "last_updated": data.get("last_updated", ""),
                "clauses": data.get("clauses", []),
            }

    _BUILT_IN_CACHE = regulations
    return regulations


def discover_custom_regulations(project_path: Optional[Path] = None) -> Dict[str, Path]:
    """Discover custom regulation YAML files (global + project-local)."""
    custom_regs: Dict[str, Path] = {}

    if CUSTOM_REGULATIONS_DIR.exists():
        for yaml_file in CUSTOM_REGULATIONS_DIR.glob("*.yml"):
            reg_code = yaml_file.stem.upper().replace("_", "-")
            custom_regs[reg_code] = yaml_file

    if project_path:
        project_regs_dir = Path(project_path) / ".clausi" / "regulations"
        if project_regs_dir.exists():
            for yaml_file in project_regs_dir.glob("*.yml"):
                reg_code = yaml_file.stem.upper().replace("_", "-")
                custom_regs[reg_code] = yaml_file

    return custom_regs


def load_custom_regulation(yaml_path: Path) -> Optional[Dict[str, Any]]:
    """Load a custom regulation YAML file (expects name/description/clauses)."""
    data = _load_regulation_file(yaml_path)
    if not data or "clauses" not in data:
        return None
    return data


def get_all_regulations() -> Tuple[Dict[str, Any], Dict[str, Path]]:
    """Get both built-in and custom regulations."""
    return get_regulations(), discover_custom_regulations()


def get_regulation_choices() -> List[str]:
    """Get list of regulation codes for Click choices (built-in + custom)."""
    built_in, custom = get_all_regulations()
    return list(built_in.keys()) + list(custom.keys())


def get_regulation_clauses(regulation_code: str, project_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Get the full regulation dict ({name, description, clauses}) for a given code,
    checking built-in regulations first, then custom ones."""
    built_in = get_regulations()
    if regulation_code in built_in:
        return built_in[regulation_code]

    custom_paths = discover_custom_regulations(project_path=project_path)
    if regulation_code in custom_paths:
        return load_custom_regulation(custom_paths[regulation_code])

    return None
