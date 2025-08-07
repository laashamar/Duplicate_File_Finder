# ui_panels.py
# Contains specialized QFrame classes for each section of the GUI.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QComboBox, QScrollArea, QWidget, QProgressBar, QTextEdit, QGridLayout,
    QCheckBox
)
from automatic_selector import SelectionStrategy

class SettingsPanel(QFrame):
    """The panel for all settings before the check starts."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        title = QLabel("<b>1. Settings</b>")
        layout.addWidget(title)

        # Folder selection
        self.label_folder = QLabel("Select a folder to begin")
        self.btn_folder = QPushButton("📂 Select Folder")
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.label_folder, 1)
        folder_layout.addWidget(self.btn_folder)
        layout.addLayout(folder_layout)

        # Mode and Strategy
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("<b>Mode:</b>"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Automatic selection", "Manual review"])
        mode_layout.addWidget(self.mode_combo)

        self.strategy_label = QLabel("<b>Strategy:</b>")
        self.strategy_combo = QComboBox()
        for strategy in SelectionStrategy:
            self.strategy_combo.addItem(str(strategy), strategy)
        mode_layout.addWidget(self.strategy_label)
        mode_layout.addWidget(self.strategy_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # --- NEW: Added options for the KEEP_ALL_UNIQUE_VERSIONS strategy ---
        self.unique_version_options_frame = QFrame()
        self.unique_version_options_frame.setFrameShape(QFrame.NoFrame)
        unique_options_layout = QVBoxLayout(self.unique_version_options_frame)
        unique_options_layout.setContentsMargins(10, 5, 10, 5)
        
        self.sort_files_checkbox = QCheckBox("Sort retained files into 'Originals' and 'Last Edited' subfolders")
        unique_options_layout.addWidget(self.sort_files_checkbox)

        self.remains_action_frame = QFrame()
        self.remains_action_frame.setFrameShape(QFrame.NoFrame)
        remains_layout = QHBoxLayout(self.remains_action_frame)
        remains_layout.setContentsMargins(0, 0, 0, 0)
        remains_layout.addWidget(QLabel("Action for other non-selected files:"))
        self.remains_action_combo = QComboBox()
        self.remains_action_combo.addItems(["Move to Recycle Bin", "Move to 'Duplicates' Folder"])
        remains_layout.addWidget(self.remains_action_combo)
        remains_layout.addStretch()
        unique_options_layout.addWidget(self.remains_action_frame)
        
        layout.addWidget(self.unique_version_options_frame)
        # --- End of new options ---

        # Sensitivity (Threshold)
        threshold_layout = QHBoxLayout()
        self.label_threshold = QLabel()
        self.slider_threshold = QSlider(Qt.Horizontal)
        self.slider_threshold.setRange(0, 64)
        self.slider_threshold.setValue(5)
        threshold_layout.addWidget(self.label_threshold)
        threshold_layout.addWidget(self.slider_threshold, 1)
        layout.addLayout(threshold_layout)

        self.help_threshold = QLabel()
        self.help_threshold.setWordWrap(True)
        layout.addWidget(self.help_threshold)

        # Start button
        self.btn_start = QPushButton("🚀 Start Duplicate Check")
        layout.addWidget(self.btn_start)


class StatusPanel(QFrame):
    """The panel for status, log, and the final action button."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        title = QLabel("<b>2. Status and Actions</b>")
        layout.addWidget(title)

        status_layout = QHBoxLayout()

        scan_scroll_area = QScrollArea()
        scan_scroll_area.setWidgetResizable(True)

        self.scan_summary_label = QLabel("Waiting for folder selection...")
        self.scan_summary_label.setWordWrap(True)
        self.scan_summary_label.setAlignment(Qt.AlignTop)
        scan_scroll_area.setWidget(self.scan_summary_label)
        status_layout.addWidget(scan_scroll_area, 1)

        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status = QLabel("Ready to start")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status)
        status_layout.addLayout(progress_layout, 1)
        layout.addLayout(status_layout)

        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setFixedHeight(100)
        layout.addWidget(self.log_window)

        # --- CHANGED: Renamed button to be more generic ---
        self.btn_process_duplicates = QPushButton("⚙️ Process Duplicates")
        self.btn_process_duplicates.setEnabled(False)
        layout.addWidget(self.btn_process_duplicates)
