# data_models.py
from dataclasses import dataclass

@dataclass
class FileMetadata:
    """Data class for holding metadata about a file."""
    path: str
    hash: int = 0
    resolution: int = 0
    size: int = 0
    mod_time: float = 0.0
