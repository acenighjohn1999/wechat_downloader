import os
import time
import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from wechat_decoder import decode_wechat_dat

# Folders to monitor
MONITOR_FOLDER = r"C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach"
THUMB_FOLDER = r"C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach\4abf8e3a5a0aab205335f53fcb40b6a6\Thumb"

# Output folder for decoded images
OUTPUT_BASE = r"C:\Users\henry\OneDrive\Documents\WeChat Decoded Images2"


class DatFileHandler(FileSystemEventHandler):
    """Handler for monitoring .dat file creation"""
    
    def __init__(self, baseline_time, monitor_folder, decode_files=True):
        super().__init__()
        self.baseline_time = baseline_time
        self.monitor_folder = monitor_folder
        self.decode_files = decode_files
    
    def on_created(self, event):
        """Called when a file or directory is created"""
        if event.is_directory:
            return
        
        # Check if it's a .dat file
        if event.src_path.lower().endswith('.dat'):
            # Get file creation/modification time
            try:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(event.src_path))
                
                # Only report if file is newer than baseline
                if file_mtime >= self.baseline_time:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    file_time_str = file_mtime.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] New .dat file detected: {event.src_path}")
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
        
        if event.src_path.lower().endswith('.dat'):
            try:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(event.src_path))
                
                # Only report if file is newer than baseline
                if file_mtime >= self.baseline_time:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    file_time_str = file_mtime.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] .dat file modified: {event.src_path}")
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


def scan_existing_files(folder, baseline_time, folder_name="", decode_files=True):
    """Scan for existing .dat files modified after baseline time"""
    folder_label = f" in {folder_name}" if folder_name else ""
    print(f"Scanning{folder_label} for existing .dat files modified after {baseline_time.strftime('%Y-%m-%d %H:%M:%S')}...\n")
    
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
    """Start monitoring the selected folder for new .dat files"""
    
    # Use current time if no baseline provided
    if baseline_time is None:
        baseline_time = datetime.now()
    
    # Select folder based on choice
    if folder_choice == 'thumbnail':
        folder_name = "Thumbnail"
        folder_path = THUMB_FOLDER
        decode_files = False  # Thumbnail folder only prints names
    else:
        folder_name = "MsgAttach"
        folder_path = MONITOR_FOLDER
        decode_files = True  # MsgAttach folder decodes
    
    # Check if folder exists
    if not os.path.exists(folder_path):
        print(f"Error: {folder_name} folder does not exist: {folder_path}")
        return
    
    print(f"WeChat File Monitor")
    print(f"=" * 50)
    print(f"Monitoring {folder_name}: {folder_path}")
    print(f"Mode: {'Print only' if not decode_files else 'Decode to JPG'}")
    print(f"Baseline time: {baseline_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"=" * 50)
    print()
    
    # First, scan for existing files
    scan_existing_files(folder_path, baseline_time, folder_name, decode_files)
    
    print("Starting continuous monitoring...")
    print("Press Ctrl+C to stop monitoring\n")
    
    # Create event handler and observer
    event_handler = DatFileHandler(baseline_time, folder_path, decode_files)
    observer = Observer()
    observer.schedule(event_handler, folder_path, recursive=True)
    
    # Start monitoring
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        observer.stop()
    
    observer.join()
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
    - thumbnail: Monitors Thumbnail folder and only prints file names (no decoding)

--start-time "YYYYmmdd HH:MM"
    Specify baseline time to filter files. Only files modified after this time will be reported.
    Format: "YYYYmmdd HH:MM" (e.g., "20241105 14:30")
    If not provided, uses current time as baseline.

USAGE EXAMPLES:
---------------

1. Monitor MsgAttach folder from current time (default behavior):
   python wechat_file_monitor.py

2. Monitor Thumbnail folder and only print file names:
   python wechat_file_monitor.py --folder thumbnail

3. Monitor MsgAttach folder for files modified after specific time:
   python wechat_file_monitor.py --start-time "20241105 10:30"

4. Monitor Thumbnail folder for files modified after specific time:
   python wechat_file_monitor.py --folder thumbnail --start-time "20241105 14:00"

5. View help information:
   python wechat_file_monitor.py --help

MONITORED FOLDERS:
------------------
MsgAttach: C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach
Thumbnail: C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach\4abf8e3a5a0aab205335f53fcb40b6a6\Thumb

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
   - Continuously watches for new or modified .dat files
   - Reports files with timestamps
   - Auto-decodes files in MsgAttach mode
   - Only prints file names in Thumbnail mode

3. To stop:
   - Press Ctrl+C to gracefully stop monitoring

NOTES:
------
- The script can only monitor ONE folder at a time (use --folder to choose)
- MsgAttach mode: Full decoding to JPG
- Thumbnail mode: Print-only (no decoding)
- The baseline time filter applies to both initial scan and continuous monitoring
- File timestamps are based on file modification time
"""
