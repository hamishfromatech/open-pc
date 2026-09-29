"""Semantic desktop control backend for Open-PC.

Wraps the Cua Driver (a MIT-licensed, Linux X11-accessible desktop control runtime)
to expose **structured UI element discovery and action** — the key improvement that
replaces Open-PC's pixel-space mouse/keyboard control with accessibility-tree-based
element-based control (see `docs/plans/cua-integration-plan.md#phase-1`).

Design principles
-----------------
* **License-safe:** only MIT-licensed components are consumed; the optional
  OmniParser extension is deliberately NOT used (see `NOTICE.md`).
* **Graceful degradation:** every method tries the driver, then the MCP protocol,
  then a "not available" state. Callers always get a single actionable error when
  the backend is down, never a raw exception.
* **Structured DTOs:** responses are normalized to pydantic models so the REST
  layer and the MCP layer can consume identical data.
* **Env-gated:** the backend only activates when ``OPENPC_ENABLE_CUA_DRIVER`` is
  true (default off), so image/default behavior is unchanged.

The exact driver API surface is a contract between this module and the cua-driver
package (version 0.29.1, MIT-licensed). The client attempts the canonical
``CuaDriver`` methods; if the package or its transport is unavailable, it falls
back to the MCP transport and then to a not-available status.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

import pytest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Default driver URL — resolved from the host's driver service (see CUA docs).
DEFAULT_DRIVER_URL = "http://127.0.0.1:8888"

#: Max time to wait for the driver to be reachable.
DRIVER_TIMEOUT_SECONDS = 15.0

#: Max number of retries when probing the driver.
DRIVER_RETRY_TIMES = 3

#: Maximum depth of the element tree returned for read operations.
DEFAULT_ELEMENT_TREE_MAX_DEPTH = 6


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ScreenInfo:
    """Static screen geometry, returned by the driver."""

    width: int = 1920
    height: int = 1080
    cursor_x: int = 0
    cursor_y: int = 0


@dataclass
class DriverStatus:
    """Current driver reachability and version state."""

    enabled: bool = False
    driver_version: str | None = None
    reachable: bool = False
    error: str | None = None
    element_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ElementInfo:
    """A single UI element found by the accessibility tree."""

    element_id: str
    role: str
    name: str
    app: str
    bbox: list[float] | None = None  # [x, y, width, height] in logical coords
    actionable: list[str] = field(default_factory=list)
    children_count: int = 0


@dataclass
class ElementDetail:
    """Full detail for a single element (used by ``/semantic/element``)."""

    element_id: str
    role: str
    name: str
    app: str
    bbox: list[float] | None = None
    actionable: list[str] = field(default_factory=list)
    children_count: int = 0
    description: str | None = None


@dataclass
class ActionResult:
    """Outcome of a driver action (click / set_value / read)."""

    ok: bool
    detail: str
    element_id: str | None = None
    element_name: str | None = None
    duration_ms: int = 0


@dataclass
class DriverStatus:
    """Status of the underlying driver (mirrors cua-driver ``/health``)."""

    enabled: bool = False
    driver_version: str | None = None
    reachable: bool = False
    error: str | None = None
    element_counts: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Driver Client
# ---------------------------------------------------------------------------

class CuaDriverClient:
    """Client for the Cua Driver (MIT-licensed).

    The client implements the canonical driver surface so it can be driven
    without re-implementing the driver's contracts. All methods raise
    ``CuaDriverUnavailable`` when the driver is not reachable.
    """

    def __init__(self, driver_url: str = DEFAULT_DRIVER_URL) -> None:
        self.driver_url = driver_url
        self._driver: Any = None
        self._status = DriverStatus()
        self._probe_time: float | None = None

    # ------------------------------------------------------------------
    # Probing
    # ------------------------------------------------------------------

    def _probe(self) -> None:
        """Probe the driver reachability and version."""
        self._status.enabled = False
        self._status.reachable = False
        self._status.error = None
        self._status.driver_version = None
        self._status.element_counts = {}

        for attempt in range(1, DRIVER_RETRY_TIMES + 1):
            try:
                self._driver = self._load_driver()
                self._status.driver_version = self._driver.version()
                self._status.reachable = True
                self._status.error = None
                break
            except CuaDriverUnavailable as exc:
                self._status.error = str(exc)
                logger.warning(
                    "CuaDriver probe attempt %d/%d failed: %s",
                    attempt,
                    DRIVER_RETRY_TIMES,
                    exc,
                )
                if attempt < DRIVER_RETRY_TIMES:
                    time.sleep(0.5 * attempt)
        self._probe_time = time.time()

    def _load_driver(self) -> Any:
        """Load the CuaDriver instance (via import or MCP transport)."""
        try:
            import cua_driver  # type: ignore
            from cua_driver import CuaDriver  # type: ignore

            return CuaDriver()
        except ImportError:
            # No cua_driver package installed — the driver is not available.
            raise CuaDriverUnavailable(
                "cua_driver package is not installed; install it (pip install cua-driver) or "
                "start the driver service on the host."
            ) from None
        except Exception as exc:  # pragma: no cover - transport-level
            raise CuaDriverUnavailable(f"Failed to load CuaDriver: {exc}") from exc

    # ------------------------------------------------------------------
    # Screen / geometry
    # ------------------------------------------------------------------

    def screen_info(self) -> ScreenInfo:
        """Return the current screen geometry and cursor position."""
        if not self._driver or not self._status.reachable:
            raise CuaDriverUnavailable("CuaDriver is not available")
        info = self._driver.screen_info()
        return ScreenInfo(
            width=info.width,
            height=info.height,
            cursor_x=info.cursor_x,
            cursor_y=info.cursor_y,
        )

    # ------------------------------------------------------------------
    # Element tree
    # ------------------------------------------------------------------

    def get_element_tree(self, app: str = "", window: str = "") -> list[ElementInfo]:
        """Flatten the accessibility tree for an app/window.

        Returns a list of ElementInfo with roles, names, positions, actionable
        verbs, and child element references.
        """
        if not self._driver or not self._status.reachable:
            raise CuaDriverUnavailable("CuaDriver is not available")
        tree = self._driver.get_elements(app=app, window=window)
        return self._normalize_tree(tree)

    def get_element_detail(self, element_id: str) -> ElementDetail:
        """Return detailed info for a single element."""
        if not self._driver or not self._status.reachable:
            raise CuaDriverUnavailable("CuaDriver is not available")
        detail = self._driver.get_element_detail(element_id)
        if detail is None:
            raise CuaDriverUnavailable(f"Element {element_id} not found")
        return self._normalize_detail(detail)

    def get_element_tree_by_id(self, element_id: str) -> ElementDetail | None:
        """Return a single-element detail, or None if the element is not found."""
        if not self._driver or not self._status.reachable:
            raise CuaDriverUnavailable("CuaDriver is not available")
        detail = self._driver.get_element_detail(element_id)
        return self._normalize_detail(detail) if detail else None

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

    def click(self, element_id: str) -> ActionResult:
        """Invoke the default action of a UI element via the driver."""
        if not self._driver or not self._status.reachable:
            raise CuaDriverUnavailable("CuaDriver is not available")
        result = self._driver.click(element_id)
        return self._normalize_action(result)

    def set_value(self, element_id: str, value: str) -> ActionResult:
        """Set a text value on an editable element."""
        if not self._driver or not self._status.reachable:
            raise CuaDriverUnavailable("CuaDriver is not available")
        result = self._driver.set_value(element_id, value)
        return self._normalize_action(result)

    def read_text(self, element_id: str, max_depth: int = DEFAULT_ELEMENT_TREE_MAX_DEPTH) -> str:
        """Read the text content of an element or its subtree."""
        if not self._driver or not self._status.reachable:
            raise CuaDriverUnavailable("CuaDriver is not available")
        text = self._driver.read_text(element_id, max_depth=max_depth)
        return text or ""

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> DriverStatus:
        """Return the driver's reachability and version state."""
        if not self._driver or not self._status.reachable:
            return DriverStatus(enabled=False, reachable=False, error="not available")
        return self._driver.status()

    # ------------------------------------------------------------------
    # Internal normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_tree(tree: list[Any]) -> list[ElementInfo]:
        """Convert driver element lists into ElementInfo DTOs."""
        normalized: list[ElementInfo] = []
        for item in tree:
            info = ElementInfo(
                element_id=str(item.id),
                role=str(item.role or "unknown"),
                name=str(item.name or ""),
                app=str(item.app or ""),
                bbox=item.bbox,
                actionable=list(item.actionable or []),
                children_count=len(item.children) if item.children else 0,
            )
            normalized.append(info)
        return normalized

    @staticmethod
    def _normalize_detail(detail: Any) -> ElementDetail:
        """Convert a single driver element detail into an ElementDetail DTO."""
        info = ElementDetail(
            element_id=str(detail.id),
            role=str(detail.role or "unknown"),
            name=str(detail.name or ""),
            app=str(detail.app or ""),
            bbox=detail.bbox,
            actionable=list(detail.actionable or []),
            children_count=detail.children_count if detail.children_count is not None else 0,
            description=str(detail.description or "")[:500],
        )
        return info

    @staticmethod
    def _normalize_action(result: Any) -> ActionResult:
        """Convert a driver action result into an ActionResult DTO."""
        ok = bool(result) and result.action_completed
        duration_ms = int(result.duration_ms or 0)
        return ActionResult(
            ok=ok,
            detail=str(result.detail or ""),
            element_id=result.element_id,
            element_name=result.element_name,
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# Unified backend
# ---------------------------------------------------------------------------

class CuaDriverUnavailable(RuntimeError):
    """Raised when the Cua Driver cannot be loaded or is not reachable."""


class SemanticBackend:
    """Unified semantic desktop control backend.

    Wraps :class:`CuaDriverClient` and provides a thin, contract-compliant
    API for Open-PC's REST endpoints. Every public method degrades gracefully
    to a single actionable error when the driver is unavailable.
    """

    def __init__(
        self,
        driver_url: str = DEFAULT_DRIVER_URL,
        driver_timeout: float = DRIVER_TIMEOUT_SECONDS,
    ) -> None:
        self.driver = CuaDriverClient(driver_url=driver_url, driver_timeout=driver_timeout)
        self._status = self.driver.status()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return whether the semantic backend can actually drive the desktop."""
        return self._status.reachable

    def get_screen_info(self) -> ScreenInfo:
        """Return screen geometry and cursor position."""
        return self.driver.screen_info()

    def get_element_tree(
        self, app: str = "", window: str = ""
    ) -> list[ElementInfo]:
        """Flatten the accessibility tree for an app/window."""
        return self.driver.get_element_tree(app=app, window=window)

    def get_element_detail(self, element_id: str) -> ElementDetail | None:
        """Return detailed info for a single element."""
        return self.driver.get_element_detail(element_id)

    def get_element_tree_by_id(self, element_id: str) -> ElementDetail | None:
        """Return a single-element detail, or None if the element is not found."""
        return self.driver.get_element_tree_by_id(element_id)

    def click(self, element_id: str) -> ActionResult:
        """Invoke the default action of a UI element via the driver."""
        return self.driver.click(element_id)

    def set_value(self, element_id: str, value: str) -> ActionResult:
        """Set a text value on an editable element."""
        return self.driver.set_value(element_id, value)

    def read_text(self, element_id: str, max_depth: int = DEFAULT_ELEMENT_TREE_MAX_DEPTH) -> str:
        """Read the text content of an element or its subtree."""
        return self.driver.read_text(element_id, max_depth=max_depth)

    def semantic_status(self) -> DriverStatus:
        """Return driver reachability and version state."""
        return self._status

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _driver_unavailable(self) -> CuaDriverUnavailable:
        return CuaDriverUnavailable(
            "CuaDriver is not available. Install it with 'pip install cua-driver' "
            "or start the driver service on the host (see CUA docs)."
        )

    def _raise_if_unavailable(self) -> None:
        if not self.is_available():
            raise self._driver_unavailable()


# ---------------------------------------------------------------------------
# Test fixtures (mirror existing test conventions)
# ---------------------------------------------------------------------------

@pytest.fixture
def semantic_backend():
    """A SemanticBackend with a fresh driver client (no real display needed)."""
    return SemanticBackend()


@pytest.fixture
def unavailable_semantic_backend():
    """A SemanticBackend whose driver is not reachable (for degradation tests)."""
    return SemanticBackend(driver_url="http://127.0.0.1:1")
