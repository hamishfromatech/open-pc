"""Tests for the semantic desktop control backend (cua-driver based).

These run without a real X11 display thanks to the fake pyautogui installed in
conftest, and without a real CuaDriver by exercising the degradation paths.
"""
import pytest

from docker.semantic_backend import (
    CuaDriverUnavailable,
    SemanticBackend,
    ElementDetail,
    ElementInfo,
    ScreenInfo,
    ActionResult,
)


# ---------------------------------------------------------------------------
# Screen / geometry
# ---------------------------------------------------------------------------

def test_semantic_backend_defaults_to_local_driver():
    """Default backend targets the local driver URL."""
    backend = SemanticBackend()
    assert backend.driver.driver_url == "http://127.0.0.1:8888"


def test_semantic_backend_screen_info_defaults():
    backend = SemanticBackend()
    info = backend.get_screen_info()
    assert isinstance(info, ScreenInfo)
    assert info.width > 0
    assert info.height > 0


# ---------------------------------------------------------------------------
# Degradation: driver unavailable
# ---------------------------------------------------------------------------

def test_semantic_backend_unavailable_raises():
    backend = SemanticBackend(driver_url="http://127.0.0.1:1")
    with pytest.raises(CuaDriverUnavailable):
        backend.get_element_tree()
    with pytest.raises(CuaDriverUnavailable):
        backend.click("any-element")
    with pytest.raises(CuaDriverUnavailable):
        backend.set_value("any-element", "value")
    with pytest.raises(CuaDriverUnavailable):
        backend.read_text("any-element")
    with pytest.raises(CuaDriverUnavailable):
        backend.semantic_status()


def test_semantic_backend_unavailable_status_is_false():
    backend = SemanticBackend(driver_url="http://127.0.0.1:1")
    status = backend.semantic_status()
    assert status.enabled is False
    assert status.reachable is False
    assert status.error is not None


def test_semantic_backend_unavailable_is_raised_from_driver():
    # The client should surface the driver-unavailable error, not a generic
    # RuntimeError, so callers get an actionable message.
    backend = SemanticBackend(driver_url="http://127.0.0.1:1")
    with pytest.raises(CuaDriverUnavailable) as exc_info:
        backend.get_element_tree(app="test", window="test")
    assert "CuaDriver" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Element tree normalization
# ---------------------------------------------------------------------------

def test_get_element_tree_normalizes_dto():
    backend = SemanticBackend()
    tree = backend.get_element_tree(app="xfce4-files", window="files")
    assert isinstance(tree, list)
    assert len(tree) > 0
    for info in tree:
        assert isinstance(info, ElementInfo)
        assert info.element_id
        assert info.role
        assert info.app
        assert info.children_count >= 0


def test_get_element_tree_by_id_returns_none_when_not_found():
    backend = SemanticBackend()
    detail = backend.get_element_tree_by_id("does-not-exist")
    assert detail is None


def test_get_element_detail_normalizes_dto():
    backend = SemanticBackend()
    detail = backend.get_element_detail("element-1")
    assert isinstance(detail, ElementDetail)
    assert detail.element_id
    assert detail.role
    assert detail.app
    assert detail.bbox is None or isinstance(detail.bbox, list)
    assert detail.children_count >= 0


def test_click_action_result_normalization():
    backend = SemanticBackend()
    result = backend.click("element-1")
    assert isinstance(result, ActionResult)
    assert isinstance(result, ActionResult)
    # A successful click yields ok=True
    assert result.ok is True


def test_read_text_normalizes_dto():
    backend = SemanticBackend()
    text = backend.read_text("element-1")
    assert isinstance(text, str)
    assert text == "" or len(text) > 0


# ---------------------------------------------------------------------------
# Dependency / API contract
# ---------------------------------------------------------------------------

def test_semantic_backend_is_available_with_driver():
    """When the driver is reachable, the backend reports it as available."""
    backend = SemanticBackend()
    assert backend.is_available() is True


def test_semantic_backend_unavailable_is_false():
    backend = SemanticBackend(driver_url="http://127.0.0.1:1")
    assert backend.is_available() is False


# ---------------------------------------------------------------------------
# Degradation: client-level errors
# ---------------------------------------------------------------------------

def test_driver_unavailable_raises_client_error():
    backend = SemanticBackend()
    # The client must raise CuaDriverUnavailable, not a raw RuntimeError.
    with pytest.raises(CuaDriverUnavailable):
        backend.driver.click("element-1")
