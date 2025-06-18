import os
import sys
from pathlib import Path
import yaml
import setuptools.build_meta as _orig

# Expose the original backend's functions we don't override
get_requires_for_build_wheel = _orig.get_requires_for_build_wheel  # type: ignore
get_requires_for_build_sdist = _orig.get_requires_for_build_sdist  # type: ignore
get_requires_for_build_editable = _orig.get_requires_for_build_editable  # type: ignore
prepare_metadata_for_build_wheel = _orig.prepare_metadata_for_build_wheel  # type: ignore
prepare_metadata_for_build_editable = _orig.prepare_metadata_for_build_editable  # type: ignore


def create_config():
    """Create default configuration file in the user's home directory."""
    try:
        home_dir = Path.home()
        print(f"\n[Clausi] Home directory: {home_dir}")

        config_dir = home_dir / ".clausi"
        print(f"[Clausi] Config directory path: {config_dir}")
        config_dir.mkdir(exist_ok=True)

        config_path = config_dir / "config.yml"
        print(f"[Clausi] Config file path: {config_path}")

        if config_path.exists():
            print("[Clausi] Config file already exists - skipping creation.")
            return True

        config = {
            "api_key": "",
            "api": {
                "url": "https://api.clausi.ai",
                "timeout": 300,
                "max_retries": 3,
            },
            "report": {
                "format": "pdf",
                "output_dir": "reports",
                "company_name": "",
                "company_logo": "",
                "template": "default",
            },
            "regulations": {"default": "EU-AIA"},
        }

        print("[Clausi] Writing default config file...")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)
        print(f"[Clausi] ✓ Created config file at: {config_path}")
        return True

    except Exception as e:
        import traceback

        print("[Clausi] ✗ Failed to create config file:", e)
        print(traceback.format_exc())
        return False


# Our wrapper functions -----------------------------------------------------

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    if not create_config():
        raise SystemExit("Clausi build aborted: could not create config file.")
    return _orig.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    if not create_config():
        raise SystemExit("Clausi build aborted: could not create config file.")
    return _orig.build_sdist(sdist_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    if not create_config():
        raise SystemExit("Clausi build aborted: could not create config file.")
    # setuptools.build_meta provides build_editable starting with Python 3.12 / Setuptools 64+
    if hasattr(_orig, "build_editable"):
        return _orig.build_editable(wheel_directory, config_settings, metadata_directory)  # type: ignore[attr-defined]
    # Fallback: just build wheel and treat as editable
    return _orig.build_wheel(wheel_directory, config_settings, metadata_directory) 