"""End-to-end API tests for the Open-PC agent server (FastAPI TestClient).

These run without a real X11 display thanks to the pyautogui mock in conftest.
They validate the high-value behaviours: routing, the slowapi rate-limit fix
(a broken /screenshot would 500), run_command sanitization, and the REST token
auth middleware.
"""
import agent_server
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with TestClient(agent_server.app) as c:
        yield c


# ----------------------------- basic routing -----------------------------

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "Open-PC Agent Server"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "display" in body


def test_screen_info(client):
    r = client.get("/screen")
    assert r.status_code == 200
    info = r.json()
    assert info["width"] == 1920 and info["height"] == 1080


# ----------------------------- slowapi rate-limit fix -----------------------------
# Before the fix these endpoints 500'd because they lacked `request: Request`.

def test_screenshot_png(client):
    r = client.get("/screenshot")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 0


def test_screenshot_base64(client):
    r = client.get("/screenshot/base64")
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert r.json()["image"]


def test_screenshot_region(client):
    r = client.get("/screenshot/region", params={"x": 0, "y": 0, "width": 100, "height": 100})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


# ----------------------------- mouse/keyboard -----------------------------

def test_mouse_click(client):
    r = client.post("/mouse/click", json={"x": 10, "y": 20, "button": "left"})
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_mouse_position(client):
    r = client.get("/mouse/position")
    assert r.status_code == 200
    assert "x" in r.json() and "y" in r.json()


def test_keyboard_type(client):
    r = client.post("/keyboard/type", json={"text": "hello"})
    assert r.status_code == 200
    assert r.json()["success"] is True


# ----------------------------- run_command sanitization -----------------------------

def test_run_command_dangerous_blocked(client):
    r = client.post("/apps/run", json={"command": "ls; rm -rf /"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "blocked" in body["error"].lower()


def test_run_command_safe_executes(client):
    # echo is harmless and present on CI; should run and succeed
    r = client.post("/apps/run", json={"command": "echo openpc", "timeout": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "openpc" in body["stdout"]


# ----------------------------- batch -----------------------------

def test_batch_wait(client):
    r = client.post("/batch", json={"steps": [{"type": "wait", "parameters": {"seconds": 0.01}}]})
    assert r.status_code == 200
    assert r.json()["success"] is True


# ----------------------------- REST token auth -----------------------------

def test_auth_exempt_endpoints_open(client):
    # /health and / are always open even when a token is configured
    agent_server.REST_AUTH_TOKEN = "secret-token"
    try:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 200
    finally:
        agent_server.REST_AUTH_TOKEN = ""


def test_auth_blocks_without_token(client):
    agent_server.REST_AUTH_TOKEN = "secret-token"
    try:
        r = client.get("/screenshot")
        assert r.status_code == 401
    finally:
        agent_server.REST_AUTH_TOKEN = ""


def test_auth_allows_with_token_header(client):
    agent_server.REST_AUTH_TOKEN = "secret-token"
    try:
        r = client.get("/screenshot", headers={"X-OpenPC-Token": "secret-token"})
        assert r.status_code == 200
    finally:
        agent_server.REST_AUTH_TOKEN = ""


def test_auth_allows_with_bearer_header(client):
    agent_server.REST_AUTH_TOKEN = "secret-token"
    try:
        r = client.get("/screenshot", headers={"Authorization": "Bearer secret-token"})
        assert r.status_code == 200
    finally:
        agent_server.REST_AUTH_TOKEN = ""


def test_auth_allows_with_query_token(client):
    # The MJPEG <img> stream can't set headers, so ?token= must also work
    agent_server.REST_AUTH_TOKEN = "secret-token"
    try:
        r = client.get("/screen", params={"token": "secret-token"})
        assert r.status_code == 200
    finally:
        agent_server.REST_AUTH_TOKEN = ""


def test_auth_rejects_wrong_token(client):
    agent_server.REST_AUTH_TOKEN = "secret-token"
    try:
        r = client.get("/screenshot", headers={"X-OpenPC-Token": "wrong"})
        assert r.status_code == 401
    finally:
        agent_server.REST_AUTH_TOKEN = ""
