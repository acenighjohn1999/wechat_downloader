import pyautogui
import time
import random
import subprocess
import threading
import os
import csv
import pyperclip
from datetime import datetime


class WeChatNavigator:
    def __init__(self):
        self.wechat_window = None
        # Safety feature - move mouse to corner to abort
        pyautogui.FAILSAFE = True
        # Add small delay between actions
        pyautogui.PAUSE = 0.5
        # For production mode monitoring
        self.last_file_time = None
        self.monitor_lock = threading.Lock()
        self.new_files_detected = False
        # CSV file and base path for folder mappings
        self.csv_file = "wechat_folder_mappings.csv"
        self.base_path = r"C:\Users\henry\OneDrive\Documents\WeChat Files\wxid_5zk2tbe173ua22\FileStorage\MsgAttach"
        
    def find_wechat_window(self):
        """Find the WeChat window on screen"""
        try:
            import pygetwindow as gw
            
            # Get all windows
            all_windows = gw.getAllWindows()
            
            # Filter for WeChat windows (exclude empty titles and command prompts)
            wechat_windows = [w for w in all_windows 
                            if w.title and 
                            ('WeChat' in w.title or '微信' in w.title) and
                            'Prompt' not in w.title and
                            '.bat' not in w.title and
                            'cmd' not in w.title.lower()]
            
            if not wechat_windows:
                print("WeChat window not found. Make sure WeChat is running.")
                print("\nAvailable windows:")
                for w in all_windows[:10]:  # Show first 10 windows
                    if w.title:
                        print(f"  - {w.title}")
                return False
            
            # Prefer window with just "WeChat" or "微信" in title
            for window in wechat_windows:
                if window.title in ['WeChat', '微信']:
                    self.wechat_window = window
                    break
            
            if not self.wechat_window:
                self.wechat_window = wechat_windows[0]
            
            # Bring window to front
            self.wechat_window.activate()
            time.sleep(0.5)
            print(f"Found WeChat window: {self.wechat_window.title}")
            
            # Move mouse to WeChat window as visual feedback
            center_x = self.wechat_window.left + self.wechat_window.width // 2
            center_y = self.wechat_window.top + self.wechat_window.height // 2
            pyautogui.moveTo(center_x, center_y, duration=0.5)
            
            return True
            
        except Exception as e:
            print(f"Error finding WeChat window: {e}")
            return False
    
    def search_chat_with_ctrl_f(self, chat_name):
        """Search for a chat using Ctrl+F (WeChat's built-in search)
        
        Uses clipboard method to support Chinese and special characters
        """
        print(f"Using Ctrl+F to search for: {chat_name}")
        
        try:
            # Press Ctrl+F to open search
            print("Pressing Ctrl+F to open search...")
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(0.8)  # Wait for search box to appear
            
            # Type the chat name using clipboard (supports Chinese characters)
            print(f"Typing chat name: {chat_name}")
            
            # Check if chat name contains non-ASCII characters (Chinese, etc.)
            has_special_chars = any(ord(char) > 127 for char in chat_name)
            
            if has_special_chars:
                # Use clipboard method for Chinese/special characters
                print("  Using clipboard method (contains Chinese/special characters)")
                pyperclip.copy(chat_name)
                time.sleep(0.1)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.3)
            else:
                # Use direct typing for ASCII-only text
                print("  Using direct typing (ASCII only)")
                pyautogui.write(chat_name, interval=0.1)
            
            time.sleep(0.5)
            
            # Press Enter to navigate to the chat
            print("Pressing Enter to navigate to chat...")
            pyautogui.press('enter')
            time.sleep(1.0)
            
            print(f"✓ Successfully navigated to '{chat_name}' using Ctrl+F search")
            return True
            
        except Exception as e:
            print(f"✗ Error during Ctrl+F search: {e}")
            return False
    
    def get_folder_for_chat(self, chat_name):
        """Look up the folder ID for a given chat name from CSV"""
        if not os.path.exists(self.csv_file):
            print(f"[Warning] {self.csv_file} not found, using default MsgAttach folder")
            return None
        
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Match chat name (case-insensitive)
                    if row['Store'].lower() == chat_name.lower():
                        folder_id = row['Folder']
                        folder_path = os.path.join(self.base_path, folder_id)
                        print(f"[Folder Lookup] Found mapping: '{chat_name}' -> {folder_id}")
                        print(f"[Folder Lookup] Monitoring path: {folder_path}")
                        return folder_path
                
                print(f"[Warning] No folder mapping found for '{chat_name}' in CSV")
                print(f"[Warning] Available chats: ", end="")
                # Show available chats
                f.seek(0)
                reader = csv.DictReader(f)
                stores = [row['Store'] for row in reader]
                print(", ".join(stores))
                return None
                
        except Exception as e:
            print(f"[Error] Failed to read {self.csv_file}: {e}")
            return None
    
    def monitor_file_changes(self, process, stop_event, timeout_seconds=10):
        """Monitor the file monitor subprocess output for new .dat files"""
        import re
        
        print(f"[File Monitor] Started monitoring for new .dat files (timeout: {timeout_seconds}s)")
        
        try:
            while not stop_event.is_set():
                line = process.stdout.readline()
                if not line:
                    break
                
                line = line.strip()
                if line:
                    print(f"[File Monitor] {line}")
                    
                    # Check if this line indicates a new .dat file was detected
                    # Look for patterns like: ".dat file detected"
                    if '.dat file detected' in line.lower():
                        with self.monitor_lock:
                            self.new_files_detected = True
                            self.last_file_time = datetime.now()
                            print(f"[File Monitor] ✓ New file detected at {self.last_file_time.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"[File Monitor] Error: {e}")
    
    def click_for_image(self, prod_mode=False):
        """Click at multiple positions to find an image, stopping when preview opens
        
        Args:
            prod_mode: If True, continues pressing left arrow until no new files detected
        """
        if not self.wechat_window:
            print("WeChat window not initialized")
            return False
        
        print("\nSearching for image in chat...")
        
        # Calculate window dimensions
        window_left = self.wechat_window.left
        window_top = self.wechat_window.top
        window_width = self.wechat_window.width
        window_height = self.wechat_window.height
        
        # Chat area is typically in the right portion (after chat list on left ~35%)
        # Images are usually in the center of the chat content area
        chat_content_left = window_left + int(window_width * 0.25)  # Start of chat content
        chat_content_width = int(window_width * 0.65)  # Width of chat content area
        
        # Fixed X position (where images are located horizontally)
        click_x = chat_content_left + int(chat_content_width * 0.05)
        
        # Generate multiple Y positions with random increments
        # Start from bottom and work upwards with random spacing
        click_positions = []
        current_y = window_top + window_height - 200  # Start near bottom
        top_limit = window_top + 150  # Don't click too high (avoid header)
        
        # Generate positions going upward with random increments
        while current_y > top_limit:
            click_positions.append((click_x, current_y))
            # Random increment between 80 and 150 pixels
            random_increment = random.randint(80, 150)
            current_y -= random_increment
        
        print(f"Generated {len(click_positions)} click positions to try")
        
        # Try each position until image preview opens
        for i, (pos_x, pos_y) in enumerate(click_positions, 1):
            print(f"\nAttempt {i}/{len(click_positions)}: Clicking at position ({pos_x}, {pos_y})")
            pyautogui.moveTo(pos_x, pos_y, duration=0.3)
            time.sleep(0.2)
            pyautogui.click(pos_x, pos_y)
            time.sleep(0.8)  # Wait a bit longer for preview to open
            
            # Check if Image Preview window opened
            if self.check_image_preview_opened():
                print(f"✓ Image Preview opened at position {i}")
                
                if prod_mode:
                    # Production mode: keep navigating until no new files
                    # Need to get chat_name from the calling context
                    # This will be passed through click_for_image
                    self.navigate_images_prod_mode(self.current_chat_name if hasattr(self, 'current_chat_name') else None)
                else:
                    # Normal mode: just 3 left arrows
                    self.navigate_images_normal_mode()
                
                # Check if Image Preview is still open and close it
                if self.check_image_preview_opened():
                    print("\nImage Preview still open, pressing Escape to close...")
                    pyautogui.press('escape')
                    time.sleep(1)
                    print("✓ Image Preview closed")
                else:
                    print("\nImage Preview already closed")
                
                print("✓ Finished navigating images")
                return True
            else:
                print(f"  No preview opened, trying next position...")
        
        print("\n✗ Could not find clickable image at any position")
        return False
    
    def navigate_images_normal_mode(self):
        """Navigate through 3 images with left arrow"""
        print("\nNavigating through images (normal mode - 3 arrows)...")
        time.sleep(3)
        
        print("Pressing left arrow (1/3)")
        pyautogui.press('left')
        time.sleep(3)
        
        print("Pressing left arrow (2/3)")
        pyautogui.press('left')
        time.sleep(3)
        
        print("Pressing left arrow (3/3)")
        pyautogui.press('left')
        time.sleep(3)
    
    def navigate_images_prod_mode(self, chat_name=None):
        """Navigate through images continuously until no new .dat files detected
        
        Args:
            chat_name: Name of the chat to look up folder path from CSV
        """
        print("\n" + "="*60)
        print("PRODUCTION MODE: Continuous navigation enabled")
        print("Will keep pressing left arrow until no new files detected")
        print("="*60 + "\n")
        
        # Look up the folder path for this chat
        folder_path = None
        if chat_name:
            folder_path = self.get_folder_for_chat(chat_name)
        
        if not folder_path:
            print("[Warning] Using default MsgAttach folder for monitoring")
            folder_path = self.base_path
        
        # Verify folder exists
        if not os.path.exists(folder_path):
            print(f"[Error] Folder does not exist: {folder_path}")
            print("[Error] Cannot start production mode without valid folder")
            return
        
        # Start file monitor subprocess
        monitor_process = None
        monitor_thread = None
        stop_event = threading.Event()
        
        try:
            # Start wechat_file_monitor.py monitoring the specific folder
            start_time = datetime.now().strftime("%Y%m%d %H:%M")
            
            # Use a Python script approach to monitor specific folder
            # Escape the folder path for the Python string
            escaped_folder_path = folder_path.replace('\\', '\\\\')
            
            cmd = [
                'python',
                '-c',
                f'''
import os
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class SimpleHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.dat'):
            print(f".dat file detected (on_created): {{event.src_path}}", flush=True)
    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.dat'):
            print(f".dat file detected (on_modified): {{event.src_path}}", flush=True)

observer = Observer()
observer.schedule(SimpleHandler(), "{escaped_folder_path}", recursive=True)
observer.start()
print("Monitoring: {escaped_folder_path}", flush=True)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
'''
            ]
            
            print(f"[File Monitor] Monitoring folder: {folder_path}")
            monitor_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self.monitor_file_changes,
                args=(monitor_process, stop_event, 10),
                daemon=True
            )
            monitor_thread.start()
            
            # Give monitor time to start up
            time.sleep(2)
            
            arrow_count = 0
            idle_cycles = 0
            max_idle_cycles = 2  # Stop after 2 cycles with no new files
            
            while True:
                # Reset new files flag
                with self.monitor_lock:
                    files_detected_this_cycle = self.new_files_detected
                    self.new_files_detected = False
                
                # Press left arrow
                arrow_count += 1
                print(f"\n[Arrow {arrow_count}] Pressing left arrow...")
                pyautogui.press('left')
                
                # Wait 2 seconds + random 0-1 second and monitor for new files
                wait_time = 2 + random.random()
                print(f"[Arrow {arrow_count}] Waiting {wait_time:.1f} seconds for new files...")
                time.sleep(wait_time)
                
                # Check if new files were detected during the wait
                with self.monitor_lock:
                    new_files_in_wait = self.new_files_detected
                    total_new_files = files_detected_this_cycle or new_files_in_wait
                
                if total_new_files:
                    print(f"[Arrow {arrow_count}] ✓ New files detected, continuing...")
                    idle_cycles = 0
                else:
                    idle_cycles += 1
                    print(f"[Arrow {arrow_count}] No new files ({idle_cycles}/{max_idle_cycles} idle cycles)")
                    
                    if idle_cycles >= max_idle_cycles:
                        print(f"\n{'='*60}")
                        print(f"STOPPING: No new files detected for {max_idle_cycles} idle cycles")
                        print(f"Total arrows pressed: {arrow_count}")
                        print(f"{'='*60}\n")
                        break
        
        finally:
            # Clean up monitor process
            if monitor_process:
                print("[File Monitor] Stopping file monitor...")
                stop_event.set()
                monitor_process.terminate()
                try:
                    monitor_process.wait(timeout=2)
                except:
                    monitor_process.kill()
            
            if monitor_thread:
                monitor_thread.join(timeout=1)
    
    def check_image_preview_opened(self):
        """Quick check if Image Preview window is currently open"""
        try:
            import pygetwindow as gw
            all_windows = gw.getAllWindows()
            
            for window in all_windows:
                if window.title and ('Image Preview' in window.title or '图片预览' in window.title or '图片查看' in window.title):
                    return True
            return False
        except:
            return False
    
    def wait_for_image_preview(self, timeout=5):
        """Wait for Image Preview window to open"""
        print("\nWaiting for Image Preview window to open...")
        
        import pygetwindow as gw
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                all_windows = gw.getAllWindows()
                
                # Look for Image Preview window
                for window in all_windows:
                    if window.title and ('Image Preview' in window.title or '图片预览' in window.title or '图片查看' in window.title):
                        print(f"✓ Image Preview window found: {window.title}")
                        return True
                
                time.sleep(0.2)
                
            except Exception as e:
                print(f"Error checking windows: {e}")
                time.sleep(0.2)
        
        print(f"✗ Image Preview window not found within {timeout} seconds")
        return False
    
    def navigate_to_chat(self, chat_name, click_image=True, prod_mode=False):
        """Main function to navigate to a specific chat and optionally click for an image
        
        Args:
            chat_name: Name of the chat to navigate to
            click_image: Whether to search for and click images
            prod_mode: If True, continuously navigate until no new .dat files detected
        """
        # Store chat name for production mode folder lookup
        self.current_chat_name = chat_name
        
        print(f"\n{'='*50}")
        print(f"WeChat Auto Navigator")
        if prod_mode:
            print(f"MODE: PRODUCTION (continuous until no new files)")
        else:
            print(f"MODE: NORMAL (3 arrow presses)")
        print(f"{'='*50}\n")
        
        # Step 1: Find WeChat window
        if not self.find_wechat_window():
            return False
        
        # Step 2: Use Ctrl+F to search for the chat
        success = self.search_chat_with_ctrl_f(chat_name)
        
        if not success:
            return False
        
        # Step 3: Click for image if requested
        if click_image:
            time.sleep(1.0)  # Wait for chat to fully load
            
            # click_for_image now tries multiple positions and checks for preview
            image_found = self.click_for_image(prod_mode=prod_mode)
            
            if image_found:
                print("\n✓ Image found and opened successfully!")
                # Wait 10 seconds before finishing
                print("\nWaiting 10 seconds before finishing...")
                time.sleep(10)
                print("Done! WeChat and Image Preview windows remain open.")
            else:
                print("\n✗ No image found at any clicked location")
                print("You may need to scroll the chat to show images")
                # Still wait before finishing
                print("\nWaiting 10 seconds before finishing...")
                time.sleep(10)
                print("Done! WeChat window remains open.")
            
            return image_found
        else:
            # Just wait before finishing
            print("\nWaiting 10 seconds before finishing...")
            time.sleep(10)
            print("Done! WeChat window remains open.")
            return True


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Automatically navigate to a WeChat chat and optionally click for an image'
    )
    parser.add_argument(
        '--chat',
        type=str,
        default='Meadowland',
        help='Name of the chat to navigate to (default: Meadowland)'
    )
    parser.add_argument(
        '--delay',
        type=int,
        default=3,
        help='Delay in seconds before starting (default: 3)'
    )
    parser.add_argument(
        '--click-image',
        action='store_true',
        default=True,
        help='Click to find and open an image in the chat (default: True)'
    )
    parser.add_argument(
        '--no-click-image',
        dest='click_image',
        action='store_false',
        help='Skip clicking for an image'
    )
    parser.add_argument(
        '--prod',
        action='store_true',
        default=False,
        help='Production mode: continuously press left arrow until no new .dat files detected'
    )
    
    args = parser.parse_args()
    
    navigator = WeChatNavigator()
    
    print(f"Attempting to navigate to '{args.chat}' chat...")
    if args.click_image:
        if args.prod:
            print("Will search for and click on an image, then continuously navigate")
            print("Production mode: Will monitor for new .dat files and keep going")
        else:
            print("Will search for and click on an image in the chat")
    print("Make sure WeChat is open and visible!")
    print(f"\nStarting in {args.delay} seconds...")
    time.sleep(args.delay)
    
    success = navigator.navigate_to_chat(args.chat, click_image=args.click_image, prod_mode=args.prod)
    
    if success:
        if args.click_image:
            if args.prod:
                print(f"\n✓ Successfully navigated to '{args.chat}' chat and completed production run!")
            else:
                print(f"\n✓ Successfully navigated to '{args.chat}' chat and found image!")
        else:
            print(f"\n✓ Successfully navigated to '{args.chat}' chat!")
    else:
        print(f"\n✗ Failed to complete task.")
        print("\nTroubleshooting tips:")
        print("1. Make sure WeChat is open and visible")
        print("2. Try manually opening WeChat and ensuring it's in focus")
        print("3. Check if the chat name matches exactly")
        if args.click_image:
            print("4. Make sure there's an image visible near the bottom of the chat")
            print("5. Try scrolling the chat to show recent images")


if __name__ == "__main__":
    main()


r"""
USAGE DOCUMENTATION
===================

This script automatically navigates to a WeChat chat, finds and clicks on images,
and navigates through them using keyboard controls.

FEATURES:
---------
1. Finds and activates WeChat window automatically
2. Uses Ctrl+F to search for chat by name
3. Automatically finds and clicks on images in the chat
4. Navigates through multiple images using left arrow key
5. Two modes: Normal (3 arrows) and Production (continuous until no new files)
6. Production mode monitors wechat_file_monitor for new .dat files
7. Closes image preview when done
8. All windows remain open after completion

COMMAND LINE OPTIONS:
---------------------
--chat <name>
    Name of the chat to navigate to.
    Default: "Meadowland"
    Supports English, Chinese, and mixed names
    Use quotes if name contains spaces

--delay <seconds>
    Delay in seconds before starting the automation.
    Default: 3 seconds
    Gives you time to ensure WeChat is visible

--click-image
    Enable image clicking and navigation (default behavior)

--no-click-image
    Skip image clicking, only navigate to the chat

--prod
    Production mode: Continuously press left arrow until no new .dat files detected.
    Uses wechat_folder_mappings.csv to find the correct folder for the chat name.
    Monitors the specific chat's folder (and subfolders) for new .dat files.
    Waits 4-5 seconds (4 + random 0-1) between each arrow press.
    Stops after 2 consecutive cycles with no new files detected.
    Falls back to default MsgAttach folder if chat not found in CSV.

USAGE EXAMPLES:
---------------

1. Navigate to default chat (Meadowland) and find images (normal mode - 3 arrows):
   python wechat_auto_navigator.py

2. Navigate to a specific chat:
   python wechat_auto_navigator.py --chat "John Doe"

3. Navigate to Chinese or mixed name chat:
   python wechat_auto_navigator.py --chat "太平 Meadowland 3"

4. Only navigate to chat without clicking images:
   python wechat_auto_navigator.py --chat "MyChat" --no-click-image

5. Custom delay before starting:
   python wechat_auto_navigator.py --chat "Family" --delay 5

6. PRODUCTION MODE - continuous navigation until no new files:
   python wechat_auto_navigator.py --chat "Meadowland" --prod

7. Production mode with custom chat:
   python wechat_auto_navigator.py --chat "Wairau" --prod --delay 5

8. Using the batch file (Windows):
   run_wechat_navigator.bat
   run_wechat_navigator.bat "ChatName"
   run_wechat_navigator.bat "太平 Meadowland 3"

BEHAVIOR:
---------
1. Startup:
   - Waits specified delay (default 3 seconds)
   - Finds and activates WeChat window
   - Brings WeChat to front

2. Chat Navigation:
   - Presses Ctrl+F to open search
   - Types the chat name (uses clipboard for Chinese/special characters)
   - Auto-detects if chat name contains Chinese characters
   - Uses Ctrl+V for Chinese, direct typing for English
   - Presses Enter to navigate to chat

3. Image Finding (if enabled):
   - Calculates click positions in chat area
   - Tries multiple positions from bottom to top
   - Uses random spacing (80-150 pixels) between attempts
   - Stops when Image Preview window opens

4. Image Navigation (if image found):
   NORMAL MODE:
   - Waits 3 seconds
   - Presses left arrow to go to previous image
   - Waits 3 seconds
   - Presses left arrow again
   - Waits 3 seconds
   - Presses left arrow third time
   - Waits 3 seconds
   - Checks if Image Preview is still open
   - Presses Escape to close if still open
   
   PRODUCTION MODE (--prod):
   - Looks up chat name in wechat_folder_mappings.csv
   - Finds the specific folder ID for that chat
   - Starts file monitor subprocess for that specific folder (and subfolders)
   - Monitors for new .dat files in real-time (on_created and on_modified events)
   - Continuously presses left arrow with 4-5 second intervals
   - Wait time: 4 seconds + random(0-1) second between each arrow
   - Checks for new file detections after each arrow press
   - If new files detected: continues navigation (resets idle counter)
   - If no new files: increments idle counter
   - Stops after 2 consecutive cycles with no new files
   - Terminates file monitor subprocess
   - Closes Image Preview with Escape

5. Completion:
   - Waits 10 seconds before finishing
   - All windows remain open
   - Script exits gracefully

REQUIREMENTS:
-------------
- Python 3.7+
- pyautogui (pip install pyautogui)
- pygetwindow (pip install pygetwindow)
- pyperclip (pip install pyperclip) - for Chinese character support
- watchdog (pip install watchdog) - for production mode
- wechat_folder_mappings.csv - for production mode folder lookup
- WeChat Desktop application

SAFETY FEATURES:
----------------
- FAILSAFE enabled: Move mouse to top-left corner to abort
- Waits and delays between actions to ensure stability
- Non-destructive: never closes WeChat or modifies settings

CLICK POSITION CONFIGURATION:
-----------------------------
The script calculates click positions based on window size:
- X position: 25% into window + 5% of chat area width
- Y positions: Multiple positions from bottom to top with random spacing
- Adjust in click_for_image() method if needed for your layout

TROUBLESHOOTING:
----------------
1. Chat not found:
   - Ensure chat name matches exactly (case-sensitive)
   - Check if chat is in your chat list
   - Try scrolling chat list to show the chat

2. Images not found:
   - Ensure there are images in the chat
   - Scroll chat to show recent images
   - Check if images are in the visible area
   - Adjust click position in the code if needed

3. Script aborts unexpectedly:
   - Check if you moved mouse to top-left corner
   - Ensure WeChat window stays visible
   - Check that WeChat is not minimized

4. Wrong window activated:
   - Close other apps with "WeChat" in title
   - Ensure main WeChat window is the only one open

NOTES:
------
- The script searches for WeChat window by title ("WeChat" or "微信")
- Chinese characters in chat names are fully supported
- Image preview detection supports multiple languages
- All timing delays are adjustable in the code
- The script uses native Windows screenshot capabilities
"""
