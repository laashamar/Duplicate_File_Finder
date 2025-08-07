# duplicate_gui.py

import sys
import os
import multiprocessing
import logging
import time
from datetime import datetime

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QFileDialog,
    QVBoxLayout, QGraphicsDropShadowEffect, QMessageBox
)
from PySide6.QtGui import QColor
from match_engine import MatchEngine
from config import DUPLICATES_FOLDER_NAME, MIN_SIZE_BYTES, TARGET_BASE_DIR
from workers import FileMover, DuplicateChecker
import styles

from logger_setup import setup_global_logger
from performance_logger import PerformanceLogger
from ui_panels import SettingsPanel, StatusPanel
# --- NEW: Import the ReviewDialog ---
from review_dialog import ReviewDialog


class DuplicateWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Duplicate Detection – Group Based")
        self.setMinimumSize(900, 700)

        # --- Instance variables ---
        self.all_groups = []
        self.current_group_index = -1
        self.folder_path = None
        self.check_thread = None
        self.move_thread = None
        self.match_engine = None
        self.performance_logger = PerformanceLogger()
        self.active_run_stats = {}
        self.start_time = 0
        self.all_file_data = {}

        self._setup_styles()
        self.build_ui()
        self.connect_signals()

        setup_global_logger()

        self.set_button_state(self.settings_panel.btn_folder, 'highlight')
        self.set_button_state(self.settings_panel.btn_start, 'disabled')
        self.on_mode_changed()
        self.update_threshold_info(5)

    def _setup_styles(self):
        self.COLORS = styles.get_colors()
        self.STYLES = {
            **styles.get_button_styles(self.COLORS),
            **styles.get_image_styles(self.COLORS)
        }
        self.setStyleSheet(styles.get_main_stylesheet(self.COLORS))

    def build_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)

        self.settings_panel = SettingsPanel()
        # --- REMOVED: The old ReviewPanel is no longer part of the main window ---
        self.status_panel = StatusPanel()

        self.layout.addWidget(self.settings_panel)
        # --- REMOVED: No longer adding the ReviewPanel to the layout ---
        self.layout.addWidget(self.status_panel)

    def connect_signals(self):
        self.settings_panel.btn_folder.clicked.connect(self.select_folder)
        self.settings_panel.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self.settings_panel.slider_threshold.valueChanged.connect(self.update_threshold_info)
        self.settings_panel.btn_start.clicked.connect(self.start_duplicate_check)

        # --- REMOVED: Signals for the old ReviewPanel ---
        self.status_panel.btn_move_duplicates.clicked.connect(self.move_approved_duplicates)

    def set_button_state(self, button, state):
        button.setStyleSheet(self.STYLES[state])
        button.setEnabled(state != 'disabled')
        if state == 'highlight':
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(self.COLORS['primary_shadow']))
            shadow.setOffset(0, 0)
            button.setGraphicsEffect(shadow)
        else:
            button.setGraphicsEffect(None)

    def on_mode_changed(self):
        is_auto = self.settings_panel.mode_combo.currentText() == "Automatic selection"
        self.settings_panel.strategy_label.setVisible(is_auto)
        self.settings_panel.strategy_combo.setVisible(is_auto)
        # --- CHANGED: The old review panel is gone, so we don't need to hide it ---

    def append_log_message(self, message):
        self.status_panel.log_window.append(message)

    def update_threshold_info(self, value):
        self.settings_panel.label_threshold.setText(f"Sensitivity (Distance): {value}")
        if 0 <= value <= 5:
            text = "<b>Almost identical:</b> Minor differences - compression, light, noise."
        elif 6 <= value <= 15:
            text = "<b>Similar:</b> Same subject, but with changes - cropping, filter, color adjustment."
        else:
            text = "<b>Related:</b> Could be the same scene, but with major changes."
        self.settings_panel.help_threshold.setText(text)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_path = folder
            self.settings_panel.label_folder.setText(f"<b>Selected:</b> {os.path.basename(folder)}")
            self.set_button_state(self.settings_panel.btn_start, 'highlight')
            self.set_button_state(self.settings_panel.btn_folder, 'toned_down')
            self.status_panel.scan_summary_label.setText("Ready to start scan...")
        elif not self.folder_path:
            self.set_button_state(self.settings_panel.btn_folder, 'highlight')

    def start_duplicate_check(self):
        if not self.folder_path:
            QMessageBox.warning(self, "Folder Missing", "Select a folder before starting.")
            return

        self.set_button_state(self.settings_panel.btn_start, 'disabled')
        self.set_button_state(self.settings_panel.btn_folder, 'disabled')
        self.set_button_state(self.status_panel.btn_move_duplicates, 'disabled')

        self.settings_panel.slider_threshold.setEnabled(False)
        self.settings_panel.mode_combo.setEnabled(False)
        self.settings_panel.strategy_combo.setEnabled(False)

        self.all_groups.clear()
        self.current_group_index = -1
        self.status_panel.progress_bar.setValue(0)
        self.status_panel.log_window.clear()
        self.status_panel.scan_summary_label.setText("Scanning folder, please wait...")

        mode = self.settings_panel.mode_combo.currentText()
        strategy = self.settings_panel.strategy_combo.currentData(Qt.UserRole)
        threshold_value = self.settings_panel.slider_threshold.value()

        self.start_time = time.monotonic()
        self.active_run_stats = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "folder": self.folder_path,
            "mode": mode, "strategy": str(strategy), "threshold": threshold_value,
            "ignore_small_files": MIN_SIZE_BYTES > 0
        }

        logging.info(f"--- Starting new duplicate check ({mode}) for folder: {self.folder_path} ---")

        self.match_engine = MatchEngine()
        self.check_thread = QThread()
        self.duplicate_checker = DuplicateChecker(self.folder_path, threshold_value, mode, strategy)
        self.duplicate_checker.moveToThread(self.check_thread)

        self.duplicate_checker.scan_summary_ready.connect(self.display_scan_summary)
        self.duplicate_checker.download_progress.connect(self.handle_download_progress)
        self.duplicate_checker.progress_updated.connect(self.handle_progress_updated)
        self.duplicate_checker.error_occurred.connect(self.handle_check_error)

        if mode == "Manual review":
            self.duplicate_checker.manual_check_finished.connect(self.handle_manual_check_finished)
            self.duplicate_checker.manual_check_finished.connect(self.check_thread.quit)
        else:
            self.duplicate_checker.automatic_selection_finished.connect(self.handle_automatic_selection_finished)
            self.duplicate_checker.automatic_selection_finished.connect(self.check_thread.quit)

        self.check_thread.started.connect(self.duplicate_checker.run)
        self.check_thread.finished.connect(self.check_thread.deleteLater)
        self.check_thread.finished.connect(lambda: setattr(self, 'check_thread', None))
        self.check_thread.start()

    def display_scan_summary(self, summary):
        total_files = summary.get('total_files', 0)
        image_files = summary.get('image_files', {})
        other_files = summary.get('other_files', {})
        total_images = sum(image_files.values())
        total_other = sum(other_files.values())
        html = f"<b>Folder analysis:</b><br>Total {total_files} files found.<hr>"
        if image_files:
            html += f"<b>Image files ({total_images}):</b><ul>" + "".join([f"<li>{ext.upper()}: {count}</li>" for ext, count in sorted(image_files.items())]) + "</ul>"
        if other_files:
            html += f"<b>Other files ({total_other}):</b><ul>" + "".join([f"<li>{ext.upper()}: {count}</li>" for ext, count in sorted(other_files.items())[:5]])
            if len(other_files) > 5:
                html += "<li>... and more</li>"
            html += "</ul>"
        self.status_panel.scan_summary_label.setText(html)
        log_text = f"Folder analysis complete: Total {total_files} files. Image files: {total_images}. Other: {total_other}."
        logging.info(log_text)
        self.append_log_message(log_text)

    def handle_download_progress(self, current, total):
        self.status_panel.status.setText(f"Downloading file {current} of {total} from the cloud...")
        self.status_panel.progress_bar.setValue(int(100 * (current / total)))

    def handle_manual_check_finished(self, check_stats, all_file_data, groups):
        self.reactivate_ui_after_check()
        self.active_run_stats.update(check_stats)
        self.all_file_data = all_file_data

        self.all_groups = groups
        self.active_run_stats["groups_found"] = len(self.all_groups)

        validated_count = check_stats.get("files_processed", 0)
        log_text = f"{validated_count} image files were validated and sent for processing."
        self.append_log_message(log_text)
        logging.info(log_text)

        status_text = f"[OK] Check finished - {len(self.all_groups)} groups found for manual review"
        logging.info(status_text)
        self.status_panel.status.setText(status_text)
        self.status_panel.progress_bar.setValue(100)
        
        if self.all_groups:
            # --- NEW: Start the new dialog-based review process ---
            self.start_manual_review_session()
        else:
            QMessageBox.information(self, "No Duplicates Found", "The scan completed, but no duplicate groups were found.")
            self.log_performance_if_finished()

    def handle_automatic_selection_finished(self, files_for_removal, check_stats):
        self.reactivate_ui_after_check()
        self.active_run_stats.update(check_stats)
        self.active_run_stats["groups_found"] = check_stats.get("groups_found", 0)
        validated_count = check_stats.get("files_processed", 0)
        log_text = f"{validated_count} image files were validated and sent for processing."
        self.append_log_message(log_text)
        logging.info(log_text)
        for file_path in files_for_removal:
            self.match_engine.add_file_for_removal(file_path)
        num_files = len(files_for_removal)
        status_text = f"[OK] Automatic selection finished. {num_files} files marked for removal."
        logging.info(status_text)
        self.status_panel.status.setText(status_text)
        self.status_panel.progress_bar.setValue(100)
        if num_files > 0:
            self.set_button_state(self.status_panel.btn_move_duplicates, 'highlight')
            QMessageBox.information(self, "Automatic Selection Complete", f"{num_files} files are ready to be moved to the duplicates folder.")
        else:
            QMessageBox.information(self, "No Duplicates", "Found no files to remove based on the selected strategy.")
            self.log_performance_if_finished()

    def reactivate_ui_after_check(self):
        self.set_button_state(self.settings_panel.btn_folder, 'toned_down')
        if self.folder_path:
            self.set_button_state(self.settings_panel.btn_start, 'highlight')
        else:
            self.set_button_state(self.settings_panel.btn_start, 'disabled')

        self.settings_panel.slider_threshold.setEnabled(True)
        self.settings_panel.mode_combo.setEnabled(True)
        self.settings_panel.strategy_combo.setEnabled(True)

    def handle_check_error(self, error_message):
        QMessageBox.critical(self, "Error During Check", error_message)
        self.status_panel.status.setText("[ERROR] An error occurred. Check has been aborted.")
        self.status_panel.progress_bar.setValue(0)
        self.reactivate_ui_after_check()

    # --- NEW: Method to manage the new review dialog session ---
    def start_manual_review_session(self):
        self.current_group_index = 0
        self.process_next_group()

    # --- NEW: Method to show the dialog for the current group ---
    def process_next_group(self):
        if not (0 <= self.current_group_index < len(self.all_groups)):
            # This is called when all groups have been reviewed
            self.status_panel.status.setText(f"[DONE] Finished reviewing all {len(self.all_groups)} groups.")
            if self.match_engine.get_files_for_removal():
                self.set_button_state(self.status_panel.btn_move_duplicates, 'highlight')
            else:
                QMessageBox.information(self, "Review Complete", "You have finished reviewing all groups, but did not select any files for removal.")
                self.log_performance_if_finished()
            return

        active_group_paths = self.all_groups[self.current_group_index]
        
        # Create and configure the dialog for the current group
        dialog = ReviewDialog(self.all_file_data, self.STYLES, self)
        dialog.group_approved.connect(self.handle_group_approved)
        dialog.group_skipped.connect(self.handle_group_skipped)
        
        # This call shows the dialog and blocks until the user makes a choice
        dialog.review_group(active_group_paths, self.current_group_index, len(self.all_groups))

    # --- NEW: Handler for when the user approves a group in the dialog ---
    def handle_group_approved(self, path_to_keep):
        active_group = self.all_groups[self.current_group_index]
        for file_path in active_group:
            if file_path != path_to_keep:
                self.match_engine.add_file_for_removal(file_path)
        logging.info(f"GROUP {self.current_group_index + 1}: Keeping '{os.path.basename(path_to_keep)}'")
        
        self.current_group_index += 1
        self.process_next_group()

    # --- NEW: Handler for when the user skips a group in the dialog ---
    def handle_group_skipped(self):
        logging.info(f"GROUP {self.current_group_index + 1}: Skipped.")
        self.current_group_index += 1
        self.process_next_group()
    
    # --- REMOVED: All old methods related to the built-in review panel ---
    # on_thumbnail_clicked, display_current_group, next_group, approve_group

    def move_approved_duplicates(self):
        files_for_removal = self.match_engine.get_files_for_removal()
        if not files_for_removal:
            QMessageBox.information(self, "No Files", "There are no approved duplicates to move.")
            return
        self.active_run_stats['files_marked_for_removal'] = len(files_for_removal)
        self.active_run_stats['discarded_files'] = files_for_removal

        duplicate_folder = os.path.join(TARGET_BASE_DIR, DUPLICATES_FOLDER_NAME)

        self.set_button_state(self.status_panel.btn_move_duplicates, 'disabled')
        logging.info(f"Starting move of {len(files_for_removal)} files to '{duplicate_folder}'...")
        self.move_thread = QThread()
        self.file_mover = FileMover(files_for_removal, duplicate_folder)
        self.file_mover.moveToThread(self.move_thread)
        self.file_mover.progress_log.connect(self.append_log_message)
        self.file_mover.finished.connect(self.handle_move_finished)
        self.move_thread.started.connect(self.file_mover.run)
        self.move_thread.finished.connect(self.move_thread.quit)
        self.move_thread.finished.connect(self.move_thread.deleteLater)
        self.move_thread.finished.connect(lambda: setattr(self, 'move_thread', None))
        self.move_thread.start()

    def handle_move_finished(self, moved_counter, failed_counter):
        logging.info(f"File move complete. {moved_counter} files moved, {failed_counter} failed.")
        QMessageBox.information(self, "Done", f"Moved {moved_counter} files. {failed_counter} failed.")
        self.active_run_stats['files_moved'] = moved_counter
        self.log_performance_if_finished()
        self.match_engine.clear_list()

    def log_performance_if_finished(self):
        if self.start_time > 0:
            total_time = time.monotonic() - self.start_time
            self.active_run_stats['total_time'] = total_time
            discarded_files = self.match_engine.get_files_for_removal()
            self.active_run_stats['discarded_files'] = discarded_files
            self.active_run_stats.setdefault('files_marked_for_removal', len(discarded_files))
            self.active_run_stats.setdefault('files_moved', 0)
            logging.info(f"--- Run completed in {total_time:.2f} seconds ---")
            self.performance_logger.log_run(self.active_run_stats)
            self.start_time = 0

    def closeEvent(self, event):
        logging.info("Application is closing.")
        if self.check_thread and self.check_thread.isRunning():
            self.check_thread.quit()
            self.check_thread.wait()
        if self.move_thread and self.move_thread.isRunning():
            self.move_thread.quit()
            self.move_thread.wait()
        event.accept()

    def handle_progress_updated(self, value, text):
        self.status_panel.progress_bar.setValue(value)
        self.status_panel.status.setText(text)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    window = DuplicateWindow()
    window.show()
    sys.exit(app.exec())
