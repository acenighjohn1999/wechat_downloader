# WeChat Image Downloader

A Python tool to download images from WeChat group chats and organize them locally.

## Features

- 📱 Downloads images from WeChat group chats
- 📁 Organizes images by group and date
- ⚙️ Configurable settings via JSON
- 📊 Detailed logging and progress tracking
- 🔍 Filter specific groups or download from all
- 💾 Handles duplicate files automatically
- 🖼️ Supports multiple image formats (JPG, PNG, GIF, etc.)

## Prerequisites

- WeChat desktop application installed and logged in
- Python 3.7 or higher
- Access to WeChat's local database files

## Installation

1. Clone or download this repository
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The tool uses a `config.json` file for settings. Key options include:

- `output_directory`: Where to save downloaded images
- `organize_by_group`: Create separate folders for each group
- `organize_by_date`: Organize images by month/year
- `target_groups`: Specific groups to download from (empty = all groups)
- `max_file_size_mb`: Maximum file size to download
- `image_formats`: Supported image file extensions

## Usage

### Basic Usage

Download images from all groups:
```bash
python wechat_image_downloader.py
```

### Advanced Usage

List available groups:
```bash
python wechat_image_downloader.py --list-groups
```

Download from specific groups:
```bash
python wechat_image_downloader.py --groups "Family Group" "Work Team"
```

Use custom configuration:
```bash
python wechat_image_downloader.py --config my_config.json
```

## How It Works

1. **Database Access**: The tool accesses WeChat's local SQLite database to find group chats and image messages
2. **Image Location**: Locates image files in WeChat's storage directory
3. **Organization**: Creates organized folder structure based on your settings
4. **File Management**: Copies images with appropriate naming and handles duplicates

## Directory Structure

After running, your images will be organized like this:
```
downloaded_images/
├── Group Name 1/
│   ├── 2024-01/
│   │   ├── 20240115_143022_12345.jpg
│   │   └── 20240118_091205_12346.png
│   └── 2024-02/
│       └── 20240201_200314_12347.gif
└── Group Name 2/
    └── 2024-01/
        └── 20240120_155530_12348.jpg
```

## Important Notes

⚠️ **Database Access**: This tool requires access to WeChat's database files. Make sure:
- WeChat is closed when running the tool
- You have read permissions to WeChat's data directory
- Your antivirus doesn't block database access

⚠️ **WeChat Versions**: Database structure may vary between WeChat versions. The tool attempts to handle common variations.

⚠️ **Privacy**: This tool only accesses your local WeChat data. No data is sent online.

## Troubleshooting

### "WeChat database not found"
- Ensure WeChat is installed and you've logged in at least once
- Check if WeChat is running and close it
- Manually specify database path in config.json

### "Permission denied" errors
- Run as administrator (Windows)
- Check file permissions on WeChat directories
- Temporarily disable antivirus scanning

### "No images found"
- Verify the groups have image messages
- Check if images are stored locally (not just in cloud)
- Try with a different group

## Configuration Examples

### Download only from specific groups:
```json
{
  "target_groups": ["Family", "Work Team", "Friends"],
  "organize_by_group": true,
  "organize_by_date": true
}
```

### Flat organization (all images in one folder):
```json
{
  "organize_by_group": false,
  "organize_by_date": false,
  "output_directory": "./all_wechat_images"
}
```

## License

This project is for personal use only. Please respect WeChat's terms of service and privacy policies.

## Contributing

Feel free to submit issues and enhancement requests!
