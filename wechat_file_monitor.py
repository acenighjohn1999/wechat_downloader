import os
import time
import argparse
import csv
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from wechat_decoder import decode_wechat_dat

# Folders to monitor
MONITOR_FOLDER = r"C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach"
BASE_THUMB_PATH = r"C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach"
CSV_FILE = "wechat_folder_mappings.csv"

# Output folder for decoded images
OUTPUT_BASE = r"C:\Users\henry\OneDrive\Documents\WeChat Decoded Images2"


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
    
    def __init__(self, baseline_time, monitor_folder, decode_files=True, folder_label="", processed_files=None):
        super().__init__()
        self.baseline_time = baseline_time
        self.monitor_folder = monitor_folder
        self.decode_files = decode_files
        self.folder_label = folder_label
        self.processed_files = processed_files if processed_files is not None else set()
        self.lock = threading.Lock()
    
    def on_created(self, event):
        """Called when a file or directory is created"""
        if event.is_directory:
            return
        
        # Check if it's a .dat file
        if event.src_path.lower().endswith('.dat'):
            # Get file creation/modification time
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
                    print(f"[{timestamp}]{folder_info} New .dat file detected (on_created): {event.src_path}")
                    print(f"  File timestamp: {file_time_str}")
                    
                    # Auto-decode the file if enabled
                    if self.decode_files:
                        try:
                            # Create output path mirroring the folder structure
                            relative_path = os.path.relpath(event.src_path, self.monitor_folder)
                            output_path = os.path.join(OUTPUT_BASE, relative_path)
                            output_path = output_path.replace(".dat", ".jpg")
                            
                            # Create output directory if needed
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            
                            # Decode the file
                            decode_wechat_dat(event.src_path, output_path)
                            print(f"  ✓ Decoded to: {output_path}")
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
                    print(f"[{timestamp}]{folder_info} .dat file detected (on_modified): {event.src_path}")
                    print(f"  File timestamp: {file_time_str}")
                    
                    # Auto-decode the file if enabled
                    if self.decode_files:
                        try:
                            # Create output path mirroring the folder structure
                            relative_path = os.path.relpath(event.src_path, self.monitor_folder)
                            output_path = os.path.join(OUTPUT_BASE, relative_path)
                            output_path = output_path.replace(".dat", ".jpg")
                            
                            # Create output directory if needed
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            
                            # Decode the file
                            decode_wechat_dat(event.src_path, output_path)
                            print(f"  ✓ Decoded to: {output_path}")
                        except Exception as decode_error:
                            print(f"  ✗ Decode failed: {decode_error}")
            except Exception as e:
                print(f"Error checking file time: {e}")


def scan_existing_files(folder, baseline_time, folder_name="", decode_files=True, processed_files=None):
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
                            
                            # Check if already processed
                            with handler.lock:
                                if file_path in handler.processed_files:
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
                                        print(f"[{timestamp}]{folder_info} .dat file detected (polling): {file_path}")
                                        print(f"  File timestamp: {file_time_str}")
                                        
                                        # Auto-decode the file if enabled
                                        if decode_files:
                                            try:
                                                relative_path = os.path.relpath(file_path, folder_path)
                                                output_path = os.path.join(OUTPUT_BASE, relative_path)
                                                output_path = output_path.replace(".dat", ".jpg")
                                                
                                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                                decode_wechat_dat(file_path, output_path)
                                                print(f"  ✓ Decoded to: {output_path}")
                                            except Exception as decode_error:
                                                print(f"  ✗ Decode failed: {decode_error}")
                                except Exception as e:
                                    pass  # Skip files we can't read
            except Exception as e:
                pass  # Skip folders we can't access


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
    print(f"=" * 50)
    print()
    
    # Create shared processed files set
    processed_files = set()
    
    # First, scan for existing files in all folders
    for name, path in existing_folders.items():
        scan_existing_files(path, baseline_time, name, decode_files, processed_files)
    
    print("Starting continuous monitoring...")
    print("Press Ctrl+C to stop monitoring\n")
    
    # Create event handlers and observer for each folder
    observer = Observer()
    handlers_dict = {}
    for name, path in existing_folders.items():
        event_handler = DatFileHandler(baseline_time, path, decode_files, folder_label=name, processed_files=processed_files)
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
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        stop_event.set()
        observer.stop()
    
    observer.join()
    polling_thread.join(timeout=2)
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
   - Scans for existing files modified after baseline time
   - Reports found files and decodes them (if MsgAttach mode)

2. During monitoring:
   - Uses DUAL detection method for reliability:
     a) Event-based: Watches for on_created and on_modified events in real-time
     b) Polling backup: Scans every 5 seconds to catch files missed by events
   - Reports files with detection method in the log (on_created/on_modified/polling)
   - Prevents duplicate processing using shared tracking set
   - Auto-decodes files in MsgAttach mode
   - Only prints file names in Thumbnail mode

3. To stop:
   - Press Ctrl+C to gracefully stop monitoring

NOTES:
------
- MsgAttach mode: Monitors single folder with full decoding to JPG
- Thumbnail mode: Monitors ALL Thumb folders from wechat_folder_mappings.csv (print-only, no decoding)
- File names printed include store name in brackets: [StoreName] for easy identification
- Requires wechat_folder_mappings.csv in same directory for thumbnail monitoring
- The baseline time filter applies to both initial scan and continuous monitoring
- File timestamps are based on file modification time
"""
