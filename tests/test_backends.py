"""Tests for the desktop backend abstraction (adapter seam).

Mirrors SmolVM's adapter/selection pattern: a Protocol the manager conforms to,
a resolve_backend() selection seam, and fail-fast on an unavailable backend.
Uses the fake pyautogui installed in conftest, so no real display is needed.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "docker"))

import pytest
from backends import (
    LOCAL_BACKEND,
    REMOTE_BACKEND,
    DesktopBackend,
    RemoteDesktopBackend,
    probe_backends,
    probe_local,
    resolve_backend,
)
from desktop_manager import DesktopManager


def test_desktop_manager_satisfies_protocol():
    # Structural typing: DesktopManager implements the DesktopBackend surface.
    assert isinstance(DesktopManager(), DesktopBackend)


def test_resolve_backend_default_is_local():
    old = os.environ.pop("OPENPC_BACKEND", None)
    try:
        b = resolve_backend()
    finally:
        if old is not None:
            os.environ["OPENPC_BACKEND"] = old
    assert isinstance(b, DesktopManager)
    assert b.backend == LOCAL_BACKEND


def test_resolve_backend_explicit_local():
    assert isinstance(resolve_backend(LOCAL_BACKEND), DesktopManager)


def test_resolve_backend_remote_not_implemented_yet():
    # Fail fast (SmolVM: raise rather than silently downgrade).
    with pytest.raises(SystemExit):
        resolve_backend(REMOTE_BACKEND)


def test_resolve_backend_unknown_raises():
    with pytest.raises(SystemExit):
        resolve_backend("kvm")


def test_resolve_backend_env_override():
    old = os.environ.get("OPENPC_BACKEND")
    os.environ["OPENPC_BACKEND"] = "kvm"
    try:
        with pytest.raises(SystemExit):
            resolve_backend()
    finally:
        if old is None:
            os.environ.pop("OPENPC_BACKEND", None)
        else:
            os.environ["OPENPC_BACKEND"] = old


def test_probe_local_available():
    s = probe_local()
    assert s.name == LOCAL_BACKEND
    assert s.available is True


def test_probe_backends_lists_both():
    names = [s.name for s in probe_backends()]
    assert names == [LOCAL_BACKEND, REMOTE_BACKEND]


def test_remote_skeleton_fails_loudly():
    # The future remote backend skeleton must not silently do nothing.
    rb = RemoteDesktopBackend()
    with pytest.raises(NotImplementedError):
        rb.take_screenshot()
