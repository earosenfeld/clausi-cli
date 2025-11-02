import yaml
from pathlib import Path

def create_config():
    """Create default config file."""
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
    
    # Create .clausi directory in user's home directory
    config_dir = Path.home() / ".clausi"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.yml"
    
    print("\n=== Creating Clausi Configuration ===")
    print(f"Config file will be created at: {config_path}")
    
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        print("[SUCCESS] Config file created successfully!")
        print("=== Configuration Complete ===\n")
    except Exception as e:
        print(f"[ERROR] Error creating config file: {e}")
        print("=== Configuration Failed ===\n")

if __name__ == "__main__":
    create_config() 