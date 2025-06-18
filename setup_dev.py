#!/usr/bin/env python3
"""Setup script for development environment."""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return its output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Error: {e.stderr}")
        sys.exit(1)

def main():
    """Set up development environment."""
    # Get the directory containing this script
    script_dir = Path(__file__).parent.absolute()
    
    # Create virtual environment
    print("Creating virtual environment...")
    venv_path = script_dir / "venv"
    if not venv_path.exists():
        run_command([sys.executable, "-m", "venv", "venv"], cwd=script_dir)
    
    # Determine the pip path
    if os.name == "nt":  # Windows
        pip_path = venv_path / "Scripts" / "pip"
    else:  # Unix-like
        pip_path = venv_path / "bin" / "pip"
    
    # Upgrade pip
    print("Upgrading pip...")
    run_command([str(pip_path), "install", "--upgrade", "pip"])
    
    # Install required packages
    print("Installing required packages...")
    run_command([str(pip_path), "install", "click", "requests", "pyyaml", "rich", "openai"])
    
    # Install development dependencies
    print("Installing development dependencies...")
    run_command([str(pip_path), "install", "-e", "."])
    
    print("\nDevelopment environment setup complete!")
    print("\nTo activate the virtual environment:")
    if os.name == "nt":  # Windows
        print(f"    {venv_path}\\Scripts\\activate")
    else:  # Unix-like
        print(f"    source {venv_path}/bin/activate")
    print("\nYou can now run 'clausi' from anywhere in the virtual environment.")

if __name__ == "__main__":
    main() 