# config.py

import os

# --- Paths ---
# The base directory where all results, logs, and moved duplicates will be stored.
TARGET_BASE_DIR = "C:\\DuplicateCheckResults"

# --- Folder Names ---
# The name of the subfolder within TARGET_BASE_DIR where duplicates will be moved.
DUPLICATES_FOLDER_NAME = "Duplicates"

# --- Logging ---
# The subfolder for log files.
LOG_FOLDER = os.path.join(TARGET_BASE_DIR, "Logs")
# The main log file for the application's operations.
LOG_FILENAME = "duplicate_check.log"
# The log file specifically for performance metrics.
PERFORMANCE_LOG_FILENAME = "performance_log.txt"

# --- Filtering ---
# Files smaller than this value (in bytes) will be ignored during the scan.
# Default is 1 MB.
MIN_SIZE_BYTES = 1 * 1024 * 1024

# --- File Types ---
# A set of allowed image file extensions to be processed by the application.
ALLOWED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic',
    '.tiff', '.bmp', '.jfif', '.dng'
}
