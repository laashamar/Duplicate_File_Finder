# file_handler.py
# Handles file system operations, including OneDrive placeholders.

import os
import logging
import ctypes
import time
from collections import Counter
# --- NEW: Added ThreadPoolExecutor for parallel downloads ---
from concurrent.futures import ThreadPoolExecutor
from config import ALLOWED_IMAGE_EXTENSIONS

# Windows file attribute constant for files that are not fully present locally
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000

def is_online_only(file_path):
    """
    Checks if a file is a placeholder (e.g., OneDrive "online-only" file).
    """
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(file_path))
        if attrs == -1:
            return False
        return (attrs & FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS) != 0
    except Exception as e:
        logging.warning(f"Could not check file attributes for {file_path}: {e}")
        return False

def scan_directory(folder_path):
    """
    Scans a directory recursively to find all files, categorizing them
    into images and others based on extensions.
    """
    start_time = time.monotonic()
    image_files = Counter()
    other_files = Counter()
    candidate_image_paths = []
    total_files = 0
    logging.info(f"Starting scan of folder: {folder_path}")
    for root, _, files in os.walk(folder_path):
        for filename in files:
            total_files += 1
            ext = os.path.splitext(filename)[1].lower()
            if not ext:
                ext = ".NO_EXT"
            if ext in ALLOWED_IMAGE_EXTENSIONS:
                image_files[ext] += 1
                candidate_image_paths.append(os.path.join(root, filename))
            else:
                other_files[ext] += 1
    scan_duration = time.monotonic() - start_time
    logging.info(f"Folder scan completed in {scan_duration:.2f} seconds.")
    return {
        "total_files": total_files, "image_files": dict(image_files),
        "other_files": dict(other_files), "candidate_paths": candidate_image_paths,
        "scan_duration": scan_duration
    }

def _trigger_download(path):
    """Reads the first byte of a file to trigger its download from the cloud."""
    try:
        with open(path, 'rb') as f:
            f.read(1)
        logging.info(f"Download complete for: {os.path.basename(path)}")
        return True
    except Exception as e:
        logging.error(f"Could not download the file {os.path.basename(path)}: {e}")
        return False

def ensure_files_are_local(file_paths, progress_callback):
    """
    Checks a list of files and triggers downloads in parallel for any that are online-only.
    """
    start_time = time.monotonic()
    online_files = [path for path in file_paths if is_online_only(path)]
    
    if not online_files:
        logging.info("All files are already available locally.")
        return 0.0
        
    total_to_download = len(online_files)
    logging.info(f"Found {total_to_download} files that need to be downloaded from the cloud.")
    
    # --- NEW: Using ThreadPoolExecutor for parallel downloads ---
    completed_count = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all download tasks
        futures = {executor.submit(_trigger_download, path): path for path in online_files}
        
        for future in futures:
            future.result()  # Wait for the download to complete
            completed_count += 1
            progress_callback(completed_count, total_to_download)
            
    download_duration = time.monotonic() - start_time
    logging.info(f"Download of {total_to_download} files completed in {download_duration:.2f} seconds.")
    return download_duration
