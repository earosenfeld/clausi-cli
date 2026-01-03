"""Dynamic regulation fetching with caching and custom regulation support."""

import logging
import os
import json
import time
import requests
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from clausi.utils.console import console

logger = logging.getLogger(__name__)

# Cache and custom regulation paths
CACHE_FILE = Path.home() / ".clausi" / "regulations_cache.json"
CUSTOM_REGULATIONS_DIR = Path.home() / ".clausi" / "custom_regulations"
CACHE_TTL = 3600  # 1 hour in seconds

# Fallback regulations if backend is unreachable
FALLBACK_REGULATIONS = {
    "EU-AIA": {
        "name": "EU AI Act",
        "description": "European Union Artificial Intelligence Act",
    },
    "GDPR": {
        "name": "GDPR",
        "description": "General Data Protection Regulation",
    },
    "ISO-42001": {
        "name": "ISO 42001",
        "description": "AI Management System – ISO/IEC 42001:2023",
    },
    "HIPAA": {
        "name": "HIPAA",
        "description": "Health Insurance Portability and Accountability Act",
    },
    "SOC2": {
        "name": "SOC 2",
        "description": "System and Organization Controls Type 2",
    },
}


def _get_cache() -> Optional[Dict[str, Any]]:
    """Load regulations from cache if valid."""
    if not CACHE_FILE.exists():
        return None

    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)

        # Check if cache is still valid
        if time.time() - cache.get('timestamp', 0) < CACHE_TTL:
            return cache.get('regulations')
    except Exception:
        pass

    return None


def _save_cache(regulations: Dict[str, Any]) -> None:
    """Save regulations to cache."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump({
                'timestamp': time.time(),
                'regulations': regulations
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to cache regulation: {e}")


def get_regulations(api_url: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
    """Fetch available regulations from backend with caching.

    Args:
        api_url: Optional API URL (defaults to environment variable or hardcoded)
        use_cache: Whether to use cached regulations (default: True)

    Returns:
        Dictionary of regulations {code: {name, description}}
    """
    # Try cache first if enabled - this is instant
    if use_cache:
        cached = _get_cache()
        if cached:
            return cached

    # No cache - use FALLBACK_REGULATIONS immediately for fast startup
    # The backend will be called during the actual scan anyway
    # This ensures CLI startup and menu navigation is instant
    if use_cache:
        # Return fallback immediately, try to update cache in background
        # For now just return fallback - cache will update on next successful API call
        return FALLBACK_REGULATIONS

    # Explicit cache bypass requested (use_cache=False) - fetch from backend
    if not api_url:
        api_url = os.getenv('CLAUSI_TUNNEL_BASE') or "https://api.clausi.ai"

    try:
        response = requests.get(
            f"{api_url}/api/clausi/regulations",
            timeout=2  # Short timeout
        )

        if response.status_code == 200:
            regulations_list = response.json()

            # Convert list format to dict format for backward compatibility
            regulations = {}
            for reg in regulations_list:
                regulations[reg['code']] = {
                    'name': reg['name'],
                    'description': reg.get('description', '')
                }

            # Save to cache for future use
            _save_cache(regulations)
            return regulations

    except Exception:
        pass

    # Final fallback
    return FALLBACK_REGULATIONS


def discover_custom_regulations(project_path: Optional[Path] = None) -> Dict[str, Path]:
    """Discover custom regulation YAML files from user's config directory AND project directory.

    Args:
        project_path: Optional path to project directory (will check .clausi/regulations/)

    Returns:
        Dictionary mapping regulation code to YAML file path
        Example: {'my-company-policy': Path('~/.clausi/custom_regulations/my-company-policy.yml')}
    """
    custom_regs = {}

    # 1. Check global custom regulations directory (~/.clausi/custom_regulations/)
    if CUSTOM_REGULATIONS_DIR.exists():
        for yaml_file in CUSTOM_REGULATIONS_DIR.glob("*.yml"):
            # Use filename (without extension) as regulation code
            reg_code = yaml_file.stem.upper().replace("_", "-")
            custom_regs[reg_code] = yaml_file

    # 2. Check project-specific custom regulations (.clausi/regulations/)
    if project_path:
        project_regs_dir = project_path / ".clausi" / "regulations"
        if project_regs_dir.exists():
            for yaml_file in project_regs_dir.glob("*.yml"):
                # Use filename (without extension) as regulation code
                reg_code = yaml_file.stem.upper().replace("_", "-")
                # Project-specific regulations override global ones
                custom_regs[reg_code] = yaml_file

    return custom_regs


def load_custom_regulation(yaml_path: Path) -> Optional[Dict[str, Any]]:
    """Load a custom regulation YAML file.

    Args:
        yaml_path: Path to the YAML file

    Returns:
        Parsed YAML content as dictionary, or None if invalid
    """
    try:
        with open(yaml_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load custom regulation {yaml_path.name}: {e}[/yellow]")
        return None


def get_all_regulations() -> Tuple[Dict[str, Any], Dict[str, Path]]:
    """Get both built-in and custom regulations.

    Returns:
        Tuple of (built_in_regulations, custom_regulations_paths)
    """
    built_in = get_regulations()
    custom = discover_custom_regulations()
    return built_in, custom


def get_regulation_choices() -> list:
    """Get list of regulation codes for Click choices (built-in + custom).

    Returns:
        List of regulation codes (e.g., ['EU-AIA', 'GDPR', 'my-company-policy'])
    """
    built_in, custom = get_all_regulations()
    return list(built_in.keys()) + list(custom.keys())


def get_custom_regulations_for_scan(selected_regulations: List[str], project_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Prepare custom regulations to send to backend.

    Args:
        selected_regulations: List of regulation codes selected by user
        project_path: Optional path to project directory

    Returns:
        List of custom regulation dicts with code and YAML content
    """
    custom_regs_paths = discover_custom_regulations(project_path=project_path)
    custom_regs_data = []

    for reg_code in selected_regulations:
        if reg_code in custom_regs_paths:
            yaml_content = load_custom_regulation(custom_regs_paths[reg_code])
            if yaml_content:
                custom_regs_data.append({
                    'code': reg_code,
                    'content': yaml_content
                })

    return custom_regs_data


def upload_custom_regulations(
    selected_regulations: List[str],
    project_path: Path,
    api_url: str,
    customer_id: str = "cli_user"
) -> None:
    """Upload custom regulations to backend before scanning.

    Args:
        selected_regulations: List of regulation codes to check
        project_path: Path to the project being scanned
        api_url: Backend API URL
        customer_id: Customer ID for tracking (default: "cli_user")
    """
    custom_regs_paths = discover_custom_regulations(project_path=project_path)

    for reg_code in selected_regulations:
        if reg_code in custom_regs_paths:
            yaml_path = custom_regs_paths[reg_code]

            # Read YAML content
            try:
                with open(yaml_path, 'r') as f:
                    yaml_content = f.read()
            except Exception as e:
                console.print(f"[yellow]Warning: Could not read {yaml_path.name}: {e}[/yellow]")
                continue

            # Upload to backend
            try:
                response = requests.post(
                    f"{api_url}/api/clausi/regulations/custom",
                    json={
                        "regulation_id": reg_code,
                        "yaml_content": yaml_content,
                        "customer_id": customer_id
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    console.print(f"[green]✓[/green] Uploaded custom regulation: {reg_code}")
                else:
                    error_msg = response.json().get("detail", "Unknown error")
                    console.print(f"[yellow]Warning: Failed to upload {reg_code}: {error_msg}[/yellow]")

            except Exception as e:
                console.print(f"[yellow]Warning: Could not upload {reg_code}: {e}[/yellow]")
