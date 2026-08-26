#!/usr/bin/env python3
"""
openpc — a noun-verb CLI for Open-PC.

Wraps `docker compose` and the REST API so operators don't have to remember
service names, ports, and curl incantations. Mirrors SmolVM's `smolvm` CLI
discipline: noun-verb commands, one short help line each, exact recovery in
error messages.

Usage:
    python3 openpc.py <command> [args]
    ./openpc.py <command>            # after: chmod +x openpc.py

Commands:
    start [--build]    Start all Open-PC containers
    stop               Stop and remove containers
    restart            Restart containers
    status             Show running containers (alias: ps, list)
    logs [service]     Tail logs (service: desktop|dashboard|mcp; add -f to follow)
    shell              Open a shell in the desktop container
    exec -- <cmd...>   Run a command in the desktop container
    screenshot [path]  Save a desktop screenshot (default: screen.png)
    open-url <url>     Open a URL in the sandbox browser
    run -- <cmd...>    Run a shell command in the sandbox (via REST /apps/run)
    desktop            Print the noVNC web URL
    doctor             Diagnose docker, compose, and the REST API
    version            Print the CLI version
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence

APP_VERSION = "0.1.0"
COMPOSE_FILE = "docker-compose.yml"

DEFAULT_REST_PORT = 8090
DESKTOP_SERVICE = "open-pc-desktop"
DASHBOARD_SERVICE = "open-pc-dashboard"
MCP_SERVICE = "open-pc-mcp"
NOVNC_PORT = 6080

ALL_SERVICES = (DESKTOP_SERVICE, DASHBOARD_SERVICE, MCP_SERVICE)
SERVICE_ALIASES = {
    "desktop": DESKTOP_SERVICE,
    "dashboard": DASHBOARD_SERVICE,
    "mcp": MCP_SERVICE,
}


# --------------------------------------------------------------------------- #
# Pure helpers (no subprocess / no network) — unit-testable in CI.
# --------------------------------------------------------------------------- #

def rest_url(port: int, path: str) -> str:
    """Build a REST URL against the host-mapped agent port."""
    if not path.startswith("/"):
        path = "/" + path
    return f"http://localhost:{port}{path}"


def build_compose_args(compose_bin: str, *args: str) -> list[str]:
    """Build the argv for a `docker compose` invocation (pure)."""
    return [compose_bin, "-f", COMPOSE_FILE, *args]


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser (pure; no I/O)."""
    parser = argparse.ArgumentParser(
        prog="openpc",
        description="Open-PC: give AI its own computer.",
    )
    parser.add_argument(
        "--version", action="version", version=f"openpc {APP_VERSION}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="Start all Open-PC containers")
    p.add_argument("--build", action="store_true", help="Rebuild images before starting")

    sub.add_parser("stop", help="Stop and remove containers")
    sub.add_parser("restart", help="Restart containers")

    p = sub.add_parser("status", help="Show running containers")
    sub.add_parser("ps", help="Alias of status")
    sub.add_parser("list", help="Alias of status")

    p = sub.add_parser("logs", help="Tail logs")
    p.add_argument("service", nargs="?", default=DESKTOP_SERVICE, help="desktop|dashboard|mcp")
    p.add_argument("-f", "--follow", action="store_true", help="Follow log output")

    sub.add_parser("shell", help="Open a shell in the desktop container")

    p = sub.add_parser("exec", help="Run a command in the desktop container")
    p.add_argument("cmd", nargs=argparse.REMAINDER, help="Command (after --) to run")

    p = sub.add_parser("screenshot", help="Save a desktop screenshot")
    p.add_argument("path", nargs="?", default="screen.png", help="Output file path")
    p.add_argument("--port", type=int, default=DEFAULT_REST_PORT, help="Host REST port")

    p = sub.add_parser("open-url", help="Open a URL in the sandbox browser")
    p.add_argument("url", help="URL to open")
    p.add_argument("--port", type=int, default=DEFAULT_REST_PORT, help="Host REST port")

    p = sub.add_parser("run", help="Run a shell command in the sandbox via REST")
    p.add_argument("cmd", nargs=argparse.REMAINDER, help="Command (after --) to run")
    p.add_argument("--port", type=int, default=DEFAULT_REST_PORT, help="Host REST port")
    p.add_argument("--timeout", type=int, default=30, help="Command timeout (seconds)")

    sub.add_parser("desktop", help="Print the noVNC web URL")
    sub.add_parser("doctor", help="Diagnose docker, compose, and the REST API")
    return parser


# --------------------------------------------------------------------------- #
# Runtime helpers (subprocess / network).
# --------------------------------------------------------------------------- #

def _detect_compose_bin() -> str:
    """Return a working compose invocation (prefers `docker compose` v2)."""
    for candidate in (("docker", "compose"), ("docker-compose",)):
        try:
            subprocess.run(
                [*candidate, "version"], capture_output=True, timeout=10,
            )
            return " ".join(candidate)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    raise SystemExit(
        "docker compose not found. Install Docker (with Compose v2) and retry."
    )


def run_compose(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a `docker compose` subcommand, streaming output to the terminal."""
    compose_bin = _detect_compose_bin()
    argv = build_compose_args(compose_bin, *args)
    return subprocess.run(argv, check=False, capture_output=capture, text=not capture)


def _rest_token() -> str:
    return os.environ.get("OPENPC_TOKEN", os.environ.get("REST_AUTH_TOKEN", ""))


def _rest_headers() -> dict[str, str]:
    token = _rest_token()
    return {"X-OpenPC-Token": token} if token else {}


def rest_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers=_rest_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def rest_post_json(url: str, body: dict, timeout: int = 15) -> dict:
    data = json.dumps(body).encode()
    headers = {**_rest_headers(), "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"REST request failed ({e.code}): {detail}") from e


def _resolve_service(name: str) -> str:
    if name in SERVICE_ALIASES:
        return SERVICE_ALIASES[name]
    if name in ALL_SERVICES:
        return name
    raise SystemExit(f"Unknown service '{name}'. Choose from: desktop, dashboard, mcp.")


# --------------------------------------------------------------------------- #
# Commands.
# --------------------------------------------------------------------------- #

def cmd_start(args) -> int:
    extra = ["--build"] if args.build else []
    run_compose("up", "-d", *extra)
    print("Open-PC starting. Dashboard: http://localhost:8092  noVNC: http://localhost:6080")
    return 0


def cmd_stop(args) -> int:
    run_compose("down")
    return 0


def cmd_restart(args) -> int:
    run_compose("restart")
    return 0


def cmd_status(args) -> int:
    run_compose("ps")
    return 0


def cmd_logs(args) -> int:
    svc = _resolve_service(args.service)
    extra = ["--follow"] if args.follow else []
    run_compose("logs", svc, *extra)
    return 0


def cmd_shell(args) -> int:
    # Interactive: inherit the TTY.
    compose_bin = _detect_compose_bin()
    argv = build_compose_args(compose_bin, "exec", DESKTOP_SERVICE, "bash")
    return subprocess.run(argv).returncode


def cmd_exec(args) -> int:
    cmd = [c for c in args.cmd if c != "--"]
    if not cmd:
        raise SystemExit("No command given. Usage: openpc exec -- <command...>")
    compose_bin = _detect_compose_bin()
    argv = build_compose_args(compose_bin, "exec", DESKTOP_SERVICE, *cmd)
    return subprocess.run(argv).returncode


def cmd_screenshot(args) -> int:
    url = rest_url(args.port, "/screenshot")
    png = rest_get(url, timeout=30)
    with open(args.path, "wb") as f:
        f.write(png)
    print(f"Saved screenshot to {args.path} ({len(png)} bytes)")
    return 0


def cmd_open_url(args) -> int:
    url = rest_url(args.port, "/apps/open-url")
    result = rest_post_json(url, {"url": args.url}, timeout=15)
    if not result.get("success"):
        raise SystemExit(f"Failed to open URL: {result.get('error', 'unknown error')}")
    print(f"Opened {args.url}")
    return 0


def cmd_run(args) -> int:
    cmd = [c for c in args.cmd if c != "--"]
    if not cmd:
        raise SystemExit("No command given. Usage: openpc run -- <command...>")
    url = rest_url(args.port, "/apps/run")
    result = rest_post_json(url, {"command": " ".join(cmd), "timeout": args.timeout}, timeout=args.timeout + 10)
    if result.get("stdout"):
        sys.stdout.write(result["stdout"])
    if result.get("stderr"):
        sys.stderr.write(result["stderr"])
    return int(result.get("return_code", 1)) if result.get("success") is False else 0


def cmd_desktop(args) -> int:
    print(f"noVNC web URL: http://localhost:{NOVNC_PORT}")
    print("Dashboard:     http://localhost:8092")
    return 0


def cmd_doctor(args) -> int:
    failures = 0

    def check(name, ok, detail=""):
        nonlocal failures
        status = "OK" if ok else "FAIL"
        print(f"  {name}: {status}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures += 1

    print("Open-PC doctor")
    docker = shutil.which("docker")
    check("docker", bool(docker), docker or "not on PATH")
    compose_bin = _detect_compose_bin() if docker else ""
    check("docker compose", bool(compose_bin), compose_bin or "compose unavailable")
    # REST health
    try:
        body = rest_get(rest_url(DEFAULT_REST_PORT, "/health"), timeout=5)
        health = json.loads(body)
        check("agent REST /health", health.get("status") == "healthy", str(health))
    except Exception as e:  # noqa: BLE001
        check("agent REST /health", False, str(e))
    print("Done." if not failures else f"{failures} check(s) failed.")
    return 1 if failures else 0


COMMANDS = {
    "start": cmd_start,
    "stop": cmd_stop,
    "restart": cmd_restart,
    "status": cmd_status,
    "ps": cmd_status,
    "list": cmd_status,
    "logs": cmd_logs,
    "shell": cmd_shell,
    "exec": cmd_exec,
    "screenshot": cmd_screenshot,
    "open-url": cmd_open_url,
    "run": cmd_run,
    "desktop": cmd_desktop,
    "doctor": cmd_doctor,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command)
    if handler is None:  # pragma: no cover - argparse enforces required subcommand
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
