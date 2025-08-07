# review_dialog.py
# This module contains the ReviewDialog class, a floating window for manual review.

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout
)
from PySide6.QtCore import Qt, Signal

from image_series import display_group

class ReviewDialog(QDialog):
    """
    A separate, floating dialog window for reviewing a single group of duplicates.
    It is designed to be resizable and to provide maximum space for image comparison.
    It communicates the user's choice back to the main window via signals.
    """
    # Signal emitted when the user approves a group, sending the path of the image to keep.
    group_approved = Signal(str)
    # Signal emitted when the user decides to skip the current group.
    group_skipped = Signal()

    def __init__(self, all_file_data, styles, parent=None):
        """
        Initializes the dialog window.
        Args:
            all_file_data (dict): A dictionary mapping file paths to their metadata.
            styles (dict): A dictionary of stylesheet fragments for styling widgets.
            parent (QWidget): The parent widget, typically the main application window.
        """
        super().__init__(parent)
        self.all_file_data = all_file_data
        self.styles = styles
        self.selected_image_in_group = None

        # --- Basic Dialog Setup ---
        self.setWindowTitle("Manual Duplicate Review")
        # Start with a generous size; the user can resize or maximize it.
        self.setMinimumSize(800, 600)
        # Inherit the dark theme from the parent window.
        if parent:
            self.setStyleSheet(parent.styleSheet())

        # --- Build the UI ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)

        # A status label at the top to show progress (e.g., "Group 1 of 10").
        self.status_label = QLabel("Reviewing duplicate group...")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; padding-bottom: 5px;")
        self.main_layout.addWidget(self.status_label)

        # The main scrollable area where the image grid will be displayed.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll_area.setWidget(self.grid_container)
        self.main_layout.addWidget(scroll_area, 1)  # The '1' makes this area stretch.

        # Action buttons at the bottom of the dialog.
        self.btn_approve = QPushButton("✅ Approve and Keep Selected")
        self.btn_skip = QPushButton("❌ Skip This Group")
        self.btn_approve.setEnabled(False)  # Disabled until an image is selected.

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.btn_approve)
        button_layout.addWidget(self.btn_skip)
        button_layout.addStretch()
        self.main_layout.addLayout(button_layout)

        # --- Connect Internal Signals ---
        self.btn_approve.clicked.connect(self._approve_and_close)
        self.btn_skip.clicked.connect(self._skip_and_close)

    def on_thumbnail_clicked(self, file_path):
        """
        Handles the click event on an image thumbnail within the grid.
        Args:
            file_path (str): The path of the clicked image.
        """
        self.selected_image_in_group = file_path
        # Update the visual style of all images in the grid to show the selection.
        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            if hasattr(widget, 'file_path'):
                style_key = 'image_keep' if widget.file_path == file_path else 'image_discard'
                widget.set_style(style_key)
        # Enable the approve button now that a selection has been made.
        self.btn_approve.setEnabled(True)

    def review_group(self, group_paths, group_index, total_groups):
        """
        This is the main public method to populate and show the dialog for a group.
        Args:
            group_paths (list): A list of file paths for the current duplicate group.
            group_index (int): The index of the current group (e.g., 0 for the first group).
            total_groups (int): The total number of groups to be reviewed.
        """
        self.selected_image_in_group = None
        self.btn_approve.setEnabled(False)

        # Update the status label to reflect the current progress.
        self.status_label.setText(f"Reviewing Group {group_index + 1} of {total_groups}")

        # Fetch the metadata for the files in the current group.
        group_metadata = [self.all_file_data[path] for path in group_paths if path in self.all_file_data]

        # Use the existing display_group function to populate the grid.
        display_group(group_metadata, self.grid_container, self.on_thumbnail_clicked, self.styles)

        # Show the dialog modally, which pauses the main window until this one is closed.
        self.exec()

    def _approve_and_close(self):
        """
        Emits the 'group_approved' signal with the selected image path and closes the dialog.
        """
        if self.selected_image_in_group:
            self.group_approved.emit(self.selected_image_in_group)
            self.accept()  # Closes the dialog with a "success" status.

    def _skip_and_close(self):
        """
        Emits the 'group_skipped' signal and closes the dialog.
        """
        self.group_skipped.emit()
        self.reject()  # Closes the dialog with a "cancel" or "failure" status.
