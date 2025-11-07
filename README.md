# WeChat Auto Downloader

A comprehensive Python-based automation tool for monitoring WeChat chats and automatically downloading images using GUI automation. The system continuously monitors for new image thumbnails and navigates through WeChat to download full-resolution images.

## Features

- 📱 **Real-time Monitoring**: Continuously watches for new WeChat image files (.dat thumbnails)
- 🤖 **GUI Automation**: Automatically navigates through WeChat's image viewer using PyAutoGUI
- 📁 **Multi-Mode Operation**:
  - **MsgAttach Mode**: Monitors single MsgAttach folder and decodes .dat files to JPG
  - **Thumbnail Mode**: Monitors ALL chat thumbnail folders with intelligent queue system
- ⚡ **Smart Queue System**: Automatically processes chats when idle, handles concurrent activity
- 🔄 **Production Mode**: Continuous navigation until no new files detected
- 📊 **Detailed Logging**: Comprehensive logging with store names, file counts, and progress
- 🏪 **Store Mapping**: CSV-based mapping of chat folders to store names for easy identification
- ⏱️ **Timeout Protection**: 10-minute safety timeout prevents hanging processes
- 🔍 **Dual Detection**: Event-based + polling backup for reliable file detection

## Prerequisites

- **WeChat Desktop** installed and logged in
- **Python 3.7+** with required packages
- **PyAutoGUI** dependencies (see installation)
- **WeChat window** must be open and visible for automation
- **CSV mapping file** (`wechat_folder_mappings.csv`) for chat identification

## Installation

1. **Clone/download** this repository
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure folder mappings** in `wechat_folder_mappings.csv`
4. **Ensure WeChat is installed** and you have access to its data directories

## Configuration

### Folder Mappings (CSV)
Create `wechat_folder_mappings.csv` with your chat folders:
```csv
Folder,Store
abc123,Family Group
def456,Work Team
ghi789,Supermarket Chat
```

### Key Settings
Located at the top of `wechat_file_monitor.py`:
- `MONITOR_FOLDER`: WeChat MsgAttach directory path
- `IDLE_THRESHOLD_SECONDS`: Wait time before processing (default: 60s)
- `QUEUE_CHECK_INTERVAL`: Queue check frequency (default: 5s)
- `MIN_FILES_TO_PROCESS`: Minimum files to trigger processing (default: 1)

## Usage

### Thumbnail Mode (Recommended)
Monitor ALL chat thumbnails with automatic processing:
```bash
python wechat_file_monitor.py --folder thumbnail
```

**Features:**
- Monitors all chat thumbnail folders from CSV
- Shows store names in brackets: `[Supermarket Chat]`
- Automatically queues and processes chats when idle
- Displays file counts and queue positions
- Handles concurrent new file arrivals gracefully

### MsgAttach Mode
Monitor single MsgAttach folder for immediate decoding:
```bash
python wechat_file_monitor.py --folder msgattach
```

### Time-Filtered Monitoring
Monitor files from a specific start time:
```bash
python wechat_file_monitor.py --folder thumbnail --start-time "20241104 10:30"
```

### Batch Files
Convenient batch files are provided:
- `run_monitor.bat`: Starts thumbnail monitoring
- `run_wechat_navigator.bat [Chat Name] prod`: Manual navigation for specific chats

## How It Works

### 1. **File Monitoring**
- Uses `watchdog` library for real-time file system monitoring
- Dual detection: events + polling every 5 seconds
- Filters files by timestamp and size (thumbnail mode: <15KB)

### 2. **Queue Management** (Thumbnail Mode)
- Tracks activity for each chat folder
- Processes chats only when idle for 60+ seconds
- Handles new files arriving during processing
- Single-threaded processing (one chat at a time)

### 3. **Auto Navigation**
When a chat is processed:
1. Launches `wechat_auto_navigator.py --chat [Name] --prod --file-count [N]`
2. Finds and activates WeChat window
3. Searches for chat using Ctrl+F
4. Clicks images and enters gallery view
5. **Production Mode**: Continuously presses left arrow while monitoring for new files
6. Stops automatically when no new files detected for 2 cycles

### 4. **Output Organization**
Images are saved to `C:\Users\[User]\OneDrive\Documents\WeChat Decoded Images2\` with folder structure mirroring the source.

## Sample Output

```
Starting continuous monitoring...
Press Ctrl+C to stop monitoring

[Queue Processor] Started

[2025-11-06 20:51:17] [Henderson] .dat file detected (polling): C:\...\Thumb\2025-11\file.dat (size: 6.1 KB)
  File timestamp: 2025-11-06 20:51:15
  ⏭️  Added to processing queue (position: 1, 23 files total)

[Queue] Henderson has been idle for 60 seconds
[Queue] 🚀 Starting: python wechat_auto_navigator.py --chat Henderson --prod --file-count 23

[Navigator Output for Henderson]
============================================================
WeChat Auto Navigator
MODE: PRODUCTION (continuous until no new files)
============================================================

What this script does:
- Finds and activates WeChat window
- Navigates to 'Henderson' chat
- Continuously presses left arrow until no new files

[Arrow 1] Pressing left arrow...
[Arrow 1] Waiting 2.3 seconds for new files...
[Arrow 1] ✓ New files detected, continuing...
...
```

## Important Notes

⚠️ **WeChat Must Be Open**: The automation requires WeChat desktop to be running and visible.

⚠️ **Mouse Safety**: Move mouse to top-left corner to abort navigation at any time.

⚠️ **Single Chat Processing**: Only one chat processes at a time to avoid conflicts.

⚠️ **10-Minute Timeout**: Safety mechanism prevents infinite hanging.

⚠️ **Local Data Only**: No data is sent online - only accesses your local WeChat files.

## Troubleshooting

### "No Thumb folders found"
- Verify `wechat_folder_mappings.csv` exists and has correct paths
- Check that thumbnail folders exist in the expected locations
- Run with `--folder msgattach` for basic functionality

### "WeChat window not found"
- Ensure WeChat desktop is open and visible
- Try running WeChat as administrator
- Check if WeChat window title matches expectations

### "Permission denied" errors
- Run command prompt as administrator
- Check antivirus isn't blocking file access
- Verify WeChat data directory permissions

### Queue not processing
- Check `IDLE_THRESHOLD_SECONDS` (default 60s)
- Verify `MIN_FILES_TO_PROCESS` threshold (default 1)
- Look for concurrent file activity preventing idle state

### Automation not working
- Ensure WeChat window is in focus
- Check screen resolution/scaling settings
- Verify PyAutoGUI can control the desktop
- Try with different delay settings in navigator

## Architecture

### Core Components
- **`wechat_file_monitor.py`**: Main monitoring and queue system
- **`wechat_auto_navigator.py`**: GUI automation for WeChat navigation
- **`wechat_decoder.py`**: .dat file decryption and JPG conversion
- **`run_wechat_navigator.bat`**: Convenience batch file launcher

### Processing Flow
1. **Monitor** detects new .dat files
2. **Queue** manages processing order by idle time
3. **Navigator** automates WeChat GUI to download images
4. **Decoder** converts .dat files to viewable images

## Development

### Adding New Features
- Queue logic in `ProcessingQueue` class
- Navigation patterns in `WeChatNavigator` class
- File detection in `DatFileHandler` class

### Testing
- Test with small file counts first
- Use `--delay` parameter to slow down automation
- Monitor logs for timing and error patterns

## License

Personal use only. Respect WeChat's terms of service and local data privacy laws.
