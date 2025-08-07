# workers.py
import os
import shutil
import logging
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# --- NEW: Added send2trash for safe deletion ---
import send2trash
from PySide6.QtCore import QObject, Signal

from file_handler import scan_directory, ensure_files_are_local
from visual_duplicate_checker import batch_duplicate_check
from automatic_selector import AutomaticSelector, SelectionStrategy

# --- NEW: Replaced FileMover with the more capable ActionWorker ---
class ActionWorker(QObject):
    """
    Worker to perform file actions: moving, recycling, and sorting.
    """
    finished = Signal(dict)
    progress_log = Signal(str)

    def __init__(self, action_config):
        super().__init__()
        self.config = action_config

    def _get_unique_path(self, path):
        """Generates a unique path by appending a number if the original exists."""
        if not os.path.exists(path):
            return path
        
        parent = Path(path).parent
        stem = Path(path).stem
        suffix = Path(path).suffix
        counter = 1
        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return str(new_path)
            counter += 1

    def run(self):
        """Main method to run all configured file actions."""
        start_time = time.monotonic()
        stats = {"moved": 0, "recycled": 0, "sorted": 0, "failed": 0}

        # --- Action 1: Handle files marked for removal ---
        files_for_removal = self.config.get('files_for_removal', [])
        remains_action = self.config.get('remains_action', 'recycle')
        duplicates_folder = self.config.get('duplicates_folder')

        if remains_action == 'recycle':
            for file_path in files_for_removal:
                try:
                    if os.path.exists(file_path):
                        send2trash.send2trash(file_path)
                        msg = f"RECYCLED: {os.path.basename(file_path)}"
                        logging.info(msg)
                        self.progress_log.emit(msg)
                        stats["recycled"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    logging.error(f"Failed to recycle {file_path}: {e}")
                    stats["failed"] += 1
        
        elif remains_action == 'move' and duplicates_folder:
            os.makedirs(duplicates_folder, exist_ok=True)
            for file_path in files_for_removal:
                try:
                    if os.path.exists(file_path):
                        dest_path = os.path.join(duplicates_folder, os.path.basename(file_path))
                        unique_dest_path = self._get_unique_path(dest_path)
                        shutil.move(file_path, unique_dest_path)
                        msg = f"MOVED: {os.path.basename(file_path)} to Duplicates folder"
                        logging.info(msg)
                        self.progress_log.emit(msg)
                        stats["moved"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    logging.error(f"Failed to move {file_path}: {e}")
                    stats["failed"] += 1

        # --- Action 2: Handle sorting for unique versions ---
        files_to_sort = self.config.get('files_to_sort', {})
        source_folder = self.config.get('source_folder')
        
        if self.config.get('enable_sorting') and source_folder and files_to_sort:
            for category, paths in files_to_sort.items():
                if not paths:
                    continue
                
                target_subfolder = os.path.join(source_folder, category)
                os.makedirs(target_subfolder, exist_ok=True)
                
                for file_path in paths:
                    try:
                        if os.path.exists(file_path):
                            dest_path = os.path.join(target_subfolder, os.path.basename(file_path))
                            unique_dest_path = self._get_unique_path(dest_path)
                            shutil.move(file_path, unique_dest_path)
                            msg = f"SORTED: {os.path.basename(file_path)} to '{category}'"
                            logging.info(msg)
                            self.progress_log.emit(msg)
                            stats["sorted"] += 1
                        else:
                            stats["failed"] += 1
                    except Exception as e:
                        logging.error(f"Failed to sort {file_path}: {e}")
                        stats["failed"] += 1

        stats["move_time"] = time.monotonic() - start_time
        self.finished.emit(stats)


class DuplicateChecker(QObject):
    """
    The main worker for the entire duplicate check process.
    Handles scanning, downloading, hashing, and selection.
    """
    scan_summary_ready = Signal(dict)
    download_progress = Signal(int, int)
    manual_check_finished = Signal(dict, dict, list) # stats, all_file_data, groups
    # --- CHANGED: Signal now returns files_to_sort as well ---
    automatic_selection_finished = Signal(list, dict, dict) # files_for_removal, files_to_sort, stats
    progress_updated = Signal(int, str)
    error_occurred = Signal(str)

    def __init__(self, folder_path, threshold, mode, strategy):
        super().__init__()
        self.folder_path = folder_path
        self.threshold = threshold
        self.mode = mode
        self.strategy = strategy
        self.automatic_selector = AutomaticSelector()

    def run(self):
        try:
            # Step 1: Scan
            self.progress_updated.emit(0, "Scanning folder...")
            scan_summary = scan_directory(self.folder_path)
            self.scan_summary_ready.emit(scan_summary)
            check_statistics = {"scan_time": scan_summary.get("scan_duration", 0)}
            candidate_paths = scan_summary.get("candidate_paths", [])

            if not candidate_paths:
                self.progress_updated.emit(100, "No image files found.")
                if self.mode == "Manual review":
                    self.manual_check_finished.emit(check_statistics, {}, [])
                else:
                    self.automatic_selection_finished.emit([], {}, check_statistics)
                return

            # Step 2: Download (if needed)
            download_duration = ensure_files_are_local(candidate_paths, self.download_progress.emit)
            check_statistics["download_time"] = download_duration

            # Step 3: Hashing, validation, and comparison
            check_results, all_file_data, groups = batch_duplicate_check(
                candidate_paths, self.threshold, self.progress_updated.emit
            )
            check_statistics.update(check_results)
            check_statistics['groups_found'] = len(groups)

            if not groups:
                if self.mode == "Manual review":
                    self.manual_check_finished.emit(check_statistics, all_file_data, [])
                else:
                    self.automatic_selection_finished.emit([], {}, check_statistics)
                return

            if self.mode == "Manual review":
                self.manual_check_finished.emit(check_statistics, all_file_data, groups)
            else:
                # Step 4: Automatic selection
                start_time_auto = time.monotonic()
                files_for_removal, files_to_sort = self.automatic_selector.run_automatic_selection(
                    groups, self.strategy, all_file_data
                )
                check_statistics["automatic_selection_time"] = time.monotonic() - start_time_auto
                logging.info(f"Automatic selection completed in {check_statistics['automatic_selection_time']:.2f} seconds.")
                self.automatic_selection_finished.emit(files_for_removal, files_to_sort, check_statistics)

        except Exception as e:
            logging.critical(f"A critical error occurred in the duplicate check thread: {e}", exc_info=True)
            self.error_occurred.emit(f"An error occurred during the duplicate check:\n\n{e}")
