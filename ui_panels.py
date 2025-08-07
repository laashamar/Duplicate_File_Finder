# ui_panels.py
# Contains specialized QFrame classes for each section of the GUI.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QComboBox, QScrollArea, QWidget, QProgressBar, QTextEdit, QGridLayout
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

class ReviewPanel(QFrame):
    """The panel for manual review of duplicate groups."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        title = QLabel("<b>2. Manual Review</b>")
        layout.addWidget(title)

        self.group_status_label = QLabel("No groups to display")
        layout.addWidget(self.group_status_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.group_display_widget = QWidget()
        self.group_display_layout = QGridLayout(self.group_display_widget)
        self.group_display_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll_area.setWidget(self.group_display_widget)
        layout.addWidget(scroll_area, 1)

        self.btn_approve_group = QPushButton("✅ Approve Group")
        self.btn_skip_group = QPushButton("❌ Skip Group")
        self.btn_approve_group.setEnabled(False)
        self.btn_skip_group.setEnabled(False)

        choice_layout = QHBoxLayout()
        choice_layout.addStretch()
        choice_layout.addWidget(self.btn_approve_group)
        choice_layout.addWidget(self.btn_skip_group)
        choice_layout.addStretch()
        layout.addLayout(choice_layout)

class StatusPanel(QFrame):
    """The panel for status, log, and the final move button."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        title = QLabel("<b>3. Status and Log</b>")
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

        self.btn_move_duplicates = QPushButton("🗑️ Move Selected Duplicates")
        self.btn_move_duplicates.setEnabled(False)
        layout.addWidget(self.btn_move_duplicates)
