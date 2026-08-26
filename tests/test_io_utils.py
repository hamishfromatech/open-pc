"""Tests for atomic file-write helpers."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'docker'))

from io_utils import atomic_write_bytes, atomic_write_text


def test_atomic_write_bytes_roundtrip(tmp_path):
    p = tmp_path / "out.bin"
    atomic_write_bytes(p, b"hello")
    assert p.read_bytes() == b"hello"
    # no leftover temp file
    assert not (tmp_path / "out.bin.tmp").exists()


def test_atomic_write_text_roundtrip(tmp_path):
    p = tmp_path / "out.txt"
    atomic_write_text(p, "héllo\n")
    assert p.read_text(encoding="utf-8") == "héllo\n"


def test_atomic_write_overwrites_atomically(tmp_path):
    p = tmp_path / "out.bin"
    atomic_write_bytes(p, b"old")
    atomic_write_bytes(p, b"new")
    assert p.read_bytes() == b"new"
    assert not (tmp_path / "out.bin.tmp").exists()
