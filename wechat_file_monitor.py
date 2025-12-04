import os
import time
import argparse
import csv
import threading
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timedelta
from wechat_decoder import decode_wechat_dat
from collections import defaultdict

# Import auto-annotation module from asian_grocer_scrapers repo
sys.path.insert(0, r'C:\Users\henry\source\repos\asian_grocer_scrapers')
try:
    from auto_annotator import auto_annotate_duplicate_image
    AUTO_ANNOTATION_AVAILABLE = True
except ImportError:
    AUTO_ANNOTATION_AVAILABLE = False
    print("[Warning] Auto-annotation module not available")

# Folders to monitor
MONITOR_FOLDER = r"C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach"
BASE_THUMB_PATH = r"C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach"
CSV_FILE = "wechat_folder_mappings.csv"

# Output folder for decoded images
OUTPUT_BASE = r"C:\Users\henry\OneDrive\Documents\WeChat Decoded Images2"

# Configuration for auto-navigation queue
IDLE_THRESHOLD_SECONDS = 60  # Process folder after 60 seconds of no activity
QUEUE_CHECK_INTERVAL = 5  # Check queue every 5 seconds
MIN_FILES_TO_PROCESS = 1  # Minimum files before processing


class FolderActivityTracker:
    """Tracks activity for each folder to determine when to process"""
    
    def __init__(self):
        self.folder_last_activity = {}  # folder_id -> datetime
        self.folder_file_counts = defaultdict(int)  # folder_id -> count
        self.folder_to_store = {}  # folder_id -> store_name (from CSV)
        self.lock = threading.Lock()
        self.load_folder_mappings()
    
    def load_folder_mappings(self):
        """Load folder ID to store name mappings from CSV"""
        if not os.path.exists(CSV_FILE):
            print(f"[Warning] {CSV_FILE} not found for folder mappings")
            return
        
        try:
            with open(CSV_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    folder_id = row['Folder']
                    store_name = row['Store']
                    self.folder_to_store[folder_id] = store_name
            print(f"[Activity Tracker] Loaded {len(self.folder_to_store)} folder mappings from CSV")
        except Exception as e:
            print(f"[Activity Tracker] Error loading CSV: {e}")
    
    def update_activity(self, file_path):
        """Update activity timestamp for a folder based on file path"""
        # Extract folder ID from path like: .../MsgAttach/abc123/Thumb/2025-11/file.dat
        try:
            parts = file_path.split(os.sep)
            # Find MsgAttach index and get folder ID after it
            if 'MsgAttach' in parts:
                msgattach_idx = parts.index('MsgAttach')
                if msgattach_idx + 1 < len(parts):
                    folder_id = parts[msgattach_idx + 1]
                    
                    with self.lock:
                        self.folder_last_activity[folder_id] = datetime.now()
                        self.folder_file_counts[folder_id] += 1
                        
                        # Get store name if available
                        store_name = self.folder_to_store.get(folder_id, folder_id)
                        return folder_id, store_name
        except Exception as e:
            pass
        return None, None
    
    def get_idle_time(self, folder_id):
        """Get seconds since last activity for a folder"""
        with self.lock:
            if folder_id in self.folder_last_activity:
                return (datetime.now() - self.folder_last_activity[folder_id]).total_seconds()
        return float('inf')
    
    def get_file_count(self, folder_id):
        """Get file count for a folder"""
        with self.lock:
            return self.folder_file_counts.get(folder_id, 0)
    
    def get_store_name(self, folder_id):
        """Get store name for a folder ID"""
        return self.folder_to_store.get(folder_id, folder_id)
    
    def reset_folder(self, folder_id):
        """Reset folder after successful processing"""
        with self.lock:
            if folder_id in self.folder_last_activity:
                del self.folder_last_activity[folder_id]
            if folder_id in self.folder_file_counts:
                del self.folder_file_counts[folder_id]
    
    def get_all_active_folders(self):
        """Get all folders with recent activity"""
        with self.lock:
            return list(self.folder_last_activity.keys())


class ProcessingQueue:
    """Manages queue of folders to process"""
    
    def __init__(self, activity_tracker):
        self.queue_items = {}  # folder_id -> QueueItem
        self.currently_processing = None
        self.needs_reprocessing = set()
        self.lock = threading.Lock()
        self.activity_tracker = activity_tracker
    
    def add_or_update(self, folder_id, store_name):
        """Add folder to queue or update if already exists"""
        with self.lock:
            if folder_id not in self.queue_items:
                self.queue_items[folder_id] = {
                    'store_name': store_name,
                    'added_at': datetime.now()
                }
    
    def mark_new_activity_during_processing(self, folder_id):
        """Mark that a folder received new activity while being processed"""
        with self.lock:
            if self.currently_processing == folder_id:
                self.needs_reprocessing.add(folder_id)
                return True
        return False
    
    def get_next_to_process(self):
        """Get next folder that's idle and ready to process"""
        with self.lock:
            if self.currently_processing:
                return None  # Already processing something
            
            # Find folders that are idle and have enough files
            candidates = []
            for folder_id in self.queue_items.keys():
                idle_time = self.activity_tracker.get_idle_time(folder_id)
                file_count = self.activity_tracker.get_file_count(folder_id)
                
                if idle_time >= IDLE_THRESHOLD_SECONDS and file_count >= MIN_FILES_TO_PROCESS:
                    candidates.append((folder_id, idle_time, file_count))
            
            if not candidates:
                return None
            
            # Sort by idle time (longest idle first)
            candidates.sort(key=lambda x: x[1], reverse=True)
            folder_id, idle_time, file_count = candidates[0]
            
            # Mark as processing
            self.currently_processing = folder_id
            store_name = self.activity_tracker.get_store_name(folder_id)
            
            return {
                'folder_id': folder_id,
                'store_name': store_name,
                'idle_time': idle_time,
                'file_count': file_count
            }
    
    def finish_processing(self, folder_id):
        """Mark folder as finished processing"""
        with self.lock:
            if self.currently_processing == folder_id:
                self.currently_processing = None
                
                # Check if needs reprocessing
                if folder_id in self.needs_reprocessing:
                    self.needs_reprocessing.remove(folder_id)
                    # Keep in queue for reprocessing
                    print(f"[Queue] ↩️  {self.activity_tracker.get_store_name(folder_id)} will be reprocessed due to new activity")
                    return True  # Needs reprocessing
                else:
                    # Remove from queue - successfully processed
                    if folder_id in self.queue_items:
                        del self.queue_items[folder_id]
                    self.activity_tracker.reset_folder(folder_id)
                    return False  # Done
        return False
    
    def get_queue_status(self):
        """Get current queue status for display"""
        with self.lock:
            status = []
            for folder_id, item in self.queue_items.items():
                store_name = self.activity_tracker.get_store_name(folder_id)
                file_count = self.activity_tracker.get_file_count(folder_id)
                idle_time = self.activity_tracker.get_idle_time(folder_id)
                
                status.append({
                    'store_name': store_name,
                    'file_count': file_count,
                    'idle_time': idle_time,
                    'processing': folder_id == self.currently_processing
                })
            
            # Sort by idle time
            status.sort(key=lambda x: x['idle_time'], reverse=True)
            return status


def get_all_thumb_folders():
    """Read CSV and generate paths to all Thumb folders"""
    thumb_folders = {}
    
    if not os.path.exists(CSV_FILE):
        print(f"Warning: {CSV_FILE} not found. Using default folder only.")
        return {}
    
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                folder_id = row['Folder']
                store_name = row['Store']
                thumb_path = os.path.join(BASE_THUMB_PATH, folder_id, 'Thumb')
                
                # Only add if folder exists
                if os.path.exists(thumb_path):
                    thumb_folders[store_name] = thumb_path
                else:
                    print(f"Note: Thumb folder not found for {store_name}: {thumb_path}")
        
        return thumb_folders
        
    except Exception as e:
        print(f"Error reading {CSV_FILE}: {e}")
        return {}


class DatFileHandler(FileSystemEventHandler):
    """Handler for monitoring .dat file creation"""
    
    def __init__(self, baseline_time, monitor_folder, decode_files=True, folder_label="", processed_files=None, executor=None, activity_tracker=None, processing_queue=None):
        super().__init__()
        self.baseline_time = baseline_time
        self.monitor_folder = monitor_folder
        self.decode_files = decode_files
        self.folder_label = folder_label
        self.processed_files = processed_files if processed_files is not None else set()
        self.lock = threading.Lock()
        self.executor = executor  # Thread pool for async decoding
        self.activity_tracker = activity_tracker  # For thumbnail mode queue
        self.processing_queue = processing_queue  # For thumbnail mode queue
        # Load folder mappings for msgattach mode
        self.folder_to_store = self._load_folder_mappings() if decode_files else {}
    
    def _load_folder_mappings(self):
        """Load folder ID to store name mappings from CSV"""
        mappings = {}
        if os.path.exists(CSV_FILE):
            try:
                with open(CSV_FILE, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        mappings[row['Folder']] = row['Store']
            except Exception:
                pass
        return mappings
    
    def _get_store_name_from_path(self, file_path):
        """Extract store name from file path"""
        try:
            parts = file_path.split(os.sep)
            if 'MsgAttach' in parts:
                msgattach_idx = parts.index('MsgAttach')
                if msgattach_idx + 1 < len(parts):
                    folder_id = parts[msgattach_idx + 1]
                    return self.folder_to_store.get(folder_id, folder_id)
        except Exception:
            pass
        return None
    
    def decode_file_async(self, file_path, output_path):
        """Decode a file asynchronously in the thread pool"""
        try:
            decode_wechat_dat(file_path, output_path)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get store name for msgattach mode
            store_name = self._get_store_name_from_path(file_path)
            store_name_info = f" [{store_name}]" if store_name else ""
            
            print(f"[{timestamp}]{store_name_info} ✓ Decoded: {output_path}")
            
            # Auto-annotate if available and store name exists
            if AUTO_ANNOTATION_AVAILABLE and store_name and os.path.exists(output_path):
                try:
                    # Set paths relative to asian_grocer_scrapers repo (using cache_data folder)
                    annotations_file = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache_data\image_annotations.json'
                    duplicates_report = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache_data\duplicates_report.txt'
                    store_date_rules = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache\store_date_rules.csv'
                    
                    if auto_annotate_duplicate_image(output_path, store_name, annotations_file, 
                                                     duplicates_report, store_date_rules):
                        print(f"  ✓ Auto-annotated: {os.path.basename(output_path)}")
                except Exception as annotate_error:
                    # Don't fail decoding if annotation fails
                    pass
        except Exception as decode_error:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get store name for msgattach mode
            store_name = self._get_store_name_from_path(file_path)
            store_name_info = f" [{store_name}]" if store_name else ""
            
            print(f"[{timestamp}]{store_name_info} ✗ Decode failed for {file_path}: {decode_error}")
    
    def on_created(self, event):
        """Called when a file or directory is created"""
        if event.is_directory:
            return
        
        # Check if it's a .dat file
        if event.src_path.lower().endswith('.dat'):
            # For msgattach mode, only decode files in Image folders
            if self.decode_files and '\\Image\\' not in event.src_path:
                return
            
            # Get file creation/modification time
            try:
                with self.lock:
                    # Skip if already processed
                    if event.src_path in self.processed_files:
                        return
                    self.processed_files.add(event.src_path)
                
                # For thumbnail mode (decode_files=False), check file size
                if not self.decode_files:
                    try:
                        file_size = os.path.getsize(event.src_path)
                        # Skip files larger than 15KB for thumbnail mode
                        if file_size > 15 * 1024:  # 15KB in bytes
                            return
                    except Exception as size_error:
                        # If we can't get size, skip the file
                        return
                
                file_mtime = datetime.fromtimestamp(os.path.getmtime(event.src_path))
                
                # Only report if file is newer than baseline
                if file_mtime >= self.baseline_time:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    file_time_str = file_mtime.strftime("%Y-%m-%d %H:%M:%S")
                    folder_info = f" [{self.folder_label}]" if self.folder_label else ""
                    
                    # Show file size for thumbnail mode
                    size_info = ""
                    if not self.decode_files:
                        try:
                            file_size = os.path.getsize(event.src_path)
                            size_kb = file_size / 1024
                            size_info = f" (size: {size_kb:.1f} KB)"
                        except:
                            pass
                    
                    # Get store name for msgattach mode
                    store_name_info = ""
                    if self.decode_files:
                        store_name = self._get_store_name_from_path(event.src_path)
                        if store_name:
                            store_name_info = f" [{store_name}]"
                    
                    print(f"[{timestamp}]{folder_info}{store_name_info} New .dat file detected (on_created): {event.src_path}{size_info}")
                    print(f"  File timestamp: {file_time_str}")
                    
                    # For thumbnail mode, update activity tracker and queue
                    if not self.decode_files and self.activity_tracker and self.processing_queue:
                        folder_id, store_name = self.activity_tracker.update_activity(event.src_path)
                        if folder_id and store_name:
                            self.processing_queue.add_or_update(folder_id, store_name)
                            file_count = self.activity_tracker.get_file_count(folder_id)
                            
                            # Check if currently processing this folder
                            if self.processing_queue.mark_new_activity_during_processing(folder_id):
                                print(f"  ⚠️  Still processing - will re-queue after completion")
                            else:
                                queue_pos = len(self.processing_queue.queue_items)
                                print(f"  ⏭️  Added to processing queue (position: {queue_pos}, {file_count} files total)")
                    
                    # Auto-decode the file if enabled (asynchronously if executor available)
                    if self.decode_files:
                        # Create output path mirroring the folder structure
                        relative_path = os.path.relpath(event.src_path, self.monitor_folder)
                        output_path = os.path.join(OUTPUT_BASE, relative_path)
                        output_path = output_path.replace(".dat", ".jpg")
                        
                        # Create output directory if needed
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        
                        if self.executor:
                            # Submit to thread pool for async processing
                            print(f"  ⏳ Queued for decoding...")
                            self.executor.submit(self.decode_file_async, event.src_path, output_path)
                        else:
                            # Fallback to synchronous decoding if no executor
                            try:
                                decode_wechat_dat(event.src_path, output_path)
                                print(f"  ✓ Decoded to: {output_path}")
                                
                                # Auto-annotate if available
                                if AUTO_ANNOTATION_AVAILABLE:
                                    try:
                                        store_name = self._get_store_name_from_path(event.src_path)
                                        if store_name and os.path.exists(output_path):
                                            annotations_file = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache_data\image_annotations.json'
                                            duplicates_report = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache_data\duplicates_report.txt'
                                            store_date_rules = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache\store_date_rules.csv'
                                            
                                            if auto_annotate_duplicate_image(output_path, store_name, annotations_file,
                                                                             duplicates_report, store_date_rules):
                                                print(f"  ✓ Auto-annotated: {os.path.basename(output_path)}")
                                    except Exception:
                                        pass  # Don't fail decoding if annotation fails
                            except Exception as decode_error:
                                print(f"  ✗ Decode failed: {decode_error}")
            except Exception as e:
                print(f"Error checking file time: {e}")
    
    def on_modified(self, event):
        """Called when a file is modified"""
        if event.is_directory:
            return
        
        # Skip on_modified for non-decoding modes (thumbnail mode)
        # These files will be caught by polling instead
        if not self.decode_files:
            return
        
        if event.src_path.lower().endswith('.dat'):
            # For msgattach mode, only decode files in Image folders
            if self.decode_files and '\\Image\\' not in event.src_path:
                return
            
            try:
                with self.lock:
                    # Skip if already processed
                    if event.src_path in self.processed_files:
                        return
                    self.processed_files.add(event.src_path)
                
                file_mtime = datetime.fromtimestamp(os.path.getmtime(event.src_path))
                
                # Only report if file is newer than baseline
                if file_mtime >= self.baseline_time:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    file_time_str = file_mtime.strftime("%Y-%m-%d %H:%M:%S")
                    folder_info = f" [{self.folder_label}]" if self.folder_label else ""
                    
                    # Get store name for msgattach mode
                    store_name_info = ""
                    if self.decode_files:
                        store_name = self._get_store_name_from_path(event.src_path)
                        if store_name:
                            store_name_info = f" [{store_name}]"
                    
                    print(f"[{timestamp}]{folder_info}{store_name_info} .dat file detected (on_modified): {event.src_path}")
                    print(f"  File timestamp: {file_time_str}")
                    
                    # Auto-decode the file if enabled (asynchronously if executor available)
                    if self.decode_files:
                        # Create output path mirroring the folder structure
                        relative_path = os.path.relpath(event.src_path, self.monitor_folder)
                        output_path = os.path.join(OUTPUT_BASE, relative_path)
                        output_path = output_path.replace(".dat", ".jpg")
                        
                        # Create output directory if needed
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        
                        if self.executor:
                            # Submit to thread pool for async processing
                            print(f"  ⏳ Queued for decoding...")
                            self.executor.submit(self.decode_file_async, event.src_path, output_path)
                        else:
                            # Fallback to synchronous decoding if no executor
                            try:
                                decode_wechat_dat(event.src_path, output_path)
                                print(f"  ✓ Decoded to: {output_path}")
                            except Exception as decode_error:
                                print(f"  ✗ Decode failed: {decode_error}")
            except Exception as e:
                print(f"Error checking file time: {e}")


def scan_existing_files(folder, baseline_time, folder_name="", decode_files=True, processed_files=None, activity_tracker=None, processing_queue=None):
    """Scan for existing .dat files modified after baseline time"""
    folder_label = f" in {folder_name}" if folder_name else ""
    print(f"Scanning{folder_label} for existing .dat files modified after {baseline_time.strftime('%Y-%m-%d %H:%M:%S')}...\n")

    if processed_files is None:
        processed_files = set()

    found_count = 0
    decoded_count = 0
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.lower().endswith('.dat'):
                file_path = os.path.join(root, file)
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                    if file_mtime >= baseline_time:
                        file_time_str = file_mtime.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"Found: {file_path}")
                        print(f"  File timestamp: {file_time_str}")
                        found_count += 1

                        # Mark as processed
                        processed_files.add(file_path)

                        # For thumbnail mode, update activity tracker and queue
                        if not decode_files and activity_tracker and processing_queue:
                            # Check file size for thumbnail mode
                            try:
                                file_size = os.path.getsize(file_path)
                                # Skip files larger than 15KB for thumbnail mode
                                if file_size > 15 * 1024:  # 15KB in bytes
                                    print(f"  Skipping file (size: {file_size/1024:.1f} KB > 15KB limit)")
                                    continue
                                else:
                                    size_info = f" (size: {file_size/1024:.1f} KB)"
                                    print(f"  File size: {file_size/1024:.1f} KB")
                            except Exception as size_error:
                                print(f"  Could not get file size: {size_error}")
                                continue

                            # Update activity tracker and queue
                            folder_id, store_name = activity_tracker.update_activity(file_path)
                            if folder_id and store_name:
                                processing_queue.add_or_update(folder_id, store_name)
                                file_count = activity_tracker.get_file_count(folder_id)

                                # Check if currently processing this folder
                                if processing_queue.mark_new_activity_during_processing(folder_id):
                                    print(f"  ⚠️  Still processing - will re-queue after completion")
                                else:
                                    queue_pos = len(processing_queue.queue_items)
                                    print(f"  ⏭️  Added to processing queue (position: {queue_pos}, {file_count} files total)")

                        # Auto-decode the file if enabled
                        if decode_files:
                            try:
                                # Create output path mirroring the folder structure
                                relative_path = os.path.relpath(file_path, folder)
                                output_path = os.path.join(OUTPUT_BASE, relative_path)
                                output_path = output_path.replace(".dat", ".jpg")

                                # Create output directory if needed
                                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                                # Decode the file
                                decode_wechat_dat(file_path, output_path)
                                print(f"  ✓ Decoded to: {output_path}")
                                decoded_count += 1
                                
                                # Auto-annotate if available
                                if AUTO_ANNOTATION_AVAILABLE:
                                    try:
                                        # Get store name from path
                                        parts = file_path.split(os.sep)
                                        store_name = None
                                        if 'MsgAttach' in parts:
                                            msgattach_idx = parts.index('MsgAttach')
                                            if msgattach_idx + 1 < len(parts):
                                                folder_id = parts[msgattach_idx + 1]
                                                # Try to get store name from CSV
                                                if os.path.exists(CSV_FILE):
                                                    try:
                                                        with open(CSV_FILE, 'r', encoding='utf-8') as f:
                                                            reader = csv.DictReader(f)
                                                            for row in reader:
                                                                if row['Folder'] == folder_id:
                                                                    store_name = row['Store']
                                                                    break
                                                    except:
                                                        pass
                                                if not store_name:
                                                    store_name = folder_id
                                        
                                        if store_name and os.path.exists(output_path):
                                            annotations_file = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache_data\image_annotations.json'
                                            duplicates_report = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache_data\duplicates_report.txt'
                                            store_date_rules = r'C:\Users\henry\source\repos\asian_grocer_scrapers\cache\store_date_rules.csv'
                                            
                                            if auto_annotate_duplicate_image(output_path, store_name, annotations_file,
                                                                             duplicates_report, store_date_rules):
                                                print(f"  ✓ Auto-annotated: {os.path.basename(output_path)}")
                                    except Exception:
                                        pass  # Don't fail decoding if annotation fails
                            except Exception as decode_error:
                                print(f"  ✗ Decode failed: {decode_error}")
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    if found_count > 0:
        print(f"\nFound {found_count} existing .dat file(s){folder_label} modified after baseline time.")
        if decode_files:
            print(f"Successfully decoded {decoded_count} file(s).\n")
        else:
            print()
    else:
        print(f"No existing .dat files found{folder_label} after baseline time.\n")


def polling_scan(folders_dict, baseline_time, decode_files, handlers_dict, stop_event, poll_interval=5):
    """
    Periodically scan folders for new .dat files that might have been missed by event handlers.
    This catches files that the watchdog on_created event might miss on Windows.
    """
    while not stop_event.is_set():
        time.sleep(poll_interval)
        
        for folder_name, folder_path in folders_dict.items():
            handler = handlers_dict.get(folder_name)
            if not handler:
                continue
            
            try:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        if file.lower().endswith('.dat'):
                            file_path = os.path.join(root, file)
                            
                            # For msgattach mode, only decode files in Image folders
                            if decode_files and '\\Image\\' not in file_path:
                                continue
                            
                            # Check if already processed
                            with handler.lock:
                                if file_path in handler.processed_files:
                                    continue
                                
                                # For thumbnail mode, check file size
                                if not decode_files:
                                    try:
                                        file_size = os.path.getsize(file_path)
                                        # Skip files larger than 15KB for thumbnail mode
                                        if file_size > 15 * 1024:  # 15KB in bytes
                                            continue
                                    except:
                                        continue
                                
                                # Check file modification time
                                try:
                                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                                    
                                    if file_mtime >= baseline_time:
                                        # Mark as processed first to avoid race condition
                                        handler.processed_files.add(file_path)
                                        
                                        # Report the file
                                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        file_time_str = file_mtime.strftime("%Y-%m-%d %H:%M:%S")
                                        folder_info = f" [{folder_name}]" if folder_name else ""
                                        
                                        # Show file size for thumbnail mode
                                        size_info = ""
                                        if not decode_files:
                                            try:
                                                file_size = os.path.getsize(file_path)
                                                size_kb = file_size / 1024
                                                size_info = f" (size: {size_kb:.1f} KB)"
                                            except:
                                                pass
                                        
                                        print(f"[{timestamp}]{folder_info} .dat file detected (polling): {file_path}{size_info}")
                                        print(f"  File timestamp: {file_time_str}")
                                        
                                        # For thumbnail mode, update activity tracker and queue
                                        if not decode_files and handler.activity_tracker and handler.processing_queue:
                                            folder_id, store_name = handler.activity_tracker.update_activity(file_path)
                                            if folder_id and store_name:
                                                handler.processing_queue.add_or_update(folder_id, store_name)
                                                file_count = handler.activity_tracker.get_file_count(folder_id)
                                                
                                                # Check if currently processing this folder
                                                if handler.processing_queue.mark_new_activity_during_processing(folder_id):
                                                    print(f"  ⚠️  Still processing - will re-queue after completion")
                                                else:
                                                    queue_pos = len(handler.processing_queue.queue_items)
                                                    print(f"  ⏭️  Added to processing queue (position: {queue_pos}, {file_count} files total)")
                                        
                                        # Auto-decode the file if enabled
                                        if decode_files:
                                            try:
                                                relative_path = os.path.relpath(file_path, folder_path)
                                                output_path = os.path.join(OUTPUT_BASE, relative_path)
                                                output_path = output_path.replace(".dat", ".jpg")
                                                
                                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                                decode_wechat_dat(file_path, output_path)
                                                print(f"  ✓ Decoded to: {output_path}")
                                                
                                                # Auto-annotate if available
                                                if AUTO_ANNOTATION_AVAILABLE:
                                                    try:
                                                        # Get store name from path
                                                        parts = file_path.split(os.sep)
                                                        store_name = None
                                                        if 'MsgAttach' in parts:
                                                            msgattach_idx = parts.index('MsgAttach')
                                                            if msgattach_idx + 1 < len(parts):
                                                                folder_id = parts[msgattach_idx + 1]
                                                                # Try to get store name from CSV
                                                                if os.path.exists(CSV_FILE):
                                                                    try:
                                                                        with open(CSV_FILE, 'r', encoding='utf-8') as f:
                                                                            reader = csv.DictReader(f)
                                                                            for row in reader:
                                                                                if row['Folder'] == folder_id:
                                                                                    store_name = row['Store']
                                                                                    break
                                                                    except:
                                                                        pass
                                                                if not store_name:
                                                                    store_name = folder_id
                                                        
                                                        if store_name and os.path.exists(output_path):
                                                            annotations_file = r'C:\Users\henry\source\repos\asian_grocer_scrapers\image_annotations.json'
                                                            duplicates_report = r'C:\Users\henry\source\repos\asian_grocer_scrapers\duplicates_report.txt'
                                                            store_date_rules = r'C:\Users\henry\source\repos\asian_grocer_scrapers\store_date_rules.csv'
                                                            
                                                            if auto_annotate_duplicate_image(output_path, store_name, annotations_file,
                                                                                             duplicates_report, store_date_rules):
                                                                print(f"  ✓ Auto-annotated: {os.path.basename(output_path)}")
                                                    except Exception:
                                                        pass  # Don't fail decoding if annotation fails
                                            except Exception as decode_error:
                                                print(f"  ✗ Decode failed: {decode_error}")
                                except Exception as e:
                                    pass  # Skip files we can't read
            except Exception as e:
                pass  # Skip folders we can't access


def queue_processor_thread(processing_queue, stop_event):
    """Background thread that processes the queue of folders"""
    print("[Queue Processor] Started\n")
    
    while not stop_event.is_set():
        try:
            # Debug: Show current queue state
            queue_status = processing_queue.get_queue_status()
            if queue_status:
                print(f"[Queue Debug] Current queue: {len(queue_status)} folders")
                for item in queue_status:
                    print(f"  - {item['store_name']}: {item['file_count']} files, {item['idle_time']:.0f}s idle, processing={item['processing']}")
            
            # Check queue for next item to process
            next_item = processing_queue.get_next_to_process()
            
            if next_item:
                folder_id = next_item['folder_id']
                store_name = next_item['store_name']
                idle_time = next_item['idle_time']
                file_count = next_item['file_count']
                
                print(f"\n{'='*60}")
                print(f"[Queue] {store_name} has been idle for {idle_time:.0f} seconds")
                print(f"[Queue] Processing {file_count} files from {store_name}")
                
                # Show current queue status
                queue_status = processing_queue.get_queue_status()
                status_str = ", ".join([
                    f"{item['store_name']} ({'processing' if item['processing'] else str(int(item['idle_time'])) + 's idle'})"
                    for item in queue_status[:5]  # Show first 5
                ])
                print(f"[Queue] Status: [{status_str}]")
                print(f"{'='*60}")
                
                # Start auto-navigation Python script directly
                print(f"[Queue] 🚀 Starting: python wechat_auto_navigator.py --chat {store_name} --prod --file-count {file_count}\n")
                
                try:
                    # Run the Python script directly with the store name, prod mode, and file count
                    result = subprocess.run(
                        ['python', 'wechat_auto_navigator.py', '--chat', store_name, '--prod', '--file-count', str(file_count)],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        timeout=600  # 10 minute timeout
                    )

                    # Print any output from the navigator script
                    if result.stdout:
                        print(f"[Navigator Output for {store_name}]")
                        print(result.stdout)
                    if result.stderr:
                        print(f"[Navigator Errors for {store_name}]")
                        print(result.stderr)

                    print(f"\n[Queue] ✓ Completed processing {store_name}")
                    if result.returncode != 0:
                        print(f"[Queue] ⚠️  Exit code: {result.returncode}")
                    
                except subprocess.TimeoutExpired:
                    print(f"\n[Queue] ⚠️  Timeout processing {store_name} (10 minutes)")
                except Exception as e:
                    print(f"\n[Queue] ✗ Error processing {store_name}: {e}")
                
                # Mark as finished
                needs_reprocessing = processing_queue.finish_processing(folder_id)
                
                if not needs_reprocessing:
                    print(f"[Queue] ✅ {store_name} completed and removed from queue")
                
                print()
            
            # Sleep before checking again
            time.sleep(QUEUE_CHECK_INTERVAL)
            
        except Exception as e:
            print(f"[Queue Processor] Error: {e}")
            time.sleep(QUEUE_CHECK_INTERVAL)
    
    print("[Queue Processor] Stopped")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Monitor WeChat folder for new .dat files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python wechat_file_monitor.py
    Monitor MsgAttach folder from current time (default)
    
  python wechat_file_monitor.py --folder thumbnail
    Monitor Thumbnail folder and only print file names
    
  python wechat_file_monitor.py --start-time "20241104 10:30"
    Monitor MsgAttach folder after Nov 4, 2024 10:30 AM
    
  python wechat_file_monitor.py --folder thumbnail --start-time "20241104 10:30"
    Monitor Thumbnail folder after Nov 4, 2024 10:30 AM
        '''
    )
    
    parser.add_argument(
        '--folder',
        type=str,
        choices=['msgattach', 'thumbnail'],
        default='msgattach',
        help='Folder to monitor: msgattach (default, with decoding) or thumbnail (print only)'
    )
    
    parser.add_argument(
        '--start-time',
        type=str,
        help='Start time in format "YYYYmmdd HH:MM" (e.g., "20241104 10:30")'
    )
    
    return parser.parse_args()


def start_monitoring(baseline_time=None, folder_choice='msgattach'):
    """Start monitoring the selected folder(s) for new .dat files"""
    
    # Use current time if no baseline provided
    if baseline_time is None:
        baseline_time = datetime.now()
    
    # Select folders based on choice
    if folder_choice == 'thumbnail':
        # Get all Thumb folders from CSV
        thumb_folders = get_all_thumb_folders()
        
        if not thumb_folders:
            print("Error: No Thumb folders found in CSV or folders don't exist")
            return
        
        folders_to_monitor = thumb_folders  # Dict: {store_name: folder_path}
        decode_files = False  # Thumbnail folders only print names
        mode_name = "Thumbnail (All Stores)"
        
    else:
        # Monitor single MsgAttach folder
        folders_to_monitor = {"MsgAttach": MONITOR_FOLDER}
        decode_files = True  # MsgAttach folder decodes
        mode_name = "MsgAttach"
    
    # Check if folders exist
    existing_folders = {}
    for name, path in folders_to_monitor.items():
        if os.path.exists(path):
            existing_folders[name] = path
        else:
            print(f"Warning: Folder does not exist for {name}: {path}")
    
    if not existing_folders:
        print("Error: No valid folders to monitor")
        return
    
    print(f"WeChat File Monitor")
    print(f"=" * 50)
    print(f"Mode: {mode_name} - {'Print only' if not decode_files else 'Decode to JPG'}")
    print(f"Baseline time: {baseline_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Monitoring {len(existing_folders)} folder(s):")
    for name, path in existing_folders.items():
        print(f"  [{name}]: {path}")
    print(f"Detection: Event-based + Polling backup (every 5s)")
    if decode_files:
        print(f"Decoding: Async thread pool (max 4 concurrent)")
    print(f"=" * 50)
    print()
    
    # Create shared processed files set
    processed_files = set()
    
    # Create thread pool executor for async decoding (only for msgattach mode)
    executor = None
    if decode_files:
        executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="Decoder")
        print("✓ Async decoding thread pool initialized (4 workers)\n")
    
    # Create activity tracker and processing queue (only for thumbnail mode)
    activity_tracker = None
    processing_queue = None
    queue_processor = None
    if not decode_files:  # Thumbnail mode
        activity_tracker = FolderActivityTracker()
        processing_queue = ProcessingQueue(activity_tracker)
        print(f"✓ Auto-navigation queue initialized")
        print(f"  - Idle threshold: {IDLE_THRESHOLD_SECONDS}s")
        print(f"  - Min files to process: {MIN_FILES_TO_PROCESS}")
        print(f"  - Queue check interval: {QUEUE_CHECK_INTERVAL}s\n")
    
    # First, scan for existing files in all folders
    for name, path in existing_folders.items():
        scan_existing_files(path, baseline_time, name, decode_files, processed_files, activity_tracker, processing_queue)
    
    print("Starting continuous monitoring...")
    print("Press Ctrl+C to stop monitoring\n")
    
    # Create event handlers and observer for each folder
    observer = Observer()
    handlers_dict = {}
    for name, path in existing_folders.items():
        event_handler = DatFileHandler(baseline_time, path, decode_files, folder_label=name, 
                                       processed_files=processed_files, executor=executor,
                                       activity_tracker=activity_tracker, processing_queue=processing_queue)
        handlers_dict[name] = event_handler
        observer.schedule(event_handler, path, recursive=True)
    
    # Start monitoring
    observer.start()
    
    # Start polling thread to catch files missed by events
    stop_event = threading.Event()
    polling_thread = threading.Thread(
        target=polling_scan,
        args=(existing_folders, baseline_time, decode_files, handlers_dict, stop_event),
        daemon=True
    )
    polling_thread.start()
    
    # Start queue processor thread for thumbnail mode
    queue_thread = None
    if not decode_files and processing_queue:
        queue_thread = threading.Thread(
            target=queue_processor_thread,
            args=(processing_queue, stop_event),
            daemon=True
        )
        queue_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        stop_event.set()
        observer.stop()
    
    observer.join()
    polling_thread.join(timeout=2)
    
    # Wait for queue processor to finish current task
    if queue_thread:
        print("Waiting for queue processor to finish...")
        queue_thread.join(timeout=5)
        print("Queue processor stopped.")
    
    # Shutdown executor and wait for pending tasks
    if executor:
        print("Waiting for pending decoding tasks to complete...")
        executor.shutdown(wait=True, cancel_futures=False)
        print("All decoding tasks completed.")
    
    print("Monitor stopped.")


if __name__ == "__main__":
    args = parse_arguments()
    
    # Parse start time if provided
    baseline_time = None
    if args.start_time:
        try:
            # Parse format: YYYYmmdd HH:MM
            baseline_time = datetime.strptime(args.start_time, "%Y%m%d %H:%M")
            print(f"Using provided start time: {baseline_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except ValueError:
            print(f"Error: Invalid time format. Expected 'YYYYmmdd HH:MM' (e.g., '20241104 10:30')")
            print(f"Received: '{args.start_time}'")
            exit(1)
    else:
        baseline_time = datetime.now()
        print(f"No start time provided. Using current time: {baseline_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    start_monitoring(baseline_time, args.folder)


r"""
USAGE DOCUMENTATION
===================

This script monitors WeChat folders for new .dat files and can optionally decode them to JPG images.

FEATURES:
---------
1. Monitor MsgAttach folder (default) - automatically decodes .dat files to JPG
2. Monitor Thumbnail folder - only prints file names without decoding
3. Filter files by modification time (current time or user-specified)
4. Continuous monitoring with real-time detection
5. Initial scan of existing files before starting continuous monitoring

COMMAND LINE OPTIONS:
---------------------
--folder <msgattach|thumbnail>
    Choose which folder to monitor:
    - msgattach: (default) Monitors MsgAttach folder and decodes .dat files to JPG
    - thumbnail: Monitors ALL Thumb folders from wechat_folder_mappings.csv and only prints file names (no decoding)

--start-time "YYYYmmdd HH:MM"
    Specify baseline time to filter files. Only files modified after this time will be reported.
    Format: "YYYYmmdd HH:MM" (e.g., "20241105 14:30")
    If not provided, uses current time as baseline.

USAGE EXAMPLES:
---------------

1. Monitor MsgAttach folder from current time (default behavior):
   python wechat_file_monitor.py

2. Monitor ALL Thumbnail folders (from CSV) and only print file names:
   python wechat_file_monitor.py --folder thumbnail

3. Monitor MsgAttach folder for files modified after specific time:
   python wechat_file_monitor.py --start-time "20241105 10:30"

4. Monitor ALL Thumbnail folders for files modified after specific time:
   python wechat_file_monitor.py --folder thumbnail --start-time "20241105 14:00"

5. View help information:
   python wechat_file_monitor.py --help

MONITORED FOLDERS:
------------------
MsgAttach: C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach
Thumbnail: ALL Thumb folders read from wechat_folder_mappings.csv
           (Multiple stores: Meadowland, Wairau, Albany, Smart-聪明超市东区, etc.)

OUTPUT:
-------
- Decoded images are saved to: C:\Users\henry\OneDrive\Documents\WeChat Decoded Images2
- Output maintains the same folder structure as the source
- .dat files are converted to .jpg format

BEHAVIOR:
---------
1. On startup:
   - Displays configuration (folder, mode, baseline time)
   - Initializes async thread pool (4 workers) for MsgAttach mode
   - Scans for existing files modified after baseline time
   - Reports found files and decodes them (if MsgAttach mode)

2. During monitoring:
   - Uses DUAL detection method for reliability:
     a) Event-based: Watches for on_created and on_modified events in real-time
     b) Polling backup: Scans every 5 seconds to catch files missed by events
   - Reports files with detection method in the log (on_created/on_modified/polling)
   - Prevents duplicate processing using shared tracking set
   - MsgAttach mode behavior:
     * Files are immediately detected and reported
     * Decoding happens asynchronously in background thread pool
     * Shows "⏳ Queued for decoding..." immediately
     * Shows "✓ Decoded" with timestamp when complete
     * Can handle burst of files without blocking
     * Up to 4 files decoded concurrently
   - Thumbnail mode behavior:
     * Only prints file names (no decoding)
     * Shows file size in KB
     * Filters out files larger than 15KB
     * Only reports small thumbnail files
     * AUTO-NAVIGATION QUEUE SYSTEM:
       - Tracks activity for each chat folder
       - Automatically queues folders when .dat files detected
       - Shows "⏭️ Added to processing queue" with position and file count
       - When folder idle for 60 seconds:
         + Auto-launches: run_wechat_navigator.bat {StoreName} prod
         + Downloads all images from that chat automatically
         + Shows queue status and progress
       - If new files arrive during processing:
         + Shows "⚠️ Still processing - will re-queue"
         + Re-processes folder after current run completes
       - Only processes folders with 3+ files (configurable)
       - Processes one chat at a time (sequential, not parallel)
       - Queue automatically prioritizes by idle time

3. To stop:
   - Press Ctrl+C to gracefully stop monitoring
   - Waits for queue processor to finish current chat
   - Waits for all pending decoding tasks to complete
   - Ensures no files are left partially processed

NOTES:
------
- MsgAttach mode: Monitors single folder with full decoding to JPG
- Thumbnail mode: Monitors ALL Thumb folders from wechat_folder_mappings.csv (print-only, no decoding)
- Auto-navigation queue configuration (top of file):
  * IDLE_THRESHOLD_SECONDS = 60  (wait time before processing)
  * MIN_FILES_TO_PROCESS = 3  (minimum files to trigger processing)
  * QUEUE_CHECK_INTERVAL = 5  (seconds between queue checks)
- File names printed include store name in brackets: [StoreName] for easy identification
- Requires wechat_folder_mappings.csv in same directory for thumbnail monitoring
- The baseline time filter applies to both initial scan and continuous monitoring
- File timestamps are based on file modification time
"""
