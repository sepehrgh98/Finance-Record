from enum import Enum


class PhysicalFileType(Enum):
    PDF = "pdf"
    SPREADSHEET = "spreadsheet"
    TEXT = "text"
    IMAGE = "image"
    HTML = "html"
    CSV = "csv"
    UNKNOWN = "unknown"
