#!/usr/bin/env python3
"""
WeChat Image Downloader

This script downloads images from WeChat group chats by accessing the local WeChat database.
It extracts images from specified groups and saves them to organized folders.

Requirements:
- WeChat must be installed and logged in
- Script must be run with appropriate permissions
- Python packages: sqlite3, os, shutil, json, datetime, requests
"""

import sqlite3
import os
import shutil
import json
import hashlib
from datetime import datetime
from pathlib import Path
import argparse
import logging
from typing import List, Dict, Optional

class WeChatImageDownloader:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the WeChat image downloader."""
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.wechat_db_path = self.find_wechat_db()
        self.output_dir = Path(self.config.get("output_directory", "./downloaded_images"))
        self.output_dir.mkdir(exist_ok=True)
        
    def load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file."""
        default_config = {
            "output_directory": "./downloaded_images",
            "organize_by_group": True,
            "organize_by_date": True,
            "image_formats": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
            "max_file_size_mb": 50,
            "target_groups": []  # Empty means all groups
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"Error loading config: {e}. Using default configuration.")
        else:
            # Create default config file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"Created default config file: {config_path}")
            
        return default_config
    
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('wechat_downloader.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def find_wechat_db(self) -> Optional[str]:
        """Find WeChat database file on the system."""
        # Common WeChat database locations on Windows
        possible_paths = [
            os.path.expanduser("~/Documents/WeChat Files/*/Msg/*.db"),
            os.path.expanduser("~/AppData/Roaming/Tencent/WeChat/*/Msg/*.db"),
            "C:/Users/*/Documents/WeChat Files/*/Msg/*.db",
        ]
        
        import glob
        for pattern in possible_paths:
            matches = glob.glob(pattern)
            if matches:
                # Find the most recent database
                latest_db = max(matches, key=os.path.getmtime)
                self.logger.info(f"Found WeChat database: {latest_db}")
                return latest_db
        
        self.logger.error("WeChat database not found. Please specify the path manually.")
        return None
    
    def get_group_chats(self) -> List[Dict]:
        """Get list of group chats from WeChat database."""
        if not self.wechat_db_path or not os.path.exists(self.wechat_db_path):
            self.logger.error("WeChat database not accessible.")
            return []
        
        try:
            conn = sqlite3.connect(self.wechat_db_path)
            cursor = conn.cursor()
            
            # Query to get group chat information
            # Note: Table structure may vary by WeChat version
            query = """
            SELECT DISTINCT
                strUsrName as group_id,
                strNickName as group_name,
                nMsgCount as message_count
            FROM Contact 
            WHERE strUsrName LIKE '%@chatroom'
            ORDER BY nMsgCount DESC
            """
            
            cursor.execute(query)
            groups = []
            for row in cursor.fetchall():
                groups.append({
                    'id': row[0],
                    'name': row[1] or 'Unknown Group',
                    'message_count': row[2] or 0
                })
            
            conn.close()
            self.logger.info(f"Found {len(groups)} group chats")
            return groups
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error: {e}")
            return []
    
    def get_images_from_group(self, group_id: str) -> List[Dict]:
        """Get image messages from a specific group."""
        if not self.wechat_db_path or not os.path.exists(self.wechat_db_path):
            return []
        
        try:
            conn = sqlite3.connect(self.wechat_db_path)
            cursor = conn.cursor()
            
            # Query to get image messages
            # Note: Table structure may vary by WeChat version
            query = """
            SELECT 
                localId,
                nMsgId,
                strUsrName,
                strContent,
                nCreateTime,
                nImgStatus,
                strImgPath
            FROM MSG 
            WHERE strUsrName = ? 
            AND nType IN (3, 47)  -- Image message types
            AND strImgPath IS NOT NULL
            AND strImgPath != ''
            ORDER BY nCreateTime DESC
            """
            
            cursor.execute(query, (group_id,))
            images = []
            for row in cursor.fetchall():
                images.append({
                    'local_id': row[0],
                    'msg_id': row[1],
                    'group_id': row[2],
                    'content': row[3],
                    'timestamp': row[4],
                    'img_status': row[5],
                    'img_path': row[6]
                })
            
            conn.close()
            self.logger.info(f"Found {len(images)} images in group {group_id}")
            return images
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error: {e}")
            return []
    
    def copy_image_file(self, src_path: str, dest_dir: Path, filename: str) -> bool:
        """Copy image file from WeChat storage to destination."""
        try:
            if not os.path.exists(src_path):
                self.logger.warning(f"Source image not found: {src_path}")
                return False
            
            # Check file size
            file_size_mb = os.path.getsize(src_path) / (1024 * 1024)
            if file_size_mb > self.config["max_file_size_mb"]:
                self.logger.warning(f"File too large ({file_size_mb:.1f}MB): {src_path}")
                return False
            
            dest_path = dest_dir / filename
            
            # Avoid overwriting existing files
            counter = 1
            original_dest_path = dest_path
            while dest_path.exists():
                name_part = original_dest_path.stem
                ext_part = original_dest_path.suffix
                dest_path = dest_dir / f"{name_part}_{counter}{ext_part}"
                counter += 1
            
            shutil.copy2(src_path, dest_path)
            self.logger.info(f"Copied: {filename} -> {dest_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error copying {src_path}: {e}")
            return False
    
    def generate_filename(self, image_info: Dict, group_name: str) -> str:
        """Generate appropriate filename for the image."""
        timestamp = datetime.fromtimestamp(image_info['timestamp'])
        
        # Extract original extension if possible
        original_path = image_info['img_path']
        _, ext = os.path.splitext(original_path)
        if not ext:
            ext = '.jpg'  # Default extension
        
        # Create filename with timestamp and message ID
        safe_group_name = "".join(c for c in group_name if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{image_info['msg_id']}{ext}"
        
        return filename
    
    def organize_output_directory(self, group_name: str, timestamp: int) -> Path:
        """Create organized directory structure for output."""
        base_dir = self.output_dir
        
        if self.config["organize_by_group"]:
            safe_group_name = "".join(c for c in group_name if c.isalnum() or c in (' ', '-', '_')).strip()
            base_dir = base_dir / safe_group_name
        
        if self.config["organize_by_date"]:
            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m')
            base_dir = base_dir / date_str
        
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    
    def download_images_from_group(self, group_info: Dict) -> int:
        """Download all images from a specific group."""
        group_id = group_info['id']
        group_name = group_info['name']
        
        self.logger.info(f"Processing group: {group_name}")
        
        images = self.get_images_from_group(group_id)
        if not images:
            self.logger.info(f"No images found in group: {group_name}")
            return 0
        
        downloaded_count = 0
        for image_info in images:
            try:
                # Organize output directory
                dest_dir = self.organize_output_directory(group_name, image_info['timestamp'])
                
                # Generate filename
                filename = self.generate_filename(image_info, group_name)
                
                # Copy the image file
                if self.copy_image_file(image_info['img_path'], dest_dir, filename):
                    downloaded_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing image {image_info['msg_id']}: {e}")
        
        self.logger.info(f"Downloaded {downloaded_count} images from {group_name}")
        return downloaded_count
    
    def run(self, specific_groups: List[str] = None):
        """Run the image downloader."""
        self.logger.info("Starting WeChat image downloader...")
        
        if not self.wechat_db_path:
            self.logger.error("Cannot proceed without WeChat database access.")
            return
        
        # Get available groups
        groups = self.get_group_chats()
        if not groups:
            self.logger.error("No groups found or database inaccessible.")
            return
        
        # Filter groups if specific ones are requested
        if specific_groups:
            groups = [g for g in groups if g['id'] in specific_groups or g['name'] in specific_groups]
        elif self.config["target_groups"]:
            groups = [g for g in groups if g['id'] in self.config["target_groups"] or g['name'] in self.config["target_groups"]]
        
        if not groups:
            self.logger.error("No matching groups found.")
            return
        
        # Display available groups
        print("\nAvailable groups:")
        for i, group in enumerate(groups, 1):
            print(f"{i}. {group['name']} (Messages: {group['message_count']})")
        
        # Download images from each group
        total_downloaded = 0
        for group in groups:
            downloaded = self.download_images_from_group(group)
            total_downloaded += downloaded
        
        self.logger.info(f"Download complete! Total images downloaded: {total_downloaded}")
        print(f"\nDownload complete! Total images downloaded: {total_downloaded}")
        print(f"Images saved to: {self.output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Download images from WeChat groups")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    parser.add_argument("--groups", nargs="+", help="Specific group names or IDs to download from")
    parser.add_argument("--list-groups", action="store_true", help="List available groups and exit")
    
    args = parser.parse_args()
    
    try:
        downloader = WeChatImageDownloader(args.config)
        
        if args.list_groups:
            groups = downloader.get_group_chats()
            print("\nAvailable WeChat groups:")
            for i, group in enumerate(groups, 1):
                print(f"{i}. {group['name']} (ID: {group['id']}, Messages: {group['message_count']})")
            return
        
        downloader.run(args.groups)
        
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
