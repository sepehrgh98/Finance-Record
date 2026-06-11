from __future__ import annotations

import hashlib
from pathlib import Path

from core.enums.physical_file_type import PhysicalFileType
from core.models.document_context import DocumentContext
from core.models.file_info import FileInfo


class DiscoveryNode:
    """
    Recursively discovers files and determines their physical file type.

    Responsibilities:
    - Find files
    - Collect basic metadata
    - Compute SHA256 hashes
    - Determine physical file type from extension

    Non-responsibilities:
    - Semantic classification
    - OCR
    - Parsing
    - Content inspection
    """

    IGNORED_FILENAMES = {
        ".DS_Store",
        "Thumbs.db",
    }

    TEMPORARY_FILENAME_PREFIXES = {
        # Microsoft Office creates lock/owner files while documents are open.
        # They are not source records and usually contain no useful financial data.
        "~$",
    }

    EXTENSION_MAP = {
        ".pdf": PhysicalFileType.PDF,
        ".xlsx": PhysicalFileType.SPREADSHEET,
        ".xls": PhysicalFileType.SPREADSHEET,
        ".txt": PhysicalFileType.TEXT,
        ".csv": PhysicalFileType.CSV,
        ".html": PhysicalFileType.HTML,
        ".htm": PhysicalFileType.HTML,
        ".jpg": PhysicalFileType.IMAGE,
        ".jpeg": PhysicalFileType.IMAGE,
        ".png": PhysicalFileType.IMAGE,
    }

    def run(self, root_dir: str | Path) -> list[DocumentContext]:
        root_path = Path(root_dir)

        if not root_path.exists():
            raise FileNotFoundError(
                f"Directory does not exist: {root_path}"
            )

        if not root_path.is_dir():
            raise ValueError(
                f"Expected a directory, got: {root_path}"
            )

        discovered_contexts: list[DocumentContext] = []

        for file_path in root_path.rglob("*"):

            if not file_path.is_file():
                continue

            if self._should_ignore(file_path):
                continue

            file_info = self._build_file_info(file_path)
            discovered_contexts.append(
                DocumentContext(
                    file_info=file_info,
                    physical_type=self._detect_physical_type(file_info),
                )
            )

        return discovered_contexts

    def discover_files(self, root_dir: str | Path) -> list[FileInfo]:
        """
        Backward-compatible helper for tests/tools that only need FileInfo.
        """

        return [
            context.file_info
            for context in self.run(root_dir)
        ]

    def _detect_physical_type(self, file_info: FileInfo) -> PhysicalFileType:
        return self.EXTENSION_MAP.get(
            file_info.extension.lower(),
            PhysicalFileType.UNKNOWN,
        )

    def _build_file_info(self, file_path: Path) -> FileInfo:
        return FileInfo(
            path=file_path,
            filename=file_path.name,
            extension=file_path.suffix.lower(),
            size_bytes=file_path.stat().st_size,
            sha256=self._compute_sha256(file_path),
        )

    def _should_ignore(self, file_path: Path) -> bool:
        """
        Return True when a file is a system artifact or temporary lock file.

        Temporary Office files such as ``~$invoices.xlsx`` are ignored because
        they are implementation details created by spreadsheet editors, not
        financial source documents that should be parsed or reported.
        """

        filename = file_path.name

        if filename in self.IGNORED_FILENAMES:
            return True

        return any(
            filename.startswith(prefix)
            for prefix in self.TEMPORARY_FILENAME_PREFIXES
        )

    @staticmethod
    def _compute_sha256(file_path: Path) -> str:
        """
        Compute SHA256 hash for a file.
        """

        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        return sha256.hexdigest()
