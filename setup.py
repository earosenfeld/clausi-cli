from setuptools import setup, find_packages, Command
from setuptools.command.build_py import build_py
import os
from pathlib import Path
import sys
import subprocess

# Try to import yaml, install it if not available
try:
    import yaml
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"])
    import yaml

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
                    "default": "EU-AIA"
                }
            }
            
            print(f"[INFO] Writing config file...")
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
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
    version="0.1.0",
    author="Clausi",
    author_email="support@clausi.ai",
    description="AI compliance auditing tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://clausi.ai",
    project_urls={
        "Bug Tracker": "https://github.com/clausi/clausi-cli/issues",
        "Documentation": "https://docs.clausi.ai",
        "Source Code": "https://github.com/clausi/clausi-cli",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Security",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.7",
    install_requires=[
        "click>=8.0.0",
        "rich>=10.0.0",
        "requests>=2.26.0",
        "pyyaml>=5.4.1",
        "python-dotenv>=0.19.0",
        "openai>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "clausi=clausi_cli.cli:main",
            "clausi-config=clausi_cli.create_config:create_config",
        ],
    },
    license="MIT",
    cmdclass={
        'build_py': CustomBuildCommand,
    }
) 