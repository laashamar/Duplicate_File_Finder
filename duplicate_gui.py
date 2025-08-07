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
# --- CHANGED: Importing ActionWorker instead of FileMover ---
from workers import ActionWorker, DuplicateChecker
import styles

from logger_setup import setup_global_logger
from performance_logger import PerformanceLogger
# --- CHANGED: Importing updated SettingsPanel and StatusPanel ---
from ui_panels import SettingsPanel, StatusPanel
from review_dialog import ReviewDialog
from automatic_selector import SelectionStrategy


class DuplicateWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visual Duplicate Finder")
        self.setMinimumSize(900, 700)

        # --- Instance variables ---
        self.all_groups = []
        self.files_for_removal = []
        self.files_to_sort = {}
        self.current_group_index = -1
        self.folder_path = None
        self.check_thread = None
        # --- CHANGED: Renamed thread variable ---
        self.action_thread = None
        self.match_engine = MatchEngine()
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
        self.status_panel = StatusPanel()

        self.layout.addWidget(self.settings_panel)
        self.layout.addWidget(self.status_panel)
        # --- NEW: Set initial state for the new UI elements ---
        self.on_strategy_changed()

    def connect_signals(self):
        self.settings_panel.btn_folder.clicked.connect(self.select_folder)
        self.settings_panel.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        # --- NEW: Connect signal for strategy changes ---
        self.settings_panel.strategy_combo.currentIndexChanged.connect(self.on_strategy_changed)
        self.settings_panel.slider_threshold.valueChanged.connect(self.update_threshold_info)
        self.settings_panel.btn_start.clicked.connect(self.start_duplicate_check)
        # --- CHANGED: Connect to the new process button ---
        self.status_panel.btn_process_duplicates.clicked.connect(self.start_file_actions)

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
        self.on_strategy_changed() # Update visibility of sub-options

    # --- NEW: Method to handle strategy changes and show/hide relevant UI ---
    def on_strategy_changed(self):
        is_auto = self.settings_panel.mode_combo.currentText() == "Automatic selection"
        selected_strategy = self.settings_panel.strategy_combo.currentData(Qt.UserRole)
        is_unique_versions = selected_strategy == SelectionStrategy.KEEP_ALL_UNIQUE_VERSIONS
        
        show_options = is_auto and is_unique_versions
        self.settings_panel.unique_version_options_frame.setVisible(show_options)

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
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", "C:\\")
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
        self.set_button_state(self.status_panel.btn_process_duplicates, 'disabled')

        self.settings_panel.setDisabled(True)

        self.all_groups.clear()
        self.files_for_removal.clear()
        self.files_to_sort.clear()
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
        else:
            self.duplicate_checker.automatic_selection_finished.connect(self.handle_automatic_selection_finished)
        
        self.check_thread.started.connect(self.duplicate_checker.run)
        self.check_thread.finished.connect(self.check_thread.quit)
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
            self.start_manual_review_session()
        else:
            QMessageBox.information(self, "No Duplicates Found", "The scan completed, but no duplicate groups were found.")
            self.log_performance_if_finished()

    def handle_automatic_selection_finished(self, files_for_removal, files_to_sort, check_stats):
        self.reactivate_ui_after_check()
        self.active_run_stats.update(check_stats)
        self.active_run_stats["groups_found"] = check_stats.get("groups_found", 0)
        
        self.files_for_removal = files_for_removal
        self.files_to_sort = files_to_sort
        
        validated_count = check_stats.get("files_processed", 0)
        log_text = f"{validated_count} image files were validated and sent for processing."
        self.append_log_message(log_text)
        logging.info(log_text)
        
        num_to_remove = len(self.files_for_removal)
        num_to_sort = len(self.files_to_sort.get('Originals', [])) + len(self.files_to_sort.get('Last Edited', []))

        status_text = f"[OK] Auto selection finished. {num_to_remove} files marked for removal, {num_to_sort} for sorting."
        logging.info(status_text)
        self.status_panel.status.setText(status_text)
        self.status_panel.progress_bar.setValue(100)
        
        if num_to_remove > 0 or num_to_sort > 0:
            self.set_button_state(self.status_panel.btn_process_duplicates, 'highlight')
            QMessageBox.information(self, "Automatic Selection Complete", f"{num_to_remove} files are ready for removal and {num_to_sort} for sorting.")
        else:
            QMessageBox.information(self, "No Actions Needed", "Found no files to remove or sort based on the selected strategy.")
            self.log_performance_if_finished()

    def reactivate_ui_after_check(self):
        self.set_button_state(self.settings_panel.btn_folder, 'toned_down')
        if self.folder_path:
            self.set_button_state(self.settings_panel.btn_start, 'highlight')
        else:
            self.set_button_state(self.settings_panel.btn_start, 'disabled')
        self.settings_panel.setEnabled(True)

    def handle_check_error(self, error_message):
        QMessageBox.critical(self, "Error During Check", error_message)
        self.status_panel.status.setText("[ERROR] An error occurred. Check has been aborted.")
        self.status_panel.progress_bar.setValue(0)
        self.reactivate_ui_after_check()

    def start_manual_review_session(self):
        self.current_group_index = 0
        self.match_engine.clear_list() # Clear previous manual selections
        self.process_next_group()

    def process_next_group(self):
        if not (0 <= self.current_group_index < len(self.all_groups)):
            self.files_for_removal = self.match_engine.get_files_for_removal()
            num_to_remove = len(self.files_for_removal)
            self.status_panel.status.setText(f"[DONE] Finished reviewing all {len(self.all_groups)} groups. {num_to_remove} files marked for removal.")
            if num_to_remove > 0:
                self.set_button_state(self.status_panel.btn_process_duplicates, 'highlight')
            else:
                QMessageBox.information(self, "Review Complete", "You finished reviewing all groups, but did not select any files for removal.")
                self.log_performance_if_finished()
            return

        active_group_paths = self.all_groups[self.current_group_index]
        
        dialog = ReviewDialog(self.all_file_data, self.STYLES, self)
        dialog.group_approved.connect(self.handle_group_approved)
        dialog.group_skipped.connect(self.handle_group_skipped)
        dialog.review_group(active_group_paths, self.current_group_index, len(self.all_groups))

    def handle_group_approved(self, path_to_keep):
        active_group = self.all_groups[self.current_group_index]
        for file_path in active_group:
            if file_path != path_to_keep:
                self.match_engine.add_file_for_removal(file_path)
        logging.info(f"GROUP {self.current_group_index + 1}: Keeping '{os.path.basename(path_to_keep)}'")
        self.current_group_index += 1
        self.process_next_group()

    def handle_group_skipped(self):
        logging.info(f"GROUP {self.current_group_index + 1}: Skipped.")
        self.current_group_index += 1
        self.process_next_group()
    
    # --- NEW: Renamed and updated to start the ActionWorker ---
    def start_file_actions(self):
        if not self.files_for_removal and not self.files_to_sort.get('Originals') and not self.files_to_sort.get('Last Edited'):
            QMessageBox.information(self, "No Files", "There are no files selected for any action.")
            return
            
        self.active_run_stats['files_marked_for_removal'] = len(self.files_for_removal)
        self.active_run_stats['discarded_files'] = self.files_for_removal
        
        # --- NEW: Build the action configuration dictionary ---
        remains_action_text = self.settings_panel.remains_action_combo.currentText()
        action_config = {
            'files_for_removal': self.files_for_removal,
            'files_to_sort': self.files_to_sort,
            'remains_action': 'recycle' if 'Recycle' in remains_action_text else 'move',
            'duplicates_folder': os.path.join(TARGET_BASE_DIR, DUPLICATES_FOLDER_NAME),
            'source_folder': self.folder_path,
            'enable_sorting': self.settings_panel.sort_files_checkbox.isChecked()
        }

        self.set_button_state(self.status_panel.btn_process_duplicates, 'disabled')
        logging.info(f"Starting file actions with config: {action_config}")
        
        self.action_thread = QThread()
        self.action_worker = ActionWorker(action_config)
        self.action_worker.moveToThread(self.action_thread)
        self.action_worker.progress_log.connect(self.append_log_message)
        self.action_worker.finished.connect(self.handle_actions_finished)
        
        self.action_thread.started.connect(self.action_worker.run)
        self.action_thread.finished.connect(self.action_thread.quit)
        self.action_thread.finished.connect(self.action_thread.deleteLater)
        self.action_thread.finished.connect(lambda: setattr(self, 'action_thread', None))
        self.action_thread.start()

    # --- NEW: Renamed and updated to handle results from ActionWorker ---
    def handle_actions_finished(self, action_stats):
        moved = action_stats.get('moved', 0)
        recycled = action_stats.get('recycled', 0)
        sorted_count = action_stats.get('sorted', 0)
        failed = action_stats.get('failed', 0)
        
        logging.info(f"File actions complete. Moved: {moved}, Recycled: {recycled}, Sorted: {sorted_count}, Failed: {failed}.")
        QMessageBox.information(self, "Done", f"Actions complete.\n- Moved to Duplicates: {moved}\n- Recycled: {recycled}\n- Sorted: {sorted_count}\n- Failed: {failed}")
        
        self.active_run_stats['files_moved'] = moved
        self.active_run_stats['files_recycled'] = recycled
        self.active_run_stats['files_sorted'] = sorted_count
        self.active_run_stats['move_time'] = action_stats.get('move_time', 0)
        
        self.log_performance_if_finished()
        self.match_engine.clear_list()
        self.files_for_removal.clear()
        self.files_to_sort.clear()


    def log_performance_if_finished(self):
        if self.start_time > 0:
            total_time = time.monotonic() - self.start_time
            self.active_run_stats['total_time'] = total_time
            self.active_run_stats.setdefault('files_marked_for_removal', 0)
            self.active_run_stats.setdefault('files_moved', 0)
            logging.info(f"--- Run completed in {total_time:.2f} seconds ---")
            self.performance_logger.log_run(self.active_run_stats)
            self.start_time = 0

    def closeEvent(self, event):
        logging.info("Application is closing.")
        if self.check_thread and self.check_thread.isRunning():
            self.check_thread.quit()
            self.check_thread.wait()
        if self.action_thread and self.action_thread.isRunning():
            self.action_thread.quit()
            self.action_thread.wait()
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
