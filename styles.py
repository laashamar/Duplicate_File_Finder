# styles.py

def get_colors():
    """
    Returns a dictionary with color codes for the new dark theme.
    """
    return {
        "background": "#212529",
        "frame_bg": "#343A40",
        "input_bg": "#495057",
        "text": "#F8F9FA",
        "text_muted": "#ADB5BD",
        "primary": "#0d6efd",
        "primary_hover": "#338bff",
        "primary_shadow": "#338bff",
        "toned_down_bg": "#495057",
        "toned_down_text": "#F8F9FA",
        "disabled_bg": "#343A40",
        "disabled_text": "#6C757D",
        "border": "#495057",
        "keep_border": "#198754", # Green for keep
        "discard_border": "#DC3545" # Red for discard
    }

def get_button_styles(colors):
    """
    Returns QSS styles for buttons, adapted for the dark theme.
    """
    return {
        "highlight": f"""
            QPushButton {{
                background-color: {colors['primary']};
                color: white;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors['primary_hover']};
            }}
        """,
        "toned_down": f"""
            QPushButton {{
                background-color: {colors['toned_down_bg']};
                color: {colors['toned_down_text']};
            }}
            QPushButton:hover {{
                background-color: #5C636A;
            }}
        """,
        "disabled": f"""
            QPushButton {{
                background-color: {colors['disabled_bg']};
                color: {colors['disabled_text']};
            }}
        """,
    }

def get_image_styles(colors):
    """
    Returns QSS styles for the image frames.
    """
    return {
        "image_default": f"border: 2px solid {colors['border']}; border-radius: 6px; padding: 2px;",
        "image_keep": f"border: 3px solid {colors['keep_border']}; border-radius: 6px; padding: 2px;",
        "image_discard": f"border: 3px solid {colors['discard_border']}; border-radius: 6px; padding: 2px;"
    }

def get_main_stylesheet(colors):
    """
    Returns the main stylesheet for the entire application, now with a dark theme.
    """
    # URL-encode the text color for use in SVG data URI
    encoded_text_color = colors["text"].replace("#", "%23")

    return f"""
        QWidget {{
            background-color: {colors['background']};
            font-family: Segoe UI, sans-serif;
            color: {colors['text']};
        }}
        QPushButton {{
            border: none;
            border-radius: 6px;
            padding: 8px 14px;
            font-size: 14px;
        }}
        QLabel {{
            font-size: 13px;
        }}
        QFrame {{
            background-color: {colors['frame_bg']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
        }}
        QComboBox, QSlider, QTextEdit, QProgressBar {{
            background-color: {colors['input_bg']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
            padding: 4px;
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox::down-arrow {{
            image: url(data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='{encoded_text_color}' viewBox='0 0 16 16'><path fill-rule='evenodd' d='M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z'/></svg>);
            width: 16px;
            height: 16px;
        }}
        QProgressBar {{
            text-align: center;
            color: {colors['text']};
        }}
        QProgressBar::chunk {{
            background-color: {colors['primary']};
            border-radius: 2px;
        }}
        QTextEdit {{
            font-family: Consolas, monaco, monospace;
            color: {colors['text_muted']};
        }}
        QScrollArea {{
            border: none;
        }}
    """
