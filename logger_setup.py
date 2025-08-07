# logger_setup.py
import logging
import sys
from pathlib import Path
from config import LOG_FOLDER, LOG_FILENAME

class QTextEditLogger(logging.Handler):
    """
    A custom logging handler that sends records to a PySide6 QTextEdit widget.
    """
    def __init__(self, text_widget):
        super().__init__()
        self.widget = text_widget
        self.widget.setReadOnly(True)

    def emit(self, record):
        """Sends a log message to the widget."""
        msg = self.format(record)
        self.widget.append(msg)

def setup_global_logger(gui_log_handler=None):
    """
    Configures a global logger that writes to both a file and, if available,
    a GUI element.
    """
    log_path = Path(LOG_FOLDER) / LOG_FILENAME
    # Added 'parents=True' to ensure the entire folder structure is created.
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Rotate the log file if it's too large
    try:
        if log_path.exists() and log_path.stat().st_size > (5 * 1024 * 1024): # 5 MB
            log_path.replace(log_path.with_suffix('.log.old'))
    except OSError:
        pass

    # Define format
    log_format = '%(asctime)s - %(levelname)s - %(module)s.%(funcName)s: %(message)s'
    formatter = logging.Formatter(log_format, '%Y-%m-%d %H:%M:%S')

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(str(log_path), encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (for debugging)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    if gui_log_handler:
        gui_log_handler.setFormatter(formatter)
        gui_log_handler.setLevel(logging.INFO)
        logger.addHandler(gui_log_handler)

    logging.info("Logger initialized.")
    return logger
