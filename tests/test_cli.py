"""Tests for the openpc CLI's pure helpers and argument parser.

Only the pure, no-I/O pieces are exercised (the SmolVM "extract pure builders
so they're unit-testable without spawning the real thing" pattern). Commands
that shell out to docker or hit the network are not tested here.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import openpc


def test_rest_url_normalizes_leading_slash():
    assert openpc.rest_url(8090, "/screen") == "http://localhost:8090/screen"
    assert openpc.rest_url(8090, "screen") == "http://localhost:8090/screen"
    assert openpc.rest_url(9000, "/apps/run") == "http://localhost:9000/apps/run"


def test_build_compose_args():
    assert openpc.build_compose_args("docker compose", "up", "-d") == [
        "docker compose", "-f", "docker-compose.yml", "up", "-d",
    ]
    assert openpc.build_compose_args("docker-compose", "ps") == [
        "docker-compose", "-f", "docker-compose.yml", "ps",
    ]


def test_parser_status_aliases():
    for alias in ("status", "ps", "list"):
        ns = openpc.build_arg_parser().parse_args([alias])
        assert ns.command == alias


def test_parser_screenshot_defaults():
    ns = openpc.build_arg_parser().parse_args(["screenshot"])
    assert ns.path == "screen.png"
    assert ns.port == 8090


def test_parser_screenshot_custom():
    ns = openpc.build_arg_parser().parse_args(["screenshot", "out.png", "--port", "9000"])
    assert ns.path == "out.png"
    assert ns.port == 9000


def test_parser_run_captures_command_after_dashes():
    ns = openpc.build_arg_parser().parse_args(["run", "--", "echo", "hi"])
    assert ns.command == "run"
    assert ns.cmd == ["--", "echo", "hi"]
    assert ns.timeout == 30


def test_parser_exec_captures_command():
    ns = openpc.build_arg_parser().parse_args(["exec", "--", "ls", "-la"])
    assert ns.command == "exec"
    assert "ls" in ns.cmd and "-la" in ns.cmd


def test_resolve_service_alias_and_full():
    assert openpc._resolve_service("desktop") == openpc.DESKTOP_SERVICE
    assert openpc._resolve_service("dashboard") == openpc.DASHBOARD_SERVICE
    assert openpc._resolve_service("mcp") == openpc.MCP_SERVICE
    assert openpc._resolve_service(openpc.DESKTOP_SERVICE) == openpc.DESKTOP_SERVICE


def test_resolve_service_unknown_raises():
    import pytest
    with pytest.raises(SystemExit):
        openpc._resolve_service("nope")


def test_main_desktop_command_no_io():
    # `desktop` just prints URLs — no docker/network needed.
    assert openpc.main(["desktop"]) == 0
