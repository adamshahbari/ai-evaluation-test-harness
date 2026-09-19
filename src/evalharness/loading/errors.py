from __future__ import annotations

from pathlib import Path


class DatasetError(Exception):
    """Raised when test definitions cannot be loaded or are invalid."""

    def __init__(self, message: str, *, source: Path | None = None) -> None:
        self.source = source
        super().__init__(f"{source}: {message}" if source else message)
