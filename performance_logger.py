# performance_logger.py

import logging
import os
from pathlib import Path
from config import LOG_FOLDER, PERFORMANCE_LOG_FILENAME

class PerformanceLogger:
    def __init__(self):
        log_folder_path = Path(LOG_FOLDER)
        log_folder_path.mkdir(parents=True, exist_ok=True)
        self.log_path = log_folder_path / PERFORMANCE_LOG_FILENAME
        self._check_log_file()

    def _check_log_file(self):
        """Creates the log file with a header if it doesn't exist."""
        if not self.log_path.exists():
            try:
                self.log_path.write_text("--- Performance Log for Duplicate Check ---\n\n", encoding="utf-8")
            except OSError as e:
                logging.error(f"Could not create performance log file: {e}")

    def log_run(self, stats_dict):
        """Writes a formatted summary of a run to the log file."""
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(f"--- Run: {stats_dict.get('timestamp')} ---\n")
                f.write(f"Folder: {stats_dict.get('folder', 'N/A')}\n")
                f.write(f"Total time: {stats_dict.get('total_time', 0):.2f} seconds\n")

                f.write("\n[Settings]\n")
                f.write(f"  Mode: {stats_dict.get('mode', 'N/A')}\n")
                if stats_dict.get('mode') == 'Automatic selection':
                    f.write(f"  Strategy: {stats_dict.get('strategy', 'N/A')}\n")
                f.write(f"  Sensitivity (threshold): {stats_dict.get('threshold', 'N/A')}\n")

                f.write("\n[Statistics]\n")
                f.write(f"  Images found for check: {stats_dict.get('files_processed', 'N/A')}\n")
                f.write(f"  Images that failed hashing: {stats_dict.get('failed_files', 'N/A')}\n")
                f.write(f"  Images hashed: {stats_dict.get('images_hashed', 'N/A')}\n")

                f.write("\n[Time Usage Details (seconds)]\n")
                f.write(f"  Scanning folder:         {stats_dict.get('scan_time', 0):.2f}\n")
                f.write(f"  Downloading from cloud:  {stats_dict.get('download_time', 0):.2f}\n")
                f.write(f"  Hashing images:          {stats_dict.get('hashing_time', 0):.2f}\n")
                f.write(f"  Comparison/grouping:     {stats_dict.get('comparison_time', 0):.2f}\n")
                if 'automatic_selection_time' in stats_dict:
                    f.write(f"  Automatic selection:     {stats_dict.get('automatic_selection_time', 0):.2f}\n")
                if 'move_time' in stats_dict:
                    f.write(f"  Moving files:            {stats_dict.get('move_time', 0):.2f}\n")

                f.write("\n[Result]\n")
                f.write(f"  Duplicate groups found: {stats_dict.get('groups_found', 'N/A')}\n")
                f.write(f"  Files marked for removal: {stats_dict.get('files_marked_for_removal', 'N/A')}\n")
                f.write(f"  Files moved: {stats_dict.get('files_moved', 'N/A')}\n")

                discarded_files = stats_dict.get('discarded_files', [])
                if discarded_files:
                    f.write("\n[Discarded Files (sample)]\n")
                    for file_path in discarded_files[:20]:
                        f.write(f"  - {os.path.basename(file_path)}\n")
                    if len(discarded_files) > 20:
                        f.write(f"  ... and {len(discarded_files) - 20} more.\n")

                f.write("-" * 50 + "\n\n")
        except OSError as e:
            logging.error(f"Could not write to performance log: {e}")
