#!/usr/bin/env python3
"""
Utility functions for WeChat Image Downloader

This module provides helper functions for image processing, file management,
and database operations used by the main downloader script.
"""

import os
import hashlib
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Handles image processing operations."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
    
    def is_valid_image(self, file_path: str) -> bool:
        """Check if file is a valid image."""
        try:
            if not os.path.exists(file_path):
                return False
            
            # Check file extension
            _, ext = os.path.splitext(file_path.lower())
            if ext not in self.supported_formats:
                return False
            
            # Try to open with PIL if available
            if PIL_AVAILABLE:
                try:
                    with Image.open(file_path) as img:
                        img.verify()
                    return True
                except Exception:
                    return False
            
            # Basic file size check if PIL not available
            return os.path.getsize(file_path) > 0
            
        except Exception as e:
            logger.warning(f"Error validating image {file_path}: {e}")
            return False
    
    def get_image_info(self, file_path: str) -> Optional[Dict]:
        """Get image metadata information."""
        if not PIL_AVAILABLE or not self.is_valid_image(file_path):
            return None
        
        try:
            with Image.open(file_path) as img:
                info = {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height,
                    'file_size': os.path.getsize(file_path)
                }
                
                # Get EXIF data if available
                if hasattr(img, '_getexif') and img._getexif():
                    info['has_exif'] = True
                else:
                    info['has_exif'] = False
                
                return info
                
        except Exception as e:
            logger.warning(f"Error getting image info for {file_path}: {e}")
            return None
    
    def create_thumbnail(self, src_path: str, dest_path: str, size: Tuple[int, int] = (200, 200)) -> bool:
        """Create thumbnail for image."""
        if not PIL_AVAILABLE:
            logger.warning("PIL not available, cannot create thumbnails")
            return False
        
        try:
            with Image.open(src_path) as img:
                # Create thumbnail maintaining aspect ratio
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Save thumbnail
                img.save(dest_path, optimize=True, quality=85)
                return True
                
        except Exception as e:
            logger.error(f"Error creating thumbnail for {src_path}: {e}")
            return False

class FileManager:
    """Handles file operations and organization."""
    
    def __init__(self, config: Dict):
        self.config = config
    
    def calculate_file_hash(self, file_path: str, algorithm: str = 'md5') -> Optional[str]:
        """Calculate hash of file for duplicate detection."""
        try:
            hash_obj = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    def find_duplicates(self, directory: str) -> Dict[str, List[str]]:
        """Find duplicate files in directory based on hash."""
        hash_map = {}
        duplicates = {}
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                file_hash = self.calculate_file_hash(file_path)
                
                if file_hash:
                    if file_hash in hash_map:
                        if file_hash not in duplicates:
                            duplicates[file_hash] = [hash_map[file_hash]]
                        duplicates[file_hash].append(file_path)
                    else:
                        hash_map[file_hash] = file_path
        
        return duplicates
    
    def safe_filename(self, filename: str, max_length: int = 255) -> str:
        """Create safe filename by removing invalid characters."""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            name = name[:max_length - len(ext) - 1]
            filename = name + ext
        
        return filename
    
    def ensure_unique_filename(self, file_path: str) -> str:
        """Ensure filename is unique by adding counter if needed."""
        if not os.path.exists(file_path):
            return file_path
        
        base_path = Path(file_path)
        counter = 1
        
        while True:
            new_name = f"{base_path.stem}_{counter}{base_path.suffix}"
            new_path = base_path.parent / new_name
            
            if not new_path.exists():
                return str(new_path)
            
            counter += 1
    
    def organize_files_by_date(self, files: List[str], base_dir: str) -> Dict[str, List[str]]:
        """Organize files by their modification date."""
        organized = {}
        
        for file_path in files:
            try:
                mtime = os.path.getmtime(file_path)
                date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m')
                
                if date_str not in organized:
                    organized[date_str] = []
                
                organized[date_str].append(file_path)
                
            except Exception as e:
                logger.warning(f"Error getting date for {file_path}: {e}")
        
        return organized
    
    def create_directory_structure(self, base_path: str, subdirs: List[str]) -> bool:
        """Create nested directory structure."""
        try:
            current_path = Path(base_path)
            current_path.mkdir(exist_ok=True)
            
            for subdir in subdirs:
                current_path = current_path / subdir
                current_path.mkdir(exist_ok=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
            return False

class DatabaseHelper:
    """Helper functions for WeChat database operations."""
    
    @staticmethod
    def format_wechat_timestamp(timestamp: int) -> datetime:
        """Convert WeChat timestamp to datetime object."""
        # WeChat timestamps are usually in milliseconds
        if timestamp > 10**10:  # If timestamp is in milliseconds
            timestamp = timestamp / 1000
        
        return datetime.fromtimestamp(timestamp)
    
    @staticmethod
    def parse_message_content(content: str) -> Dict:
        """Parse WeChat message content for image information."""
        try:
            # WeChat stores image info in XML-like format
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(content)
            img_info = {}
            
            # Extract image information
            img_element = root.find('.//img')
            if img_element is not None:
                img_info.update(img_element.attrib)
            
            return img_info
            
        except Exception as e:
            logger.debug(f"Error parsing message content: {e}")
            return {}
    
    @staticmethod
    def get_group_avatar_path(group_id: str, wechat_dir: str) -> Optional[str]:
        """Get path to group avatar image."""
        # Common avatar locations
        avatar_patterns = [
            f"{wechat_dir}/Avatar/{group_id}.jpg",
            f"{wechat_dir}/Avatar/{group_id}.png",
            f"{wechat_dir}/Avatars/{group_id}.jpg",
            f"{wechat_dir}/Avatars/{group_id}.png"
        ]
        
        for pattern in avatar_patterns:
            if os.path.exists(pattern):
                return pattern
        
        return None

class ProgressTracker:
    """Track and display download progress."""
    
    def __init__(self, total_items: int):
        self.total_items = total_items
        self.completed_items = 0
        self.failed_items = 0
        self.start_time = datetime.now()
    
    def update(self, success: bool = True):
        """Update progress counters."""
        if success:
            self.completed_items += 1
        else:
            self.failed_items += 1
    
    def get_progress_info(self) -> Dict:
        """Get current progress information."""
        elapsed = datetime.now() - self.start_time
        processed = self.completed_items + self.failed_items
        
        progress_info = {
            'total': self.total_items,
            'completed': self.completed_items,
            'failed': self.failed_items,
            'processed': processed,
            'remaining': self.total_items - processed,
            'success_rate': (self.completed_items / processed * 100) if processed > 0 else 0,
            'elapsed_time': elapsed,
            'estimated_remaining': None
        }
        
        # Estimate remaining time
        if processed > 0:
            avg_time_per_item = elapsed.total_seconds() / processed
            remaining_seconds = avg_time_per_item * progress_info['remaining']
            progress_info['estimated_remaining'] = remaining_seconds
        
        return progress_info
    
    def print_progress(self):
        """Print current progress to console."""
        info = self.get_progress_info()
        
        print(f"\rProgress: {info['completed']}/{info['total']} "
              f"({info['success_rate']:.1f}% success) "
              f"- {info['failed']} failed", end='', flush=True)

def setup_logging(config: Dict) -> logging.Logger:
    """Setup logging configuration."""
    log_level = getattr(logging, config.get('logging', {}).get('level', 'INFO'))
    log_file = config.get('logging', {}).get('log_file', 'wechat_downloader.log')
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def validate_config(config: Dict) -> List[str]:
    """Validate configuration and return list of issues."""
    issues = []
    
    # Check required fields
    if not config.get('output_directory'):
        issues.append("output_directory is required")
    
    # Check output directory is writable
    output_dir = config.get('output_directory', '.')
    if not os.access(os.path.dirname(os.path.abspath(output_dir)), os.W_OK):
        issues.append(f"Output directory not writable: {output_dir}")
    
    # Check file size limit
    max_size = config.get('max_file_size_mb', 50)
    if not isinstance(max_size, (int, float)) or max_size <= 0:
        issues.append("max_file_size_mb must be a positive number")
    
    # Check image formats
    formats = config.get('image_formats', [])
    if not isinstance(formats, list) or not formats:
        issues.append("image_formats must be a non-empty list")
    
    return issues
