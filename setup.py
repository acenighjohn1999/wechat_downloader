#!/usr/bin/env python3
"""
Setup script for WeChat Image Downloader

This script helps with initial setup and configuration.
"""

import os
import json
import sys
from pathlib import Path

def create_default_config():
    """Create default configuration file."""
    config = {
        "output_directory": "./downloaded_images",
        "organize_by_group": True,
        "organize_by_date": True,
        "image_formats": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
        "max_file_size_mb": 50,
        "target_groups": [],
        "wechat_db_path": "",
        "download_settings": {
            "skip_existing": True,
            "create_thumbnails": False,
            "preserve_metadata": True
        },
        "logging": {
            "level": "INFO",
            "log_file": "wechat_downloader.log"
        }
    }
    
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✓ Created config.json with default settings")

def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []
    
    try:
        import sqlite3
    except ImportError:
        missing.append("sqlite3 (should be included with Python)")
    
    try:
        from PIL import Image
        print("✓ Pillow is available for image processing")
    except ImportError:
        print("⚠ Pillow not found - install with: pip install Pillow")
        print("  (Optional: needed for thumbnails and image validation)")
    
    if missing:
        print("✗ Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        return False
    
    print("✓ All core dependencies available")
    return True

def find_wechat_installation():
    """Try to find WeChat installation."""
    import glob
    
    # Common WeChat locations on Windows
    patterns = [
        os.path.expanduser("~/Documents/WeChat Files/*/Msg/*.db"),
        os.path.expanduser("~/AppData/Roaming/Tencent/WeChat/*/Msg/*.db"),
        "C:/Users/*/Documents/WeChat Files/*/Msg/*.db",
    ]
    
    found_dbs = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        found_dbs.extend(matches)
    
    if found_dbs:
        print(f"✓ Found {len(found_dbs)} WeChat database(s):")
        for db in found_dbs:
            print(f"  - {db}")
        
        # Update config with the most recent database
        latest_db = max(found_dbs, key=os.path.getmtime)
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            config['wechat_db_path'] = latest_db
            
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Updated config.json with database path: {latest_db}")
        except Exception as e:
            print(f"⚠ Could not update config: {e}")
    else:
        print("⚠ No WeChat databases found automatically")
        print("  Make sure WeChat is installed and you've logged in at least once")
        print("  You may need to manually specify the database path in config.json")

def create_output_directory():
    """Create output directory."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        output_dir = Path(config.get('output_directory', './downloaded_images'))
        output_dir.mkdir(exist_ok=True)
        
        print(f"✓ Created output directory: {output_dir}")
        
    except Exception as e:
        print(f"⚠ Could not create output directory: {e}")

def main():
    """Run setup process."""
    print("WeChat Image Downloader Setup")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 7):
        print("✗ Python 3.7 or higher is required")
        sys.exit(1)
    else:
        print(f"✓ Python {sys.version.split()[0]} detected")
    
    # Create configuration
    if not os.path.exists('config.json'):
        create_default_config()
    else:
        print("✓ config.json already exists")
    
    # Check dependencies
    check_dependencies()
    
    # Find WeChat installation
    find_wechat_installation()
    
    # Create output directory
    create_output_directory()
    
    print("\n" + "=" * 40)
    print("Setup complete! Next steps:")
    print("1. Review and customize config.json if needed")
    print("2. Run: python wechat_image_downloader.py --list-groups")
    print("3. Run: python wechat_image_downloader.py")
    print("\nFor help: python wechat_image_downloader.py --help")

if __name__ == "__main__":
    main()
