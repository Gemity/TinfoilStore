"""Tests for orchestrator.fileutil - atomic writes and hashing."""

import hashlib
from pathlib import Path

from orchestrator.fileutil import atomic_write, compute_sha256


class TestAtomicWrite:
    def test_creates_file(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        atomic_write(target, "hello world")
        assert target.read_text() == "hello world"

    def test_overwrites_existing(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        target.write_text("old")
        atomic_write(target, "new")
        assert target.read_text() == "new"

    def test_creates_parent_dirs(self, tmp_path: Path):
        target = tmp_path / "sub" / "dir" / "test.txt"
        atomic_write(target, "data")
        assert target.read_text() == "data"

    def test_no_temp_file_left(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        atomic_write(target, "data")
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "test.txt"


class TestComputeSha256:
    def test_known_hash(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        content = "hello world"
        target.write_text(content, encoding="utf-8")
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert compute_sha256(target) == expected

    def test_empty_file(self, tmp_path: Path):
        target = tmp_path / "empty.txt"
        target.write_text("", encoding="utf-8")
        expected = hashlib.sha256(b"").hexdigest()
        assert compute_sha256(target) == expected
