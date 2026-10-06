"""Dataset discovery module."""

from collections.abc import Iterator
from pathlib import Path

from geo_audit.models import FileFormat

SUPPORTED_EXTENSIONS = {
    ".csv": FileFormat.CSV,
    ".geojson": FileFormat.GEOJSON,
    ".json": FileFormat.GEOJSON,
}


def discover_files(root: Path) -> Iterator[tuple[Path, FileFormat]]:
    """Recursively discover supported files in a directory."""
    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    for path in root.rglob("*"):
        if path.is_file():
            ext = path.suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                yield path, SUPPORTED_EXTENSIONS[ext]


def get_file_format(path: Path) -> FileFormat:
    """Determine file format from extension."""
    ext = path.suffix.lower()
    return SUPPORTED_EXTENSIONS.get(ext, FileFormat.UNKNOWN)


def get_file_size(path: Path) -> int:
    """Get file size in bytes."""
    try:
        return path.stat().st_size
    except OSError:
        return 0
