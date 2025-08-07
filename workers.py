# workers.py
import os
import shutil
import logging
import time
from PySide6.QtCore import QObject, Signal

from file_handler import scan_directory, ensure_files_are_local
from visual_duplicate_checker import batch_duplicate_check
from automatic_selector import AutomaticSelector

class FileMover(QObject):
    """
    Worker to move files to a destination folder in a separate thread.
    """
    finished = Signal(int, int)
    progress_log = Signal(str)

    def __init__(self, files_to_move, destination_folder):
        super().__init__()
        self.files_to_move = files_to_move
        self.destination_folder = destination_folder

    def run(self):
        os.makedirs(self.destination_folder, exist_ok=True)
        moved_count = 0
        failed_count = 0
        for file_path in self.files_to_move:
            try:
                if os.path.exists(file_path):
                    file_name = os.path.basename(file_path)
                    destination_path = os.path.join(self.destination_folder, file_name)
                    shutil.move(file_path, destination_path)
                    message = f"MOVED: {file_name}"
                    logging.info(message)
                    self.progress_log.emit(message)
                    moved_count += 1
                else:
                    message = f"ERROR: The file '{os.path.basename(file_path)}' no longer exists."
                    logging.warning(message)
                    self.progress_log.emit(message)
                    failed_count += 1
            except Exception as e:
                message = f"ERROR while moving {os.path.basename(file_path)}: {e}"
                logging.error(message)
                self.progress_log.emit(message)
                failed_count += 1
        self.finished.emit(moved_count, failed_count)


class DuplicateChecker(QObject):
    """
    The main worker for the entire duplicate check process.
    Handles scanning, downloading, hashing, and selection.
    """
    scan_summary_ready = Signal(dict)
    download_progress = Signal(int, int)
    manual_check_finished = Signal(dict, dict, list) # stats, all_file_data, groups
    automatic_selection_finished = Signal(list, dict) # files_for_removal, stats
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
                    self.automatic_selection_finished.emit([], check_statistics)
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
                    self.automatic_selection_finished.emit([], check_statistics)
                return

            if self.mode == "Manual review":
                self.manual_check_finished.emit(check_statistics, all_file_data, groups)
            else:
                # Step 4: Automatic selection
                start_time_auto = time.monotonic()
                files_for_removal = self.automatic_selector.run_automatic_selection(
                    groups, self.strategy, all_file_data
                )
                check_statistics["automatic_selection_time"] = time.monotonic() - start_time_auto
                logging.info(f"Automatic selection completed in {check_statistics['automatic_selection_time']:.2f} seconds.")
                self.automatic_selection_finished.emit(files_for_removal, check_statistics)

        except Exception as e:
            logging.critical(f"A critical error occurred in the duplicate check thread: {e}", exc_info=True)
            self.error_occurred.emit(f"An error occurred during the duplicate check:\n\n{e}")
