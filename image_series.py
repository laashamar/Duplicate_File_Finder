# image_series.py

import os
import logging
from PySide6.QtWidgets import QLabel, QGridLayout, QWidget, QVBoxLayout
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QPoint, Signal
from PIL import Image
from PIL.ImageQt import ImageQt

from data_models import FileMetadata

def create_pixmap_from_path(path, size):
    """
    A robust function for creating a QPixmap.
    Tries Qt directly first, then Pillow as a fallback for complex formats.
    """
    pixmap = QPixmap(path)
    if not pixmap.isNull():
        return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    # Fallback to Pillow if QPixmap fails (typically for DNG/RAW)
    try:
        with Image.open(path) as img:
            # Converts to RGBA for best compatibility
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            qimage = ImageQt(img)
            pixmap = QPixmap.fromImage(qimage)
            return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception as e:
        logging.warning(f"Could not load preview for {os.path.basename(path)} with Pillow: {e}")
        # Returns an empty pixmap if everything fails
        return QPixmap()


class HoverLabel(QLabel):
    """A QLabel subclass that displays a magnified popup image on hover."""
    clicked = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = None
        self.popup = None
        self.setMouseTracking(True)

    def set_file_path(self, path):
        self.file_path = path

    def mousePressEvent(self, event):
        self.clicked.emit(self.file_path)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        if self.file_path and os.path.exists(self.file_path):
            if not self.popup and self.window():
                self.popup = QLabel(self.window(), Qt.Window | Qt.FramelessWindowHint)
                self.popup.setAttribute(Qt.WA_TranslucentBackground)
                self.popup.setStyleSheet("background-color: transparent;")
                self.popup.setFixedSize(400, 400)

            if self.popup:
                # Uses the robust loading function for the popup image as well
                scaled_pixmap = create_pixmap_from_path(self.file_path, 400)
                self.popup.setPixmap(scaled_pixmap)
                pos = event.globalPosition().toPoint()
                self.popup.move(pos + QPoint(15, 15))
                self.popup.show()

        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.popup:
            self.popup.hide()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        if self.popup and self.popup.isVisible():
            pos = event.globalPosition().toPoint()
            self.popup.move(pos + QPoint(15, 15))
        super().mouseMoveEvent(event)

class ImageInfoWidget(QWidget):
    """A widget that displays an image (HoverLabel) and text with metadata."""
    clicked = Signal(str)

    def __init__(self, metadata: FileMetadata, styles, thumbnail_size=140, parent=None):
        super().__init__(parent)
        self.file_path = metadata.path
        self.styles = styles

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        self.image_label = HoverLabel()
        self.image_label.set_file_path(metadata.path)
        
        pix = create_pixmap_from_path(metadata.path, thumbnail_size)
        self.image_label.setPixmap(pix)
        # Set size based on the thumbnail, adding a little extra for the border
        self.image_label.setFixedSize(thumbnail_size + 10, thumbnail_size + 10)
        
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.clicked.connect(self.clicked.emit)

        filename = os.path.basename(metadata.path)
        size_kb = metadata.size / 1024
        size_str = f"{size_kb:.0f} KB"
        if size_kb > 1024:
            size_str = f"{size_kb / 1024:.1f} MB"

        # Calculate resolution
        width = 0
        height = 0
        try:
            # Try to get from pixmap first, as it's fastest
            if not pix.isNull():
                aspect_ratio = pix.width() / pix.height() if pix.height() > 0 else 1
                width = int((metadata.resolution * aspect_ratio)**0.5)
                height = int(metadata.resolution / width) if width > 0 else 0
        except Exception:
            # Ignore errors here, resolution_str will become "Unknown"
            pass

        resolution_str = f"{width}x{height}" if width > 0 and height > 0 else "Unknown"

        info_text = (f"<div style='font-size: 11px; text-align: center;'>"
                     f"<b>{filename}</b><br>"
                     f"{resolution_str} - {size_str}</div>")

        self.info_label = QLabel(info_text)
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.image_label)
        layout.addWidget(self.info_label)

        self.set_style('image_default')

    def set_style(self, style_key):
        self.setStyleSheet(f"QWidget {{ {self.styles[style_key]} }}")


def display_group(group_metadata_list, container_widget, click_handler, styles):
    """Displays all images in a duplicate group with metadata in a grid."""
    layout = container_widget.layout()

    # Clear previous widgets
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    # Determine thumbnail size based on the number of images
    num_images = len(group_metadata_list)
    if num_images > 10:
        thumbnail_size = 80  # Smallest size for very large groups
    elif num_images > 5:
        thumbnail_size = 110 # Medium size for medium groups
    else:
        thumbnail_size = 140 # Largest size for small groups

    # Estimate the horizontal space one item takes up (thumbnail + padding)
    item_width_estimate = thumbnail_size + 20
    
    # Get the usable width of the container panel, subtracting a margin
    container_width = container_widget.width() - 20
    
    # Calculate how many columns can fit, ensuring it's at least 1
    if item_width_estimate > 0:
        num_columns = max(1, container_width // item_width_estimate)
    else:
        num_columns = 1 # Fallback in case of an error
    
    MAX_COLUMNS = num_columns
    
    row = 0
    col = 0

    for metadata in group_metadata_list:
        info_widget = ImageInfoWidget(metadata, styles, thumbnail_size)
        info_widget.clicked.connect(click_handler)

        layout.addWidget(info_widget, row, col)

        col += 1
        if col >= MAX_COLUMNS:
            col = 0
            row += 1