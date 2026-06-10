# models/file_info.py

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileInfo:
    path: Path
    filename: str
    extension: str
    size_bytes: int
    sha256: str
