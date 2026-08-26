"""
Open-PC I/O helpers: atomic file writes.

``atomic_write_*`` writes to a sibling temp file, fsyncs, then renames over the
target so a reader never observes a half-written file and a crash never leaves a
corrupt final file. Staged here for upcoming persistent outputs (screenshot
save-to-disk, session files).

Inspired by SmolVM's ``disk.rs``, which writes to a sibling ``.tmp`` and
``rename(2)``s atomically for every produced file.
"""
from __future__ import annotations

import os
from pathlib import Path


def atomic_write_bytes(path: str | os.PathLike, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically: temp file -> fsync -> rename."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_text(path: str | os.PathLike, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` atomically."""
    atomic_write_bytes(path, text.encode(encoding))
