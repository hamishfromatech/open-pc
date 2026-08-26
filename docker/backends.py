"""
Open-PC desktop backend abstraction.

Today the agent server runs inside the desktop container and drives the X11
display in-process through pyautogui/xdotool (``DesktopManager``). This module
defines the ``DesktopBackend`` contract so a future backend — e.g. the agent
server running on the host and driving a remote QEMU/KVM guest over vsock or
SSH, exactly like SmolVM's guest-agent model — can be swapped in behind the
same REST/WS surface without touching the API layer.

Backend selection mirrors SmolVM's ``runtime/backends.py``: ``resolve_backend``
probes the environment and returns a concrete adapter, raising a clear,
actionable error when the requested backend is unavailable.

Select a backend with ``OPENPC_BACKEND`` (``local`` default; ``remote`` is the
future QEMU/KVM path, not wired up yet).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

LOCAL_BACKEND = "local"
REMOTE_BACKEND = "remote"


@runtime_checkable
class DesktopBackend(Protocol):
    """The surface the agent server uses to drive a desktop.

    Structural typing (a ``Protocol``, not an ABC) — a concrete backend just
    needs to implement these methods. ``DesktopManager`` already conforms, so
    it is the local adapter with no changes.
    """

    backend: str

    def get_screen_info(self) -> Any: ...
    def take_screenshot(self) -> bytes: ...
    def take_screenshot_jpeg(self, quality: int = 80) -> bytes: ...
    def take_screenshot_base64(self) -> str: ...
    def take_screenshot_region(self, x: int, y: int, width: int, height: int) -> bytes: ...
    def mouse_move(self, x: int, y: int, duration: float = 0.0) -> Any: ...
    def mouse_click(self, x: int | None = None, y: int | None = None, *args: Any, **kw: Any) -> Any: ...
    def mouse_double_click(self, x: int | None = None, y: int | None = None) -> Any: ...
    def mouse_right_click(self, x: int | None = None, y: int | None = None) -> Any: ...
    def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5) -> Any: ...
    def mouse_scroll(self, clicks: int = 3, direction: str = "down", x: int | None = None, y: int | None = None) -> Any: ...
    def get_mouse_position(self) -> tuple[int, int]: ...
    def keyboard_type(self, text: str, interval: float = 0.05) -> Any: ...
    def keyboard_press(self, key: str) -> Any: ...
    def keyboard_hotkey(self, *keys: str) -> Any: ...
    def keyboard_key_down(self, key: str) -> Any: ...
    def keyboard_key_up(self, key: str) -> Any: ...
    def list_windows(self) -> list[Any]: ...
    def get_active_window(self) -> Any: ...
    def focus_window(self, window_id: str) -> Any: ...
    def close_window(self, window_id: str | None = None) -> Any: ...
    def maximize_window(self, window_id: str | None = None) -> Any: ...
    def minimize_window(self, window_id: str | None = None) -> Any: ...
    def launch_application(self, app_name: str) -> Any: ...
    def open_url(self, url: str, browser: str = "google-chrome") -> Any: ...
    def run_command(self, command: str, timeout: int = 30) -> Any: ...
    def ocr_screenshot(self, region: tuple[int, int, int, int] | None = None) -> Any: ...
    def locate_on_screen(self, image_path: str, confidence: float = 0.9) -> Any: ...
    def locate_on_screen_base64(self, image_b64: str, confidence: float = 0.9) -> Any: ...


@dataclass
class BackendStatus:
    """Probe result for a candidate backend (mirrors SmolVM's ``BackendStatus``)."""
    name: str
    available: bool
    detail: str = ""


def probe_local() -> BackendStatus:
    """Probe whether the in-process X11 desktop backend is usable."""
    try:
        from desktop_manager import DesktopManager  # local import: heavy (pyautogui)

        DesktopManager()  # constructor only verifies the display softly
        return BackendStatus(LOCAL_BACKEND, available=True, detail="in-process X11")
    except Exception as e:  # noqa: BLE001
        return BackendStatus(LOCAL_BACKEND, available=False, detail=str(e))


def probe_backends() -> list[BackendStatus]:
    """Probe every known backend, in preference order."""
    return [probe_local(), BackendStatus(REMOTE_BACKEND, available=False, detail="not implemented yet")]


def resolve_backend(backend: str | None = None) -> DesktopBackend:
    """Return a concrete ``DesktopBackend``.

    Selection order: explicit ``backend`` arg > ``OPENPC_BACKEND`` env > ``local``.
    Mirrors SmolVM's ``resolve_backend`` — raise a clear error rather than
    silently downgrading when the requested backend is unavailable.
    """
    chosen = backend or os.environ.get("OPENPC_BACKEND", LOCAL_BACKEND)

    if chosen == LOCAL_BACKEND:
        from desktop_manager import DesktopManager  # local adapter (in-process)

        dm = DesktopManager()
        dm.backend = LOCAL_BACKEND  # tag for introspection / /health
        return dm

    if chosen == REMOTE_BACKEND:
        raise SystemExit(
            f"The '{REMOTE_BACKEND}' desktop backend (QEMU/KVM over vsock or SSH) "
            f"is not implemented yet. Use OPENPC_BACKEND={LOCAL_BACKEND}."
        )

    raise SystemExit(
        f"Unknown backend '{chosen}'. Set OPENPC_BACKEND to one of: {LOCAL_BACKEND}, {REMOTE_BACKEND}."
    )


class RemoteDesktopBackend:
    """Future backend: drive a QEMU/KVM guest over vsock or SSH from the host.

    Not implemented yet — kept here to make the adapter seam concrete. When
    wired up, this would talk to a guest agent (like SmolVM's) instead of
    touching pyautogui in-process. Any operation raises a clear error so it
    can never be selected accidentally today.
    """

    backend = REMOTE_BACKEND

    def __init__(self) -> None:
        # Construct freely; operations fail loudly so the local backend is the
        # only one that actually does work until this is implemented.
        pass

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"Remote desktop backend does not implement '{name}' yet. "
            f"Use OPENPC_BACKEND=local (the in-process Docker desktop)."
        )
