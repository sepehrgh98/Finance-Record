from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

from models.file_info import FileInfo


class DiscoveryNode:
    """
    Recursively discovers files inside a root directory.

    Responsibilities:
    - Find files
    - Collect basic metadata
    - Compute SHA256 hashes

    Non-responsibilities:
    - Classification
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

    def run(self, root_dir: str | Path) -> List[FileInfo]:
        root_path = Path(root_dir)

        if not root_path.exists():
            raise FileNotFoundError(
                f"Directory does not exist: {root_path}"
            )

        if not root_path.is_dir():
            raise ValueError(
                f"Expected a directory, got: {root_path}"
            )

        discovered_files: List[FileInfo] = []

        for file_path in root_path.rglob("*"):

            if not file_path.is_file():
                continue

            if self._should_ignore(file_path):
                continue

            discovered_files.append(
                FileInfo(
                    path=file_path,
                    filename=file_path.name,
                    extension=file_path.suffix.lower(),
                    size_bytes=file_path.stat().st_size,
                    sha256=self._compute_sha256(file_path),
                )
            )

        return discovered_files

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
