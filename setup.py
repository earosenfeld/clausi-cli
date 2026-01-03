from setuptools import setup, find_packages, Command
from setuptools.command.build_py import build_py
import os
from pathlib import Path
import sys

# Read version from package without importing (avoids dependency issues)
version_file = Path(__file__).parent / "clausi" / "__init__.py"
__version__ = None
with open(version_file) as f:
    for line in f:
        if line.startswith("__version__"):
            __version__ = line.split("=")[1].strip().strip('"').strip("'")
            break
if __version__ is None:
    __version__ = "1.0.0"

class PostUninstallCommand(Command):
    """Post-uninstall command to remove config directory."""
    description = "Remove .clausi configuration directory"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        config_dir = Path.home() / ".clausi"
        if config_dir.exists():
            try:
                import shutil
                shutil.rmtree(config_dir)
                print(f"Removed configuration directory: {config_dir}")
            except Exception as e:
                print(f"Warning: Could not remove configuration directory: {e}")

class CustomBuildCommand(build_py):
    """Custom build command that ensures config is created."""
    
    def run(self):
        """Run the build and config creation."""
        # First create the config
        if not self.create_config():
            raise SystemExit("Failed to create config file. Build aborted.")
            
        # Then run the normal build
        build_py.run(self)
        
    def create_config(self):
        """Create default configuration file."""
        try:
            home_dir = Path.home()
            print(f"\n[INFO] Home directory: {home_dir}")
            
            config_dir = home_dir / ".clausi"
            print(f"[INFO] Config directory path: {config_dir}")
            
            print(f"[INFO] Creating config directory...")
            config_dir.mkdir(exist_ok=True)
            print(f"[INFO] Config directory exists: {config_dir.exists()}")
            
            config_path = config_dir / "config.yml"
            print(f"[INFO] Config file path: {config_path}")

            # Don't overwrite existing config - preserve user settings
            if config_path.exists():
                print(f"[INFO] Config file already exists, preserving user settings")
                return True

            config = {
                "api_key": "",
                "api": {
                    "url": "https://api.clausi.ai",
                    "timeout": 300,
                    "max_retries": 3
                },
                "report": {
                    "format": "pdf",
                    "output_dir": "reports",
                    "company_name": "",
                    "company_logo": "",
                    "template": "default"
                },
                "regulations": {
                    "selected": ["EU-AIA", "GDPR", "ISO-42001", "HIPAA", "SOC2"]
                }
            }
            
            print(f"[INFO] Writing config file...")
            # Use simple string formatting instead of yaml
            config_str = f"""api_key: ""
api_token: ""
api_keys:
  openai: ""
  anthropic: ""
api:
  url: https://api.clausi.ai
  timeout: 300
  max_retries: 3
report:
  format: pdf
  output_dir: clausi/reports
  company_name: ""
  company_logo: ""
  template: default
regulations:
  selected:
    - EU-AIA
    - GDPR
    - ISO-42001
    - HIPAA
    - SOC2
"""
            with open(config_path, 'w') as f:
                f.write(config_str)
            print(f"[SUCCESS] Created config file at: {config_path}")
            print(f"[INFO] Config file exists: {config_path.exists()}")
            print(f"[INFO] Config file size: {config_path.stat().st_size} bytes")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to create config file: {str(e)}")
            print(f"[ERROR] Error type: {type(e).__name__}")
            import traceback
            print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
            return False

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="clausi",
    version=__version__,
    author="Clausi",
    author_email="support@clausi.ai",
    description="AI compliance auditing CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://clausi.ai",
    project_urls={
        "Homepage": "https://clausi.ai",
        "Documentation": "https://docs.clausi.ai",
        "Support": "https://clausi.ai/contact",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Security",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "rich>=10.0.0",
        "requests>=2.26.0",
        "pyyaml>=5.4.1",
        "python-dotenv>=0.19.0",
        "openai>=1.0.0",
        "anthropic>=0.18.0",  # Claude API client
        "pathspec>=0.10.0",
        "textual>=0.47.0",  # TUI framework
        "questionary>=2.0.0",  # Arrow key menu navigation
    ],
    entry_points={
        "console_scripts": [
            "clausi=clausi.cli:main",
        ],
    },
    license="MIT",
    cmdclass={
        'build_py': CustomBuildCommand,
        'post_uninstall': PostUninstallCommand,
    },
) 