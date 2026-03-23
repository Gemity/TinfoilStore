"""Atomic file operations and hashing utilities.

Maps to runtime spec section 2 rule 5 (atomic writes) and section 11 (sha256).
"""

import hashlib
import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, data: str, encoding: str = "utf-8") -> None:
    """Write data to a file atomically via temp-file + rename.

    The temp file is created in the same directory as the target to ensure
    os.replace() is an atomic same-volume rename on both POSIX and NTFS.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up temp file on any failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def compute_sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_directory(path: Path) -> None:
    """Create directory and parents if they don't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)
